#!/usr/bin/env python3
"""
TikTok Autopilot — Browser-based Publisher (no API needed)
Uses AppleScript to control Chrome — uploads video and fills in caption/hashtags.
Same approach as reddit-cultivate: controls real browser, undetectable.

Supports:
  - TikTok (tiktok.com/tiktokstudio/upload)
  - YouTube Shorts (studio.youtube.com)
  - Instagram Reels (instagram.com)

Usage:
    python3 publish_browser.py \
        --video /tmp/tiktok-chinaready/day01.mp4 \
        --product chinaready \
        --day 1 \
        --platforms tiktok youtube instagram

    # Single platform:
    python3 publish_browser.py --video /tmp/day01.mp4 --product chinaready --day 1 --platforms youtube

    # Dry run (print what would happen):
    python3 publish_browser.py --video /tmp/day01.mp4 --product chinaready --day 1 --dry-run

Requirements:
    - Chrome installed and logged into each platform
    - pip3 install python-dotenv
    - macOS (AppleScript)

Lessons learned (2026-04-17):
    - chrome_js() requires "Allow JavaScript from Apple Events" enabled in Chrome
      → auto-enabled at startup via keyboard navigation of 显示>开发者 menu
    - TikTok shows 2 blocking dialogs after upload (content check + new feature promo)
      → dismissed automatically via JS button click
    - TikTok caption uses Draft.js (offsetHeight=21, not >40)
      → use .public-DraftEditor-content selector + execCommand('insertText')
    - TikTok publish button text is '发布' (Chinese), not 'post'
    - Emoji in AppleScript strings cause syntax errors
      → always write JS to temp file, read via `do shell script "cat"`
"""

import argparse
import json
import os
import subprocess
import sys
import time
import random
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = Path.home() / ".claude" / "tiktok-autopilot"


# ── AppleScript helpers ────────────────────────────────────────────────────────

def run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True
    )
    if result.returncode != 0 and result.stderr:
        print(f"  ⚠ AppleScript: {result.stderr.strip()[:120]}")
    return result.stdout.strip()


def run_applescript_file(script: str) -> str:
    """Run AppleScript from a temp file (avoids string escaping issues)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.applescript', delete=False, encoding='utf-8') as f:
        f.write(script)
        tmp = f.name
    result = subprocess.run(
        ["osascript", tmp],
        capture_output=True, text=True
    )
    Path(tmp).unlink(missing_ok=True)
    if result.returncode != 0 and result.stderr:
        print(f"  ⚠ AppleScript: {result.stderr.strip()[:200]}")
    return result.stdout.strip()


def chrome_navigate(url: str):
    run_applescript(f'''
        tell application "Google Chrome"
            activate
            set URL of active tab of front window to "{url}"
        end tell
    ''')


def chrome_js(js: str) -> str:
    """Execute JavaScript in Chrome's active tab via temp file (handles emoji/Unicode)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(js)
        tmp = f.name
    result = run_applescript(f'''
        set jsCode to do shell script "cat {tmp}"
        tell application "Google Chrome"
            execute active tab of front window javascript jsCode
        end tell
    ''')
    Path(tmp).unlink(missing_ok=True)
    return result


