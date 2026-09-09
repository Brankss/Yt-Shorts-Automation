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
   │  assemble → split → script → voice → art → build → render   │
   │  → publish → measure                                        │
   └──────────────────────────┬──────────────────────────────────┘
                              │  retention per block
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

### B2. Set the percentages

Write a split on every block. They are authored rather than measured — the
channel owner's call — and each block records `"source": "authored"` so a file
never passes an invented figure off as a counted one.

Two rules, both enforced by `validate_content.py`:

- **Sum to 100.** This is the failure viewers actually catch. The most-liked
  comment across every breakout video mined was people mocking a channel's
  arithmetic: *"How tf is 90 % and 15%"*, 148 likes.
- **Top share between 55 and 88.** Under that reads as a coin flip and provokes
  nothing; over it is not a dilemma. At least one block per episode should sit
  near the top of the band — a viewer discovering they are in an unexpected
  minority is the whole engine.

When the channel passes 500 subscribers the Community tab unlocks and counted
numbers become available; `community_poll` and `comment_poll` are already
accepted sources and are a straight upgrade.

### B3. Script

One line per block: the question, ≤14 words, written into the episode file.
`validate_content.py` enforces the count. It speaks the stem and both fragments —
the only place the stem exists, since the screen shows the fragments alone.

**The reveal is silent.** Nothing is spoken over the percentages: a line there
would tell the viewer what to think about a number they are still reading.

Then voice it:

```bash
python3 scripts/make_voiceover.py content/episodes/ep001.json
```

Kokoro, offline, free. Every hosted TTS is unreachable from these sessions —
HeyGen, Microsoft's Edge voices, Google Translate and ElevenLabs all answer 403
through the egress proxy — but GitHub release assets get through, and that is
where Kokoro publishes its weights. They live in `~/.cache/kokoro` (338MB,
outside the repo); generation itself touches no network.

One clip per block, and only the question. The reveal is silent: the
percentages land with the chime and nothing explains them away.

`make_voiceover.py` measures each clip and writes its length back into the
episode file. That measurement is what the next stage times the video to.

**The voice is identity, not a setting.** `am_adam` stays fixed across episodes
for the same reason the palette does — a channel is recognised by its sound
before its layout. Swapping to a recorded human voice later is an upgrade worth
making; swapping between synthetic voices episode to episode is just noise.

### B3b. Source the images

Ten subjects per episode, one per fragment. Every dilemma in the bank already
carries `image_a` / `image_b`, so this stage is normally just:

```bash
node scripts/export_icons.mjs
```

which writes one SVG per referenced icon into `videos/wyr-template/assets/`.
Reuse is the point — `pizza` comes up often, and a stable picture for a
recurring fragment makes the channel more recognisable, not less.

**This stage is unresolved — see `dna/video-dna.json` → `images.open_decision`.**

The current source is the `@iconify-json/noto` npm package (Apache-2.0, 3,800
icons). That was not a design choice: the session that built this pipeline ran
behind an egress policy that returned 403 for every image CDN *and* every image
API, while leaving the npm registry reachable, so the artwork had to come from a
package. Off that sandbox the constraint is gone.

It half works. Emoji are strong for concrete nouns — pizza, a lemon, a battery —
and weak for people, feelings and actions, which render as a yellow face.
"Sadness" becomes a circle. About a third of the bank's fragments are in that
weak class, and the channel owner rejected the result.

The DNA sets out three options — generate them, buy stock, or keep emoji for
nouns and add a second source for people — and recommends generating, with the
style prompt frozen into the DNA so all 96 fragments share one look. Whatever is
chosen, adopting it is a change to `image_a` / `image_b` in the bank plus a new
export step. **Nothing in the composition changes**: the box is 420px with
`object-fit: contain` and does not care what it is handed.

New fragments need a mapping before they can ship. `export_icons.mjs` exits
non-zero and names any icon it cannot find.

### B3c. Build

```bash
python3 scripts/build_episode.py content/episodes/ep001.json
```

Writes the content, the block timings, the audio placement and the root duration
into the composition, between markers. Everything outside those markers — the
split, the type, the motion — is untouched.

**Block length is not fixed.** The timer starts when the question stops
speaking, so each block runs `0.2s + question + 3.5s timer + 2.5s hold + 0.35s
exit`. A fixed block would have the timer running while the question was still
being asked, and the viewer would be timed on a choice they had not finished
hearing. The cost is that the timings cannot be authored by hand, which is what
this stage is for. It warns if the total leaves the 41–60s band.

The same stage cuts the two episode-length audio beds from the owner's source
files in `assets/source/` (gitignored): the end-card tick, which runs one second
past the closing line, and the music, from its cue point for exactly the length
of the video. Neither can be a fixed asset because both depend on how long the
episode turned out to be.

### B4. Render

```bash
cd videos/wyr-template && npx hyperframes check && npx hyperframes render
```

`ffmpeg` and `ffprobe` are not in the base image; the static binaries from the
`ffmpeg-static` and `ffprobe-static` npm packages work and need no apt.

Then normalise and land the publishable file:

```bash
ffmpeg -i renders/<latest>.mp4 -af "loudnorm=I=-14:TP=-1.5:LRA=11" \
  -t <total> -c:v copy -c:a aac -b:a 192k out/wyr-ep001-food-edition.mp4
```

The explicit `-t` matters: `loudnorm` adds about 100ms of lookahead padding, and
the last frame has to match the first for the Shorts loop to close.

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
README.md                     setup from a clean machine, and how to run it
CLAUDE.md                     orientation + the hard rules, for an agent
dna/
  video-dna.json              binding style + structure spec — normative
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
  publish-ep001.md            title, description, tags, settings, rights notes
scripts/
  validate_content.py         schema + DNA-rule check
  make_voiceover.py           Kokoro TTS, measures clip durations
  build_episode.py            episode JSON → composition, between markers
  export_icons.mjs            image refs in the bank → SVGs on disk
  make_sfx.py                 legacy synthetic SFX (superseded)
  niche_scorecard.py          niche comparison, conditioned on channel size
  auth_write_manual.py        two-step OAuth for the write scope
videos/wyr-template/          the HyperFrames composition
  assets/source/              owner-supplied audio (gitignored, required)
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
