---
name: youtube-channel-insights
description: "Deep private analytics for your OWN YouTube channel using the YouTube Analytics API v2 — audience retention curves, traffic source mix, watch time, demographics, subscriber attribution, and revenue. These are the metrics the public Data API cannot see. Use when users want to (1) Understand why a video did or did not perform, (2) Diagnose their traffic mix (Search vs Suggested vs Browse), (3) Find where viewers drop off with retention analysis, (4) See who their audience actually is by age, gender, country, and device, (5) Identify which videos convert viewers into subscribers, (6) Review RPM and revenue by video, (7) Get a prioritized action plan for channel growth. Requires one-time Google OAuth setup (read-only scopes)."
---

# YouTube Channel Insights

Analyze your own channel with the data only the channel owner can see. The other skills in this suite read public data; this one authenticates as you and pulls **retention, traffic sources, watch time, demographics, subscriber attribution, and revenue** from the YouTube Analytics API v2.

| Question | Public Data API | This skill |
|----------|-----------------|-----------|
| How many views? | Yes | Yes |
| How long did people watch? | No | Yes (watch time, avg view %) |
| Where did viewers drop off? | No | Yes (retention curve) |
| Where did the traffic come from? | No | Yes (Search / Suggested / Browse) |
| Who is the audience? | No | Yes (age, gender, country, device) |
| Which videos gained subscribers? | No | Yes |
| What did it earn? | No | Yes (with `--with-revenue`) |

## One-time setup

The user does this once, then never again. Walk them through it if `python3 scripts/auth.py --check` reports anything missing.

