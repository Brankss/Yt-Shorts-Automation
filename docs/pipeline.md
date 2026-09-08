# Production pipeline

Two pipelines. The first turns signals into a bank of scored dilemmas. The second
turns a set of five of them into a published video. They run at different
cadences on purpose: ideas are harvested in batches, videos are produced daily.

```
   ┌──────────────── PIPELINE A — ideas (weekly) ────────────────┐
   │  harvest → score → bank                                     │
   └──────────────────────────┬──────────────────────────────────┘
                              │  content/dilemmas.json
   ┌──────────────────────────▼──────────────────────────────────┐
   │  PIPELINE B — video (daily)                                 │
   │  assemble → poll → script → render → publish → measure      │
   └──────────────────────────┬──────────────────────────────────┘
                              │  real percentages + retention
                              └──────────────► back into scoring
```

---

## Pipeline A — idea creation

Runs weekly. Produces enough dilemmas for 7–10 episodes so that Pipeline B never
blocks on writing.

### A1. Harvest

Four sources, in descending order of value:

| Source | Tool | What it yields |
|---|---|---|
| Comments on our own videos | `youtube-comment-miner --channel @branks.s` | Dilemmas the audience proposed themselves, and the ones they argued about |
| Comments on competitors' breakouts | `youtube-comment-miner --videos <ids>` | What provokes in this niche right now |
| Trending in the niche | `youtube-trending-scanner "would you rather"` | Rising sub-formats before they saturate |
| Adjacent verticals | `youtube-topic-researcher "<vertical> shorts"` | New territory once food is exhausted |

The first source is the one that compounds. Every episode we publish makes the
next harvest better, which is the whole reason the poll loop exists.

### A2. Score

Each candidate dilemma gets scored 1–5 on four axes. The product of the four is
the rank; anything with a zero on any axis is discarded rather than fixed.

| Axis | Question | Fails when |
|---|---|---|
| **Polarization** | Will the split land between 55/45 and 88/12? | Everyone picks the same option, or it is a pure coin flip |
| **Universality** | Does it apply to essentially everyone watching? | Needs a sister, a car, a job — the `What happens if I don't have a sister` failure, 138 likes on that complaint |
| **Instant read** | Both fragments understood in under 2 seconds? | Needs a clause, a condition, or an "unless" |
| **Imageable** | Does each fragment name one photographable thing? | Nothing to picture, so the field stays flat |

Dilemmas are written as a **spoken stem plus two short fragments** — "would you
rather never feel / pain again / sadness again". The stem never appears on
screen. Fragments are capped at 22 characters and target 16, which is one line.

### A3. Bank

Scored dilemmas land in `content/dilemmas.json` against
`content/schemas/dilemma.schema.json`, each with a `status` of `banked`,
`scheduled`, `polled`, or `used`. A dilemma is never reused, but its *result* is
reusable forever — the percentages become reference material for future scoring.

---

## Pipeline B — video creation

Runs per episode. Each stage has one input and one output, so any stage can be
rerun without redoing the others.

### B1. Assemble

Pick 5 banked dilemmas matching the difficulty ramp in the DNA
(`copy_rules.difficulty_ramp`): easy+funny, easy, medium, hard, hardest. At least
one must be flagged `counterintuitive` — that is the block that produces the
comments. Write the episode file against `content/schemas/episode.schema.json`.

### B2. Poll

Post the 5 dilemmas as Community-tab polls. This happens **one episode ahead**:
while episode N renders, episode N+1's dilemmas are already collecting votes.

Episode 1 has no prior poll, so its blocks use `prediction_no_number` framing.
From episode 2 on, percentages are real.

*This stage is manual for now — the YouTube Data API cannot create Community
posts. It is roughly two minutes per episode in YouTube Studio.*

### B3. Script

Two lines per block, written into the episode file: ≤14 words on the setup at
+0.2s, ≤10 words on the reaction at +4.4s. `validate_content.py` enforces both
counts. The setup speaks the stem and both fragments — this is the only place
the stem exists, since the screen shows the fragments alone. The reaction names
the surprise in the result and never re-explains the dilemma.

**Voicing it is the one stage that cannot run in these sessions.** HeyGen's
endpoints return 403 through the egress proxy, exactly like the image CDNs, so
`npx hyperframes tts` has nothing to reach. Three ways forward, in order of how
good the channel ends up sounding:

1. **Record it yourself.** A recognisable human voice is worth more to a channel
   building an identity than any synthetic one, and the script is 24 short lines.
