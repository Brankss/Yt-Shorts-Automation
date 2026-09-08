#!/usr/bin/env python3
"""Validate the dilemma bank and any episode files against the schemas and the DNA.

The JSON schemas cover shape. They cannot cover the rules that live in
dna/video-dna.json -- character budgets that come from the type size, forbidden
words, the difficulty ramp, percentages summing to 100 -- because those are
properties of the design, not of the data model. This checks both, so a dilemma
that would overflow its card or a block that invented its numbers fails here
rather than at render time.

Usage:
    python3 scripts/validate_content.py                 # bank + every episode
    python3 scripts/validate_content.py content/episodes/ep001.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DNA = json.loads((ROOT / "dna/video-dna.json").read_text())
RULES = DNA["copy_rules"]
RAMP = RULES["difficulty_ramp"]

try:
    import jsonschema
except ImportError:
    sys.exit("ERROR: pip3 install jsonschema")


def load_schema(name):
    return json.loads((ROOT / "content/schemas" / name).read_text())


def check_option(text, where, errors):
    """The card is 850px wide with 76px Anton over at most two lines; 42 characters
    is what fits. Longer text does not wrap, it overflows."""
    if len(text) > RULES["option_max_chars"]:
        errors.append(f"{where}: {len(text)} chars, max {RULES['option_max_chars']} — {text!r}")
    if text.rstrip().endswith((".", "!", "?")):
        errors.append(f"{where}: option ends with punctuation — {text!r}")
    low = f" {text.lower()} "
    for bad in RULES["forbidden_in_options"]:
        if f" {bad} " in low or (bad in ("?",) and bad in text):
            errors.append(f"{where}: contains forbidden {bad!r} — {text!r}")


def validate_bank(errors):
    path = ROOT / "content/dilemmas.json"
    if not path.exists():
        return 0
    schema = load_schema("dilemma.schema.json")
    bank = json.loads(path.read_text())
    seen = set()
    for d in bank["dilemmas"]:
        where = f"dilemmas.json/{d.get('id', '?')}"
        try:
            jsonschema.validate(d, schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{where}: {exc.message}")
            continue
        if d["id"] in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(d["id"])
        check_option(d["option_a"], where + ".option_a", errors)
        check_option(d["option_b"], where + ".option_b", errors)
        if d["option_a"].strip().lower() == d["option_b"].strip().lower():
            errors.append(f"{where}: both options are the same")
    return len(bank["dilemmas"])


def validate_episode(path, errors):
    schema = load_schema("episode.schema.json")
    ep = json.loads(Path(path).read_text())
    where0 = Path(path).name
    try:
        jsonschema.validate(ep, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"{where0}: {exc.message}")
        return

    for i, b in enumerate(ep["blocks"]):
        where = f"{where0}/block{i + 1}"
        check_option(b["option_a"], where + ".option_a", errors)
        check_option(b["option_b"], where + ".option_b", errors)

        r = b["reveal"]
        if r["source"] == "community_poll":
            total = r["a"] + r["b"]
            if total != DNA["reveal_mechanic"]["percentages_must_sum_to"]:
                # This is the failure viewers actually catch: the most-liked
                # comment across every breakout we mined is people mocking it.
                errors.append(f"{where}: percentages sum to {total}, not 100")
            lo, hi = DNA["reveal_mechanic"]["target_split_range"]
            top = max(r["a"], r["b"])
            if not (lo <= top <= hi):
                errors.append(
                    f"{where}: split {r['a']}/{r['b']} outside the {lo}-{hi} band "
                    "(a coin flip provokes nothing, a blowout is not a dilemma)"
                )

        vo = b["vo"]
        n1 = len(vo["setup"].split())
        n2 = len(vo["reaction"].split())
        if n1 > DNA["audio"]["voiceover"]["max_words_line_1"]:
            errors.append(f"{where}: vo.setup {n1} words, max {DNA['audio']['voiceover']['max_words_line_1']}")
        if n2 > DNA["audio"]["voiceover"]["max_words_line_2"]:
            errors.append(f"{where}: vo.reaction {n2} words, max {DNA['audio']['voiceover']['max_words_line_2']}")

    ids = [b["dilemma_id"] for b in ep["blocks"]]
    if len(set(ids)) != len(ids):
        errors.append(f"{where0}: the same dilemma appears twice")

    if not any(b["reveal"]["source"] == "community_poll" for b in ep["blocks"]) and ep["episode"] > 1:
        errors.append(f"{where0}: no real poll numbers, but this is not episode 1")


def main():
    errors = []
    targets = sys.argv[1:]

    if targets:
        for t in targets:
            validate_episode(t, errors)
        checked = f"{len(targets)} episode file(s)"
    else:
        n = validate_bank(errors)
        eps = sorted((ROOT / "content/episodes").glob("*.json")) if (ROOT / "content/episodes").exists() else []
        for e in eps:
            validate_episode(e, errors)
        checked = f"{n} dilemmas, {len(eps)} episode file(s)"

    if errors:
        print(f"FAIL — {len(errors)} problem(s) in {checked}\n")
        for e in errors:
            print("  " + e)
        return 1
    print(f"OK — {checked} conform to the schemas and to DNA {DNA['meta']['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
