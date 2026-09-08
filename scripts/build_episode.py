#!/usr/bin/env python3
"""Write an episode into the composition: content, timings, and audio placement.

Block length is no longer fixed. The timer starts when the question stops
speaking, so every block is exactly as long as its own question needs:

    lead-in 0.2s → question (measured) → timer 5.0s → reveal → hold 2.5s → exit 0.35s

That means `data-start` and `data-duration` cannot be authored by hand, and the
audio cannot either. They are computed here from `vo.setup_duration`, which
make_voiceover.py measured off the rendered clips, and written between the
markers in index.html. Everything outside those markers — the split, the type,
the motion — is untouched, which is the whole point of keeping them separate.

Run make_voiceover.py first; without measured durations there is nothing to
derive the timing from.

Usage:
    python3 scripts/build_episode.py content/episodes/ep001.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LEAD_IN = 0.2
TIMER = 5.0
HOLD = 2.5
EXIT = 0.35
END_CARD = 3.5

# From dna/video-dna.json → audio.sfx / audio.voiceover.
VOL_TICK = 0.5
VOL_REVEAL = 0.7
VOL_VO = 1.0


def block_layout(blocks):
    """Absolute times for every block, derived from the measured questions."""
    out, t = [], 0.0
    for b in blocks:
        d = b["vo"].get("setup_duration")
        if d is None:
            sys.exit(
                f"ERROR: {b['dilemma_id']} has no vo.setup_duration.\n"
                "  Run: python3 scripts/make_voiceover.py <episode>"
            )
        speech_end = LEAD_IN + d
        length = speech_end + TIMER + HOLD + EXIT
        out.append({
            "start": round(t, 3),
            "length": round(length, 3),
            "vo_at": round(t + LEAD_IN, 3),
            "tick_at": round(t + speech_end, 3),          # the instant the question stops
            "reveal_at": round(t + speech_end + TIMER, 3),
        })
        t += length
    return out, round(t, 3)


def fill(html, marker, body):
    start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(html):
        sys.exit(f"ERROR: markers for {marker} not found in index.html")
    return pattern.sub(start + "\n" + body + "\n      " + end, html)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("episode")
    ap.add_argument("--project", default="videos/wyr-template")
    args = ap.parse_args()

    ep = json.loads(Path(args.episode).read_text())
    project = ROOT / args.project
    index = project / "index.html"
    html = index.read_text()

    layout, blocks_total = block_layout(ep["blocks"])
    total = round(blocks_total + END_CARD, 3)
    tag = f"ep{ep['episode']:03d}"

    # 1. Content island — what the composition reads at run time.
    island = {
        "episode": ep["episode"],
        "blocks": [
            {**{k: b[k] for k in ("dilemma_id", "stem", "option_a", "option_b") if k in b},
             **{k: b[k] for k in ("image_a", "image_b") if k in b},
             "reveal": b["reveal"],
             "timing": layout[i]}
            for i, b in enumerate(ep["blocks"])
        ],
        "end_card": ep["end_card"],
        "total": total,
        "end_card_at": blocks_total,
    }
    body = "\n".join("      " + l for l in json.dumps(island, indent=2).splitlines())
    html = fill(html, "EPISODE", body)

    # 2. Block sections. One clip each, at its computed place on the timeline.
    lines = [
        f'      <section id="b{i + 1}" class="clip" data-start="{L["start"]}" data-duration="{L["length"]}"></section>'
        for i, L in enumerate(layout)
    ]
    lines.append(f'      <section id="or-holder" class="clip" data-start="0" data-duration="{blocks_total}">')
    lines.append('        <div id="or">OR</div>')
    lines.append('      </section>')
    lines.append(f'      <section id="end" class="clip" data-start="{blocks_total}" data-duration="{END_CARD}">')
    lines.append(f'        <div id="end-a">{ep["end_card"]["cta"]}</div>')
    lines.append(f'        <div id="end-b">{ep["end_card"].get("next_teaser", "")}</div>')
    lines.append('      </section>')
    html = fill(html, "BLOCKS", "\n".join(lines))

    # 3. Audio, at the composition root with absolute times. A plain timed
    #    wrapper does not rebase media, so a scene-local start would be read as
    #    root time anyway and only look like it meant something else.
    audio = []
    for i, L in enumerate(layout, start=1):
        audio.append(f'      <audio id="vo-b{i}" src="assets/vo/{tag}-b{i}-setup.wav" '
                     f'data-start="{L["vo_at"]}" data-volume="{VOL_VO}"></audio>')
        audio.append(f'      <audio id="sfx-tick-{i}" src="assets/sfx-tick.wav" '
                     f'data-start="{L["tick_at"]}" data-volume="{VOL_TICK}"></audio>')
        audio.append(f'      <audio id="sfx-reveal-{i}" src="assets/sfx-reveal.wav" '
                     f'data-start="{L["reveal_at"]}" data-volume="{VOL_REVEAL}"></audio>')
    html = fill(html, "AUDIO", "\n".join(audio))

    # 4. Root duration.
    html = re.sub(r'(id="root"[^>]*?data-duration=")[\d.]+(")',
                  lambda m: m.group(1) + str(total) + m.group(2), html, flags=re.S)

    index.write_text(html)

    print(f"{tag} → {args.project}/index.html")
    for i, L in enumerate(layout, start=1):
        print(f"  b{i}  {L['start']:6.2f}s  question→{L['tick_at']:6.2f}s  "
              f"timer→{L['reveal_at']:6.2f}s  reveal  ({L['length']:.2f}s)")
    print(f"  end card at {blocks_total:.2f}s   total {total:.2f}s")
    if not 41 <= total <= 60:
        print("  WARNING: outside the 41-60s band this niche rewards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
