# Yt-Shorts-Automation

An automated production line for YouTube Shorts on the channel **Branks**
(`@branks.s`). One format: *Would You Rather* — a split red/blue screen, five
dilemmas, a spoken question, a timer, a percentage reveal.

Everything here is built so a video can be produced by running scripts rather
than by hand-editing a composition. If you find yourself hand-editing the
rendered HTML, you are working against the design.

---

## Read this first, in this order

1. **`dna/video-dna.json`** — the binding spec. Canvas, timing, layout, colour,
   type, audio, copy rules, image rules, invariants. It is normative: the
   composition, the validator and the docs all have to agree with it, and when
   they disagree *this file is right and they are wrong*.
2. **`dna/README.md`** — how to read and change the DNA.
3. **`docs/strategy.md`** — why this niche, backed by pulled channel data.
4. **`docs/pipeline.md`** — the two pipelines (ideas, video) stage by stage.

The DNA's `invariants` list is the short version. If a change would break one of
those lines, it is not a tweak — stop and raise it.

## Repo map

```
dna/video-dna.json       the spec. Start here.
content/
  dilemmas.json          the bank — 48 scored dilemmas
  episodes/ep001.json    one file per episode: content, timing, publish metadata
  schemas/               JSON Schema for both of the above
scripts/
  validate_content.py    schema + DNA-rule check. Run it after every content edit.
  make_voiceover.py      Kokoro TTS → per-segment WAVs, writes durations back
  build_episode.py       episode JSON → composition HTML (between markers)
  export_icons.mjs       resolves image refs in the bank into SVGs on disk
  make_sfx.py            legacy synthetic SFX (superseded by the owner's own files)
  niche_scorecard.py     niche comparison, conditioned on channel size
  auth_write_manual.py   two-step OAuth for the YouTube write scope
videos/wyr-template/     the HyperFrames composition (has its own CLAUDE.md)
docs/                    strategy, pipeline, per-episode publish packages
out/                     rendered mp4s (gitignored)
```

## Hard rules

**The DNA is versioned, and every change records why.** `meta.changelog` is a
list of `{version, change, reason}`. The reason is the point — it should cite
evidence or an explicit decision by the channel owner, not taste. Bump the
version in the same edit.

**Generated regions of `index.html` are off limits.** `build_episode.py`
rewrites three marker-delimited regions:

```
<!-- EPISODE:START --> … <!-- EPISODE:END -->     episode data island
<!-- BLOCKS:START  --> … <!-- BLOCKS:END  -->     per-block DOM
<!-- AUDIO:START   --> … <!-- AUDIO:END   -->     audio elements
```

Everything outside them — CSS, GSAP logic, structure — is hand-authored and
survives a rebuild. Edit inside a marker and your work is gone on the next
build. Change the generator instead.

**Renders are deterministic.** No network fetch, no `Math.random()`, no
`Date.now()` at render time. GSAP is vendored into `vendor/`, the font is
embedded from `assets/fonts/`, and images are files on disk. This is a
HyperFrames requirement and it fails closed in cloud renders.

**Timings are measured, never authored.** `make_voiceover.py` synthesises each
question as three separate clips (stem / option A / "or" + option B) and writes
their real durations into the episode file. `build_episode.py` derives every
on-screen cue from those numbers. That is what makes text appear exactly on the
word that is spoken. Do not hand-write a timing.

**Percentages are never invented silently.** Every block's `reveal` declares a
`source`. `authored` means the owner wrote them; they still have to sum to 100
and sit in the 55–88 band, and `validate_content.py` enforces both. The
most-liked comment across every competitor breakout we mined was viewers mocking
a channel whose numbers did not add up.

**The voice is identity.** `am_adam`, fixed. Swapping synthetic voices between
episodes is noise, not variety.

## Making a video

```bash
python3 scripts/validate_content.py                        # after any content edit
python3 scripts/make_voiceover.py content/episodes/epNNN.json
node    scripts/export_icons.mjs
python3 scripts/build_episode.py content/episodes/epNNN.json
cd videos/wyr-template && npm run check && npm run render
```

Then normalise and land the publishable file (the explicit `-t` matters —
`loudnorm` adds ~100ms of lookahead padding and the last frame has to match the
first for the Shorts loop to close):

```bash
ffmpeg -i renders/<latest>.mp4 -af "loudnorm=I=-14:TP=-1.5:LRA=11" \
  -t <total> -c:v copy -c:a aac -b:a 192k out/wyr-epNNN-<slug>.mp4
```

Check the result against `dna/video-dna.json` → `invariants` before publishing.

Full stage-by-stage detail, including the idea pipeline: `docs/pipeline.md`.
Setup from a clean machine: `README.md`.

## Not in git — you must supply these

| What | Where | Why not committed |
|---|---|---|
| Kokoro weights (338MB) | `~/.cache/kokoro/` | Large, and reproducible from a GitHub release. `make_voiceover.py` prints the exact `curl` commands if missing. |
| Owner's `tick.mp3`, `music.mp3`, `chime.mp3` | `videos/wyr-template/assets/source/` | `music.mp3` is a commercial recording; its licence is the owner's to manage, not this repo's to redistribute. `build_episode.py` re-cuts the beds from it on every build. |
| YouTube API key + OAuth tokens | `~/.config/youtube-skills/` | Credentials. |

`README.md` has the setup commands for all three.

## Open decisions

**Images.** See `dna/video-dna.json` → `images.open_decision`. The current Noto
emoji source was forced by a sandbox that blocked every image CDN and API. It is
good for concrete nouns and bad for people, feelings and actions — "sadness"
renders as a yellow circle — and the channel owner rejected it. The DNA lays out
three options with a recommendation. **This is the first thing to settle**; it
blocks nothing technically, but every video shipped before it is settled carries
artwork the owner does not want.

**Music rights.** `docs/publish-ep001.md` flags this in full. The bed on episode
1 is a commercial track the owner chose knowing a Content ID claim is
near-certain. A 54-second excerpt of it is also present in git history from
commit `4f57acd`; it was removed from the tree in the following commit but
purging it from history needs a rewrite, which is the owner's call and has not
been made.

**Percentages.** `authored` is a stopgap. At 500 subscribers the Community tab
unlocks and `community_poll` becomes available — `comment_poll` works at any
size. Both are already accepted `source` values and are a straight upgrade.
