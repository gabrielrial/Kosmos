# Kosmos — things to build

Ideas parked with enough context to pick up later. Measurements come from the
sample images in `img/`, taken with `tools/survey.py` and ad-hoc scripts.

---

## Expression: signals the image can give us

Measured across five sample images. The ratio is max ÷ min across the set —
how much room a mapping would have to work with. A signal that barely varies
between photographs cannot express anything.

| signal | range | ratio | extracted? | verdict |
|---|---|---|---|---|
| stars per megapixel | 26 – 2,690 | **102×** | yes | strongest signal available |
| empty fraction of frame | 0% – 50% | **500×** | no | where the picture is silent |
| vertical star gradient | 0.004 – 0.28 | **68×** | no | is the field top- or bottom-heavy |
| star flux dynamic range | 6.0 – 35.2 | 5.9× | partly | are there dominant stars, or are they all alike |
| nebula elongation | 0.69 – 3.43 | 4.9× | yes | shape of the diffuse regions |
| nearest-neighbour distance | 6.1 – 22.4 px | 3.7× | no | how tightly stars cluster |
| global contrast (p95–p5) | 0.37 – 0.79 | 2.1× | no | dark sky vs bright field |
| mean star saturation | 0.18 – 0.41 | 2.3× | yes | how colourful the stars are |
| nebula contrast | 26.5 – 64.8 | 2.4× | yes | how strongly nebulae stand out |
| nebula saturation | 0.29 – 0.47 | 1.6× | yes | too flat to map |
| Clark–Evans clustering | 0.70 – 1.02 | 1.5× | no | **contaminated**: `minimum_distance` suppression imposes regularity, so it measures the detector, not the sky |
| nebula coverage | 30% – 36% | 1.2× | yes | too flat to map |

### What to do with them

- **Empty fraction → silence.** The most direct answer to "more stars, fewer
  silences". A frame with large dark regions should have real rests; an even
  field should be continuous. Nothing uses this yet.
- **Vertical gradient → shape over time.** Since the playhead sweeps top to
  bottom, a top-heavy field naturally front-loads the piece. Could drive a
  slow swell instead of leaving it to chance.
- **Flux dynamic range → velocity spread.** An image with a few dominant
  stars should have sharp accents; one where every star is alike should be
  flat. Currently velocity always uses the full range regardless.
- **Global contrast → filter opening / brightness.** Maps naturally to CC74
  or to how open the sound is.

### Not worth mapping

Nebula coverage (1.2×) and nebula saturation (1.6×) barely move between
photographs. Clark–Evans would be the right statistic for clustering, but it
needs a density-matched subsample before it measures anything real.

---

## Harmony: the pitch-class bottleneck

`MidiFactory.color_to_note` is `round(hue * 12) % 12`, which collapses the
whole image onto very few notes:

| image | distinct notes |
|---|---|
| e000275 | 4 of 12 (C, C#, D, D#) |
| e002086 | 2 of 12 |
| e000012 | 5 of 12 |
| e001642 | 5 of 12 |
| iss071 | **1 of 12** |

In e000275, 21 of 25 dominant colours map to the same note, because the image
is reddish throughout and hues from 0° to 14° all round to C.

Options, in order of how much they change the sound:

1. Normalise hue against the image's own range instead of the absolute wheel,
   so a narrow-hue photograph still spreads across the scale.
2. Use the colour index (B−R)/(B+R), already used for star pitch and known to
   stay meaningful on near-white sources.
3. Let a nebula's chords modulate, rather than all sharing one tonic.

This is the reason a 20-minute piece from a red image circles one chord. Worth
attacking before adding more expression on top.

---

## Live and continuous input

### Chaining images live
Play one image, and when its cycles are done move to the next, carrying the
harmony across the seam rather than restarting. Needs: a queue of images,
analysis of the next one while the current plays, and a transition rule so the
first chord of the new image voice-leads from the last chord of the old.

### Video and camera input
Capture frames from a camera or a video file and treat each frame as an image.
The hard parts are not the capture:
- Analysis currently takes about 5 seconds per image; a frame rate of any kind
  needs that under ~100 ms, so detection has to become incremental.
- Consecutive frames are nearly identical, so the interesting signal is what
  *changed*, not what is there. That is a different detector.
- The timeline is built ahead of time; live input means building it as it
  plays, which the `Sequencer` currently cannot do.

Both share a prerequisite: the pipeline has to separate "analyse an image"
from "schedule a piece" more cleanly than it does now.

---

## Smaller things

- `music/` (orchestrator, harmonic_path, star_mapper) is dead code, superseded
  by `mapping/`. `HarmonicPath` would crash if called — `Chord` is frozen and
  it assigns to `chord.duration`. Delete it.
- `ChordProgression` and `models/chords.py::Filmscoring` are near-duplicate
  implementations of the same rules.
- The harmony modules have no tests at all, while detection and transport have
  97. `_apply_progression` can leave a chord at zero duration; path search can
  return `None`.
- Star layers share one density budget. A per-layer budget would let big stars
  stay sparse while small ones carry the texture.
