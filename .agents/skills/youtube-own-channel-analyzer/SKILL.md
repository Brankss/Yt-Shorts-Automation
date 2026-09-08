---
name: youtube-own-channel-analyzer
description: "Comprehensive YouTube channel analysis using YouTube Data API v3. Analyze your own channel's performance metrics, content strategy, upload patterns, engagement rates, video performance, and growth trends. Use when users want to (1) Analyze their YouTube channel performance, (2) Get insights on video engagement and metrics, (3) Understand upload patterns and optimal posting times, (4) Identify top-performing content types, (5) Generate channel health reports, (6) Track subscriber and view growth patterns. Requires user's YouTube Data API v3 key."
---

# YouTube Own Channel Analyzer

Analyze your YouTube channel's performance using the YouTube Data API v3.

## Usage

```
/youtube-own-channel-analyzer @MyChannel
/youtube-own-channel-analyzer https://youtube.com/@MyChannel
/youtube-own-channel-analyzer UCxxxxxxxxxxxxxxxxxxxxxx --max-videos 300
```

## Instructions

### Step 1: Parse Arguments

- **Channel** (required): `@handle`, channel URL, or channel ID (`UC...`)
- **--max-videos N** (optional): how many recent uploads to analyze (default: 200, `0` = all)

### Step 2: Get the API Key

Get a key from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
with YouTube Data API v3 enabled. Check Claude memory first; if not found, ask the user to paste it.

### Step 3: Run the Bundled Script

Run `scripts/analyze_channel.py` — resolve the path relative to this skill's own directory:

```bash
YT_API_KEY=API_KEY python3 <skill-dir>/scripts/analyze_channel.py "@CHANNEL" [--max-videos N]
```

Dependency: `pip3 install google-api-python-client`.

### Step 4: Read the Data

```
reports/data/channel-analysis-<channel-slug>-<YYYY-MM-DD>.json
```

### Step 5: Write the Report

Write to the path the script printed: `reports/channel-analysis-<channel-slug>-<YYYY-MM-DD>.md`

## What the Script Computes

### Channel Resolution
`@handle` → `channels.list(forHandle=...)`; `/channel/UC...` and bare `UC...` → `channels.list(id=...)`;
legacy `/user/name` → `forUsername`. Never `search.list`.

### Video Collection
`contentDetails.relatedPlaylists.uploads` → `playlistItems.list` pagination → `videos.list` in batches of 50.

### Content Types
Categorized by title/description/tag patterns:

| Type | Pattern |
|------|---------|
| Tutorial | tutorial, how to, guide, learn |
| Review | review, unbox, first look, comparison |
| Vlog | vlog, day in, life, daily |
| Educational | explain, education, lesson |
| Gaming | gameplay, game, gaming, stream |
| Music | music, song, cover, lyrics |
| Other | no match |

### Duration Buckets
Short (<5 min), Medium (5-15 min), Long (15-30 min), Very Long (30+ min).

### Performance Metrics vs Benchmarks

| Metric | Formula | Benchmark |
|--------|---------|-----------|
| View-to-sub ratio | views / subscribers | 10-20% |
| Engagement rate | (likes + comments) / views | 1-5% |
| Like rate | likes / views | 3-7% |
| Comment rate | comments / views | 0.5-2% |
| Viral threshold | views > 5x subscribers | flagged per video |
| Underperforming | views < 10% of subscribers | flagged per video |

The benchmarks ship inside the JSON as `benchmarks` so the report can compare directly.

### Upload Patterns
Day-of-week and hour-of-day distribution, average days between uploads, uploads per
week, and a consistency score (population stddev of the gaps — lower is more consistent).

### Title Analysis
Rates of numbers, emojis, questions, brackets, ALL-CAPS words, and "how to"; average
title length in characters and words; the 20 most common non-stopword terms.

## Output Report Structure

```markdown
# Channel Analysis Report: [Channel Name]
*Analyzed [date] | [N] videos*

## Executive Summary
- Subscribers, total views, videos, avg engagement, upload consistency
- One-line health verdict

## Channel Overview
- Basic info, statistics table, description, keywords, country, created date

## Content Analysis
- Category breakdown table (count, %, avg views, avg engagement)
- Duration distribution table
- Title patterns

## Performance Metrics
| Metric | This Channel | Benchmark | Verdict |
|--------|-------------|-----------|---------|
Compare each metric in `performance` against `benchmarks`.

## Upload Patterns
- Optimal day/hour, uploads per week, consistency stddev
- Day and hour distribution

## Engagement Analysis
- Top 5 high-engagement videos (`top_by_engagement`)
- Bottom 5 needing improvement (`needs_improvement`)
- Viral and underperforming counts

## Recommendations
- Content optimization, upload frequency, title suggestions
- Each recommendation tied to a specific number from the data

## Quota Usage
| Operation | Calls | Units |
|-----------|-------|-------|
Use the `quota_used.breakdown` block from the JSON.
```

### Step 6: Report Completion

Tell the user the report path, subscriber/view/video counts, the health verdict,
the top recommendation, and the quota consumed.

## Quota Estimate

No `search.list` at all — this skill only touches its own channel.

| Operation | Calls | Units |
|-----------|-------|-------|
| `channels.list` (resolve) | 1 | 1 |
| `playlistItems.list` (200 uploads) | 4 | 4 |
| `videos.list` (batches of 50) | 4 | 4 |
| **Total (200 videos)** | | **~9** |

Roughly 1 unit per 25 videos analyzed. The previously documented
`search.list(channelId=...)` route cost 100 units per 50 videos (~400 units for the
same 200 videos). Daily default allowance is 10,000 units, resetting at midnight Pacific Time.
