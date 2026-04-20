#!/usr/bin/env python3
"""
TikTok Autopilot — Comic-Style Post Generator
Replicates the @one_cup_of_english formula:
  AI illustration scene + dialogue speech bubbles

Usage:
    python3 create_comic.py \
        --product lingomock \
        --post-id post-comic-01 \
        --scenario "job_interview" \
        --output /tmp/tiktok-lingomock/comic-01/

Scenarios: job_interview, airport, restaurant, small_talk, phone_call
"""

import argparse
import io
import os
import sys
import textwrap
from pathlib import Path
from dotenv import dotenv_values

SKILL_DIR = Path(__file__).parent.parent
ENV_PATH = SKILL_DIR / ".env"
env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
GEMINI_API_KEY = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

try:
    from PIL import Image, ImageDraw, ImageFont
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    print("pip3 install Pillow google-genai")
    sys.exit(1)

# Canvas: TikTok 9:16
W, H = 1080, 1920

# ── Scenarios ─────────────────────────────────────────────────────────────

SCENARIOS = {
    "job_interview": {
        "scene": "professional office job interview room, applicant sitting across desk from interviewer, clean modern office, bright warm lighting, potted plants in background",
        "color": "#1a3a5c",  # navy
        "exchanges": [
            ("Interviewer", "So, tell me about yourself."),
            ("You", "I... um... I studied computer science and..."),
            ("Interviewer", "Take your time. What are your strengths?"),
            ("You", "Sorry, I know what I want to say but..."),
            ("Interviewer", "It's okay. Let's try again."),
            ("LingoMock", "Practice this exact scenario before your real interview.\nAI roleplay. Free. No judgment."),
        ],
    },
    "airport": {
        "scene": "busy airport check-in counter, traveler with red suitcase talking to airline staff, large windows with planes visible, teal and blue tones",
        "color": "#0d4f6e",
        "exchanges": [
            ("Staff", "Good morning! Where are you flying today?"),
            ("You", "Good morning! I'm flying to Toronto."),
            ("Staff", "May I see your passport and booking?"),
            ("You", "Of course! Here you go."),
            ("Staff", "Do you have any bags to check in?"),
            ("LingoMock", "Feel ready for any airport conversation.\nPractice with AI. Free."),
        ],
    },
    "restaurant": {
        "scene": "cozy restaurant interior, customer sitting at table talking to friendly waiter, warm ambient lighting, wooden tables and plants",
        "color": "#3d2b1f",
        "exchanges": [
            ("Waiter", "Hi! Are you ready to order?"),
            ("You", "Yes! I'd like the grilled salmon, please."),
            ("Waiter", "Great choice. Any allergies I should know about?"),
            ("You", "I'm allergic to nuts, actually."),
            ("Waiter", "Noted! And to drink?"),
            ("LingoMock", "Order confidently anywhere in the world.\nAI English practice. Free."),
        ],
    },
    "small_talk": {
        "scene": "office break room, two coworkers chatting by coffee machine, casual and friendly atmosphere, modern office kitchen background",
        "color": "#2d4a3e",
        "exchanges": [
            ("Coworker", "Hey! How was your weekend?"),
            ("You", "It was great, thanks! I went hiking."),
            ("Coworker", "Oh nice! Where did you go?"),
            ("You", "To the mountains near the city. So peaceful!"),
            ("Coworker", "That sounds amazing. I should try that!"),
            ("LingoMock", "Never run out of things to say in English.\nAI conversation practice. Free."),
        ],
    },
    "phone_call": {
        "scene": "person sitting at desk talking on phone, home office setting, calm and focused expression, natural window light",
        "color": "#2c1654",
        "exchanges": [
            ("Agent", "Thank you for calling. How can I help you?"),
            ("You", "Hi, I'd like to change my appointment, please."),
            ("Agent", "Of course. What date works better for you?"),
            ("You", "Would next Thursday be possible?"),
            ("Agent", "Let me check... Yes, 3pm is available."),
            ("LingoMock", "Handle any phone call in English with confidence.\nAI roleplay. Free."),
        ],
    },
}

# ── Imagen 4 scene generation ──────────────────────────────────────────────

