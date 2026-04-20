#!/usr/bin/env python3
"""
TikTok Autopilot — Video Generator (Wan 2.6 via fal.ai)
Animates each comic slide with real AI motion, then:
  - Overlays original speech bubble area back (fixes AI text distortion)
  - Optionally generates edge-tts voiceover and mixes audio

Cost: ~$0.05/s × 5s × 6 slides ≈ $1.50 per post

Usage:
    # With auto voiceover:
    python3 create_video_wan.py \
        --slides /tmp/tiktok-lingomock/comic-01/ \
        --scenario job_interview \
        --output /tmp/tiktok-lingomock/comic-01/final_wan.mp4

    # With existing audio:
    python3 create_video_wan.py \
        --slides /tmp/tiktok-lingomock/comic-01/ \
        --audio /tmp/tiktok-lingomock/comic-01/voiceover.mp3 \
        --output /tmp/tiktok-lingomock/comic-01/final_wan.mp4

Dependencies:
    pip3 install fal-client requests edge-tts
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

ENDPOINT = "wan/v2.6/image-to-video"
COST_PER_SEC = 0.05

# Motion prompts per slide index
MOTION_PROMPTS = [
    "subtle atmospheric motion, soft light rays shifting gently, very slow camera drift, cinematic and calm",
    "gentle breathing motion in the scene, warm light pulse, barely perceptible movement, still and focused",
    "slow light shimmer on surfaces, slight depth-of-field breathing, peaceful cinematic mood",
    "soft environmental motion, leaves or curtains gently swaying, warm ambient light changes",
    "elegant slow zoom pull-back, inspirational mood, calm and confident energy",
    "peaceful scene with gentle light flicker, motivational and warm feeling, still cinematic",
]

# Voiceover: dialogue per scenario (speaker → edge-tts voice)
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


# ── Image upload ───────────────────────────────────────────────────────────────

def upload_image(filepath: Path) -> str:
    """Upload local image — tries multiple hosts in order."""
    import requests

    print(f"  Uploading {filepath.name}...")

    # Method 1: fal.ai storage (fastest, same provider)
    try:
        import fal_client
        url = fal_client.upload_file(str(filepath))
        print(f"  ✓ fal.ai: {url}")
        return url
    except Exception as e:
        print(f"  fal.ai upload failed ({e.__class__.__name__}), trying catbox...")

    # Method 2: litterbox.catbox.moe (72h)
    try:
        with open(filepath, "rb") as f:
            resp = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "72h"},
                files={"fileToUpload": (filepath.name, f, "image/jpeg")},
                timeout=30,
            )
        resp.raise_for_status()
        url = resp.text.strip()
        if url.startswith("http"):
            print(f"  ✓ catbox: {url}")
            return url
    except Exception as e:
        print(f"  catbox failed ({e.__class__.__name__}), trying tmpfiles...")

    # Method 3: tmpfiles.org (24h)
    with open(filepath, "rb") as f:
        resp = requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": (filepath.name, f, "image/jpeg")},
            timeout=30,
        )
    resp.raise_for_status()
    data = resp.json()
    url = data.get("data", {}).get("url", "").replace("tmpfiles.org/", "tmpfiles.org/dl/")
    if not url.startswith("http"):
        raise ValueError(f"tmpfiles upload failed: {data}")
    print(f"  ✓ tmpfiles: {url}")
    return url


# ── Wan 2.6 animation ─────────────────────────────────────────────────────────

def animate_slide(image_url: str, slide_idx: int, duration: int = 5) -> str:
    """Send image to Wan 2.6, return video URL."""
    import fal_client

    prompt = MOTION_PROMPTS[slide_idx % len(MOTION_PROMPTS)]
    cost = COST_PER_SEC * duration
    print(f"  Animating with Wan 2.6... (~${cost:.2f})")

    result = fal_client.subscribe(
        ENDPOINT,
        arguments={
            "image_url": image_url,
            "prompt": prompt,
            "negative_prompt": "text, letters, watermark, logo, blur, distortion, ugly, bad quality",
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


# ── Text overlay fix ──────────────────────────────────────────────────────────

def overlay_bubble(clip: Path, slide: Path, output: Path, bubble_frac: float = 0.42):
    """
    Re-overlay the bottom `bubble_frac` of the original slide onto the
    animated clip, fixing AI-distorted text in speech bubbles.
    """
    # Crop bottom portion of slide, scale to match clip dimensions, overlay
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(clip),
        "-i", str(slide),
        "-filter_complex", (
            f"[1:v]scale=iw:ih,"
            f"crop=iw:ih*{bubble_frac}:0:ih*(1-{bubble_frac})[bubble];"
            f"[0:v][bubble]overlay=0:H-h[v]"
        ),
        "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "20", "-preset", "fast",
        str(output)
    ], check=True, capture_output=True)


# ── Voiceover generation ──────────────────────────────────────────────────────

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
    """Generate TTS for each slide, pad to clip_duration, concat → voiceover.mp3."""
    try:
        import edge_tts
    except ImportError:
        print("pip3 install edge-tts")
        sys.exit(1)

    exchanges = SCENARIOS.get(scenario)
    if not exchanges:
        raise ValueError(f"Unknown scenario: {scenario}")

    print(f"\nGenerating voiceover for {scenario} ({len(exchanges)} lines)...")
    tts_dir = clips_dir / "_tts"
    tts_dir.mkdir(exist_ok=True)

    # Generate all TTS in parallel
    async def gen_all():
        tasks = []
        paths = []
        for i, (speaker, text) in enumerate(exchanges):
            voice = VOICES.get(speaker.lower(), "en-US-JennyNeural")
            path = tts_dir / f"line_{i:02d}.mp3"
            paths.append(path)
            tasks.append(_gen_tts(text, voice, path))
        await asyncio.gather(*tasks)
        return paths

    tts_files = asyncio.run(gen_all())

    # Pad each line to clip_duration seconds
    padded = []
    for i, (tf, (speaker, _)) in enumerate(zip(tts_files, exchanges)):
        dur = get_audio_duration(tf)
        pad = max(clip_duration - dur, 0.1)
        out = tts_dir / f"padded_{i:02d}.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(tf),
            "-af", f"apad=pad_dur={pad:.2f}",
            "-t", str(clip_duration),
            str(out)
        ], check=True, capture_output=True)
        padded.append(out)
        print(f"  [{i+1}] {speaker}: {dur:.1f}s → padded to {clip_duration}s")

    # Concatenate all padded audio
    list_file = tts_dir / "concat.txt"
    with open(list_file, "w") as f:
        for p in padded:
            f.write(f"file '{p.absolute()}'\n")

    vo_path = clips_dir / "voiceover.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(vo_path)
    ], check=True, capture_output=True)

    total = clip_duration * len(exchanges)
    print(f"  ✓ voiceover.mp3 ({total}s total)")
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

def run(slides_dir: Path, output: Path, duration: int = 5,
        audio: Path | None = None, scenario: str | None = None):
    if not FAL_KEY:
        print("ERROR: FAL_KEY not set in .env")
        sys.exit(1)

    os.environ["FAL_KEY"] = FAL_KEY

    slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not slides:
        print(f"ERROR: No slide_*.jpg in {slides_dir}")
        sys.exit(1)

    n = len(slides)
    total_cost = COST_PER_SEC * duration * n
    print(f"\nWan 2.6 Video Generator")
    print(f"  Slides: {n} × {duration}s = {n*duration}s")
    print(f"  Estimated cost: ${total_cost:.2f}")
    print(f"  Output: {output}\n")

    output.parent.mkdir(parents=True, exist_ok=True)
    clips_dir = output.parent / "_wan_clips"
    clips_dir.mkdir(exist_ok=True)

    # Step 1: Animate each slide + overlay speech bubble
    fixed_clips = []
    for i, slide in enumerate(slides):
        raw_clip = clips_dir / f"clip_{i:02d}_raw.mp4"
        fixed_clip = clips_dir / f"clip_{i:02d}.mp4"

        if fixed_clip.exists() and fixed_clip.stat().st_size > 10000:
            print(f"[{i+1}/{n}] {slide.name} — skipping (clip exists)")
            fixed_clips.append(fixed_clip)
            continue

        print(f"[{i+1}/{n}] {slide.name}")
        image_url = upload_image(slide)
        video_url = animate_slide(image_url, i, duration)
        download_clip(video_url, raw_clip)

        print(f"  Overlaying speech bubble (fixing text)...")
        overlay_bubble(raw_clip, slide, fixed_clip)
        raw_clip.unlink(missing_ok=True)
        fixed_clips.append(fixed_clip)
        print(f"  ✓ clip done")
        time.sleep(1)

    # Step 2: Generate voiceover if scenario given
    if scenario and not audio:
        audio = generate_voiceover(scenario, clips_dir, duration)

    # Step 3: Concatenate + mix audio
    print(f"\nConcatenating {n} clips...")
    if audio and audio.exists():
        raw_video = clips_dir / "raw_video.mp4"
        concat_clips(fixed_clips, raw_video)
        mix_audio(raw_video, audio, output)
    else:
        concat_clips(fixed_clips, output)

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\n✅ {output} ({size_mb:.1f} MB)")
    print(f"   Upload: https://www.tiktok.com/tiktokstudio/upload")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides", required=True)
    parser.add_argument("--output")
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--audio", help="Existing voiceover mp3 (optional)")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()),
                        help="Auto-generate voiceover for this scenario")
    args = parser.parse_args()

    slides_dir = Path(args.slides)
    output = Path(args.output) if args.output else slides_dir / "final_wan.mp4"
    audio = Path(args.audio) if args.audio else None

    run(slides_dir, output, args.duration, audio, args.scenario)


if __name__ == "__main__":
    main()
