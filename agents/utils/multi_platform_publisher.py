"""
Multi-Platform Publisher Agent
Handles uploads to YouTube, TikTok, Instagram, and Facebook with retry, idempotency, and token refresh.
Run: python -m agents.scripts.publisher --title "..." --video_path "..." --platforms youtube,tiktok
"""
import os
import time
import uuid
from datetime import datetime
from utils.firebase_status import get_firestore_client, log_activity, update_video_record
from compliance.ai_disclosure import get_ai_disclosure
from utils.sanitize import safe_log
from utils.platform_captions import optimize_for_platform, optimize_title_for_platform
from utils.subprocess_helper import (retry_with_backoff, rate_limiter, security_audit, safe_run,
                                    register_temp_dir, NonRetryableError)

_FACEBOOK_CRF = os.getenv("FACEBOOK_CRF", "30")
# Above this size we use Meta's 3-phase resumable upload instead of a single
# multipart POST. Module constant (not an inline literal) so tests can force the
# resumable path with a small file -- otherwise exercising the protocol needs a
# real 50MB+ upload every time.
_FB_RESUMABLE_THRESHOLD = 50 * 1024 * 1024
# Chunk size for each 'transfer' call. 5MB is a safe per-request payload; the
# upload's overall size is driven by Meta's returned next-offset, not by this.
_FB_CHUNK_BYTES = 5 * 1024 * 1024
_FACEBOOK_TEMP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "facebook"
)
os.makedirs(_FACEBOOK_TEMP_DIR, exist_ok=True)
register_temp_dir(_FACEBOOK_TEMP_DIR)

_INSTAGRAM_TEMP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "instagram"
)
os.makedirs(_INSTAGRAM_TEMP_DIR, exist_ok=True)
register_temp_dir(_INSTAGRAM_TEMP_DIR)

IG_REELS_MAX_SECONDS = 90


def _compress_for_facebook(video_path: str) -> str:
    """Compress video for Facebook upload to reduce processing timeouts.
    
    Uses lower CRF (higher compression) than the master render since Facebook
    re-encodes videos anyway. Returns path to compressed temp file.
    """
    # self-heal: the 04:00 UTC cleanup_local_files() rmdir's empty tmp/ subdirs
    # and this one is always empty after upload, so module-import-only makedirs
    # left ffmpeg writing to a deleted dir -> fell back to the uncompressed
    # original -> "Video Upload Time Out" (subcode 1363030). Same bug+fix as
    # viral_news.generate_image().
    os.makedirs(_FACEBOOK_TEMP_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]
    out_path = os.path.join(_FACEBOOK_TEMP_DIR, f"{base}_fb.mp4")
    original_size = os.path.getsize(video_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", _FACEBOOK_CRF,
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        out_path,
    ]
    result = safe_run(cmd, timeout=300, capture_output=True, text=True)
    if result.returncode != 0:
        log_activity('publisher', f"Facebook compression failed, falling back to original: {result.stderr[-200:]}", 'warn')
        return video_path

    compressed_size = os.path.getsize(out_path)
    ratio = compressed_size / original_size if original_size else 1
    log_activity(
        'publisher',
        f"Facebook compression: {original_size // 1024}KB → {compressed_size // 1024}KB ({ratio:.0%})",
        'info',
    )
    return out_path


