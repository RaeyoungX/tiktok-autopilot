#!/usr/bin/env python3
"""
generate_viral_video.py — TikTok viral video generator (T2V approach)

APPROACH:
  1. Load calendar post (hook + script lines)
  2. Gemini Flash analyzes script → writes cinematic scene-by-scene breakdown
     (each scene = what the CAMERA SHOWS, not just text on background)
  3. Each scene description → T2V AI (Wan 2.6 via fal.ai) → real video clip
  4. ffmpeg: text overlay + voiceover per clip
  5. Concat → final TikTok-ready video

This replicates @cristinainshanghai format (29K-49K likes):
  NOT text-on-background, but actual visual scenes:
  - "Person opens blocked TikTok app in Shanghai, confused look, red error screen"
  - "VPN shield icon animates in, phone connects, Instagram opens, relief expression"

Cost: ~$0.30-0.50/scene × 6-8 scenes ≈ $2-4/video (Wan 2.6 fast)

Usage:
    python3 generate_viral_video.py --product chinaready --day 2
    python3 generate_viral_video.py --product chinaready --day 2 --dry-run
    python3 generate_viral_video.py --product chinaready --day 2 --print-scenes

Dependencies:
    pip3 install google-genai fal-client edge-tts python-dotenv Pillow requests
    brew install ffmpeg
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Run: pip3 install Pillow")
    sys.exit(1)

from dotenv import dotenv_values

SKILL_DIR = Path(__file__).parent.parent
ENV = dotenv_values(SKILL_DIR / ".env") if (SKILL_DIR / ".env").exists() else {}

GEMINI_KEY = ENV.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
FAL_KEY    = ENV.get("FAL_KEY")          or os.environ.get("FAL_KEY")

DATA_DIR = Path.home() / ".claude" / "tiktok-autopilot"
W, H, FPS = 1080, 1920, 30

# T2V models to try in order (fal.ai endpoints)
T2V_MODELS = [
    "fal-ai/minimax/video-01",                          # MiniMax Hailuo — best quality, 6s
    "fal-ai/kling-video/v1.6/standard/text-to-video",  # Kling 1.6 — duration must be '5' or '10'
    "fal-ai/wan-ai/wan2.6",                             # Wan 2.6 T2V
]

# Model-specific parameter overrides
MODEL_PARAMS = {
    "fal-ai/kling-video/v1.6/standard/text-to-video": {
        "duration": "5",  # Kling only accepts '5' or '10'
        "aspect_ratio": "9:16",
    },
    "fal-ai/minimax/video-01": {
        "aspect_ratio": "9:16",
        # duration not supported — uses default 6s
    },
}


# ── Calendar loading ───────────────────────────────────────────────────────────

def load_calendar_post(product: str, day: int) -> dict:
    path = DATA_DIR / product / "calendar_30day.json"
    if not path.exists():
        print(f"ERROR: No calendar at {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        cal = json.load(f)
    for p in cal.get("posts", []):
        if p.get("day") == day:
            return p
    print(f"ERROR: Day {day} not in calendar")
    sys.exit(1)


# ── Scene breakdown via Gemini Flash ──────────────────────────────────────────

SCENE_BREAKDOWN_PROMPT = """You are a TikTok video director. Convert this script into a cinematic scene-by-scene breakdown for text-to-video AI generation.

VIRAL FORMAT REFERENCE: @cristinainshanghai "Don't land in Shanghai without THESE apps!" (6K+ likes)
- Each scene shows REAL ACTIONS (person using the app, reactions, locations)
- NOT text-on-background — actual visual storytelling
- Quick cuts, 3-5 seconds per scene
- Modern, vibrant, authentic TikTok aesthetic

PRODUCT: {product}
HOOK: {hook}
SCRIPT LINES:
{script_lines}

Generate a JSON array of scenes. Each scene:
{{
  "scene_num": 1,
  "duration": 4,
  "t2v_prompt": "Cinematic description of what the camera shows (action, location, emotion). No text on screen. 9:16 vertical. TikTok aesthetic. Max 100 words.",
  "text_overlay": "Short punchy text that appears on screen (from script line)",
  "tts_narration": "What the voiceover says (from script line, natural speaking)"
}}

