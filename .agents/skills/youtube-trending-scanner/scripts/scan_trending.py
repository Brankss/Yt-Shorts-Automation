#!/usr/bin/env python3
"""YouTube Trending Scanner -- data collection.

Scans recent videos in a niche to surface velocity outliers, rising channels,
and emerging topics, then writes structured JSON for analysis.

Usage:
    YT_API_KEY=KEY python3 scan_trending.py "meditation"
    YT_API_KEY=KEY python3 scan_trending.py "AI tools" --days 14
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        "ERROR: google-api-python-client is not installed.\n"
        "  Install it with: pip3 install google-api-python-client",
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
# Trend scanning
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "you", "your", "my", "this", "that", "i", "me", "we",
    "how", "what", "why", "do", "does", "can", "will", "be", "are", "was",
    "not", "no", "so", "if", "its", "just", "like", "get", "new", "one",
}


def search_recent(youtube, query, days, order, quota, max_results=50):
    """Keyword search within a time window -- search.list is required here."""
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    video_ids = []
    next_page = None
    remaining = max_results

    while remaining > 0:
        batch = min(remaining, 50)
        try:
            resp = youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                order=order,
                publishedAfter=after,
                maxResults=batch,
                pageToken=next_page,
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


def duration_format(seconds):
    if seconds <= 60:
        return "Short (<1 min)"
    if seconds <= 300:
        return "Short-form (1-5 min)"
    if seconds <= 900:
        return "Medium (5-15 min)"
    if seconds <= 1800:
        return "Standard (15-30 min)"
    return "Long-form (30+ min)"


def main():
    parser = argparse.ArgumentParser(description="Scan YouTube trends in a niche")
    parser.add_argument("niche", help="Niche/keyword to scan")
    parser.add_argument("--days", type=int, default=14,
                        help="Time window in days (default: 14, max: 30)")
    parser.add_argument("--reports-dir", default="reports",
                        help="Root output directory (default: reports)")
    args = parser.parse_args()

    api_key = require_api_key()
    days = min(args.days, 30)
    youtube = build("youtube", "v3", developerKey=api_key)
    quota = QuotaTracker()

    print(f"Scanning trends in: {args.niche}")
    print(f"Time window: last {days} days\n")

    print("Searching recent videos (by relevance)...")
    relevance_ids = search_recent(youtube, args.niche, days, "relevance", quota, 50)
    print(f"  Found {len(relevance_ids)}")

    print("Searching recent videos (by view count)...")
    viewcount_ids = search_recent(youtube, args.niche, days, "viewCount", quota, 50)
    print(f"  Found {len(viewcount_ids)}")

    print("Searching newest uploads...")
    date_ids = search_recent(youtube, args.niche, days, "date", quota, 50)
    print(f"  Found {len(date_ids)}")

    print("Fetching baseline (last 90 days by viewCount)...")
    baseline_ids = search_recent(youtube, args.niche, 90, "viewCount", quota, 50)
    print(f"  Found {len(baseline_ids)} baseline videos")

    all_ids = list(dict.fromkeys(relevance_ids + viewcount_ids + date_ids + baseline_ids))
    print(f"\nTotal unique videos: {len(all_ids)}")

    print("Fetching video details...")
    raw_videos = batch_video_details(youtube, all_ids, quota)
    print(f"  Got {len(raw_videos)} videos")

    channel_ids = [v["snippet"]["channelId"] for v in raw_videos]
    print("Fetching channel details...")
    channels = batch_channel_details(youtube, channel_ids, quota)
    print(f"  Got {len(channels)} channels")

    videos_data = []
    for v in raw_videos:
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        duration = parse_duration(v.get("contentDetails", {}).get("duration", ""))
        channel_id = v["snippet"]["channelId"]
        subs = channels.get(channel_id, {}).get("subscribers", 0)
        age = max(days_ago(v["snippet"]["publishedAt"]), 0.1)

        videos_data.append({
            "video_id": v["id"],
            "title": v["snippet"]["title"],
            "channel_id": channel_id,
            "channel_name": v["snippet"]["channelTitle"],
            "channel_subs": subs,
            "published_at": v["snippet"]["publishedAt"],
            "age_days": round(age, 1),
            "views": views,
            "likes": likes,
            "comments": comments,
            "duration_sec": duration,
            "velocity": round(views / age),
            "vs_ratio": round(views / subs, 2) if subs > 0 else 0,
            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
            "tags": v.get("snippet", {}).get("tags", []),
            "is_recent": age <= days,
        })

    recent = [v for v in videos_data if v["is_recent"]]
    baseline = [v for v in videos_data if not v["is_recent"]]

    if recent:
        velocities = sorted(v["velocity"] for v in recent)
        avg_velocity = sum(velocities) / len(velocities)
        median_velocity = velocities[len(velocities) // 2]
        velocity_outliers = [v for v in recent if v["velocity"] > avg_velocity * 3]
        velocity_outliers.sort(key=lambda x: x["velocity"], reverse=True)
    else:
        avg_velocity = 0
        median_velocity = 0
        velocity_outliers = []

    channel_videos = {}
    for v in recent:
        channel_videos.setdefault(v["channel_id"], []).append(v)

    rising_channels = []
    for cid, vids in channel_videos.items():
        ch = channels.get(cid, {})
        subs = ch.get("subscribers", 0)
        if subs < 100_000:
            total_recent_views = sum(v["views"] for v in vids)
            avg_vs_ratio = sum(v["vs_ratio"] for v in vids) / len(vids)
            if avg_vs_ratio > 1.0 or total_recent_views > subs * 2:
                rising_channels.append({
                    "channel_id": cid,
                    "channel_name": ch.get("title", "Unknown"),
                    "subscribers": subs,
                    "recent_videos": len(vids),
                    "total_recent_views": total_recent_views,
                    "avg_vs_ratio": round(avg_vs_ratio, 2),
                    "top_video": max(vids, key=lambda x: x["views"])["title"],
                })

    rising_channels.sort(key=lambda x: x["avg_vs_ratio"], reverse=True)

    word_counter = Counter()
    bigram_counter = Counter()
    for v in recent:
        words = re.findall(r"[a-zA-Z]{3,}", v["title"].lower())
        filtered = [w for w in words if w not in STOP_WORDS]
        for w in filtered:
            word_counter[w] += 1
        for i in range(len(filtered) - 1):
            bigram_counter[f"{filtered[i]} {filtered[i + 1]}"] += 1

    recent_per_day = len(recent) / max(days, 1)
    baseline_per_day = len(baseline) / 90 if baseline else 0

    format_counter = Counter(duration_format(v["duration_sec"]) for v in recent)

    data_path, report_path = report_paths(args.reports_dir, "trending-scan", slugify(args.niche))

    output = {
        "niche": args.niche,
        "time_window_days": days,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_recent_videos": len(recent),
            "total_baseline_videos": len(baseline),
            "recent_publishing_rate": round(recent_per_day, 2),
            "baseline_publishing_rate": round(baseline_per_day, 2),
            "avg_velocity": round(avg_velocity),
            "median_velocity": round(median_velocity),
            "unique_channels_recent": len(channel_videos),
        },
        "velocity_outliers": [
            {
                "title": v["title"],
                "video_id": v["video_id"],
                "views": v["views"],
                "velocity": v["velocity"],
                "age_days": v["age_days"],
                "channel_name": v["channel_name"],
                "channel_subs": v["channel_subs"],
                "vs_ratio": v["vs_ratio"],
            }
            for v in velocity_outliers[:15]
        ],
        "rising_channels": rising_channels[:10],
        "trending_topics": {
            "words": word_counter.most_common(30),
            "bigrams": bigram_counter.most_common(20),
        },
        "format_distribution": dict(format_counter.most_common()),
        "top_recent_videos": [
            {
                "title": v["title"],
                "video_id": v["video_id"],
                "views": v["views"],
                "velocity": v["velocity"],
                "channel_name": v["channel_name"],
                "channel_subs": v["channel_subs"],
                "age_days": v["age_days"],
                "engagement_rate": v["engagement_rate"],
            }
            for v in sorted(recent, key=lambda x: x["views"], reverse=True)[:20]
        ],
        "all_recent_videos": recent,
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, output)

    print(f"\nData saved to: {data_path}")
    print(f"Write the markdown report to: {report_path}")
    print(f"Recent videos: {len(recent)}")
    print(f"Velocity outliers: {len(velocity_outliers)}")
    print(f"Rising channels: {len(rising_channels)}")
    quota.report()


if __name__ == "__main__":
    main()
