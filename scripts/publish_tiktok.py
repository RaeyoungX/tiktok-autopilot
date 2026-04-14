#!/usr/bin/env python3
"""
TikTok Autopilot — Photo Post Publisher
Uploads local slides to a temp host, then posts via TikTok Content Posting API.

Usage:
    # First time: OAuth setup (opens browser, saves token)
    python3 publish_tiktok.py --auth

    # Publish a post
    python3 publish_tiktok.py \
        --slides /tmp/tiktok-lingomock/post-01-v2/ \
        --caption "Your caption here #hashtag"

Dependencies:
    pip3 install tiktok-api-client requests
"""

import argparse
import json
import os
import sys
import time
import webbrowser
import threading
import requests
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import dotenv_values, set_key

SKILL_DIR = Path(__file__).parent.parent
ENV_PATH = SKILL_DIR / ".env"
env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

TIKTOK_CLIENT_KEY = env.get("TIKTOK_CLIENT_KEY") or os.environ.get("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = env.get("TIKTOK_CLIENT_SECRET") or os.environ.get("TIKTOK_CLIENT_SECRET")
TIKTOK_ACCESS_TOKEN = env.get("TIKTOK_ACCESS_TOKEN") or os.environ.get("TIKTOK_ACCESS_TOKEN")

REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = ["video.publish", "user.info.basic"]

# ── OAuth: one-time setup ──────────────────────────────────────────────────

class CallbackHandler(BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            CallbackHandler.code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization failed. No code received.</h2>")
    def log_message(self, *args):
        pass  # suppress server logs


def do_oauth():
    if not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        print("ERROR: Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env first")
        print(f"  Edit: {ENV_PATH}")
        print("\n  Get your keys at: https://developers.tiktok.com/")
        sys.exit(1)

    from tiktok_api_client import TikTok
    client = TikTok(
        client_key=TIKTOK_CLIENT_KEY,
        client_secret=TIKTOK_CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scopes=SCOPES,
    )

    auth_url = client.get_authorization_url()
    print(f"\nOpening browser for TikTok authorization...")
    print(f"URL: {auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to catch callback
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server.timeout = 120
    print("Waiting for authorization (120s timeout)...")
    while CallbackHandler.code is None:
        server.handle_request()

    code = CallbackHandler.code
    print(f"Got authorization code. Exchanging for tokens...")

    token_data = client.exchange_code_for_token(code=code)
    access_token = token_data.get("access_token") or token_data.get("data", {}).get("access_token")

    if not access_token:
        print(f"ERROR: Unexpected token response: {token_data}")
        sys.exit(1)

    # Save to .env
    set_key(str(ENV_PATH), "TIKTOK_ACCESS_TOKEN", access_token)
    if "refresh_token" in token_data:
        set_key(str(ENV_PATH), "TIKTOK_REFRESH_TOKEN", token_data["refresh_token"])

    print(f"\n✓ Access token saved to {ENV_PATH}")
    print("  Run publish_tiktok.py --slides <dir> --caption '<text>' to post")


# ── Image hosting: upload to 0x0.st (no-auth temp host) ───────────────────

def upload_image_temp(filepath: Path) -> str:
    """Upload image to 0x0.st and return public URL."""
    print(f"  Uploading {filepath.name} to temp host...")
    with open(filepath, "rb") as f:
        resp = requests.post(
            "https://0x0.st",
            files={"file": (filepath.name, f, "image/jpeg")},
            timeout=30,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    print(f"  ✓ {url}")
    return url


# ── TikTok API: post photo ─────────────────────────────────────────────────

def post_photo(access_token: str, photo_urls: list[str], caption: str, cover_index: int = 0):
    """Call TikTok Content Posting API to create a photo post."""
    endpoint = "https://open.tiktokapis.com/v2/post/publish/content/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    payload = {
        "post_info": {
            "title": caption[:90],           # max 90 runes for title
            "description": caption,           # full caption with hashtags
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "photo_images": photo_urls,
            "photo_cover_index": cover_index,
        },
        "post_mode": "DIRECT_POST",
        "media_type": "PHOTO",
    }

    print("\nCalling TikTok Content Posting API...")
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)

    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}

    if resp.status_code == 200 and data.get("error", {}).get("code") == "ok":
        post_id = data.get("data", {}).get("publish_id", "unknown")
        print(f"\n✓ Photo post published! publish_id: {post_id}")
        return data
    else:
        print(f"\n✗ API error ({resp.status_code}): {json.dumps(data, indent=2)}")
        return None


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TikTok photo post publisher")
    parser.add_argument("--auth", action="store_true", help="Run OAuth setup (first time only)")
    parser.add_argument("--slides", help="Path to folder containing slide_*.jpg files")
    parser.add_argument("--caption", help="Post caption with hashtags")
    parser.add_argument("--cover", type=int, default=0, help="Cover image index (0-based)")
    args = parser.parse_args()

    if args.auth:
        do_oauth()
        return

    if not args.slides or not args.caption:
        parser.print_help()
        sys.exit(1)

    # Load fresh env
    env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    access_token = env.get("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        print("ERROR: No access token. Run: python3 publish_tiktok.py --auth")
        sys.exit(1)

    # Find slides
    slides_dir = Path(args.slides)
    slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not slides:
        print(f"ERROR: No slide_*.jpg files found in {slides_dir}")
        sys.exit(1)

    print(f"\nFound {len(slides)} slides in {slides_dir}")
    print(f"Caption: {args.caption[:60]}...")

    # Upload to temp host
    print("\nUploading images to temporary host (0x0.st)...")
    photo_urls = []
    for slide in slides:
        url = upload_image_temp(slide)
        photo_urls.append(url)
        time.sleep(0.5)  # be gentle

    # Post to TikTok
    result = post_photo(access_token, photo_urls, args.caption, args.cover)
    if result:
        print("\nPost live on TikTok! Check your profile.")
    else:
        print("\nPost failed. Check error above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
