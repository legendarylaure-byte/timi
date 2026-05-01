import os
import boto3
from botocore.client import Config
from datetime import datetime

ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
ACCESS_KEY = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
BUCKET = os.getenv("CLOUDFLARE_R2_BUCKET", "vyom-ai-videos")

if ACCOUNT_ID and ACCESS_KEY and SECRET_KEY:
    R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
    r2_client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )
else:
    r2_client = None

def get_r2_client():
    if r2_client is None:
        raise ValueError("Cloudflare R2 credentials not configured")
    return r2_client

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

    for key in pending_keys:
        try:
            r2_client.delete_object(Bucket=BUCKET, Key=key)
            print(f"Auto-deleted: {key}")
            deleted["success"] += 1
        except Exception as e:
            print(f"Failed to delete {key}: {e}")
            deleted["failed"] += 1
            deleted["errors"].append({"key": key, "error": str(e)})

    print(f"Cleanup complete: {deleted['success']} deleted, {deleted['failed']} failed")
    return deleted
