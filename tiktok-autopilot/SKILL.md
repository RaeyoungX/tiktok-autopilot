---
name: tiktok-autopilot
description: |
  Full-cycle TikTok photo-post (图文) marketing automation for product promotion.
  Trigger when user wants to: promote a product on TikTok, find viral content for their niche,
  generate TikTok posts, auto-publish to TikTok, or says "/tiktok-autopilot".
  Also triggers on: "help me grow on TikTok", "viral content for my product", "TikTok marketing".
  User only provides a product URL — the skill acts as CMO and autonomously decides all strategy.
  Handles the complete pipeline: product research → viral scraping → pattern deconstruction → content generation → auto-publish.
license: MIT
metadata:
  author: rae
  version: 1.1.0
---

# TikTok Autopilot

Full-cycle TikTok photo-post marketing automation. User provides a **product URL only** — you act as CMO and autonomously make all strategy decisions.

**Format: TikTok 图文 (Photo Posts)** — multi-image slides with captions. Simpler than video, still high-reach.

---

## Usage

```
/tiktok-autopilot <product-url>           # full run from URL
/tiktok-autopilot --profile <slug>        # skip Phase 1, use saved profile
/tiktok-autopilot --phase <1-5> <url>     # jump to a specific phase
```

---

## Phase 1: Product Intelligence (CMO Mode)

**Goal:** Autonomously research the product and build a complete marketing profile — no questions asked.

**You are the CMO. Make all decisions yourself.**

### Step 1: Detect URL type and fetch accordingly

**Detect which type of URL was given, then extract accordingly:**

#### Type A: App Store (apps.apple.com)
Use `WebFetch` on the URL. Key fields to extract:
- App name, subtitle (the one-liner under the name)
- Description (first 3 paragraphs = core positioning)
- Category + age rating
- Price / IAP model
- Rating + review count (social proof signal)
- "What's New" section (shows active development = trust)
- Top user reviews (verbatim pain language = gold for hooks)
- Screenshots descriptions (reveals core use cases)

#### Type B: Play Store (play.google.com/store/apps)
Use `WebFetch` on the URL. Key fields to extract:
- App name + short description
- Full description (first 200 words)
- Category, rating, install count ("10M+" = major social proof)
- Price model
- Recent reviews (especially 3-4 star = honest pain points)

> **Tip for both stores:** User reviews contain the exact language real users use to describe their pain — mine these aggressively for hook copy. "I used to..." and "Finally..." patterns are especially valuable.

#### Type C: Product website
Use `WebFetch` on the URL. Key fields to extract:
- Hero headline + subheadline
- Feature list
- Pricing page (if linked, fetch it too)
- Testimonials / press logos
- Target audience signals from copy tone

### Step 2: Autonomous strategy decisions
As CMO, decide and document:

| Decision | Your job |
|----------|---------|
| **Niche** | Primary + sub-niche (e.g., "productivity / focus tools") |
| **ICP** | Ideal customer profile — age range, lifestyle, pain state |
| **Positioning** | The single most compelling angle for TikTok (emotional, not feature-driven) |
| **Content tone** | e.g., "empathetic + aspirational", "direct + slightly edgy" |
| **Brand color** | Pick or extract a dark hex for image backgrounds |
| **5 content angles** | Pain Point, Education, Transformation, Comparison, List |
| **8-10 seed keywords** | TikTok search terms mixing problem + solution + audience language |
| **Hashtag sets** | Big / Medium / Small / Micro tiers (see `references/product-analysis.md`) |
| **Competitor signals** | Guess 2-3 likely competitor hashtags based on niche |

### Step 3: Present your decisions
Show a concise CMO brief — what you decided and why (1 sentence rationale each). Do NOT ask for approval — proceed immediately to Phase 2.

```
## CMO Brief: {Product Name}
- Niche: ...
- ICP: ...
- Positioning hook: "..." (the emotional angle that will drive content)
- Tone: ...
- Brand color: #...
- Top 3 seed keywords: ...
- Proceeding to viral scraping now →
```

Save profile to: `~/.claude/skills/tiktok-autopilot/profiles/{product-slug}.md`

See `references/product-analysis.md` for the full analysis framework.

---

## Phase 2: Viral Scraping (爆款抓取)