def generate_scene(scene_desc: str) -> Image.Image:
    """Generate one illustration-style scene with Imagen 4."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"2D cartoon illustration, clean vector art style, bright vivid colors, "
        f"anime-adjacent professional look, {scene_desc}. "
        f"Two characters in a natural conversation pose. "
        f"Teal and blue dominant color palette. "
        f"Clean modern animation style like a high-quality explainer video. "
        f"Portrait 9:16 vertical format. "
        f"STRICT: NO text, NO words, NO speech bubbles, NO UI elements, NO logos."
    )
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
    img_bytes = result.generated_images[0].image.image_bytes
    return Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((W, H))


# ── Speech bubble ──────────────────────────────────────────────────────────

def draw_speech_bubble(draw: ImageDraw, text: str, speaker: str,
                        x: int, y: int, width: int, brand_color: str,
                        is_brand: bool = False):
    """Draw a comic-style speech bubble with speaker label."""
    font_path = None
    # Try to find a bold system font
    for fp in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        if Path(fp).exists():
            font_path = fp
            break

    try:
        font_body = ImageFont.truetype(font_path, 38) if font_path else ImageFont.load_default()
        font_label = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
    except Exception:
        font_body = ImageFont.load_default()
        font_label = font_body

    # Wrap text
    wrapped = textwrap.fill(text, width=28)
    lines = wrapped.split("\n")
    line_h = 48
    pad = 30
    bubble_h = len(lines) * line_h + pad * 2 + 40  # +40 for label

    # Brand slide style
    if is_brand:
        bg_color = brand_color
        text_color = "white"
        border_color = "white"
    else:
        bg_color = "white"
        text_color = "#1a1a1a"
        border_color = "#e0e0e0"

    # Draw rounded rectangle bubble
    r = 24
    box = [x, y, x + width, y + bubble_h]
    draw.rounded_rectangle(box, radius=r, fill=bg_color, outline=border_color, width=2)

    # Speaker label
    label_color = brand_color if not is_brand else "white"
    draw.text((x + pad, y + pad - 6), speaker.upper(), font=font_label,
              fill=label_color if not is_brand else "rgba(255,255,255,180)")

    # Body text
    for i, line in enumerate(lines):
        ty = y + pad + 36 + i * line_h
        draw.text((x + pad, ty), line, font=font_body, fill=text_color)

    return bubble_h


# ── Compose one frame ──────────────────────────────────────────────────────

def compose_frame(scene: Image.Image, speaker: str, dialogue: str,
                  brand_color: str, frame_idx: int, total: int,
                  product_name: str) -> Image.Image:
    """Overlay speech bubble on scene image."""
    img = scene.copy()

    # Darken bottom 45% for readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    grad_top = int(H * 0.55)
    draw_ov.rectangle([0, grad_top, W, H], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    is_brand = speaker == product_name or speaker == "LingoMock"

    # Bubble position: bottom area
    margin = 40
    bw = W - margin * 2
    by = H - 420 if not is_brand else H - 460

    draw_speech_bubble(draw, dialogue, speaker, margin, by, bw,
                       brand_color, is_brand=is_brand)

    # Progress dots
    dot_y = H - 50
    dot_r = 8
    spacing = 28
    total_w = total * spacing
    start_x = (W - total_w) // 2
    for i in range(total):
        cx = start_x + i * spacing + dot_r
        color = brand_color if i == frame_idx else "#cccccc"
        draw.ellipse([cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r], fill=color)

    return img


# ── Main ───────────────────────────────────────────────────────────────────

def run(product: str, post_id: str, scenario_key: str, output_dir: Path):
    if not GEMINI_API_KEY:
        print("ERROR: Set GEMINI_API_KEY in .env")
        sys.exit(1)

    scenario = SCENARIOS.get(scenario_key)
    if not scenario:
        print(f"Unknown scenario: {scenario_key}")
        print(f"Available: {', '.join(SCENARIOS.keys())}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    brand_color = scenario["color"]
    exchanges = scenario["exchanges"]

    print(f"\nGenerating {scenario_key} comic post for {product}")
    print(f"  {len(exchanges)} frames → {output_dir}")
    print(f"  Generating AI scene with Imagen 4...")

    scene = generate_scene(scenario["scene"])
    print(f"  ✓ Scene generated")

    for i, (speaker, dialogue) in enumerate(exchanges):
        is_brand = i == len(exchanges) - 1
        frame = compose_frame(scene, speaker, dialogue, brand_color,
                              i, len(exchanges), product.capitalize())
        path = output_dir / f"slide_{i+1:02d}.jpg"
        frame.save(path, "JPEG", quality=95)
        print(f"  ✓ slide_{i+1:02d}.jpg — {speaker}: {dialogue[:40]}...")

    print(f"\n✅ {len(exchanges)} slides saved to {output_dir}")
    print(f"   Open in Finder: open {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Comic-style TikTok post generator")
    parser.add_argument("--product", default="lingomock")
    parser.add_argument("--post-id", default="comic-01")
    parser.add_argument("--scenario", default="job_interview",
                        choices=list(SCENARIOS.keys()))
    parser.add_argument("--output", help="Output directory")
    args = parser.parse_args()

    output = Path(args.output) if args.output else \
        Path(f"/tmp/tiktok-{args.product}/{args.post_id}/")

    run(args.product, args.post_id, args.scenario, output)


if __name__ == "__main__":
    main()
