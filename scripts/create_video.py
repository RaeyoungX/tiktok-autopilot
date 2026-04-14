#!/usr/bin/env python3
"""
TikTok Autopilot — Video Generator (Phase 4b)
Uses Seedance 2.0 (Image-to-Video) to animate each Imagen 4 slide,
then concatenates into a TikTok-ready 9:16 MP4 with ffmpeg.

Pipeline:
  slide_01.jpg ─┐
  slide_02.jpg ─┤  Seedance 2.0 I2V  →  clip_01.mp4 ─┐
  slide_03.jpg ─┤  (fal.ai)          →  clip_02.mp4 ─┤  ffmpeg concat  →  final.mp4
  slide_04.jpg ─┘                    →  clip_03.mp4 ─┘

Usage:
    # Animate existing slides from create_images.py
    python3 create_video.py \
        --slides /tmp/tiktok-lingomock/post-01/ \
        --output /tmp/tiktok-lingomock/post-01/final.mp4 \
        --duration 5 \
        --quality fast

    # Generate from scratch with text prompts (no slides needed)
    python3 create_video.py \
        --product lingomock \
        --post-id post-01 \
        --prompt "Person confidently speaking English in a job interview" \
        --output /tmp/tiktok-lingomock/post-01/final.mp4

Dependencies:
    pip3 install fal-client
    brew install ffmpeg
"""

import argparse
import os
import subprocess
import sys
import time
import tempfile
import urllib.request
from pathlib import Path
from dotenv import dotenv_values

SKILL_DIR = Path(__file__).parent.parent
ENV_PATH = SKILL_DIR / ".env"
env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

FAL_KEY = env.get("FAL_KEY") or os.environ.get("FAL_KEY")

# Seedance 2.0 endpoints on fal.ai
ENDPOINTS = {
    "fast":     "bytedance/seedance-2.0/fast/image-to-video",
    "standard": "bytedance/seedance-2.0/image-to-video",
}

# Cost reference (fal.ai, per second of 720p)
COST_PER_SEC = {"fast": 0.2419, "standard": 0.30}


# ── Image hosting helper ───────────────────────────────────────────────────

def upload_image(filepath: Path) -> str:
    """Upload local image to 0x0.st for a public URL (Seedance needs URLs)."""
    import urllib.request, urllib.parse
    print(f"  Uploading {filepath.name}...")
    with open(filepath, "rb") as f:
        import requests
        resp = requests.post("https://0x0.st", files={"file": (filepath.name, f, "image/jpeg")}, timeout=30)
        resp.raise_for_status()
        url = resp.text.strip()
    print(f"  ✓ {url}")
    return url


# ── Seedance 2.0 via fal.ai ───────────────────────────────────────────────

def animate_slide(image_url: str, prompt: str, duration: int, quality: str) -> str:
    """Send one image to Seedance 2.0, return video URL."""
    import fal_client

    endpoint = ENDPOINTS[quality]
    print(f"  Generating {duration}s clip... (${COST_PER_SEC[quality] * duration:.2f})")

    result = fal_client.subscribe(
        endpoint,
        arguments={
            "image_url": image_url,
            "prompt": prompt,
            "duration": str(duration),
            "resolution": "720p",
            "aspect_ratio": "9:16",
        },
        with_logs=False,
    )

    video_url = result.get("video", {}).get("url") or result.get("url", "")
    if not video_url:
        raise ValueError(f"No video URL in response: {result}")
    return video_url


def download_video(url: str, dest: Path):
    """Download video from URL to local file."""
    print(f"  Downloading clip → {dest.name}")
    urllib.request.urlretrieve(url, dest)


# ── ffmpeg concat ──────────────────────────────────────────────────────────

def concat_clips(clip_paths: list[Path], output: Path, crossfade_sec: float = 0.5):
    """Concatenate video clips with crossfade transition using ffmpeg."""
    if len(clip_paths) == 1:
        import shutil
        shutil.copy(clip_paths[0], output)
        return

    # Build ffmpeg filter_complex for crossfade between all clips
    # Simple approach: use concat filter (no crossfade for reliability)
    list_file = output.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{clip.absolute()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr[-300:]}")
        raise RuntimeError("ffmpeg concat failed")

    print(f"  ✓ Concatenated {len(clip_paths)} clips → {output}")


