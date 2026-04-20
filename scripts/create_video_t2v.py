#!/usr/bin/env python3
"""
TikTok Autopilot — Text-to-Video Generator (Wan 2.6 via fal.ai)
Generates clean scene videos from text, then overlays speech bubbles + voiceover.

Advantages over image-to-video:
  - No text distortion (clean scenes, bubbles added via ffmpeg)
  - No need to upload source images
  - More cinematic motion

Cost: ~$0.05/s × 5s × 6 clips ≈ $1.50 per post

Usage:
    python3 create_video_t2v.py \
        --scenario job_interview \
        --slides /tmp/tiktok-lingomock/comic-01/ \
        --output /tmp/tiktok-lingomock/comic-01/final_t2v.mp4

Dependencies:
    pip3 install fal-client edge-tts
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from dotenv import dotenv_values

SKILL_DIR = Path(__file__).parent.parent
ENV_PATH = SKILL_DIR / ".env"
env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
FAL_KEY = env.get("FAL_KEY") or os.environ.get("FAL_KEY")

ENDPOINT = "wan/v2.6/text-to-video"
COST_PER_SEC = 0.05

# ── Scene prompts per scenario ─────────────────────────────────────────────────
# Each scenario has one consistent scene description + per-slide motion notes.
SCENE_BASE = {
    "job_interview": (
        "two professionals in a modern office, job interview setting, "
        "warm ambient lighting, potted plants in background, clean minimal desk, "
        "cinematic depth of field, photorealistic, 9:16 portrait"
    ),
    "airport": (
        "busy airport check-in counter, traveler with red suitcase talking to airline staff, "
        "large windows with planes visible, teal and blue tones, cinematic, 9:16 portrait"
    ),
    "small_talk": (
        "two coworkers chatting in a modern office break room, coffee machine in background, "
        "warm natural light, casual and friendly atmosphere, cinematic, 9:16 portrait"
    ),
    "phone_call": (
        "person sitting at a desk talking on phone, home office with natural window light, "
        "calm focused expression, warm tones, cinematic, 9:16 portrait"
    ),
    "restaurant": (
        "customer at a cozy restaurant table talking to a friendly waiter, "
        "warm ambient lighting, wooden tables, plants in background, cinematic, 9:16 portrait"
    ),
}

# Varied motion per slide for visual interest
SLIDE_MOTION = [
    "slow cinematic push-in, warm light, calm and professional",
    "subtle breathing motion, soft bokeh, attentive expression",
    "gentle camera drift right, warm light shimmer, natural movement",
    "slow zoom out, thoughtful pause, cinematic mood",
    "soft focus pull, reassuring atmosphere, warm color grading",
    "gentle parallax motion, inspirational feeling, smooth and elegant",
]

# ── Voiceover ─────────────────────────────────────────────────────────────────
VOICES = {
    "interviewer": "en-US-GuyNeural",
    "staff":       "en-US-GuyNeural",
    "coworker":    "en-US-JennyNeural",
    "agent":       "en-US-GuyNeural",
    "waiter":      "en-US-GuyNeural",
    "you":         "en-US-JennyNeural",
    "lingomock":   "en-US-AriaNeural",
}

SCENARIOS = {
    "job_interview": [
        ("Interviewer", "So, tell me about yourself."),
        ("You", "I... um... I studied computer science and..."),
        ("Interviewer", "Take your time. What are your strengths?"),
        ("You", "Sorry, I know what I want to say but..."),
        ("Interviewer", "It's okay. Let's try again."),
        ("LingoMock", "Practice this exact scenario before your real interview. AI roleplay. Free. No judgment."),
    ],
    "airport": [
        ("Staff", "Good morning! Where are you flying today?"),
        ("You", "Good morning! I'm flying to Toronto."),
        ("Staff", "May I see your passport and booking?"),
        ("You", "Of course! Here you go."),
        ("Staff", "Do you have any bags to check in?"),
        ("LingoMock", "Feel ready for any airport conversation. Practice with AI. Free."),
    ],
    "small_talk": [
        ("Coworker", "Hey! How was your weekend?"),
        ("You", "It was great, thanks! I went hiking."),
        ("Coworker", "Oh nice! Where did you go?"),
        ("You", "To the mountains near the city. So peaceful!"),
        ("Coworker", "That sounds amazing. I should try that!"),
        ("LingoMock", "Never run out of things to say in English. AI conversation practice. Free."),
    ],
    "phone_call": [
        ("Agent", "Thank you for calling. How can I help you?"),
        ("You", "Hi, I'd like to change my appointment, please."),
        ("Agent", "Of course. What date works better for you?"),
        ("You", "Would next Thursday be possible?"),
        ("Agent", "Let me check... Yes, 3pm is available."),
        ("LingoMock", "Handle any phone call in English with confidence. AI roleplay. Free."),
    ],
    "restaurant": [
        ("Waiter", "Hi! Are you ready to order?"),
        ("You", "Yes! I'd like the grilled salmon, please."),
        ("Waiter", "Great choice. Any allergies I should know about?"),
        ("You", "I'm allergic to nuts, actually."),
        ("Waiter", "Noted! And to drink?"),
        ("LingoMock", "Order confidently anywhere in the world. AI English practice. Free."),
    ],
}


# ── Text-to-Video ─────────────────────────────────────────────────────────────

def generate_scene_clip(scene: str, slide_idx: int, duration: int = 5) -> str:
    """Generate a clean scene video clip via Wan 2.6 T2V. Returns video URL."""
    import fal_client

    motion = SLIDE_MOTION[slide_idx % len(SLIDE_MOTION)]
    prompt = f"{scene}, {motion}"
    cost = COST_PER_SEC * duration
    print(f"  T2V generating... (~${cost:.2f})")

    result = fal_client.subscribe(
        ENDPOINT,
        arguments={
            "prompt": prompt,
            "negative_prompt": "text, letters, captions, subtitles, watermark, logo, blur, low quality, ugly",
            "resolution": "720p",
            "duration": str(duration),
            "enable_prompt_expansion": False,
        },
        with_logs=False,
    )

    video_url = result.get("video", {}).get("url", "")
    if not video_url:
        raise ValueError(f"No video URL in response: {result}")
    return video_url


def download_clip(url: str, dest: Path):
    print(f"  Downloading → {dest.name}")
    urllib.request.urlretrieve(url, dest)


# ── Speech bubble overlay ─────────────────────────────────────────────────────

def overlay_bubble(clip: Path, slide: Path, output: Path, bubble_frac: float = 0.42):
    """
    Overlay the bottom `bubble_frac` of the original slide (speech bubble area)
    onto the animated clip. Top = clean T2V scene. Bottom = original crisp text.
    """
    # Get clip dimensions
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(clip)
    ], capture_output=True, text=True)
    try:
        w, h = map(int, probe.stdout.strip().split(","))
    except Exception:
        w, h = 720, 1280  # fallback

    bubble_h = int(h * bubble_frac)
    bubble_y = h - bubble_h

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(clip),
        "-i", str(slide),
        "-filter_complex", (
            f"[1:v]scale={w}:{h}[s];"
            f"[s]crop={w}:{bubble_h}:0:{bubble_y}[bubble];"
            f"[0:v]scale={w}:{h}[base];"
            f"[base][bubble]overlay=0:{bubble_y}[v]"
        ),
        "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "20", "-preset", "fast",
        str(output)
    ], check=True, capture_output=True)


# ── Voiceover ─────────────────────────────────────────────────────────────────

async def _gen_tts(text: str, voice: str, path: Path):
    import edge_tts
    comm = edge_tts.Communicate(text, voice=voice, rate="-5%")
    await comm.save(str(path))

def get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 4.0

def generate_voiceover(scenario: str, clips_dir: Path, clip_duration: int) -> Path:
    try:
        import edge_tts
    except ImportError:
        print("pip3 install edge-tts")
        sys.exit(1)

    exchanges = SCENARIOS[scenario]
    print(f"\nGenerating voiceover ({len(exchanges)} lines)...")
    tts_dir = clips_dir / "_tts"
    tts_dir.mkdir(exist_ok=True)

    async def gen_all():
        tasks, paths = [], []
        for i, (speaker, text) in enumerate(exchanges):
            voice = VOICES.get(speaker.lower(), "en-US-JennyNeural")
            path = tts_dir / f"line_{i:02d}.mp3"
            paths.append(path)
            tasks.append(_gen_tts(text, voice, path))
        await asyncio.gather(*tasks)
        return paths

    tts_files = asyncio.run(gen_all())

    padded = []
    for i, (tf, (speaker, _)) in enumerate(zip(tts_files, exchanges)):
        dur = get_audio_duration(tf)
        pad = max(clip_duration - dur, 0.1)
        out = tts_dir / f"padded_{i:02d}.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(tf),
            "-af", f"apad=pad_dur={pad:.2f}",
            "-t", str(clip_duration), str(out)
        ], check=True, capture_output=True)
        padded.append(out)
        print(f"  [{i+1}] {speaker}: {dur:.1f}s → padded to {clip_duration}s")

    list_file = tts_dir / "concat.txt"
    with open(list_file, "w") as f:
        for p in padded:
            f.write(f"file '{p.absolute()}'\n")

    vo_path = clips_dir / "voiceover.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(vo_path)
    ], check=True, capture_output=True)
    print(f"  ✓ voiceover.mp3")
    return vo_path


# ── Concat + mix ──────────────────────────────────────────────────────────────

def concat_clips(clips: list[Path], output: Path):
    list_file = output.parent / "_concat.txt"
    with open(list_file, "w") as f:
        for c in clips:
            f.write(f"file '{c.absolute()}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output)
    ], check=True, capture_output=True)
    list_file.unlink(missing_ok=True)

def mix_audio(video: Path, audio: Path, output: Path):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(video), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        "-movflags", "+faststart", str(output)
    ], check=True, capture_output=True)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(scenario: str, slides_dir: Path, output: Path, duration: int = 5):
    if not FAL_KEY:
        print("ERROR: FAL_KEY not set in .env")
        sys.exit(1)

    os.environ["FAL_KEY"] = FAL_KEY

    scene = SCENE_BASE.get(scenario)
    if not scene:
        print(f"Unknown scenario: {scenario}")
        print(f"Available: {', '.join(SCENE_BASE.keys())}")
        sys.exit(1)

    slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not slides:
        print(f"ERROR: No slide_*.jpg in {slides_dir}")
        sys.exit(1)

    n = len(slides)
    total_cost = COST_PER_SEC * duration * n
    print(f"\nWan 2.6 Text-to-Video")
    print(f"  Scenario: {scenario}")
    print(f"  Clips: {n} × {duration}s = {n*duration}s")
    print(f"  Estimated cost: ${total_cost:.2f}")
    print(f"  Output: {output}\n")

    output.parent.mkdir(parents=True, exist_ok=True)
    clips_dir = output.parent / "_t2v_clips"
    clips_dir.mkdir(exist_ok=True)

    # Step 1: Generate T2V clips + overlay bubbles
    fixed_clips = []
    for i, slide in enumerate(slides):
        raw_clip = clips_dir / f"clip_{i:02d}_raw.mp4"
        fixed_clip = clips_dir / f"clip_{i:02d}.mp4"

        if fixed_clip.exists() and fixed_clip.stat().st_size > 10000:
            print(f"[{i+1}/{n}] slide_{i+1:02d} — skipping (exists)")
            fixed_clips.append(fixed_clip)
            continue

        print(f"[{i+1}/{n}] slide_{i+1:02d}")
        video_url = generate_scene_clip(scene, i, duration)
        download_clip(video_url, raw_clip)
        print(f"  Overlaying speech bubble...")
        overlay_bubble(raw_clip, slide, fixed_clip)
        raw_clip.unlink(missing_ok=True)
        fixed_clips.append(fixed_clip)
        print(f"  ✓ done")
        time.sleep(1)

    # Step 2: Voiceover
    audio = generate_voiceover(scenario, clips_dir, duration)

    # Step 3: Concat + mix
    print(f"\nConcatenating {n} clips...")
    raw_video = clips_dir / "raw_video.mp4"
    concat_clips(fixed_clips, raw_video)
    mix_audio(raw_video, audio, output)

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\n✅ {output} ({size_mb:.1f} MB)")
    print(f"   Upload: https://www.tiktok.com/tiktokstudio/upload")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=list(SCENARIOS.keys()))
    parser.add_argument("--slides", required=True, help="Dir with slide_*.jpg (for speech bubbles)")
    parser.add_argument("--output")
    parser.add_argument("--duration", type=int, default=5)
    args = parser.parse_args()

    slides_dir = Path(args.slides)
    output = Path(args.output) if args.output else slides_dir / "final_t2v.mp4"
    run(args.scenario, slides_dir, output, args.duration)


if __name__ == "__main__":
    main()