def ensure_chrome_js_enabled():
    """
    Enable 'Allow JavaScript from Apple Events' in Chrome if not already on.
    Menu path: 显示 (View) > 开发者 (Developer) > 允许 Apple 事件中的 JavaScript
    Uses keyboard navigation to reliably toggle the setting.
    """
    # First check if it's already enabled by trying a test execution
    test_result = run_applescript('''
        tell application "Google Chrome"
            activate
            try
                execute active tab of front window javascript "'ok'"
                return "enabled"
            on error
                return "disabled"
            end try
        end tell
    ''')
    if "enabled" in test_result:
        return  # Already enabled

    print("  Enabling Chrome JavaScript from Apple Events...")
    # Use keyboard navigation — more reliable than clicking menu items
    run_applescript_file('''
        tell application "Google Chrome" to activate
        delay 0.8
        tell application "System Events"
            tell process "Google Chrome"
                -- Open 显示 menu
                click menu bar item "显示" of menu bar 1
                delay 0.8
                -- Navigate down to 开发者 (last item in 显示 menu, ~11 items down)
                repeat 12 times
                    key code 125
                    delay 0.05
                end repeat
                -- Open 开发者 submenu with right arrow
                key code 124
                delay 0.6
                -- Navigate down to 允许 Apple 事件中的 JavaScript (5 items down)
                repeat 5 times
                    key code 125
                    delay 0.05
                end repeat
                -- Press Enter to toggle
                key code 36
            end tell
        end tell
    ''')
    time.sleep(0.5)

    # Verify it worked
    test2 = run_applescript('''
        tell application "Google Chrome"
            try
                execute active tab of front window javascript "'ok'"
                return "enabled"
            on error
                return "disabled"
            end try
        end tell
    ''')
    if "enabled" not in test2:
        print("  ⚠ Could not enable JavaScript from Apple Events automatically.")
        print("    Manual fix: Chrome menu → 显示 → 开发者 → 允许 Apple 事件中的 JavaScript")


def chrome_click_upload(file_path: str):
    """
    Select a file in the macOS native file picker dialog.
    Uses Cmd+Shift+G to open 'Go to folder', types the path, presses Enter.
    Works because native dialogs respond to System Events regardless of Accessibility.
    """
    abs_path = str(Path(file_path).absolute())
    run_applescript_file(f'''
        tell application "Google Chrome" to activate
        delay 1
        tell application "System Events"
            keystroke "g" using {{command down, shift down}}
            delay 0.8
            keystroke "{abs_path}"
            delay 0.5
            key code 36
            delay 0.5
            key code 36
        end tell
    ''')


def set_clipboard(text: str):
    """Copy text to macOS clipboard (handles emoji and all Unicode)."""
    subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)


def paste_from_clipboard():
    """Paste clipboard contents into focused element."""
    run_applescript('tell application "System Events" to keystroke "v" using {command down}')


def human_delay(min_s: float = 1.5, max_s: float = 3.5):
    time.sleep(random.uniform(min_s, max_s))


def wait_for_page(seconds: float = 3.0):
    time.sleep(seconds)


def dismiss_blocking_dialogs():
    """
    Click any blocking modal button by common dismiss texts.
    TikTok shows multiple dialogs after upload — dismiss them all.
    """
    dismiss_texts = ['知道了', '取消', 'Got it', 'OK', 'ok', 'Cancel', '确定']
    for text in dismiss_texts:
        result = chrome_js(f"""
            var dismissed = false;
            document.querySelectorAll('button, [role=button]').forEach(function(b) {{
                if (!dismissed && b.textContent.trim() === '{text}' && b.offsetParent !== null) {{
                    b.click();
                    dismissed = true;
                }}
            }});
            dismissed ? 'dismissed:{text}' : 'none';
        """)
        if result and result.startswith('dismissed:'):
            print(f"  ↳ Dismissed dialog: '{text}'")
            time.sleep(0.8)


# ── Calendar loader ────────────────────────────────────────────────────────────

def load_post(product: str, day: int) -> dict:
    cal_path = DATA_DIR / product / "calendar_30day.json"
    if not cal_path.exists():
        print(f"ERROR: No calendar at {cal_path}")
        sys.exit(1)
    with open(cal_path, encoding="utf-8") as f:
        cal = json.load(f)
    for p in cal["posts"]:
        if p["day"] == day:
            return p
    print(f"ERROR: Day {day} not in calendar")
    sys.exit(1)


def build_caption(post: dict, platform: str, max_chars: int = 2200) -> str:
    """Build platform-appropriate caption from post data."""
    caption = post["caption"]
    hashtags = " ".join(f"#{h}" for h in post["hashtags"])

    if platform == "youtube":
        return f"{caption}\n\n{hashtags}\n\nFull China prep guide: chinaready.org"

    full = f"{caption}\n\n{hashtags}"
    if len(full) > max_chars:
        full = full[:max_chars - 3] + "..."
    return full


