# Video DNA

`video-dna.json` is the channel's visual and structural identity expressed as
values rather than adjectives. It exists so that two videos built weeks apart, in
different sessions, come out identical in everything except their content.

## Why a file and not a style guide

"Bold typography, dark background, energetic pacing" produces a different video
every time it is read. `"option": { "size": 76, "case": "uppercase", "tracking": -0.01 }`
produces the same one. Anything an agent could reasonably interpret two ways is a
gap in the DNA, and gaps are what make a channel look like six different channels.

When you find yourself making a judgement call during a render, that call belongs
in this file. Add it, bump `meta.version`, and move on.

## How to use it

Every render reads the DNA first and treats it as binding:

1. Load `video-dna.json`.
2. Build the composition from `timeline`, `layout`, `color`, `typography`, `motion`.
3. Fill only the content slots: 5 dilemmas, their percentages, the VO lines, the
   episode number.
4. Before rendering, check the output against `invariants`. A violation is a bug.

The content slots are the *only* freedom. Everything else is already decided.

## Structure of an episode

```
0.0s ─┬─ BLOCK 1   easy + funny      ← this is the hook; no intro exists
      │  0.0  cards enter (A from left, B from right, 80ms apart)
      │  0.5  timer ring starts, 3500ms, yellow
      │  4.0  reveal: bars fill, numbers count up
      │  4.7  hold — VO lands the second line here
      │  8.1  cards exit toward opposite edges
8.5s ─┼─ BLOCK 2   easy
17.0s─┼─ BLOCK 3   medium
25.5s─┼─ BLOCK 4   hard
34.0s─┼─ BLOCK 5   hardest           ← the one people argue about
42.5s─┴─ END CARD  poll CTA, 3.5s
46.0s    loop point — last frame matches frame 1
```

## The two rules that are not about style

**Duration.** 41–60 seconds. In this niche, and against every instinct about
Shorts, short videos collect nothing: 16–25s videos have a median of 751 views,
41–60s have 26,239. The 8500ms block length exists to land inside that band with
five blocks. Do not "tighten" it.

**Percentages.** They come from a real Community-tab poll, or the block makes a
prediction with no number. Never invented. This is in the DNA rather than the
strategy doc because it is a property of the artifact: a viewer can check whether
two numbers add to 100, and across every breakout video we mined, they do.

## Mapping to HyperFrames

HyperFrames renders video from HTML whose DOM declares timing through `data-*`
attributes. The DNA maps onto that directly:

| DNA | HyperFrames |
|---|---|
| `canvas` | composition dimensions and fps |
| `timeline.block_phases` | `data-start` / `data-duration` on each block's elements |
| `layout` | absolute positioning inside the 1080×1920 stage |
| `color`, `typography` | CSS custom properties emitted once at the top of the composition |
| `motion` | keyframes and easing on the animated properties |
| `render` | encoder settings for the render step |

Route: `/general-video` — a multi-scene custom composition. Not `/motion-graphics`,
which is for unnarrated units under 10s, and not `/faceless-explainer`, which
invents its own visual language per topic. We already have ours; that is the point.

## Changing the DNA

- Content changes need no DNA change.
- A visual change needs a `meta.version` bump and a note on what measurement
  prompted it. Retention curves and comment volume are the only valid reasons.
- Entries under `invariants` are what makes the channel recognizable in a feed.
  Changing one resets that recognition to zero, so it needs a real argument, not
  a preference.
