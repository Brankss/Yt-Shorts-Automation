---
name: youtube-channel-breakdown
description: >-
  Comprehensive YouTube channel breakdown analysis pipeline for live stream shows.
  Runs data collection, analyzes all metrics, and writes expert analysis.
  Use when users want to (1) Do a full channel breakdown for a live stream,
  (2) Generate an expert-level channel analysis document,
  (3) Prepare channel research for a show or presentation.
  Accepts @handle, channel URL, or channel ID.
---

# YouTube Channel Breakdown Analysis

Comprehensive YouTube channel analysis pipeline for the Channel Breakdown Live Stream show. Runs the data collection pipeline, reads all collected data, and writes a single expert analysis document.

## Usage

```
/youtube-channel-breakdown @channelhandle
```

Examples:
- `/youtube-channel-breakdown @hubspotmarketing`
- `/youtube-channel-breakdown @aliabdaal`
- `/youtube-channel-breakdown @mkbhd`

## What This Skill Does

1. **Data Collection** - Runs the Python pipeline to fetch ALL videos from the channel
2. **Expert Analysis** - Reads all collected data and writes `channel_analysis.md`

The single deliverable is `channel_analysis.md` — a 4,000-5,000 word expert analysis written from the perspective of a YouTube strategist.

## External Dependency

Unlike the other YouTube skills, this one does **not** bundle its own collection script.
It drives the external **Channel_Breakdown_Live_Stream** pipeline
(`channel_research_pipeline.py`), which lives outside this repo.

The pipeline directory is read from the `CHANNEL_BREAKDOWN_PIPELINE_DIR` environment
variable, falling back to:

```
/Users/nikhilbhansali/Library/CloudStorage/Dropbox/Claude Projects/Onewrk Digital Marketing and content research/07_Documentation/Channel_Breakdown_Live_Stream/scripts
```

## Instructions

When the user invokes this skill with a channel handle:

### Step 1: Locate the Pipeline

```bash
PIPELINE_DIR="${CHANNEL_BREAKDOWN_PIPELINE_DIR:-/Users/nikhilbhansali/Library/CloudStorage/Dropbox/Claude Projects/Onewrk Digital Marketing and content research/07_Documentation/Channel_Breakdown_Live_Stream/scripts}"
test -f "$PIPELINE_DIR/channel_research_pipeline.py" && echo "FOUND: $PIPELINE_DIR" || echo "MISSING"
```

**If the pipeline is missing, stop and tell the user:**

> This skill depends on the external **Channel_Breakdown_Live_Stream** pipeline
> (`channel_research_pipeline.py`), which I can't find at
> `<the path that was checked>`. Where is that pipeline located? Once you tell me,
> I'll use it — or you can set `CHANNEL_BREAKDOWN_PIPELINE_DIR` to its directory so
> this skill finds it automatically next time.
>
> If you don't have that pipeline, use `youtube-own-channel-analyzer` (channel health),
> `youtube-competitor-analyzer` (competitive position), and `youtube-comment-miner`
> (audience analysis) instead — together they cover most of what this report needs.

Do not fabricate the analysis or substitute another data source without telling the user.

### Step 2: Run the Research Pipeline

```bash
cd "$PIPELINE_DIR"
python3 channel_research_pipeline.py --channel "@channelhandle"
```

Wait for completion (can take 2-5 minutes for large channels). Note the output folder path printed at the end.

### Step 3: Read All Data Files

Read these files from the output folder (`research_data/[ChannelName]_[date]/`):

1. `channel_metrics.json` - Basic channel stats
2. `analysis_summary.json` - Full analysis (content breakdown, top videos, upload consistency, title/SEO analysis, monetization, audience sentiment, growth trajectory, content formats, shorts patterns, live stream patterns, collaboration analysis, playlist strategy, description optimization, thumbnail patterns, creator background)
3. `competitors.json` - Discovered competitors with relevance scores and rankings
4. `verification.json` - Data validation results
5. `top_comments.json` - Top comments from top 3 videos
6. `top_videos.json` - Top 10 performing videos
7. `research_brief.md` - Markdown summary with content type tables
8. `company_intelligence.json` - Company news and context (if available)

Read ALL of these files. You need the complete data to write the analysis.

### Step 4: Write the Expert Analysis

Write `channel_analysis.md` in the same output folder. Follow the template and guidelines below exactly.

### Step 5: Report Completion

Tell the user:
- Output folder location
- Channel name, subscribers, total views, video count
- Data verification status
- A 2-3 sentence teaser of the most interesting finding
- Confirm `channel_analysis.md` has been written

---

## channel_analysis.md Template (16 Sections)

The document MUST follow this exact structure. Adapt section content based on available data — skip subsections where data doesn't exist (e.g., skip "Live Streaming" section if channel has no live streams), but always include all sections that have supporting data.

### Title Format
```
# [Channel Name]: A Strategic Analysis of [brief descriptor of what makes them notable]
```

