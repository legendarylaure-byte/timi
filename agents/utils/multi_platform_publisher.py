"""
Multi-Platform Publisher Agent
Handles uploads to YouTube, TikTok, Instagram, and Facebook with retry, idempotency, and token refresh.
Run: python -m agents.scripts.publisher --title "..." --video_path "..." --platforms youtube,tiktok
"""
import os
import uuid
from datetime import datetime
from utils.firebase_status import get_firestore_client, log_activity, update_video_record
from compliance.ai_disclosure import get_ai_disclosure
from utils.sanitize import safe_log
from utils.platform_captions import optimize_for_platform, optimize_title_for_platform
from utils.subprocess_helper import retry_with_backoff, rate_limiter, security_audit, safe_run, register_temp_dir

_FACEBOOK_CRF = os.getenv("FACEBOOK_CRF", "30")
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
    """Persist env vars to both .env files."""
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


def upload_to_platform(platform: str, title: str, description: str, video_path: str, thumbnail_path: str, format_type: str = 'shorts', publish_at: str = None, subtitle_path: str = None, tags: list = None) -> dict:  # noqa: E501
    """Upload a video to a specific platform."""
    platform_info = PLATFORMS.get(platform)
    if not platform_info:
        return {'success': False, 'error': f'Unknown platform: {platform}'}

    log_activity('publisher', f'Uploading to {platform_info["name"]}: {title}', 'info')

    try:
        if platform == 'youtube':
            return _upload_youtube(title, description, video_path, thumbnail_path, format_type, publish_at, subtitle_path, tags=tags)
        elif platform == 'tiktok':
            return _upload_tiktok(title, video_path, format_type)
        elif platform == 'instagram':
            return _upload_instagram(title, video_path, format_type)
        elif platform == 'facebook':
            return _upload_facebook(title, description, video_path, thumbnail_path)
        else:
            return {'success': False, 'error': 'Platform not implemented'}
    except Exception as e:
        log_activity('publisher', f'Upload to {platform_info["name"]} failed: {safe_log(str(e))}', 'error')
        return {'success': False, 'error': safe_log(str(e))}


def _upload_youtube(title: str, description: str, video_path: str, thumbnail_path: str, format_type: str, publish_at: str = None, subtitle_path: str = None, tags: list = None) -> dict:  # noqa: E501
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
            tags=combined_tags[:15],
            thumbnail_file=thumbnail_path,
            category_id=tech_meta["categoryId"],
            is_shorts=(format_type == "shorts"),
            publish_at=publish_at,
            subtitle_path=subtitle_path,
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


