#!/usr/bin/env python3
"""
TikTok Autopilot — Image Generator (Imagen 3 + PIL)
Each slide: Imagen 3 generates a cinematic 9:16 background → PIL overlays text.

Usage:
    python3 create_images.py \
        --product "lingomock" \
        --post-id "post-01" \
        --slides '["Hook text", "Slide 2", "CTA slide"]' \
        --context "English speaking practice app for non-native speakers" \
        --color "#2D1B69" \
        --output "/tmp/tiktok-lingomock/post-01/"

Dependencies:
    pip install Pillow google-generativeai
"""

import argparse
import json
import os
import sys
import io
import re
import time
from pathlib import Path
from dotenv import dotenv_values

# Load API key from .env next to this script
SKILL_DIR = Path(__file__).parent.parent
ENV_PATH = SKILL_DIR / ".env"
env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
GEMINI_API_KEY = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Run: pip3 install Pillow")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("Warning: google-genai not found. Run: pip3 install google-genai")

# Canvas: TikTok portrait 9:16
WIDTH, HEIGHT = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 180, 280

# Typography
FONT_SIZE_HOOK = 88      # slide 1 (larger)
FONT_SIZE_BODY = 72      # slides 2+
FONT_SIZE_SMALL = 40     # counter, button
LINE_SPACING = 1.45
MAX_CHARS = 20           # per line before wrap


# ── Imagen prompt builder ──────────────────────────────────────────────────

SLIDE_MOODS = {
    0: "dramatic cinematic portrait, emotional tension, dim lighting, shallow depth of field",
    1: "minimalist conceptual photo, moody atmosphere, artistic lighting",
    2: "documentary style, realistic, slightly desaturated",
    3: "aspirational lifestyle photo, warm light, optimistic",
    4: "clean product-adjacent lifestyle, soft bokeh, positive energy",
    5: "motivational, bright accent light, forward momentum",
}

def build_imagen_prompt(slide_text: str, slide_idx: int, product_context: str, brand_color: str) -> str:
    mood = SLIDE_MOODS.get(slide_idx, SLIDE_MOODS[1])
    # Strip emoji and keep core meaning
    clean = re.sub(r'[^\x00-\x7F\u4e00-\u9fff]+', '', slide_text).strip()
    return (
        f"Cinematic background photo for a TikTok slide. "
        f"Emotional theme: {clean[:80]}. "
        f"Visual style: {mood}. "
        f"Color palette: deep purple and dark tones, dramatic lighting. "
        f"STRICT RULES: absolutely NO text, NO words, NO letters, NO numbers, "
        f"NO phone screens, NO app UI, NO mockups, NO devices, NO logos. "
        f"Pure atmospheric photography only. Portrait 9:16. Photorealistic."
    )


# ── Imagen API call ────────────────────────────────────────────────────────

def generate_background(prompt: str, fallback_color: str) -> Image.Image:
    """Call Imagen 3 via google-genai SDK. Falls back to gradient on error."""
    if not HAS_GENAI or not GEMINI_API_KEY:
        print("  ⚠ No Gemini API key — using gradient fallback")
        return make_gradient(WIDTH, HEIGHT, fallback_color)

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        result = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="9:16",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
                person_generation="ALLOW_ADULT",
            ),
        )
        if result.generated_images:
            img_bytes = result.generated_images[0].image.image_bytes
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            return img.resize((WIDTH, HEIGHT), Image.LANCZOS)
    except Exception as e:
        print(f"  ⚠ Imagen error: {e} — using gradient fallback")

    return make_gradient(WIDTH, HEIGHT, fallback_color)


# ── Utilities ──────────────────────────────────────────────────────────────

def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def darken(rgb: tuple, f: float = 0.35) -> tuple:
    return tuple(max(0, int(c * f)) for c in rgb)

