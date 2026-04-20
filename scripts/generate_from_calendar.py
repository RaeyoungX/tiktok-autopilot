#!/usr/bin/env python3
"""
TikTok Autopilot — Viral-Format Video Generator
Reads calendar + viral analysis → generates slides that MIMIC proven viral structures → animates.

Pipeline:
  1. Load viral analysis (scraped posts + pattern deconstruction)
  2. Match this day's content_type to the best viral formula
  3. Map calendar script lines → slide structure of that formula
  4. Generate branded slides (PIL): hook slide, numbered points with app logos, CTA
  5. Animate each slide → video clip (ffmpeg Ken Burns zoompan — FREE, no API)
  6. Add edge-tts voiceover per clip
  7. Concatenate → final.mp4

This produces content that looks like @maryjoychiamaka's proven format:
  - Large text on clean gradient background
  - App logo badge on app-related slides
  - Numbered point indicator
  - Subtitle burned into clip

Usage:
    python3 generate_from_calendar.py --product chinaready --day 1
    python3 generate_from_calendar.py --product chinaready --day 1 --dry-run
    python3 generate_from_calendar.py --product chinaready --day 1 --output /tmp/day1.mp4

Cost: $0 (no T2V API calls — PIL slides + ffmpeg Ken Burns)

Dependencies:
    pip3 install Pillow edge-tts python-dotenv requests
    brew install ffmpeg
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import textwrap
import time
import urllib.request
import hashlib
import random
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Run: pip3 install Pillow")
    sys.exit(1)

DATA_DIR = Path.home() / ".claude" / "tiktok-autopilot"
SKILL_DIR = Path(__file__).parent.parent
CACHE_DIR = Path.home() / ".claude" / "tiktok-autopilot" / "_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Canvas: TikTok 9:16 portrait
WIDTH, HEIGHT = 1080, 1920

# Proven viral formula structures (from analysis_2026-04-15.md)
VIRAL_FORMULAS = {
    "list": {
        "name": "REGRET LIST",
        "hook_prefix": "things I wish I knew",     # e.g., @calebrevs: 52K likes, 6.2x
        "structure": ["hook", "point", "point", "point", "point", "point", "cta"],
        "example": "@calebrevs: '5 things I wish I knew before visiting China' — 52K likes",
    },
    "education": {
        "name": "APP TUTORIAL (Talking Head)",
        "hook_prefix": "main apps you need",       # @maryjoychiamaka: 43K likes, 9.7x
        "structure": ["hook", "point", "point", "point", "point", "cta"],
        "example": "@maryjoychiamaka: app tutorial format — 43K likes, 9.7x explosiveness",
    },
    "pain_point": {
        "name": "STRESS/PAIN HOOK",
        "structure": ["hook", "pain", "solution", "proof", "cta"],
        "example": "Pain + relief arc format",
    },
    "comparison": {
        "name": "ANTI-TOURIST HOOK",
        "hook_prefix": "Stop doing this",          # @first time in Shanghai: 33K likes
        "structure": ["hook", "wrong_way", "right_way", "right_way", "cta"],
        "example": "@first time in Shanghai: anti-tourist format — 33K likes",
    },
    "transformation": {
        "name": "SERIES CONTINUATION",
        "structure": ["hook", "point", "point", "point", "series_cta"],
        "example": "Series Part X format — 41K likes, 13.3x explosiveness",
    },
    "other": {
        "name": "APP LOVE",
        "structure": ["hook", "point", "point", "point", "cta"],
        "example": "App appreciation format — 19K likes, 15.9x explosiveness",
    },
}

# App logo URLs — official icons (cached locally)
APP_LOGOS = {
    "alipay":  "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Alipay_logo.svg/512px-Alipay_logo.svg.png",
    "wechat":  "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/WeChat_logo.svg/512px-WeChat_logo.svg.png",
    "didi":    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Didi_Chuxing_Logo.svg/512px-Didi_Chuxing_Logo.svg.png",
    "amap":    None,  # Use fallback colored circle
    "vpn":     None,
}

# Keyword → app name mapping
APP_KEYWORDS = {
    "alipay": "alipay", "pay": "alipay", "payment": "alipay",
    "wechat": "wechat", "weixin": "wechat",
    "didi": "didi", "ride": "didi", "taxi": "didi", "uber": "didi",
    "amap": "amap", "maps": "amap", "navigation": "amap", "navigate": "amap",
    "vpn": "vpn", "internet": "vpn", "wifi": "vpn",
    "esim": "esim", "sim card": "esim", "sim": "esim",
}

# Brand colors per app (fallback for logo-less apps)
APP_COLORS = {
    "alipay": "#1677FF",
    "wechat": "#07C160",
    "didi":   "#FF6B00",
    "amap":   "#1E90FF",
    "vpn":    "#6B46C1",
    "esim":   "#0EA5E9",
}


# ── Calendar + Analysis loader ─────────────────────────────────────────────────

def load_calendar(product: str) -> dict:
    path = DATA_DIR / product / "calendar_30day.json"
    if not path.exists():
        print(f"ERROR: No calendar at {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_post(calendar: dict, day: int) -> dict:
    for p in calendar.get("posts", []):
        if p.get("day") == day:
            return p
    print(f"ERROR: Day {day} not in calendar")
    sys.exit(1)


def load_viral_analysis(product: str) -> dict:
    """Load the most recent scraped viral data for this product."""
    product_dir = DATA_DIR / product
    json_files = sorted(product_dir.glob("*.json"), reverse=True)
    if not json_files:
        return {}
    with open(json_files[0], encoding="utf-8") as f:
        return json.load(f)


def find_best_viral_match(post: dict, viral_data: dict) -> dict | None:
    """
    Find the highest-performing post to model after.
    Prefers: same content_type + high likes. Falls back to top likes overall.
    """
    content_type = post.get("content_type", "other")
    hook_lower = post.get("hook", "").lower()
    all_posts = [p for p in viral_data.get("posts", []) if p.get("author") and p.get("likes", 0) > 0]
    if not all_posts:
        return None

    def score(p):
        likes = p.get("likes", 0)
        same_type = 2.0 if p.get("content_type") == content_type else 1.0
        # Bonus if hook keywords overlap
        hook_match = 1.5 if any(w in p.get("hook", "").lower() for w in hook_lower.split()[:5]) else 1.0
        return likes * same_type * hook_match

    return max(all_posts, key=score)


# ── App logo helpers ───────────────────────────────────────────────────────────

def detect_app(text: str) -> str | None:
    """Detect which app is mentioned in a slide's text."""
    text_lower = text.lower()
    for kw, app in APP_KEYWORDS.items():
        if kw in text_lower:
            return app
    return None


