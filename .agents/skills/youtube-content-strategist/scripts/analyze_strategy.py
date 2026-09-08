#!/usr/bin/env python3
"""YouTube Content Strategist -- data collection.

Analyzes a channel's performance plus niche benchmarks and writes structured
JSON used to build a content strategy and 30-day calendar.

Usage:
    YT_API_KEY=KEY python3 analyze_strategy.py @MyChannel --niche "productivity"
    YT_API_KEY=KEY python3 analyze_strategy.py UCxxxx --niche "fitness" --uploads-per-week 3
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
# Strategy analysis
# ---------------------------------------------------------------------------

def fetch_playlists(youtube, channel_id, quota):
    """List a channel's playlists (1 unit per 50)."""
    playlists = []
    next_page = None
    while True:
        try:
            resp = youtube.playlists().list(
                part="snippet,contentDetails", channelId=channel_id,
                maxResults=50, pageToken=next_page,
            ).execute()
            quota.record("playlists.list")
        except HttpError as e:
            check_quota_error(e)
            print(f"  playlists.list error: {e}", file=sys.stderr)
            break
        for item in resp.get("items", []):
            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "video_count": item["contentDetails"]["itemCount"],
            })
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
    return playlists


def classify_content(title, tags, duration_sec):
    """Bucket a video into a content type and duration band."""
    combined = f"{title.lower()} {' '.join(t.lower() for t in tags)}"

    content_type = "other"
    if duration_sec <= 60:
        content_type = "short"
    elif re.search(r"\b(tutorial|how to|guide|learn|step by step)\b", combined):
        content_type = "tutorial"
    elif re.search(r"\b(review|unbox|first look|hands on|comparison)\b", combined):
        content_type = "review"
    elif re.search(r"\b(vlog|day in|daily|life|routine)\b", combined):
        content_type = "vlog"
    elif re.search(r"\b(tips|tricks|hack|mistakes|advice)\b", combined):
        content_type = "tips"
    elif re.search(r"\b(interview|podcast|conversation|talk|chat with|feat)\b", combined):
        content_type = "interview"
    elif re.search(r"\b(news|update|announcement|breaking|latest)\b", combined):
        content_type = "news"
    elif re.search(r"\b(challenge|experiment|test|try|attempt)\b", combined):
        content_type = "challenge"
    elif re.search(r"\b(top \d|best \d|\d+ best|\d+ ways|\d+ things)\b", combined):
        content_type = "listicle"
    elif re.search(r"\b(story|experience|journey|honest|real|truth)\b", combined):
        content_type = "storytelling"

    duration_bucket = "short"
    if duration_sec > 1800:
        duration_bucket = "long (30+ min)"
    elif duration_sec > 900:
        duration_bucket = "standard (15-30 min)"
    elif duration_sec > 300:
        duration_bucket = "medium (5-15 min)"
    elif duration_sec > 60:
        duration_bucket = "short-form (1-5 min)"

    return {"content_type": content_type, "duration_bucket": duration_bucket}


def niche_benchmark(youtube, niche, quota):
    """Sample the niche's top videos for benchmark numbers (keyword search)."""
    try:
        resp = youtube.search().list(
            part="snippet", q=niche, type="video",
            order="viewCount", maxResults=50,
        ).execute()
        quota.record("search.list")
        niche_ids = [item["id"]["videoId"] for item in resp.get("items", [])]
    except HttpError as e:
        check_quota_error(e)
        print(f"  search.list error: {e}", file=sys.stderr)
        niche_ids = []

    niche_videos = []
    if niche_ids:
        for v in batch_video_details(youtube, niche_ids, quota):
            niche_videos.append({
                "views": int(v.get("statistics", {}).get("viewCount", 0) or 0),
                "duration_sec": parse_duration(v.get("contentDetails", {}).get("duration", "")),
                "title": v["snippet"]["title"],
            })

    return {
        "avg_views": round(sum(v["views"] for v in niche_videos) / max(len(niche_videos), 1)),
        "avg_duration": round(sum(v["duration_sec"] for v in niche_videos) / max(len(niche_videos), 1)),
        "sample_size": len(niche_videos),
    }


