#!/usr/bin/env python3
"""YouTube Own Channel Analyzer -- data collection.

Resolves a channel, lists its uploads, and computes content-type mix, duration
distribution, engagement metrics against benchmarks, upload patterns, and title
patterns. Writes structured JSON for the channel health report.

Usage:
    YT_API_KEY=KEY python3 analyze_channel.py @MyChannel
    YT_API_KEY=KEY python3 analyze_channel.py UCxxxxxxxxxxxxxxxxxxxxxx --max-videos 300
"""

import argparse
import json
import os
import re
import statistics
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
# Channel analysis
# ---------------------------------------------------------------------------

# Benchmarks documented in SKILL.md -- emitted so the report can compare directly.
BENCHMARKS = {
    "view_to_sub_ratio_pct": [10, 20],
    "engagement_rate_pct": [1, 5],
    "like_rate_pct": [3, 7],
    "comment_rate_pct": [0.5, 2],
    "viral_multiple_of_subs": 5,
    "underperforming_pct_of_subs": 10,
}

CONTENT_TYPE_PATTERNS = [
    ("Tutorial", r"\b(tutorial|how\s+to|guide|learn)\b"),
    ("Review", r"\b(review|unbox|first look|comparison)\b"),
    ("Vlog", r"\b(vlog|day in|life|daily)\b"),
    ("Educational", r"\b(explain|education|lesson)\b"),
    ("Gaming", r"\b(gameplay|game|gaming|stream)\b"),
    ("Music", r"\b(music|song|cover|lyrics)\b"),
]

STOP_WORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "you", "your", "my", "this", "that", "i", "me", "we",
    "how", "what", "why", "do", "does", "can", "will", "be", "are", "was",
    "not", "no", "so", "if",
}


def classify_content_type(title, description, tags):
    """Categorize a video by title/description/tag patterns."""
    combined = f"{title} {description[:300]} {' '.join(tags)}".lower()
    for label, pattern in CONTENT_TYPE_PATTERNS:
        if re.search(pattern, combined):
            return label
    return "Other"


def duration_bucket(seconds):
    """Short (<5min), Medium (5-15min), Long (15-30min), Very Long (30+min)."""
    if seconds < 300:
        return "Short (<5 min)"
    if seconds < 900:
        return "Medium (5-15 min)"
    if seconds < 1800:
        return "Long (15-30 min)"
    return "Very Long (30+ min)"


def analyze_titles(titles):
    """Title pattern rates plus the most common non-stopword terms."""
    counts = {
        "has_number": 0, "has_emoji": 0, "is_question": 0,
        "has_brackets": 0, "has_caps_word": 0, "has_how_to": 0,
    }
    word_counter = Counter()

    for title in titles:
        if re.search(r"\d", title):
            counts["has_number"] += 1
        if re.search(r"[^\w\s,.\-!?\'\"()\[\]:;/\\@#$%^&*+=~`|<>]", title):
            counts["has_emoji"] += 1
        if title.rstrip().endswith("?"):
            counts["is_question"] += 1
        if re.search(r"[\[\(]", title):
            counts["has_brackets"] += 1
        if re.search(r"\b[A-Z]{2,}\b", title):
            counts["has_caps_word"] += 1
        if re.search(r"how\s+to", title, re.I):
            counts["has_how_to"] += 1
        for w in re.findall(r"[a-zA-Z]{3,}", title.lower()):
            if w not in STOP_WORDS:
                word_counter[w] += 1

    total = len(titles) or 1
    result = {k: round(v / total * 100, 1) for k, v in counts.items()}
    result["avg_length_chars"] = round(sum(len(t) for t in titles) / total, 1)
    result["avg_length_words"] = round(sum(len(t.split()) for t in titles) / total, 1)
    result["common_words"] = word_counter.most_common(20)
    return result


def upload_patterns(published_dates):
    """Day/hour distribution and consistency (stddev of days between uploads)."""
    if not published_dates:
        return {}
    dates = sorted(published_dates)
    day_counter = Counter(d.strftime("%A") for d in dates)
    hour_counter = Counter(d.hour for d in dates)

    gaps = [(dates[i + 1] - dates[i]).total_seconds() / 86400 for i in range(len(dates) - 1)]
    avg_gap = round(sum(gaps) / len(gaps), 2) if gaps else 0
    gap_stddev = round(statistics.pstdev(gaps), 2) if len(gaps) > 1 else 0

    return {
        "by_day": day_counter.most_common(),
        "by_hour_utc": sorted(hour_counter.items()),
        "best_day": day_counter.most_common(1)[0][0] if day_counter else None,
        "best_hour_utc": hour_counter.most_common(1)[0][0] if hour_counter else None,
        "avg_days_between_uploads": avg_gap,
        "consistency_stddev_days": gap_stddev,
        "uploads_per_week": round(7 / avg_gap, 2) if avg_gap > 0 else 0,
        "first_upload": dates[0].isoformat(),
        "latest_upload": dates[-1].isoformat(),
    }


def group_performance(videos, key):
    """Count + average views/engagement for each value of `key`."""
    out = {}
    for value in Counter(v[key] for v in videos):
        group = [v for v in videos if v[key] == value]
        out[value] = {
            "count": len(group),
            "pct": round(len(group) / len(videos) * 100, 1),
            "avg_views": round(sum(v["views"] for v in group) / len(group)),
            "avg_engagement_rate": round(
                sum(v["engagement_rate"] for v in group) / len(group), 2
            ),
        }
    return out


