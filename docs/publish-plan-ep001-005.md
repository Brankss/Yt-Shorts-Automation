# Publish plan — episodes 1 to 5

Everything needed to schedule the first five uploads by hand: lineup, title,
description, tags, pinned comment, settings, cadence and slot.

Evidence base: a fresh pull on 2026-09-12 — 473 Would You Rather / This or That
Shorts published since 2025-09-01, of which **260 from channels under 100K subs**
and **156 under 10K**, the cohort Branks is actually in. Raw data in
`reports/wyr-niche.json` (gitignored, re-pullable).

> **Read the corrections section first.** This pull is roughly 6× the sample the
> earlier docs were written on, and it reverses two of their recommendations.

---

## Corrections to earlier advice

I gave you two confident recommendations that this larger sample does not
support. Both are in `docs/publish-ep001.md` and `docs/strategy.md`.

### 1. Hashtags in the title — I had this backwards

`publish-ep001.md` told you to keep the title clean, on a table built from 76
videos. On 156 videos from channels under 10K subs:

| Real hashtags in title | n | Median views |
|---|---|---|
| 0 | 55 | **1,332** |
| 1 | 10 | 4,501 |
| **2** | **30** | **61,863** |
| 3 | 30 | 16,666 |
| 4 | 14 | 15,767 |
| 5+ | 17 | 6,726 |

The old table said zero hashtags won with a median of 492,170. This one says
zero hashtags is the *worst* cell. Same niche, same method, opposite answer —
which tells you the honest thing here is that **neither table is strong
evidence**. Observational samples this small, on a metric as skewed as views,
flip when you re-draw them.

What makes me change the recommendation anyway is that the new direction agrees
with what the proven channels actually do. See the proof cases below: the
breakout titles in this niche carry hashtags, and the pattern is consistent
across channel sizes.

**Revised: 2 hashtags in the title.** Not 3+, where the curve turns back down.

One caveat on mechanism, because it affects how much to expect. The hashtags
that work in the proof cases are *topic* hashtags — `#minecraft`, `#roblox`,
`#caseoh` — which attach the video to a large existing audience. A food WYR has
no equivalent topic to ride; `#wouldyourather` matches a niche, not a fandom. So
take the upside as "cheap and probably mildly positive", not as the 60K median.

### 2. Duration — the 41–60s target does not replicate

`strategy.md` set a 45–55s target on a table where 41–60s was the winning band.
On the <10K cohort now:

| Duration | n | Median |
|---|---|---|
| 0–15s | 7 | 62,707 |
| 16–25s | 14 | 14,182 |
| 26–40s | 31 | 5,088 |
| 41–60s | 30 | 5,597 |
| 61–90s | 32 | 3,165 |
| 91–180s | 42 | 14,120 |

There is no clean duration signal. The proof cases run from 24s to 141s. The
cells are small and the medians are unstable.

**What to do about it: nothing, for now.** Episode 1 is built at 55.75s and the
format's own logic — ask, let the viewer commit, reveal — needs that room.
Changing the DNA's timing on a table this noisy would be trading a working build
for a coin flip. Revisit it against your *own* retention data after 10 episodes,
which is evidence about your videos rather than about strangers'.

### What did replicate

> **RETRACTED 2026-09-12, same day.** This section called numbering "the one
> finding that replicated". A within-channel re-analysis — 40 full catalogues,
> 4,341 Shorts, each channel compared only against itself — shows numbering does
> **nothing**: among the 9 channels that publish both numbered and plain titles,
> numbered wins on 5 and loses on 4, median ratio **1.08×**. The 21× gap below is
> entirely channel-size confounding: series channels are established channels.
> Replication did not fix the confound, it reproduced it.
>
> Keep the numbering — it costs nothing and helps a returning viewer — but expect
> no reach from it. Full analysis: `docs/niche-research-2026-09-12.md`.

The retracted reasoning follows.

**Numbered series titles.** The one finding that holds across both samples,
in the same direction, with a large gap:

| | n | Median views |
|---|---|---|
| Numbered (`#N`, `Part N`, `Episode N`) | 27 | **429,124** |
| Not numbered | 233 | 20,340 |

And on the <10K cohort alone: 103,980 (n=10) against 4,604 (n=146).

Heavily confounded — series channels have both the numbering and the audience —
but it costs nothing, every big channel in the niche does it, and it is the one
thing two independent samples agree on. **Number every episode.**

---

## Proof cases

Channels under 10K subscribers, sorted by views. These are the templates.

| Views | Subs | Dur | Title |
|---|---|---|---|
| 1,275,343 | 3,890 | 24s | `Would you rather: southern baddie edition😋😩#meme #funny #wouldyourather` |
| 1,220,098 | 7,180 | 38s | `Would You Rather Quiz – Hard Questions! 🤯😰` |
| 971,371 | 8,250 | 68s | `Unhinged would you rathers mix. #shorts #funnyshorts #wouldyourather` |
| 680,430 | 6,710 | 125s | `Would You Rather: The Boys Or Your Girlfriend!? #shorts #girlfriend` |
| 429,124 | 7,180 | 40s | `Would You Rather Quiz – Hard Choices! 🤯 (Part 6)` |
| 328,350 | 1,210 | 51s | `Nike or adidas #reaction #funny #wouldyourather #quiz` |