def get_app_logo(app_name: str, size: int = 80) -> Image.Image | None:
    """Download and cache app logo, return as PIL Image (RGBA, square)."""
    url = APP_LOGOS.get(app_name)
    if not url:
        return _make_colored_circle(APP_COLORS.get(app_name, "#888"), size, app_name)

    cache_key = hashlib.md5(url.encode()).hexdigest()[:12]
    cache_path = CACHE_DIR / f"logo_{app_name}_{cache_key}.png"

    if not cache_path.exists():
        try:
            import urllib.request
            urllib.request.urlretrieve(url, cache_path)
        except Exception:
            return _make_colored_circle(APP_COLORS.get(app_name, "#888"), size, app_name)

    try:
        img = Image.open(cache_path).convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
        return img
    except Exception:
        return _make_colored_circle(APP_COLORS.get(app_name, "#888"), size, app_name)


def _make_colored_circle(color: str, size: int, label: str) -> Image.Image:
    """Fallback: colored circle with first letter as logo."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    draw.ellipse([0, 0, size - 1, size - 1], fill=(r, g, b, 255))
    try:
        font = _get_font(size // 2)
        ch = label[0].upper()
        bbox = draw.textbbox((0, 0), ch, font=font)
        tx = (size - (bbox[2] - bbox[0])) // 2
        ty = (size - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), ch, font=font, fill=(255, 255, 255, 255))
    except Exception:
        pass
    return img


# ── Font helper ────────────────────────────────────────────────────────────────

_font_cache: dict = {}

def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    # Try system fonts in priority order
    candidates = []
    if bold:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay-Bold.otf",
            "/System/Library/Fonts/SF-Pro-Display-Bold.otf",
            "/Library/Fonts/Arial Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.otf",
            "/System/Library/Fonts/SF-Pro-Display-Regular.otf",
            "/Library/Fonts/Arial.ttf",
        ]

    for path in candidates:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue

    font = ImageFont.load_default()
    _font_cache[key] = font
    return font


# ── Slide generation ───────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def make_gradient_bg(color1: str, color2: str | None = None) -> Image.Image:
    """Create vertical gradient background."""
    r1, g1, b1 = _hex_to_rgb(color1)
    if color2 is None:
        # Darker version of same color
        r2 = max(0, r1 - 60)
        g2 = max(0, g1 - 60)
        b2 = max(0, b1 - 60)
    else:
        r2, g2, b2 = _hex_to_rgb(color2)

    img = Image.new("RGB", (WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        for x in range(WIDTH):
            img.putpixel((x, y), (r, g, b))
    return img


def wrap_to_lines(text: str, max_chars: int = 20) -> list[str]:
    words = text.split()
    lines, current = [], []
    for word in words:
        if sum(len(w) for w in current) + len(current) + len(word) <= max_chars:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def make_hook_slide(text: str, brand_color: str, part_num: int = 1, series_total: int = 30) -> Image.Image:
    """
    Slide 1 — Hook slide (modeled after viral hook format):
    - Large bold text centered
    - Series indicator: "Part 1 of China Prep Series"
    - Brand gradient background
    """
    img = make_gradient_bg(brand_color)
    draw = ImageDraw.Draw(img)

    # Series badge at top
    badge_font = _get_font(38)
    series_text = f"Part {part_num} · China Prep Series"
    badge_w = draw.textlength(series_text, font=badge_font)
    # Draw pill badge
    bx = (WIDTH - badge_w - 48) // 2
    by = 140
    draw.rounded_rectangle([bx, by, bx + badge_w + 48, by + 58], radius=29, fill=(255, 255, 255, 40))
    draw.text((bx + 24, by + 10), series_text, font=badge_font, fill=(255, 255, 255, 200))

    # Main hook text
    font_size = 96
    font = _get_font(font_size, bold=True)
    lines = wrap_to_lines(text, max_chars=18)

    total_h = len(lines) * int(font_size * 1.3)
    y = (HEIGHT - total_h) // 2 - 60

    for line in lines:
        lw = draw.textlength(line, font=font)
        x = (WIDTH - lw) // 2
        # Shadow
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += int(font_size * 1.3)

    # "save this 👇" sub-text
    sub_font = _get_font(46)
    sub = "save this 👇"
    sw = draw.textlength(sub, font=sub_font)
    draw.text(((WIDTH - sw) // 2, y + 30), sub, font=sub_font, fill=(255, 255, 255, 180))

    # Bottom: "More in Part 2 →"
    next_font = _get_font(38)
    next_text = f"More in Part {part_num + 1} →"
    nw = draw.textlength(next_text, font=next_font)
    draw.text(((WIDTH - nw) // 2, HEIGHT - 200), next_text, font=next_font, fill=(255, 255, 255, 160))

    return img


def make_point_slide(
    text: str,
    brand_color: str,
    point_num: int,
    total_points: int,
    app_name: str | None = None,
) -> Image.Image:
    """
    Point slide — numbered item in the list (core viral format):
    - Point number (large, top-left accent)
    - App logo badge (if relevant)
    - Main explanation text
    - Subtle progress dots at bottom
    """
    img = make_gradient_bg(brand_color)
    draw = ImageDraw.Draw(img)

    # Large point number (accent, top-left area)
    num_font = _get_font(180, bold=True)
    num_str = str(point_num)
    draw.text((80, 160), num_str, font=num_font, fill=(255, 255, 255, 30))

    # App logo (top-right corner)
    if app_name:
        logo = get_app_logo(app_name, size=120)
        if logo:
            logo_x = WIDTH - 160
            logo_y = 80
            if logo.mode == "RGBA":
                img.paste(logo, (logo_x, logo_y), logo)
            else:
                img.paste(logo, (logo_x, logo_y))
            # App name label under logo
            app_label_font = _get_font(32)
            lw = draw.textlength(app_name.capitalize(), font=app_label_font)
            draw.text((logo_x + (120 - lw) // 2, logo_y + 128), app_name.capitalize(),
                      font=app_label_font, fill=(255, 255, 255, 160))

    # Main text
    font_size = 84
    font = _get_font(font_size, bold=True)
    lines = wrap_to_lines(text, max_chars=20)
    total_h = len(lines) * int(font_size * 1.25)
    y = (HEIGHT - total_h) // 2

    for line in lines:
        lw = draw.textlength(line, font=font)
        x = (WIDTH - lw) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += int(font_size * 1.25)

    # Progress dots
    dot_r = 10
    dot_spacing = 36
    total_w = total_points * dot_spacing
    dx = (WIDTH - total_w) // 2 + dot_r
    dy = HEIGHT - 140
    for i in range(total_points):
        color = (255, 255, 255, 230) if i == point_num - 1 else (255, 255, 255, 70)
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=color)
        dx += dot_spacing

    return img


def make_cta_slide(brand_color: str, product_url: str = "chinaready.org", series_num: int = 1) -> Image.Image:
    """
    CTA slide — Series continuation hook (proven: drives follows + saves):
    - "Save this!" large
    - "Full guide → chinaready.org"
    - "Follow for Part [N+1] →"
    """
    img = make_gradient_bg(brand_color)
    draw = ImageDraw.Draw(img)

    lines_data = [
        ("Save this! 🔖", 92, True, 255),
        (f"Full guide →", 64, False, 200),
        (product_url, 64, True, 200),
        ("", 0, False, 0),
        (f"Follow for Part {series_num + 1} →", 58, False, 170),
    ]

    total_h = sum(int(sz * 1.3) for _, sz, _, _ in lines_data if sz > 0)
    y = (HEIGHT - total_h) // 2 - 40

    for text, sz, bold, alpha in lines_data:
        if sz == 0:
            y += 20
            continue
        font = _get_font(sz, bold=bold)
        lw = draw.textlength(text, font=font)
        x = (WIDTH - lw) // 2
        draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 80))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))
        y += int(sz * 1.3)

    return img


def generate_slides_for_day(post: dict, viral_match: dict | None, brand_color: str, output_dir: Path) -> list[Path]:
    """
    Map calendar post → slides based on viral formula.
    Returns list of slide PNG paths.
    """
    content_type = post.get("content_type", "other")
    formula = VIRAL_FORMULAS.get(content_type, VIRAL_FORMULAS["other"])
    hook = post.get("hook", "")
    script_lines = post.get("script", [])
    day = post.get("day", 1)

    print(f"  Viral formula: {formula['name']}")
    if viral_match:
        print(f"  Modeling after: @{viral_match.get('author', '?')} ({viral_match.get('likes', 0):,} likes)")

    output_dir.mkdir(parents=True, exist_ok=True)
    slides = []

    # Build slide sequence based on formula structure
    structure = formula.get("structure", ["hook"] + ["point"] * 4 + ["cta"])
    point_lines = [l for l in script_lines if l]  # content lines
    point_idx = 0
    total_points = sum(1 for s in structure if s in ("point", "pain", "solution", "proof", "wrong_way", "right_way"))

    for slide_num, slide_type in enumerate(structure):
        slide_path = output_dir / f"slide_{slide_num + 1:02d}.png"

        if slide_type == "hook":
            img = make_hook_slide(hook, brand_color, part_num=day)
            img.save(slide_path, "PNG")
            print(f"  slide {slide_num+1}: [HOOK] {hook[:50]}")

        elif slide_type in ("point", "pain", "solution", "proof", "wrong_way", "right_way", "series_cta"):
            if slide_type == "series_cta":
                img = make_cta_slide(brand_color, series_num=day)
            elif point_idx < len(point_lines):
                line = point_lines[point_idx]
                app = detect_app(line)
                point_num_display = point_idx + 1
                img = make_point_slide(line, brand_color, point_num_display, total_points, app_name=app)
                print(f"  slide {slide_num+1}: [POINT {point_num_display}]{' ['+app+']' if app else ''} {line[:50]}")
                point_idx += 1
            else:
                img = make_cta_slide(brand_color, series_num=day)

            img.save(slide_path, "PNG")

        elif slide_type == "cta":
            img = make_cta_slide(brand_color, series_num=day)
            img.save(slide_path, "PNG")
            print(f"  slide {slide_num+1}: [CTA]")

        slides.append(slide_path)

    return slides


# ── Ken Burns animation (ffmpeg zoompan) ──────────────────────────────────────

KEN_BURNS_VARIANTS = [
    # Slow zoom in from center
    "zoompan=z='min(zoom+0.0015,1.5)':d=150:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # Slow zoom out
    "zoompan=z='if(lte(zoom,1.0),1.5,max(zoom-0.0015,1.0))':d=150:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # Pan right with slight zoom
    "zoompan=z='1.2':d=150:x='if(gte(on,1),x+0.5,0)':y='ih/2-(ih/zoom/2)'",
    # Pan left
    "zoompan=z='1.2':d=150:x='if(gte(on,1),x-0.5,iw/4)':y='ih/2-(ih/zoom/2)'",
    # Gentle float (center, minimal motion)
    "zoompan=z='1.05+0.02*sin(on/50)':d=150:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
]


def animate_slide(slide_path: Path, clip_path: Path, duration: float = 5.0, variant_idx: int = 0):
    """
    Convert a PNG slide → video clip using ffmpeg Ken Burns zoompan.
    Produces a 1080x1920 vertical clip at 30fps.
    Free — no API calls.
    """
    kb_filter = KEN_BURNS_VARIANTS[variant_idx % len(KEN_BURNS_VARIANTS)]

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(slide_path),
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"{kb_filter},"
            f"scale=1080:1920,fps=30"
        ),
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(clip_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠ ffmpeg error: {result.stderr[-200:]}")
        return False
    return True


# ── Voiceover (edge-tts) ───────────────────────────────────────────────────────

TTS_VOICE = "en-US-AriaNeural"


def generate_voiceover(text: str, out_path: Path, duration: float = 5.0):
    """Generate TTS audio and pad/trim to exact duration."""
    import asyncio
    import edge_tts

    async def _tts():
        communicate = edge_tts.Communicate(text, TTS_VOICE, rate="+5%", volume="+10%")
        raw = out_path.with_suffix(".raw.mp3")
        await communicate.save(str(raw))
        # Pad/trim to clip duration
        subprocess.run([
            "ffmpeg", "-y", "-i", str(raw),
            "-af", f"apad,atrim=0:{duration}",
            "-c:a", "aac", "-b:a", "128k",
            str(out_path)
        ], capture_output=True)
        raw.unlink(missing_ok=True)

    asyncio.run(_tts())


def merge_audio_video(video_path: Path, audio_path: Path, out_path: Path):
    """Merge video + audio into final clip."""
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        str(out_path)
    ], capture_output=True)


# ── Concatenation ──────────────────────────────────────────────────────────────

def concat_clips(clip_paths: list[Path], output: Path):
    """Concatenate video clips into final video."""
    list_file = output.parent / "_concat_list.txt"
    with open(list_file, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{cp.absolute()}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output)
    ], capture_output=True)
    list_file.unlink(missing_ok=True)


# ── Main pipeline ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate viral-format TikTok video from calendar")
    parser.add_argument("--product", required=True)
    parser.add_argument("--day", type=int, required=True)
    parser.add_argument("--output", help="Output video path (default: /tmp/tiktok-{product}/day{N:02d}.mp4)")
    parser.add_argument("--brand-color", default="#1a1a2e", help="Brand hex color (default: dark blue)")
    parser.add_argument("--no-audio", action="store_true", help="Skip voiceover generation")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Resolve output path
    tmp_dir = Path(f"/tmp/tiktok-{args.product}")
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = tmp_dir / f"day{args.day:02d}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load data
    calendar = load_calendar(args.product)
    post = get_post(calendar, args.day)
    viral_data = load_viral_analysis(args.product)
    viral_match = find_best_viral_match(post, viral_data)

    print(f"\nViral-Format Generator")
    print(f"  Product     : {args.product}")
    print(f"  Day         : {args.day} — {post.get('date', '?')}")
    print(f"  Hook        : {post.get('hook', '')[:70]}")
    print(f"  Content type: {post.get('content_type', '?')}")
    print(f"  Formula     : {VIRAL_FORMULAS.get(post.get('content_type','other'), {}).get('name', '?')}")
    if viral_match:
        print(f"  Modeling    : @{viral_match.get('author', '?')} — {viral_match.get('likes',0):,} likes, {viral_match.get('explosiveness',0):.1f}x")
    print(f"  Output      : {output_path}")
    print(f"  Cost        : $0 (Ken Burns animation, no T2V API)")
    if args.dry_run:
        print("  Mode        : DRY RUN\n")
        return

    # Step 1: Generate slides
    print(f"\n[1/4] Generating slides...")
    slides_dir = tmp_dir / f"day{args.day:02d}_slides"
    slide_paths = generate_slides_for_day(post, viral_match, args.brand_color, slides_dir)
    print(f"  → {len(slide_paths)} slides generated in {slides_dir}")

    # Step 2: Animate each slide → video clip (Ken Burns)
    print(f"\n[2/4] Animating slides (Ken Burns — ffmpeg)...")
    clips_dir = tmp_dir / f"day{args.day:02d}_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    script_lines = [l for l in post.get("script", []) if l]

    final_clips = []
    for i, slide_path in enumerate(slide_paths):
        clip_path = clips_dir / f"clip_{i+1:02d}_silent.mp4"
        variant = i % len(KEN_BURNS_VARIANTS)
        ok = animate_slide(slide_path, clip_path, duration=5.0, variant_idx=variant)
        if not ok:
            print(f"  ⚠ Slide {i+1} animation failed, skipping")
            continue
        print(f"  ✓ Slide {i+1}/{len(slide_paths)} animated")

        # Step 3: Add voiceover
        if not args.no_audio and i < len(script_lines):
            audio_path = clips_dir / f"clip_{i+1:02d}.aac"
            merged_path = clips_dir / f"clip_{i+1:02d}.mp4"
            print(f"  🎤 Voiceover: {script_lines[i][:50]}...")
            try:
                generate_voiceover(script_lines[i], audio_path, duration=5.0)
                merge_audio_video(clip_path, audio_path, merged_path)
                final_clips.append(merged_path)
            except Exception as e:
                print(f"  ⚠ TTS failed: {e} — using silent clip")
                final_clips.append(clip_path)
        else:
            final_clips.append(clip_path)

    # Step 4: Concatenate
    print(f"\n[4/4] Concatenating {len(final_clips)} clips → {output_path.name}...")
    concat_clips(final_clips, output_path)

    size_mb = output_path.stat().st_size / 1024 / 1024 if output_path.exists() else 0
    print(f"\n✅ Done! {output_path} ({size_mb:.1f} MB)")
    print(f"\nNext step:")
    print(f"  python3 publish_browser.py --video {output_path} --product {args.product} --day {args.day} --platforms tiktok")


if __name__ == "__main__":
    main()