def main():
    parser = argparse.ArgumentParser(description="Analyze your own YouTube channel")
    parser.add_argument("channel", help="Channel @handle, URL, or ID (UCxxxxxxx)")
    parser.add_argument("--max-videos", type=int, default=200,
                        help="How many recent uploads to analyze (default: 200, 0 = all)")
    parser.add_argument("--reports-dir", default="reports",
                        help="Root output directory (default: reports)")
    args = parser.parse_args()

    api_key = require_api_key()
    youtube = build("youtube", "v3", developerKey=api_key)
    quota = QuotaTracker()

    print(f"Resolving channel: {args.channel}")
    channel = resolve_channel_id(youtube, args.channel, quota)
    if not channel:
        print("ERROR: Could not resolve channel. Check the handle/URL/ID.", file=sys.stderr)
        sys.exit(1)
    print(f"  Found: {channel['title']} ({format_number(channel['subscribers'])} subs, "
          f"{channel['video_count']} videos)")

    print("Listing uploads...")
    uploads = list_uploads(youtube, channel["uploads_playlist"], quota,
                           max_items=args.max_videos or None)
    print(f"  Found {len(uploads)} uploads")

    print("Fetching video details...")
    raw_videos = batch_video_details(youtube, [u["video_id"] for u in uploads], quota)
    print(f"  Got {len(raw_videos)} videos")

    if not raw_videos:
        print("ERROR: No videos found for this channel.", file=sys.stderr)
        sys.exit(1)

    subs = channel["subscribers"]
    videos = []
    published_dates = []

    for v in raw_videos:
        snippet = v["snippet"]
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        duration = parse_duration(v.get("contentDetails", {}).get("duration", ""))
        tags = snippet.get("tags", [])
        age = max(days_ago(snippet["publishedAt"]), 0.1)

        try:
            published_dates.append(
                datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
            )
        except ValueError:
            pass

        videos.append({
            "video_id": v["id"],
            "title": snippet["title"],
            "published_at": snippet["publishedAt"],
            "age_days": round(age, 1),
            "views": views,
            "likes": likes,
            "comments": comments,
            "duration_sec": duration,
            "content_type": classify_content_type(snippet["title"],
                                                  snippet.get("description", ""), tags),
            "duration_bucket": duration_bucket(duration),
            "tags": tags,
            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
            "like_rate": round(likes / max(views, 1) * 100, 2),
            "comment_rate": round(comments / max(views, 1) * 100, 2),
            "view_to_sub_ratio": round(views / subs * 100, 2) if subs else 0,
            "velocity": round(views / age),
            "is_viral": bool(subs and views > subs * BENCHMARKS["viral_multiple_of_subs"]),
            "is_underperforming": bool(
                subs and views < subs * BENCHMARKS["underperforming_pct_of_subs"] / 100
            ),
        })

    videos.sort(key=lambda x: x["published_at"], reverse=True)
    n = len(videos)

    total_views_sampled = sum(v["views"] for v in videos)
    performance = {
        "videos_analyzed": n,
        "total_views_sampled": total_views_sampled,
        "avg_views": round(total_views_sampled / n),
        "median_views": sorted(v["views"] for v in videos)[n // 2],
        "avg_engagement_rate": round(sum(v["engagement_rate"] for v in videos) / n, 2),
        "avg_like_rate": round(sum(v["like_rate"] for v in videos) / n, 2),
        "avg_comment_rate": round(sum(v["comment_rate"] for v in videos) / n, 2),
        "avg_view_to_sub_ratio": round(sum(v["view_to_sub_ratio"] for v in videos) / n, 2),
        "avg_duration_sec": round(sum(v["duration_sec"] for v in videos) / n),
        "viral_videos": sum(1 for v in videos if v["is_viral"]),
        "underperforming_videos": sum(1 for v in videos if v["is_underperforming"]),
    }

    by_engagement = sorted(videos, key=lambda x: x["engagement_rate"], reverse=True)
    summary_fields = ("video_id", "title", "views", "likes", "comments",
                      "engagement_rate", "content_type", "duration_sec", "published_at")

    def summarize(items):
        return [{k: v[k] for k in summary_fields} for v in items]

    slug = slugify(channel.get("handle") or channel["title"])
    data_path, report_path = report_paths(args.reports_dir, "channel-analysis", slug)

    output = {
        "channel": channel,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "benchmarks": BENCHMARKS,
        "performance": performance,
        "content_types": group_performance(videos, "content_type"),
        "duration_distribution": group_performance(videos, "duration_bucket"),
        "upload_patterns": upload_patterns(published_dates),
        "title_analysis": analyze_titles([v["title"] for v in videos]),
        "top_by_views": summarize(sorted(videos, key=lambda x: x["views"], reverse=True)[:10]),
        "top_by_engagement": summarize(by_engagement[:5]),
        "needs_improvement": summarize(by_engagement[-5:][::-1]),
        "recent_videos": summarize(videos[:20]),
        "all_videos": videos,
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, output)

    print(f"\nData saved to: {data_path}")
    print(f"Write the markdown report to: {report_path}")
    print(f"Videos analyzed: {n}")
    print(f"Avg views: {format_number(performance['avg_views'])} | "
          f"Avg engagement: {performance['avg_engagement_rate']}%")
    print(f"Viral: {performance['viral_videos']} | "
          f"Underperforming: {performance['underperforming_videos']}")
    quota.report()


if __name__ == "__main__":
    main()