RULES for t2v_prompt:
- Show ACTIONS not logos: "person taps Alipay on phone, payment animation appears" not "Alipay logo"
- Include LOCATION: Shanghai street, airport, convenience store, cafe
- Include EMOTION: surprised, confident, relieved, excited
- End with: "cinematic, vertical 9:16, modern TikTok style, no text on screen"
- Be specific about what's ON SCREEN visually

Return ONLY valid JSON array, no markdown, no explanation."""


def generate_scene_breakdown(post: dict, product: str) -> list[dict]:
    """Use Gemini Flash to convert script into cinematic T2V scene descriptions."""
    if not GEMINI_KEY:
        print("  ⚠ No GEMINI_API_KEY — using fallback scene descriptions")
        return _fallback_scenes(post)

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_KEY)
        hook = post.get("hook", "")
        script_lines = post.get("script", [])
        lines_text = "\n".join(f"{i+1}. {l}" for i, l in enumerate(script_lines) if l.strip())

        prompt = SCENE_BREAKDOWN_PROMPT.format(
            product=product,
            hook=hook,
            script_lines=lines_text,
        )

        # Try models in order until one works
        response = None
        for model_id in ["gemini-2.5-flash", "gemini-2.0-flash-001", "gemini-flash-latest"]:
            try:
                response = client.models.generate_content(model=model_id, contents=prompt)
                break
            except Exception as model_err:
                print(f"  ⚠ {model_id}: {model_err}")
                continue
        if response is None:
            raise RuntimeError("All Gemini models failed")

        raw = response.text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        scenes = json.loads(raw)
        print(f"  ✓ Gemini generated {len(scenes)} scenes")
        return scenes

    except Exception as e:
        print(f"  ⚠ Gemini scene generation failed: {e}")
        return _fallback_scenes(post)


def _fallback_scenes(post: dict) -> list[dict]:
    """Fallback: build scenes directly from script lines."""
    scenes = []
    hook = post.get("hook", "")
    script_lines = [l for l in post.get("script", []) if l.strip()]

    # Hook scene
    scenes.append({
        "scene_num": 0,
        "duration": 4,
        "t2v_prompt": (
            f"Person in Shanghai city looking at phone with curious expression, "
            f"city street background with neon lights, close-up of face then wide shot, "
            f"modern urban setting, cinematic, vertical 9:16, TikTok style, no text on screen"
        ),
        "text_overlay": hook,
        "tts_narration": re.sub(r'[^\x00-\x7F]+', '', hook).strip() or hook,
    })

    for i, line in enumerate(script_lines):
        clean = re.sub(r'[^\x00-\x7F]+', '', line).strip() or line
        scenes.append({
            "scene_num": i + 1,
            "duration": 5,
            "t2v_prompt": (
                f"Realistic scene illustrating: {line[:80]}. "
                f"Shanghai urban setting, person reacting naturally, modern smartphone visible, "
                f"cinematic lighting, vertical 9:16, TikTok documentary style, no text on screen"
            ),
            "text_overlay": line,
            "tts_narration": clean,
        })

    # CTA scene
    scenes.append({
        "scene_num": len(scenes),
        "duration": 3,
        "t2v_prompt": (
            "Happy traveler in Shanghai walking confidently, phone in hand, city skyline background, "
            "thumbs up gesture, golden hour lighting, excited expression, "
            "cinematic, vertical 9:16, TikTok style, no text on screen"
        ),
        "text_overlay": "Save this ⬇️  Follow for more China tips!",
        "tts_narration": "Save this and follow for more China travel tips!",
    })

    return scenes


# ── T2V via fal.ai ─────────────────────────────────────────────────────────────

def generate_t2v_clip(t2v_prompt: str, duration: int, out_path: Path) -> bool:
    """Generate video clip from text prompt using fal.ai T2V models."""
    if not FAL_KEY:
        print("  ⚠ No FAL_KEY — cannot call T2V")
        return False

    os.environ["FAL_KEY"] = FAL_KEY

    try:
        import fal_client
    except ImportError:
        print("  ⚠ Run: pip3 install fal-client")
        return False

    for model in T2V_MODELS:
        try:
            print(f"  T2V [{model.split('/')[-1]}]: {t2v_prompt[:60]}...")

            # Build args — use model-specific overrides where needed
            args = {
                "prompt": t2v_prompt,
                "duration": str(duration),
                "aspect_ratio": "9:16",
            }
            # Apply model-specific overrides (e.g. Kling needs '5' not '4')
            overrides = MODEL_PARAMS.get(model, {})
            args.update(overrides)

            result = fal_client.subscribe(
                model,
                arguments=args,
                with_logs=False,
            )

            # Extract video URL (different models return different structures)
            video_url = (
                result.get("video", {}).get("url")
                or result.get("video_url")
                or result.get("url")
                or (result.get("videos") or [{}])[0].get("url", "")
            )

            if not video_url:
                print(f"  ⚠ No video URL from {model}: {list(result.keys())}")
                continue

            print(f"  ✓ Downloading from {model}...")
            urllib.request.urlretrieve(video_url, out_path)

            if out_path.exists() and out_path.stat().st_size > 10000:
                return True
            else:
                print(f"  ⚠ Download too small, trying next model...")

        except Exception as e:
            print(f"  ⚠ {model} failed: {e}")
            continue

    return False


# ── Text overlay (PIL) ─────────────────────────────────────────────────────────

def _get_font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/SFNSDisplay.otf",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_text_overlay(text: str, out_path: Path, is_hook: bool = False):
    """
    Create transparent PNG overlay with text at bottom of frame.
    Bottom 35%: semi-transparent dark gradient + bold white text.
    """
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Dark gradient band at bottom for readability
    band_start = int(H * (0.45 if is_hook else 0.58))
    for y in range(band_start, H):
        t = (y - band_start) / (H - band_start)
        alpha = int(200 * min(1.0, t ** 0.7))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    # Clean text (remove emoji for better rendering)
    clean_text = re.sub(r'[^\x00-\x7F]+', ' ', text).strip()
    if not clean_text:
        clean_text = text  # keep original if all emoji

    font_size = 80 if is_hook else 72
    font = _get_font(font_size, bold=True)

    # Word wrap
    words = clean_text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        try:
            tw = draw.textlength(test, font=font)
        except Exception:
            tw = len(test) * font_size * 0.55
        if tw < W - 80:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))

    line_h = int(font_size * 1.25)
    total_h = len(lines) * line_h

    if is_hook:
        start_y = H // 2 - total_h // 2
    else:
        start_y = H - 200 - total_h

    for i, line in enumerate(lines):
        try:
            tw = draw.textlength(line, font=font)
        except Exception:
            tw = len(line) * font_size * 0.55
        x = (W - tw) // 2
        y = start_y + i * line_h
        # Shadow
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    overlay.save(out_path, "PNG")


def composite_text(video_path: Path, overlay_path: Path, out_path: Path, duration: float) -> bool:
    """Overlay text PNG onto video clip."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(overlay_path),
        "-filter_complex",
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[bg];"
        f"[bg][1:v]overlay=0:0:format=auto[out]",
        "-map", "[out]",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p",
        str(out_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ⚠ ffmpeg composite error: {r.stderr[-200:]}")
    return r.returncode == 0


# ── Voiceover ──────────────────────────────────────────────────────────────────

def generate_voiceover(text: str, out_path: Path, duration: float):
    async def _run():
        try:
            import edge_tts
            tts = edge_tts.Communicate(text, "en-US-AriaNeural", rate="+5%")
            raw = out_path.with_suffix(".raw.mp3")
            await tts.save(str(raw))
            subprocess.run([
                "ffmpeg", "-y", "-i", str(raw),
                "-af", f"apad,atrim=0:{duration}",
                "-c:a", "aac", "-b:a", "128k", str(out_path)
            ], capture_output=True)
            raw.unlink(missing_ok=True)
        except Exception as e:
            print(f"  ⚠ TTS: {e}")
    asyncio.run(_run())


def merge_audio(video: Path, audio: Path, out: Path):
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)
    ], capture_output=True)


