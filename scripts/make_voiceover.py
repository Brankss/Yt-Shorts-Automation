#!/usr/bin/env python3
"""Generate an episode's voiceover with Kokoro, offline, and time the video to it.

Why this engine. Every hosted TTS is unreachable from these sessions — HeyGen,
Microsoft's Edge voices, Google Translate and ElevenLabs all return 403 through
the egress proxy. GitHub release assets do get through, which is where Kokoro
publishes its weights, so this is the one free route that works here. The model
lives in ~/.cache/kokoro (338MB, outside the repo, never committed); generation
itself touches no network.

The voiceover is not decoration. The screen shows two fragments and never the
stem that joins them, so the setup line is the only place the dilemma exists as
a question.

One line per block, and only the setup. The reveal is silent: the percentages
land with the chime and nothing talks over them or explains them away.

The measured length of each clip is written back into the episode file as
`vo.setup_duration`, because the video's timing is derived from it rather than
fixed in advance — the timer starts when the question stops, never before, so a
block is exactly as long as its own question needs.

Usage:
    python3 scripts/make_voiceover.py content/episodes/ep001.json
    python3 scripts/make_voiceover.py content/episodes/ep001.json --voice bm_george
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = Path.home() / ".cache" / "kokoro"
MODEL = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES = MODEL_DIR / "voices-v1.0.bin"

# From dna/video-dna.json → timeline. Everything after the question is fixed;
# only the question's own length varies.
LEAD_IN = 0.2      # silence before the voice starts
TIMER = 3.5        # the supplied tick track, exactly
HOLD = 2.5         # numbers on screen, no voice
EXIT = 0.35
CHIME = 2.769      # the supplied chime, full length — it closes the video


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("episode", help="path to content/episodes/epNNN.json")
    ap.add_argument("--voice", default="am_adam", help="Kokoro voice id")
    ap.add_argument("--speed", type=float, default=1.0, help="DNA audio.voiceover.rate")
    ap.add_argument("--out", default="videos/wyr-template/assets/vo")
    args = ap.parse_args()

    if not MODEL.exists() or not VOICES.exists():
        sys.exit(
            f"ERROR: Kokoro weights missing from {MODEL_DIR}.\n"
            "  mkdir -p ~/.cache/kokoro && cd ~/.cache/kokoro\n"
            "  curl -sSL -O https://github.com/thewh1teagle/kokoro-onnx/releases/"
            "download/model-files-v1.0/kokoro-v1.0.onnx\n"
            "  curl -sSL -O https://github.com/thewh1teagle/kokoro-onnx/releases/"
            "download/model-files-v1.0/voices-v1.0.bin"
        )

    import soundfile as sf
    from kokoro_onnx import Kokoro

    ep_path = Path(args.episode)
    ep = json.loads(ep_path.read_text())
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    kokoro = Kokoro(str(MODEL), str(VOICES))
    if args.voice not in kokoro.get_voices():
        sys.exit(f"ERROR: unknown voice {args.voice!r}. Available: {sorted(kokoro.get_voices())}")

    tag = f"ep{ep['episode']:03d}"
    print(f"{tag}  voice={args.voice}  speed={args.speed}")

    def say(text, name):
        samples, rate = kokoro.create(text, voice=args.voice, speed=args.speed, lang="en-us")
        sf.write(out / name, samples, rate)
        return len(samples) / rate

    total = 0.0
    for i, block in enumerate(ep["blocks"], start=1):
        name = f"{tag}-b{i}-setup.wav"
        dur = say(block["vo"]["setup"], name)

        block["vo"]["setup_duration"] = round(dur, 3)
        block["vo"].pop("reaction", None)  # the reveal is silent

        block_len = LEAD_IN + dur + TIMER + HOLD + EXIT
        total += block_len
        print(f"  b{i}  question {dur:5.2f}s  →  block {block_len:5.2f}s   {name}")

    # The end card speaks too. The tick runs one second past the line, then the
    # chime closes the video, so the tail is measured rather than assumed.
    ec = ep["end_card"]
    ec_dur = say(ec["vo"], f"{tag}-end.wav")
    ec["vo_duration"] = round(ec_dur, 3)
    end_card = ec_dur + 1.0 + CHIME
    print(f"  end  line     {ec_dur:5.2f}s  →  card  {end_card:5.2f}s   {tag}-end.wav")

    ep_path.write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n")

    print(f"\n  {len(ep['blocks'])} blocks {total:.2f}s + end card {end_card:.2f}s = {total + end_card:.2f}s")
    if not 41 <= total + end_card <= 60:
        # 41-60s is the only duration band that performs in this niche:
        # median 26,239 views against 751 for 16-25s and 8,834 above 60s.
        print("  WARNING: outside the 41-60s band this niche rewards.")
    print(f"  durations written back to {ep_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
