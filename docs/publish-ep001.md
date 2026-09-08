# Publish sheet — episode 1

File: `out/wyr-ep001-food-edition.mp4`
1080×1920 · 30fps · 46.000s · H.264 + AAC · 4.4MB · normalised to −14 LUFS

---

## Title

```
Would You Rather... #1 FOOD EDITION
```

35 characters. Two decisions in it, both measured.

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

Reply A or B on each one in the comments — the next episode reveals what everyone actually picked.

#wouldyourather #thisorthat #shorts
```

## Hashtags — where they go, and why

You asked whether they belong in the title, the description, or both. **The
description only.**

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
Reply with your five: A or B. Episode 2 shows the real numbers — no made-up percentages on this channel.
```

This is not a nicety. It is the mechanism that produces episode 2's percentages.

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

## What I could not settle from data

**When to post.** Your channel has 547 views over 28 days across 7 videos — not
enough for a posting-time signal that means anything. Pick a time you can hold
daily and let three weeks of `youtube-channel-insights` decide it later. The
consistency matters more than the hour.

---

## One correction to the strategy

`docs/strategy.md` builds the growth loop on Community-tab polls. **YouTube gates
the Community tab at 500 subscribers**, and the channel has 1. That loop cannot
start yet, and I should have checked it before designing around it.

The comment poll replaces it and is arguably better at this size:

```
Episode N     asks five dilemmas, pinned comment asks for A/B replies
                  ↓
Comments      real viewers answer, in public, where other viewers see them
                  ↓
Episode N+1   opens on the real counts, then asks five new dilemmas
```

Same honest numbers, no subscriber gate, and it forces the comment behaviour the
channel is missing outright — 0 comments across all 7 existing videos. The
episode schema now takes `comment_poll` as a reveal source alongside
`community_poll`, with the same rule: real counts or no number at all.

Move to Community polls at 500 subscribers, when they become cleaner to tally.

## Episode 1 has no numbers

Every block states a prediction rather than a percentage, because there is no
prior poll to draw from. That is the honest opening, and the end card says so:
*real numbers in episode 2*. From episode 2 the reveals carry counted replies.