1. **Create or reuse a Google Cloud project** — [console.cloud.google.com](https://console.cloud.google.com/). Any project works, including one already used for a Data API key.
2. **Enable both APIs** in *APIs & Services > Library*:
   - **YouTube Data API v3** (used to attach titles, durations, and publish dates to analytics rows)
   - **YouTube Analytics API** (the actual insights)
   Both are required. Missing the Analytics API is the single most common cause of a 403.
3. **Configure the OAuth consent screen** — *APIs & Services > OAuth consent screen*:
   - User type: **External**
   - Fill in app name and your email
   - Add your own Google account under **Test users**
   - Then **PUBLISH the app to Production**. This matters: while the consent screen sits in *Testing* mode, Google expires refresh tokens after **7 days**, so you would have to re-authorize every week. Publishing without Google verification is fine for a personal, single-user tool — you will see an "unverified app" warning at sign-in and can click through via *Advanced > Go to (app)*.
4. **Create an OAuth client ID** — *APIs & Services > Credentials > Create Credentials > OAuth client ID*:
   - Application type: **Desktop app**
   - Download the JSON
5. **Save the file** as `~/.config/youtube-skills/client_secret.json`:
   ```bash
   mkdir -p ~/.config/youtube-skills
   mv ~/Downloads/client_secret_*.json ~/.config/youtube-skills/client_secret.json
   chmod 600 ~/.config/youtube-skills/client_secret.json
   ```
6. **Install dependencies and authorize**:
   ```bash
   pip3 install google-api-python-client google-auth-oauthlib
   python3 scripts/auth.py                  # analytics + channel read access
   python3 scripts/auth.py --with-revenue   # also unlock revenue / RPM metrics
   ```
   A browser opens. **Sign in with the Google account that owns the channel.** The token lands in `~/.config/youtube-skills/token.json` (mode 600) and refreshes itself from then on.

**Security:** only read-only scopes are ever requested — `yt-analytics.readonly`, `youtube.readonly`, and optionally `yt-analytics-monetary.readonly`. The scripts refuse to run with write scopes (`youtube`, `youtube.force-ssl`). Nothing can be uploaded, edited, or deleted with these credentials. Credentials never touch the repo or `/tmp`; override the location with `YT_OAUTH_DIR` if you need to.

## Usage

```
/youtube-channel-insights
/youtube-channel-insights --days 28
/youtube-channel-insights retention for video dQw4w9WgXcQ
/youtube-channel-insights why is my traffic dropping
```

## Instructions

When the user invokes this skill:

### Step 1: Check authorization

```bash
python3 scripts/auth.py --check
```

If the token is missing or invalid, walk the user through **One-time setup** above rather than guessing. If they mention revenue, RPM, or earnings, make sure they ran `auth.py --with-revenue`.

### Step 2: Parse arguments

- **--days N** (optional): analysis window, default **90**. Use 28 for "what changed recently", 90 for strategy, 365 for annual review.
- **Specific video ID** (optional): if the user names one video, run targeted `retention` and `traffic --video` instead of the full sweep.

### Step 3: Fetch the data

For a full channel review — one command, one combined file:

```bash
python3 scripts/fetch_insights.py all --days 90
```

This writes `reports/data/channel-insights-<YYYY-MM-DD>.json` (directories created automatically) and prints the path. It runs overview, top videos, traffic, audience, subscribers, revenue (if authorized), and retention curves for the top 5 videos by watch time.

For targeted questions, use single subcommands — each prints JSON to stdout or to `--out`:

| Subcommand | What it answers |
|------------|-----------------|
| `overview --days N` | Daily views, watch time, avg view duration & %, subs gained/lost, likes, comments, shares |
| `top-videos --days N --limit K` | Best videos by watch time, enriched with titles, durations, publish dates |
| `retention --video ID` | Audience retention curve + relative retention vs similar videos |
| `traffic --days N [--video ID]` | Traffic source mix, plus detail drill-down (search terms, suggesting videos) |
| `audience --days N` | Age/gender, top countries, device + OS breakdown |
| `subscribers --days N` | Subscribers gained/lost per video, plus subs per 1,000 views |
| `revenue --days N` | Revenue, ad revenue, CPM, RPM, ad impressions, monetized playbacks |

Useful flags: `--limit` (videos returned, max 200), `--detail-sources` (how many traffic sources to drill into), `--retention-videos` (how many curves `all` pulls), `--audience-type ORGANIC` (exclude ad-driven traffic from a retention curve), `--out PATH`.

### Step 4: Read and analyze the JSON

Read the combined file. **Do not dump raw numbers back at the user** — interpret them. Every payload carries a `window` block with the exact date range and a `note` on any empty result, so you always know whether a blank section means "no activity" or "not applicable".

Compute these yourself from the data before writing:

- **Watch time trend**: split the daily series in half and compare `estimatedMinutesWatched`. Rising watch time with flat views means retention improved.
- **Average view percentage** against video length (benchmarks below).
- **Traffic mix percentages** — already provided as `share_of_views_pct`.
- **Retention at 30 seconds**: find the curve row where `elapsed_seconds` ≈ 30. This is the hook test.
- **Biggest cliffs**: the largest drops in `audienceWatchRatio` between consecutive points; convert to timestamps via `elapsed_seconds`.
- **Subscriber conversion**: `subs_per_1000_views`, already computed per video.
- **RPM** per video, already computed as `rpm` when revenue is available.

### Step 5: Write the report

Write markdown to `reports/channel-insights-<YYYY-MM-DD>.md` using the template below. Write as a channel strategist, not a dashboard: every number needs a "so what".

### Step 6: Report completion

Tell the user the report path, the single most important finding, and the #1 recommended action.

## Benchmarks

Use these numbers when judging performance. State the benchmark alongside the channel's actual figure so the user can see the gap.

| Metric | Weak | Solid | Strong |
|--------|------|-------|--------|
| Average view percentage (video < 10 min) | < 35% | 40–50% | **50%+** |
| Average view percentage (10–20 min) | < 25% | 30–40% | 45%+ |
| Average view percentage (20 min+) | < 20% | 25–35% | 40%+ |
| Retention at 30 seconds | < 60% | 65–75% | 80%+ |
| Subscribers per 1,000 views | < 1 | 1–3 | **5+** |
| Like rate (likes / views) | < 1% | 2–4% | 5%+ |
| Comment rate | < 0.1% | 0.3–0.8% | 1%+ |
| Returning-viewer signal: Browse share of views | < 10% | 20–35% | 40%+ |
| RPM (varies wildly by niche/geo) | < $2 | $3–8 | $10+ |

Retention curves fall fastest in the first 30 seconds; a drop to ~70% by 0:30 is normal. A drop below 50% by 0:30 means the hook, not the topic, is the problem.

## Report template

```markdown
# Channel Insights: [Channel Name]
*[start date] – [end date] · [N] days · generated [date]*

## Executive Summary
- Three to five bullets. Lead with the finding that changes what they do next week.
- State the direction of travel: watch time up/down X%, subs up/down Y, and why.
- One sentence naming the single biggest lever available.

## Algorithm Health
| Metric | This period | Prior half vs latter half | Benchmark | Verdict |
|--------|-------------|---------------------------|-----------|---------|
| Views | | | | |
| Watch time (hours) | | | | |
| Average view duration | | | | |
| Average view percentage | | | 50%+ strong for <10min | |
| Net subscribers | | | | |

Watch time is what the algorithm optimizes for — views without watch time do not compound.
Interpret: is watch time growing faster, slower, or in line with views? Faster means retention is
improving and the algorithm will push harder. Slower means the channel is buying views with
titles and thumbnails that the content does not pay off.

## Traffic Source Diagnosis
| Source | Views | % of views | Avg view duration |
|--------|-------|-----------|-------------------|
| YouTube search | | | |
| Suggested videos | | | |
| Browse features | | | |
| External / Shorts feed / other | | | |

Read the mix, then pick the matching playbook:

- **Search-heavy (40%+ from YT_SEARCH)** — an evergreen/SEO channel. Traffic is durable but
  ceiling-limited by query volume. *Do:* target higher-volume queries, refresh titles and
  descriptions on older winners, build topic clusters that link to each other. *Do not* expect
  a spike from any single upload.
- **Suggested-heavy (40%+ from RELATED_VIDEO)** — the algorithm has momentum. This is the
  fastest-growing state and the most fragile. *Do:* publish more of exactly the format that is
  being suggested, while the window is open. Check the `insightTrafficSourceDetail` rows to see
  *which* videos are feeding you — make companion pieces to those. *Do not* pivot topics now.
- **Browse-heavy (35%+ from Browse features / home)** — a strong returning audience that YouTube
  serves on their homepage. *Do:* protect upload consistency, since Browse traffic depends on
  habit. Experiment more freely; loyal audiences forgive range. *Do:* work on packaging, because
  homepage placement means you're competing on thumbnail against everything else they subscribe to.
- **External-heavy** — traffic is being imported, not earned. Sustainable only if the external
  source is durable. Watch whether imported viewers stick (compare their avg view duration).

Note any source with unusually high or low average view duration — that is where the audience
mismatch lives.

## Retention Deep-Dive
For each of the top videos analyzed:

**[Video title]** — [duration] · [views] views · [avg view %] avg view percentage
- Retention at 0:30: **X%** (benchmark 70%+)
- Biggest cliff: **-X points at [MM:SS]** — [what happens there; sponsor read? topic change? recap?]
- Relative retention performance: X (above / below typical for this length)

Then across the set:
- Videos performing **above** typical: what do their openings share?
- Videos performing **below** typical: name the concrete structural fix.
- The pattern to repeat and the pattern to stop.

## Audience Profile
| Segment | Top values | Implication |
|---------|-----------|-------------|
| Age / gender | | Tone, references, thumbnail faces |
| Top countries | | Posting time, language, sponsor fit, RPM |
| Device | | Mobile-heavy → bigger thumbnail text, tighter edits, front-load the payoff |

State the practical consequences: if X% watch on mobile, thumbnail text must survive at 120px
wide. If the audience concentrates in one timezone, name the posting window. If a high-RPM
country dominates, that changes the monetization ceiling.

## Subscriber Drivers
| Video | Views | Subs gained | Subs per 1,000 views | Format |
|-------|-------|-------------|---------------------|--------|

The top converters, not the top viewed. A video with 20K views and 8 subs/1,000 is a better
template than one with 200K views and 0.5 subs/1,000. Name the shared trait — format, topic,
length, or call-to-action placement — and say explicitly which format to double down on.
Also flag videos with high subscribers *lost*: those are audience-mismatch signals.

## Revenue
*(Only if the monetary scope was granted and the channel is monetized.)*
| Video / topic | Views | Revenue | RPM | Playback CPM |
|---------------|-------|---------|-----|-------------|

Which topics earn multiples of the channel average RPM? Length, geography, and topic drive RPM
more than view count does. Recommend where to spend production effort for revenue, and note when
the highest-RPM content is not the highest-viewed content.

## Prioritized Action Plan
Top 5 moves, ranked by expected impact. Each one:
1. **[Action]** — Why (cite the specific number), expected effect, effort, how to measure it in 30 days.
```

## Limitations

Be honest with the user about these — do not invent numbers to fill the gaps.

- **Thumbnail impressions and impressions click-through rate are NOT available.** The public YouTube Analytics API does not expose them; they exist only inside YouTube Studio. If CTR matters to the analysis, tell the user to read it in Studio (*Analytics > Reach*) and paste it in. Never estimate CTR from other metrics.
- **Data lags 2–3 days.** Every window this skill requests ends at *today minus 3* so the last days are settled, and the exact range is recorded in every payload. Yesterday's upload will not appear.
- **Demographics are withheld on small samples.** YouTube suppresses age/gender rows when too few viewers are in a bucket. Empty is not zero.
- **Retention needs volume.** Videos under roughly 100 views usually return no retention curve.
- **Revenue requires the Partner Program** *and* the `--with-revenue` scope. The script degrades gracefully and says which one is missing.
- **`channel==MINE` only.** These credentials analyze the authorized channel and nothing else. For competitor analysis, use `youtube-competitor-analyzer`.

## Quota notes

The YouTube Analytics API has **its own quota, separate from the Data API's 10,000 units/day**. It is generous — a full `all` run costs on the order of 15–20 Analytics queries, nowhere near any practical limit, and there is no per-unit cost table to budget against.

The only Data API usage here is `videos.list` and `channels.list` for enrichment, at **1 unit per call** (batched 50 IDs at a time). A full run typically spends **2–8 Data API units** — negligible against the 10,000/day budget, so this skill can be run repeatedly without endangering the quota the other skills in this suite depend on.

## Files

- `scripts/auth.py` — one-time OAuth flow, token storage, silent refresh, `--check` status
- `scripts/fetch_insights.py` — all subcommands
- `references/api_reference.md` — Analytics API v2 metrics, dimensions, filters, and scopes