def build_title(post: dict) -> str:
    """YouTube title (max 100 chars)."""
    hook = post["hook"]
    return hook[:97] + "..." if len(hook) > 100 else hook


# ── Platform publishers ────────────────────────────────────────────────────────

def publish_tiktok(video_path: str, post: dict, dry_run: bool = False) -> bool:
    """Upload to TikTok Studio via Chrome."""
    caption = build_caption(post, "tiktok")
    print(f"\n── TikTok ──")
    print(f"  Caption ({len(caption)} chars): {caption[:80]}...")

    if dry_run:
        print("  [dry-run] Would navigate to tiktok.com/tiktokstudio/upload")
        return True

    print("  Opening TikTok Studio...")
    chrome_navigate("https://www.tiktok.com/tiktokstudio/upload?lang=en")
    wait_for_page(4)

    # Click the hidden file input to open native file picker
    print("  Triggering file upload...")
    chrome_js("""
        var inputs = document.querySelectorAll('input[type=file]');
        if (inputs.length > 0) inputs[0].click();
    """)
    human_delay(1, 2)

    # Select the video file via native macOS file dialog (Cmd+Shift+G)
    chrome_click_upload(video_path)
    print("  Waiting for video to process... (35s)")
    wait_for_page(35)

    # TikTok shows 1-2 blocking dialogs after upload:
    #   1. "开启自动内容检查?" — content moderation opt-in (click any button)
    #   2. "全新编辑功能已上线" — new feature promo (click 知道了)
    print("  Dismissing any post-upload dialogs...")
    for _ in range(3):
        dismiss_blocking_dialogs()
        time.sleep(0.5)

    # Fill caption using Draft.js execCommand (clipboard paste doesn't work with Draft.js)
    # Note: TikTok uses .public-DraftEditor-content with offsetHeight=21 (not >40)
    print("  Filling caption...")
    caption_js = f"""
        var editor = document.querySelector('.public-DraftEditor-content');
        if (!editor) editor = document.querySelector('[contenteditable=true]');
        if (editor) {{
            editor.focus();
            editor.click();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            var text = {json.dumps(caption)};
            var ok = document.execCommand('insertText', false, text);
            'ok:' + ok + ' len:' + editor.textContent.length;
        }} else {{
            'editor not found';
        }}
    """
    result = chrome_js(caption_js)
    print(f"  Caption result: {result}")
    human_delay(1, 2)

    # Close any hashtag suggestion dropdown (Escape)
    run_applescript('tell application "System Events" to tell process "Google Chrome" to key code 53')
    time.sleep(0.5)

    # Click 发布 (Publish) button — TikTok UI is in Chinese
    print("  Clicking Publish button...")
    pub_result = chrome_js("""
        var published = false;
        var publishTexts = ['发布', 'Post', '立即发布', 'Publish'];
        document.querySelectorAll('button').forEach(function(b) {
            if (!published && !b.disabled && publishTexts.includes(b.textContent.trim())) {
                b.click();
                published = true;
            }
        });
        published ? 'clicked' : 'button not found';
    """)
    print(f"  Publish result: {pub_result}")
    human_delay(3, 5)

    # Verify success by checking if page navigated away from /upload
    url_check = run_applescript('''
        tell application "Google Chrome"
            return URL of active tab of front window
        end tell
    ''')
    if "/upload" not in url_check:
        print("  ✓ TikTok post submitted (navigated to content page)")
    else:
        print("  ⚠ Still on upload page — may need manual check")

    return True


