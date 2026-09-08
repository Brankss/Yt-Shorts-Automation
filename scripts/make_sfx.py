#!/usr/bin/env python3
"""Synthesise the three sound effects the DNA calls for, as WAV files.

There is no ffmpeg and no reachable sound library in this environment, and the
egress policy blocks the asset providers, so the effects are generated from the
standard library instead. That turns out to be the better answer regardless:
three short synthetic sounds are deterministic, weigh a few hundred KB, carry no
licence, and are reproducible from this file rather than fetched and forgotten.

    tick    a soft click, four of them, one per second of the decide phase.
            The DNA removed the on-screen timer because the reference videos
            have none; the urgency it used to carry moves to the ear, where it
            does not compete with reading two options.
    reveal  the chime under the percentages. A struck bell: three partials on a
            C major triad, fast attack, long decay.
    swoosh  the push between blocks.

Levels are left near full scale here and attenuated in the composition through
data-volume, so the DNA's gain figures in dB map straight onto the markup.

Usage:
    python3 scripts/make_sfx.py [--out videos/wyr-template/assets]
"""

import argparse
import array
import math
import random
import wave
from pathlib import Path

RATE = 48_000
ROOT = Path(__file__).resolve().parent.parent


def write_wav(path: Path, samples: list[float]) -> None:
    """16-bit mono, with a short fade at both ends so nothing clicks."""
    n = len(samples)
    fade = min(64, n // 8)
    buf = array.array("h")
    for i, s in enumerate(samples):
        if i < fade:
            s *= i / fade
        elif i > n - fade:
            s *= (n - i) / fade
        buf.append(int(max(-1.0, min(1.0, s)) * 32000))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(buf.tobytes())


def lowpass(samples: list[float], cutoff_hz: float) -> list[float]:
    """One-pole filter. Crude, but noise only needs its edge taken off."""
    a = math.exp(-2 * math.pi * cutoff_hz / RATE)
    out, prev = [], 0.0
    for s in samples:
        prev = (1 - a) * s + a * prev
        out.append(prev)
    return out


def tick(rng: random.Random) -> list[float]:
    """A 25ms click: a noise transient over a short high tone."""
    n = int(0.025 * RATE)
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 5000)
    out = []
    for i in range(n):
        env = math.exp(-i / (0.006 * RATE))
        tone = math.sin(2 * math.pi * 3000 * i / RATE)
        out.append((0.55 * noise[i] + 0.45 * tone) * env)
    return out


def build_tick_track(rng: random.Random) -> list[float]:
    """Four ticks, one per second, covering the decide phase."""
    total = int(3.6 * RATE)
    out = [0.0] * total
    click = tick(rng)
    for beat in range(4):
        at = int(beat * 1.0 * RATE)
        for i, s in enumerate(click):
            if at + i < total:
                out[at + i] += s
    return out


def build_reveal() -> list[float]:
    """A struck bell on C6-G6-C7. The number landing is the payoff, so this is
    the brightest sound in the video and the only one that rings."""
    dur = 0.7
    n = int(dur * RATE)
    partials = [(1046.50, 1.00, 0.20), (1568.00, 0.55, 0.16), (2093.00, 0.32, 0.11)]
    out = []
    for i in range(n):
        t = i / RATE
        attack = min(1.0, t / 0.004)
        s = 0.0
        for freq, amp, tau in partials:
            s += amp * math.sin(2 * math.pi * freq * t) * math.exp(-t / tau)
        out.append(0.55 * s * attack)
    return out


def build_swoosh(rng: random.Random) -> list[float]:
    """Filtered noise falling in pitch: the push out of a block."""
    dur = 0.3
    n = int(dur * RATE)
    noise = [rng.uniform(-1, 1) for _ in range(n)]
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        env = math.sin(math.pi * min(1.0, t / dur)) ** 1.5
        freq = 900 - 700 * (t / dur)
        phase += 2 * math.pi * freq / RATE
        out.append((0.5 * noise[i] + 0.5 * math.sin(phase)) * env * 0.7)
    return lowpass(out, 4000)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="videos/wyr-template/assets")
    args = ap.parse_args()

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    # Fixed seed: the noise has to be the same in every render.
    rng = random.Random(7)

    files = {
        "sfx-tick.wav": build_tick_track(rng),
        "sfx-reveal.wav": build_reveal(),
        "sfx-swoosh.wav": build_swoosh(rng),
    }
    for name, samples in files.items():
        write_wav(out / name, samples)
        print(f"  {name:<16} {len(samples) / RATE:.2f}s  {(out / name).stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