def _get_video_duration_ffprobe(video_path: str) -> float:
    try:
        result = safe_run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            timeout=30, capture_output=True, text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _trim_for_instagram(video_path: str, max_seconds: float = IG_REELS_MAX_SECONDS) -> str:
    # self-heal: see _compress_for_facebook -- tmp/ subdirs are rmdir'd by the
    # daily cleanup, so module-import-only makedirs is not enough.
    os.makedirs(_INSTAGRAM_TEMP_DIR, exist_ok=True)
    duration = _get_video_duration_ffprobe(video_path)
    if duration <= max_seconds:
        return video_path
    base = os.path.splitext(os.path.basename(video_path))[0]
    out_path = os.path.join(_INSTAGRAM_TEMP_DIR, f"{base}_ig_trim.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-t", str(max_seconds),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    result = safe_run(cmd, timeout=120, capture_output=True, text=True)
    if result.returncode != 0:
        log_activity('publisher', f"Instagram trim failed, using original: {result.stderr[-200:]}", 'warn')
        return video_path
    trimmed_size = os.path.getsize(out_path)
    log_activity('publisher', f"Instagram trim: {duration:.1f}s → {max_seconds}s ({trimmed_size // 1024}KB)", 'info')
    return out_path


PLATFORMS = {
    'youtube': {
        'name': 'YouTube',
        'icon': '🔴',
        'color': '#FF0000',
        'api': 'YouTube Data API v3',
        'endpoint': 'https://www.googleapis.com/upload/youtube/v3/videos',
    },
    'tiktok': {
        'name': 'TikTok',
        'icon': '🎵',
        'color': '#000000',
        'api': 'TikTok Content Posting API',
        'endpoint': 'https://open.tiktokapis.com/v2/post/publish/video/init/',
    },
    'instagram': {
        'name': 'Instagram',
        'icon': '📸',
        'color': '#E4405F',
        'api': 'Instagram Graph API',
        'endpoint': 'https://graph.facebook.com/v25.0/{page_id}/media',
    },
    'facebook': {
        'name': 'Facebook',
        'icon': '👤',
        'color': '#1877F2',
        'api': 'Facebook Graph API',
        'endpoint': 'https://graph.facebook.com/v25.0/{page_id}/videos',
    },
}


def _refresh_tiktok_token() -> str | None:
    """Refresh TikTok access token. Returns new token or None."""
    refresh_token = os.getenv('TIKTOK_REFRESH_TOKEN')
    client_key = os.getenv('TIKTOK_CLIENT_KEY')
    client_secret = os.getenv('TIKTOK_CLIENT_SECRET')
    if not refresh_token or not client_key or not client_secret:
        return None
    try:
        import requests
        resp = requests.post(
            'https://open.tiktokapis.com/v2/oauth/token/',
            data={
                'client_key': client_key,
                'client_secret': client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            new_token = data.get('access_token')
            if new_token:
                os.environ['TIKTOK_ACCESS_TOKEN'] = new_token
                _save_env({'TIKTOK_ACCESS_TOKEN': new_token})
                return new_token
        return None
    except Exception as refresh_err:
        security_audit("TOKEN_REFRESH_FAILED", f"TikTok token refresh failed: {safe_log(str(refresh_err))}", "error")
        return None


def _save_env(updates: dict):
    """Persist env vars to both .env files (and Firestore env_vars)."""
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _agents_dir = os.path.dirname(_script_dir)
    _root_dir = os.path.dirname(_agents_dir)
    for _p in [os.path.join(_agents_dir, '.env'), os.path.join(_root_dir, '.env')]:
        if os.path.exists(_p):
            _lines = []
            with open(_p) as _f:
                _lines = _f.readlines()
            _updated_keys = set(updates.keys())
            _existing_keys = set()
            _new_lines = []
            for _line in _lines:
                _stripped = _line.strip()
                if _stripped and not _stripped.startswith('#'):
                    _key, _, _ = _stripped.partition('=')
                    _key = _key.strip()
                    if _key in updates:
                        _new_lines.append(f'{_key}={updates[_key]}\n')
                        _existing_keys.add(_key)
                        continue
                _new_lines.append(_line)
            for _key, _val in updates.items():
                if _key not in _existing_keys:
                    _new_lines.append(f'{_key}={_val}\n')
            with open(_p, 'w') as _f:
                _f.writelines(_new_lines)
    # Firestore env_vars overrides .env at boot (sync_env_from_firestore),
    # so a refreshed token written only to .env would be lost on restart.
    try:
        from utils.firebase_status import get_firestore_client
        _db = get_firestore_client()
        if _db is not None:
            for _key, _val in updates.items():
                _db.collection('env_vars').document(_key).set({'value': _val}, merge=True)
    except Exception:
        pass


def _refresh_facebook_token() -> str | None:
    """Extend Facebook access token lifetime. Returns new token or None."""
    token = os.getenv('FACEBOOK_ACCESS_TOKEN')
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    if not token or not app_id or not app_secret:
        return None
    try:
        import requests
        resp = requests.get(
            'https://graph.facebook.com/v25.0/oauth/access_token',
            params={
                'grant_type': 'fb_exchange_token',
                'client_id': app_id,
                'client_secret': app_secret,
                'fb_exchange_token': token,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            new_token = resp.json().get('access_token')
            if new_token:
                os.environ['FACEBOOK_ACCESS_TOKEN'] = new_token
                _save_env({'FACEBOOK_ACCESS_TOKEN': new_token})
                return new_token
        return None
    except Exception as refresh_err:
        security_audit("TOKEN_REFRESH_FAILED", f"Facebook token refresh failed: {safe_log(str(refresh_err))}", "error")
        return None


def _idempotency_key() -> str:
    return str(uuid.uuid4())


def _check_meta_rate_limit(response, platform: str):
    """Parse X-App-Usage header and log warnings near rate limits."""
    try:
        usage_header = response.headers.get('X-App-Usage')
        if usage_header:
            import json as _json
            usage = _json.loads(usage_header) if isinstance(usage_header, str) else usage_header
            if isinstance(usage, dict):
                pct = max(usage.get(k, 0) for k in ('call_count', 'total_cputime', 'total_time'))
                if pct >= 80:
                    security_audit("RATE_LIMIT", f"{platform} usage at {pct}%", "warning")
                    log_activity('publisher', f'{platform} rate limit usage: {pct}%', 'warn')
    except Exception:
        pass


def _is_graph_permission_error(err: dict) -> bool:
    """Check if Facebook Graph API error is a permanent permission error (skip retry)."""
    code = err.get('code', 0)
    msg = (err.get('error_user_title', '') + err.get('message', '')).lower()
    if code in (190, 200) or 'permission' in msg:
        return True
    return False


def upload_to_platform(platform: str, title: str, description: str, video_path: str, thumbnail_path: str, format_type: str = 'shorts', publish_at: str = None, subtitle_path: str = None, tags: list = None, tiktok_privacy_level: str = None, tiktok_comment_disabled: bool = False, tiktok_duet_disabled: bool = False, tiktok_stitch_disabled: bool = False, default_language: str = None, tiktok_brand_content: bool = False, tiktok_brand_organic: bool = False) -> dict:  # noqa: E501
    """Upload a video to a specific platform."""
    platform_info = PLATFORMS.get(platform)
    if not platform_info:
        return {'success': False, 'error': f'Unknown platform: {platform}'}

    log_activity('publisher', f'Uploading to {platform_info["name"]}: {title}', 'info')

    try:
        if platform == 'youtube':
            return _upload_youtube(title, description, video_path, thumbnail_path, format_type, publish_at, subtitle_path, tags=tags, default_language=default_language)
        elif platform == 'tiktok':
            return _upload_tiktok(title, video_path, format_type, privacy_level=tiktok_privacy_level,
                                  comment_disabled=tiktok_comment_disabled,
                                  duet_disabled=tiktok_duet_disabled,
                                  stitch_disabled=tiktok_stitch_disabled,
                                  brand_content=tiktok_brand_content,
                                  brand_organic=tiktok_brand_organic)
        elif platform == 'instagram':
            return _upload_instagram(title, video_path, format_type)
        elif platform == 'facebook':
            return _upload_facebook(title, description, video_path, thumbnail_path)
        else:
            return {'success': False, 'error': 'Platform not implemented'}
    except Exception as e:
        log_activity('publisher', f'Upload to {platform_info["name"]} failed: {safe_log(str(e))}', 'error')
        return {'success': False, 'error': safe_log(str(e))}


def _fit_tags(tags: list, budget: int = 480) -> list:
    """Fit a tag list under YouTube's 500-char total / 100-per-tag hard limits.

    Tags that exceed the API limit make the whole upload fail with a 400, so the
    list is trimmed by cumulative length in order (early tags are the caller's
    most valuable SEO keywords), never just sliced by count.
    """
    out = []
    used = 0
    for tag in tags:
        t = str(tag).strip().strip("#")[:100]
        if not t:
            continue
        sep = 1 if out else 0
        if used + sep + len(t) > budget:
            continue
        out.append(t)
        used += sep + len(t)
    return out


def _upload_youtube(title: str, description: str, video_path: str, thumbnail_path: str, format_type: str, publish_at: str = None, subtitle_path: str = None, tags: list = None, default_language: str = None) -> dict:  # noqa: E501
    try:
        from utils.youtube_upload import upload_video_to_youtube
        from utils.description_gen import get_tech_metadata

        tech_meta = get_tech_metadata("tech educational", format_type, title)

        if tags:
            combined_tags = list(dict.fromkeys(tags + [format_type, "vyom-ai-cloud", "ai", "technology"]))
        else:
            combined_tags = tech_meta.get("tags", []) + [format_type, "vyom-ai-cloud", "ai", "technology"]

        print(f"[PUBLISHER] Uploading YouTube video: {title} (format={format_type}, publish_at={publish_at})")
        result = upload_video_to_youtube(
            video_file=video_path,
            title=title,
            description=description,
            tags=_fit_tags(combined_tags),
            thumbnail_file=thumbnail_path,
            category_id=tech_meta["categoryId"],
            is_shorts=(format_type == "shorts"),
            publish_at=publish_at,
            subtitle_path=subtitle_path,
            default_language=default_language,
        )

        ai_flags = get_ai_disclosure("youtube")
        result["ai_disclosure"] = ai_flags
        result["made_for_kids"] = False
        result["ai_generated"] = True

        if result.get('success'):
            print(f"[PUBLISHER] YouTube upload successful: {result.get('video_url', 'unknown')}")
            log_activity('publisher', f"YouTube upload complete: {result.get('video_url', 'unknown')}", 'success')
        else:
            print(f"[PUBLISHER] YouTube upload failed: {result.get('error', 'unknown error')}")
            log_activity('publisher', f"YouTube upload FAILED: {result.get('error', 'unknown error')}", 'error')
        return result
    except Exception as e:
        import traceback, sys
        print(f"[PUBLISHER] YouTube upload exception at line 241: type(title)={type(title).__name__}, type(desc)={type(description).__name__}, type(fmt)={type(format_type).__name__}")
        print(f"[PUBLISHER] YouTube upload exception: {e}")
        traceback.print_exc(file=sys.stdout)
        log_activity('publisher', f"YouTube upload FAILED: {e}", 'error')
        return {
            'success': False,
            'platform': 'youtube',
            'error': str(e),
            'title': title,
        }


_TIKTOK_PERMANENT_INIT_CODES = {
    # The account/app is barred until a human changes something external. Re-sending
    # the identical init body cannot alter any of these.
    'spam_risk_user_banned_from_posting',
    'unaudited_client_can_only_post_to_private_accounts',
    'reached_active_user_cap',
    'privacy_level_option_mismatch',
}


def _tiktok_error_code(resp) -> str:
    """Best-effort pull of error.code, so classification never re-parses the body."""
    try:
        body = resp.json()
    except ValueError:
        return ''
    if isinstance(body, dict):
        err = body.get('error') or {}
        if isinstance(err, dict):
            return str(err.get('code') or '')
    return ''


def _tiktok_init_error(resp, brand_content: bool = False) -> str:
    """Turn TikTok's init/publish error codes into something an operator can act on.

    The raw body is a JSON envelope whose `message` is a developer string
    ("The user has reached their quota limit") -- useless in an alert at 03:00
    without knowing which of five distinct causes produced it. Two of these are
    permanent account/app states that no retry will ever fix, and one of them is
    the reason a SELF_ONLY post still failed. `creator_info` carries no quota
    field, so the quota state is only ever visible here.
    """
    try:
        body = resp.json()
    except ValueError:
        return safe_log((resp.text or '')[:200])

    code = ''
    msg = ''
    if isinstance(body, dict):
        err = body.get('error') or {}
        if isinstance(err, dict):
            code = str(err.get('code') or '')
            msg = str(err.get('message') or '')

    guidance = {
        'spam_risk_too_many_posts': 'posting limit reached for this user; retry later',
        'reached_active_user_cap': 'client active-user cap reached; retry later',
        'spam_risk_user_banned_from_posting': 'ACCOUNT cannot post; not retryable',
        'privacy_level_option_mismatch': 'privacy_level not offered for this user; refresh options',
    }
    if code == 'unaudited_client_can_only_post_to_private_accounts':
        # The most misleading line in this table if left unqualified. An
        # unaudited app may ONLY post privately -- but a branded post may not be
        # private, because the disclosure the brand flag asserts is not visible
        # on a self-only post. So "use SELF_ONLY" is a fix for a normal post and
        # an impossibility for a branded one, and the operator needs both.
        if brand_content:
            return (f'{code}: app is not audited, so TikTok permits only SELF_ONLY; '
                    f'brand content cannot be published privately, so this post cannot '
                    f'comply -- complete App Review or unset the brand content toggle '
                    f'(raw: {safe_log(msg)})')
        return f'{code}: app not audited; use SELF_ONLY (raw: {safe_log(msg)})'
    if code in guidance:
        return f'{code}: {guidance[code]} (raw: {safe_log(msg)})'
    return safe_log(f'{code} {msg}'.strip() or (resp.text or '')[:200])


def _upload_tiktok(title: str, video_path: str, format_type: str, privacy_level: str = None,
                   comment_disabled: bool = False, duet_disabled: bool = False,
                   stitch_disabled: bool = False,
                   brand_content: bool = False, brand_organic: bool = False) -> dict:
    """Upload to TikTok via Content Posting API v2 with retry, rate limit, idempotency."""
    if not rate_limiter("tiktok_upload", max_per_hour=5):
        # Soft limit: warn, never block. A 5-video slate needs exactly 5 per
        # platform, so a hard block with zero headroom silently dropped the 6th
        # upload in an hour -- and the bucket is in-memory, so a container restart
        # reset it mid-run, which is how the 2026-10-01 TikTok 429 happened. The
        # real protection is PLATFORM_UPLOAD_DELAY plus retry_with_backoff, which
        # backs off on a genuine 429. A refused upload loses a platform for good;
        # a retried one only costs time.
        security_audit("RATE_LIMIT", "TikTok upload rate limit would be hit -- proceeding", "error")

    access_token = os.getenv('TIKTOK_ACCESS_TOKEN')
    open_id = os.getenv('TIKTOK_OPEN_ID')
    if not access_token or not open_id:
        return {
            'success': False,
            'platform': 'tiktok',
            'error': 'TikTok upload not configured. Set TIKTOK_ACCESS_TOKEN and TIKTOK_OPEN_ID env vars.',
        }

    if not privacy_level:
        privacy_level = os.getenv('TIKTOK_PRIVACY_LEVEL', '')
    if not privacy_level:
        msg = 'TikTok privacy_level not set. Provide a per-post override or set TIKTOK_PRIVACY_LEVEL env (no implicit default).'
        log_activity('publisher', msg, 'error')
        security_audit("PRIVACY_MISSING", 'TikTok publish blocked: no privacy_level', "error")
        return {'success': False, 'platform': 'tiktok', 'error': msg}

    if not os.path.exists(video_path):
        return {'success': False, 'platform': 'tiktok', 'error': f'Video file not found: {video_path}'}

    # TikTok rejects brand content published to a private audience: the disclosure
    # a branded post requires is not visible on a SELF_ONLY post, so the two states
    # are mutually exclusive. Caught here rather than in the composer because all
    # three callers (shorts, long, composer job) reach this function, and a check
    # that lives in one caller leaves the other two able to send the illegal pair.
    if brand_content and privacy_level == 'SELF_ONLY':
        msg = ('TikTok does not allow brand content with SELF_ONLY privacy '
               '(the required disclosure is not visible on a private post). '
               'Choose a public privacy level or unset the brand content toggle.')
        log_activity('publisher', msg, 'error')
        security_audit("TIKTOK_BRAND_PRIVACY_CONFLICT", safe_log(msg), "error")
        return {'success': False, 'platform': 'tiktok', 'error': msg}

    idem_key = _idempotency_key()
    _tiktok_refresh_attempted = False

    def _do_upload():
        nonlocal access_token, _tiktok_refresh_attempted
        import requests

        file_size = os.path.getsize(video_path)

        # TikTok Media Transfer: chunk_size 5-64MB, total_chunk_count = floor(size/chunk_size).
        # Files >64MB MUST be multi-chunk; last chunk absorbs trailing bytes (up to 128MB).
        chunk_size = min(file_size, 64 * 1024 * 1024)
        total_chunk_count = file_size // chunk_size if chunk_size else 1
        while total_chunk_count < 2 and chunk_size > 5 * 1024 * 1024:
            chunk_size //= 2
            total_chunk_count = file_size // chunk_size
        if total_chunk_count < 1:
            total_chunk_count = 1
            chunk_size = file_size

        init_resp = requests.post(
            'https://open.tiktokapis.com/v2/post/publish/video/init/',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={
                'source_info': {
                    'source': 'FILE_UPLOAD',
                    'video_size': file_size,
                    'chunk_size': chunk_size,
                    'total_chunk_count': total_chunk_count,
                },
                'post_info': {'privacy_level': privacy_level},
            },
            timeout=30,
        )

        if init_resp.status_code == 401 and not _tiktok_refresh_attempted:
            _tiktok_refresh_attempted = True
            refreshed = _refresh_tiktok_token()
            if refreshed:
                access_token = refreshed
                return _do_upload()

        if init_resp.status_code != 200:
            _msg = (f'TikTok init failed: {init_resp.status_code} '
                    f'{_tiktok_init_error(init_resp, brand_content)}')
            if _tiktok_error_code(init_resp) in _TIKTOK_PERMANENT_INIT_CODES:
                # Without this the unaudited/banned/capped states were retried 3x
                # with 5->60s backoff, spending ~65s of the run to re-derive an
                # identical error and three rate-limit slots per video.
                raise NonRetryableError(_msg)
            raise RuntimeError(_msg)

        init_data = init_resp.json()
        upload_url = init_data.get('data', {}).get('upload_url')
        publish_id = init_data.get('data', {}).get('publish_id')

        if not upload_url or not publish_id:
            raise RuntimeError('No upload URL / publish id in TikTok init response')

        # Upload chunks sequentially with per-chunk Content-Range; 201 = done, 206 = more pending.
        # Non-final chunks = exactly chunk_size; the FINAL chunk absorbs ALL trailing bytes
        # (up to 128MB, per Media Transfer guide) so cumulative bytes reach file_size.
        with open(video_path, 'rb') as f:
            for i in range(total_chunk_count):
                start = i * chunk_size
                end = (file_size - 1) if i == total_chunk_count - 1 else (start + chunk_size - 1)
                f.seek(start)
                data = f.read(end - start + 1)
                upload_resp = requests.put(
                    upload_url, data=data, timeout=300,
                    headers={'Content-Range': f'bytes {start}-{end}/{file_size}',
                             'Content-Type': 'video/mp4'},
                )
                if upload_resp.status_code not in (200, 201, 206):
                    raise RuntimeError(f'TikTok chunk {i + 1}/{total_chunk_count} upload failed: {upload_resp.status_code}')

        ai_flags = get_ai_disclosure("tiktok")
        # Field names are `disable_*`, not `*_disabled`. The old names were not
        # rejected -- TikTok ignored them -- so every comment/duet/stitch
        # choice silently did nothing and the post published with all three
        # enabled regardless of what the composer asked for.
        # Every toggle is sent explicitly. An omitted `brand_content_toggle`
        # defaults to TRUE on TikTok's side, which declares the post as branded
        # content and requires a matching disclosure in the UI; relying on that
        # default is exactly what gets an app rejected, so the state is always
        # stated here rather than inherited.
        post_info = {
            'title': title,
            'privacy_level': privacy_level,
            'disable_comment': bool(comment_disabled),
            'disable_duet': bool(duet_disabled),
            'disable_stitch': bool(stitch_disabled),
            'brand_content_toggle': bool(brand_content),
            'brand_organic_toggle': bool(brand_organic),
        }
        if ai_flags.get("is_aigc"):
            post_info["is_aigc"] = True

        # Publish via status polling (init -> upload -> poll status/fetch until PUBLISH_COMPLETE)
        publish_payload = {'publish_id': publish_id, 'post_info': post_info}
        publish_resp = requests.post(
            'https://open.tiktokapis.com/v2/post/publish/video/publish/',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Idempotency-Key': idem_key,
            },
            json=publish_payload,
            timeout=30,
        )

        # Some clients return a routing/404 on the publish POST; fall back to status polling.
        # poll status/fetch until PUBLISH_COMPLETE.
        video_id = None
        status = 'processing'
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                status_resp = requests.post(
                    'https://open.tiktokapis.com/v2/post/publish/status/fetch/',
                    headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                    json={'publish_id': publish_id},
                    timeout=30,
                )
                if status_resp.status_code == 200:
                    data = status_resp.json().get('data', {})
                    status = data.get('status', status)
                    video_id = data.get('publicaly_available_post_id') or data.get('video_id') or video_id
                    if status == 'PUBLISH_COMPLETE':
                        break
                    if status == 'PUBLISH_FAILED':
                        raise RuntimeError('TikTok publish failed (status PUBLISH_FAILED)')
            except Exception as e:
                if 'PUBLISH_FAILED' in str(e):
                    raise
            time.sleep(8)

        if status not in ('PUBLISH_COMPLETE', 'SEND_TO_USER_INBOX'):
            raise RuntimeError(f'TikTok publish did not complete (status={status})')

        # For private (SELF_ONLY) posts TikTok returns no public post id — fall back to publish_id.
        final_id = video_id or publish_id
        return {
            'success': True,
            'platform': 'tiktok',
            'video_id': final_id,
            'url': f'https://www.tiktok.com/@{open_id}/video/{final_id}',
            'title': title,
            'status': 'published',
        }

    try:
        ok, result = retry_with_backoff(_do_upload, max_retries=3, base_delay=5, max_delay=60)
        if ok:
            return result
        log_activity('publisher', f"TikTok upload FAILED after retries: {safe_log(str(result)[:200])}", 'error')
        security_audit("UPLOAD_FAILED", f"TikTok — {safe_log(str(result)[:200])}", "error")
        return {
            'success': False, 'platform': 'tiktok',
            'error': safe_log(str(result)),
        }
    except ImportError:
        return {'success': False, 'platform': 'tiktok', 'error': 'Missing requests library'}
    except Exception as e:
        log_activity('publisher', f"TikTok upload FAILED: {safe_log(str(e)[:200])}", 'error')
        security_audit("UPLOAD_FAILED", f"TikTok — {safe_log(str(e)[:200])}", "error")
        return {'success': False, 'platform': 'tiktok', 'error': safe_log(str(e))}


def _upload_instagram(title: str, video_path: str, format_type: str) -> dict:
    """Upload to Instagram via Graph API with retry, rate limit, token refresh."""
    if not rate_limiter("instagram_upload", max_per_hour=5):
        # Soft limit, same reasoning as _upload_tiktok: warn, never drop a platform.
        security_audit("RATE_LIMIT", "Instagram upload rate limit would be hit -- proceeding", "error")

    access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
    ig_account_id = os.getenv('INSTAGRAM_ACCOUNT_ID')
    if not access_token or not ig_account_id:
        return {
            'success': False,
            'platform': 'instagram',
            'error': 'Instagram upload not configured. Set FACEBOOK_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID env vars.',
        }

    if format_type == 'shorts' and not video_path.startswith(('http://', 'https://')):
        video_path = _trim_for_instagram(video_path)

    instagram_video_url = os.getenv('INSTAGRAM_VIDEO_URL', '')
    if not instagram_video_url:
        if video_path.startswith(('http://', 'https://')):
            instagram_video_url = video_path
        else:
            try:
                from utils.r2_storage import get_r2_client, generate_presigned_url
                from datetime import datetime
                import uuid as _uuid
                _client = get_r2_client()
                _bucket = os.getenv('CLOUDFLARE_R2_BUCKET', 'vyom-ai-videos')
                _key = f"videos/{_uuid.uuid4().hex}_{format_type}.mp4"
                with open(video_path, 'rb') as _f:
                    _client.upload_fileobj(
                        _f, _bucket, _key,
                        ExtraArgs={
                            'ContentType': 'video/mp4',
                            'Metadata': {'uploaded-at': datetime.utcnow().isoformat(), 'format': format_type},
                        },
                    )
                instagram_video_url = generate_presigned_url(_key, expires_in=3600)
                log_activity('publisher', f'Uploaded video to R2 for Instagram: {_key}', 'info')
            except Exception as r2_err:
                log_activity('publisher', f'R2 upload failed for Instagram: {safe_log(str(r2_err))}', 'error')
                security_audit("UPLOAD_FAILED", f"Instagram R2 upload failed: {safe_log(str(r2_err))}", "error")
                return {
                    'success': False, 'platform': 'instagram',
                    'error': f'Instagram needs a public URL. R2 upload failed: {safe_log(str(r2_err))}',
                }

    idem_key = _idempotency_key()
    _instagram_refresh_attempted = False

    def _do_upload():
        nonlocal access_token, _instagram_refresh_attempted
        import requests

        # Meta deprecated media_type=VIDEO (400 code 100 subcode 2207067).
        # REELS works for both formats; longs keep share_to_feed=true (below)
        # so they still publish to the Instagram feed.
        media_type = 'REELS'

        ai_flags = get_ai_disclosure("instagram")
        media_params = {
            'access_token': access_token,
            'media_type': media_type,
            'video_url': instagram_video_url,
            'caption': title,
            'share_to_feed': 'true' if format_type == 'long' else 'false',
        }
        if ai_flags.get("is_ai_generated"):
            media_params["is_ai_generated"] = "true"

        create_resp = requests.post(
            f'https://graph.facebook.com/v25.0/{ig_account_id}/media',
            params=media_params,
            timeout=30,
        )
        _check_meta_rate_limit(create_resp, 'Instagram')

        if create_resp.status_code == 401 and not _instagram_refresh_attempted:
            _instagram_refresh_attempted = True
            refreshed = _refresh_facebook_token()
            if refreshed:
                access_token = refreshed
                return _do_upload()

        if create_resp.status_code != 200:
            resp_body = create_resp.text[:500]
            log_activity('publisher', f'Instagram media creation error {create_resp.status_code}: {resp_body}', 'error')
            raise RuntimeError(f'Instagram media creation failed: {create_resp.status_code} — {resp_body}')

        creation_id = create_resp.json().get('id')
        if not creation_id:
            raise RuntimeError('No media creation ID from Instagram')

        import time
        poll_attempts = 60
        poll_finished = False
        for attempt in range(poll_attempts):
            status_resp = requests.get(
                f'https://graph.facebook.com/v25.0/{creation_id}',
                params={'access_token': access_token, 'fields': 'status_code'},
                timeout=15,
            )
            _check_meta_rate_limit(status_resp, 'Instagram')
            if status_resp.status_code == 200:
                status_code = status_resp.json().get('status_code')
                if status_code == 'FINISHED':
                    poll_finished = True
                    break
                elif status_code == 'ERROR':
                    raise RuntimeError('Instagram media processing failed')
            time.sleep(5)
        if not poll_finished:
            raise RuntimeError('Instagram media processing timed out')

        publish_resp = requests.post(
            f'https://graph.facebook.com/v25.0/{ig_account_id}/media_publish',
            params={'access_token': access_token, 'creation_id': creation_id, 'idempotency_key': idem_key},
            timeout=30,
        )
        _check_meta_rate_limit(publish_resp, 'Instagram')

        if publish_resp.status_code == 200:
            media_id = publish_resp.json().get('id', creation_id)
            return {
                'success': True,
                'platform': 'instagram',
                'video_id': media_id,
                'url': f'https://www.instagram.com/reel/{media_id}/' if format_type == 'shorts' else f'https://www.instagram.com/p/{media_id}/',
                'title': title,
                'status': 'published',
            }
        else:
            raise RuntimeError(f'Instagram publish failed: {publish_resp.status_code}')

    try:
        ok, result = retry_with_backoff(_do_upload, max_retries=3, base_delay=5, max_delay=60)
        if ok:
            return result
        log_activity('publisher', f"Instagram upload FAILED after retries: {safe_log(str(result)[:200])}", 'error')
        security_audit("UPLOAD_FAILED", f"Instagram — {safe_log(str(result)[:200])}", "error")
        return {
            'success': False, 'platform': 'instagram',
            'error': safe_log(str(result)),
        }
    except ImportError:
        return {'success': False, 'platform': 'instagram', 'error': 'Missing requests library'}
    except Exception as e:
        log_activity('publisher', f"Instagram upload FAILED: {safe_log(str(e)[:200])}", 'error')
        security_audit("UPLOAD_FAILED", f"Instagram — {safe_log(str(e)[:200])}", "error")
        return {'success': False, 'platform': 'instagram', 'error': safe_log(str(e))}


def _fb_json(resp, phase: str) -> dict:
    """Parse a Graph response without blowing up on an HTML/plaintext error body.

    `requests.Response.json()` raises `Expecting value: line 1 column 1` on a
    non-JSON reply, which is how the resumable bug reported itself: an opaque
    exception with no status code, no phase, and no body. Keep the response
    object under `_resp` so the caller can still inspect the status.
    """
    try:
        body = resp.json()
    except ValueError:
        snippet = safe_log((resp.text or '')[:200])
        raise RuntimeError(
            f'Facebook {phase} returned non-JSON (HTTP {resp.status_code}): {snippet}'
        )
    if not isinstance(body, dict):
        raise RuntimeError(
            f'Facebook {phase} returned {type(body).__name__}, expected object '
            f'(HTTP {resp.status_code})'
        )
    body['_resp'] = resp
    return body


def _fb_resumable_transfer(upload_path: str, page_id: str, access_token: str,
                           file_size: int, session: dict, idem_key: str,
                           _fb_json, _raise_fb_api_error, _check_meta_rate_limit,
                           on_401=None, start_offset: int = 0) -> None:
    """Phases 2 and 3 of Meta's resumable upload: transfer chunks, then finish.

    The old code sent the entire file in one request under the field name
    `source` with `start_offset=0` and never called `finish`, so the session was
    opened and abandoned mid-flight (error 1363030). The byte offset must come
    from Meta, and the file handle must be seeked to it -- sending the whole
    stream against a non-zero `start_offset` is the same bug with a different
    symptom.

    `start_offset` comes from the 'start' response and is the resume position.
    We do NOT cap chunks by `end_offset`: on the start response that field is
    the last byte received so far, not a limit on how much we may send. Capping
    by it made a fresh session (which reports end_offset=0) send one byte per
    request -- ~5M requests for a 5GB file. Each transfer response returns the
    next offset, and that is what drives the loop.

    Error 1363037 means the offset is no longer valid; Meta returns the correct
    window in that response and the upload continues from there.
    """
    import requests

    url = f'https://graph.facebook.com/v25.0/{page_id}/videos'
    upload_session_id = session['upload_session_id']
    offset = max(0, int(start_offset or 0))
    # ponytail: bounded retry. A stalled resumable session is recoverable, but
    # an unbounded loop would hang the overnight run.
    stalls = 0
    MAX_STALLS = 3

    with open(upload_path, 'rb') as f:
        while offset < file_size:
            f.seek(offset)
            chunk = f.read(_FB_CHUNK_BYTES)
            if not chunk:
                break

            params = {
                'access_token': access_token,
                'upload_phase': 'transfer',
                'upload_session_id': upload_session_id,
                'start_offset': str(offset),
                'idempotency_key': idem_key,
            }
            resp = requests.post(
                url, params=params,
                files={'video_file_chunk': chunk},
                timeout=600,
            )
            _check_meta_rate_limit(resp, 'Facebook')

            # Refresh BEFORE parsing: an expired token can come back as an HTML
            # error page, and _fb_json would raise on it and skip the refresh.
            if resp.status_code in (401, 403) and on_401 is not None:
                new_token = on_401()
                if new_token:
                    access_token = new_token
                    params['access_token'] = new_token
                    continue  # same offset, fresh token

            body = _fb_json(resp, f'resumable transfer @{offset}')
            err = body.get('error') or {}

            # 1363037 means the offset went stale (session idle too long, or a
            # previous attempt got further than this one). Meta returns the valid
            # window in the SAME error body, so this is recoverable -- raising here
            # would throw away an upload that is most of the way done.
            if err.get('code') == 1363037 and 'start_offset' in body:
                next_offset = int(body['start_offset'])
            else:
                _raise_fb_api_error(body, f'resumable transfer @{offset}')
                # Trust Meta's window when it gives one; otherwise advance by what
                # we actually sent.
                next_offset = body.get('start_offset')
                next_offset = offset + len(chunk) if next_offset is None else int(next_offset)

            if next_offset <= offset:
                stalls += 1
                if stalls > MAX_STALLS:
                    raise RuntimeError(
                        f'Facebook resumable upload stalled at offset {offset}/{file_size} '
                        f'(meta returned {next_offset})'
                    )
            else:
                stalls = 0
            offset = next_offset

    if offset < file_size:
        raise RuntimeError(
            f'Facebook resumable upload incomplete: {offset}/{file_size} bytes sent'
        )

    # Phase 3 -- without this the session is opened and never published.
    finish = _fb_json(requests.post(
        url,
        params={
            'access_token': access_token,
            'upload_phase': 'finish',
            'upload_session_id': upload_session_id,
        },
        timeout=120,
    ), 'resumable finish')

    _raise_fb_api_error(finish, 'resumable finish')
    if not finish.get('success', True):
        raise RuntimeError('Facebook resumable finish reported success=false')


def _upload_facebook(title: str, description: str, video_path: str, thumbnail_path: str = None) -> dict:
    """Upload to Facebook via Graph API with retry, rate limit, token refresh."""
    if not rate_limiter("facebook_upload", max_per_hour=5):
        # Soft limit, same reasoning as _upload_tiktok: warn, never drop a platform.
        security_audit("RATE_LIMIT", "Facebook upload rate limit would be hit -- proceeding", "error")

    access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
    page_id = os.getenv('FACEBOOK_PAGE_ID')
    if not access_token or not page_id:
        return {
            'success': False,
            'platform': 'facebook',
            'error': 'Facebook upload not configured. Set FACEBOOK_ACCESS_TOKEN and FACEBOOK_PAGE_ID env vars.',
        }

    if not os.path.exists(video_path):
        return {'success': False, 'platform': 'facebook', 'error': f'Video file not found: {video_path}'}

    upload_path = _compress_for_facebook(video_path)

    _facebook_refresh_attempted = False
    idem_key = _idempotency_key()

    def _raise_fb_api_error(body, phase):
        err = body.get('error')
        if err:
            msg = err.get('error_user_title', err.get('message', 'unknown'))
            code = err.get('code', '?')
            subcode = err.get('error_subcode', '')
            if _is_graph_permission_error(err):
                raise PermissionError(f'Facebook {phase} failed (PERMANENT): {msg} (code {code}, subcode {subcode})')
            raise RuntimeError(f'Facebook {phase} failed: {msg} (code {code}, subcode {subcode})')

    def _do_upload():
        nonlocal access_token, _facebook_refresh_attempted
        import requests

        file_size = os.path.getsize(upload_path)
        upload_method = 'resumable' if file_size > _FB_RESUMABLE_THRESHOLD else 'direct'

        ai_flags = get_ai_disclosure("facebook")
        fb_description = description
        if ai_flags.get("caption_hashtag"):
            fb_description += f"\n\n{ai_flags['caption_hashtag']}"

        if upload_method == 'direct':
            source_fp = open(upload_path, 'rb')
            thumb_fp = open(thumbnail_path, 'rb') if thumbnail_path and os.path.exists(thumbnail_path) else None
            fb_files = {'source': source_fp}
            if thumb_fp:
                fb_files['thumb'] = thumb_fp
            try:
                upload_resp = requests.post(
                    f'https://graph.facebook.com/v25.0/{page_id}/videos',
                    params={'access_token': access_token, 'idempotency_key': idem_key},
                    files=fb_files,
                    data={
                        'title': title,
                        'description': fb_description,
                        'published': 'true',
                    },
                    timeout=600,
                )
            finally:
                source_fp.close()
                if thumb_fp:
                    thumb_fp.close()

            _check_meta_rate_limit(upload_resp, 'Facebook')

            if upload_resp.status_code in (401, 403) and not _facebook_refresh_attempted:
                _facebook_refresh_attempted = True
                refreshed = _refresh_facebook_token()
                if refreshed:
                    access_token = refreshed
                    return _do_upload()

            body = _fb_json(upload_resp, 'direct upload')
            _raise_fb_api_error(body, 'direct upload')

            video_id = body.get('id')
            if not video_id:
                raise RuntimeError(f'Facebook direct upload returned no video ID (size={file_size})')
            return {
                'success': True,
                'platform': 'facebook',
                'video_id': video_id,
                'url': f'https://www.facebook.com/watch/?v={video_id}',
                'title': title,
                'status': 'published',
            }
        else:
            # Meta's 3-phase resumable protocol. The bug this replaces sent the
            # whole file in ONE transfer under the field name 'source' and never
            # called 'finish', so the session was opened and abandoned -> 1363030.
            # The field is 'video_file_chunk', each transfer response carries the
            # next offset, and video_id arrives on 'start'.
            init_resp = requests.post(
                f'https://graph.facebook.com/v25.0/{page_id}/videos',
                params={
                    'access_token': access_token,
                    'title': title,
                    'description': fb_description,
                    'upload_phase': 'start',
                    'file_size': file_size,
                },
                timeout=30,
            )

            _check_meta_rate_limit(init_resp, 'Facebook')

            if init_resp.status_code in (401, 403) and not _facebook_refresh_attempted:
                _facebook_refresh_attempted = True
                refreshed = _refresh_facebook_token()
                if refreshed:
                    access_token = refreshed
                    return _do_upload()

            init_body = _fb_json(init_resp, 'resumable start')
            _raise_fb_api_error(init_body, 'resumable start')

            # The id lives on the start response; the finish response has none.
            video_id = init_body.get('video_id') or init_body.get('id')
            upload_session_id = init_body.get('upload_session_id')
            if not upload_session_id:
                raise RuntimeError(f'No upload session ID from Facebook (size={file_size})')
            if not video_id:
                raise RuntimeError(f'Facebook resumable start returned no video ID (size={file_size})')

            session = {'upload_session_id': upload_session_id, 'video_id': video_id}

            def _retry_with_new_token():
                """One-shot token refresh mid-transfer. Returns the new token or None."""
                nonlocal _facebook_refresh_attempted
                if _facebook_refresh_attempted:
                    return None
                _facebook_refresh_attempted = True
                refreshed = _refresh_facebook_token()
                if not refreshed:
                    return None
                return refreshed

            _fb_resumable_transfer(
                upload_path, page_id, access_token, file_size, session, idem_key,
                _fb_json, _raise_fb_api_error, _check_meta_rate_limit,
                on_401=_retry_with_new_token,
                start_offset=init_body.get('start_offset') or 0,
            )

            return {
                'success': True,
                'platform': 'facebook',
                'video_id': video_id,
                'url': f'https://www.facebook.com/watch/?v={video_id}',
                'title': title,
                'status': 'published',
            }

    try:
        ok, result = retry_with_backoff(_do_upload, max_retries=3, base_delay=5, max_delay=60)
        if ok:
            return result
        log_activity('publisher', f"Facebook upload FAILED after retries: {safe_log(str(result)[:200])}", 'error')
        security_audit("UPLOAD_FAILED", f"Facebook — {safe_log(str(result)[:200])}", "error")
        return {
            'success': False, 'platform': 'facebook',
            'error': safe_log(str(result)),
        }
    except PermissionError as e:
        msg = safe_log(str(e))
        log_activity('publisher', f"Facebook upload FAILED (permanent): {msg}", 'error')
        security_audit("UPLOAD_FAILED", f"Facebook permission error — {msg}", "error")
        return {'success': False, 'platform': 'facebook', 'error': msg}
    except ImportError:
        return {'success': False, 'platform': 'facebook', 'error': 'Missing requests library'}
    except Exception as e:
        log_activity('publisher', f"Facebook upload FAILED: {safe_log(str(e)[:200])}", 'error')
        security_audit("UPLOAD_FAILED", f"Facebook — {safe_log(str(e)[:200])}", "error")
        return {'success': False, 'platform': 'facebook', 'error': safe_log(str(e))}


def multi_platform_publish(video_id: str, title: str, description: str, video_path: str,
                           thumbnail_path: str, format_type: str = 'shorts',
                           platforms: list = None, publish_at: str = None,
                           category: str = "", cleanup: bool = True,
                           subtitle_path: str = None, tags: list = None,
                           tiktok_privacy_level: str = None,
                           tiktok_comment_disabled: bool = False,
                           tiktok_duet_disabled: bool = False,
                           tiktok_stitch_disabled: bool = False,
                           default_language: str = None,
                           tiktok_path: str = None,
                           tiktok_brand_content: bool = False,
                           tiktok_brand_organic: bool = False) -> dict:
    """Publish to multiple platforms with progress tracking.

    `tiktok_path` is the watermark-free master. TikTok's App Review rejects
    watermarked submissions, and it is the only platform that must not receive
    the channel logo, so it gets its own file while every other platform keeps
    `video_path`.

    Fail-closed, deliberately: when the pipeline is watermarking and no usable
    clean master exists, TikTok is SKIPPED rather than fed the watermarked copy.
    The earlier fallback here was a guard that could not fail -- it published
    exactly the artifact App Review rejects, so a lost clean file surfaced hours
    later as an external rejection instead of a pipeline error. Other platforms
    are unaffected, so YouTube/Facebook/Instagram still land. With
    ENABLE_WATERMARK=false `video_path` is already watermark-free, so the
    fallback is still allowed there and no caller has to know about it.
    """
    if platforms is None:
        platforms = ['youtube']

    # `video_path` is the watermarked copy exactly when this is on, so this flag
    # -- not the presence of tiktok_path -- decides whether TikTok must fail.
    _watermarking = os.getenv("ENABLE_WATERMARK", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )

    log_activity('publisher', f"Starting multi-platform publish: {title}", 'info')

    results = {
        'video_id': video_id,
        'title': title,
        'format': format_type,
        'platforms': {},
        'success_count': 0,
        'total_count': len(platforms),
        'all_success': True,
    }

    import time
    _inter_platform_delay = int(os.getenv("PLATFORM_UPLOAD_DELAY", "60"))

    for i, platform in enumerate(platforms):
        if i > 0 and _inter_platform_delay > 0:
            log_activity('publisher', f"Waiting {_inter_platform_delay}s before {PLATFORMS[platform]['name']} upload to avoid rate limiting...", 'info')
            time.sleep(_inter_platform_delay)

        try:
            platform_title = optimize_title_for_platform(title, platform)
            platform_desc = optimize_for_platform(title, description, platform)

            # TikTok takes the clean master; everything else takes the watermarked one.
            path_for_platform = video_path
            if platform == 'tiktok':
                # The question is "is this file watermark-free", not "was a second
                # path supplied". Keying the check on tiktok_path meant a caller
                # that passed none at all skipped the whole branch and shipped the
                # watermarked master -- the exact rejection, now invisible because
                # the guard looked like it was covering the case.
                _clean_ok = (tiktok_path and tiktok_path != video_path
                             and os.path.exists(tiktok_path))
                if _clean_ok:
                    path_for_platform = tiktok_path
                elif not _watermarking:
                    log_activity('publisher',
                                 f"No separate clean master for TikTok ({tiktok_path or 'none'}); "
                                 f"ENABLE_WATERMARK is off so {os.path.basename(video_path)} "
                                 "is already watermark-free", 'info')
                else:
                    # Publishing the watermarked copy would be the App Review
                    # rejection this whole path exists to prevent.
                    _why = (f"no clean master was supplied" if not tiktok_path
                            else f"the watermark-free master is missing ({tiktok_path})")
                    _msg = (f"TikTok skipped: {_why}, and this pipeline watermarks its "
                            f"output, so {os.path.basename(video_path)} would be rejected "
                            "by App Review. Other platforms still published.")
                    log_activity('publisher', _msg, 'error')
                    security_audit("TIKTOK_NO_CLEAN_MASTER", safe_log(_msg), "error")
                    results['platforms'][platform] = {
                        'success': False, 'platform': 'tiktok',
                        'error': 'watermark-free master unavailable; refusing to post a '
                                 'watermarked video',
                    }
                    results['all_success'] = False
                    continue

            log_activity('publisher', f"Uploading to {PLATFORMS[platform]['name']}...", 'info')
            result = upload_to_platform(platform, platform_title, platform_desc, path_for_platform,
                                        thumbnail_path, format_type, publish_at, subtitle_path, tags=tags,
                                        tiktok_privacy_level=tiktok_privacy_level,
                                        tiktok_comment_disabled=tiktok_comment_disabled,
                                        tiktok_duet_disabled=tiktok_duet_disabled,
                                        tiktok_stitch_disabled=tiktok_stitch_disabled,
                                        default_language=default_language,
                                        tiktok_brand_content=tiktok_brand_content,
                                        tiktok_brand_organic=tiktok_brand_organic)
            results['platforms'][platform] = result

            if result['success']:
                results['success_count'] += 1
            else:
                results['all_success'] = False

        except Exception as e:
            results['platforms'][platform] = {'success': False, 'error': str(e)}
            results['all_success'] = False

    # Update video record
    update_data = {
        # Success-only. This used to be every *attempted* platform, so a video
        # that reached 3/4 still recorded `published_platforms: [youtube, tiktok,
        # facebook, instagram]` and read as a clean 4/4 to anything counting
        # that list -- which is how a silent TikTok failure (attempted, no URL)
        # got reported as a full publish. Count what landed, not what was tried.
        'published_platforms': sorted(p for p, r in results['platforms'].items() if r.get('success')),
        'publish_urls': {p: r.get('url', r.get('video_url', '')) for p, r in results['platforms'].items() if r.get('success')},  # noqa: E501
        # Raw per-platform outcome, so a later failure can be diagnosed. The
        # success counters above are lossy: a `success` with no URL and a
        # hard failure look identical once logged, which is exactly how the
        # 09-27 TikTok miss became unrecoverable after the log rotated.
        'platform_publish_results': results['platforms'],
    }
    yt_result = results['platforms'].get('youtube', {})
    if yt_result.get('success') and yt_result.get('video_id'):
        update_data['youtube_id'] = yt_result['video_id']
        _register_in_playlist(yt_result['video_id'], category)
    update_video_record(video_id, update_data)

    # Send Telegram notification
    _send_telegram_notification(results)

    # Clean up cloud and local files after successful publish
    if results['success_count'] > 0:
        try:
            from utils.r2_storage import delete_video, delete_thumbnail
            delete_video(video_id, format_type)
            if thumbnail_path and thumbnail_path.startswith(('http://', 'https://')):
                pass
            else:
                delete_thumbnail(video_id)
        except Exception as e:
            log_activity('publisher', f"R2 cleanup skipped: {e}", 'warn')

        if cleanup:
            # Both files, not just `video_path`. The clean master is a second
            # real file on disk; deleting only the watermarked one leaked
            # ~1.5GB per long video, and the compositor temp dir is not
            # swept until the next cleanup pass.
            for _p in {video_path, tiktok_path} - {None, ''}:
                try:
                    if os.path.exists(_p):
                        size = os.path.getsize(_p)
                        os.remove(_p)
                        log_activity('publisher', f"Deleted local output: {_p} ({size / 1024 / 1024:.1f}MB)", 'info')
                except Exception as e:
                    log_activity('publisher', f"Local file cleanup skipped for {_p}: {e}", 'warn')

    log_activity(
        'publisher', f"Publish complete: {results['success_count']}/{results['total_count']} successful", 'success')
    return results


def _register_in_playlist(youtube_id: str, category: str) -> None:
    if not category:
        return
    try:
        from utils.youtube_upload import get_youtube_service
        from utils.series_router import pick_series_for_category
        from utils.series_builder import load_series, save_series, create_youtube_playlist, add_video_to_playlist, register_video_in_series

        service = get_youtube_service()
        if not service:
            return
        series = pick_series_for_category(category)
        if not series:
            return
        series_id = series.get("id", "")
        playlist_id = series.get("playlist_id", "")
        if not playlist_id:
            playlist_id = create_youtube_playlist(service, series["title"], series.get("description", ""))
            if not playlist_id:
                return
            series_map = load_series()
            if series_id in series_map:
                series_map[series_id]["playlist_id"] = playlist_id
                save_series(series_map)
        add_video_to_playlist(service, playlist_id, youtube_id)
        register_video_in_series(series_id, youtube_id, "", series.get("current_part", 0) + 1)
        log_activity("publisher", f"Added video to playlist '{series['title']}' ({playlist_id})", "info")
    except Exception as e:
        log_activity("publisher", f"Playlist registration failed: {e}", "warn")


def _send_telegram_notification(results: dict):
    """Send Telegram notification with publish results."""
    try:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not bot_token or not chat_id:
            return

        import requests
        success_urls = []
        failures = []
        for platform, result in results['platforms'].items():
            if result.get('success'):
                icon = PLATFORMS[platform]['icon']
                success_urls.append(f"{icon} {platform.title()}: {result.get('url', 'uploaded')}")
            else:
                icon = PLATFORMS.get(platform, {}).get('icon', '⚠️')
                failures.append(f"{icon} {platform.title()}: {result.get('error', 'unknown error')}")

        message = "🎬 *Video Published!*\n\n"
        message += f"📌 {results['title']}\n"
        message += f"📊 {results['success_count']}/{results['total_count']} platforms\n"
        if success_urls:
            message += "\n" + "\n".join(success_urls)
        if failures:
            message += "\n\n⚠️ *Failed:*\n" + "\n".join(failures)

        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'},
            timeout=10
        )
    except Exception as e:
        log_activity('publisher', f"Telegram notification failed: {e}", 'warn')