def publish_youtube(video_path: str, post: dict, dry_run: bool = False) -> bool:
    """Upload to YouTube Studio as a Short via Chrome."""
    title = build_title(post)
    description = build_caption(post, "youtube")
    print(f"\n── YouTube Shorts ──")
    print(f"  Title: {title}")

    if dry_run:
        print("  [dry-run] Would navigate to studio.youtube.com")
        return True

    print("  Opening YouTube Studio...")
    chrome_navigate("https://studio.youtube.com")
    wait_for_page(4)

    # Click the CREATE / upload button
    print("  Clicking Create button...")
    chrome_js("""
        var btns = document.querySelectorAll('ytcp-button, button');
        for (var b of btns) {
            var txt = b.textContent.trim().toUpperCase();
            if (txt === 'CREATE' || txt === '创作' || txt === 'UPLOAD VIDEOS') { b.click(); break; }
        }
    """)
    human_delay(1.5, 2.5)

    # Click "Upload videos" in dropdown
    chrome_js("""
        var items = document.querySelectorAll('tp-yt-paper-item, ytcp-menu-item');
        for (var item of items) {
            if (item.textContent.includes('Upload') || item.textContent.includes('上传')) {
                item.click(); break;
            }
        }
    """)
    human_delay(1, 2)

    # Select file
    print("  Selecting video file...")
    chrome_js("""
        var input = document.querySelector('input[type=file]');
        if (input) input.click();
    """)
    human_delay(0.5, 1)
    chrome_click_upload(video_path)

    print("  Waiting for upload to start... (20s)")
    wait_for_page(20)

    # Fill title (select all + paste)
    print("  Setting title...")
    chrome_js("""
        var titleField = document.querySelector('#title-textarea textarea, [aria-label*="title" i] textarea, ytcp-social-suggestions-textbox textarea');
        if (titleField) { titleField.focus(); titleField.select(); }
    """)
    set_clipboard(title)
    time.sleep(0.3)
    paste_from_clipboard()
    human_delay(1, 2)

    # Fill description
    print("  Setting description...")
    chrome_js("""
        var descField = document.querySelector('#description-textarea textarea, [aria-label*="description" i] textarea');
        if (descField) { descField.focus(); }
    """)
    set_clipboard(description)
    time.sleep(0.3)
    paste_from_clipboard()
    human_delay(1, 2)

    # Navigate wizard: Next × 3 then Publish
    print("  Navigating publish wizard...")
    for step in range(4):
        chrome_js("""
            var btns = document.querySelectorAll('ytcp-button');
            for (var b of btns) {
                var txt = b.textContent.trim().toUpperCase();
                if (txt === 'NEXT' || txt === 'PUBLISH' || txt === '下一步' || txt === '发布') {
                    b.click(); break;
                }
            }
        """)
        human_delay(3, 5)

    print("  ✓ YouTube Short submitted")
    return True