2. **HeyGen from a machine that can reach it** — `npx hyperframes auth login`,
   then `npx hyperframes tts` against the episode file.
3. **Kokoro, the offline local engine** — `pip install kokoro-onnx soundfile`,
   free and no network at generation time, though its model weights have to be
   fetched once from somewhere reachable.

The rendered audio drops in as `<audio>` elements at the composition root
alongside the sound effects, two per block, at the times above.

**Until the voiceover exists the video is not shippable.** Two words on two
colours are not a question — the sound effects give it rhythm, not meaning.

### B3b. Source the images

Ten subjects per episode, one per fragment. Every dilemma in the bank already
carries `image_a` / `image_b`, so this stage is normally just:

```bash
node scripts/export_icons.mjs
```

which writes one SVG per referenced icon into `videos/wyr-template/assets/`.
Reuse is the point — `pizza` comes up often, and a stable picture for a
recurring fragment makes the channel more recognisable, not less.

**On where the artwork comes from.** Photographic cut-outs are what the
reference videos use and remain the stronger treatment. They need an image
source, and this project's sessions run behind an egress policy that returns
403 for every image CDN. Artwork therefore comes from the `@iconify-json/noto`
npm package (Apache-2.0, 3,800 icons) — npm is reachable directly, the files
land on disk, and nothing is fetched at render time.

To move to photographs later: change `image_a` / `image_b` in the bank to point
at the new files. Nothing in the composition changes.

New fragments need a mapping before they can ship. `export_icons.mjs` exits
non-zero and names any icon it cannot find.

### B4. Render

Invoke the `hyperframes` skill on the `/general-video` route, handing it the
episode file plus `dna/video-dna.json`. The DNA is binding: the render fills the
content slots and nothing else. Output goes to `out/wyr-ep{NNN}-{slug}.mp4`.

Before publishing, check the render against `dna/video-dna.json` → `invariants`.

### B5. Publish

Title, description and tags follow the patterns measured in the niche:

- **Title:** `Would You Rather... #{N}` — the 1.53M-subscriber channel's numbered
  series holds 75M, 18.6M and 15.1M views on episodes 9, 39 and 43. Add an
  edition tag when the episode has one: `FOOD EDITION`, `HARD EDITION`.
- **Tags:** the measured cloud for this niche — `would you rather`, `quiz`,
  `would you rather game`, `this or that`, `wyr`, `impossible choices`,
  `would you rather food`.
- **Pinned comment:** the poll link, plus the question that turns viewers into
  commenters — `which ones did you get?`

`youtube-metadata-updater` can rewrite titles and descriptions after the fact if
a pattern turns out to underperform.

### B6. Measure

After 72 hours (YouTube Analytics settles at ~3 days):

```bash
cd .agents/skills/youtube-channel-insights
python3 scripts/fetch_insights.py retention --video <id>
python3 scripts/fetch_insights.py traffic --video <id>
```

Three questions, three actions:

| Reading | Means | Action |
|---|---|---|
| Drop before 0:08 | Block 1 failed as a hook | Re-score that dilemma's polarization; never open with that type again |
| Drop at a block boundary | The transition is losing people | Shorten the hold phase in the DNA and bump the version |
| Traffic mostly `SHORTS` and rising | The format is being distributed | Publish more of exactly this |

Retention per block is the only feedback that matters. View counts on a single
video tell us nothing this early.

---

## Repository layout

```
dna/
  video-dna.json              binding style + structure spec
  README.md                   how to read and change it
content/
  schemas/
    dilemma.schema.json       one dilemma
    episode.schema.json       five dilemmas + episode metadata
  dilemmas.json               the bank
  episodes/ep001.json         one file per episode
docs/
  strategy.md                 why this niche, backed by the pulled data
  pipeline.md                 this file
scripts/
  niche_scorecard.py          niche comparison, conditioned on channel size
  auth_write_manual.py        two-step OAuth for the write scope
out/                          rendered mp4s (gitignored)
reports/                      skill output (gitignored)
```

## Cadence

| | |
|---|---|
| **Publish** | 1 episode/day. The channel's current problem is 7 videos in 70 days; volume is the first fix. |
| **Harvest** | Weekly, batch of 40–50 dilemmas |
| **Poll** | Daily, one episode ahead |
| **Measure** | Weekly, on the previous 7 episodes together |
| **DNA review** | Every 20 episodes, only against retention data |
