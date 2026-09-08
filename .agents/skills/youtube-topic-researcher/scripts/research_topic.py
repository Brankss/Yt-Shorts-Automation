#!/usr/bin/env python3
"""YouTube Topic Researcher -- data collection.

Searches YouTube for a topic/keyword across three orderings, fetches video and
channel details, and writes structured JSON for analysis.

Usage:
    YT_API_KEY=KEY python3 research_topic.py "air fryer recipes"
    YT_API_KEY=KEY python3 research_topic.py "Python automation" --max-results 75
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

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
# Topic research
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "you", "your", "my", "this", "that", "i", "me", "we",
    "how", "what", "why", "do", "does", "can", "will", "be", "are", "was",
    "not", "no", "so", "if",
}


def search_videos(youtube, query, max_results, quota, order="relevance"):
    """Keyword search -- the one place search.list is genuinely required."""
    video_ids = []
    next_page = None
    remaining = max_results

    while remaining > 0:
        batch_size = min(remaining, 50)
        try:
            resp = youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                order=order,
                maxResults=batch_size,
                pageToken=next_page,
            ).execute()
            quota.record("search.list")
        except HttpError as e:
            check_quota_error(e)
            print(f"  search.list error: {e}", file=sys.stderr)
            break

        for item in resp.get("items", []):
            video_ids.append(item["id"]["videoId"])

        remaining -= batch_size
        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    return video_ids


def extract_tags(videos_data):
    """Extract and count all tags across videos."""
    tag_counter = Counter()
    for v in videos_data:
        for tag in v.get("tags", []):
            tag_counter[tag.lower()] += 1
    return tag_counter.most_common(50)


def classify_format(duration_sec):
    """Classify video format based on duration."""
    if duration_sec <= 60:
        return "Short"
    if duration_sec <= 180:
        return "Short-form"
    if duration_sec <= 600:
        return "Medium (5-10 min)"
    if duration_sec <= 1200:
        return "Standard (10-20 min)"
    if duration_sec <= 2400:
        return "Long-form (20-40 min)"
    return "Deep-dive (40+ min)"


def analyze_title_patterns(titles):
    """Analyze common patterns in video titles."""
    patterns = {
        "has_number": 0,
        "is_question": 0,
        "has_how_to": 0,
        "has_brackets": 0,
        "has_caps_word": 0,
        "has_emoji": 0,
        "has_year": 0,
        "has_list_format": 0,
        "has_vs": 0,
        "has_review": 0,
        "avg_length": 0,
        "common_words": [],
    }

    word_counter = Counter()

    for title in titles:
        if re.search(r"\d", title):
            patterns["has_number"] += 1
        if title.rstrip().endswith("?"):
            patterns["is_question"] += 1
        if re.search(r"how\s+to", title, re.I):
            patterns["has_how_to"] += 1
        if re.search(r"[\[\(]", title):
            patterns["has_brackets"] += 1
        if re.search(r"\b[A-Z]{2,}\b", title):
            patterns["has_caps_word"] += 1
        if re.search(r"[^\w\s,.\-!?\'\"()\[\]:;/\\@#$%^&*+=~`|<>]", title):
            patterns["has_emoji"] += 1
        if re.search(r"20[12]\d", title):
            patterns["has_year"] += 1
        if re.search(r"^\d+\s", title):
            patterns["has_list_format"] += 1
        if re.search(r"\bvs\.?\b", title, re.I):
            patterns["has_vs"] += 1
        if re.search(r"\breview\b", title, re.I):
            patterns["has_review"] += 1

        for w in re.findall(r"[a-zA-Z]{3,}", title.lower()):
            if w not in STOP_WORDS:
                word_counter[w] += 1

    total = len(titles) or 1
    patterns["avg_length"] = round(sum(len(t) for t in titles) / total, 1)
    patterns["common_words"] = word_counter.most_common(20)

    for key in ("has_number", "is_question", "has_how_to", "has_brackets",
                "has_caps_word", "has_emoji", "has_year", "has_list_format",
                "has_vs", "has_review"):
        patterns[key] = round(patterns[key] / total * 100, 1)

    return patterns


def percentile(sorted_values, pct):
    if not sorted_values:
        return 0
    idx = min(int(round((pct / 100.0) * (len(sorted_values) - 1))), len(sorted_values) - 1)
    return sorted_values[idx]


def main():
    parser = argparse.ArgumentParser(description="Research a YouTube topic")
    parser.add_argument("topic", help="Topic or keyword to research")
    parser.add_argument("--max-results", type=int, default=50,
                        help="Max videos per search ordering (default: 50, max: 100)")
    parser.add_argument("--reports-dir", default="reports",
                        help="Root output directory (default: reports)")
    args = parser.parse_args()

    api_key = require_api_key()
    max_results = min(args.max_results, 100)
    youtube = build("youtube", "v3", developerKey=api_key)
    quota = QuotaTracker()

    print(f"Researching topic: {args.topic}")
    print(f"Target: {max_results} videos per ordering\n")

    print("Searching by relevance...")
    relevance_ids = search_videos(youtube, args.topic, max_results, quota, order="relevance")
    print(f"  Found {len(relevance_ids)} videos by relevance")

    print("Searching by view count...")
    viewcount_ids = search_videos(youtube, args.topic, max_results, quota, order="viewCount")
    print(f"  Found {len(viewcount_ids)} videos by view count")

    print("Searching recent uploads...")
    recent_ids = search_videos(youtube, args.topic, 25, quota, order="date")
    print(f"  Found {len(recent_ids)} recent videos")

    all_ids = list(dict.fromkeys(relevance_ids + viewcount_ids + recent_ids))
    print(f"\nTotal unique videos: {len(all_ids)}")

    print("Fetching video details...")
    raw_videos = batch_video_details(youtube, all_ids, quota)
    print(f"  Got details for {len(raw_videos)} videos")

    channel_ids = [v["snippet"]["channelId"] for v in raw_videos]
    print("Fetching channel details...")
    channels = batch_channel_details(youtube, channel_ids, quota)
    print(f"  Got details for {len(channels)} channels")

    videos_data = []
    for v in raw_videos:
        duration_sec = parse_duration(v.get("contentDetails", {}).get("duration", ""))
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        channel_id = v["snippet"]["channelId"]
        channel_subs = channels.get(channel_id, {}).get("subscribers", 0)
        age = days_ago(v["snippet"]["publishedAt"])

        videos_data.append({
            "video_id": v["id"],
            "title": v["snippet"]["title"],
            "channel_id": channel_id,
            "channel_name": v["snippet"]["channelTitle"],
            "channel_subs": channel_subs,
            "published_at": v["snippet"]["publishedAt"],
            "age_days": int(age),
            "views": views,
            "likes": likes,
            "comments": comments,
            "duration_sec": duration_sec,
            "format": classify_format(duration_sec),
            "tags": v.get("snippet", {}).get("tags", []),
            "description_preview": v["snippet"].get("description", "")[:200],
            "velocity": round(views / max(age, 1.0), 1),
            "outlier_score": round(views / channel_subs, 2) if channel_subs > 0 else 0,
            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
            "like_rate": round(likes / max(views, 1) * 100, 2),
        })

    videos_data.sort(key=lambda x: x["views"], reverse=True)

    views_list = sorted(v["views"] for v in videos_data)
    total_views = sum(views_list)
    avg_views = round(total_views / len(views_list)) if views_list else 0
    median_views = percentile(views_list, 50)

    format_counts = Counter(v["format"] for v in videos_data)
    format_performance = {}
    for fmt in format_counts:
        vids = [v for v in videos_data if v["format"] == fmt]
        format_performance[fmt] = {
            "count": len(vids),
            "avg_views": round(sum(v["views"] for v in vids) / len(vids)),
            "avg_engagement": round(sum(v["engagement_rate"] for v in vids) / len(vids), 2),
        }

    durations = [v["duration_sec"] for v in videos_data if v["duration_sec"] > 0]
    avg_duration = round(sum(durations) / len(durations)) if durations else 0

    title_patterns = analyze_title_patterns([v["title"] for v in videos_data])
    tag_cloud = extract_tags(videos_data)

    channel_counter = Counter(v["channel_id"] for v in videos_data)
    unique_channels = len(channel_counter)
    top_channels = channel_counter.most_common(10)

    outlier_threshold = median_views * 5
    outliers = [v for v in videos_data if v["views"] > outlier_threshold]

    channel_sizes = {"micro (<10K)": 0, "small (10K-100K)": 0,
                     "medium (100K-1M)": 0, "large (1M+)": 0}
    for v in videos_data:
        subs = v["channel_subs"]
        if subs < 10_000:
            channel_sizes["micro (<10K)"] += 1
        elif subs < 100_000:
            channel_sizes["small (10K-100K)"] += 1
        elif subs < 1_000_000:
            channel_sizes["medium (100K-1M)"] += 1
        else:
            channel_sizes["large (1M+)"] += 1

    age_buckets = {"last_7_days": 0, "last_30_days": 0, "last_90_days": 0,
                   "last_year": 0, "older": 0}
    for v in videos_data:
        age = v["age_days"]
        if age <= 7:
            age_buckets["last_7_days"] += 1
        elif age <= 30:
            age_buckets["last_30_days"] += 1
        elif age <= 90:
            age_buckets["last_90_days"] += 1
        elif age <= 365:
            age_buckets["last_year"] += 1
        else:
            age_buckets["older"] += 1

    data_path, report_path = report_paths(args.reports_dir, "topic-research", slugify(args.topic))

    output = {
        "topic": args.topic,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_videos_analyzed": len(videos_data),
        "summary": {
            "total_views": total_views,
            "avg_views": avg_views,
            "median_views": median_views,
            "avg_duration_sec": avg_duration,
            "avg_engagement_rate": round(
                sum(v["engagement_rate"] for v in videos_data) / len(videos_data), 2
            ) if videos_data else 0,
            "unique_channels": unique_channels,
        },
        "view_percentiles": {
            "p25": percentile(views_list, 25),
            "p50": percentile(views_list, 50),
            "p75": percentile(views_list, 75),
            "p90": percentile(views_list, 90),
        },
        "format_distribution": dict(format_counts.most_common()),
        "format_performance": format_performance,
        "channel_size_distribution": channel_sizes,
        "age_distribution": age_buckets,
        "title_patterns": title_patterns,
        "tag_cloud": tag_cloud,
        "top_channels": [
            {
                "channel_id": cid,
                "channel_name": channels.get(cid, {}).get("title", "Unknown"),
                "subscribers": channels.get(cid, {}).get("subscribers", 0),
                "videos_in_results": count,
            }
            for cid, count in top_channels
        ],
        "outlier_videos": [
            {
                "title": v["title"],
                "video_id": v["video_id"],
                "views": v["views"],
                "channel_name": v["channel_name"],
                "channel_subs": v["channel_subs"],
                "outlier_score": v["outlier_score"],
                "age_days": v["age_days"],
            }
            for v in outliers[:10]
        ],
        "top_videos": [
            {
                "title": v["title"],
                "video_id": v["video_id"],
                "views": v["views"],
                "likes": v["likes"],
                "comments": v["comments"],
                "channel_name": v["channel_name"],
                "channel_subs": v["channel_subs"],
                "duration_sec": v["duration_sec"],
                "format": v["format"],
                "engagement_rate": v["engagement_rate"],
                "velocity": v["velocity"],
                "age_days": v["age_days"],
                "published_at": v["published_at"],
            }
            for v in videos_data[:20]
        ],
        "all_videos": videos_data,
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, output)

    print(f"\nData saved to: {data_path}")
    print(f"Write the markdown report to: {report_path}")
    print(f"Videos analyzed: {len(videos_data)}")
    print(f"Unique channels: {unique_channels}")
    quota.report()


if __name__ == "__main__":
    main()
