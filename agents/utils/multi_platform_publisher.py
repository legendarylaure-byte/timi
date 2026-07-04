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
from utils.platform_captions import optimize_for_platform
from utils.subprocess_helper import retry_with_backoff, rate_limiter, security_audit

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
                return new_token
        return None
    except Exception:
        return None


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
                return new_token
        return None
    except Exception:
        return None


def _idempotency_key() -> str:
    return str(uuid.uuid4())


def upload_to_platform(platform: str, title: str, description: str, video_path: str, thumbnail_path: str, format_type: str = 'shorts', publish_at: str = None) -> dict:  # noqa: E501
    """Upload a video to a specific platform."""
    platform_info = PLATFORMS.get(platform)
    if not platform_info:
        return {'success': False, 'error': f'Unknown platform: {platform}'}

    log_activity('publisher', f'Uploading to {platform_info["name"]}: {title}', 'info')

    try:
        if platform == 'youtube':
            return _upload_youtube(title, description, video_path, thumbnail_path, format_type, publish_at)
        elif platform == 'tiktok':
            return _upload_tiktok(title, video_path, format_type)
        elif platform == 'instagram':
            return _upload_instagram(title, video_path, format_type)
        elif platform == 'facebook':
            return _upload_facebook(title, description, video_path)
        else:
            return {'success': False, 'error': 'Platform not implemented'}
    except Exception as e:
        log_activity('publisher', f'Upload to {platform_info["name"]} failed: {safe_log(str(e))}', 'error')
        return {'success': False, 'error': safe_log(str(e))}


