# Yt-Shorts-Automation

Automated production line for *Would You Rather* YouTube Shorts on the channel
**Branks** (`@branks.s`).

One episode is five dilemmas on a split red/blue screen: a spoken question, text
and image appearing on the word that names them, a 3.5-second timer, then a
silent percentage reveal. Roughly 55 seconds, vertical, 1080×1920.

The pipeline is scripted end to end — content lives in JSON, the composition is
generated from it, and the video is rendered by HyperFrames. Nothing is
hand-placed.

- **Building or changing a video?** Read `CLAUDE.md`, then `dna/video-dna.json`.
- **Why this format?** `docs/strategy.md`.
- **What each stage does?** `docs/pipeline.md`.

---

## Setup from a clean machine

Tested on Python 3.11 and Node 22. Older Node will not run the HyperFrames CLI.

### 1. Clone and install

```bash
git clone https://github.com/Brankss/Yt-Shorts-Automation.git
cd Yt-Shorts-Automation

pip3 install jsonschema kokoro-onnx soundfile
pip3 install google-api-python-client google-auth-oauthlib   # only for the youtube-* skills

cd videos/wyr-template && npm install && cd ../..
```

### 2. ffmpeg and ffprobe

Both must be on `PATH`. Use the system package manager:

```bash
brew install ffmpeg            # macOS
sudo apt install ffmpeg        # Debian/Ubuntu
```

If you cannot install system packages, `npm install` above already pulled
`ffmpeg-static` and `ffprobe-static`; symlink their binaries onto `PATH`:

```bash
cd videos/wyr-template
sudo ln -sf "$(node -p "require('ffmpeg-static')")"                    /usr/local/bin/ffmpeg
sudo ln -sf "$(node -p "require('ffprobe-static').path")"              /usr/local/bin/ffprobe
```

### 3. Voice model (Kokoro, ~338MB)

Offline neural TTS. Downloaded once, lives outside the repo, touches no network
when generating.

```bash
mkdir -p ~/.cache/kokoro && cd ~/.cache/kokoro
curl -sSL -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -sSL -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

`make_voiceover.py` prints these exact commands if the weights are missing.

### 4. Owner-supplied audio

Three files the channel owner provides, not in git:

```
videos/wyr-template/assets/source/
  tick.mp3     the timer tick — its pattern is always taken from the file's start
  chime.mp3    the reveal chime
  music.mp3    the bed. Cut from 57.0s (dna → audio.music.cue_point)
```

`build_episode.py` re-cuts the episode-length beds from these on every build, so
they cannot be replaced by fixed assets. It exits with a clear error naming any
that are missing.

> `music.mp3` is a commercial recording. It is deliberately not in git, and the
> licence is the channel owner's to manage. See the rights note in
> `docs/publish-ep001.md` before publishing.

### 5. YouTube credentials (only for analytics and metadata skills)

Not needed to render a video. The `.agents/skills/youtube-*` skills each
document their own setup; material is stored in `~/.config/youtube-skills/`,
outside the repo. For the write scope:

```bash
python3 scripts/auth_write_manual.py
```

### 6. Verify

```bash
python3 scripts/validate_content.py
```

Expected: `OK — 48 dilemmas, 1 episode file(s) conform to the schemas and to DNA 3.4.0`

---

## Make a video

### From an existing episode file

Episode 1 is already written, voiced and rendered. To rebuild it:

```bash
python3 scripts/build_episode.py content/episodes/ep001.json
cd videos/wyr-template && npm run check && npm run render
```

### From scratch

```bash
# 1. Write the episode file: 5 banked dilemmas on the difficulty ramp,
#    percentages set. Validate as you go.
python3 scripts/validate_content.py content/episodes/ep002.json

# 2. Voice it. Writes measured clip durations back into the episode file.
python3 scripts/make_voiceover.py content/episodes/ep002.json

# 3. Resolve the artwork the bank references into SVGs on disk.
node scripts/export_icons.mjs

# 4. Generate the composition from the episode file.
python3 scripts/build_episode.py content/episodes/ep002.json

# 5. Render.
cd videos/wyr-template && npm run check && npm run render
```

### Land the publishable file

`loudnorm` adds about 100ms of lookahead padding, and the last frame has to match
the first for the Shorts loop to close — so pass the episode total explicitly
(`build_episode.py` prints it):

```bash
ffmpeg -i videos/wyr-template/renders/<latest>.mp4 \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" -t <total> \
  -c:v copy -c:a aac -b:a 192k out/wyr-ep002-<slug>.mp4
```

Check the result against `dna/video-dna.json` → `invariants` before publishing.
Title, description, tags and settings for episode 1 are in
`docs/publish-ep001.md`.

---

## Before you ship anything

**The artwork is unresolved.** The current Noto emoji source was forced by a
sandbox that blocked every image CDN and image API. It works for concrete nouns
and fails for people, feelings and actions — "sadness" renders as a yellow
circle — and the channel owner rejected it on sight.
`dna/video-dna.json` → `images.open_decision` sets out three options with a
recommendation (generate them, and freeze the style prompt into the DNA so all
96 fragments match). Settle this first.

**Episode 1's music will be claimed.** Read the rights note in
`docs/publish-ep001.md`.
