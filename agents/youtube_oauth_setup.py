import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import os

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
TOKEN_FILE = "./youtube_token.json"

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in environment")
    exit(1)

auth_url = (
    "https://accounts.google.com/o/oauth2/auth?"
    "response_type=code"
    f"&client_id={CLIENT_ID}"
    "&redirect_uri=http://localhost:8080"
    "&scope=https://www.googleapis.com/auth/youtube.upload+https://www.googleapis.com/auth/youtube+https://www.googleapis.com/auth/yt-analytics.readonly"
    "&access_type=offline&prompt=consent"
)

print("=" * 60)
print("YouTube OAuth Setup")
print("=" * 60)
print()
print("1. Opening browser to Google authorization page...")
try:
    webbrowser.open(auth_url)
except Exception:
    print("   Could not open browser automatically. Use this URL:")
    print()
    print(auth_url)
    print()

print("2. Authorize the app (click Advanced > Go to unsafe > Allow)")
print("3. After allowing, copy the FULL URL from your browser address bar")
print("   (it starts with http://localhost:8080/?code=...)")
print()

redirect_url = input("Paste the redirected URL here: ").strip()

if not redirect_url or "code=" not in redirect_url:
    print("ERROR: No authorization code found.")
    exit(1)

code = parse_qs(urlparse(redirect_url).query)["code"][0]
print("Exchanging code for tokens...")

resp = requests.post("https://oauth2.googleapis.com/token", data={
    "code": code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": "http://localhost:8080",
    "grant_type": "authorization_code",
})

if resp.status_code == 200:
    token_data = resp.json()
    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
        ],
    )

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print("SUCCESS! Token saved.")
    print()

    youtube = build("youtube", "v3", credentials=creds)
    response = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    if response.get("items"):
        ch = response["items"][0]
        print(f"Connected to: {ch['snippet']['title']}")
        print(f"Subscribers: {ch['statistics'].get('subscriberCount', 'hidden')}")
        print(f"Videos: {ch['statistics'].get('videoCount', '0')}")
else:
    print(f"ERROR: {resp.status_code}")
    print(resp.text)