def make_gradient(w: int, h: int, hex_color: str) -> Image.Image:
    base = hex_to_rgb(hex_color)
    dark = darken(base)
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        r = y / h
        color = tuple(int(dark[i] * (1-r) + base[i] * r) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return img

def wrap_text(text: str, max_chars: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]

def get_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── Slide renderer ─────────────────────────────────────────────────────────

def render_slide(
    bg: Image.Image,
    text: str,
    slide_num: int,
    total: int,
    brand_color: str,
    is_hook: bool = False,
    is_cta: bool = False,
) -> Image.Image:
    img = bg.copy().resize((WIDTH, HEIGHT), Image.LANCZOS)

    # Dark overlay for text readability (stronger at center)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    # Vignette-style: darker at edges, semi-dark center
    ov_draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=(0, 0, 0, 140))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    base_rgb = hex_to_rgb(brand_color)

    # Top accent bar
    accent = tuple(min(255, int(c * 1.8)) for c in base_rgb)
    draw.rectangle([(0, 0), (WIDTH, 6)], fill=accent)

    # Slide counter
    counter_font = get_font(FONT_SIZE_SMALL)
    draw.text((WIDTH - 90, 36), f"{slide_num}/{total}", font=counter_font, fill=(255, 255, 255, 180))

    # Main text
    font_size = FONT_SIZE_HOOK if is_hook else FONT_SIZE_BODY
    font = get_font(font_size)
    line_h = int(font_size * LINE_SPACING)
    max_c = 16 if is_hook else MAX_CHARS

    # Handle newlines in text
    raw_lines = text.split("\n")
    lines = []
    for raw in raw_lines:
        if raw.strip() == "":
            lines.append("")
        else:
            lines.extend(wrap_text(raw.strip(), max_c))

    total_h = len(lines) * line_h
    safe_h = HEIGHT - SAFE_TOP - SAFE_BOTTOM
    start_y = SAFE_TOP + (safe_h - total_h) // 2

    for i, line in enumerate(lines):
        if not line:
            continue
        y = start_y + i * line_h
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(line) * (font_size // 2)
        x = (WIDTH - tw) // 2
        # Shadow
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 120))
        # Main
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    # CTA button on last slide
    if is_cta:
        btn_w, btn_h = 520, 88
        btn_x = (WIDTH - btn_w) // 2
        btn_y = HEIGHT - SAFE_BOTTOM - 20
        draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)],
                                radius=44, fill=accent)
        btn_font = get_font(42)
        btn_text = "Link in Bio"
        try:
            bb = draw.textbbox((0, 0), btn_text, font=btn_font)
            btw = bb[2] - bb[0]
        except Exception:
            btw = len(btn_text) * 22
        draw.text(((WIDTH - btw) // 2, btn_y + 22), btn_text,
                  font=btn_font, fill=(10, 5, 30))

    # Bottom bar
    draw.rectangle([(0, HEIGHT - 6), (WIDTH, HEIGHT)], fill=accent)
    return img


# ── Main ───────────────────────────────────────────────────────────────────

def create_post_images(product, post_id, slides, context, color, output_dir) -> list[str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = len(slides)
    saved = []

    for i, text in enumerate(slides):
        n = i + 1
        is_hook = n == 1
        is_cta = n == total
        print(f"  [{n}/{total}] Generating background with Imagen 3...")
        prompt = build_imagen_prompt(text, i, context, color)
        bg = generate_background(prompt, color)
        img = render_slide(bg, text, n, total, color, is_hook=is_hook, is_cta=is_cta)
        path = out / f"slide_{n:02d}.jpg"
        img.save(str(path), "JPEG", quality=95)
        saved.append(str(path))
        print(f"  ✓ {path}")
        if n < total:
            time.sleep(1)  # avoid rate limit

    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True)
    parser.add_argument("--post-id", required=True)
    parser.add_argument("--slides", required=True, help="JSON array of slide texts")
    parser.add_argument("--context", default="", help="Product context for Imagen prompts")
    parser.add_argument("--color", default="#2D1B69")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    try:
        slides = json.loads(args.slides)
    except json.JSONDecodeError as e:
        print(f"Error parsing --slides: {e}")
        sys.exit(1)

    output_dir = args.output or f"/tmp/tiktok-{args.product}/{args.post_id}/"
    print(f"\nGenerating {len(slides)} slides → {output_dir}")
    print(f"Backend: {'Imagen 3' if HAS_GENAI and GEMINI_API_KEY else 'gradient fallback'}\n")

    create_post_images(
        product=args.product,
        post_id=args.post_id,
        slides=slides,
        context=args.context,
        color=args.color,
        output_dir=output_dir,
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
