#!/usr/bin/env python3
"""
TikTok Autopilot — Voiceover Generator
Uses edge-tts (free, Microsoft) to generate dialogue audio for comic posts,
then ffmpeg merges audio + Ken Burns video into final TikTok MP4.

Usage:
    python3 create_voiceover.py \
        --slides /tmp/tiktok-lingomock/comic-01/ \
        --scenario job_interview \
        --output /tmp/tiktok-lingomock/comic-01/final.mp4

Cost: $0 (edge-tts is free)

Dependencies:
    pip3 install edge-tts
    brew install ffmpeg
"""

import argparse
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("pip3 install edge-tts")
    sys.exit(1)

# ── Voice assignments ──────────────────────────────────────────────────────
# Two voices per scenario: one for interviewer/staff/other, one for "You"
VOICES = {
    "interviewer": "en-US-GuyNeural",       # male, formal
    "staff":       "en-US-GuyNeural",
    "coworker":    "en-US-JennyNeural",     # female, friendly
    "agent":       "en-US-GuyNeural",
    "you":         "en-US-JennyNeural",     # learner voice
    "lingomock":   "en-US-AriaNeural",      # brand voice, warm
}

def get_voice(speaker: str) -> str:
    return VOICES.get(speaker.lower(), "en-US-JennyNeural")

# ── Dialogue definitions (mirrors create_comic.py) ─────────────────────────
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
}

# ── TTS generation ─────────────────────────────────────────────────────────

async def generate_line(text: str, voice: str, output: Path):
    comm = edge_tts.Communicate(text, voice=voice, rate="-5%")  # slightly slower = clearer
    await comm.save(str(output))

async def generate_all_audio(exchanges: list, tmp: Path) -> list[Path]:
    """Generate one mp3 per dialogue line."""
    audio_files = []
    tasks = []
    paths = []
    for i, (speaker, text) in enumerate(exchanges):
        voice = get_voice(speaker)
        path = tmp / f"line_{i:02d}.mp3"
        paths.append(path)
        tasks.append(generate_line(text, voice, path))

    await asyncio.gather(*tasks)
    return paths

def get_audio_duration(path: Path) -> float:
    """Get duration of an audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 4.0

# ── Video assembly ─────────────────────────────────────────────────────────

def build_video(slides: list[Path], audio_files: list[Path],
                output: Path, min_slide_duration: float = 3.5):
    """
    Build final video: each slide stays on screen while its audio plays,
    with Ken Burns zoom effect and fade transitions.
    """
    assert len(slides) == len(audio_files), "Slide/audio count mismatch"

    # Get durations for each audio line (slide stays for audio + 0.5s buffer)
    durations = []
    for af in audio_files:
        d = get_audio_duration(af)
        durations.append(max(d + 0.5, min_slide_duration))

    print(f"  Slide durations: {[f'{d:.1f}s' for d in durations]}")
    print(f"  Total video length: {sum(durations):.1f}s")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # Step 1: Generate Ken Burns clip per slide
        slide_clips = []
        for i, (slide, dur) in enumerate(zip(slides, durations)):
            clip = tmp / f"clip_{i:02d}.mp4"
            frames = int(dur * 30)
            zoom_speed = 0.0006
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-t", str(dur), "-i", str(slide),
                "-vf", (
                    f"scale=1080:1920,"
                    f"zoompan=z='min(zoom+{zoom_speed},1.06)':d={frames}:"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920,"
                    f"fps=30,"
                    f"fade=t=in:st=0:d=0.3,"
                    f"fade=t=out:st={dur-0.4:.2f}:d=0.4"
                ),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-b:v", "4000k",
                "-an", str(clip)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            slide_clips.append(clip)
            print(f"  ✓ clip_{i+1:02d}.mp4 ({dur:.1f}s)")

        # Step 2: Concatenate video clips
        concat_list = tmp / "concat.txt"
        with open(concat_list, "w") as f:
            for clip in slide_clips:
                f.write(f"file '{clip}'\n")

        video_only = tmp / "video_only.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy", str(video_only)
        ], capture_output=True, check=True)

        # Step 3: Concatenate audio files (with silence padding between lines)
        audio_list = tmp / "audio_concat.txt"
        padded_audios = []
        for i, (af, dur) in enumerate(zip(audio_files, durations)):
            # Pad audio to match slide duration
            padded = tmp / f"padded_{i:02d}.mp3"
            audio_dur = get_audio_duration(af)
            pad = dur - audio_dur
            cmd = [
                "ffmpeg", "-y", "-i", str(af),
                "-af", f"apad=pad_dur={max(pad, 0):.2f}",
                "-t", str(dur),
                str(padded)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            padded_audios.append(padded)

        with open(audio_list, "w") as f:
            for pa in padded_audios:
                f.write(f"file '{pa}'\n")

        audio_only = tmp / "audio_only.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(audio_list),
            "-c", "copy", str(audio_only)
        ], capture_output=True, check=True)

        # Step 4: Merge video + audio
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(video_only),
            "-i", str(audio_only),
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            "-movflags", "+faststart",
            str(output)
        ], capture_output=True, check=True)

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\n✅ Final video: {output} ({size_mb:.1f} MB)")
    print(f"   Upload: https://www.tiktok.com/tiktokstudio/upload")

# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides", required=True, help="Directory with slide_*.jpg")
    parser.add_argument("--scenario", required=True, choices=list(SCENARIOS.keys()))
    parser.add_argument("--output", help="Output MP4 path")
    args = parser.parse_args()

    slides_dir = Path(args.slides)
    slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not slides:
        print(f"ERROR: No slide_*.jpg in {slides_dir}")
        sys.exit(1)

    exchanges = SCENARIOS[args.scenario]
    output = Path(args.output) if args.output else slides_dir / "final.mp4"

    print(f"\nVoiceover Generator (edge-tts, free)")
    print(f"  Scenario: {args.scenario}")
    print(f"  Slides: {len(slides)}")
    print(f"  Lines: {len(exchanges)}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        print("\nGenerating TTS audio (all lines in parallel)...")
        audio_files = asyncio.run(generate_all_audio(exchanges, tmp))
        for i, (af, (speaker, text)) in enumerate(zip(audio_files, exchanges)):
            d = get_audio_duration(af)
            print(f"  [{i+1}] {speaker}: {text[:40]}... ({d:.1f}s)")

        print("\nBuilding video with Ken Burns + voiceover...")
        build_video(slides, audio_files, output)


if __name__ == "__main__":
    main()
