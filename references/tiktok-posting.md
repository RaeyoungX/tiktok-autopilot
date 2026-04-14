# TikTok Photo Post — Publishing Guide

> **IMPORTANT: TikTok 图文 (photo carousel) posts cannot be created via TikTok Studio web.**
> The web upload page (`tiktok.com/tiktokstudio/upload`) only accepts video files.
> Photo posts must be uploaded via the **TikTok mobile app**.

---

## Method A: Mobile Upload (Required for 图文)

### Prerequisites
- TikTok app installed on iPhone/Android
- Logged into TikTok on mobile
- Images saved to a location accessible from the phone

### Step 1: Transfer Images to Phone

**Via AirDrop (fastest, Mac → iPhone):**
```bash
# Open Finder to the post folder
open /tmp/tiktok-{PRODUCT_SLUG}/post-{POST_ID}/
```
Then select all slide_*.jpg files → right-click → Share → AirDrop → your iPhone.

**Via iCloud:**
```bash
# Copy to iCloud Drive
cp /tmp/tiktok-{PRODUCT_SLUG}/post-{POST_ID}/slide_*.jpg ~/Library/Mobile\ Documents/com~apple~CloudDocs/TikTok/
```
Access from iPhone: Files app → iCloud Drive → TikTok folder.

### Step 2: Create Photo Post on TikTok Mobile

1. Open TikTok app on iPhone
2. Tap **+** (center bottom)
3. Tap **Templates** or swipe to **Photo** tab (varies by app version)
   - If no Photo tab: tap the **Gallery** icon (bottom left of camera)
   - Select multiple images (tap in order: slide_01, 02, 03...)
4. Tap **Next**
5. Paste caption from the generated content
6. Add hashtags
7. Tap **Post**

---

## Method B: TikTok Studio Web (Video Only)

While 图文 isn't supported, you can convert slides to a slideshow video using ffmpeg, then upload via web.

### Convert slides to video:
```bash
# Install ffmpeg if needed: brew install ffmpeg
PRODUCT="lingomock"
POST="post-01"
DIR="/tmp/tiktok-${PRODUCT}/${POST}"

# Create 3-second-per-slide video with smooth transition
ffmpeg -framerate 1/3 \
  -pattern_type glob -i "${DIR}/slide_*.jpg" \
  -vf "scale=1080:1920,fps=30" \
  -c:v libx264 -pix_fmt yuv420p \
  "${DIR}/slideshow.mp4"

echo "Created: ${DIR}/slideshow.mp4"
```

Then upload `slideshow.mp4` via TikTok Studio web as a normal video.

### Web upload steps (for video):
1. Go to `https://www.tiktok.com/tiktokstudio/upload`
2. Click **选择视频** and select the generated slideshow.mp4
3. Add caption and hashtags
4. Click **发布**

---

## Generated Content Reference

### LingoMock — post-01-v2 (Pain Point)

**Images:** `/tmp/tiktok-lingomock/post-01-v2/slide_01.jpg` through `slide_04.jpg`

**Caption:**
```
You studied English for years. Then someone says "Tell me about yourself" and your mind goes blank.

This isn't about grammar. It's about never practicing real situations under pressure.

LingoMock fixes this — AI roleplay for job interviews, airports, small talk. Free.

🔗 Link in bio to try your first scenario

#english #learnEnglish #englishlearning #speakenglish #englishpractice #englishspeakingpractice #spokenenglish #englishtips #englishconversation #speakingconfidence #lingomock #AIenglish #fyp #learnontiktok #englishfluency
```

---

## Bulk Upload Helper Script

For publishing multiple posts via mobile, this script generates an AirDrop-ready summary:

```bash
#!/bin/bash
PRODUCT=$1  # e.g., "lingomock"
echo "=== TikTok 图文 Upload Checklist for ${PRODUCT} ==="
for post_dir in /tmp/tiktok-${PRODUCT}/*/; do
    post=$(basename "$post_dir")
    count=$(ls "$post_dir"slide_*.jpg 2>/dev/null | wc -l)
    echo ""
    echo "📱 ${post} — ${count} slides"
    echo "   Path: ${post_dir}"
    ls "$post_dir"slide_*.jpg 2>/dev/null | while read f; do echo "   → $(basename $f)"; done
done
echo ""
echo "To AirDrop: open /tmp/tiktok-${PRODUCT}/ in Finder, select files → Share → AirDrop"
```

Usage: `bash upload_helper.sh lingomock`

---

## TikTok Photo Post Limits (2024–2025)

| Limit | Value |
|-------|-------|
| Max images per post | 35 |
| Recommended | 3–8 (optimal engagement) |
| Image format | JPG, PNG |
| Max image size | 20MB per image |
| Caption length | Up to 2,200 characters |
| Max hashtags | 30 (use 15–20 for best reach) |
| Posts per day | No official limit; stay under 3–5 to avoid shadow-ban |

---

## Error Handling

| Issue | Cause | Fix |
|-------|-------|-----|
| Web upload only shows video | 图文 is mobile-only | Use Method A (AirDrop) |
| Photo tab missing in app | Older app version | Update TikTok app |
| Images out of order | Tap order matters | Tap slides in sequence 01→02→03 |
| Caption too long | >2200 chars | Shorten body text, keep hashtags |
| Post goes to drafts | Private account | Check account visibility settings |
