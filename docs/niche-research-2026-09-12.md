# Would You Rather / Shorts — niche research briefing

**Self-contained.** Written to be handed to a session that did not run this
research. Contains analysis only: no video ideas, no titles, no descriptions, no
upload settings. The findings are about the *niche and the format*, so they hold
regardless of which specific videos a session is working on.

Pulled 2026-09-12 with YouTube Data API v3 and YouTube Analytics API v2.

---

## Headline: most per-video optimisation in this niche is noise

The single most important result. Across 37 channels with complete Shorts
catalogues:

| Measure | Value |
|---|---|
| Share of a channel's views held by its **single best video** | **9.7%** (median) |
| Share held by the **top 10%** of its videos | **48.4%** (median) |
| Ratio of best video to median video | **33×** (median) |
| Channels whose best video is **>100×** their own median | **12 of 37** |

Concrete: *ThatsAladdin*, 21,700 subs — median video **6,992** views, best video
**9,680,704**. A 1,384× spread inside one channel, same format, same creator,
same audience.

Every per-video lever tested came back at noise level (details below). The
outcome distribution is dominated by whether the Shorts feed picks a video up,
not by how the video was packaged.

**Operational consequence:** volume and consistency beat per-video optimisation.
Time spent perfecting one upload's metadata is worth less than time spent
shipping the next one. Optimise the *pipeline's throughput*, not the individual
video.

This is the one conclusion here with a large, clean effect size. Everything else
in this document is smaller than it.

---

## Method, and why the earlier method was wrong

Two samples were used, and they disagree. Understanding why matters more than
either result.

**Sample A — search-derived (weaker).** 473 videos returned by `search.list` for
Would You Rather / This or That queries, published since 2025-09-01. This is how
the project's earlier research was done. It has two defects:

1. **Selection bias.** `search.list` returns what YouTube chooses to surface for
   a query. Videos are in the sample *because* they ranked, so ranking factors
   are entangled with the sample itself.
2. **Channel-size confounding.** Comparing videos across channels mostly measures
   which channels are big, not which choices work. A 10M-sub channel's worst
   video beats a 5K-sub channel's best.

**Sample B — catalogue-derived (used for all conclusions below).** 40 channels
active in the niche, each channel's full recent upload list pulled via
`playlistItems.list`, filtered to Shorts (≤185s): **4,341 videos**. Every video a
channel published is present, not just the ones that ranked.

Analysis on Sample B is **within-channel**: each channel is compared only against
itself (Spearman rank correlation per channel, or median-vs-median for binary
splits), then the per-channel results are aggregated with one vote each. This
neutralises channel size entirely.

**If you take one methodological point from this document:** cross-channel
medians in this niche are close to worthless. They are what produced all three
errors below.

---

## Corrections — three claims that did not survive

Earlier project docs assert these. They are wrong. If the repo you are working in
still states them, treat this section as the correction.

### 1. Numbered series titles ("#3", "Part 5", "Episode 7") — NO EFFECT

Claimed effect, cross-channel: numbered titles median **429,124** views against
**20,340** for plain. A 21× gap, and it replicated across two separate
cross-channel samples, which is why it was believed.

Within-channel, restricted to the 9 channels that publish **both** numbered and
plain titles:

| | |
|---|---|
| Channels where numbered wins | **5** |
| Channels where numbered loses | **4** |
| Median ratio numbered / plain | **1.08×** |

A coin flip. The 21× cross-channel gap was **entirely confounding**: channels
that run numbered series are established channels with audiences. The numbering
did not cause the views; having an audience caused both.

This is the most instructive error in the set, because the confounded result
replicated across two independent samples and still turned out to be an artifact.
Replication does not fix a confound — it reproduces it.

*Numbering is still fine to use.* It costs nothing and helps a returning viewer.
Just do not expect reach from it, and do not trade anything away for it.

### 2. Duration target of 41–60s — NOT SUPPORTED

Claimed: a cross-channel table put 41–60s as the winning band; a 45–55s target was
set from it.

Within-channel, duration vs views:

| | |
|---|---|
| Channels analysed (≥15 shorts each) | 38 |
| Median Spearman ρ | **+0.050** |
| Direction split | 24 positive / 14 negative |

ρ = +0.05 is nothing. And the cross-channel picture does not even agree with
itself between samples: Sample A's <10K cohort put 0–15s highest, the original
research put 41–60s highest.

