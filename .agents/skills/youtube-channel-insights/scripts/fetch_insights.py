#!/usr/bin/env python3
"""
YouTube Channel Insights - data fetcher (YouTube Analytics API v2).

Pulls the private, OAuth-only metrics the public Data API cannot see:
retention curves, traffic sources, demographics, watch time, subscriber
attribution, and (optionally) revenue.

Every subcommand prints JSON to stdout, or writes it to --out.

Usage:
    python3 scripts/fetch_insights.py overview     --days 90
    python3 scripts/fetch_insights.py top-videos   --days 90 --limit 25
    python3 scripts/fetch_insights.py retention    --video VIDEO_ID
    python3 scripts/fetch_insights.py traffic      --days 90 [--video VIDEO_ID]
    python3 scripts/fetch_insights.py audience     --days 90
    python3 scripts/fetch_insights.py subscribers  --days 90
    python3 scripts/fetch_insights.py revenue      --days 90
    python3 scripts/fetch_insights.py all          --days 90

`all` writes a combined file to reports/data/channel-insights-<date>.json.

NOTE: YouTube Analytics data lags 2-3 days. Every date range produced here
ends at (today - 3 days) and every payload records the exact window used.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INSTALL_HINT = (
    "ERROR: Google API libraries not installed.\n"
    "Run: pip3 install google-api-python-client google-auth-oauthlib"
)

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(INSTALL_HINT)
    sys.exit(1)

try:
    from auth import AuthError, get_credentials, has_revenue_scope
except ImportError:
    print("ERROR: could not import auth.py. Run this script from the skill's scripts/ dir.")
    sys.exit(1)


# --- Constants --------------------------------------------------------------

CHANNEL_IDS = "channel==MINE"

# Analytics processing lag. Data for the last ~2 days is incomplete.
DATA_LAG_DAYS = 3

OVERVIEW_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
    "subscribersGained,subscribersLost,likes,comments,shares"
)

VIDEO_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
    "subscribersGained,subscribersLost,likes,comments,shares"
)

REVENUE_DAY_METRICS = (
    "estimatedRevenue,estimatedAdRevenue,playbackBasedCpm,adImpressions,monetizedPlaybacks"
)

REVENUE_VIDEO_METRICS = (
    "views,estimatedRevenue,estimatedAdRevenue,playbackBasedCpm,adImpressions,monetizedPlaybacks"
)

# Traffic source types for which the API exposes an insightTrafficSourceDetail
# drill-down. Any other type returns an error if you ask for detail.
DETAILABLE_TRAFFIC_SOURCES = {
    "ADVERTISING",
    "CAMPAIGN_CARD",
    "END_SCREEN",
    "EXT_URL",
    "HASHTAGS",
    "NOTIFICATION",
    "RELATED_VIDEO",
    "SOUND_PAGE",
    "SUBSCRIBER",
    "YT_CHANNEL",
    "YT_OTHER_PAGE",
    "YT_SEARCH",
    "VIDEO_REMIXES",
}

VALID_AUDIENCE_TYPES = {"ORGANIC", "AD_INSTREAM", "AD_INDISPLAY"}


# --- Small helpers ----------------------------------------------------------

def date_window(days: int):
    """
    Return (start_date, end_date) as YYYY-MM-DD strings, ending at the last
    day with settled data (today - DATA_LAG_DAYS).
    """
    days = max(int(days), 1)
    end = date.today() - timedelta(days=DATA_LAG_DAYS)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def parse_duration(iso_duration: str) -> int:
    """ISO 8601 duration -> seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


def rows_to_dicts(response: dict) -> list:
    """Turn the Analytics columnHeaders/rows shape into a list of dicts."""
    headers = [h["name"] for h in response.get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in response.get("rows", []) or []]


def eprint(*args):
    print(*args, file=sys.stderr)


