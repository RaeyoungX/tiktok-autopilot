# TikTok Autopilot

A Claude Code skill for full-cycle TikTok 图文 (photo carousel) marketing automation. Give it a product URL — it acts as your CMO and handles everything.

```
/tiktok-autopilot https://apps.apple.com/app/your-product
```

**What it does automatically:**
1. Researches your product from App Store / Play Store / website
2. Scrapes 15–30 viral TikTok posts in your niche (via Apify)
3. Deconstructs viral patterns → 5 content templates
4. Generates cinematic slide images with Imagen 4 + text overlay
5. Publishes to TikTok via Content Posting API

---

## Pipeline

```
Product URL
  │ WebFetch
  ▼
Phase 1 — Product Intelligence (CMO mode)
  Extracts: positioning, ICP, brand color, keywords, hashtag strategy
  Saves to: profiles/{slug}.md
  │
  ▼
Phase 2 — Viral Scraping
  Tool: Apify clockworks/free-tiktok-scraper + yt-dlp
  Output: ~/.claude/tiktok-autopilot/{slug}/{date}.json
  Fields: hook, likes, comments, shares, plays, hashtags, content_type
  │
  ▼
Phase 3 — Pattern Deconstruction
  Claude analyzes JSON → extracts hook formulas, slide structures, hashtag clusters
  Output: 5 fill-in-the-blank content templates
  │
  ▼
Phase 4 — Content Generation
  Imagen 4 generates cinematic 9:16 backgrounds (one per slide, mood-matched)
  PIL overlays text + dark vignette + brand color bar + CTA button
  Output: /tmp/tiktok-{slug}/post-0N/slide_01~05.jpg (1080×1920px)
  │
  ▼
Phase 5 — Auto-Publish
  Method A: TikTok Content Posting API (fully automated)
    → uploads slides to temp host → calls /v2/post/publish/content/init/
  Method B: AirDrop to iPhone → TikTok app (zero setup)
```

---

## Setup

### 1. Install as a Claude Code skill

```bash
git clone https://github.com/yourusername/tiktok-autopilot ~/.claude/skills/tiktok-autopilot
cd ~/.claude/skills/tiktok-autopilot
cp .env.example .env
pip3 install Pillow google-genai apify-client yt-dlp tiktok-api-client python-dotenv requests
```

### 2. Configure API keys in `.env`

| Key | Required for | Get it |
|-----|-------------|--------|
| `GEMINI_API_KEY` | Image generation (Phase 4) | [aistudio.google.com](https://aistudio.google.com/apikey) — free |
| `APIFY_TOKEN` | TikTok scraping (Phase 2) | [console.apify.com](https://console.apify.com) — free tier |
| `TIKTOK_CLIENT_KEY` + `SECRET` | Auto-publishing (Phase 5) | [developers.tiktok.com](https://developers.tiktok.com) — free, needs app review |

**Missing a key?** Each phase degrades gracefully — images fall back to gradients, scraping falls back to Claude's knowledge base, publishing falls back to mobile upload instructions.

### 3. One-time TikTok OAuth (for Phase 5 API publishing)

```bash
python3 scripts/publish_tiktok.py --auth
# Opens browser → log in → token saved automatically
```

---

## Usage

```
# Full pipeline from URL
/tiktok-autopilot https://apps.apple.com/ca/app/lingomock/id6760037363

# Use existing profile (skip Phase 1)
/tiktok-autopilot --profile lingomock

# Jump to a specific phase
/tiktok-autopilot --phase 4 lingomock
```

Also triggers on: `"help me promote on TikTok"`, `"viral content for my product"`, `"TikTok marketing"`

---

## Scripts

### `scripts/scrape_tiktok.py`

```bash
python3 scripts/scrape_tiktok.py \
  --product lingomock \
  --keywords "english speaking practice,speak english confidently,english freeze" \
  --limit 15 \
  --download 5   # download top 5 videos with yt-dlp for visual reference
```

Output JSON per post:
```json
{
  "keyword": "english speaking practice",
  "hook": "POV: you studied English for 5 years but...",
  "likes": 284000,
  "comments": 1820,
  "hashtags": ["english", "speakenglish", "fyp"],
  "content_type": "pain_point",
  "local_video": "/tmp/tiktok-lingomock/scrape/videos/xxx.mp4"
}
```

### `scripts/create_images.py`

```bash
python3 scripts/create_images.py \
  --product lingomock \
  --post-id post-01 \
  --slides '["You studied English for years...", "Then someone says: Tell me about yourself", "Your mind goes blank.", "LingoMock — real scenario AI practice. Free."]' \
  --color "#2D1B69" \
  --output "/tmp/tiktok-lingomock/post-01/"
```

Each slide: Imagen 4 generates a mood-matched cinematic background → PIL overlays text with shadow, dark vignette, brand accent bar, and CTA button on final slide.

### `scripts/publish_tiktok.py`

```bash
# OAuth setup (once)
python3 scripts/publish_tiktok.py --auth

# Publish a post
python3 scripts/publish_tiktok.py \
  --slides /tmp/tiktok-lingomock/post-01/ \
  --caption "You studied English for years... #english #lingomock #fyp"

# Batch publish all posts with random delay
for i in 01 02 03 04 05; do
  python3 scripts/publish_tiktok.py \
    --slides /tmp/tiktok-lingomock/post-${i}/ \
    --caption "$(cat /tmp/captions/post-${i}.txt)"
  sleep $((RANDOM % 60 + 45))
done
```

---

## File Structure

```
tiktok-autopilot/
├── SKILL.md                    # Claude skill definition (all phases)
├── .env.example                # API key template
├── scripts/
│   ├── scrape_tiktok.py        # Phase 2: Apify + yt-dlp scraper
│   ├── create_images.py        # Phase 4: Imagen 4 + PIL image generator
│   └── publish_tiktok.py       # Phase 5: TikTok API publisher
├── references/
│   ├── product-analysis.md     # Product classification & content angle framework
│   ├── viral-patterns.md       # TikTok English viral hook formula library
│   └── tiktok-posting.md       # Publishing guide (API + mobile fallback)
└── profiles/
    └── example.md              # Example product profile (SleepDrift)
```

---

## Publishing: Two Methods

### Method A: TikTok Content Posting API (automated)

> Note: TikTok Studio web only supports video. Photo/图文 posts require the API or mobile.

The script uploads images to [0x0.st](https://0x0.st) (no-account temp host) to get public URLs, then calls the TikTok Content Posting API. Requires app review for `video.publish` scope (~2 weeks).

### Method B: AirDrop to iPhone (zero setup, works today)

```
Finder → select slide_*.jpg → right-click → Share → AirDrop → iPhone
TikTok app → + → Gallery → tap slides in order → paste caption → Post
```

Add trending music in the app for better reach (API doesn't support audio).

---

## Known Limitations

| Issue | Status |
|-------|--------|
| Emoji renders as □ in images (system font limitation) | Open |
| TikTok API requires app review before public posting | Working around with mobile upload |
| Imagen 4 occasionally generates backgrounds with text | Retry resolves it |
| TikTok API doesn't support adding background music | Add manually in app after posting |

---

## Tech Stack

- **Claude Code** — orchestration, CMO strategy decisions
- **Google Imagen 4** (`imagen-4.0-generate-001`) — cinematic background generation
- **Pillow (PIL)** — text overlay, vignette, brand styling
- **Apify** (`clockworks/free-tiktok-scraper`) — TikTok data extraction
- **yt-dlp** — video download for visual reference
- **TikTok Content Posting API v2** — photo post publishing
- **0x0.st** — zero-config temporary image hosting

---

## License

MIT