**Goal:** Find 15-30 high-performing TikTok posts across 3-5 keywords. Use the Apify scraper script — TikTok is a JS SPA and cannot be directly fetched.

### Run the scraper:
```bash
python3 ~/.claude/skills/tiktok-autopilot/scripts/scrape_tiktok.py \
  --product "{product-slug}" \
  --keywords "english speaking practice,speak english confidently,english freeze" \
  --limit 15 \
  --download 5
```

**What it does:**
1. Calls Apify `clockworks/free-tiktok-scraper` for each keyword
2. Returns: hook text, likes, comments, shares, plays, hashtags, author stats
3. Downloads top 5 videos with `yt-dlp` for visual analysis
4. Auto-classifies by content type (pain_point / education / comparison / transformation / list)
5. Saves to `~/.claude/tiktok-autopilot/{product-slug}/{YYYY-MM-DD}.json`

**Requires:** `APIFY_TOKEN` in `.env` (free tier: $5/month credits ≈ 500 posts)
Get token: https://console.apify.com → Settings → Integrations

**Output JSON structure per post:**
```json
{
  "keyword": "english speaking practice",
  "hook": "POV: you've studied English for 5 years but...",
  "likes": 284000,
  "comments": 1820,
  "shares": 9400,
  "plays": 2100000,
  "hashtags": ["english", "speakenglish", "fyp"],
  "content_type": "pain_point",
  "author_followers": 45000,
  "local_video": "/tmp/tiktok-{slug}/scrape/videos/xxx.mp4"
}
```

**Minimum target:** 15 posts across 3+ keywords before proceeding to Phase 3.

---

## Phase 3: Pattern Deconstruction (拆爆款)

**Goal:** Identify the viral formulas behind the scraped posts.

Analyze the JSON data from Phase 2 and extract:

### Hook Formula Analysis
Group hooks by structure. Common patterns (see `references/viral-patterns.md`):
- `POV: you finally discovered [solution]`
- `No one talks about [problem] but...`
- `I tried [product] for 30 days and...`
- `Stop doing [wrong thing] if you want [result]`
- `[Number] signs you need [product]`

### Content Structure Mapping
For each post type, note:
- Opening hook (text on slide 1)
- Slide 2-3: problem agitation or proof
- Slide 4-5: solution reveal
- Final slide: CTA (link in bio, comment, etc.)

### Hashtag Cluster Analysis
Identify the top 5 hashtags by frequency. Check which tier they fall into:
- **Big** (>1B views): reach
- **Medium** (100M-1B): discoverability
- **Small** (<100M): targeted niche

### Output: 5 Content Templates
Generate 5 fill-in-the-blank templates adapted to the product, e.g.:
```
Template A [Pain Point]:
Hook: "If you struggle with [pain], read this 👇"
Slide 2: "[stat or relatable scenario]"
Slide 3: "Most people try [wrong solution] but it fails because..."
Slide 4: "[Product] works differently by [USP]"
Slide 5: "Try it risk-free → link in bio"
Caption: [Hook] + [1 sentence USP] + hashtags
```

---

## Phase 4: Content Generation (内容生成)

**Goal:** Produce 5 ready-to-post 图文 posts with images.

For each of the 5 templates, generate:

### Text Content
- **Slide texts** (1-2 punchy lines per slide, ≤80 chars each)
- **Caption** (hook + 1-2 sentences + hashtag block)
- **Hashtag set** (15-20 tags: mix big/medium/small from Phase 3)

### Image Generation
Run the image creation script:
```bash
python3 ~/.claude/skills/tiktok-autopilot/scripts/create_images.py \
  --product "{product-slug}" \
  --post-id "{post-01}" \
  --slides '["Slide 1 text", "Slide 2 text", ...]' \
  --color "{brand_color_hex or #1a1a2e}" \
  --output "/tmp/tiktok-{product-slug}/post-01/"
```

This creates `slide_1.jpg` through `slide_N.jpg` at 1080×1920px (TikTok portrait format).

After generating all 5 posts, display a summary table:
```
Post | Template     | Hook (preview)          | Slides | Output Dir
-----|-------------|-------------------------|--------|------------------
01   | Pain Point  | "If you struggle with..." | 5    | /tmp/tiktok-.../
...
```

Ask the user: "Publish as **photo post** (图文) or convert to **video** with Seedance 2.0?"