Duration of the 716 actual WYR-format videos in Sample B, for reference:

| Duration | n | Median views |
|---|---|---|
| 0–15s | 23 | 30,577 |
| 16–25s | 31 | 2,941 |
| 26–40s | 133 | 6,982 |
| 41–60s | 159 | 2,794 |
| 61–90s | 253 | 1,223 |
| 91–185s | 117 | 61,776 |

Non-monotone and unstable — the two extremes both look good, which is the shape
of noise, not of a duration effect.

**Useful fact rather than a target: the median WYR Short in this niche runs 61
seconds.** Anything in roughly the 30–90s range is unremarkable to the audience.
Pick duration from what the format needs, not from a table.

### 3. Hashtags in the title — the original "keep titles clean" advice was wrong; the revised advice survives

Original claim (cross-channel, n=76): zero hashtags in title won with a 492,170
median. A re-pull (cross-channel, n=260) put zero hashtags in the *worst* cell at
1,332 with two hashtags at 61,863 — the exact opposite.

Within-channel resolves it:

| | |
|---|---|
| Channels analysed | 34 |
| Median Spearman ρ (hashtag count vs views) | **+0.151** |
| Direction split | 25 positive / 9 negative |

**ρ = +0.151 with 25 of 34 channels agreeing on sign.** Weak, but it is the only
packaging variable in this study that shows a consistent direction. Hashtags in
the title are mildly positive.

Cross-channel data suggests 2 is the peak and 3+ declines, but that shape comes
from the unreliable sample — treat "a small number, not a wall of them" as the
finding, not a precise optimum.

**Mechanism caveat, which limits how much to expect.** The hashtags on the
niche's breakout titles are *topic* hashtags attaching the video to an existing
fandom — `#minecraft`, `#roblox`, `#caseoh`. A generic format hashtag matches a
category, not an audience. If a channel has no fandom to attach to, the realistic
expectation is "cheap and mildly positive", not the cross-channel medians.

---

## Other variables tested — all noise

Same within-channel method, ≥20 videos per channel:

| Variable | Median ρ | Split | Verdict |
|---|---|---|---|
| Upload hour of day | **+0.049** | 25 pos / 12 neg | No usable effect |
| Title length in characters | **+0.026** | 20 pos / 17 neg | No effect |
| Duration | +0.050 | 24 pos / 14 neg | No effect |
| Hashtags in title | +0.151 | 25 pos / 9 neg | Weak positive — the only one |

**On upload time specifically.** A cross-channel hour table showed a 73× spread
between the best and worst hour — entirely an artifact of which channels upload
when, with the top cell decided by nine videos. Within-channel it vanishes
(ρ=+0.05). Shorts are feed-distributed rather than subscription-gated, and a
video that gets picked up is served over days, not in one evening.

Upload time is worth fixing for *operational* reasons — a constant slot keeps it
from becoming a confounding variable when reading your own analytics later — not
because any hour outperforms.

---

## What is true about the format itself

### WYR trades reach for engagement

Comparing the 716 WYR / this-or-that videos against the other 3,625 Shorts in the
same 40 catalogues:

| | n | Median comments / 1k views | Likes / 1k | Median views |
|---|---|---|---|---|
| **WYR / this-or-that** | 716 | **0.61** | 19.4 | **3,996** |
| Everything else | 3,625 | 0.35 | 21.0 | 85,362 |

**Comment rate is 1.7× higher. Median views are 21× lower.**

Both halves matter and the second one was not in the earlier research. WYR is a
high-engagement, lower-reach format *inside these catalogues*. Choosing it for a
comment-driven strategy is well founded; expecting it to be the highest-reach
thing a channel can publish is not.

The like rate is flat (19.4 vs 21.0), so the engagement gain is specifically in
comments — which is exactly the mechanic the format is built on.

### Breakouts take time to arrive

Position of a channel's best-performing video within its own upload timeline:

| | |
|---|---|
| Median position | **39%** of the way through the catalogue |
| Best video in the first 25% of uploads | 10 of 37 |
| Best video in the **last 25%** of uploads | **0 of 37** |

Partly an age artifact — recent videos have had less time to accumulate. But the
direction is consistent, and combined with the skew finding it sets the
expectation: **a channel's breakout is not its 5th upload.** Median catalogue size
among these channels is ~128 Shorts.

