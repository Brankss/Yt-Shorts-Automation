# YouTube Analytics API v2 Reference

Everything this skill sends to `reports.query`, plus the OAuth details behind it.

## Authentication

Unlike the Data API (which takes an `key=API_KEY` parameter), the Analytics API requires **OAuth 2.0**. There is no API-key mode.

### Scopes

| Scope | Grants | Requested |
|-------|--------|-----------|
| `https://www.googleapis.com/auth/yt-analytics.readonly` | View YouTube Analytics reports for your content | Always |
| `https://www.googleapis.com/auth/youtube.readonly` | Read your channel/video metadata (titles, durations, publish dates) | Always |
| `https://www.googleapis.com/auth/yt-analytics-monetary.readonly` | View monetary reports (revenue, CPM, ad impressions) | Only with `auth.py --with-revenue` |

**Never requested:** `youtube`, `youtube.force-ssl`, `youtube.upload`, `youtubepartner`. These are write scopes. `auth.py` hard-fails if any appear in a scope list or in a stored token.

### Token storage and refresh

| Item | Path |
|------|------|
| Credential directory | `~/.config/youtube-skills/` (override with `$YT_OAUTH_DIR`) |
| OAuth client | `client_secret.json` — downloaded from Google Cloud Console, type **Desktop app** |
| Stored token | `token.json` — written by `auth.py`, mode `600` |

Flow: `google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0, prompt="consent")`. Port 0 lets the OS pick a free localhost port, so no redirect URI needs configuring beyond what the Desktop-app client type provides automatically.

`get_credentials()` loads `token.json` and, if the access token is expired, calls `creds.refresh(Request())` using the refresh token and rewrites the file. This is silent — no browser. A browser is only needed on first authorization or after `--force`.

**Refresh token lifetime:** a Google Cloud OAuth consent screen left in **Testing** status expires refresh tokens after **7 days**. Publishing the consent screen to **Production** (unverified is acceptable for a personal single-user tool) makes them long-lived. This is the fix when re-authorization keeps being demanded weekly.

## reports.query

```
GET https://youtubeanalytics.googleapis.com/v2/reports
```

Called through the Python client as:

```python
analytics = build("youtubeAnalytics", "v2", credentials=creds)
analytics.reports().query(
    ids="channel==MINE",
    startDate="2026-05-15",
    endDate="2026-08-12",
    metrics="views,estimatedMinutesWatched",
    dimensions="day",
    sort="day",
).execute()
```

### Parameters

| Param | Required | Notes |
|-------|----------|-------|
| `ids` | Yes | `channel==MINE` for the authorized channel. (`channel==CHANNEL_ID` also works if you own it; `contentOwner==ID` is CMS-only.) |
| `startDate` | Yes | `YYYY-MM-DD` |
| `endDate` | Yes | `YYYY-MM-DD`, inclusive |
| `metrics` | Yes | Comma-separated, no spaces |
| `dimensions` | No | Comma-separated. Omit for a single totals row. |
| `filters` | No | `dim==value`, joined with `;` for AND. e.g. `video==ID;audienceType==ORGANIC` |
| `sort` | No | Dimension or metric name; prefix `-` for descending. Some reports require it. |
| `maxResults` | No | Required alongside `sort` for several detail reports. Video dimension caps at 200. |
| `startIndex` | No | 1-based pagination offset |
| `currency` | No | ISO 4217 code for monetary metrics; defaults to the channel's AdSense currency |

### Response shape

```json
{
  "kind": "youtubeAnalytics#resultTable",
  "columnHeaders": [
    { "name": "day", "columnType": "DIMENSION", "dataType": "STRING" },
    { "name": "views", "columnType": "METRIC", "dataType": "INTEGER" }
  ],
  "rows": [
    ["2026-08-01", 1420],
    ["2026-08-02", 1105]
  ]
}
```

Rows are positional arrays matching `columnHeaders` order. `fetch_insights.py` zips them into dicts. **`rows` is absent entirely when a query matches nothing** — treat a missing key as an empty result, not an error.

## Dates and the reporting lag

YouTube Analytics data is not final for roughly **2–3 days**. Querying up to today returns partial rows that look like a cliff in the trend.

This skill therefore computes:

```
end   = today - 3 days
start = end - (days - 1)
```

and records the exact window in every payload alongside a `data_lag_note`.

## Metrics used

### Core / engagement

