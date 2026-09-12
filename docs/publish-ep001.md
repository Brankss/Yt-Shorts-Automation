# Publish sheet — episode 1

File: `out/wyr-ep001-food-edition.mp4`
1080×1920 · 30fps · 54.10s · H.264 + AAC · normalised to −14 LUFS

Block length varies: the timer starts when each question stops speaking, so a
block runs as long as its own question needs. Five of them plus the end card
land at 54.10s — inside the 41–60s band. The end card is measured too: the
closing line, one second of tick alone, then the chime ringing out.

---

## Title

> **SUPERSEDED 2026-09-12.** The series title format is now
> `Would You Rather 1 — FOOD EDITION 🍕 #wouldyourather #food`, set once for all
> five episodes in `docs/publish-plan-ep001-005.md`. Nothing is published yet, so
> the convention was cheaper to fix now than at episode 2. (The numbering
> rationale below was also retracted later the same day — see the next note.)

```
Would You Rather... #1 FOOD EDITION
```

35 characters. Two decisions in it, both measured.

> **RETRACTED 2026-09-12.** Within-channel analysis (40 full catalogues, 4,341
> Shorts) shows numbering has no effect: 5 wins / 4 losses across the channels
> that do both, median ratio 1.08x. The large cross-channel gaps cited here are
> channel-size confounding. Keep numbering for viewer convenience, expect no
> reach from it. See `docs/niche-research-2026-09-12.md`.

**The series number stays.** Titles in this niche carrying `#N`, `part N` or
`episode N` have a median of **9,734,657** views against **10,430** without
(n=10 vs 66). That gap is mostly confounded — established series channels have
both the numbering *and* the audience, and the numbering did not cause the
views. But it costs nothing, it is what the format's biggest channels all do,
and it gives a returning viewer something to return to.

**No hashtags in the title.** See below.

## Description

Paste as-is:

```
5 impossible food choices. Which ones did you get?

Comment what you'd like to see in the next video.

#wouldyourather #thisorthat #shorts
```

## Hashtags — where they go, and why

> **SUPERSEDED 2026-09-12 — this section's conclusion is reversed.** A re-pull
> with roughly 6× the sample (260 videos from channels under 100K subs, against
> the 76 below) puts *zero* hashtags in the title in the worst-performing cell,
> not the best, and the proven channels in the niche all carry them. The current
> recommendation — **2 hashtags in the title** — and the reasoning for changing
> it are in `docs/publish-plan-ep001-005.md`. The table below is kept because
> the disagreement between the two samples is itself the useful finding: on a
> metric this skewed, samples this small are not reliable evidence in either
> direction.

The original conclusion follows. **The description only.**

Measured across 76 English Shorts in this niche, counting real hashtags and
excluding `#9`-style episode numbers:

| Real hashtags in title | n | Median views |
|---|---|---|
| **0** | 13 | **492,170** |
| 1 | 12 | 7,482 |
| 2 | 9 | 5,272 |
| 3 | 19 | 21,101 |
| 4+ | 23 | 12,202 |

Treat the size of that gap with suspicion — it is a small sample and the clean
titles belong disproportionately to bigger channels. But nothing in the data
suggests hashtags in a title *help*, and they cost the one thing a Shorts title
has: the handful of words a viewer reads before deciding.

*(My first pass at this got it backwards, reading `#9` and `#43` as hashtags
when they were episode numbers. The table above excludes them.)*

**In the description they earn their place.** YouTube renders the first three as
clickable links above the title and uses them for topic association. Three is
the useful maximum — past that they stop being displayed and start looking like
spam.

The three chosen come from the niche's measured tag cloud: `would you rather`
appears on 41 videos, `this or that` on 24. `#shorts` is no longer required for
Shorts classification — aspect ratio and duration decide that — but it is
conventional and harmless.

## Tags field

```
would you rather, quiz, would you rather game, this or that, wyr,
would you rather questions, impossible choices, would you rather food, shorts
```

Tags carry little ranking weight now. They are cheap, they help disambiguate a
new channel with no history, and that is the whole case for them.

## Pinned comment

Post it, then pin it, immediately after upload:

```
What should the next five be? Best ideas in the comments go into episode 2.
```

It asks for the same thing the video's last frame asks for. A pinned comment
that contradicts the end card just splits the audience's attention.

## Upload settings

| Setting | Value | Why |
|---|---|---|
| **Audience** | **Not made for kids** | The single most important switch here. Made-for-kids **disables comments**, and comments are this format's engine. Getting it wrong makes the strategy impossible. |
| Age restriction | No | |
| Category | Entertainment | |
| Language | English (United States) | |
| Comments | On, sorted by **Top**, no hold-for-review | Holding comments for review delays exactly the signal we want early. |
| Allow remixing | Yes | Free distribution; nothing here is worth protecting from a remix. |
| Paid promotion | No | |
| License | Standard YouTube License | |
| Playlist | Create **Would You Rather**, add every episode | Reinforces the series the title promises. |
| Visibility | Public | |
| Thumbnail | Pick a frame from the first block | Shorts rarely show it, but the browse surface sometimes does. |

**One thing to know before you upload.** The music bed is a commercial track.
YouTube's Content ID will almost certainly match it: the video stays up, but
monetisation goes to the rights holder, and in some territories it can be
blocked outright. That is the trade being made, not a surprise waiting to
happen — swapping in a licensed or royalty-free bed later is a one-line change
to the cue point in `build_episode.py`.

## What I could not settle from data

**When to post.** Your channel has 547 views over 28 days across 7 videos — not
enough for a posting-time signal that means anything. Pick a time you can hold
daily and let three weeks of `youtube-channel-insights` decide it later. The
consistency matters more than the hour.

---

## About the percentages

They are written, not measured — your call, and the episode file labels them
`"source": "authored"` so no file ever quietly passes an invented figure off as
a counted one.

The evidence I raised against it still stands and is worth keeping in view: the
most-liked comment across every breakout video mined was people mocking a
channel's percentages. But what they caught was arithmetic — figures that did
not add to 100. Every split here sums to 100 exactly, and
`validate_content.py` fails the build if one ever does not.

Splits for this episode: 68/32 · 57/43 · 61/39 · **23/77** · **79/21**. Two are
deliberately lopsided, which is where the format's engine lives — a viewer
discovering they are in a minority they did not expect.

## Community-tab polls, for later

`docs/strategy.md` originally built the growth loop on Community polls. **YouTube
gates the Community tab at 500 subscribers** and the channel has 1, so that
route is closed for now regardless. When it opens, real counted numbers are a
straight upgrade over authored ones — the episode schema already takes
`community_poll` and `comment_poll` as sources.
