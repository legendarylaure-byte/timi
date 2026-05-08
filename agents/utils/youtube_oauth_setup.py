import os
import webbrowser
import urllib.parse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "839918420419-88cjde4sjnt3s18stnaehoaggtdcp617.apps.googleusercontent.com")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "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")
TOKEN_FILE = "./youtube_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtubepartner",
]


def setup_oauth():
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri=http://localhost:8080"
        f"&response_type=code"
        f"&scope={' '.join(SCOPES)}"
        f"&access_type=offline"
        f"&prompt=consent"
    )

    print("=" * 60)
    print("YouTube OAuth Setup")
    print("=" * 60)
    print()
    print("Step 1: Open this URL in your browser:")
    print()
    print(auth_url)
    print()

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("Step 2: After authorizing, you'll be redirected to a URL like:")
    print("  http://localhost:8080/?code=4/0A...")
    print()
    print("Copy the full redirected URL and paste it below:")
    print()

    redirect_url = input("Redirected URL: ").strip()

    if not redirect_url or "code=" not in redirect_url:
        print("No authorization code found in the URL.")
        return

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)["code"][0]

    print()
    print("Step 3: Exchanging code for tokens...")

    import requests

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": "http://localhost:8080",
            "grant_type": "authorization_code",
        },
    )

    if token_response.status_code == 200:
        token_data = token_response.json()
        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

        print(f"SUCCESS! Token saved to {TOKEN_FILE}")
        print()

        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.channels().list(part="snippet,statistics", mine=True).execute()

        if response.get("items"):
            channel = response["items"][0]
            print(f"Connected to: {channel['snippet']['title']}")
            print(f"Subscribers: {channel['statistics'].get('subscriberCount', 'N/A')}")
            print(f"Videos: {channel['statistics'].get('videoCount', 'N/A')}")
    else:
        print(f"Token exchange failed: {token_response.status_code}")
        print(token_response.text)


if __name__ == "__main__":
    setup_oauth()
