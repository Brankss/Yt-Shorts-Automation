---
name: youtube-title-tag-optimizer
description: "Optimize YouTube video titles, tags, and descriptions before publishing using YouTube Data API v3. Analyze top-ranking videos for a keyword to reverse-engineer winning title patterns, extract effective tags, and generate optimized title variations. Use when users want to (1) Optimize a video title before publishing, (2) Find the best tags for a video, (3) Analyze what title patterns work for a keyword, (4) Score an existing title against competitors, (5) Build an optimized tag set, (6) Get description SEO templates. Requires user's YouTube Data API v3 key."
---

# YouTube Title & Tag Optimizer

Optimize your video title, tags, and description before publishing by analyzing what works for top-ranking videos.

## Usage

```
/youtube-title-tag-optimizer "air fryer recipes"
/youtube-title-tag-optimizer "Python tutorial" --my-title "Learn Python in 10 Minutes"
/youtube-title-tag-optimizer --keyword "home workout" --my-title "Best Home Workout for Beginners 2024"
```

## Instructions

### Step 1: Parse Arguments

- **Keyword** (required): the topic/keyword to optimize for
- **--my-title "..."** (optional): the user's working title to score and improve

### Step 2: Get the API Key

Check the user's Claude memory for a YouTube Data API v3 key. If not found, ask:
> "I need a YouTube Data API v3 key to analyze ranking videos. You can get one from the Google Cloud Console. Please paste your key."

### Step 3: Run the Bundled Script

Run `scripts/optimize_title_tags.py` — resolve the path relative to this skill's own directory:

```bash
YT_API_KEY=API_KEY python3 <skill-dir>/scripts/optimize_title_tags.py "KEYWORD" [--my-title "User Title"]
```

Dependency: `pip3 install google-api-python-client`.

The script pulls the top 50 by relevance and top 50 by views, analyzes every title
for length, formatting elements, power words and structures, aggregates tag usage,
and — when `--my-title` is given — scores it out of 100 with itemized feedback.

### Step 4: Read the Data

```
reports/data/title-tag-<keyword-slug>-<YYYY-MM-DD>.json
```

### Step 5: Write the Report

Write to the path the script printed:

```
reports/title-tag-<keyword-slug>-<YYYY-MM-DD>.md
```

```markdown
# Title & Tag Optimization: [Keyword]
*Analyzed [date] | [N] videos*

## Your Title Score (if provided)
**Score: [X]/100**
| Criterion | Status |
|-----------|--------|
[Feedback items as table rows]

### Improved Title Suggestions
Generate 5-10 optimized title variations based on:
- Top-performing patterns from the data
- Power words that work in this niche
- Optimal length (40-70 chars)
- Keyword placement (front-loaded)

## Keyword Analysis
| Metric | Value |
|--------|-------|
| Videos Analyzed | |
| Avg Title Length | chars / words |
| Avg Tags per Video | |

## Top-Performing Titles
| # | Title | Views | Engagement | Key Patterns |
|---|-------|-------|------------|--------------|
[Top 10 titles with analysis]

## Title Pattern Analysis
### What Works for "[Keyword]"

**Title Structures:**
| Structure | Usage % | Avg Views |
|-----------|---------|-----------|
Use `aggregate_title_analysis.structures` and `structure_avg_views`.

**Power Words:**
| Category | Usage % | Top Words |
|----------|---------|-----------|

**Formatting Elements:**
| Element | Usage % | Impact |
|---------|---------|--------|
[numbers, brackets, caps, emoji, year, etc.]

### Winning Title Formulas
Based on top performers, these formulas work best for this keyword:
1. [Formula 1 with example]
2. [Formula 2 with example]
3. [Formula 3 with example]

## Optimized Tag Set
Ordered by priority:

### Primary Tags (use these first)
[Top 10 most-used tags]

### Secondary Tags
[Next 10 tags]

### Long-tail Tags
[Suggested long-tail variations]

### Recommended Tag Set (copy-paste ready)
[Comma-separated complete tag set optimized for the keyword]

## Description SEO Template
Based on top performers' first lines:
```
[Template with placeholders]
```

### Top Description First Lines
| Video | First Line |
|-------|------------|

## Hashtag Recommendations
Top hashtags to use based on video data.

## Quick-Reference Checklist
- [ ] Title is 40-70 characters
- [ ] Keyword appears in first 5 words
- [ ] Contains a number or power word
- [ ] Uses proven structure (how-to/listicle/question)
- [ ] Tags include primary + secondary + long-tail
- [ ] Description first line contains keyword

## Quota Usage
| Operation | Calls | Units |
|-----------|-------|-------|
Use the `quota_used.breakdown` block from the JSON.
```

### Step 6: Report Completion

Tell the user the report path, the title score (if provided), the top 3 recommended
title variations, the tag count extracted, and the quota used.

## Quota Estimate

Reverse-engineering what ranks for a keyword requires `search.list`, so it stays.

| Operation | Calls | Units |
|-----------|-------|-------|
| `search.list` (relevance + viewCount) | 2 | 200 |
| `videos.list` (batches of 50) | ~2 | ~2 |
| **Total** | | **~202** |

Daily default allowance is 10,000 units, resetting at midnight Pacific Time.