| Metric | Type | Meaning |
|--------|------|---------|
| `views` | integer | Video views |
| `estimatedMinutesWatched` | integer | Total watch time in minutes — the metric the algorithm optimizes for |
| `averageViewDuration` | integer | Seconds watched per view |
| `averageViewPercentage` | float | Percent of the video watched per view |
| `subscribersGained` | integer | Subs gained, attributable to a video when `dimensions=video` |
| `subscribersLost` | integer | Subs lost |
| `likes` / `dislikes` | integer | `dislikes` is deprecated and returns 0 |
| `comments` | integer | Comments left |
| `shares` | integer | Shares via the share button |
| `viewerPercentage` | float | Share of views in a demographic bucket. **Cannot be combined with other metrics.** |

### Retention

| Metric | Meaning |
|--------|---------|
| `audienceWatchRatio` | Fraction of viewers still watching at each `elapsedVideoTimeRatio` point. 1.0 = everyone who started. |
| `relativeRetentionPerformance` | This video vs similar-length YouTube videos. `>0.5` above typical, `<0.5` below typical. Unavailable on low-view videos and when some filters are applied. |

### Monetary (require `yt-analytics-monetary.readonly`)

| Metric | Meaning |
|--------|---------|
| `estimatedRevenue` | Total net revenue (ads + YouTube Premium) |
| `estimatedAdRevenue` | Net ad revenue only |
| `grossRevenue` | Pre-revenue-share earnings |
| `playbackBasedCpm` | Estimated gross revenue per 1,000 playbacks with ads |
| `cpm` | Estimated gross revenue per 1,000 ad impressions |
| `adImpressions` | Verified ad impressions served |
| `monetizedPlaybacks` | Playbacks that showed at least one ad |

**RPM is not an API metric.** Compute it: `estimatedRevenue / views * 1000`. `fetch_insights.py` adds it as `rpm` on every revenue-by-video row.

## Dimensions used

| Dimension | Values | Used by |
|-----------|--------|---------|
| `day` | `YYYY-MM-DD` | `overview`, `subscribers`, `revenue` |
| `video` | Video IDs (max 200 rows) | `top-videos`, `subscribers`, `revenue` |
| `elapsedVideoTimeRatio` | `0.00`–`1.00` in 100 steps | `retention` |
| `insightTrafficSourceType` | see table below | `traffic` |
| `insightTrafficSourceDetail` | search terms, source videos, external URLs | `traffic` drill-down |
| `ageGroup` | `age13-17`, `age18-24`, `age25-34`, `age35-44`, `age45-54`, `age55-64`, `age65-` | `audience` |
| `gender` | `female`, `male`, `user_specified` | `audience` |
| `country` | ISO 3166-1 alpha-2 | `audience` |
| `deviceType` | `DESKTOP`, `MOBILE`, `TABLET`, `TV`, `GAME_CONSOLE`, `UNKNOWN_PLATFORM` | `audience` |
| `operatingSystem` | `ANDROID`, `IOS`, `WINDOWS`, `MACINTOSH`, `LINUX`, `PLAYSTATION`, ... | `audience` |

### Traffic source types

| Value | What it means | Strategic read |
|-------|---------------|----------------|
| `YT_SEARCH` | YouTube search results | Evergreen / SEO demand |
| `RELATED_VIDEO` | Suggested next to or after another video | Algorithm momentum |
| `SUBSCRIBER` | Home feed, subscription feed, Shorts feed | Returning-audience strength |
| `NO_LINK_OTHER` / `NO_LINK_EMBEDDED` | Direct or embedded plays with no referrer | Off-platform / dark traffic |
| `EXT_URL` | External websites | Imported traffic |
| `NOTIFICATION` | Bell / email notifications | Core-fan reach |
| `PLAYLIST` | Played from a playlist | Session-building |
| `CHANNEL` / `YT_CHANNEL` | Channel page | Discovery via profile |
| `END_SCREEN` | End screen of another video | Internal routing |
| `ANNOTATION` / `CAMPAIGN_CARD` | Cards | Internal routing |
| `ADVERTISING` | Paid | Bought traffic |
| `SHORTS` | Shorts feed | Short-form surface |
| `HASHTAGS`, `SOUND_PAGE`, `PRODUCT_PAGE`, `VIDEO_REMIXES`, `YT_OTHER_PAGE` | Misc surfaces | Usually long-tail |

**Note:** "Browse features" in YouTube Studio maps to `SUBSCRIBER` plus parts of `YT_OTHER_PAGE` in the API — the Studio label and the API value are not one-to-one.

### Traffic source detail

`insightTrafficSourceDetail` needs an `insightTrafficSourceType` filter, plus `sort` and `maxResults`:

