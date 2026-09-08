#!/usr/bin/env python3
"""YouTube Competitor Analyzer -- discovery + comparative data collection.

Discovers competitor channels by keyword/content similarity (or takes them
directly), fetches comparative metrics and recent-content signals, ranks them
against the user's channel, and writes structured JSON for the report.

Usage:
    YT_API_KEY=KEY python3 analyze_competitors.py --channel @MyChannel
    YT_API_KEY=KEY python3 analyze_competitors.py --channel @MyChannel --keywords "meditation" "mindfulness"
    YT_API_KEY=KEY python3 analyze_competitors.py --competitors @rivalA @rivalB UCxxxx
"""

import argparse
import json
import math
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
# Competitor discovery + comparison
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "you", "your", "my", "this", "that", "i", "me", "we",
    "how", "what", "why", "do", "does", "can", "will", "be", "are", "was",
    "not", "no", "so", "if", "from", "about", "channel", "video", "videos",
    "subscribe", "youtube", "new", "best", "top",
}


def derive_keywords(channel, recent_titles, limit=3):
    """Build discovery queries from channel keywords, description, and title terms."""
    queries = []

    for kw in re.findall(r'"([^"]+)"|(\S+)', channel.get("keywords", "")):
        term = (kw[0] or kw[1]).strip().lower()
        if len(term) > 4 and term not in STOP_WORDS:
            queries.append(term)

    word_counter = Counter()
    for text in [channel.get("description", "")] + recent_titles:
        for w in re.findall(r"[a-zA-Z]{5,}", text.lower()):
            if w not in STOP_WORDS:
                word_counter[w] += 1
    queries.extend(w for w, _ in word_counter.most_common(10))

    deduped = list(dict.fromkeys(queries))
    return deduped[:limit]


def search_channels(youtube, query, quota, max_results=10):
    """Channel discovery -- one of the few legitimate uses of search.list."""
    try:
        resp = youtube.search().list(
            part="snippet", q=query, type="channel",
            maxResults=min(max_results, 50),
        ).execute()
        quota.record("search.list")
        return [item["snippet"]["channelId"] for item in resp.get("items", [])]
    except HttpError as e:
        check_quota_error(e)
        print(f"  search.list error for '{query}': {e}", file=sys.stderr)
        return []


def channel_metrics(channel):
    """Derived comparison metrics for one channel."""
    subs = channel["subscribers"]
    views = channel["total_views"]
    count = channel["video_count"]
    age_days = days_ago(channel.get("created_at", ""))
    months = max(age_days / 30.44, 1)

    return {
        "channel_id": channel["id"],
        "channel_name": channel["title"],
        "handle": channel.get("handle", ""),
        "country": channel.get("country", ""),
        "subscribers": subs,
        "total_views": views,
        "video_count": count,
        "views_per_video": round(views / max(count, 1)),
        "views_per_sub": round(views / subs, 2) if subs else 0,
        "uploads_per_month": round(count / months, 2),
        "channel_age_days": int(age_days),
        "created_at": channel.get("created_at", ""),
    }


def size_similarity(comp_subs, target_subs):
    """Log-scale size closeness, 0-1 (from the skill's documented formula)."""
    return max(
        0.0,
        1 - abs(math.log10(comp_subs + 1) - math.log10(target_subs + 1)) / 10,
    )


