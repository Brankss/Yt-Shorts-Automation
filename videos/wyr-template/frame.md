# Design spec — Would You Rather template

**`../../dna/video-dna.json` is brand truth.** Where this file and the DNA
disagree, the DNA wins and this file is the thing that is wrong. What follows is
the reasoning behind those values, which JSON cannot carry.

## Concept angle

Two colours, split down the middle, one thing in each. The frame is a ballot,
not a game show: the viewer should be able to answer before they have finished
reading, and there should be nothing else on screen to look at.

## What this replaced, and why

Version 1.x wrapped the two options in rounded cards on a dark background, with
a depleting timer ring, a VS disc, an episode badge, progress dots and animated
fill bars. It was designed from reasoning about the mechanic rather than from
what the winning videos in this niche look like.

They look like this instead: flat saturated red over flat saturated blue, edge
to edge, one cut-out subject per side, heavy outlined lowercase captions, and a
black OR disc on the seam. Nothing else. Every element 1.x added was one more
thing competing with a decision the viewer makes in three seconds.

The copy was wrong in the same way. 1.x wrote whole sentences on both cards, a
median of 26 characters. The reference reads `pain again` and `sadness again`:
10 and 13 characters, sharing a stem that is never shown. That stem is what the
voiceover says, and it is why the voiceover is required rather than optional —
without it, two fragments on two colours are not a question.

## Focal element

The two captions, and only because they sit closest to the seam. Top is always
`#FF1E1E`, bottom always `#0A84FF`, never swapped. The images push outward and
the words meet in the middle, so the eye lands on the comparison first and the
pictures are what it drifts to afterwards.

## Type

Nunito 900, lowercase, white, with a 10px black outline, skewed -8°.

Nunito is the only rounded face among the renderer's 18 pre-bundled families,
and rounded-heavy is what the genre uses. Bundled matters: a non-bundled family
resolves through an implicit build-time fetch from Google Fonts that is
fail-closed in cloud renders — the render errors rather than substituting.

The skew is a static CSS transform on an inner element rather than synthetic
italic, so the angle is exact and identical in every render, and the animated
wrapper is a different element so no tween ever fights it.

The outline is not decoration. White on `#FF1E1E` is 3.85:1 and on `#0A84FF` is
3.65:1 — both clear AA for large text on the flat field alone. The outline is
what keeps the caption readable once a photograph is sitting behind it.

## Images

One cut-out subject per option, no photographic background, no drop shadow,
subject composed in the upper half of its box so the bottom field's image
survives the Shorts UI band.

The image is what stops the scroll; the caption is what makes it a choice. A
block without one still renders — the field is simply flat — and the composition
draws a dashed slot in its place. That slot is meant to be visible and wrong: it
is a missing asset, not a minimal style.

## Motion

Four moves in the whole video. Things arrive, the number slams, the loser
darkens, things leave. There is no on-screen timer: the decide phase is 3.65
seconds in which nothing at all moves, because the voice is asking the question
and a countdown would only compete with it.

Explicitly excluded: blur transitions, 3D rotation, particles, camera shake, and
any progress indicator.

## What the reveal has to do

The reveal is the product. The percentage slams in over the picture at 190px
with a back-ease overshoot, the picture drops to 35% so the number reads, and
the losing field takes a 45% black scrim. Both numbers stay legible — the viewer
on the losing side is the one who comments.