### Audience vocabulary (from earlier comment mining, 1,001 comments)

Retained from prior research, not re-verified in this pull:
`never` (103) · `pain` (79) · `pizza` (77) · `pineapple` (61) · `sister` (59) ·
`glow` (45) · `money` (45) · `unlimited` (38) · `already` (37) · `both` (36)

`never …` and `unlimited …` are the two recurring framings. `both` is people
refusing to choose — a signal the dilemma was not sharp enough.

### Why people comment on this format — three triggers

From 1,001 comments mined across the breakout videos of small channels
(2026-09-08 pull). Not re-verified here, but nothing in the within-channel study
contradicts it, and it is the most actionable material in the earlier research.

1. **Counterintuitive split.** The majority picks the option the viewer considers
   obviously wrong. Sample comment: `0:23 WHAT THE FU- FAST FOOD OVER HOME
   COOKED MEALS? 😨`
2. **"I already am that."** A dilemma naming a condition the viewer already lives
   with produces instant self-deprecating replies. `I already have bad eyesight
   lol` — 49 likes, with a near-duplicate at 18 likes on the same video.
3. **Broken edge case.** A dilemma that does not apply to the viewer at all.
   `What happens if I don't have a sister and bad hearing 😅` — **138 likes**.

Trigger 3 is the cheapest engagement and the most expensive to rely on: it works
by being wrong, so it buys comments at the cost of credibility. Triggers 1 and 2
are the ones worth engineering.

The most-liked comment across every breakout mined was people mocking arithmetic:

> **"How tf is 90 % and 15% 💀💀💀"** — 148 likes
>
> "Love how half of these are misspelled and the numbers don't quite add up to 100%" — 49 likes

Whatever a video claims numerically, the audience checks it. This is the one
detail they demonstrably police.

### Existence proofs — small channels that broke out

From the search-derived sample, so **not** a basis for rates or comparisons. They
are valid as existence claims: these specific channels, at these specific sizes,
did reach these numbers.

| Views | Subs | Dur | Title |
|---|---|---|---|
| 1,275,343 | 3,890 | 24s | `Would you rather: southern baddie edition😋😩#meme #funny #wouldyourather` |
| 1,220,098 | 7,180 | 38s | `Would You Rather Quiz – Hard Questions! 🤯😰` |
| 971,371 | 8,250 | 68s | `Unhinged would you rathers mix. #shorts #funnyshorts #wouldyourather` |
| 680,430 | 6,710 | 125s | `Would You Rather: The Boys Or Your Girlfriend!? #shorts #girlfriend` |
| 328,350 | 1,210 | 51s | `Nike or adidas #reaction #funny #wouldyourather #quiz` |

And one at a size worth studying — *Skydaaguy*, 127,000 subs, 53 Shorts in the
catalogue pull, **median 667,813 views**, best video 18,783,515:
`Would You Rather 21!? ✅❌ #minecraft #funny`

Note what that title actually does: it attaches a generic format to **Minecraft**.
That is the fandom-attachment mechanism, and it is the same reason the niche's
biggest velocity outlier in the 2026-09-08 trending scan was a Minecraft-skinned
WYR at **436K views/day**. The durations in the table above span 24s to 125s,
which is further evidence that duration is not the lever.

*(Borrowing someone else's IP is what makes this work. It is effective and it is
not ours to take — noted as an observed mechanism, not a recommendation.)*

---

## Own-channel baseline (Analytics API, private data)

Channel `Branks` / `@branks.s` — `UC3_Viek4Zhn3r_JM_jT8y7g`, created 2026-06-29.
Window: 90 days to 2026-09-09.

| | |
|---|---|
| Subscribers | 1 |
| Total views | 2,066 |
| Videos | 7 |
| Comments received, all videos | **0** |

**Traffic mix:** SHORTS feed **95.6%** · channel page 2.4% · search 1.1%.

Distribution is entirely feed-driven. Search and browse optimisation are
irrelevant at this stage — which is consistent with the packaging variables above
coming back at noise level.

**Per-video retention** (duration derived from `averageViewDuration ÷
averageViewPercentage`):

| Derived duration | Avg view duration | Avg view % |
|---|---|---|
| 12.4s | 11s | **88.4%** |
| 12.9s | 9s | 69.8% |
| 13.9s | 10s | 71.9% |
| 15.7s | 12s | 76.5% |
| 21.3s | 13s | 61.0% |
| 22.4s | 11s | 49.0% |
| 39.9s | 17s | **42.6%** |

