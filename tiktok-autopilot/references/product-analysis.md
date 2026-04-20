# Product Analysis Framework

Use this framework in **Phase 1** to transform a raw product description into a structured content strategy.

---

## Step 1: Niche Classification

Assign the product to one primary niche and one sub-niche:

| Niche | Sub-niches |
|-------|-----------|
| Health & Wellness | Sleep, Weight Loss, Fitness, Mental Health, Skincare, Supplements |
| Productivity | Study, Work-from-home, Time Management, Focus, Organization |
| Finance | Budgeting, Investing, Side Hustle, Debt, Frugal Living |
| Beauty | Makeup, Hair Care, Nail Art, Skincare Routines |
| Parenting | Baby Gear, Education, Toddler Hacks, Mom Life |
| Pet | Dogs, Cats, Training, Accessories |
| Tech & Gadgets | Smart Home, Phone Accessories, Gaming, Wearables |
| Food & Beverage | Recipes, Meal Prep, Specialty Diets, Snacks |
| Fashion | Outfit Ideas, Sustainable Fashion, Thrifting, Accessories |
| Home & Decor | Organization, Cleaning Hacks, Interior Design, DIY |
| Education | Language Learning, Skills, Certifications, Online Courses |
| Travel | Budget Travel, Packing, Destinations, Digital Nomad |

---

## Step 2: Content Angle Matrix

Generate one content idea per angle. These become the 5 post templates in Phase 3.

### Angle 1: Pain Point (Most Viral)
- Focus on the frustration before discovering the product
- Tone: empathetic, relatable
- Format: "If you [have this problem], you need to see this"
- Example hook: "Why do I wake up exhausted even after 8 hours of sleep? 😩"

### Angle 2: Education / Surprising Fact
- Teach something counterintuitive related to the problem
- Tone: authoritative, eye-opening
- Format: "Most people don't know that [insight]"
- Example hook: "The reason your skincare isn't working (it's not what you think)"

### Angle 3: Social Proof / Transformation
- Show results or simulate testimonial perspective
- Tone: inspiring, credible
- Format: "I tried X for [time period] and here's what happened"
- Example hook: "30 days of using this supplement changed everything"

### Angle 4: Comparison / Myth-busting
- Position against a common wrong approach
- Tone: direct, slightly contrarian
- Format: "[Common solution] vs [your solution]"
- Example hook: "Stop spending $200/month on [expensive alternative]"

### Angle 5: List / Tips
- Educational value, high save rate
- Tone: helpful, practical
- Format: "[N] things you didn't know about [problem/solution]"
- Example hook: "5 signs your [problem] is worse than you think"

---

## Step 3: Keyword Generation

Generate seed keywords for TikTok search in Phase 2.

**Formula:** Combine problem terms + solution terms + audience terms

**Example for a sleep supplement:**
- Problem: "can't sleep", "insomnia tips", "sleep problems", "tired all the time"
- Solution: "sleep supplement", "melatonin alternative", "natural sleep aid"
- Audience: "sleep hacks", "better sleep routine", "sleep hygiene"
- Competitor signal: "#sleeptok", "#sleepbetter", "#insomniarelief"

**Target: 8-10 seed keywords, mix long-tail and short-tail**

---

## Step 4: Hashtag Strategy (3-Tier System)

Build a set of 15-20 hashtags per post using this mix:

| Tier | View Range | Purpose | Count per post |
|------|-----------|---------|---------------|
| Big | >1B views | Maximum reach exposure | 2-3 tags |
| Medium | 100M–1B views | Discoverability in niche | 5-7 tags |
| Small | 10M–100M views | Targeted niche audience | 6-8 tags |
| Micro | <10M views | Deep niche, high relevance | 2-3 tags |

**Always include:**
- 1-2 generic big tags (`#foryou`, `#fyp`, `#viral`)
- Product category tag (`#sleeptok`, `#skincarecheck`, etc.)
- Problem-specific tags (`#insomnia`, `#cantfall asleep`, etc.)
- Solution tags (`#naturalremedies`, `#wellnesstips`, etc.)

---

## Profile File Format

Save to `~/.claude/skills/tiktok-autopilot/profiles/{slug}.md`:

```markdown
---
product: Product Name
slug: product-slug
updated: YYYY-MM-DD
market: en-US
brand_color: "#hexcode"
---

## Product
- **Name:** ...
- **Description:** ...
- **Problem solved:** ...
- **Target audience:** ...
- **Price:** ...
- **Purchase URL:** ...
- **USP:** ...

## Content Strategy
- **Niche:** Primary / Sub-niche
- **Content angles:** Pain Point, Education, Transformation, Comparison, List

## Keywords
- seed_keywords: [list]
- competitor_handles: [@handle1, @handle2]
- competitor_hashtags: [#tag1, #tag2]

## Hashtag Sets
### Big (use 2-3)
#fyp #foryou #viral

### Medium (use 5-7)
#[niche]tok #[problem] ...

### Small (use 6-8)
#[specific] #[longtail] ...
```
