#!/usr/bin/env python3
"""YouTube Thumbnail Analyzer -- data collection + thumbnail download.

Downloads thumbnails from top-performing videos for a topic or channel, along
with the performance data needed to correlate design choices with views.

Usage:
    YT_API_KEY=KEY python3 fetch_thumbnails.py --topic "air fryer recipes" --max 20
    YT_API_KEY=KEY python3 fetch_thumbnails.py --channel @handle --max 20
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

try:
    import requests
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        "ERROR: missing dependencies.\n"
        "  Install them with: pip3 install google-api-python-client requests",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Shared helpers -- kept byte-identical across every youtube-* skill script.
# Each skill is distributed on its own, so these are copied rather than imported.
# ---------------------------------------------------------------------------

# Quota cost per YouTube Data API v3 call (units).
QUOTA_COSTS = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
    "playlists.list": 1,
    "playlistItems.list": 1,
    "commentThreads.list": 1,
    "videoCategories.list": 1,
}


class QuotaTracker:
    """Counts API calls and reports the quota units they consumed."""

    def __init__(self):
        self.calls = Counter()

    def record(self, endpoint, calls=1):
        self.calls[endpoint] += calls

    @property
    def total(self):
        return sum(QUOTA_COSTS.get(ep, 1) * n for ep, n in self.calls.items())

    def breakdown(self):
        return {
            ep: {"calls": n, "units": QUOTA_COSTS.get(ep, 1) * n}
            for ep, n in sorted(self.calls.items())
        }

    def report(self):
        for ep, info in self.breakdown().items():
            print(f"  {ep}: {info['calls']} call(s) = {info['units']} units")
        print(f"Estimated quota used: {self.total} units")


def require_api_key():
    """Return YT_API_KEY or exit with instructions for getting one."""
    key = os.environ.get("YT_API_KEY")
    if not key:
        print(
            "ERROR: YT_API_KEY environment variable is not set.\n"
            "  To get a YouTube Data API v3 key:\n"
            "    1. Open https://console.cloud.google.com/apis/credentials\n"
            "    2. Create or select a project, then enable 'YouTube Data API v3'\n"
            "    3. Create Credentials -> API key\n"
            "    4. Run: export YT_API_KEY='your-key-here'",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def check_quota_error(err):
    """Exit with a clear message when an HttpError means the daily quota is gone."""
    status = getattr(getattr(err, "resp", None), "status", None)
    text = str(err).lower()
    if status == 403 and ("quotaexceeded" in text.replace(" ", "") or "quota" in text):
        print(
            "ERROR: YouTube Data API quota exhausted for today.\n"
            "  The default allowance is 10,000 units/day and it resets at midnight\n"
            "  Pacific Time. Wait for the reset, or request more quota in the\n"
            "  Google Cloud Console (APIs & Services -> YouTube Data API v3 -> Quotas).",
            file=sys.stderr,
        )
        sys.exit(2)


def parse_duration(iso_duration):
    """ISO 8601 duration (PT1H2M3S) -> total seconds."""
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not m:
        return 0
    days, hours, minutes, seconds = (int(g or 0) for g in m.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def format_number(n):
    """1234567 -> '1.2M', 3400 -> '3.4K'."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def days_ago(published_at):
    """Fractional days between an ISO-8601 timestamp and now (UTC). Never negative."""
    try:
        pub = datetime.fromisoformat((published_at or "").replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return 0.0
    return max((datetime.now(timezone.utc) - pub).total_seconds() / 86400.0, 0.0)


def slugify(text, max_len=60):
    """Kebab-case slug safe for filenames."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return s[:max_len].rstrip("-") or "untitled"


def report_paths(reports_dir, short_name, slug):
    """Standard output paths: reports/data/<short>-<slug>-<date>.json + reports/<...>.md.

    Creates both directories. The markdown path is returned so the script can tell
    the caller exactly where the final report belongs.
    """
    stem = f"{short_name}-{slug}-{datetime.now().strftime('%Y-%m-%d')}"
    data_dir = os.path.join(reports_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, stem + ".json"), os.path.join(reports_dir, stem + ".md")


def save_json(path, payload):
    """Write JSON, exiting with a clear message if the write fails."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except (IOError, OSError) as e:
        print(f"ERROR: Could not write {path}: {e}", file=sys.stderr)
        sys.exit(1)


def _channel_info(item):
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    branding = item.get("brandingSettings", {}).get("channel", {})
    related = item.get("contentDetails", {}).get("relatedPlaylists", {})
    return {
        "id": item.get("id", ""),
        "title": snippet.get("title", ""),
        "handle": snippet.get("customUrl", ""),
        "description": snippet.get("description", ""),
        "country": snippet.get("country", ""),
        "created_at": snippet.get("publishedAt", ""),
        "uploads_playlist": related.get("uploads", ""),
        "subscribers": int(stats.get("subscriberCount", 0) or 0),
        "total_views": int(stats.get("viewCount", 0) or 0),
        "video_count": int(stats.get("videoCount", 0) or 0),
        "keywords": branding.get("keywords", ""),
    }


def resolve_channel_id(youtube, channel_input, quota):
    """Resolve any channel reference to a channel info dict for 1 quota unit.

    Accepts UC... IDs, /channel/UC... URLs, @handles, /@handle URLs, /c/name and
    legacy /user/name URLs. Uses channels.list (1 unit) and never search.list (100).
    Returns None if the channel cannot be found.
    """
    raw = (channel_input or "").strip().rstrip("/")
    legacy_user = None

    m = re.search(r"youtube\.com/channel/(UC[\w-]{22})", raw)
    if m:
        raw = m.group(1)
    elif re.search(r"youtube\.com/user/([\w.-]+)", raw):
        legacy_user = re.search(r"youtube\.com/user/([\w.-]+)", raw).group(1)
    elif re.search(r"youtube\.com/@([\w.-]+)", raw):
        raw = "@" + re.search(r"youtube\.com/@([\w.-]+)", raw).group(1)
    elif re.search(r"youtube\.com/c/([\w.-]+)", raw):
        raw = re.search(r"youtube\.com/c/([\w.-]+)", raw).group(1)

    if legacy_user:
        attempts = [{"forUsername": legacy_user}]
    elif re.fullmatch(r"UC[\w-]{22}", raw):
        attempts = [{"id": raw}]
    else:
        handle = raw.lstrip("@")
        attempts = [{"forHandle": handle}, {"forUsername": handle}]

    part = "snippet,statistics,contentDetails,brandingSettings"
    for kwargs in attempts:
        try:
            resp = youtube.channels().list(part=part, **kwargs).execute()
            quota.record("channels.list")
        except HttpError as e:
            check_quota_error(e)
            continue
        items = resp.get("items", [])
        if items:
            return _channel_info(items[0])
    return None


def list_uploads(youtube, uploads_playlist, quota, max_items=None):
    """Page a channel's uploads playlist -- 1 unit per 50 videos.

    This replaces search.list(channelId=...), which costs 100 units per page.
    Returns a list of {"video_id", "published_at"} newest-first.
    """
    items = []
    next_page = None
    if not uploads_playlist:
        return items
    while True:
        page_size = 50
        if max_items is not None:
            remaining = max_items - len(items)
            if remaining <= 0:
                break
            page_size = min(50, remaining)
        try:
            resp = youtube.playlistItems().list(
                part="contentDetails,snippet",
                playlistId=uploads_playlist,
                maxResults=page_size,
                pageToken=next_page,
            ).execute()
            quota.record("playlistItems.list")
        except HttpError as e:
            check_quota_error(e)
            print(f"  playlistItems.list error: {e}", file=sys.stderr)
            break
        for it in resp.get("items", []):
            details = it.get("contentDetails", {})
            items.append({
                "video_id": details.get("videoId", ""),
                "published_at": details.get("videoPublishedAt")
                or it.get("snippet", {}).get("publishedAt", ""),
            })
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
    return items


def batch_video_details(youtube, video_ids, quota, part="snippet,statistics,contentDetails"):
    """Fetch video resources in chunks of 50 (videos.list = 1 unit per call)."""
    videos = []
    unique_ids = [v for v in dict.fromkeys(video_ids) if v]
    for i in range(0, len(unique_ids), 50):
        chunk = unique_ids[i:i + 50]
        try:
            resp = youtube.videos().list(part=part, id=",".join(chunk)).execute()
            quota.record("videos.list")
            videos.extend(resp.get("items", []))
        except HttpError as e:
            check_quota_error(e)
            print(f"  videos.list error: {e}", file=sys.stderr)
    return videos


def batch_channel_details(youtube, channel_ids, quota):
    """Fetch channel stats in chunks of 50. Returns a dict keyed by channel ID."""
    channels = {}
    unique_ids = [c for c in dict.fromkeys(channel_ids) if c]
    for i in range(0, len(unique_ids), 50):
        chunk = unique_ids[i:i + 50]
        try:
            resp = youtube.channels().list(
                part="snippet,statistics,contentDetails,brandingSettings",
                id=",".join(chunk),
            ).execute()
            quota.record("channels.list")
            for item in resp.get("items", []):
                channels[item["id"]] = _channel_info(item)
        except HttpError as e:
            check_quota_error(e)
            print(f"  channels.list error: {e}", file=sys.stderr)
    return channels


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------

def thumbnails_dir(reports_dir, slug):
    """reports/thumbnails/<slug>-<YYYY-MM-DD>/ -- created if missing."""
    path = os.path.join(reports_dir, "thumbnails",
                        f"{slug}-{datetime.now().strftime('%Y-%m-%d')}")
    os.makedirs(path, exist_ok=True)
    return path


def download_thumbnail(video_id, title, rank, output_dir):
    """Download the highest-quality thumbnail available. Returns filename or None."""
    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    ]

    safe_title = "".join(c for c in title[:40] if c.isalnum() or c in " -_").strip()
    safe_title = re.sub(r"\s+", "_", safe_title)
    filename = f"{rank:02d}_{safe_title}_{video_id}.jpg"
    filepath = os.path.join(output_dir, filename)

    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                if not resp.headers.get("content-type", "").startswith("image/"):
                    continue
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return filename
        except requests.RequestException:
            continue

    return None