### Phase 4b: Video Generation (optional — Seedance 2.0)

If user chooses video, animate each slide into a cinematic clip then concat:

```bash
python3 ~/.claude/skills/tiktok-autopilot/scripts/create_video.py \
  --slides /tmp/tiktok-{slug}/post-01/ \
  --output /tmp/tiktok-{slug}/post-01/final.mp4 \
  --duration 5 \
  --quality fast \
  --context "English speaking practice app"
```

**What it does:**
1. Uploads each slide_*.jpg to 0x0.st (public URL)
2. Calls Seedance 2.0 (`bytedance/seedance-2.0/fast/image-to-video`) via fal.ai
3. Each slide → 5s cinematic clip with mood-matched motion prompt
4. ffmpeg concatenates all clips → `final.mp4` (1080×1920, TikTok-ready)

**Cost:** ~$0.24/s × 5s × 4 slides ≈ **$4.84 per post**
**Requires:** `FAL_KEY` in `.env` — get at https://fal.ai/dashboard/keys

**Advantage over photo post:**
- Upload via TikTok Studio web (no API approval wait)
- Add background music in TikTok app after upload
- Algorithm generally favors video over photo carousel

---

## Phase 5: Auto-Publish (自动发布)

**Goal:** Publish approved posts to TikTok via the official Content Posting API.

> **Note:** TikTok Studio web only supports video uploads. Photo/图文 posts require either the API or mobile app. Use Method A (API) for full automation.

See `references/tiktok-posting.md` for detailed instructions including mobile upload fallback.

### Method A: TikTok Content Posting API (Recommended — fully automated)

**One-time setup** (first product only):
1. Go to https://developers.tiktok.com/ → Create App → enable `video.publish` scope
2. Add `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` to `.env`
3. Run OAuth once: `python3 ~/.claude/skills/tiktok-autopilot/scripts/publish_tiktok.py --auth`
   - Opens browser for TikTok login → saves access token automatically

**Per post** (fully automated after setup):
```bash
python3 ~/.claude/skills/tiktok-autopilot/scripts/publish_tiktok.py \
  --slides /tmp/tiktok-{slug}/post-01/ \
  --caption "Your caption #hashtag1 #hashtag2"
```

**What it does under the hood:**
1. Uploads each slide_*.jpg to 0x0.st (temporary public host, no account needed)
2. Calls `POST /v2/post/publish/content/init/` with `media_type: PHOTO`
3. Post goes live immediately on your TikTok profile

**Batch all posts:**
```bash
for i in 01 02 03 04 05; do
  python3 ~/.claude/skills/tiktok-autopilot/scripts/publish_tiktok.py \
    --slides /tmp/tiktok-{slug}/post-${i}/ \
    --caption "$(cat /tmp/captions/post-${i}.txt)"
  sleep $((RANDOM % 60 + 45))  # 45-105s random wait
done
```

### Method B: Mobile Upload (No setup required)

AirDrop images to iPhone → TikTok app → + → Gallery → select slides in order → paste caption → Post.

See `references/tiktok-posting.md` for step-by-step.

**Error handling:**
- `401 Unauthorized`: token expired → run `--auth` again to refresh
- `400 photo_images invalid`: image URL not publicly accessible → retry upload
- App not approved: TikTok sandbox limits to private posts → request `video.publish` approval

---

## Data Persistence

| What | Where |
|------|-------|
| Product profiles | `~/.claude/skills/tiktok-autopilot/profiles/{slug}.md` |
| Scraped TikTok data | `~/.claude/tiktok-autopilot/{slug}/{date}.json` |
| Generated images | `/tmp/tiktok-{slug}/{post-id}/slide_N.jpg` |

---

## Reference Files

- `references/product-analysis.md` — Product classification & content angle framework
- `references/viral-patterns.md` — TikTok English viral hook & structure library
- `references/tiktok-posting.md` — Publishing guide (API method + mobile fallback)
- `scripts/scrape_tiktok.py` — Apify + yt-dlp viral post scraper (Phase 2)
- `scripts/create_images.py` — Imagen 4 + PIL slide generator (Phase 4)
- `scripts/create_video.py` — Seedance 2.0 image-to-video animator (Phase 4b)
- `scripts/publish_tiktok.py` — TikTok Content Posting API publisher (Phase 5)