def main():
    parser = argparse.ArgumentParser(description="YouTube content strategy generator")
    parser.add_argument("channel", help="Channel @handle, URL, or ID")
    parser.add_argument("--niche", required=True, help="Niche/topic keyword")
    parser.add_argument("--uploads-per-week", type=int, default=0,
                        help="Target upload frequency (default: auto-detect from history)")
    parser.add_argument("--max-videos", type=int, default=200,
                        help="How many recent uploads to analyze (default: 200)")
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
    print(f"  Found: {channel['title']} ({format_number(channel['subscribers'])} subs)")

    print(f"Fetching channel uploads (last {args.max_videos})...")
    playlist_items = list_uploads(youtube, channel["uploads_playlist"], quota,
                                  max_items=args.max_videos)
    vid_ids = [v["video_id"] for v in playlist_items]
    print(f"  Found {len(vid_ids)} videos")

    print("Fetching video details...")
    raw_videos = batch_video_details(youtube, vid_ids, quota)
    print(f"  Got {len(raw_videos)} videos")

    if not raw_videos:
        print("ERROR: No videos found for this channel.", file=sys.stderr)
        sys.exit(1)

    channel_videos = []
    for v in raw_videos:
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        duration = parse_duration(v.get("contentDetails", {}).get("duration", ""))
        tags = v.get("snippet", {}).get("tags", [])
        title = v["snippet"]["title"]
        classification = classify_content(title, tags, duration)
        age = max(days_ago(v["snippet"]["publishedAt"]), 0.1)

        channel_videos.append({
            "video_id": v["id"],
            "title": title,
            "views": views,
            "likes": likes,
            "comments": comments,
            "duration_sec": duration,
            "published_at": v["snippet"]["publishedAt"],
            "age_days": round(age, 1),
            "tags": tags,
            "content_type": classification["content_type"],
            "duration_bucket": classification["duration_bucket"],
            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
            "velocity": round(views / age),
        })

    channel_videos.sort(key=lambda x: x["published_at"], reverse=True)

    type_counter = Counter(v["content_type"] for v in channel_videos)
    type_performance = {}
    for ct in type_counter:
        vids = [v for v in channel_videos if v["content_type"] == ct]
        type_performance[ct] = {
            "count": len(vids),
            "pct": round(len(vids) / len(channel_videos) * 100, 1),
            "avg_views": round(sum(v["views"] for v in vids) / len(vids)),
            "avg_engagement": round(sum(v["engagement_rate"] for v in vids) / len(vids), 2),
            "total_views": sum(v["views"] for v in vids),
        }

    shorts = [v for v in channel_videos if v["content_type"] == "short"]
    longform = [v for v in channel_videos if v["content_type"] != "short"]
    shorts_analysis = {
        "count": len(shorts),
        "pct": round(len(shorts) / max(len(channel_videos), 1) * 100, 1),
        "avg_views": round(sum(v["views"] for v in shorts) / max(len(shorts), 1)),
        "avg_engagement": round(sum(v["engagement_rate"] for v in shorts) / max(len(shorts), 1), 2),
    }
    longform_analysis = {
        "count": len(longform),
        "pct": round(len(longform) / max(len(channel_videos), 1) * 100, 1),
        "avg_views": round(sum(v["views"] for v in longform) / max(len(longform), 1)),
        "avg_engagement": round(sum(v["engagement_rate"] for v in longform) / max(len(longform), 1), 2),
    }

    duration_counter = Counter(v["duration_bucket"] for v in channel_videos)
    duration_performance = {}
    for db in duration_counter:
        vids = [v for v in channel_videos if v["duration_bucket"] == db]
        duration_performance[db] = {
            "count": len(vids),
            "avg_views": round(sum(v["views"] for v in vids) / len(vids)),
        }

    if len(channel_videos) >= 2:
        dates = sorted(
            datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
            for v in channel_videos
        )
        gaps = [(dates[i + 1] - dates[i]).total_seconds() / 86400 for i in range(len(dates) - 1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 7
        uploads_per_week = round(7 / max(avg_gap, 0.1), 1)
        day_counter = Counter(d.strftime("%A") for d in dates)
        hour_counter = Counter(d.hour for d in dates)
    else:
        avg_gap = 7
        uploads_per_week = 1
        day_counter = Counter()
        hour_counter = Counter()

    avg_views = sum(v["views"] for v in channel_videos) / max(len(channel_videos), 1)
    sequel_candidates = [
        v for v in channel_videos if v["views"] > avg_views * 2 and v["age_days"] > 60
    ]
    sequel_candidates.sort(key=lambda x: x["views"], reverse=True)

    print(f"\nFetching niche benchmark data for: {args.niche}")
    benchmark = niche_benchmark(youtube, args.niche, quota)

    print("Fetching playlists...")
    playlists = fetch_playlists(youtube, channel["id"], quota)

    target_uploads = args.uploads_per_week if args.uploads_per_week > 0 else round(uploads_per_week)
    slug = slugify(channel.get("handle") or channel["title"])
    data_path, report_path = report_paths(args.reports_dir, "content-strategy", slug)

    output = {
        "channel": channel,
        "niche": args.niche,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_videos_analyzed": len(channel_videos),
        "content_pillars": type_performance,
        "shorts_vs_longform": {"shorts": shorts_analysis, "longform": longform_analysis},
        "duration_performance": duration_performance,
        "upload_schedule": {
            "current_uploads_per_week": uploads_per_week,
            "target_uploads_per_week": target_uploads,
            "avg_days_between_uploads": round(avg_gap, 1),
            "preferred_days": day_counter.most_common(3),
            "preferred_hours": hour_counter.most_common(3),
        },
        "sequel_opportunities": [
            {"title": v["title"], "video_id": v["video_id"], "views": v["views"],
             "age_days": v["age_days"], "content_type": v["content_type"]}
            for v in sequel_candidates[:10]
        ],
        "niche_benchmark": benchmark,
        "playlists": playlists,
        "top_performing": [
            {"title": v["title"], "video_id": v["video_id"], "views": v["views"],
             "engagement_rate": v["engagement_rate"], "content_type": v["content_type"],
             "duration_sec": v["duration_sec"]}
            for v in sorted(channel_videos, key=lambda x: x["views"], reverse=True)[:10]
        ],
        "recent_videos": channel_videos[:20],
        "all_videos": channel_videos,
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, output)

    print(f"\nData saved to: {data_path}")
    print(f"Write the markdown report to: {report_path}")
    print(f"Videos analyzed: {len(channel_videos)}")
    print(f"Content types found: {len(type_counter)}")
    print(f"Current upload rate: {uploads_per_week}/week")
    print(f"Sequel opportunities: {len(sequel_candidates)}")
    quota.report()


if __name__ == "__main__":
    main()