def search_topic_videos(youtube, topic, max_results, quota):
    """Keyword search -- search.list is required here."""
    video_ids = []
    next_page = None
    remaining = max_results

    while remaining > 0:
        batch = min(remaining, 50)
        try:
            resp = youtube.search().list(
                part="snippet", q=topic, type="video",
                order="viewCount", maxResults=batch, pageToken=next_page,
            ).execute()
            quota.record("search.list")
        except HttpError as e:
            check_quota_error(e)
            print(f"  search.list error: {e}", file=sys.stderr)
            break
        for item in resp.get("items", []):
            video_ids.append(item["id"]["videoId"])
        remaining -= batch
        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    return video_ids


def channel_top_video_ids(youtube, channel, quota, scan_limit=None):
    """All uploads of a channel via playlistItems (1 unit per 50) -- no search.list."""
    uploads = list_uploads(youtube, channel["uploads_playlist"], quota, max_items=scan_limit)
    return [u["video_id"] for u in uploads]


def main():
    parser = argparse.ArgumentParser(description="Download and analyze YouTube thumbnails")
    parser.add_argument("--topic", default=None, help="Topic/keyword to search")
    parser.add_argument("--channel", default=None, help="Channel @handle, URL, or ID")
    parser.add_argument("--max", type=int, default=20,
                        help="Max thumbnails to download (default: 20, max: 50)")
    parser.add_argument("--scan-limit", type=int, default=0,
                        help="Channel mode: cap uploads scanned (0 = whole channel)")
    parser.add_argument("--reports-dir", default="reports",
                        help="Root output directory (default: reports)")
    args = parser.parse_args()

    api_key = require_api_key()
    if not args.topic and not args.channel:
        print("ERROR: Provide --topic or --channel", file=sys.stderr)
        sys.exit(1)

    max_thumbs = min(args.max, 50)
    youtube = build("youtube", "v3", developerKey=api_key)
    quota = QuotaTracker()

    if args.topic:
        source_label = args.topic
        slug = slugify(args.topic)
        print(f"Searching top videos for: {args.topic}")
        video_ids = search_topic_videos(youtube, args.topic, max_thumbs, quota)
        print(f"  Found {len(video_ids)} videos")
    else:
        print(f"Resolving channel: {args.channel}")
        channel = resolve_channel_id(youtube, args.channel, quota)
        if not channel:
            print("ERROR: Could not resolve channel. Check the handle/URL/ID.", file=sys.stderr)
            sys.exit(1)
        source_label = channel["title"]
        slug = slugify(channel.get("handle") or channel["title"])
        print(f"  Found: {channel['title']} ({format_number(channel['subscribers'])} subs)")
        print("Listing uploads...")
        video_ids = channel_top_video_ids(youtube, channel, quota,
                                          scan_limit=args.scan_limit or None)
        print(f"  Found {len(video_ids)} uploads")

    if not video_ids:
        print("No videos found. Exiting.", file=sys.stderr)
        sys.exit(1)

    print("Fetching video details...")
    raw_videos = batch_video_details(youtube, video_ids, quota)
    print(f"  Got {len(raw_videos)} videos")

    print("Fetching channel details...")
    channel_info = batch_channel_details(
        youtube, [v["snippet"]["channelId"] for v in raw_videos], quota
    )

    processed = []
    for v in raw_videos:
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        ch = channel_info.get(v["snippet"]["channelId"], {})

        processed.append({
            "video_id": v["id"],
            "title": v["snippet"]["title"],
            "channel_name": v["snippet"]["channelTitle"],
            "channel_subs": ch.get("subscribers", 0),
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
            "duration_sec": parse_duration(v.get("contentDetails", {}).get("duration", "")),
            "published_at": v["snippet"]["publishedAt"],
        })

    processed.sort(key=lambda x: x["views"], reverse=True)
    processed = processed[:max_thumbs]

    thumbs_dir = thumbnails_dir(args.reports_dir, slug)
    print(f"\nDownloading {len(processed)} thumbnails to {thumbs_dir}/ ...")
    for rank, video in enumerate(processed, 1):
        filename = download_thumbnail(video["video_id"], video["title"], rank, thumbs_dir)
        video["thumbnail_file"] = filename
        video["thumbnail_path"] = os.path.join(thumbs_dir, filename) if filename else None
        print(f"  [{'OK' if filename else 'FAILED'}] {rank:2d}. {video['title'][:55]}")

    index_lines = [
        f"# Thumbnail Analysis: {source_label}\n",
        f"*Downloaded {datetime.now().strftime('%Y-%m-%d')} | {len(processed)} thumbnails*\n",
    ]
    for rank, v in enumerate(processed, 1):
        index_lines.append(f"## {rank}. {v['title']}")
        index_lines.append(
            f"**Views:** {format_number(v['views'])} | "
            f"**Channel:** {v['channel_name']} ({format_number(v['channel_subs'])} subs) | "
            f"**Engagement:** {v['engagement_rate']}%"
        )
        index_lines.append(f"**Video:** https://youtube.com/watch?v={v['video_id']}\n")
        index_lines.append(
            f"![]({v['thumbnail_file']})\n" if v.get("thumbnail_file")
            else "*Thumbnail not available*\n"
        )

    index_path = os.path.join(thumbs_dir, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))

    data_path, report_path = report_paths(args.reports_dir, "thumbnail-analysis", slug)

    data = {
        "source": source_label,
        "mode": "topic" if args.topic else "channel",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_thumbnails": len(processed),
        "thumbnails_dir": thumbs_dir,
        "index_path": index_path,
        "videos": processed,
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, data)

    print(f"\nData saved to: {data_path}")
    print(f"Thumbnails: {thumbs_dir}/")
    print(f"Index: {index_path}")
    print(f"Write the markdown report to: {report_path}")
    quota.report()


if __name__ == "__main__":
    main()