def _upload_youtube(title: str, description: str, video_path: str, thumbnail_path: str, format_type: str, publish_at: str = None) -> dict:  # noqa: E501
    try:
        from utils.youtube_upload import upload_video_to_youtube
        from utils.description_gen import get_tech_metadata

        tech_meta = get_tech_metadata("tech educational", format_type, title)

        tags = tech_meta.get("tags", []) + [format_type, "vyom-ai-cloud", "ai", "technology"]

        print(f"[PUBLISHER] Uploading YouTube video: {title} (format={format_type}, publish_at={publish_at})")
        result = upload_video_to_youtube(
            video_file=video_path,
            title=title,
            description=description,
            tags=tags[:15],
            thumbnail_file=thumbnail_path,
            category_id=tech_meta["categoryId"],
            is_shorts=(format_type == "shorts"),
            publish_at=publish_at,
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
        print(f"[PUBLISHER] YouTube upload exception: {e}")
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

    def _do_upload():
        nonlocal access_token
        import requests

        file_size = os.path.getsize(video_path)
        idem_key = _idempotency_key()

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

        if init_resp.status_code == 401:
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
            return {
                'success': True,
                'platform': 'tiktok',
                'video_id': publish_id,
                'url': f'https://www.tiktok.com/@{open_id}/video/{publish_id}' if publish_id else '',
                'title': title,
                'status': 'published',
            }
        else:
            raise RuntimeError(f'TikTok publish failed: {publish_resp.status_code}')

    try:
        ok, result = retry_with_backoff(_do_upload, max_retries=3, base_delay=5, max_delay=60)
        if ok:
            return result
        security_audit("UPLOAD_FAILED", f"TikTok — {safe_log(str(result)[:200])}", "error")
        return {
            'success': False, 'platform': 'tiktok',
            'error': safe_log(str(result)),
        }
    except ImportError:
        return {'success': False, 'platform': 'tiktok', 'error': 'Missing requests library'}
    except Exception as e:
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

    instagram_video_url = os.getenv('INSTAGRAM_VIDEO_URL', '')
    if not instagram_video_url:
        if video_path.startswith(('http://', 'https://')):
            instagram_video_url = video_path
        else:
            return {
                'success': False, 'platform': 'instagram',
                'error': 'Instagram Graph API requires a public URL. Set INSTAGRAM_VIDEO_URL env var or pass a URL.',
            }

    def _do_upload():
        nonlocal access_token
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

        if create_resp.status_code == 401:
            refreshed = _refresh_facebook_token()
            if refreshed:
                access_token = refreshed
                return _do_upload()

        if create_resp.status_code != 200:
            raise RuntimeError(f'Instagram media creation failed: {create_resp.status_code}')

        creation_id = create_resp.json().get('id')
        if not creation_id:
            raise RuntimeError('No media creation ID from Instagram')

        import time
        poll_attempts = 12
        for attempt in range(poll_attempts):
            status_resp = requests.get(
                f'https://graph.facebook.com/v25.0/{creation_id}',
                params={'access_token': access_token, 'fields': 'status_code'},
                timeout=15,
            )
            if status_resp.status_code == 200:
                status_code = status_resp.json().get('status_code')
                if status_code == 'FINISHED':
                    break
                elif status_code == 'ERROR':
                    raise RuntimeError('Instagram media processing failed')
            time.sleep(2)

        idem_key = _idempotency_key()
        publish_resp = requests.post(
            f'https://graph.facebook.com/v25.0/{ig_account_id}/media_publish',
            params={'access_token': access_token, 'creation_id': creation_id, 'idempotency_key': idem_key},
            timeout=30,
        )

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
        security_audit("UPLOAD_FAILED", f"Instagram — {safe_log(str(result)[:200])}", "error")
        return {
            'success': False, 'platform': 'instagram',
            'error': safe_log(str(result)),
        }
    except ImportError:
        return {'success': False, 'platform': 'instagram', 'error': 'Missing requests library'}
    except Exception as e:
        security_audit("UPLOAD_FAILED", f"Instagram — {safe_log(str(e)[:200])}", "error")
        return {'success': False, 'platform': 'instagram', 'error': safe_log(str(e))}


def _upload_facebook(title: str, description: str, video_path: str) -> dict:
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

    def _do_upload():
        nonlocal access_token
        import requests

        file_size = os.path.getsize(video_path)
        upload_method = 'resumable' if file_size > 100 * 1024 * 1024 else 'direct'

        ai_flags = get_ai_disclosure("facebook")
        fb_description = description
        if ai_flags.get("caption_hashtag"):
            fb_description += f"\n\n{ai_flags['caption_hashtag']}"

        if upload_method == 'direct':
            idem_key = _idempotency_key()
            with open(video_path, 'rb') as f:
                upload_resp = requests.post(
                    f'https://graph.facebook.com/v25.0/{page_id}/videos',
                    params={'access_token': access_token, 'idempotency_key': idem_key},
                    files={'source': f},
                    data={
                        'title': title,
                        'description': fb_description,
                        'published': 'true',
                    },
                    timeout=600,
                )

            if upload_resp.status_code == 401:
                refreshed = _refresh_facebook_token()
                if refreshed:
                    access_token = refreshed
                    return _do_upload()

            if upload_resp.status_code == 200:
                video_id = upload_resp.json().get('id')
                return {
                    'success': True,
                    'platform': 'facebook',
                    'video_id': video_id,
                    'url': f'https://www.facebook.com/watch/?v={video_id}' if video_id else '',
                    'title': title,
                    'status': 'published',
                }
            else:
                raise RuntimeError(f'Facebook direct upload failed: {upload_resp.status_code}')
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

            if init_resp.status_code == 401:
                refreshed = _refresh_facebook_token()
                if refreshed:
                    access_token = refreshed
                    return _do_upload()

            if init_resp.status_code != 200:
                raise RuntimeError(f'Facebook resumable init failed: {init_resp.status_code}')

            upload_session_id = init_resp.json().get('upload_session_id')
            if not upload_session_id:
                raise RuntimeError('No upload session ID from Facebook')

            idem_key = _idempotency_key()
            with open(video_path, 'rb') as f:
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

            if chunk_resp.status_code == 200:
                video_id = chunk_resp.json().get('id')
                return {
                    'success': True,
                    'platform': 'facebook',
                    'video_id': video_id,
                    'url': f'https://www.facebook.com/watch/?v={video_id}' if video_id else '',
                    'title': title,
                    'status': 'published',
                }
            else:
                raise RuntimeError(f'Facebook resumable upload failed: {chunk_resp.status_code}')

    try:
        ok, result = retry_with_backoff(_do_upload, max_retries=3, base_delay=5, max_delay=60)
        if ok:
            return result
        security_audit("UPLOAD_FAILED", f"Facebook — {safe_log(str(result)[:200])}", "error")
        return {
            'success': False, 'platform': 'facebook',
            'error': safe_log(str(result)),
        }
    except ImportError:
        return {'success': False, 'platform': 'facebook', 'error': 'Missing requests library'}
    except Exception as e:
        security_audit("UPLOAD_FAILED", f"Facebook — {safe_log(str(e)[:200])}", "error")
        return {'success': False, 'platform': 'facebook', 'error': safe_log(str(e))}


def multi_platform_publish(video_id: str, title: str, description: str, video_path: str,
                           thumbnail_path: str, format_type: str = 'shorts',
                           platforms: list = None, publish_at: str = None,
                           category: str = "", cleanup: bool = True) -> dict:
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

    for platform in platforms:
        try:
            platform_desc = optimize_for_platform(title, description, platform)
            log_activity('publisher', f"Uploading to {PLATFORMS[platform]['name']}...", 'info')
            result = upload_to_platform(platform, title, platform_desc, video_path,
                                        thumbnail_path, format_type, publish_at)
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
    except Exception:
        pass


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
        print(f"[PUBLISHER] Telegram notification failed: {e}")


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
        print(f"[PUBLISHER] Schedule failed: {e}")