def recent_content_profile(youtube, channel, quota, sample=25):
    """Sample a competitor's recent uploads via playlistItems (1 unit/page)."""
    uploads = list_uploads(youtube, channel["uploads_playlist"], quota, max_items=sample)
    if not uploads:
        return {}
    videos = batch_video_details(youtube, [u["video_id"] for u in uploads], quota)
    if not videos:
        return {}

    durations, views_list, titles, dates, tags = [], [], [], [], Counter()
    for v in videos:
        durations.append(parse_duration(v.get("contentDetails", {}).get("duration", "")))
        views_list.append(int(v.get("statistics", {}).get("viewCount", 0) or 0))
        titles.append(v["snippet"]["title"])
        dates.append(v["snippet"]["publishedAt"])
        for t in v.get("snippet", {}).get("tags", []):
            tags[t.lower()] += 1

    parsed_dates = []
    for d in dates:
        try:
            parsed_dates.append(datetime.fromisoformat(d.replace("Z", "+00:00")))
        except ValueError:
            pass
    parsed_dates.sort()
    gaps = [
        (parsed_dates[i + 1] - parsed_dates[i]).total_seconds() / 86400
        for i in range(len(parsed_dates) - 1)
    ]

    word_counter = Counter()
    for t in titles:
        for w in re.findall(r"[a-zA-Z]{4,}", t.lower()):
            if w not in STOP_WORDS:
                word_counter[w] += 1

    shorts = sum(1 for d in durations if 0 < d <= 60)

    return {
        "sample_size": len(videos),
        "avg_duration_sec": round(sum(durations) / len(durations)),
        "shorts_pct": round(shorts / len(durations) * 100, 1),
        "avg_recent_views": round(sum(views_list) / len(views_list)),
        "avg_days_between_uploads": round(sum(gaps) / len(gaps), 1) if gaps else None,
        "preferred_days": Counter(d.strftime("%A") for d in parsed_dates).most_common(3),
        "top_title_words": word_counter.most_common(15),
        "top_tags": tags.most_common(15),
        "recent_titles": titles[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="Find and analyze YouTube competitors")
    parser.add_argument("--channel", default=None,
                        help="Your channel @handle, URL, or ID (for context and ranking)")
    parser.add_argument("--competitors", nargs="*", default=[],
                        help="Competitor @handles/URLs/IDs to analyze directly")
    parser.add_argument("--keywords", nargs="*", default=[],
                        help="Discovery keywords (default: derived from your channel)")
    parser.add_argument("--max-queries", type=int, default=3,
                        help="Max discovery searches, 100 units each (default: 3)")
    parser.add_argument("--top", type=int, default=12,
                        help="How many competitors to profile in depth (default: 12)")
    parser.add_argument("--reports-dir", default="reports",
                        help="Root output directory (default: reports)")
    args = parser.parse_args()

    api_key = require_api_key()
    if not args.channel and not args.competitors:
        print("ERROR: Provide --channel and/or --competitors", file=sys.stderr)
        sys.exit(1)

    youtube = build("youtube", "v3", developerKey=api_key)
    quota = QuotaTracker()

    target = None
    target_recent_titles = []
    if args.channel:
        print(f"Resolving your channel: {args.channel}")
        target = resolve_channel_id(youtube, args.channel, quota)
        if not target:
            print("ERROR: Could not resolve your channel. Check the handle/URL/ID.",
                  file=sys.stderr)
            sys.exit(1)
        print(f"  Found: {target['title']} ({format_number(target['subscribers'])} subs)")

        uploads = list_uploads(youtube, target["uploads_playlist"], quota, max_items=25)
        for v in batch_video_details(youtube, [u["video_id"] for u in uploads], quota):
            target_recent_titles.append(v["snippet"]["title"])

    # --- Discovery ---
    discovery_hits = Counter()
    queries_used = []

    for ref in args.competitors:
        ch = resolve_channel_id(youtube, ref, quota)
        if ch:
            discovery_hits[ch["id"]] += 2  # direct input outranks a search hit
        else:
            print(f"  WARNING: could not resolve competitor '{ref}'", file=sys.stderr)

    if target:
        queries = args.keywords or derive_keywords(target, target_recent_titles,
                                                   limit=args.max_queries)
        queries = queries[:args.max_queries]
        for q in queries:
            print(f"Discovering competitors for: {q}")
            for cid in search_channels(youtube, q, quota, max_results=10):
                if not target or cid != target["id"]:
                    discovery_hits[cid] += 1
            queries_used.append(q)
    elif args.keywords:
        for q in args.keywords[:args.max_queries]:
            print(f"Discovering competitors for: {q}")
            for cid in search_channels(youtube, q, quota, max_results=10):
                discovery_hits[cid] += 1
            queries_used.append(q)

    if not discovery_hits:
        print("ERROR: No competitor channels found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nFetching details for {len(discovery_hits)} candidate channels...")
    candidates = batch_channel_details(youtube, list(discovery_hits.keys()), quota)

    max_hits = max(discovery_hits.values()) or 1
    target_subs = target["subscribers"] if target else 0

    ranked = []
    for cid, ch in candidates.items():
        metrics = channel_metrics(ch)
        relevance = discovery_hits[cid] / max_hits
        size_score = size_similarity(ch["subscribers"], target_subs) if target else 0.5
        metrics["relevance_score"] = round(relevance, 3)
        metrics["size_similarity"] = round(size_score, 3)
        metrics["overall_score"] = round(size_score * 0.3 + relevance * 0.7, 3)
        metrics["uploads_playlist"] = ch["uploads_playlist"]
        ranked.append(metrics)

    ranked.sort(key=lambda x: x["overall_score"], reverse=True)
    top = ranked[:args.top]

    print(f"Profiling recent content for top {len(top)} competitors...")
    for comp in top:
        comp["recent_content"] = recent_content_profile(
            youtube, {"uploads_playlist": comp.pop("uploads_playlist")}, quota
        )
    for comp in ranked[len(top):]:
        comp.pop("uploads_playlist", None)

    comp_avgs = {}
    if top:
        for field in ("subscribers", "total_views", "video_count",
                      "views_per_video", "uploads_per_month"):
            comp_avgs[f"avg_{field}"] = round(sum(c[field] for c in top) / len(top), 2)

    positioning = None
    if target:
        target_metrics = channel_metrics(target)
        positioning = {
            "target": target_metrics,
            "competitor_averages": comp_avgs,
            "vs_average": {
                field: round(
                    target_metrics[field] / comp_avgs[f"avg_{field}"] * 100, 1
                ) if comp_avgs.get(f"avg_{field}") else None
                for field in ("subscribers", "total_views", "video_count",
                              "views_per_video", "uploads_per_month")
            },
            "rank_by_subscribers": sorted(
                [target_metrics] + top, key=lambda x: x["subscribers"], reverse=True
            ).index(target_metrics) + 1,
            "field_size": len(top) + 1,
        }

    slug = slugify(
        (target.get("handle") or target["title"]) if target
        else (queries_used[0] if queries_used else "competitors")
    )
    data_path, report_path = report_paths(args.reports_dir, "competitor-analysis", slug)

    output = {
        "target_channel": target,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "discovery_queries": queries_used,
        "direct_competitors_supplied": args.competitors,
        "candidates_found": len(ranked),
        "competitors": top,
        "all_candidates": ranked,
        "competitor_averages": comp_avgs,
        "positioning": positioning,
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, output)

    print(f"\nData saved to: {data_path}")
    print(f"Write the markdown report to: {report_path}")
    print(f"Competitors profiled: {len(top)} (of {len(ranked)} candidates)")
    quota.report()


if __name__ == "__main__":
    main()