def _upload_tiktok(title: str, video_path: str, format_type: str) -> dict:
    """Upload to TikTok via Content Posting API v2 with retry, rate limit, idempotency."""
    if not rate_limiter("tiktok_upload", max_per_hour=5):
        security_audit("RATE_LIMIT", "TikTok upload rate limit hit", "warning")
        return {'success': False, 'platform': 'tiktok', 'error': 'TikTok upload rate limit reached (max 5/hour)'}

    access_token = os.getenv('TIKTOK_ACCESS_TOKEN')
    open_id = os.getenv('TIKTOK_OPEN_ID')
    if not access_token or not open_id:
        return {
            'success': False,
            'platform': 'tiktok',
            'error': 'TikTok upload not configured. Set TIKTOK_ACCESS_TOKEN and TIKTOK_OPEN_ID env vars.',
        }

    if not os.path.exists(video_path):
        return {'success': False, 'platform': 'tiktok', 'error': f'Video file not found: {video_path}'}

    idem_key = _idempotency_key()
    _tiktok_refresh_attempted = False

    def _do_upload():
        nonlocal access_token, _tiktok_refresh_attempted
        import requests

        file_size = os.path.getsize(video_path)

        init_resp = requests.post(
            'https://open.tiktokapis.com/v2/post/publish/video/init/',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={
                'source_info': {
                    'source': 'FILE_UPLOAD',
                    'video_size': file_size,
                    'chunk_size': file_size,
                    'total_chunk_count': 1,
                }
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
            raise RuntimeError(f'TikTok init failed: {init_resp.status_code}')

        init_data = init_resp.json()
        upload_url = init_data.get('data', {}).get('upload_url')
        publish_id = init_data.get('data', {}).get('publish_id')

        if not upload_url:
            raise RuntimeError('No upload URL in TikTok init response')

        with open(video_path, 'rb') as f:
            upload_resp = requests.put(upload_url, data=f, timeout=300)

        if upload_resp.status_code not in (200, 201):
            raise RuntimeError(f'TikTok file upload failed: {upload_resp.status_code}')

        ai_flags = get_ai_disclosure("tiktok")
        publish_payload = {
            'publish_id': publish_id,
            'post_info': {
                'title': title,
                'privacy_level': 'PUBLIC_TO_EVERYONE',
                'disable_duet': False,
                'disable_comment': False,
                'disable_stitch': False,
            },
        }
        if ai_flags.get("is_aigc"):
            publish_payload["post_info"]["is_aigc"] = True

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

        if publish_resp.status_code == 200:
            if not publish_id:
                raise RuntimeError('TikTok publish succeeded but no video ID returned')
            return {
                'success': True,
                'platform': 'tiktok',
                'video_id': publish_id,
                'url': f'https://www.tiktok.com/@{open_id}/video/{publish_id}',
                'title': title,
                'status': 'published',
            }
        else:
            raise RuntimeError(f'TikTok publish failed: {publish_resp.status_code}')

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
        security_audit("RATE_LIMIT", "Instagram upload rate limit hit", "warning")
        return {'success': False, 'platform': 'instagram', 'error': 'Instagram upload rate limit reached (max 5/hour)'}

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

        media_type = 'REELS' if format_type == 'shorts' else 'VIDEO'

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


def _upload_facebook(title: str, description: str, video_path: str, thumbnail_path: str = None) -> dict:
    """Upload to Facebook via Graph API with retry, rate limit, token refresh."""
    if not rate_limiter("facebook_upload", max_per_hour=5):
        security_audit("RATE_LIMIT", "Facebook upload rate limit hit", "warning")
        return {'success': False, 'platform': 'facebook', 'error': 'Facebook upload rate limit reached (max 5/hour)'}

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
        upload_method = 'resumable' if file_size > 50 * 1024 * 1024 else 'direct'

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

            body = upload_resp.json()
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

            init_body = init_resp.json()
            _raise_fb_api_error(init_body, 'resumable init')

            upload_session_id = init_body.get('upload_session_id')
            if not upload_session_id:
                raise RuntimeError(f'No upload session ID from Facebook (size={file_size})')

            with open(upload_path, 'rb') as f:
                chunk_resp = requests.post(
                    f'https://graph.facebook.com/v25.0/{page_id}/videos',
                    params={
                        'access_token': access_token,
                        'upload_phase': 'transfer',
                        'upload_session_id': upload_session_id,
                        'start_offset': '0',
                        'idempotency_key': idem_key,
                    },
                    files={'source': f},
                    timeout=600,
                )

            _check_meta_rate_limit(chunk_resp, 'Facebook')

            if chunk_resp.status_code in (401, 403) and not _facebook_refresh_attempted:
                _facebook_refresh_attempted = True
                refreshed = _refresh_facebook_token()
                if refreshed:
                    access_token = refreshed
                    return _do_upload()

            chunk_body = chunk_resp.json()
            _raise_fb_api_error(chunk_body, 'resumable upload')

            video_id = chunk_body.get('id')
            if not video_id:
                raise RuntimeError(f'Facebook resumable upload returned no video ID (size={file_size})')
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
                           subtitle_path: str = None, tags: list = None) -> dict:
    """Publish to multiple platforms with progress tracking."""
    if platforms is None:
        platforms = ['youtube']

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
            log_activity('publisher', f"Uploading to {PLATFORMS[platform]['name']}...", 'info')
            result = upload_to_platform(platform, platform_title, platform_desc, video_path,
                                        thumbnail_path, format_type, publish_at, subtitle_path, tags=tags)
            results['platforms'][platform] = result

            # Update queue in Firestore
            _update_queue(video_id, platform, result['success'])

            if result['success']:
                results['success_count'] += 1
            else:
                results['all_success'] = False

        except Exception as e:
            results['platforms'][platform] = {'success': False, 'error': str(e)}
            results['all_success'] = False

    # Update video record
    update_data = {
        'published_platforms': list(results['platforms'].keys()),
        'publish_urls': {p: r.get('url', r.get('video_url', '')) for p, r in results['platforms'].items() if r.get('success')},  # noqa: E501
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
            try:
                if os.path.exists(video_path):
                    size = os.path.getsize(video_path)
                    os.remove(video_path)
                    log_activity('publisher', f"Deleted local output: {video_path} ({size / 1024 / 1024:.1f}MB)", 'info')
            except Exception as e:
                log_activity('publisher', f"Local file cleanup skipped: {e}", 'warn')

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


def _update_queue(video_id: str, platform: str, success: bool):
    """Update upload queue in Firestore."""
    try:
        db = get_firestore_client()
        doc_ref = db.collection('upload_queue').document(video_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            progress = data.get('progress', {})
            progress[platform] = 100 if success else 0
            doc_ref.update({
                'progress': progress,
                'status': 'published' if all(v == 100 for v in progress.values()) else 'failed',
            })
    except Exception as e:
        log_activity('publisher', f"Upload queue update failed for {video_id}: {e}", 'warn')


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


def schedule_upload(video_id: str, title: str, platforms: list, scheduled_time: str):
    """Schedule an upload for later."""
    try:
        db = get_firestore_client()
        db.collection('upload_queue').add({
            'video_id': video_id,
            'title': title,
            'platforms': platforms,
            'status': 'queued',
            'scheduled_time': scheduled_time,
            'progress': {p: 0 for p in platforms},
            'created_at': datetime.utcnow(),
        })
        log_activity('publisher', f"Scheduled upload: {title} at {scheduled_time}", 'info')
    except Exception as e:
        log_activity('publisher', f"Schedule failed: {e}", 'warn')
