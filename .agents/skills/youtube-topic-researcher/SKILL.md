---
name: youtube-topic-researcher
description: "Research any YouTube topic or niche using YouTube Data API v3. Analyze top-performing videos, find content gaps, identify outlier videos, assess niche saturation, and generate data-driven video ideas. Use when users want to (1) Research a topic before making videos, (2) Find content gaps in a niche, (3) Validate whether a niche is worth entering, (4) Discover what's working for a keyword, (5) Find underserved subtopics, (6) Get video ideas backed by data. Requires user's YouTube Data API v3 key."
---

# YouTube Topic Researcher

Research any topic or niche across YouTube to find what's working, identify content gaps, and generate data-driven video ideas.

## Usage

```
/youtube-topic-researcher air fryer recipes
/youtube-topic-researcher "Python automation"
/youtube-topic-researcher meditation for beginners
/youtube-topic-researcher --topic "home gym setup" --max-results 75
```

## Instructions

### Step 1: Parse Arguments

- **Topic/keyword** (required): the search term to research
- **--max-results N** (optional): videos per search ordering (default: 50, max: 100)

### Step 2: Get the API Key

Check the user's Claude memory for a YouTube Data API v3 key. If not found, ask:
> "I need a YouTube Data API v3 key to research this topic. You can get one from the Google Cloud Console. Please paste your key."

Export it as `YT_API_KEY` when running the script.

### Step 3: Run the Bundled Script

Run `scripts/research_topic.py` — resolve the path relative to this skill's own directory:

```bash
YT_API_KEY=API_KEY python3 <skill-dir>/scripts/research_topic.py "TOPIC" [--max-results N]
```

Dependency: `pip3 install google-api-python-client` (the script tells you if it's missing).

The script searches by relevance, view count, and date; batches video and channel
details; computes percentiles, format performance, title patterns, tag cloud,
outliers, and saturation signals; then writes the raw JSON and prints the exact
markdown path for the report.

### Step 4: Read the Data

Read the JSON the script wrote:

```
reports/data/topic-research-<topic-slug>-<YYYY-MM-DD>.json
```

### Step 5: Write the Report

Write the markdown report to the path the script printed:

```
reports/topic-research-<topic-slug>-<YYYY-MM-DD>.md
```

#### Report Structure

```markdown
# Topic Research: [Topic]
*Analyzed [date] | [N] videos across [N] channels*

## Executive Summary
- 3-4 bullet points: Is this niche worth entering? Key findings at a glance.
- Overall assessment: Saturated / Growing / Underserved / Emerging

## Market Overview
| Metric | Value |
|--------|-------|
| Videos Analyzed | |
| Total Views (sample) | |
| Average Views | |
| Median Views | |
| Avg Engagement Rate | |
| Unique Channels | |
| Avg Video Duration | |

## Performance Benchmarks
- What view count = "good" in this niche (use `view_percentiles`)
- 25th / 50th / 75th / 90th percentile views
- Engagement rate benchmarks

## Content Format Analysis
Table showing format breakdown (Short, Medium, Long-form, etc.) with avg views per format
(use `format_performance`). Which format performs best? Which is most common?

## Channel Landscape
- Channel size distribution (micro/small/medium/large)
- Top channels dominating the results
- Is this a "winner take all" niche or distributed?
- Opportunities for small channels

## Title Patterns That Work
- Data from `title_patterns`
- Most common words/phrases
- Title formulas used by top performers
- What distinguishes high-performing titles

## Tag Cloud & SEO
- Top tags used
- Tag clusters (groups of related tags)
- Missing tag opportunities

## Outlier Videos (Breakout Hits)
Table of outlier videos with views, channel size, outlier score.
What do these have in common? Why did they break out?

## Content Freshness
- Age distribution of top results
- Is YouTube favoring new or evergreen content for this topic?
- Recency signals

## Content Gaps & Opportunities
- Subtopics underrepresented in results
- Formats not being used effectively
- Angle/perspective gaps
- Audience segments not being served

## Video Ideas (Data-Backed)
3-5 specific video ideas with:
- Suggested title
- Why this would work (data backing)
- Target format and duration
- Key tags to use

## Saturation Assessment
- Competition density score (unique channels / total videos)
- Big channel dominance percentage
- Recent content velocity
- Final verdict: Is this niche worth entering?

## Quota Usage
| Operation | Calls | Units |
|-----------|-------|-------|
Use the `quota_used.breakdown` block from the JSON.
```

### Step 6: Report Completion

Tell the user the report path, the data path, the single most interesting insight,
the saturation verdict, the number of video ideas generated, and the quota consumed.

## Quota Estimate

Keyword search is the whole point of this skill, so `search.list` (100 units/call) stays.

| Operation | Calls | Units |
|-----------|-------|-------|
| `search.list` (relevance, viewCount, date) | 3 | 300 |
| `videos.list` (batches of 50) | ~3 | ~3 |
| `channels.list` (batches of 50) | ~2 | ~2 |
| **Total (default)** | | **~305** |

With `--max-results 100` each ordering paginates twice: **~507 units**.
Daily default allowance is 10,000 units, resetting at midnight Pacific Time.
