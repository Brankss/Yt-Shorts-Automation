#!/usr/bin/env python3
"""Generate the voiceover for an episode with Kokoro, offline.

Why this engine. Every hosted TTS is unreachable from these sessions — HeyGen,
Microsoft's Edge voices, Google Translate and ElevenLabs all return 403 through
the egress proxy. GitHub release assets do get through, which is where Kokoro
publishes its weights, so this is the one free route that works here. The model
lives in ~/.cache/kokoro (338MB, outside the repo, never committed); generation
itself touches no network.

The voiceover is not decoration. The screen shows two fragments and never the
stem that joins them, so the setup line is the only place the dilemma exists as
a question.

Timing is checked, not assumed. The DNA lands the setup at +0.2s and the
reaction at +4.4s inside an 8.5s block, with the reveal at +4.0s, so a setup
longer than 3.8s would still be talking over its own answer. Anything that does
not fit is reported and the script exits non-zero.

Usage:
    python3 scripts/make_voiceover.py content/episodes/ep001.json
    python3 scripts/make_voiceover.py content/episodes/ep001.json --voice am_michael
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = Path.home() / ".cache" / "kokoro"
MODEL = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES = MODEL_DIR / "voices-v1.0.bin"

# From dna/video-dna.json → audio.voiceover and timeline.block_phases.
SETUP_AT = 0.2
REACTION_AT = 4.4
REVEAL_AT = 4.0
BLOCK = 8.5
SETUP_BUDGET = REVEAL_AT - SETUP_AT      # 3.8s — must be done before the answer
REACTION_BUDGET = BLOCK - REACTION_AT    # 4.1s — must be done before the block ends


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("episode", help="path to content/episodes/epNNN.json")
    ap.add_argument("--voice", default="af_heart", help="Kokoro voice id")
    ap.add_argument("--speed", type=float, default=1.05, help="DNA audio.voiceover.rate")
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

    ep = json.loads(Path(args.episode).read_text())
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    kokoro = Kokoro(str(MODEL), str(VOICES))
    tag = f"ep{ep['episode']:03d}"
    overruns = []

    print(f"{tag}  voice={args.voice}  speed={args.speed}")
    for i, block in enumerate(ep["blocks"], start=1):
        for line, budget, at in (
            ("setup", SETUP_BUDGET, SETUP_AT),
            ("reaction", REACTION_BUDGET, REACTION_AT),
        ):
            text = block["vo"][line]
            samples, rate = kokoro.create(text, voice=args.voice, speed=args.speed, lang="en-us")
            dur = len(samples) / rate
            name = f"{tag}-b{i}-{line}.wav"
            sf.write(out / name, samples, rate)

            flag = "  OK"
            if dur > budget:
                flag = f"  OVER by {dur - budget:.2f}s"
                overruns.append((name, dur, budget, text))
            print(f"  b{i} {line:<8} {dur:5.2f}s / {budget:.1f}s{flag}  {name}")

    if overruns:
        print("\nThese lines do not fit their slot. Shorten the copy — do not")
        print("speed the voice up, the rate is fixed by the DNA:")
        for name, dur, budget, text in overruns:
            print(f"  {name}: {dur:.2f}s > {budget:.1f}s — {text!r}")
        return 1

    print(f"\n{2 * len(ep['blocks'])} clips written to {Path(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
