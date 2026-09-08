#!/usr/bin/env python3
"""YouTube Comment Miner -- data collection.

Fetches comments from YouTube videos and extracts structured data for content
idea mining, FAQ extraction, pain points, and monetization signals.

Usage:
    YT_API_KEY=KEY python3 mine_comments.py --videos VIDEO_ID1 VIDEO_ID2
    YT_API_KEY=KEY python3 mine_comments.py --channel @handle --top 5
    YT_API_KEY=KEY python3 mine_comments.py --topic "meditation" --top 10
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
# Comment mining
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "you", "your", "my", "this", "that", "i", "me", "we",
    "its", "was", "are", "be", "have", "has", "had", "do", "does", "did",
    "not", "so", "if", "just", "like", "can", "will", "about", "from", "they",
    "them", "would", "been", "very", "much", "more", "also", "all", "one",
    "get", "got", "really", "know", "think", "see", "make", "going", "want",
    "need", "even", "still", "way", "well", "too", "here", "when", "than",
    "some", "could",
}


def extract_video_id(url_or_id):
    """Extract a video ID from a watch/shorts/youtu.be URL, or pass through an ID."""
    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})", url_or_id)
    if m:
        return m.group(1)
    return url_or_id


def top_videos_from_channel(youtube, channel, top_n, quota, scan_limit=None):
    """Top N videos of a channel by view count, via the uploads playlist.

    Uses playlistItems.list (1 unit per 50) + videos.list (1 unit per 50) instead
    of search.list(channelId=..., order=viewCount), which costs 100 units and only
    ever sees a truncated slice of the channel.
    """
    uploads = list_uploads(youtube, channel["uploads_playlist"], quota, max_items=scan_limit)
    if not uploads:
        return [], {}
    details = batch_video_details(youtube, [u["video_id"] for u in uploads], quota,
                                  part="snippet,statistics")
    ranked = sorted(
        details,
        key=lambda v: int(v.get("statistics", {}).get("viewCount", 0) or 0),
        reverse=True,
    )
    top = ranked[:top_n]
    info = {
        v["id"]: {
            "title": v["snippet"]["title"],
            "channel": v["snippet"]["channelTitle"],
            "views": int(v.get("statistics", {}).get("viewCount", 0) or 0),
            "likes": int(v.get("statistics", {}).get("likeCount", 0) or 0),
            "comment_count": int(v.get("statistics", {}).get("commentCount", 0) or 0),
        }
        for v in top
    }
    return [v["id"] for v in top], info


def search_topic_videos(youtube, topic, top_n, quota):
    """Keyword search -- search.list is required here."""
    try:
        resp = youtube.search().list(
            part="snippet", q=topic, order="viewCount",
            type="video", maxResults=min(top_n, 50),
        ).execute()
        quota.record("search.list")
        return [item["id"]["videoId"] for item in resp.get("items", [])]
    except HttpError as e:
        check_quota_error(e)
        print(f"  search.list error: {e}", file=sys.stderr)
        return []


def fetch_video_info(youtube, video_ids, quota):
    """Basic video info keyed by video ID."""
    info = {}
    for item in batch_video_details(youtube, video_ids, quota, part="snippet,statistics"):
        stats = item.get("statistics", {})
        info[item["id"]] = {
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "views": int(stats.get("viewCount", 0) or 0),
            "likes": int(stats.get("likeCount", 0) or 0),
            "comment_count": int(stats.get("commentCount", 0) or 0),
        }
    return info


def fetch_comments(youtube, video_id, quota, max_comments=100):
    """Fetch top-level comments for a video (1 unit per 100 comments)."""
    comments = []
    next_page = None

    while len(comments) < max_comments:
        batch_size = min(max_comments - len(comments), 100)
        try:
            resp = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=batch_size,
                order="relevance",
                textFormat="plainText",
                pageToken=next_page,
            ).execute()
            quota.record("commentThreads.list")
        except HttpError as e:
            check_quota_error(e)
            if "commentsDisabled" in str(e):
                print(f"  Comments disabled for {video_id}")
            else:
                print(f"  commentThreads.list error for {video_id}: {e}", file=sys.stderr)
            break

        for item in resp.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": snippet["textDisplay"],
                "author": snippet["authorDisplayName"],
                "likes": snippet.get("likeCount", 0),
                "published_at": snippet["publishedAt"],
                "reply_count": item["snippet"]["totalReplyCount"],
            })

        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    return comments


def categorize_comment(text):
    """Categorize a comment into one or more types."""
    categories = []
    text_lower = text.lower()

    if "?" in text or re.search(r"\b(how|what|when|where|why|which|can you|could you|do you|is there|are there)\b", text_lower):
        categories.append("question")
    if re.search(r"\b(make a video|do a video|cover|tutorial on|video about|video on|please make|can you do|would love to see)\b", text_lower):
        categories.append("content_request")
    if re.search(r"\b(struggling|confused|frustrated|difficult|hard to|problem|issue|trouble|stuck|can't figure|don't understand|help me)\b", text_lower):
        categories.append("pain_point")
    if re.search(r"\b(thank|amazing|awesome|great|best|love this|helpful|saved|changed my|incredible|fantastic|brilliant)\b", text_lower):
        categories.append("praise")
    if re.search(r"\b(wrong|incorrect|disagree|bad|terrible|waste|misleading|clickbait|disappointing|worst)\b", text_lower):
        categories.append("criticism")
    if re.search(r"\b(should|suggest|recommend|try|instead|better if|would be nice|improvement|tip:|pro tip)\b", text_lower):
        categories.append("suggestion")
    if re.search(r"\b(course|buy|purchase|price|cost|paid|where can i get|link|affiliate|merch|membership|patreon|sponsor)\b", text_lower):
        categories.append("monetization_signal")
    if re.search(r"\b(i tried|i did|my experience|i started|i've been|in my case|for me|i found|i discovered|i realized)\b", text_lower):
        categories.append("personal_story")

    if not categories:
        categories.append("general")

    return categories


CATEGORY_BUCKETS = [
    ("question", "questions"),
    ("content_request", "content_requests"),
    ("pain_point", "pain_points"),
    ("praise", "praise"),
    ("criticism", "criticism"),
    ("suggestion", "suggestions"),
    ("monetization_signal", "monetization_signals"),
    ("personal_story", "personal_stories"),
]


def main():
    parser = argparse.ArgumentParser(description="Mine YouTube comments")
    parser.add_argument("--videos", nargs="*", help="Video IDs or URLs to mine")
    parser.add_argument("--channel", help="Channel @handle, URL, or ID")
    parser.add_argument("--topic", help="Topic to search for")
    parser.add_argument("--top", type=int, default=5,
                        help="Number of top videos to mine (channel/topic mode, default: 5)")
    parser.add_argument("--max-comments", type=int, default=100,
                        help="Max comments per video (default: 100, max: 500)")
    parser.add_argument("--scan-limit", type=int, default=0,
                        help="Channel mode: cap uploads scanned (0 = whole channel)")
    parser.add_argument("--reports-dir", default="reports",
                        help="Root output directory (default: reports)")
    args = parser.parse_args()

    api_key = require_api_key()
    youtube = build("youtube", "v3", developerKey=api_key)
    quota = QuotaTracker()
    max_comments = min(args.max_comments, 500)

    video_ids = []
    video_info = {}
    source_info = {}
    slug = "videos"

    if args.videos:
        video_ids = [extract_video_id(v) for v in args.videos]
        source_info = {"mode": "direct_videos", "count": len(video_ids)}
        slug = slugify(video_ids[0] if video_ids else "videos")
        print(f"Mining comments from {len(video_ids)} specified videos")

    elif args.channel:
        print(f"Resolving channel: {args.channel}")
        channel = resolve_channel_id(youtube, args.channel, quota)
        if not channel:
            print("ERROR: Could not resolve channel. Check the handle/URL/ID.", file=sys.stderr)
            sys.exit(1)
        print(f"  Found: {channel['title']} ({format_number(channel['subscribers'])} subscribers)")

        print(f"Scanning uploads to find the top {args.top} videos by views...")
        video_ids, video_info = top_videos_from_channel(
            youtube, channel, args.top, quota, scan_limit=args.scan_limit or None
        )
        source_info = {"mode": "channel", "channel": channel["title"],
                       "channel_id": channel["id"], "subscribers": channel["subscribers"]}
        slug = slugify(channel.get("handle") or channel["title"])
        print(f"  Got {len(video_ids)} videos")

    elif args.topic:
        print(f"Searching topic: {args.topic}")
        video_ids = search_topic_videos(youtube, args.topic, args.top, quota)
        source_info = {"mode": "topic", "topic": args.topic}
        slug = slugify(args.topic)
        print(f"  Found {len(video_ids)} videos")

    else:
        print("ERROR: Provide --videos, --channel, or --topic", file=sys.stderr)
        sys.exit(1)

    if not video_ids:
        print("No videos found. Exiting.", file=sys.stderr)
        sys.exit(1)

    if not video_info:
        print("\nFetching video details...")
        video_info = fetch_video_info(youtube, video_ids, quota)

    all_comments = {}
    total_comments = 0
    for vid_id in video_ids:
        title = video_info.get(vid_id, {}).get("title", "Unknown")
        print(f"\nMining: {title[:60]}...")
        comments = fetch_comments(youtube, vid_id, quota, max_comments)
        all_comments[vid_id] = comments
        total_comments += len(comments)
        print(f"  Got {len(comments)} comments")

    print("\nCategorizing comments...")
    categorized = {bucket: [] for _, bucket in CATEGORY_BUCKETS}
    categorized["gold_nuggets"] = []

    category_counts = Counter()
    word_counter = Counter()

    for vid_id, comments in all_comments.items():
        vid_info = video_info.get(vid_id, {})
        for comment in comments:
            cats = categorize_comment(comment["text"])
            entry = {
                "text": comment["text"][:500],
                "author": comment["author"],
                "likes": comment["likes"],
                "reply_count": comment["reply_count"],
                "video_id": vid_id,
                "video_title": vid_info.get("title", "Unknown"),
            }

            for cat in cats:
                category_counts[cat] += 1
            for cat, bucket in CATEGORY_BUCKETS:
                if cat in cats:
                    categorized[bucket].append(entry)

            if comment["likes"] >= 5 and ("question" in cats or "content_request" in cats):
                categorized["gold_nuggets"].append(entry)

            for w in re.findall(r"[a-zA-Z]{3,}", comment["text"].lower()):
                if w not in STOP_WORDS:
                    word_counter[w] += 1

    for bucket in categorized:
        categorized[bucket].sort(key=lambda x: x["likes"], reverse=True)
        categorized[bucket] = categorized[bucket][:25]

    data_path, report_path = report_paths(args.reports_dir, "comment-mine", slug)

    output = {
        "source": source_info,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_videos": len(video_ids),
        "total_comments_mined": total_comments,
        "video_info": {vid: video_info.get(vid, {}) for vid in video_ids},
        "category_counts": dict(category_counts.most_common()),
        "categorized_comments": categorized,
        "audience_language": word_counter.most_common(40),
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, output)

    print(f"\nData saved to: {data_path}")
    print(f"Write the markdown report to: {report_path}")
    print(f"Total comments mined: {total_comments}")
    print(f"Questions found: {category_counts.get('question', 0)}")
    print(f"Content requests: {category_counts.get('content_request', 0)}")
    print(f"Pain points: {category_counts.get('pain_point', 0)}")
    print(f"Gold nuggets: {len(categorized['gold_nuggets'])}")
    quota.report()


if __name__ == "__main__":
    main()
