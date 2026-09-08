---
name: youtube-content-strategist
description: "Create a data-driven YouTube content strategy and 30-day content calendar using YouTube Data API v3. Analyzes your channel's performance, cross-references with niche data, identifies content pillars, evaluates Shorts vs long-form split, determines optimal duration and schedule, and finds sequel opportunities. Use when users want to (1) Plan their next 30 days of content, (2) Get a data-backed content calendar, (3) Optimize their content mix, (4) Identify sequel and follow-up opportunities, (5) Compare their strategy against niche benchmarks, (6) Find their best-performing content pillars. Requires user's YouTube Data API v3 key."
---

# YouTube Content Strategist

Create a data-driven 30-day content calendar by analyzing your channel + niche benchmarks.

## Usage

```
/youtube-content-strategist @MyChannel --niche "productivity"
/youtube-content-strategist @MyChannel --niche "cooking recipes" --uploads-per-week 3
/youtube-content-strategist UCxxxxxxx --niche "fitness"
```

## Instructions

### Step 1: Parse Arguments

- **Channel** (required): `@handle`, URL, or channel ID
- **--niche "keyword"** (required): the niche/topic area
- **--uploads-per-week N** (optional): target upload frequency (default: auto-detect from history)
- **--max-videos N** (optional): how many recent uploads to analyze (default: 200)

### Step 2: Get the API Key

Check Claude memory for a YouTube Data API v3 key. If not found, ask:
> "I need a YouTube Data API v3 key. You can get one from the Google Cloud Console. Please paste your key."

### Step 3: Run the Bundled Script

Run `scripts/analyze_strategy.py` — resolve the path relative to this skill's own directory:

```bash
YT_API_KEY=API_KEY python3 <skill-dir>/scripts/analyze_strategy.py "@CHANNEL" --niche "NICHE" [--uploads-per-week N]
```

Dependency: `pip3 install google-api-python-client`.

The script resolves the channel with `channels.list` (1 unit), pages the uploads
playlist, classifies every video into a content type and duration bucket, measures
Shorts vs long-form performance, derives the upload cadence and preferred days/hours,
finds sequel candidates (2x average views and older than 60 days), samples the niche
for benchmarks, and lists the channel's playlists.

### Step 4: Read the Data

```
reports/data/content-strategy-<channel-slug>-<YYYY-MM-DD>.json
```

### Step 5: Write the Strategy Report

Write to the path the script printed:

```
reports/content-strategy-<channel-slug>-<YYYY-MM-DD>.md
```

```markdown
# Content Strategy: [Channel Name]
*Niche: [Niche] | Analyzed [date] | [N] videos analyzed*

## Channel Position Assessment
Where does this channel stand? Subscribers, total views, video count.
How does it compare to niche benchmarks?

## Content Mix Analysis
### Current Mix
| Content Type | Count | % | Avg Views | Avg Engagement |
|-------------|-------|---|-----------|----------------|
What's working best? What's underperforming?

### Optimal Mix Recommendation
Based on performance data, recommend shifting the mix.

## Shorts vs Long-Form Strategy
| Metric | Shorts | Long-Form |
|--------|--------|-----------|
Which is performing better for this channel?
Recommendation on Shorts strategy.

## Optimal Video Duration
| Duration Bucket | Count | Avg Views |
|----------------|-------|-----------|
What duration sweet spot should this channel target?

## Upload Schedule
| Metric | Current | Recommended |
|--------|---------|-------------|
Best days and times based on historical data.
Upload frequency recommendation with reasoning.

## Content Pillars (Ranked by Impact)
For each content pillar:
- Performance metrics
- Strategic role (growth, engagement, authority, etc.)
- Recommendation (double down / maintain / reduce / try)

## Sequel & Follow-Up Opportunities
Videos that outperformed and deserve sequels.
| Original Video | Views | Age | Suggested Follow-Up |
|---------------|-------|-----|---------------------|

## Playlist Strategy
Current playlists and their sizes.
Recommendations for new playlists or series.

## 30-Day Content Calendar
Generate a concrete calendar:
| Week | Day | Video Title Idea | Type | Duration | Rationale |
|------|-----|------------------|------|----------|-----------|
| 1 | Mon | ... | tutorial | 12 min | Top-performing format |
| 1 | Thu | ... | tips | 8 min | High engagement topic |
...

Base every recommendation on actual data from the analysis.

## Growth Levers (Ranked by Impact)
1. **[Lever]** - Data backing - Expected impact
2. **[Lever]** - Data backing - Expected impact
...

## Quota Usage
| Operation | Calls | Units |
|-----------|-------|-------|
Use the `quota_used.breakdown` block from the JSON.
```

### Step 6: Report Completion

Tell the user the report path, the channel position summary, the top content pillar
finding, the upload schedule recommendation, a 30-day calendar overview, and the quota consumed.

## Quota Estimate

Only the niche benchmark needs `search.list`; everything about the user's own channel
goes through `channels.list` + `playlistItems.list`.

| Operation | Calls | Units |
|-----------|-------|-------|
| `channels.list` (resolve handle/ID/URL) | 1 | 1 |
| `playlistItems.list` (200 uploads) | 4 | 4 |
| `videos.list` (200 videos, batches of 50) | 4 | 4 |
| `search.list` (niche benchmark) | 1 | 100 |
| `videos.list` (benchmark details) | 1 | 1 |
| `playlists.list` | 1 | 1 |
| **Total** | | **~111** |

Resolving an `@handle` previously fell back to `search.list` (100 units) when the
first lookup missed; `forHandle`/`forUsername` now handles every input form for 1 unit.
Daily default allowance is 10,000 units, resetting at midnight Pacific Time.
