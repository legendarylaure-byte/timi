"""
Multi-Platform Publisher Agent
Handles uploads to YouTube, TikTok, Instagram, and Facebook.
Run: python -m agents.scripts.publisher --title "..." --video_path "..." --platforms youtube,tiktok
"""
import os
from datetime import datetime
from utils.firebase_status import get_firestore_client, log_activity, update_video_record

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
        'endpoint': 'https://graph.facebook.com/v18.0/{page_id}/media',
    },
    'facebook': {
        'name': 'Facebook',
        'icon': '👤',
        'color': '#1877F2',
        'api': 'Facebook Graph API',
        'endpoint': 'https://graph.facebook.com/v18.0/{page_id}/videos',
    },
}


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
        log_activity('publisher', f'Upload to {platform_info["name"]} failed: {str(e)}', 'error')
        return {'success': False, 'error': str(e)}


def _upload_youtube(title: str, description: str, video_path: str, thumbnail_path: str, format_type: str, publish_at: str = None) -> dict:  # noqa: E501
    try:
        from utils.youtube_upload import upload_video_to_youtube
        from utils.description_gen import get_coppa_metadata

        coppa_meta = get_coppa_metadata("kids content", format_type)

        tags = coppa_meta.get("tags", []) + [format_type, "vyom ai cloud"]

        print(f"[PUBLISHER] Uploading YouTube video: {title} (format={format_type}, publish_at={publish_at})")
        result = upload_video_to_youtube(
            video_file=video_path,
            title=title,
            description=description,
            tags=tags[:15],
            thumbnail_file=thumbnail_path,
            category_id=coppa_meta["categoryId"],
            is_shorts=(format_type == "shorts"),
            publish_at=publish_at,
        )

        result["made_for_kids"] = True
        result["coppa_compliant"] = True

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
    """Upload to TikTok via Content Posting API v2."""
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

    try:
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

        if init_resp.status_code != 200:
            return {
                'success': False, 'platform': 'tiktok',
                'error': f'Init failed: {init_resp.status_code} {init_resp.text}',
            }

        init_data = init_resp.json()
        upload_url = init_data.get('data', {}).get('upload_url')
        publish_id = init_data.get('data', {}).get('publish_id')

        if not upload_url:
            return {
                'success': False, 'platform': 'tiktok',
                'error': 'No upload URL in init response',
            }

        with open(video_path, 'rb') as f:
            upload_resp = requests.put(upload_url, data=f, timeout=300)

        if upload_resp.status_code not in (200, 201):
            return {
                'success': False, 'platform': 'tiktok',
                'error': f'Upload failed: {upload_resp.status_code}',
            }

        publish_resp = requests.post(
            'https://open.tiktokapis.com/v2/post/publish/video/publish/',
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={
                'publish_id': publish_id,
                'post_info': {
                    'title': title,
                    'privacy_level': 'PUBLIC_TO_EVERYONE',
                    'disable_duet': False,
                    'disable_comment': False,
                    'disable_stitch': False,
                },
            },
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
            return {
                'success': False, 'platform': 'tiktok',
                'error': f'Publish failed: {publish_resp.status_code} {publish_resp.text}',
            }

    except ImportError:
        return {'success': False, 'platform': 'tiktok', 'error': 'Missing requests library'}
    except Exception as e:
        return {'success': False, 'platform': 'tiktok', 'error': str(e)}


def _upload_instagram(title: str, video_path: str, format_type: str) -> dict:
    """Upload to Instagram via Graph API."""
    access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
    ig_account_id = os.getenv('INSTAGRAM_ACCOUNT_ID')
    if not access_token or not ig_account_id:
        return {
            'success': False,
            'platform': 'instagram',
            'error': 'Instagram upload not configured. Set FACEBOOK_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID env vars.',
        }

    if not os.path.exists(video_path):
        return {'success': False, 'platform': 'instagram', 'error': f'Video file not found: {video_path}'}

    try:
        import requests

        media_type = 'REELS' if format_type == 'shorts' else 'VIDEO'

        create_resp = requests.post(
            f'https://graph.facebook.com/v18.0/{ig_account_id}/media',
            params={
                'access_token': access_token,
                'media_type': media_type,
                'video_url': '',  # Requires a publicly accessible URL
                'caption': title,
                'share_to_feed': 'true' if format_type == 'long' else 'false',
            },
            timeout=30,
        )

        if create_resp.status_code != 200:
            return {
                'success': False, 'platform': 'instagram',
                'error': f'Media creation failed: {create_resp.status_code} {create_resp.text}',
            }

        creation_id = create_resp.json().get('id')
        if not creation_id:
            return {
                'success': False, 'platform': 'instagram',
                'error': 'No media creation ID returned',
            }

        import time
        max_retries = 12
        for attempt in range(max_retries):
            status_resp = requests.get(
                f'https://graph.facebook.com/v18.0/{creation_id}',
                params={'access_token': access_token, 'fields': 'status_code'},
                timeout=15,
            )
            if status_resp.status_code == 200:
                status_code = status_resp.json().get('status_code')
                if status_code == 'FINISHED':
                    break
                elif status_code == 'ERROR':
                    return {
                        'success': False, 'platform': 'instagram',
                        'error': 'Media processing failed on Instagram',
                    }
            time.sleep(2)

        publish_resp = requests.post(
            f'https://graph.facebook.com/v18.0/{ig_account_id}/media_publish',
            params={'access_token': access_token, 'creation_id': creation_id},
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
            return {
                'success': False, 'platform': 'instagram',
                'error': f'Publish failed: {publish_resp.status_code} {publish_resp.text}',
            }

    except ImportError:
        return {'success': False, 'platform': 'instagram', 'error': 'Missing requests library'}
    except Exception as e:
        return {'success': False, 'platform': 'instagram', 'error': str(e)}


def _upload_facebook(title: str, description: str, video_path: str) -> dict:
    """Upload to Facebook via Graph API."""
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

    try:
        import requests

        file_size = os.path.getsize(video_path)
        if file_size > 100 * 1024 * 1024:
            upload_method = 'resumable'
        else:
            upload_method = 'direct'

        if upload_method == 'direct':
            with open(video_path, 'rb') as f:
                upload_resp = requests.post(
                    f'https://graph.facebook.com/v18.0/{page_id}/videos',
                    params={'access_token': access_token},
                    files={'source': f},
                    data={
                        'title': title,
                        'description': description,
                        'published': 'true',
                    },
                    timeout=600,
                )

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
                return {
                    'success': False, 'platform': 'facebook',
                    'error': f'Upload failed: {upload_resp.status_code} {upload_resp.text}',
                }
        else:
            init_resp = requests.post(
                f'https://graph.facebook.com/v18.0/{page_id}/videos',
                params={
                    'access_token': access_token,
                    'title': title,
                    'description': description,
                    'upload_phase': 'start',
                    'file_size': file_size,
                },
                timeout=30,
            )

            if init_resp.status_code != 200:
                return {
                    'success': False, 'platform': 'facebook',
                    'error': f'Resumable init failed: {init_resp.status_code} {init_resp.text}',
                }

            upload_session_id = init_resp.json().get('upload_session_id')
            if not upload_session_id:
                return {
                    'success': False, 'platform': 'facebook',
                    'error': 'No upload session ID returned',
                }

            with open(video_path, 'rb') as f:
                chunk_resp = requests.post(
                    f'https://graph.facebook.com/v18.0/{page_id}/videos',
                    params={
                        'access_token': access_token,
                        'upload_phase': 'transfer',
                        'upload_session_id': upload_session_id,
                        'start_offset': '0',
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
                return {
                    'success': False, 'platform': 'facebook',
                    'error': f'Resumable upload failed: {chunk_resp.status_code} {chunk_resp.text}',
                }

    except ImportError:
        return {'success': False, 'platform': 'facebook', 'error': 'Missing requests library'}
    except Exception as e:
        return {'success': False, 'platform': 'facebook', 'error': str(e)}


def multi_platform_publish(video_id: str, title: str, description: str, video_path: str,
                           thumbnail_path: str, format_type: str = 'shorts',
                           platforms: list = None, publish_at: str = None) -> dict:
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
            log_activity('publisher', f"Uploading to {PLATFORMS[platform]['name']}...", 'info')
            result = upload_to_platform(platform, title, description, video_path,
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
    update_video_record(video_id, update_data)

    # Send Telegram notification
    _send_telegram_notification(results)

    log_activity(
        'publisher', f"Publish complete: {results['success_count']}/{results['total_count']} successful", 'success')
    return results


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
