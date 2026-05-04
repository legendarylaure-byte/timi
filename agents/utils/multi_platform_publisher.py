"""
Multi-Platform Publisher Agent
Handles uploads to YouTube, TikTok, Instagram, and Facebook.
Run: python -m agents.scripts.publisher --title "..." --video_path "..." --platforms youtube,tiktok
"""
import os
import json
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

def upload_to_platform(platform: str, title: str, description: str, video_path: str, thumbnail_path: str, format_type: str = 'shorts', publish_at: str = None) -> dict:
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


def _upload_youtube(title: str, description: str, video_path: str, thumbnail_path: str, format_type: str, publish_at: str = None) -> dict:
    try:
        from utils.youtube_upload import upload_video_to_youtube
        from utils.description_gen import get_coppa_metadata

        coppa_meta = get_coppa_metadata("kids content", format_type)

        tags = coppa_meta.get("tags", []) + [format_type, "vyom ai cloud"]

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

        log_activity('publisher', f"YouTube upload complete: {result.get('video_url', 'unknown')}", 'success')
        return result
    except Exception as e:
        log_activity('publisher', f"YouTube upload FAILED: {e}", 'error')
        return {
            'success': False,
            'platform': 'youtube',
            'error': str(e),
            'title': title,
        }


def _upload_tiktok(title: str, video_path: str, format_type: str) -> dict:
    """Upload to TikTok via Content Posting API."""
    return {
        'success': False,
        'platform': 'tiktok',
        'error': 'TikTok upload not yet implemented. API integration required.',
    }


def _upload_instagram(title: str, video_path: str, format_type: str) -> dict:
    """Upload to Instagram via Graph API."""
    return {
        'success': False,
        'platform': 'instagram',
        'error': 'Instagram upload not yet implemented. API integration required.',
    }


def _upload_facebook(title: str, description: str, video_path: str) -> dict:
    """Upload to Facebook via Graph API."""
    return {
        'success': False,
        'platform': 'facebook',
        'error': 'Facebook upload not yet implemented. API integration required.',
    }


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
            result = upload_to_platform(platform, title, description, video_path, thumbnail_path, format_type, publish_at)
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
    update_video_record(video_id, {
        'published_platforms': list(results['platforms'].keys()),
        'publish_urls': {p: r.get('url', r.get('video_url', '')) for p, r in results['platforms'].items() if r.get('success')},
    })
    
    # Send Telegram notification
    _send_telegram_notification(results)
    
    log_activity('publisher', f"Publish complete: {results['success_count']}/{results['total_count']} successful", 'success')
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

        message = f"🎬 *Video Published!*\n\n"
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
