#!/usr/bin/env python3
"""YouTube Title & Tag Optimizer -- data collection.

Analyzes top-ranking videos for a keyword to extract winning title patterns,
effective tags, and (optionally) score the user's working title.

Usage:
    YT_API_KEY=KEY python3 optimize_title_tags.py "air fryer recipes"
    YT_API_KEY=KEY python3 optimize_title_tags.py "Python tutorial" --my-title "Learn Python Fast"
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
# Title analysis
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "you", "your", "my", "this", "that", "i", "me", "we",
    "how", "what", "why", "do", "does", "can", "will", "be", "are", "was",
    "not", "no", "so", "if",
}

POWER_WORDS = {
    "urgency": ["now", "today", "immediately", "urgent", "hurry", "fast", "quick", "instantly", "stop"],
    "curiosity": ["secret", "hidden", "surprising", "shocking", "unexpected", "weird", "strange", "mystery", "truth", "reveal"],
    "value": ["free", "best", "top", "ultimate", "complete", "guide", "hack", "tips", "tricks", "easy", "simple"],
    "emotional": ["amazing", "incredible", "insane", "mind-blowing", "life-changing", "game-changer", "beautiful", "perfect", "love", "hate"],
    "fear": ["mistake", "wrong", "avoid", "never", "worst", "dangerous", "warning", "risk", "fail", "scam", "don't"],
}


def search_keyword(youtube, keyword, order, quota, max_results=50):
    """Keyword search -- search.list is required here."""
    try:
        resp = youtube.search().list(
            part="snippet", q=keyword, type="video",
            order=order, maxResults=min(max_results, 50),
        ).execute()
        quota.record("search.list")
        return [item["id"]["videoId"] for item in resp.get("items", [])]
    except HttpError as e:
        check_quota_error(e)
        print(f"  search.list ({order}) error: {e}", file=sys.stderr)
        return []


def analyze_title(title):
    """Analyze a single title for patterns, power words, and structures."""
    analysis = {
        "length_chars": len(title),
        "length_words": len(title.split()),
        "has_number": bool(re.search(r"\d", title)),
        "has_question": title.rstrip().endswith("?"),
        "has_how_to": bool(re.search(r"how\s+to", title, re.I)),
        "has_brackets": bool(re.search(r"[\[\(]", title)),
        "has_parentheses": bool(re.search(r"\(", title)),
        "has_caps_word": bool(re.search(r"\b[A-Z]{2,}\b", title)),
        "has_emoji": bool(re.search(r"[^\w\s,.\-!?\'\"()\[\]:;/\\@#$%^&*+=~`|<>]", title)),
        "has_year": bool(re.search(r"20[12]\d", title)),
        "has_list_format": bool(re.search(r"^\d+\s", title)),
        "has_vs": bool(re.search(r"\bvs\.?\b", title, re.I)),
        "has_colon": ":" in title,
        "has_pipe": "|" in title,
        "has_dash_separator": " - " in title or " — " in title,
        "has_exclamation": "!" in title,
        "starts_with_how": title.lower().startswith("how"),
        "starts_with_why": title.lower().startswith("why"),
        "starts_with_what": title.lower().startswith("what"),
        "starts_with_number": bool(re.match(r"^\d", title)),
    }

    title_lower = title.lower()
    found_power_words = {}
    for category, words in POWER_WORDS.items():
        matches = [w for w in words if w in title_lower]
        if matches:
            found_power_words[category] = matches
    analysis["power_words"] = found_power_words

    structures = []
    if re.match(r"^\d+\s", title):
        structures.append("listicle")
    if re.search(r"how\s+to", title, re.I):
        structures.append("how-to")
    if title.rstrip().endswith("?"):
        structures.append("question")
    if re.search(r"\bvs\.?\b", title, re.I):
        structures.append("comparison")
    if re.search(r"\breview\b", title, re.I):
        structures.append("review")
    if re.search(r"in\s+\d+\s+(minute|min|second|sec|hour|day|step)", title, re.I):
        structures.append("time-bound")
    if re.search(r"for\s+(beginners|newbies|noobs|starters)", title, re.I):
        structures.append("beginner-targeted")
    if re.search(r"(complete|ultimate|full|definitive)\s+guide", title, re.I):
        structures.append("comprehensive-guide")
    if re.search(r"\b(do|don't|never|stop|avoid)\b", title, re.I):
        structures.append("imperative")
    analysis["structures"] = structures

    return analysis


def score_title(my_title, keyword, top_titles):
    """Score the user's working title out of 100 against the keyword and top performers."""
    my_analysis = analyze_title(my_title)
    score = 0
    feedback = []

    if 40 <= my_analysis["length_chars"] <= 70:
        score += 15
        feedback.append("Title length is in the optimal range (40-70 chars)")
    elif my_analysis["length_chars"] < 30:
        feedback.append("Title is too short -- aim for 40-70 characters")
    elif my_analysis["length_chars"] > 80:
        feedback.append("Title may be too long -- could get truncated in search results")
    else:
        score += 10
        feedback.append("Title length is acceptable but could be optimized")

    keyword_lower = keyword.lower()
    title_lower = my_title.lower()
    if keyword_lower in title_lower:
        score += 20
        if title_lower.startswith(keyword_lower) or title_lower[:20].find(keyword_lower) >= 0:
            score += 5
            feedback.append("Keyword appears early in title -- great for SEO")
        else:
            feedback.append("Keyword is present in title")
    else:
        kw_words = keyword_lower.split()
        matches = sum(1 for w in kw_words if w in title_lower)
        if matches > 0:
            score += 10
            feedback.append(f"Partial keyword match ({matches}/{len(kw_words)} words)")
        else:
            feedback.append("WARNING: Keyword not found in title -- critical for SEO")

    if my_analysis["has_number"]:
        score += 10
        feedback.append("Contains a number -- increases click-through rate")

    if my_analysis["power_words"]:
        score += 10
        feedback.append(f"Uses power words ({', '.join(my_analysis['power_words'].keys())})")
    else:
        feedback.append("Consider adding power words for emotional impact")

    if my_analysis["structures"]:
        score += 10
        feedback.append(f"Uses proven structure: {', '.join(my_analysis['structures'])}")
    else:
        feedback.append("Consider using a proven structure (how-to, listicle, question)")

    if my_analysis["has_brackets"]:
        score += 5
        feedback.append("Uses brackets -- can boost CTR")

    if my_analysis["has_caps_word"]:
        score += 5
        feedback.append("Strategic use of CAPS for emphasis")

    common_patterns_in_top = set()
    for t in top_titles:
        for s in analyze_title(t)["structures"]:
            common_patterns_in_top.add(s)

    matching_patterns = set(my_analysis["structures"]) & common_patterns_in_top
    if matching_patterns:
        score += 10
        feedback.append(f"Matches top-performer patterns: {', '.join(sorted(matching_patterns))}")

    return {
        "title": my_title,
        "score": min(score, 100),
        "analysis": my_analysis,
        "feedback": feedback,
    }


