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
TIMER = 3.5
HOLD = 2.5
EXIT = 0.35
CHIME = 2.769      # the owner's chime, full length — it closes the video
END_TAIL = 1.0     # the tick keeps running this long after the closing line
MUSIC_FROM = 57.0  # the owner's cue point in the source track

# From dna/video-dna.json → audio.sfx / audio.voiceover.
VOL_TICK = 0.5
VOL_REVEAL = 0.7
VOL_VO = 1.0
VOL_MUSIC = 0.16   # a bed, not a layer: the questions have to stay in front


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
        tick_at = t + speech_end
        out.append({
            "start": round(t, 3),
            "length": round(length, 3),
            "vo_at": round(t + LEAD_IN, 3),
            "tick_at": round(tick_at, 3),                 # the instant the question stops
            "reveal_at": round(tick_at + TIMER, 3),
            # One pulse of the seam per second of the tick, so the countdown is
            # visible without a countdown being drawn.
            "pulses": [round(tick_at + n, 3) for n in range(int(TIMER) + 1) if n <= TIMER],
        })
        t += length
    return out, round(t, 3)


def fill(html, marker, body):
    start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(html):
        sys.exit(f"ERROR: markers for {marker} not found in index.html")
    return pattern.sub(start + "\n" + body + "\n      " + end, html)


def run(cmd):
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ERROR: " + " ".join(cmd[:3]) + " ...\n" + r.stderr.strip()[:600])


def derive_beds(project, tag, end_tick_len, total):
    """Cut the owner's source audio down to what this episode needs.

    Both are episode-length, so neither can be a fixed asset. The tick is always
    taken from the start of the source and cut at the tail, so its pattern
    always begins where the owner's file begins. The music starts at the cue
    point they chose and runs the length of the video.
    """
    src = project / "assets/source"
    out = project / "assets"
    tick_src, music_src = src / "tick.mp3", src / "music.mp3"
    missing = [p.name for p in (tick_src, music_src) if not p.exists()]
    if missing:
        sys.exit(f"ERROR: missing owner-supplied source audio in {src}: {', '.join(missing)}")

    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(tick_src),
         "-t", f"{end_tick_len:.3f}", "-af", f"afade=t=out:st={end_tick_len - 0.1:.3f}:d=0.1",
         "-ar", "48000", "-ac", "1", str(out / "sfx-tick-end.wav")])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{MUSIC_FROM}",
         "-i", str(music_src), "-t", f"{total:.3f}",
         "-af", f"afade=t=out:st={total - 1.5:.3f}:d=1.5", "-ar", "48000", "-ac", "2",
         str(out / f"music-{tag}.wav")])


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
    tag = f"ep{ep['episode']:03d}"

    ec = ep["end_card"]
    ec_vo = ec.get("vo_duration")
    if ec_vo is None:
        sys.exit("ERROR: end_card has no vo_duration.\n"
                 "  Run: python3 scripts/make_voiceover.py <episode>")
    # The closing line, then a second of tick alone, then the chime rings out.
    end_tick_len = round(ec_vo + END_TAIL, 3)
    chime_at = round(blocks_total + end_tick_len, 3)
    total = round(chime_at + CHIME, 3)
    end_len = round(total - blocks_total, 3)
    end_pulses = [round(blocks_total + n, 3) for n in range(int(end_tick_len) + 1)]

    derive_beds(project, tag, end_tick_len, total)

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
        "end_card": {"cta": ec["cta"], "at": blocks_total, "length": end_len, "pulses": end_pulses},
        "total": total,
    }
    body = "\n".join("      " + l for l in json.dumps(island, indent=2).splitlines())
    html = fill(html, "EPISODE", body)

    # 2. Block sections. One clip each, at its computed place on the timeline.
    lines = [
        f'      <section id="b{i + 1}" class="clip" data-start="{L["start"]}" data-duration="{L["length"]}"></section>'
        for i, L in enumerate(layout)
    ]
    # The seam runs the whole video because it pulses through the end card too.
    # The OR disc stops with the last block: the end card is one word, alone.
    lines.append(f'      <section id="seam-holder" class="clip" data-start="0" data-duration="{total}">')
    lines.append('        <div id="seam-glow"></div>')
    lines.append('        <div id="seam"></div>')
    lines.append('      </section>')
    lines.append(f'      <section id="or-holder" class="clip" data-start="0" data-duration="{blocks_total}">')
    lines.append('        <div id="or">OR</div>')
    lines.append('      </section>')
    lines.append(f'      <section id="end" class="clip" data-start="{blocks_total}" data-duration="{end_len}">')
    lines.append(f'        <div id="end-a">{ec["cta"]}</div>')
    lines.append('      </section>')
    html = fill(html, "BLOCKS", "\n".join(lines))

    # 3. Audio, at the composition root with absolute times. A plain timed
    #    wrapper does not rebase media, so a scene-local start would be read as
    #    root time anyway and only look like it meant something else.
    audio = [f'      <audio id="music" src="assets/music-{tag}.wav" '
             f'data-start="0" data-volume="{VOL_MUSIC}"></audio>']
    for i, L in enumerate(layout, start=1):
        audio.append(f'      <audio id="vo-b{i}" src="assets/vo/{tag}-b{i}-setup.wav" '
                     f'data-start="{L["vo_at"]}" data-volume="{VOL_VO}"></audio>')
        audio.append(f'      <audio id="sfx-tick-{i}" src="assets/sfx-tick.wav" '
                     f'data-start="{L["tick_at"]}" data-volume="{VOL_TICK}"></audio>')
        audio.append(f'      <audio id="sfx-reveal-{i}" src="assets/sfx-reveal.wav" '
                     f'data-start="{L["reveal_at"]}" data-volume="{VOL_REVEAL}"></audio>')
    audio.append(f'      <audio id="vo-end" src="assets/vo/{tag}-end.wav" '
                 f'data-start="{blocks_total}" data-volume="{VOL_VO}"></audio>')
    audio.append(f'      <audio id="sfx-tick-end" src="assets/sfx-tick-end.wav" '
                 f'data-start="{blocks_total}" data-volume="{VOL_TICK}"></audio>')
    audio.append(f'      <audio id="sfx-reveal-end" src="assets/sfx-reveal.wav" '
                 f'data-start="{chime_at}" data-volume="{VOL_REVEAL}"></audio>')
    html = fill(html, "AUDIO", "\n".join(audio))

    # 4. Root duration.
    html = re.sub(r'(id="root"[^>]*?data-duration=")[\d.]+(")',
                  lambda m: m.group(1) + str(total) + m.group(2), html, flags=re.S)

    index.write_text(html)

    print(f"{tag} → {args.project}/index.html")
    for i, L in enumerate(layout, start=1):
        print(f"  b{i}  {L['start']:6.2f}s  question→{L['tick_at']:6.2f}s  "
              f"timer→{L['reveal_at']:6.2f}s  reveal  ({L['length']:.2f}s)")
    print(f"  end  {blocks_total:6.2f}s  line→{blocks_total + ec_vo:6.2f}s  "
          f"tick→{chime_at:6.2f}s  chime  ({end_len:.2f}s)")
    print(f"  total {total:.2f}s   music from {MUSIC_FROM:.0f}s of source")
    if not 41 <= total <= 60:
        print("  WARNING: outside the 41-60s band this niche rewards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