def concat_clips(clips: list[Path], output: Path):
    list_file = output.parent / "_concat.txt"
    with open(list_file, "w") as f:
        for c in clips:
            f.write(f"file '{c.absolute()}'\n")
    r = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output)
    ], capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    if r.returncode != 0:
        print(f"  ⚠ Concat error: {r.stderr[-200:]}")


# ── Main pipeline ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate viral TikTok video via T2V AI")
    parser.add_argument("--product", required=True)
    parser.add_argument("--day", type=int, required=True)
    parser.add_argument("--output", help="Output MP4 path")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-scenes", action="store_true",
                        help="Print Gemini scene breakdown and exit (no video generation)")
    args = parser.parse_args()

    tmp_dir = Path(f"/tmp/tiktok-{args.product}")
    out_path = Path(args.output) if args.output else tmp_dir / f"day{args.day:02d}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    post = load_calendar_post(args.product, args.day)
    hook = post.get("hook", "")

    print(f"\n{'='*60}")
    print(f"  Viral Video Generator (T2V approach)")
    print(f"  Pipeline: Gemini scene breakdown → T2V AI → text overlay")
    print(f"{'='*60}")
    print(f"  Product : {args.product}")
    print(f"  Day     : {args.day} — {post.get('date', '?')}")
    print(f"  Hook    : {hook[:65]}")
    print(f"  Lines   : {len([l for l in post.get('script', []) if l.strip()])}")
    print(f"  Output  : {out_path}")

    # Step 1: Generate scene breakdown
    print(f"\n[1/4] Gemini Flash → scene breakdown...")
    scenes = generate_scene_breakdown(post, args.product)

    # Print scenes and optionally exit
    print(f"\n  {'─'*56}")
    print(f"  SCENE BREAKDOWN ({len(scenes)} scenes):")
    print(f"  {'─'*56}")
    for s in scenes:
        print(f"\n  Scene {s['scene_num']} ({s['duration']}s)")
        print(f"  Camera: {s['t2v_prompt'][:80]}...")
        print(f"  Text:   {s['text_overlay'][:60]}")
    print(f"  {'─'*56}")

    if args.print_scenes or args.dry_run:
        print("\n  [--print-scenes / --dry-run] Exiting before video generation.")
        return

    # Step 2-4: Generate each scene
    work_dir = tmp_dir / f"day{args.day:02d}_t2v"
    work_dir.mkdir(parents=True, exist_ok=True)
    final_clips = []

    for scene in scenes:
        snum = scene["scene_num"]
        duration = scene.get("duration", 5)
        t2v_prompt = scene["t2v_prompt"]
        text = scene.get("text_overlay", "")
        tts_text = scene.get("tts_narration", text)

        seg_dir = work_dir / f"scene_{snum:02d}"
        seg_dir.mkdir(exist_ok=True)

        print(f"\n  ── Scene {snum}: {text[:50]} ──")

        # Step 2: T2V generation
        raw_clip = seg_dir / "raw.mp4"
        ok = generate_t2v_clip(t2v_prompt, duration, raw_clip)

        if not ok:
            print(f"  ⚠ T2V failed for scene {snum}, skipping")
            continue

        # Step 3: Text overlay
        overlay_path = seg_dir / "overlay.png"
        is_hook = snum == 0
        make_text_overlay(text, overlay_path, is_hook=is_hook)

        composited = seg_dir / "composited.mp4"
        if not composite_text(raw_clip, overlay_path, composited, duration):
            composited = raw_clip  # use raw if composite failed

        # Step 4: Voiceover
        if not args.no_audio and tts_text:
            tts_clean = re.sub(r'[^\x00-\x7F]+', '', tts_text).strip() or tts_text
            audio_path = seg_dir / "voice.aac"
            final_clip = seg_dir / "final.mp4"
            print(f"  Voiceover: {tts_clean[:50]}...")
            generate_voiceover(tts_clean, audio_path, duration)
            if audio_path.exists():
                merge_audio(composited, audio_path, final_clip)
                final_clips.append(final_clip)
                continue

        final_clips.append(composited)

    if not final_clips:
        print("\n⚠ No clips generated! Check FAL_KEY and T2V model availability.")
        print("  Tip: run with --print-scenes to see the scene breakdown without generating video.")
        return

    # Concatenate
    print(f"\n[4/4] Concatenating {len(final_clips)} clips...")
    concat_clips(final_clips, out_path)

    size_mb = out_path.stat().st_size / 1024 / 1024 if out_path.exists() else 0
    print(f"\n{'='*60}")
    print(f"  ✅ {out_path.name} ({size_mb:.1f} MB)")
    print(f"{'='*60}")
    print(f"\nPublish:")
    print(f"  python3 publish_browser.py --video {out_path} --product {args.product} --day {args.day}")


if __name__ == "__main__":
    main()