def publish_instagram(video_path: str, post: dict, dry_run: bool = False) -> bool:
    """Upload Reel to Instagram web via Chrome."""
    caption = build_caption(post, "instagram", max_chars=2200)
    print(f"\n── Instagram Reels ──")
    print(f"  Caption ({len(caption)} chars): {caption[:80]}...")

    if dry_run:
        print("  [dry-run] Would navigate to instagram.com")
        return True

    print("  Opening Instagram...")
    chrome_navigate("https://www.instagram.com")
    wait_for_page(3)

    # Click + Create button
    print("  Clicking Create button...")
    chrome_js("""
        var links = document.querySelectorAll('a, div[role=button], button');
        for (var el of links) {
            if (el.getAttribute('aria-label') === 'New post' ||
                el.querySelector('svg[aria-label="New post"]')) {
                el.click(); break;
            }
        }
    """)
    human_delay(1.5, 2.5)

    # Click "Post" option
    chrome_js("""
        var items = document.querySelectorAll('[role=menuitem], div[tabindex]');
        for (var item of items) {
            if (item.textContent.trim() === 'Post') { item.click(); break; }
        }
    """)
    human_delay(1, 2)

    # Select file
    print("  Selecting video file...")
    chrome_js("""
        var input = document.querySelector('input[type=file]');
        if (input) input.click();
    """)
    human_delay(0.5, 1)
    chrome_click_upload(video_path)

    print("  Waiting for upload... (10s)")
    wait_for_page(10)

    # Click Next until Caption step
    print("  Navigating to caption step...")
    for _ in range(3):
        chrome_js("""
            var btns = document.querySelectorAll('div[role=button], button');
            for (var b of btns) {
                if (b.textContent.trim() === 'Next') { b.click(); break; }
            }
        """)
        human_delay(2, 3)

    # Fill caption — try execCommand first, fall back to clipboard paste
    print("  Filling caption...")
    ig_caption_js = f"""
        var textarea = document.querySelector('textarea[aria-label*="caption" i], div[aria-label*="caption" i][contenteditable]');
        if (!textarea) {{
            var areas = document.querySelectorAll('textarea, div[contenteditable=true]');
            textarea = areas[areas.length - 1];
        }}
        if (textarea) {{
            textarea.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            var ok = document.execCommand('insertText', false, {json.dumps(caption)});
            ok ? 'inserted' : 'fallback-needed';
        }} else {{ 'not found'; }}
    """
    ig_result = chrome_js(ig_caption_js)
    if ig_result == 'fallback-needed':
        # Fall back to clipboard paste
        set_clipboard(caption)
        paste_from_clipboard()
    print(f"  Caption result: {ig_result}")
    human_delay(2, 3)

    # Click Share
    print("  Clicking Share...")
    chrome_js("""
        var btns = document.querySelectorAll('div[role=button], button');
        for (var b of btns) {
            if (b.textContent.trim() === 'Share') { b.click(); break; }
        }
    """)
    human_delay(3, 5)

    print("  ✓ Instagram Reel submitted")
    return True


# ── Main ───────────────────────────────────────────────────────────────────────

PLATFORM_FUNCS = {
    "tiktok": publish_tiktok,
    "youtube": publish_youtube,
    "instagram": publish_instagram,
}


def main():
    parser = argparse.ArgumentParser(description="Publish video to TikTok/YouTube/Instagram via Chrome")
    parser.add_argument("--video", required=True, help="Path to video file (.mp4)")
    parser.add_argument("--product", required=True, help="Product slug (e.g. chinaready)")
    parser.add_argument("--day", type=int, required=True, help="Calendar day number")
    parser.add_argument("--platforms", default="tiktok",
                        help="Comma-separated platforms: tiktok,youtube,instagram (default: tiktok)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without browser automation")
    args = parser.parse_args()

    video_path = str(Path(args.video).absolute())
    if not Path(video_path).exists() and not args.dry_run:
        print(f"ERROR: Video not found: {video_path}")
        sys.exit(1)

    post = load_post(args.product, args.day)
    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]

    print(f"\nPublisher — Browser Mode")
    print(f"  Product  : {args.product}")
    print(f"  Day      : {args.day} — {post['date']}")
    print(f"  Hook     : {post['hook'][:70]}")
    print(f"  Video    : {video_path}")
    print(f"  Platforms: {', '.join(platforms)}")
    if args.dry_run:
        print(f"  Mode     : DRY RUN\n")

    # Enable Chrome's JavaScript from Apple Events (required for chrome_js to work)
    if not args.dry_run:
        ensure_chrome_js_enabled()

    results = {}
    for platform in platforms:
        if platform not in PLATFORM_FUNCS:
            print(f"  ⚠ Unknown platform: {platform} (available: tiktok, youtube, instagram)")
            continue
        try:
            ok = PLATFORM_FUNCS[platform](video_path, post, dry_run=args.dry_run)
            results[platform] = "✅ done" if ok else "❌ failed"
        except Exception as e:
            print(f"  ❌ {platform} error: {e}")
            results[platform] = f"❌ error: {e}"

        if not args.dry_run and len(platforms) > 1:
            delay = random.uniform(8, 15)
            print(f"\n  Waiting {delay:.0f}s before next platform...")
            time.sleep(delay)

    print(f"\n── Results ──")
    for platform, status in results.items():
        print(f"  {platform}: {status}")


if __name__ == "__main__":
    main()