And the single most useful one — a channel at a size you can actually reach,
running exactly this format as a numbered series:

> **Skydaaguy** — 125K subs, 6 WYR videos in the sample, **median 7,802,883 views**
> `Would You Rather 21!? ✅❌ #minecraft #funny`
> `Would You Rather 12!? ✅❌ #minecraft #funny` — 18,783,367 views

Numbered. Emoji marker. Two topic hashtags. No edition word, no punctuation
noise. That is the pattern the title format below copies.

**Emoji in the title are neutral** — 24,857 median with, 26,574 without, n=260.
Use them to break up the line, not to buy reach.

---

## Title format

```
Would You Rather <N> — <EDITION> <emoji> #wouldyourather #food
```

The phrase leads so it survives mobile truncation. The number is bare rather
than `#1`, so it cannot be misread as a hashtag. Hashtags sit last, where
truncation hides them from the reader but not from topic association.

> This changes episode 1's title from the `Would You Rather... #1 FOOD EDITION`
> in `publish-ep001.md`. Nothing is published yet, so setting the convention now
> costs nothing — and a series that changes its title format at episode 2 is
> worse than either format.

---

## The five episodes

All five draw from the food bank (48 dilemmas, 43 unused after episode 1). Each
follows the DNA's difficulty ramp — easy and funny first, hardest last — and
each carries at least one dilemma flagged `counterintuitive`, which is the block
that produces comments.

### Episode 1 — FOOD EDITION
`d0001 · d0012 · d0022 · d0031 · d0041` — already built, `out/wyr-ep001-food-edition.mp4`

**Title**
```
Would You Rather 1 — FOOD EDITION 🍕 #wouldyourather #food
```
**Description**
```
5 impossible food choices. Which ones did you get?

Comment what you'd like to see in the next video.

#wouldyourather #thisorthat #shorts
```
**Pinned comment**
```
What should the next five be? Best ideas in the comments go into episode 2.
```

---

### Episode 2 — IMPOSSIBLE EDITION
`d0006 · d0002 · d0010 · d0007 (CI) · d0026`

whole lemon vs spoon of mustard → never pizza vs never fries → fries always
soggy vs always cold → chocolate tastes like fish vs soap → taste nothing vs
eat only greens

**Title**
```
Would You Rather 2 — IMPOSSIBLE EDITION 🤯 #wouldyourather #food
```
**Description**
```
The last one has no right answer. Which ones did you get?

Comment what you'd like to see in the next video.

#wouldyourather #thisorthat #shorts
```
**Pinned comment**
```
Number 4 broke everyone. A or B — settle it in the replies.
```

---

### Episode 3 — BREAKFAST EDITION
`d0003 (CI) · d0005 · d0014 · d0015 · d0017 (CI)`

cereal first vs milk first → coffee always cold vs always burnt → free coffee
forever vs free breakfast forever → never coffee vs never energy drinks → cut
out bread forever vs rice forever

Opening on cereal-versus-milk is deliberate: it is the one dilemma here the
internet already argues about, so block 1 arrives pre-loaded.

**Title**
```
Would You Rather 3 — BREAKFAST EDITION ☕ #wouldyourather #food
```
**Description**
```
Milk first is a crime. Prove me wrong in the comments.

Comment what you'd like to see in the next video.

#wouldyourather #thisorthat #shorts
```
**Pinned comment**
```
Cereal first or milk first. Reply A or B — I'm counting them.
```

---

### Episode 4 — HARD EDITION
`d0009 · d0011 · d0018 · d0013 (CI) · d0040`

eat a burger like corn vs with a spoon → unlimited free pizza vs sushi → every
meal too spicy vs totally bland → only sweet vs only salty → give up chewing vs
drinking

`HARD EDITION` is a measured title word in this niche — an 89.9K-sub channel
runs `HARD EDITION! (Episode 5)`, and two of the proof cases above use
"Hard Questions" and "Hard Choices".

**Title**
```
Would You Rather 4 — HARD EDITION 💀 #wouldyourather #food
```
**Description**
```
No easy ones this time. How many did you actually answer?

Comment what you'd like to see in the next video.

#wouldyourather #thisorthat #shorts
```
**Pinned comment**
```
Giving up chewing or drinking — nobody agrees on this one. Which?
```

---

### Episode 5 — TOGETHER OR ALONE EDITION
`d0004 · d0019 · d0032 · d0028 (CI) · d0048`

forced ketchup on pasta vs mayo on pizza → never order takeout vs never cook
again → every meal made by your enemy vs a random kid → never eat with anyone
vs never eat alone again → eat perfectly alone vs badly with people

