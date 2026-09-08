---
name: youtube-thumbnails
description: "Download top 10 thumbnails for videos, shorts, and live streams from any YouTube channel. Creates an Obsidian-compatible index with embedded thumbnails. Use when the user wants to download thumbnails, analyze thumbnail designs, or create a visual overview of a YouTube channel's content. Accepts @handle, channel URL, or channel ID."
---

# YouTube Thumbnail Downloader

Downloads the top 10 most-viewed thumbnails per category (regular videos, Shorts, live streams) from any YouTube channel.

## Usage

```
/youtube-thumbnails @ChannelHandle
/youtube-thumbnails @ChannelHandle --skip-verify
/youtube-thumbnails https://youtube.com/@Handle
/youtube-thumbnails UCxxxxxxx
```

## Instructions

### Step 1: Parse Arguments

- **Channel identifier** (required): `@handle`, channel URL, or channel ID (`UCxxxxxxx`)
- **--skip-verify** (optional): skip Level 2 HTTP verification for faster execution
- **--scan-limit N** (optional): cap uploads scanned (default: whole channel)

### Step 2: Get the API Key

Check the user's Claude memory for a YouTube Data API v3 key. If not found, ask:
> "I need a YouTube Data API v3 key to fetch channel data. You can get one from the Google Cloud Console. Please paste your key."

### Step 3: Run the Bundled Script

Run `scripts/download_thumbnails.py` — resolve the path relative to this skill's own directory:

```bash
YT_API_KEY=API_KEY python3 <skill-dir>/scripts/download_thumbnails.py CHANNEL_ARG [--skip-verify]
```

Dependencies: `pip3 install google-api-python-client requests`.

### Step 4: Report Results

Tell the user:
- The thumbnails folder: `reports/thumbnails/<channel-slug>-<YYYY-MM-DD>/`
- Thumbnails downloaded per category (videos, shorts, live streams)
- The path to `index.md` inside that folder
- The data file: `reports/data/thumbnails-<channel-slug>-<YYYY-MM-DD>.json`
- Quota consumed
- Suggest opening `index.md` in Obsidian to see all thumbnails with embedded images

## How Classification Works

**Level 1 — API classification** (from `videos.list` with `liveStreamingDetails`):
- Live stream: has `actualStartTime` or `scheduledStartTime`
- Short: duration between 1 and 180 seconds
- Video: everything else

Priority is live stream > short > regular.

**Level 2 — HTTP verification** (skipped with `--skip-verify`):
- Shorts: `HEAD /shorts/{id}` returns 200 for a real Short, 303 redirect otherwise
- Live streams: the watch page says "Streamed live" for a real stream, "Premiered" for a premiere

Anything that fails verification is demoted to `videos`. Both checks fail conservatively
so a network hiccup never silently drops content from a category.

Each category is then sorted by view count and the top 10 are kept.

## Output Layout

```
reports/
├── data/
│   └── thumbnails-<channel-slug>-<YYYY-MM-DD>.json
└── thumbnails/
    └── <channel-slug>-<YYYY-MM-DD>/
        ├── index.md
        ├── videos/
        ├── shorts/
        └── live_streams/
```

Thumbnails download at the highest resolution available (maxres → sd → hq → mq) and
are named `<rank>_<safe_title>_<video_id>.jpg`.

## Quota Estimate

No `search.list` at all.

| Operation | Calls | Units |
|-----------|-------|-------|
| `channels.list` (resolve handle/ID/URL) | 1 | 1 |
| `playlistItems.list` (500 uploads) | 10 | 10 |
| `videos.list` (batches of 50) | 10 | 10 |
| **Total (500-video channel)** | | **~21** |

Roughly 1 unit per 25 videos on the channel. Resolving a handle previously fell back
to `search.list` (100 units) when the first lookup missed; `forHandle`/`forUsername` now
covers every input form for 1 unit. Thumbnail image downloads use img.youtube.com and
cost 0 quota. Daily default allowance is 10,000 units, resetting at midnight Pacific Time.
