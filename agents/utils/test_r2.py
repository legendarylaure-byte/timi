#!/usr/bin/env python3
"""Test Cloudflare R2 connection and bucket access"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from utils.r2_storage import get_r2_client, BUCKET

try:
    client = get_r2_client()
    response = client.list_buckets()
    buckets = [b["Name"] for b in response.get("Buckets", [])]

    print(f"✅ R2 Connection Successful!")
    print(f"Account: {os.getenv('CLOUDFLARE_ACCOUNT_ID')}")
    print(f"Bucket: {BUCKET}")
    print(f"Available buckets: {buckets}")

    if BUCKET in buckets:
        print(f"✅ Bucket '{BUCKET}' exists and is accessible")
    else:
        print(f"⚠️  Bucket '{BUCKET}' not found. Available: {buckets}")
        print(f"   Create it in Cloudflare R2 dashboard or use one of the above")

except Exception as e:
    print(f"❌ R2 Connection Failed: {e}")
    sys.exit(1)