This is the first episode that is about people rather than food, while staying
inside the food vertical. If it outperforms, that is the signal to widen the
bank past food earlier than episode 20.

**Title**
```
Would You Rather 5 — TOGETHER OR ALONE 🍽️ #wouldyourather #food
```
**Description**
```
The last two stopped being about food. Which did you pick?

Comment what you'd like to see in the next video.

#wouldyourather #thisorthat #shorts
```
**Pinned comment**
```
Eat perfectly alone, or badly with people? Reply A or B.
```

---

## Settings — identical for all five

| Setting | Value | Why |
|---|---|---|
| **Made for kids** | **No — "Not made for kids"** | The one switch that can kill the strategy. Made-for-kids **disables comments**, and comments are this format's whole engine. |
| Age restriction | No | |
| Category | Entertainment | |
| Video language | English (United States) | |
| Title language | English | |
| Comments | **On**, sorted by **Top**, no hold-for-review | Holding comments delays the signal the format runs on. |
| Allow remixing | Yes | Free distribution; nothing here is worth protecting. |
| Paid promotion | No | |
| Licence | Standard YouTube Licence | |
| Playlist | **Would You Rather** — add all five | Reinforces the series the numbered title promises. |
| Visibility | Public (or Scheduled) | |
| Thumbnail | A frame from block 1 | Shorts rarely surface it; the browse and channel tabs do. |
| Location / recording date | leave blank | No effect on Shorts distribution. |

**Tags field** — same for all five, ~460 characters:

```
would you rather, would you rather game, would you rather questions, this or that,
wyr, would you rather food, impossible choices, quiz, food quiz, hard choices,
would you rather hard, this or that game, food edition, shorts
```

Tags carry little ranking weight now. They are free, and they help a channel
with no history disambiguate what it is.

---

## Cadence

**One per day, at the same time, for at least 14 days.**

The reasoning is not about an optimal interval — it is that your channel has
**7 videos in 70 days and 1 subscriber**. At that volume YouTube has no basis to
classify the channel or find its audience. Volume is the first fix, and the
pipeline is scripted, so the marginal cost of episode 6 is a build command.

Five episodes is five days. Do not batch-publish them in one afternoon: each
upload is a separate test, and same-day uploads compete with each other for the
same impressions.

If daily is not sustainable, **every other day beats an inconsistent daily**. A
schedule you hold is worth more than a schedule you intended.

## Time of day

**I cannot answer this from data, and I am not going to pretend otherwise.**

Upload hour against views, <100K subs, cells with n≥8:

| Hour UTC | n | Median |
|---|---|---|
| 00:00 | 9 | 199,945 |
| 14:00 | 25 | 61,586 |
| 16:00 | 20 | 25,479 |
| 21:00 | 25 | 18,279 |
| 17:00 | 15 | 2,736 |
| 18:00 | 10 | 2,718 |

A 73× spread between 00:00 and 18:00 is not a time-of-day effect — it is which
channels happened to upload in those cells. Nine videos decide the top row.
Anyone selling you a "best time to post" off a table like this is reading noise.

What is actually true: **Shorts are feed-distributed, not subscription-gated**,
so upload time matters far less than it does for long-form. A Short picked up by
the feed gets served over hours and days, not in the first evening.

**Practical default — hold this unless your own data says otherwise:**

> **18:00–20:00 Italian time** (16:00–18:00 UTC in winter, 17:00–19:00 in summer)

The case for it is not in the table above: it puts the upload in front of the
Italian evening and the US late-morning/midday at the same time, and it is a
slot you can realistically hit every day. **Consistency is the part that
matters** — a fixed slot lets you read your own analytics later without upload
time being a confounding variable.

**The real answer arrives in about three weeks.** After 15–20 uploads at a fixed
time:

```bash
cd .agents/skills/youtube-channel-insights
python3 scripts/fetch_insights.py traffic --video <id>
```

Then read your own audience's active hours in YouTube Studio → Analytics →
Audience → *When your viewers are on YouTube*. That is measured on your viewers,
which no competitor table can substitute for.

---

## Before you schedule any of this

**The artwork is still unresolved.** `dna/video-dna.json` → `images.open_decision`.
Episode 1 currently ships emoji you rejected. Five videos published with artwork
you do not want is five videos of first impressions you do not get back. Settle
the image source before uploading, not after.

**Episode 1's music will be claimed.** The bed is a commercial track. Content ID
will almost certainly match: the video stays up, monetisation goes to the rights
holder, and some territories may block it. Known trade, not a surprise — but if
you would rather not hand episode 1's revenue away, swapping the bed is a
one-line change to the cue point in `build_episode.py`.

**Episodes 2–5 do not exist yet.** The lineups above are chosen and validated
against the bank, but the episode files, voiceover and renders still have to be
produced. `README.md` → *Make a video* has the sequence.