def die_on_http(exc: HttpError, context: str):
    """Translate an HttpError into an actionable message and exit."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    detail = ""
    try:
        body = json.loads(exc.content.decode("utf-8"))
        detail = body.get("error", {}).get("message", "")
    except Exception:
        detail = str(exc)

    eprint(f"ERROR during {context}: HTTP {status} - {detail}")
    if status in (401, 403):
        eprint()
        eprint("This usually means your authorization expired or is missing a scope.")
        eprint("Fix: python3 scripts/auth.py --force")
        eprint("     (add --with-revenue if you need revenue metrics)")
        eprint("Also confirm the YouTube Analytics API is enabled in your Google Cloud project.")
    sys.exit(1)


# --- API plumbing -----------------------------------------------------------

def build_clients(with_revenue: bool = False):
    """Return (analytics_client, data_client, credentials)."""
    try:
        creds = get_credentials(with_revenue=with_revenue)
    except AuthError as exc:
        eprint(f"ERROR: {exc}")
        sys.exit(1)
    analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    data = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return analytics, data, creds


def query(analytics, context: str, **params) -> dict:
    """
    Run reports().query() and return {"rows": [...], "columns": [...], "note": ...}.
    Empty results are reported, never fatal.
    """
    params = {k: v for k, v in params.items() if v is not None}
    params.setdefault("ids", CHANNEL_IDS)
    try:
        resp = analytics.reports().query(**params).execute()
    except HttpError as exc:
        die_on_http(exc, context)
        return {}

    rows = rows_to_dicts(resp)
    out = {
        "query": {k: v for k, v in params.items()},
        "columns": [h["name"] for h in resp.get("columnHeaders", [])],
        "row_count": len(rows),
        "rows": rows,
    }
    if not rows:
        out["note"] = (
            "No rows returned for this query. Common causes: the channel had no "
            "activity in this window, the metric does not apply to this channel, "
            "or the data is still within the 2-3 day processing lag."
        )
    return out


def soft_query(analytics, context: str, fatal_auth: bool = True, **params) -> dict:
    """
    Like query(), but an API error becomes an in-payload error rather than exit.
    Used for optional drill-downs that not every channel supports.

    fatal_auth=False also swallows 401/403 - use it for revenue queries, where
    a 403 legitimately means "channel isn't monetized" rather than "re-auth".
    """
    params = {k: v for k, v in params.items() if v is not None}
    params.setdefault("ids", CHANNEL_IDS)
    try:
        resp = analytics.reports().query(**params).execute()
    except HttpError as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if fatal_auth and status == 401:
            die_on_http(exc, context)
        message = str(exc)
        try:
            message = json.loads(exc.content.decode("utf-8"))["error"]["message"]
        except Exception:
            pass
        return {
            "query": params,
            "columns": [],
            "row_count": 0,
            "rows": [],
            "error": f"HTTP {status}: {message}",
        }
    rows = rows_to_dicts(resp)
    return {
        "query": params,
        "columns": [h["name"] for h in resp.get("columnHeaders", [])],
        "row_count": len(rows),
        "rows": rows,
    }


def enrich_videos(data, video_ids: list) -> dict:
    """Batch-fetch titles/durations/publish dates. Returns dict keyed by video ID."""
    meta = {}
    ids = [v for v in dict.fromkeys(video_ids) if v]
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        try:
            resp = data.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(batch),
            ).execute()
        except HttpError as exc:
            eprint(f"  Warning: videos.list enrichment failed for a batch: {exc}")
            continue
        for item in resp.get("items", []):
            snip = item.get("snippet", {})
            dur = item.get("contentDetails", {}).get("duration", "")
            stats = item.get("statistics", {})
            meta[item["id"]] = {
                "title": snip.get("title", ""),
                "published_at": snip.get("publishedAt", ""),
                "duration_iso": dur,
                "duration_sec": parse_duration(dur),
                "lifetime_views": int(stats.get("viewCount", 0) or 0),
                "lifetime_likes": int(stats.get("likeCount", 0) or 0),
                "url": f"https://www.youtube.com/watch?v={item['id']}",
            }
    return meta


def attach_meta(rows: list, meta: dict) -> list:
    """Merge video metadata into analytics rows keyed on the `video` column."""
    for r in rows:
        info = meta.get(r.get("video"), {})
        r["title"] = info.get("title", "(title unavailable)")
        r["published_at"] = info.get("published_at", "")
        r["duration_sec"] = info.get("duration_sec", 0)
        r["url"] = info.get("url", f"https://www.youtube.com/watch?v={r.get('video','')}")
    return rows


def channel_profile(data) -> dict:
    """Basic identity info for the authorized channel, for report headers."""
    try:
        resp = data.channels().list(part="snippet,statistics", mine=True).execute()
    except HttpError as exc:
        eprint(f"  Warning: channels.list(mine=True) failed: {exc}")
        return {}
    items = resp.get("items", [])
    if not items:
        return {}
    it = items[0]
    stats = it.get("statistics", {})
    return {
        "channel_id": it.get("id", ""),
        "title": it.get("snippet", {}).get("title", ""),
        "custom_url": it.get("snippet", {}).get("customUrl", ""),
        "created_at": it.get("snippet", {}).get("publishedAt", ""),
        "subscribers": int(stats.get("subscriberCount", 0) or 0),
        "total_views": int(stats.get("viewCount", 0) or 0),
        "video_count": int(stats.get("videoCount", 0) or 0),
    }


def window_block(start: str, end: str, days: int) -> dict:
    return {
        "start_date": start,
        "end_date": end,
        "days": days,
        "data_lag_note": (
            f"YouTube Analytics lags ~{DATA_LAG_DAYS} days. This range deliberately "
            f"ends on {end} (today minus {DATA_LAG_DAYS}) so every day is settled."
        ),
    }


# --- Subcommand implementations --------------------------------------------

def cmd_overview(analytics, data, args) -> dict:
    start, end = date_window(args.days)
    daily = query(
        analytics, "overview (daily timeseries)",
        startDate=start, endDate=end,
        metrics=OVERVIEW_METRICS,
        dimensions="day",
        sort="day",
    )
    totals = query(
        analytics, "overview (period totals)",
        startDate=start, endDate=end,
        metrics=OVERVIEW_METRICS,
    )
    return {
        "report": "overview",
        "window": window_block(start, end, args.days),
        "channel": channel_profile(data),
        "totals": totals,
        "daily": daily,
    }


def cmd_top_videos(analytics, data, args) -> dict:
    start, end = date_window(args.days)
    limit = max(1, min(int(args.limit), 200))
    result = query(
        analytics, "top videos",
        startDate=start, endDate=end,
        metrics=VIDEO_METRICS,
        dimensions="video",
        sort="-estimatedMinutesWatched",
        maxResults=limit,
    )
    ids = [r.get("video") for r in result.get("rows", [])]
    meta = enrich_videos(data, ids) if ids else {}
    attach_meta(result.get("rows", []), meta)
    return {
        "report": "top_videos",
        "window": window_block(start, end, args.days),
        "limit": limit,
        "videos": result,
    }


def cmd_retention(analytics, data, args) -> dict:
    video_id = args.video
    filters = f"video=={video_id}"
    audience_type = (args.audience_type or "").upper() or None
    if audience_type:
        if audience_type not in VALID_AUDIENCE_TYPES:
            eprint(
                f"ERROR: --audience-type must be one of {sorted(VALID_AUDIENCE_TYPES)}"
            )
            sys.exit(1)
        filters += f";audienceType=={audience_type}"

    start, end = date_window(args.days)

    # relativeRetentionPerformance is unavailable for some videos (too few
    # views, or combined with an audienceType filter). Fall back cleanly.
    curve = soft_query(
        analytics, "retention curve",
        startDate=start, endDate=end,
        metrics="audienceWatchRatio,relativeRetentionPerformance",
        dimensions="elapsedVideoTimeRatio",
        filters=filters,
        sort="elapsedVideoTimeRatio",
    )
    if curve.get("error") or not curve.get("rows"):
        fallback = soft_query(
            analytics, "retention curve (audienceWatchRatio only)",
            startDate=start, endDate=end,
            metrics="audienceWatchRatio",
            dimensions="elapsedVideoTimeRatio",
            filters=filters,
            sort="elapsedVideoTimeRatio",
        )
        if fallback.get("rows"):
            fallback["note"] = (
                "relativeRetentionPerformance was unavailable for this video; "
                "returned audienceWatchRatio only."
            )
            curve = fallback

    summary = soft_query(
        analytics, "retention summary metrics",
        startDate=start, endDate=end,
        metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        filters=f"video=={video_id}",
    )

    meta = enrich_videos(data, [video_id])
    info = meta.get(video_id, {})
    duration_sec = info.get("duration_sec", 0)

    # Convert the 0.0-1.0 elapsed ratio into wall-clock seconds when we know
    # the video length - this is what makes cliff timestamps actionable.
    for r in curve.get("rows", []):
        try:
            ratio = float(r.get("elapsedVideoTimeRatio", 0))
        except (TypeError, ValueError):
            ratio = 0.0
        r["elapsed_seconds"] = round(ratio * duration_sec, 1) if duration_sec else None

    if not curve.get("rows"):
        curve.setdefault(
            "note",
            "No retention rows. Videos need enough watch data (roughly 100+ views) "
            "before YouTube returns an audience retention curve.",
        )

    return {
        "report": "retention",
        "window": window_block(start, end, args.days),
        "video_id": video_id,
        "video": info,
        "audience_type": audience_type or "ALL",
        "summary": summary,
        "curve": curve,
        "reading_guide": (
            "audienceWatchRatio is the fraction of viewers still watching at each "
            "point (1.0 = everyone who started). relativeRetentionPerformance "
            "compares this video to similar-length YouTube videos: >0.5 is "
            "above typical, <0.5 below typical."
        ),
    }


def cmd_traffic(analytics, data, args) -> dict:
    start, end = date_window(args.days)
    base_filter = f"video=={args.video}" if args.video else None

    by_type = query(
        analytics, "traffic sources",
        startDate=start, endDate=end,
        metrics="views,estimatedMinutesWatched,averageViewDuration",
        dimensions="insightTrafficSourceType",
        filters=base_filter,
        sort="-views",
    )

    total_views = sum(int(r.get("views", 0) or 0) for r in by_type.get("rows", []))
    for r in by_type.get("rows", []):
        v = int(r.get("views", 0) or 0)
        r["share_of_views_pct"] = round(v / total_views * 100, 1) if total_views else 0.0

    # Drill into the top few sources that support a detail dimension.
    details = {}
    ranked = sorted(
        by_type.get("rows", []),
        key=lambda r: int(r.get("views", 0) or 0),
        reverse=True,
    )
    for row in ranked[: args.detail_sources]:
        src = row.get("insightTrafficSourceType")
        if src not in DETAILABLE_TRAFFIC_SOURCES:
            continue
        detail_filter = f"insightTrafficSourceType=={src}"
        if base_filter:
            detail_filter = f"{base_filter};{detail_filter}"
        details[src] = soft_query(
            analytics, f"traffic detail for {src}",
            startDate=start, endDate=end,
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceDetail",
            filters=detail_filter,
            sort="-views",
            maxResults=25,
        )

    return {
        "report": "traffic",
        "window": window_block(start, end, args.days),
        "scope": f"video {args.video}" if args.video else "whole channel",
        "total_views_in_window": total_views,
        "by_source_type": by_type,
        "source_details": details,
        "detail_note": (
            "insightTrafficSourceDetail requires an insightTrafficSourceType filter "
            "and is only supported for some source types "
            f"({', '.join(sorted(DETAILABLE_TRAFFIC_SOURCES))})."
        ),
    }


def cmd_audience(analytics, data, args) -> dict:
    start, end = date_window(args.days)

    # viewerPercentage cannot be combined with other metrics.
    demographics = query(
        analytics, "audience demographics",
        startDate=start, endDate=end,
        metrics="viewerPercentage",
        dimensions="ageGroup,gender",
        sort="gender,ageGroup",
    )
    geography = query(
        analytics, "audience geography",
        startDate=start, endDate=end,
        metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
        dimensions="country",
        sort="-views",
        maxResults=25,
    )
    devices = query(
        analytics, "audience devices",
        startDate=start, endDate=end,
        metrics="views,estimatedMinutesWatched,averageViewDuration",
        dimensions="deviceType,operatingSystem",
        sort="-views",
        maxResults=50,
    )

    geo_total = sum(int(r.get("views", 0) or 0) for r in geography.get("rows", []))
    for r in geography.get("rows", []):
        v = int(r.get("views", 0) or 0)
        r["share_of_views_pct"] = round(v / geo_total * 100, 1) if geo_total else 0.0

    dev_total = sum(int(r.get("views", 0) or 0) for r in devices.get("rows", []))
    for r in devices.get("rows", []):
        v = int(r.get("views", 0) or 0)
        r["share_of_views_pct"] = round(v / dev_total * 100, 1) if dev_total else 0.0

    return {
        "report": "audience",
        "window": window_block(start, end, args.days),
        "demographics": demographics,
        "geography": geography,
        "devices": devices,
        "demographics_note": (
            "viewerPercentage rows sum to 100 across all age/gender buckets. "
            "YouTube withholds demographics when the sample is too small."
        ),
    }


def cmd_subscribers(analytics, data, args) -> dict:
    start, end = date_window(args.days)
    limit = max(1, min(int(args.limit), 200))

    by_video = query(
        analytics, "subscriber drivers by video",
        startDate=start, endDate=end,
        metrics="views,subscribersGained,subscribersLost",
        dimensions="video",
        sort="-subscribersGained",
        maxResults=limit,
    )
    ids = [r.get("video") for r in by_video.get("rows", [])]
    meta = enrich_videos(data, ids) if ids else {}
    attach_meta(by_video.get("rows", []), meta)

    # Conversion rate is the real signal - raw gains just track view volume.
    for r in by_video.get("rows", []):
        views = int(r.get("views", 0) or 0)
        gained = int(r.get("subscribersGained", 0) or 0)
        lost = int(r.get("subscribersLost", 0) or 0)
        r["net_subscribers"] = gained - lost
        r["subs_per_1000_views"] = round(gained / views * 1000, 2) if views else 0.0

    daily = query(
        analytics, "subscriber daily trend",
        startDate=start, endDate=end,
        metrics="subscribersGained,subscribersLost",
        dimensions="day",
        sort="day",
    )

    return {
        "report": "subscribers",
        "window": window_block(start, end, args.days),
        "by_video": by_video,
        "daily": daily,
        "benchmark_note": (
            "subs_per_1000_views is the conversion metric to compare across videos. "
            "1-3 subs per 1,000 views is typical; 5+ is a strong converter."
        ),
    }


def cmd_revenue(analytics, data, args, creds=None) -> dict:
    start, end = date_window(args.days)

    if creds is not None and not has_revenue_scope(creds):
        return {
            "report": "revenue",
            "window": window_block(start, end, args.days),
            "available": False,
            "reason": (
                "The monetary analytics scope was not granted. "
                "Run: python3 scripts/auth.py --with-revenue"
            ),
        }

    daily = soft_query(
        analytics, "revenue daily", fatal_auth=False,
        startDate=start, endDate=end,
        metrics=REVENUE_DAY_METRICS,
        dimensions="day",
        sort="day",
    )
    if daily.get("error"):
        return {
            "report": "revenue",
            "window": window_block(start, end, args.days),
            "available": False,
            "reason": (
                "Revenue metrics were rejected by the API: "
                f"{daily['error']}. This normally means the channel is not in the "
                "YouTube Partner Program, or the monetary scope was not granted "
                "(re-run: python3 scripts/auth.py --with-revenue)."
            ),
        }

    totals = soft_query(
        analytics, "revenue totals", fatal_auth=False,
        startDate=start, endDate=end,
        metrics=REVENUE_DAY_METRICS,
    )
    by_video = soft_query(
        analytics, "revenue by video", fatal_auth=False,
        startDate=start, endDate=end,
        metrics=REVENUE_VIDEO_METRICS,
        dimensions="video",
        sort="-estimatedRevenue",
        maxResults=max(1, min(int(args.limit), 200)),
    )
    ids = [r.get("video") for r in by_video.get("rows", [])]
    if ids:
        attach_meta(by_video.get("rows", []), enrich_videos(data, ids))

    # RPM = revenue per 1,000 views. The API gives CPM (per 1,000 ad
    # impressions); RPM is the number creators actually plan against.
    for r in by_video.get("rows", []):
        views = int(r.get("views", 0) or 0)
        try:
            rev = float(r.get("estimatedRevenue", 0) or 0)
        except (TypeError, ValueError):
            rev = 0.0
        r["rpm"] = round(rev / views * 1000, 2) if views else 0.0

    available = bool(daily.get("rows")) or bool(by_video.get("rows"))
    out = {
        "report": "revenue",
        "window": window_block(start, end, args.days),
        "available": available,
        "currency_note": "Amounts are in the channel's payment currency as configured in AdSense.",
        "totals": totals,
        "daily": daily,
        "by_video": by_video,
    }
    if not available:
        out["reason"] = (
            "The monetary scope is granted but the API returned no revenue rows. "
            "The channel is likely not monetized, or earned nothing in this window."
        )
    return out


# --- `all` orchestration ----------------------------------------------------

def cmd_all(analytics, data, args, creds) -> dict:
    start, end = date_window(args.days)
    eprint(f"Fetching channel insights for {start} -> {end} ({args.days} days)...")

    combined = {
        "report": "all",
        "generated_for_window": window_block(start, end, args.days),
        "channel": channel_profile(data),
    }

    eprint("  [1/6] overview")
    combined["overview"] = cmd_overview(analytics, data, args)

    eprint("  [2/6] top videos")
    top = cmd_top_videos(analytics, data, args)
    combined["top_videos"] = top

    eprint("  [3/6] traffic sources")
    traffic_args = argparse.Namespace(
        days=args.days, video=None, detail_sources=args.detail_sources
    )
    combined["traffic"] = cmd_traffic(analytics, data, traffic_args)

    eprint("  [4/6] audience")
    combined["audience"] = cmd_audience(analytics, data, args)

    eprint("  [5/6] subscriber drivers")
    combined["subscribers"] = cmd_subscribers(analytics, data, args)

    eprint("  [6/6] revenue")
    if has_revenue_scope(creds):
        combined["revenue"] = cmd_revenue(analytics, data, args, creds=creds)
    else:
        combined["revenue"] = {
            "report": "revenue",
            "available": False,
            "reason": (
                "Monetary scope not granted - skipped. "
                "Run `python3 scripts/auth.py --with-revenue` to include revenue."
            ),
        }

    # Retention for the top N videos by watch time - the expensive-but-valuable part.
    retention = {}
    top_rows = top.get("videos", {}).get("rows", [])[: args.retention_videos]
    if top_rows:
        eprint(f"  [+] retention curves for top {len(top_rows)} videos")
    # Retention is a property of the video, not the reporting period, so use a
    # wide window (at least a year) to get a stable curve.
    retention_days = max(args.days, 365)
    for row in top_rows:
        vid = row.get("video")
        if not vid:
            continue
        r_args = argparse.Namespace(video=vid, days=retention_days, audience_type=None)
        retention[vid] = cmd_retention(analytics, data, r_args)
    combined["retention"] = retention

    combined["limitations"] = [
        "Thumbnail impressions and impressions click-through rate are NOT exposed by "
        "the public YouTube Analytics API. Read those in YouTube Studio.",
        f"Analytics data lags ~{DATA_LAG_DAYS} days; this window ends at {end}.",
        "Demographic rows are withheld by YouTube when the sample is too small.",
    ]
    return combined


# --- Output -----------------------------------------------------------------

def emit(payload: dict, out_path: str = None, default_path: str = None) -> None:
    target = out_path or default_path
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if not target:
        print(text)
        return
    p = Path(target).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(text, encoding="utf-8")
    except OSError as exc:
        eprint(f"ERROR: could not write {p}: {exc}")
        sys.exit(1)
    eprint(f"Wrote {p}")
    print(str(p))


# --- CLI --------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch private YouTube Analytics data for your own channel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p, default_days=90):
        p.add_argument("--days", type=int, default=default_days,
                       help=f"Length of the analysis window in days (default: {default_days})")
        p.add_argument("--out", default=None,
                       help="Write JSON to this file instead of stdout")

    p_over = sub.add_parser("overview", help="Channel-level daily timeseries and totals")
    add_common(p_over)

    p_top = sub.add_parser("top-videos", help="Best videos by watch time, with metadata")
    add_common(p_top)
    p_top.add_argument("--limit", type=int, default=25, help="Videos to return (default: 25, max: 200)")

    p_ret = sub.add_parser("retention", help="Audience retention curve for one video")
    add_common(p_ret, default_days=365)
    p_ret.add_argument("--video", required=True, help="Video ID to analyze")
    p_ret.add_argument("--audience-type", default=None,
                       choices=sorted(VALID_AUDIENCE_TYPES),
                       help="Restrict to ORGANIC / AD_INSTREAM / AD_INDISPLAY traffic")

    p_traf = sub.add_parser("traffic", help="Traffic source mix, with detail drill-down")
    add_common(p_traf)
    p_traf.add_argument("--video", default=None, help="Limit to a single video ID")
    p_traf.add_argument("--detail-sources", type=int, default=4,
                        help="How many top sources to drill into (default: 4)")

    p_aud = sub.add_parser("audience", help="Age/gender, country, and device breakdowns")
    add_common(p_aud)

    p_sub = sub.add_parser("subscribers", help="Which videos gained and lost subscribers")
    add_common(p_sub)
    p_sub.add_argument("--limit", type=int, default=25, help="Videos to return (default: 25, max: 200)")

    p_rev = sub.add_parser("revenue", help="Revenue, CPM, RPM (needs --with-revenue auth)")
    add_common(p_rev)
    p_rev.add_argument("--limit", type=int, default=25, help="Videos to return (default: 25, max: 200)")

    p_all = sub.add_parser("all", help="Run everything and write one combined JSON file")
    add_common(p_all)
    p_all.add_argument("--limit", type=int, default=25, help="Videos per video-level report (default: 25)")
    p_all.add_argument("--detail-sources", type=int, default=4,
                       help="How many top traffic sources to drill into (default: 4)")
    p_all.add_argument("--retention-videos", type=int, default=5,
                       help="Pull retention curves for the top N videos (default: 5)")

    return parser


def main() -> int:
    args = build_parser().parse_args()

    wants_revenue = args.command == "revenue"
    analytics, data, creds = build_clients(with_revenue=wants_revenue)

    if args.command == "overview":
        emit(cmd_overview(analytics, data, args), args.out)
    elif args.command == "top-videos":
        emit(cmd_top_videos(analytics, data, args), args.out)
    elif args.command == "retention":
        emit(cmd_retention(analytics, data, args), args.out)
    elif args.command == "traffic":
        emit(cmd_traffic(analytics, data, args), args.out)
    elif args.command == "audience":
        emit(cmd_audience(analytics, data, args), args.out)
    elif args.command == "subscribers":
        emit(cmd_subscribers(analytics, data, args), args.out)
    elif args.command == "revenue":
        emit(cmd_revenue(analytics, data, args, creds=creds), args.out)
    elif args.command == "all":
        payload = cmd_all(analytics, data, args, creds)
        default_path = os.path.join(
            "reports", "data", f"channel-insights-{date.today().isoformat()}.json"
        )
        emit(payload, args.out, default_path=default_path)
    else:  # pragma: no cover - argparse enforces the choices
        eprint(f"Unknown command: {args.command}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