**Absolute watch time sits at 9–17 seconds regardless of video length.** Longer
videos therefore post lower retention percentages, monotonically.

Handle this finding carefully. These 7 videos are unstructured lifestyle clips
with no hook mechanic and no reason to keep watching — a format with a reveal at
the end is exactly the case where this relationship should break. It is **not**
evidence that a longer format will fail. It *is* a concrete, measured baseline:
at ~12s of default attention, a long video must earn every second past the first
block, and average view percentage is worth watching closely on the first
uploads of any longer format.

---

## Niche-selection evidence (2026-09-08, cross-channel)

Cross-channel, so weak by this document's own standard — but the question it was
answering is *which niche to enter*, where comparing across channels is the
natural unit. Treat as directional.

| Signal | Value |
|---|---|
| Median views, channels <100K subs | 9,628 — 2nd highest of 16 niches tested (~5,400 videos) |
| Small channels among results | 60 of 76 |
| Rising channels in a 30-day scan | 29, including accounts at **22, 26 and 27 subs** |
| Best small-channel result observed | **904,865 views from 937 subs** |

The runner-up niche considered was **psychology facts** — higher median (234K)
but a text-and-voiceover format whose only lever is hook writing. WYR was chosen
because it is a *mechanic*: templatable, repeatable, renderable without a face.
Given the skew finding above, "repeatable at volume" matters more than the
original reasoning credited it for.

## Weak and untested signals

Kept because they are cheap to act on, flagged because none was tested
within-channel. Do not spend anything to satisfy them.

- **Emoji in the title: neutral.** 24,857 median with, 26,574 without (n=260,
  cross-channel). Consistent with everything else here — packaging is noise. Use
  them for legibility, not reach.
- **Very heavy hashtag stuffing in the description looks bad.** Cross-channel:
  0 hashtags 47,370 · 1–3 28,416 · 4–9 25,678 · **10+ 6,726**. Direction only.
- **Niche tag vocabulary.** `would you rather` appeared on 41 of 76 videos,
  `this or that` on 24.
- **Food as the entry sub-vertical.** The 2026-09-08 research claimed food
  converts best, citing a 324-sub channel at 135,487 views and an 865-sub channel
  at 446,781. Cross-channel and cherry-picked; listed under open questions below.

## Platform constraints that shape the format

Factual platform behaviour, not packaging preferences. Each one can silently
break a comment-driven format.

- **"Made for kids" disables comments entirely.** For any format whose engine is
  the comment section, this single upload flag is the difference between the
  strategy working and being impossible.
- **The Community tab is gated at 500 subscribers.** Any growth loop built on
  Community polls does not exist below that threshold. Comment-reply tallying is
  the only poll mechanism available to a small channel.
- **`#shorts` is not required for Shorts classification.** Aspect ratio and
  duration decide it. The tag is conventional and harmless, not functional.

---

## Open questions this research does not answer

- **What actually causes a Shorts breakout.** Nothing measurable from public
  metadata predicted it. The variance lives in the recommendation system's
  response to early watch-time signal, which is not visible through these APIs.
- **Whether the weak hashtag effect transfers** to a channel with no fandom to
  attach to. Untested.
- **Whether the retention-vs-duration relationship on the owner's channel holds
  for a format with a payoff.** Needs the channel's own data across 10+ uploads.
- **Sub-vertical performance** (food vs money vs relationships). Not tested here;
  prior research claimed food converts best, on cross-channel data, which this
  study has shown to be an unreliable basis.

## Reproducing this

```bash
# API key at ~/.config/youtube-skills/api_key, OAuth token at ~/.config/youtube-skills/token.json
cd .agents/skills/youtube-channel-insights
python3 scripts/fetch_insights.py overview  --days 90
python3 scripts/fetch_insights.py traffic   --days 90
python3 scripts/fetch_insights.py top-videos --days 90
```

Raw pulls land in `reports/` (gitignored): `wyr-niche.json` (Sample A, 473 rows)
and `wyr-channels.json` (Sample B, 4,341 rows).

**When re-running any of this: compare within channels, not across them.** Three
of the three packaging claims that were built on cross-channel medians turned out
to be artifacts.
