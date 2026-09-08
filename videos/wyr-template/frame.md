# Design spec — Would You Rather template

**`../../dna/video-dna.json` is brand truth.** Where this file and the DNA
disagree, the DNA wins and this file is the thing that is wrong. What follows is
the reasoning behind those values, which JSON cannot carry.

## Concept angle

Two doors, one clock, and a number that tells you which side of the room you are
standing on. The frame is a voting booth, not a game show: dark, quiet, and
built so that the only bright thing on screen is the choice you have not made yet.

## Focal element

The two option cards, stacked. Top is always `#FF2D6F`, bottom always `#00D1FF`
— never swapped, never re-coloured per episode. The viewer learns the geometry
in one video and reads every later one without decoding it. Vertical stacking
rather than side-by-side because a phone held in one hand reads top-to-bottom,
and because 42 characters of condensed type needs the full 850px width.

## Edge anchors

Episode badge top-left, progress dots bottom-centre. Both sit inside the Shorts
safe bands, and both exist for the same reason: they tell the viewer this is
episode 7 of something, and dilemma 3 of five. A viewer who knows how much is
left stays for the rest.

## Supporting detail

The timer ring between the cards, in `#FFD400` — the only warm colour in the
frame, used once, on the one element that means "decide now". Its 3.5s sweep is
the whole tension of the format. When it empties, the answer arrives.

## Background

Near-black `#0B0B12` with a single radial lift toward `#1A1030` behind the cards.
Flat black would make the cards float; the lift gives them a room to sit in
without introducing a texture that competes with type.

## Typography

- **Oswald 700** for options at 76px uppercase. Condensed, so 42 characters fit
  two lines inside the card without shrinking.
- **Archivo Black** for percentages at 120px. The number is the payoff and gets
  the heaviest face in the system.

Both are pre-bundled by the renderer and embed as local data URIs. The DNA
originally specified Anton, which is not bundled: it resolves through an implicit
build-time fetch from Google Fonts that is **fail-closed in cloud renders** — the
render errors rather than substituting. DNA 1.1.0 records that change and why.

Archivo Black ships weight 400 only. Asking for 700 or 900 produces a synthetic
weight, not a real cut.

## Motion

Motion is functional. Cards enter from opposite edges because they are opposites.
The ring depletes because time is running out. The bar fills and the number
counts because the result is being measured in front of you. Nothing else moves.

Explicitly excluded: blur transitions, 3D rotation, particles, camera shake.
Each of them would compete with a decision the viewer is trying to make in
three and a half seconds.

## What the reveal has to do

The reveal is the product. It carries the strongest accent in the block: the
winning card goes to full colour and pops 3%, the losing card desaturates and
settles back 4%. If a viewer looks away for one second, this is the second they
must not miss.
