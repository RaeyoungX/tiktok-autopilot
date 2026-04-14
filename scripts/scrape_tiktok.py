#!/usr/bin/env python3
"""
TikTok Autopilot — Phase 2: Viral Scraper
Uses Apify TikTok scraper to get metadata + yt-dlp to download top videos.

Usage:
    python3 scrape_tiktok.py \
        --keywords "english speaking practice,speak english confidently,english freeze" \
        --product lingomock \
        --limit 15

Output:
    ~/.claude/tiktok-autopilot/{product}/{date}.json   — structured post data
    /tmp/tiktok-{product}/scrape/{keyword}/            — downloaded videos

Dependencies:
    pip3 install apify-client yt-dlp
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from dotenv import dotenv_values

SKILL_DIR = Path(__file__).parent.parent
ENV_PATH = SKILL_DIR / ".env"
env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
APIFY_TOKEN = env.get("APIFY_TOKEN") or os.environ.get("APIFY_TOKEN")

# Where to save scrape results
DATA_DIR = Path.home() / ".claude" / "tiktok-autopilot"
YT_DLP = Path.home() / "Library" / "Python" / "3.9" / "bin" / "yt-dlp"
if not YT_DLP.exists():
    YT_DLP = "yt-dlp"  # fallback to PATH


# ── Apify scraper ──────────────────────────────────────────────────────────

def scrape_keyword(keyword: str, limit: int) -> list[dict]:
    """Search TikTok for a keyword, return top posts sorted by likes."""
    if not APIFY_TOKEN:
        print("  ⚠ No APIFY_TOKEN — skipping live scrape")
        return []

    from apify_client import ApifyClient
    client = ApifyClient(APIFY_TOKEN)

    print(f"  Searching TikTok: '{keyword}' (limit={limit})...")
    run = client.actor("clockworks/free-tiktok-scraper").call(
        run_input={
            "searchQueries": [keyword],
            "resultsPerPage": limit,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
            "shouldDownloadSubtitles": False,
        },
        timeout_secs=120,
    )

    posts = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        post = {
            "keyword": keyword,
            "id": item.get("id", ""),
            "url": item.get("webVideoUrl") or f"https://www.tiktok.com/@{item.get('authorMeta', {}).get('name', '')}/video/{item.get('id', '')}",
            "hook": (item.get("text") or "")[:120],
            "caption": item.get("text") or "",
            "hashtags": [t.get("name", "") for t in (item.get("hashtags") or [])],
            "likes": item.get("diggCount") or 0,
            "comments": item.get("commentCount") or 0,
            "shares": item.get("shareCount") or 0,
            "plays": item.get("playCount") or 0,
            "author": item.get("authorMeta", {}).get("name", ""),
            "author_followers": item.get("authorMeta", {}).get("fans", 0),
            "duration": item.get("videoMeta", {}).get("duration", 0),
            "created": item.get("createTimeISO", ""),
            "content_type": classify_content(item.get("text") or ""),
        }
        posts.append(post)

    # Sort by likes descending
    posts.sort(key=lambda x: x["likes"], reverse=True)
    print(f"  ✓ Got {len(posts)} posts, top like count: {posts[0]['likes'] if posts else 0}")
    return posts


def classify_content(caption: str) -> str:
    """Guess content type from caption text."""
    c = caption.lower()
    if any(w in c for w in ["pov:", "tell me about", "when you", "that moment"]):
        return "pain_point"
    if any(w in c for w in ["why ", "how to", "here's why", "secret", "truth"]):
        return "education"
    if any(w in c for w in ["vs", "versus", "instead of", "stop using", "duolingo"]):
        return "comparison"
    if any(w in c for w in ["day 1", "30 days", "week ", "after using", "results"]):
        return "transformation"
    if any(w in c for w in ["5 ", "3 ", "7 ", "signs", "reasons", "things"]):
        return "list"
    return "other"


# ── yt-dlp downloader ──────────────────────────────────────────────────────

def download_video(url: str, output_dir: Path) -> str | None:
    """Download a TikTok video with yt-dlp. Returns output path or None."""
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / "%(id)s.%(ext)s")

    result = subprocess.run(
        [str(YT_DLP),
         "--output", template,
         "--write-info-json",      # save metadata alongside video
         "--no-playlist",
         "--quiet",
         url],
        capture_output=True, text=True, timeout=60
    )

    if result.returncode == 0:
        # Find downloaded file
        for f in output_dir.iterdir():
            if f.suffix in (".mp4", ".webm") and not f.name.endswith(".info.json"):
                return str(f)
    else:
        print(f"    ⚠ yt-dlp error: {result.stderr[:100]}")
    return None


# ── Main pipeline ──────────────────────────────────────────────────────────

def run_scrape(product: str, keywords: list[str], limit: int, download_top: int) -> dict:
    today = date.today().isoformat()
    out_dir = DATA_DIR / product
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{today}.json"

    all_posts = []

    for keyword in keywords:
        posts = scrape_keyword(keyword, limit)
        all_posts.extend(posts)
        time.sleep(2)  # be gentle

    # Deduplicate by video ID
    seen = set()
    unique = []
    for p in all_posts:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique.append(p)

    # Sort globally by likes
    unique.sort(key=lambda x: x["likes"], reverse=True)

    # Download top N videos for visual analysis
    if download_top > 0 and unique:
        print(f"\nDownloading top {download_top} videos for analysis...")
        video_dir = Path(f"/tmp/tiktok-{product}/scrape/videos")
        for i, post in enumerate(unique[:download_top]):
            print(f"  [{i+1}/{download_top}] {post['url']}")
            path = download_video(post["url"], video_dir)
            if path:
                post["local_video"] = path
                print(f"    ✓ {path}")
            time.sleep(1)

    # Build summary
    result = {
        "product": product,
        "scraped_at": today,
        "keywords": keywords,
        "total_posts": len(unique),
        "posts": unique,
        "top_hashtags": extract_top_hashtags(unique),
        "content_type_breakdown": content_breakdown(unique),
        "hook_patterns": extract_hooks(unique[:20]),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved {len(unique)} posts → {out_path}")
    return result


def extract_top_hashtags(posts: list[dict]) -> list[dict]:
    counts = {}
    for p in posts:
        for tag in p.get("hashtags", []):
            counts[tag] = counts.get(tag, 0) + 1
    sorted_tags = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"tag": t, "count": c} for t, c in sorted_tags[:20]]


def content_breakdown(posts: list[dict]) -> dict:
    breakdown = {}
    for p in posts:
        ct = p.get("content_type", "other")
        breakdown[ct] = breakdown.get(ct, 0) + 1
    return breakdown


def extract_hooks(posts: list[dict]) -> list[str]:
    """Extract first line (hook) from top posts."""
    hooks = []
    for p in posts:
        first_line = p.get("caption", "").split("\n")[0].strip()
        if first_line and len(first_line) > 10:
            hooks.append(first_line[:100])
    return hooks[:15]


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TikTok viral post scraper")
    parser.add_argument("--keywords", required=True,
                        help="Comma-separated search keywords")
    parser.add_argument("--product", required=True,
                        help="Product slug (e.g. lingomock)")
    parser.add_argument("--limit", type=int, default=15,
                        help="Posts per keyword (default: 15)")
    parser.add_argument("--download", type=int, default=5,
                        help="Download top N videos for analysis (default: 5, 0=skip)")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    print(f"\nTikTok Viral Scraper")
    print(f"Product: {args.product}")
    print(f"Keywords: {keywords}")
    print(f"Limit: {args.limit} per keyword")
    print(f"Backend: {'Apify' if APIFY_TOKEN else 'NO API KEY — set APIFY_TOKEN in .env'}\n")

    if not APIFY_TOKEN:
        print("To get a free Apify token:")
        print("  1. Go to https://console.apify.com/sign-up (free)")
        print("  2. Copy your API token from Settings → Integrations")
        print(f"  3. Add to {ENV_PATH}: APIFY_TOKEN=apify_api_xxxxx")
        sys.exit(1)

    result = run_scrape(
        product=args.product,
        keywords=keywords,
        limit=args.limit,
        download_top=args.download,
    )

    # Print summary
    print("\n── Top 5 Posts ──")
    for i, p in enumerate(result["posts"][:5]):
        print(f"{i+1}. [{p['content_type']}] {p['hook'][:70]}")
        print(f"   ❤️ {p['likes']:,}  💬 {p['comments']:,}  🔁 {p['shares']:,}")

    print("\n── Top Hashtags ──")
    for h in result["top_hashtags"][:10]:
        print(f"  #{h['tag']} ({h['count']}x)")

    print("\n── Content Type Breakdown ──")
    for ct, count in result["content_type_breakdown"].items():
        print(f"  {ct}: {count}")

    print(f"\n── Hook Patterns (top posts) ──")
    for hook in result["hook_patterns"][:5]:
        print(f'  "{hook}"')


if __name__ == "__main__":
    main()
