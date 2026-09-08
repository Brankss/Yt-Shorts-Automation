---
workflow: general-video
flow: automation
storyboard: no
message: "You are in the minority and you did not know it"
destination: youtube-shorts
aspect: 1080x1920
language: en
audience: "Shorts viewers who will not scroll past an unresolved choice"
length: 46s
---

## Intent

A reusable template, not an episode. It renders one Would You Rather Shorts
episode: five dilemmas, each ending in a percentage reveal, then a card pointing
at the poll that produces the next episode's numbers.

Content arrives from an episode file validated against
`content/schemas/episode.schema.json`. Everything else — structure, timing,
palette, type, motion — is fixed by `dna/video-dna.json` and must not vary
between episodes. That is the whole point of the template: two episodes built
weeks apart should differ only in their words and their numbers.

The build is deliberately stopping before any episode is rendered. The user
asked for the template and explicitly not for the first video.

## Assets

- `../../dna/video-dna.json` — binding style and structure spec; brand truth.
- `../../content/dilemmas.json` — the dilemma bank the episodes draw from.
- `../../content/schemas/episode.schema.json` — the shape of the content slots.

## Customizations

- Content slots are populated from a JSON island in the composition, so a build
  step can swap an episode without touching structure or motion.
- The percentage reveal is the engagement mechanic and carries the strongest
  motion accent in each block; everything else stays quiet so it lands.

## Notes

- Duration is not a stylistic choice. In this niche 16–25s videos have a median
  of 751 views against 26,239 for 41–60s, so the five 8.5s blocks exist to land
  inside that band. Do not shorten it.
- The Shorts player draws its own UI over the frame. Nothing meaningful may
  enter the safe bands in the DNA — 200px top, 380px bottom, 140px right.
- Percentages are real Community-poll results or absent. Never invented.
- No borrowed IP, characters, or footage: the motion design has to carry it.
