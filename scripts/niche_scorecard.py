#!/usr/bin/env python3
"""Compare niches from youtube-topic-researcher output on one question:
can a channel with no audience actually win here?

Average views across a niche is a vanity number -- it is dominated by a handful
of channels with millions of subscribers whose floor is higher than our ceiling.
A niche where MrBeast-scale channels post is not a niche we can enter; a niche
where unknown channels routinely clear six figures is.

So every metric here is conditioned on channel size:

  winnable_median  median views of videos from channels under 100K subs --
                   the realistic outcome for us, not for the incumbents
  small_share      share of results coming from channels under 100K subs --
                   how much of the surface area is reachable at all
  micro_breakouts  videos from channels under 10K subs that cleared 100K views --
                   direct proof that the algorithm distributes on content here,
                   not on existing audience
  entry_ratio      winnable_median / overall median -- below ~0.3 means the
                   niche's numbers belong to incumbents and do not transfer

plus the production constraints that decide whether we can actually ship it
daily: median duration, engagement, and how fresh the winning results are.

Usage:
    python3 scripts/niche_scorecard.py reports/data/topic-research-*.json
"""

import json
import statistics
import sys
from pathlib import Path

SMALL_SUBS = 100_000
MICRO_SUBS = 10_000
BREAKOUT_VIEWS = 100_000


def median(values):
    return int(statistics.median(values)) if values else 0


def score_file(path):
    data = json.loads(Path(path).read_text())
    videos = data.get("all_videos", [])
    # Shorts only: a niche's long-form numbers say nothing about our format.
    shorts = [v for v in videos if (v.get("duration_sec") or 0) <= 90]
    if not shorts:
        return None

    small = [v for v in shorts if (v.get("channel_subs") or 0) < SMALL_SUBS]
    micro = [v for v in shorts if (v.get("channel_subs") or 0) < MICRO_SUBS]
    breakouts = [v for v in micro if (v.get("views") or 0) >= BREAKOUT_VIEWS]

    all_median = median([v.get("views", 0) for v in shorts])
    win_median = median([v.get("views", 0) for v in small])

    best = max(micro, key=lambda v: v.get("views", 0)) if micro else None

    return {
        "niche": data.get("topic", Path(path).stem),
        "n_shorts": len(shorts),
        "all_median": all_median,
        "winnable_median": win_median,
        "entry_ratio": round(win_median / all_median, 2) if all_median else 0,
        "small_share": round(100 * len(small) / len(shorts)),
        "micro_breakouts": len(breakouts),
        "median_engagement": round(
            statistics.median([v.get("engagement_rate", 0) for v in shorts]), 2
        ),
        "median_duration": median([v.get("duration_sec", 0) for v in shorts]),
        "fresh_7d": sum(1 for v in shorts if (v.get("age_days") or 999) <= 7),
        "best_micro": {
            "title": best.get("title", "")[:60],
            "views": best.get("views", 0),
            "subs": best.get("channel_subs", 0),
            "channel": best.get("channel_name", ""),
        } if best else None,
    }


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 1

    rows = [r for r in (score_file(p) for p in paths) if r]
    # Rank by what we can actually reach, not by what the niche produces overall.
    rows.sort(key=lambda r: (r["winnable_median"], r["micro_breakouts"]), reverse=True)

    header = f"{'NICHE':<38} {'WIN.MED':>10} {'ENTRY':>6} {'SMALL%':>7} {'BREAK':>6} {'ENG':>6} {'DUR':>5} {'7D':>4}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['niche'][:38]:<38} {r['winnable_median']:>10,} {r['entry_ratio']:>6} "
            f"{r['small_share']:>6}% {r['micro_breakouts']:>6} {r['median_engagement']:>5}% "
            f"{r['median_duration']:>4}s {r['fresh_7d']:>4}"
        )

    print("\nBest result from a channel under 10K subs, per niche:")
    for r in rows:
        b = r["best_micro"]
        if b and b["views"] >= 10_000:
            print(f"  {r['niche'][:34]:<34} {b['views']:>10,} views  ({b['subs']:,} subs)  {b['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