def add_audio(video: Path, audio: Path, output: Path):
    """Mix background audio into video (optional)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"  ✓ Audio mixed → {output}")


# ── Slide prompts ──────────────────────────────────────────────────────────

SLIDE_MOTION_PROMPTS = [
    "slow cinematic zoom in, shallow depth of field, dramatic atmospheric lighting",
    "gentle camera drift left, soft bokeh background, emotional mood",
    "slow pan upward, moody cinematic color grade, film grain",
    "subtle handheld motion, warm golden light, aspirational feel",
    "slow pull back reveal, dramatic contrast, cinematic widescreen feel",
]


def build_slide_prompt(slide_idx: int, product_context: str = "") -> str:
    motion = SLIDE_MOTION_PROMPTS[slide_idx % len(SLIDE_MOTION_PROMPTS)]
    base = f"Cinematic vertical video 9:16. {motion}."
    if product_context:
        base += f" Context: {product_context[:60]}."
    base += " NO text, NO UI, NO phone screens. Pure atmospheric visual."
    return base


# ── Main pipeline ──────────────────────────────────────────────────────────

def run_video(
    slides_dir: Path,
    output: Path,
    duration: int,
    quality: str,
    product_context: str = "",
    audio_path: Path | None = None,
):
    if not FAL_KEY:
        print("ERROR: Set FAL_KEY in .env")
        print("  Get key: https://fal.ai/dashboard/keys")
        sys.exit(1)

    os.environ["FAL_KEY"] = FAL_KEY

    # Find slides
    slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not slides:
        print(f"ERROR: No slide_*.jpg found in {slides_dir}")
        sys.exit(1)

    n = len(slides)
    total_cost = COST_PER_SEC[quality] * duration * n
    total_sec = duration * n

    print(f"\nSeedance 2.0 Video Generator")
    print(f"  Slides: {n} × {duration}s = {total_sec}s total")
    print(f"  Quality: {quality} @ ${COST_PER_SEC[quality]}/s")
    print(f"  Estimated cost: ${total_cost:.2f}")
    print(f"  Output: {output}\n")

    output.parent.mkdir(parents=True, exist_ok=True)
    clip_paths = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        for i, slide in enumerate(slides):
            print(f"\n[{i+1}/{n}] {slide.name}")

            # Upload slide to get public URL
            image_url = upload_image(slide)

            # Animate with Seedance
            prompt = build_slide_prompt(i, product_context)
            video_url = animate_slide(image_url, prompt, duration, quality)

            # Download clip
            clip_path = tmp / f"clip_{i+1:02d}.mp4"
            download_video(video_url, clip_path)
            clip_paths.append(clip_path)

            time.sleep(1)  # rate limiting courtesy

        # Concatenate all clips
        print(f"\nConcatenating {n} clips...")
        raw_output = tmp / "raw_final.mp4" if audio_path else output
        concat_clips(clip_paths, raw_output)

        # Optional: add background audio
        if audio_path and audio_path.exists():
            print("Mixing background audio...")
            add_audio(raw_output, audio_path, output)
        elif audio_path:
            print(f"  ⚠ Audio file not found: {audio_path}, skipping")

    print(f"\n✅ Video ready: {output}")
    print(f"   Upload via TikTok Studio: https://www.tiktok.com/tiktokstudio/upload")
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"   File size: {size_mb:.1f} MB")


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate TikTok video from slides using Seedance 2.0")
    parser.add_argument("--slides", required=True, help="Directory containing slide_*.jpg files")
    parser.add_argument("--output", help="Output MP4 path (default: slides_dir/final.mp4)")
    parser.add_argument("--duration", type=int, default=5, help="Seconds per slide (4-10, default: 5)")
    parser.add_argument("--quality", choices=["fast", "standard"], default="fast",
                        help="fast=$0.24/s, standard=$0.30/s (default: fast)")
    parser.add_argument("--context", default="", help="Product context for motion prompts")
    parser.add_argument("--audio", help="Optional background audio file (.mp3/.wav)")
    args = parser.parse_args()

    slides_dir = Path(args.slides)
    output = Path(args.output) if args.output else slides_dir / "final.mp4"
    audio = Path(args.audio) if args.audio else None

    run_video(
        slides_dir=slides_dir,
        output=output,
        duration=args.duration,
        quality=args.quality,
        product_context=args.context,
        audio_path=audio,
    )


if __name__ == "__main__":
    main()