```python
filters="insightTrafficSourceType==YT_SEARCH"
dimensions="insightTrafficSourceDetail"
metrics="views,estimatedMinutesWatched"
sort="-views"
maxResults=25
```

Only some types support the drill-down: `ADVERTISING`, `CAMPAIGN_CARD`, `END_SCREEN`, `EXT_URL`, `HASHTAGS`, `NOTIFICATION`, `RELATED_VIDEO`, `SOUND_PAGE`, `SUBSCRIBER`, `VIDEO_REMIXES`, `YT_CHANNEL`, `YT_OTHER_PAGE`, `YT_SEARCH`. Requesting detail for any other type returns a 400.

What the detail column contains varies by type: search *queries* for `YT_SEARCH`, source *video IDs* for `RELATED_VIDEO`, *domains* for `EXT_URL`.

## Filters

| Filter | Values | Notes |
|--------|--------|-------|
| `video==ID` | One video ID | Combine with `;` for AND |
| `country==XX` | ISO 3166-1 alpha-2 | |
| `insightTrafficSourceType==TYPE` | see above | Required for detail drill-downs |
| `audienceType==TYPE` | `ORGANIC`, `AD_INSTREAM`, `AD_INDISPLAY` | Retention only. `ORGANIC` excludes ad-driven views — use it when a video ran ads, or the curve is polluted. |

## Report recipes used by this skill

| Subcommand | metrics | dimensions | filters | sort |
|------------|---------|------------|---------|------|
| `overview` | views, estimatedMinutesWatched, averageViewDuration, averageViewPercentage, subscribersGained, subscribersLost, likes, comments, shares | `day` (and once with none, for totals) | — | `day` |
| `top-videos` | same as overview | `video` | — | `-estimatedMinutesWatched` |
| `retention` | audienceWatchRatio, relativeRetentionPerformance | `elapsedVideoTimeRatio` | `video==ID[;audienceType==T]` | `elapsedVideoTimeRatio` |
| `traffic` | views, estimatedMinutesWatched, averageViewDuration | `insightTrafficSourceType` | optional `video==ID` | `-views` |
| `audience` (1) | viewerPercentage | `ageGroup,gender` | — | `gender,ageGroup` |
| `audience` (2) | views, estimatedMinutesWatched, averageViewDuration, averageViewPercentage | `country` | — | `-views` |
| `audience` (3) | views, estimatedMinutesWatched, averageViewDuration | `deviceType,operatingSystem` | — | `-views` |
| `subscribers` | views, subscribersGained, subscribersLost | `video` | — | `-subscribersGained` |
| `revenue` | estimatedRevenue, estimatedAdRevenue, playbackBasedCpm, adImpressions, monetizedPlaybacks | `day`, then `video` | — | `day` / `-estimatedRevenue` |

## Data API v3 calls (enrichment only)

The Analytics API returns bare video IDs. Titles, durations, and publish dates come from the Data API using the same OAuth credential:

```
GET https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,statistics&id=ID1,ID2,...
GET https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true
```

IDs are batched 50 at a time. Cost: **1 unit per call** against the standard 10,000/day Data API quota.

## Not available in this API

| Metric | Where to get it |
|--------|-----------------|
| Thumbnail impressions | YouTube Studio only (*Analytics > Reach*) |
| Impressions click-through rate | YouTube Studio only |
| "Browse features" as a single labeled bucket | Studio label; approximate from `SUBSCRIBER` + `YT_OTHER_PAGE` |
| Real-time (last 48h) figures | Studio; API data settles after ~2–3 days |

## Errors

| Code | Typical cause | Fix |
|------|---------------|-----|
| 400 | Invalid metric/dimension combination, missing required `filters` or `sort` for a detail report | Check the recipe table above |
| 401 | Access token expired and refresh failed; refresh token revoked | `python3 scripts/auth.py --force` |
| 403 | YouTube Analytics API not enabled on the project; missing scope; channel not monetized (revenue queries) | Enable the API, or re-run `auth.py --with-revenue` |
| 404 | Bad video ID in a filter | Verify the ID |
| 429 | Rate limited | Back off and retry |

`fetch_insights.py` maps 401/403 to an explicit "re-run auth.py" message, and treats empty `rows` as a reported-but-non-fatal condition on every query.

## Quota

The Analytics API maintains **its own quota, independent of the Data API's 10,000 units/day**. There is no published per-call unit table; the practical limits are generous request-rate caps. A full `fetch_insights.py all` run issues roughly 15–20 Analytics queries and a handful of Data API calls, so it can be run repeatedly without meaningful quota pressure on the other skills in this suite.