def main():
    parser = argparse.ArgumentParser(description="Optimize YouTube titles and tags")
    parser.add_argument("keyword", help="Keyword to optimize for")
    parser.add_argument("--my-title", default=None, help="Your working title to score")
    parser.add_argument("--reports-dir", default="reports",
                        help="Root output directory (default: reports)")
    args = parser.parse_args()

    api_key = require_api_key()
    youtube = build("youtube", "v3", developerKey=api_key)
    quota = QuotaTracker()

    print(f"Analyzing keyword: {args.keyword}")
    if args.my_title:
        print(f"Your title: {args.my_title}\n")

    print("Fetching top-ranking videos (by relevance)...")
    relevance_ids = search_keyword(youtube, args.keyword, "relevance", quota)
    print(f"  Found {len(relevance_ids)}")

    print("Fetching most-viewed videos...")
    viewcount_ids = search_keyword(youtube, args.keyword, "viewCount", quota)
    print(f"  Found {len(viewcount_ids)}")

    all_ids = list(dict.fromkeys(relevance_ids + viewcount_ids))
    if not all_ids:
        print("ERROR: No videos found for this keyword.", file=sys.stderr)
        sys.exit(1)
    print(f"Total unique videos: {len(all_ids)}")

    print("Fetching video details...")
    videos = batch_video_details(youtube, all_ids, quota)
    print(f"  Got details for {len(videos)} videos")

    processed = []
    all_tags = Counter()
    title_analyses = []

    for v in videos:
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        likes = int(stats.get("likeCount", 0) or 0)
        comments = int(stats.get("commentCount", 0) or 0)
        duration = parse_duration(v.get("contentDetails", {}).get("duration", ""))
        title = v["snippet"]["title"]
        tags = v.get("snippet", {}).get("tags", [])

        for tag in tags:
            all_tags[tag.lower()] += 1

        t_analysis = analyze_title(title)
        title_analyses.append(t_analysis)

        processed.append({
            "video_id": v["id"],
            "title": title,
            "title_analysis": t_analysis,
            "channel": v["snippet"]["channelTitle"],
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
            "duration_sec": duration,
            "tags": tags,
            "tag_count": len(tags),
            "description_first_line": v["snippet"].get("description", "").split("\n")[0][:200],
            "published_at": v["snippet"]["publishedAt"],
        })

    processed.sort(key=lambda x: x["views"], reverse=True)

    total = len(title_analyses) or 1
    aggregate_title = {
        "avg_length_chars": round(sum(t["length_chars"] for t in title_analyses) / total, 1),
        "avg_length_words": round(sum(t["length_words"] for t in title_analyses) / total, 1),
        "pct_has_number": round(sum(1 for t in title_analyses if t["has_number"]) / total * 100, 1),
        "pct_question": round(sum(1 for t in title_analyses if t["has_question"]) / total * 100, 1),
        "pct_how_to": round(sum(1 for t in title_analyses if t["has_how_to"]) / total * 100, 1),
        "pct_brackets": round(sum(1 for t in title_analyses if t["has_brackets"]) / total * 100, 1),
        "pct_caps_word": round(sum(1 for t in title_analyses if t["has_caps_word"]) / total * 100, 1),
        "pct_emoji": round(sum(1 for t in title_analyses if t["has_emoji"]) / total * 100, 1),
        "pct_year": round(sum(1 for t in title_analyses if t["has_year"]) / total * 100, 1),
        "pct_list_format": round(sum(1 for t in title_analyses if t["has_list_format"]) / total * 100, 1),
        "pct_colon": round(sum(1 for t in title_analyses if t["has_colon"]) / total * 100, 1),
        "pct_pipe": round(sum(1 for t in title_analyses if t["has_pipe"]) / total * 100, 1),
        "pct_exclamation": round(sum(1 for t in title_analyses if t["has_exclamation"]) / total * 100, 1),
    }

    structure_counter = Counter()
    for t in title_analyses:
        for s in t["structures"]:
            structure_counter[s] += 1
    aggregate_title["structures"] = {
        k: round(v / total * 100, 1) for k, v in structure_counter.most_common()
    }

    # Average views per structure, so the report can rank structures by impact.
    structure_views = {}
    for s in structure_counter:
        vids = [v for v in processed if s in v["title_analysis"]["structures"]]
        structure_views[s] = round(sum(v["views"] for v in vids) / max(len(vids), 1))
    aggregate_title["structure_avg_views"] = structure_views

    power_category_counter = Counter()
    for t in title_analyses:
        for cat in t["power_words"]:
            power_category_counter[cat] += 1
    aggregate_title["power_word_categories"] = {
        k: round(v / total * 100, 1) for k, v in power_category_counter.most_common()
    }

    word_counter = Counter()
    for v in processed:
        for w in re.findall(r"[a-zA-Z]{3,}", v["title"].lower()):
            if w not in STOP_WORDS:
                word_counter[w] += 1
    aggregate_title["common_title_words"] = word_counter.most_common(30)

    my_title_score = None
    if args.my_title:
        my_title_score = score_title(
            args.my_title, args.keyword, [v["title"] for v in processed[:10]]
        )

    data_path, report_path = report_paths(args.reports_dir, "title-tag", slugify(args.keyword))

    output = {
        "keyword": args.keyword,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_videos_analyzed": len(processed),
        "aggregate_title_analysis": aggregate_title,
        "top_tags": all_tags.most_common(50),
        "tag_stats": {
            "unique_tags": len(all_tags),
            "avg_tags_per_video": round(
                sum(v["tag_count"] for v in processed) / len(processed), 1
            ) if processed else 0,
        },
        "top_videos": [
            {
                "title": v["title"],
                "video_id": v["video_id"],
                "views": v["views"],
                "engagement_rate": v["engagement_rate"],
                "channel": v["channel"],
                "tag_count": v["tag_count"],
                "title_analysis": v["title_analysis"],
                "description_first_line": v["description_first_line"],
            }
            for v in processed[:20]
        ],
        "all_videos": processed,
        "my_title_score": my_title_score,
        "quota_used": {"breakdown": quota.breakdown(), "total_estimated": quota.total},
        "report_path": report_path,
    }

    save_json(data_path, output)

    print(f"\nData saved to: {data_path}")
    print(f"Write the markdown report to: {report_path}")
    print(f"Videos analyzed: {len(processed)}")
    print(f"Unique tags found: {len(all_tags)}")
    if my_title_score:
        print(f"Your title score: {my_title_score['score']}/100")
    quota.report()


if __name__ == "__main__":
    main()