### Section I: The Channel at a Glance

A comprehensive metrics table. Pull ALL values from `channel_metrics.json` and `analysis_summary.json`:

```markdown
| Metric | Value |
|--------|-------|
| Subscribers | [exact number, formatted with commas] |
| Total Views | [formatted] |
| Videos Published | [total] ([regular] regular, [shorts] shorts, [live] live) |
| Channel Created | [date] |
| Country | [country] |
| Average Views/Video | [calculated] |
| Engagement Rate | [from analysis] |
| Upload Frequency | [X videos per week/month] |
| Average Duration | [from analysis] |
| Estimated Monthly Views | [from analysis] |
| Views/Subscriber Ratio | [from analysis] |
| Channel Health | [score or assessment from analysis] |
```

Follow the table with 2-3 sentences contextualizing what these numbers mean relative to the niche.

### Section II: Who Is [Creator/Brand] and Why Does This Channel Exist

- Creator/company background and credentials
- Origin story — what existed before the YouTube channel
- The founding insight or market gap they identified
- What problem this channel solves for its audience
- Target audience and their pain points

Source: `analysis_summary.json` (creator_background), `company_intelligence.json`, channel description from `channel_metrics.json`.

### Section III: The Growth Story

This is the most important narrative section. Tell the story in phases:

- **The Launch**: First video details, early performance, initial strategy
- **Phase 1**: Early growth period, what formats they tried
- **Phase 2**: Strategic pivots, format evolution, what changed
- **Phase 3**: Format additions (Shorts, Live, etc.) and their impact
- **Phase 4**: Current state and business model
- **Growth Trajectory Today**: Recent performance vs historical (growing/stable/declining)
- **Evergreen Content**: Which old videos still get views and why

Source: `analysis_summary.json` (growth_trajectory, first_video, first_hit_video, format_evolution, evergreen_content, recent_vs_older).

### Section IV: Content Strategy — The Machine Behind [X] Videos

- Content mix breakdown: regular videos vs shorts vs live streams (exact counts and percentages)
- Content format analysis: tutorials, vlogs, interviews, etc. (with performance by format)
- Duration distribution and sweet spots
- Upload cadence: consistency score, average days between uploads, gaps/breaks
- Publishing patterns: preferred days, times
- Content repurposing signals (if detectable)

Source: `analysis_summary.json` (content_type_breakdown, content_formats, upload_consistency, duration_analysis).

### Section V: The Top 10 Videos — What Goes Viral

Include the top 10 table:

```markdown
| # | Title | Views | Engagement | Type | Duration |
|---|-------|-------|------------|------|----------|
```

Then analyze:
- Viral threshold (what view count = viral for this channel, typically 5x average)
- Common patterns across top performers (format, topic, hook style, duration)
- What the #1 video reveals about the algorithm's preference for this channel
- Collaboration effects on top videos (if any)

Source: `top_videos.json`, `analysis_summary.json` (performance_tiers, viral_threshold).

### Section VI: Shorts Strategy Deep Dive

- Total shorts count, total shorts views, average views per short
- Engagement rate comparison: shorts vs long-form
- Hook patterns analysis (questions, numbers, caps, "this", etc.)
- Top 5 shorts with views
- Strategic role: are shorts feeding the main channel or standalone?

Source: `analysis_summary.json` (shorts_patterns, content_type_breakdown.shorts).

*Skip this section if channel has fewer than 5 shorts.*

### Section VII: Live Streaming Analysis

- Total streams, average duration, average views
- Schedule patterns (day, time, frequency)
- Topic distribution across streams
- Top 5 streams with views
- Strategic function: community building, content generation, or both?

Source: `analysis_summary.json` (live_stream_patterns, content_type_breakdown.live_streams).

*Skip this section if channel has fewer than 3 live streams.*

### Section VIII: Title, SEO, and Description Patterns

**Title Analysis:**
- Average title length (chars and words)
- Power word usage breakdown (urgency, curiosity, value, emotional, fear — with percentages)
- Title structure patterns (how-to, lists, questions, vs/comparisons — with percentages)
- Most effective title formulas based on top performers

**Description Optimization:**
- Optimization score (0-100)
- Timestamps/chapters usage rate
- Hashtag strategy
- CTA presence and types
- Link density
- Specific gaps and opportunities

Source: `analysis_summary.json` (title_analysis, description_optimization).

### Section IX: Collaboration Strategy

- Total collaborations detected, collab rate percentage
- Performance comparison: collab videos vs solo (views, engagement)
- Most frequent collaborators (names if detectable)
- Strategic assessment: how collaborations serve growth

Source: `analysis_summary.json` (collaboration_analysis).

*Skip if collab rate is 0%.*

### Section X: Playlist Architecture

- Total playlists, average playlist size
- Largest/most important playlists
- Series or course detection
- How playlists serve the content strategy (binge-watching, onboarding, etc.)

Source: `analysis_summary.json` (playlist_strategy).

