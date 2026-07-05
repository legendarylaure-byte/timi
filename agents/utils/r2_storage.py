import os
import boto3
from botocore.client import Config
from datetime import datetime

ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
ACCESS_KEY = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
BUCKET = os.getenv("CLOUDFLARE_R2_BUCKET", "vyom-ai-videos")

_r2_client = None


def get_r2_client():
    global _r2_client
    if _r2_client is not None:
        return _r2_client
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    access_key = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
    secret_key = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
    if not (account_id and access_key and secret_key):
        raise ValueError("Cloudflare R2 credentials not configured (set CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_R2_ACCESS_KEY_ID, CLOUDFLARE_R2_SECRET_ACCESS_KEY)")
    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    _r2_client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )
    return _r2_client


def upload_video(file_path: str, video_id: str, format_type: str = "long") -> str:
    client = get_r2_client()
    ext = os.path.splitext(file_path)[1]
    key = f"videos/{video_id}_{format_type}{ext}"

    with open(file_path, "rb") as f:
        client.upload_fileobj(
            f,
            BUCKET,
            key,
            ExtraArgs={
                "ContentType": "video/mp4",
                "Metadata": {
                    "uploaded-at": datetime.utcnow().isoformat(),
                    "format": format_type,
                    "auto-delete": "true",
                    "delete-after-days": "1",
                },
            },
        )

    public_url = f"https://pub-{ACCOUNT_ID}.r2.dev/{key}"
    print(f"Uploaded to R2: {key} -> {public_url}")
    return public_url


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    client = get_r2_client()
    url = client.generate_presigned_url(
        ClientMethod='get_object',
        Params={'Bucket': BUCKET, 'Key': key},
        ExpiresIn=expires_in,
    )
    return url


def upload_thumbnail(file_path: str, video_id: str) -> str:
    client = get_r2_client()
    ext = os.path.splitext(file_path)[1]
    key = f"thumbnails/{video_id}{ext}"

    with open(file_path, "rb") as f:
        client.upload_fileobj(
            f,
            BUCKET,
            key,
            ExtraArgs={
                "ContentType": "image/jpeg",
                "Metadata": {
                    "uploaded-at": datetime.utcnow().isoformat(),
                },
            },
        )

    public_url = f"https://pub-{ACCOUNT_ID}.r2.dev/{key}"
    print(f"Uploaded thumbnail to R2: {key} -> {public_url}")
    return public_url


def delete_video(video_id: str, format_type: str = "long"):
    client = get_r2_client()
    ext = ".mp4"
    key = f"videos/{video_id}_{format_type}{ext}"

    try:
        client.delete_object(Bucket=BUCKET, Key=key)
        print(f"Deleted from R2: {key}")
        return True
    except Exception as e:
        print(f"Failed to delete {key}: {e}")
        return False


def delete_thumbnail(video_id: str):
    client = get_r2_client()
    ext = ".jpg"
    key = f"thumbnails/{video_id}{ext}"

    try:
        client.delete_object(Bucket=BUCKET, Key=key)
        print(f"Deleted thumbnail from R2: {key}")
        return True
    except Exception as e:
        print(f"Failed to delete {key}: {e}")
        return False


def list_pending_deletion() -> list:
    client = get_r2_client()
    response = client.list_objects_v2(Bucket=BUCKET, Prefix="videos/")

    pending = []
    now = datetime.utcnow()

    for obj in response.get("Contents", []):
        metadata = client.head_object(Bucket=BUCKET, Key=obj["Key"])
        meta = metadata.get("Metadata", {})
        if meta.get("auto-delete") == "true":
            uploaded_at = datetime.fromisoformat(meta.get("uploaded-at", ""))
            hours_since_upload = (now - uploaded_at).total_seconds() / 3600
            if hours_since_upload >= 24:
                pending.append(obj["Key"])

    return pending


def cleanup_old_videos() -> dict:
    pending_keys = list_pending_deletion()
    deleted = {"success": 0, "failed": 0, "errors": []}

    client = get_r2_client()
    for key in pending_keys:
        try:
            client.delete_object(Bucket=BUCKET, Key=key)
            print(f"Auto-deleted: {key}")
            deleted["success"] += 1
        except Exception as e:
            print(f"Failed to delete {key}: {e}")
            deleted["failed"] += 1
            deleted["errors"].append({"key": key, "error": str(e)})

    print(f"Cleanup complete: {deleted['success']} deleted, {deleted['failed']} failed")
    return deleted


def delete_orphan_r2_objects() -> dict:
    """Delete R2 objects whose video_id no longer exists in Firestore.

    Scans both videos/ and thumbnails/ prefixes, cross-references with
    Firestore, and removes orphans.
    """
    result = {"deleted": 0, "failed": 0, "errors": [], "scanned": 0}
    try:
        from utils.firebase_status import get_firestore_client
        db = get_firestore_client()
        if db is None:
            result["errors"].append("Firestore unavailable")
            return result

        existing_ids = set()
        for doc in db.collection('videos').stream():
            existing_ids.add(doc.id)

        client = get_r2_client()
        for prefix in ("videos/", "thumbnails/"):
            response = client.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
            for obj in response.get("Contents", []):
                result["scanned"] += 1
                key = obj["Key"]
                video_id = key.split("/")[-1].replace(".mp4", "").replace(".jpg", "")
                if "_" in video_id and prefix == "videos/":
                    video_id = video_id.split("_")[0]

                if video_id not in existing_ids:
                    try:
                        client.delete_object(Bucket=BUCKET, Key=key)
                        result["deleted"] += 1
                        print(f"[R2] Deleted orphan: {key}")
                    except Exception as e:
                        result["failed"] += 1
                        result["errors"].append(str(e))
                        print(f"[R2] Failed to delete orphan {key}: {e}")

        if result["deleted"]:
            print(f"[R2] Orphan cleanup: {result['deleted']} deleted, {result['scanned']} scanned")
        return result
    except Exception as e:
        result["errors"].append(str(e))
        return result