### Section XI: Audience and Comment Analysis

- Overall sentiment breakdown (positive/negative/neutral/questions)
- Top themes in comments (what viewers talk about most)
- Representative comments that reveal audience identity
- What comments reveal about the audience's relationship with the creator
- Creator's reply behavior and community culture

Source: `top_comments.json`, `analysis_summary.json` (audience_analysis, comment_sentiment).

### Section XII: The Monetization Model

- Identified revenue streams (sponsorships, affiliates, products, memberships, courses, merch)
- Specific sponsors detected (names from analysis)
- Affiliate platforms detected
- Business funnel: how YouTube fits into broader business
- Revenue model assessment: diversified or dependent?

Source: `analysis_summary.json` (monetization_detection).

### Section XIII: Competitive Position

Include comparison table:

```markdown
| Channel | Subscribers | Total Views | Views/Video | Country |
|---------|------------|-------------|-------------|---------|
```

Then analyze:
- Where this channel ranks among competitors (by subs, views, views/video)
- Percentile position
- Views-per-subscriber ratio comparison (who's more efficient?)
- Gap to next level
- Unique positioning vs competitors

Source: `competitors.json`.

### Section XIV: What This Channel Gets Right — Strategic Advantages

4-6 numbered strategic strengths. Each should be:
- A structural advantage, not just a surface observation
- Tied to specific data points
- Explained in terms of WHY it works (algorithm, audience psychology, business logic)

### Section XV: What This Channel Could Improve

3-5 numbered opportunities. Each should be:
- Backed by specific data (e.g., "description optimization score is 35/100")
- Actionable and specific
- Prioritized by potential impact

### Section XVI: Summary — The [Channel Name] Playbook

- 5-point distillation of what makes this channel work
- Long-term viability assessment
- One key question or prediction about the channel's future
- Closing statement on strategic positioning

---

## Writing Guidelines

Follow these rules strictly:

1. **Voice**: Write as a YouTube strategist who understands platform mechanics, algorithm signals, and growth levers. NOT a generic content marketer or blogger.

2. **No Data Fabrication**: Every number must come from the JSON/CSV files you read. If a data point isn't available, say so or skip the subsection. NEVER invent statistics.

3. **Narrative Interpretation**: Don't just list metrics — explain what they mean. "Upload consistency score of 82 means this channel rarely misses a week, which signals reliability to the algorithm" is better than "Upload consistency: 82/100."

4. **Specificity**: Use exact numbers, reference actual video titles, quote real comments. Vague analysis is worthless.

5. **Patterns Over Lists**: Identify patterns and explain strategic choices. Don't enumerate facts.

6. **Competitive Context**: Position findings relative to competitors and niche norms.

7. **Strategic Framing**: Frame observations as strategic choices and their effects, not just descriptions.

8. **Length**: Target 4,000-5,000 words total. Sections I-II: ~500-800 words. Section III: ~800-1,000 words. Sections IV-XIII: ~200-400 words each. Sections XIV-XVI: ~300-500 words each.

9. **Markdown Formatting**: Use proper headers (##), tables, bold for emphasis, and blockquotes for standout insights.

10. **Verification**: Cross-check key numbers between files. If `verification.json` shows discrepancies, note them.

---

## Output Location

The pipeline owns its own output layout — all files are saved to its
`research_data/[ChannelName]_[YYYYMMDD]/` folder, a sibling of
`$CHANNEL_BREAKDOWN_PIPELINE_DIR`:

```
$CHANNEL_BREAKDOWN_PIPELINE_DIR/../research_data/[ChannelName]_[YYYYMMDD]/
```

Use the exact path the pipeline prints on completion rather than assuming it.

## Files Generated

| File | Description |
|------|-------------|
| `channel_metrics.json` | Basic channel info and stats |
| `all_videos.csv` | Every video with full metadata |
| `videos.csv` | Regular videos only |
| `shorts.csv` | Shorts only (<60s) |
| `live_streams.csv` | Live streams only |
| `analysis_summary.json` | Complete analysis with all metrics |
| `competitors.json` | Competitor channels with stats and rankings |
| `top_videos.json` | Top 10 performing videos |
| `top_comments.json` | Top comments from top 3 videos |
| `verification.json` | Data validation results |
| `research_brief.md` | Markdown summary for live stream prep |
| `company_intelligence.json` | Company news and context |
| `screenshot_urls.json` | R2 CDN URLs for all images |
| `screenshots/` | Thumbnails and browser screenshots |
| **`channel_analysis.md`** | **Expert analysis document (written by Claude)** |

## Dependencies

Required:
- Python 3.11+
- google-api-python-client
- pandas

Optional (graceful fallback if missing):
- playwright (for browser screenshots)
- boto3 (for R2 uploads)

## API Keys Required

- YouTube Data API v3 key in `02_SEO_Research/config/api_credentials.json`
- Cloudflare R2 credentials in `06_Tools_APIs/cloudflare_r2/config/r2_config.json`
