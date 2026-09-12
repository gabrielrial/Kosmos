# Kosmos

An experimental image-to-MIDI instrument for astronomical photographs.

Kosmos measures an image — where the stars are, how bright and what colour
they are, where the diffuse nebulosity lies — and turns those measurements
into music. The result plays live over virtual MIDI ports, so a DAW such as
Ableton Live can follow Kosmos' clock, and is also written to a `.mid` file.

---

## How it works

An image is analysed in two passes, separated by **spatial frequency** rather
than brightness, because that is what actually distinguishes a star from a
cloud:

| band | what it holds | goes to |
|---|---|---|
| high | small, sharp | the star detector |
| mid | large, soft | the nebula detector |
| low | sky, gradient, vignetting | discarded |

**Stars** are extracted as connected regions above an adaptive threshold. Each
one is measured for position, area, integrated flux, shape and colour, then
split into two playing layers by brightness. Sources that are not point-like
are rejected rather than played.

**Nebulae** are found in the middle band using hysteresis: a high threshold
decides where a region may start, a much lower one decides how far it reaches,
and a pixel is kept only if it clears the low threshold *and* connects back to
a seed. A nebula has no edge, it fades out, so a single threshold leaves
disconnected bright cores instead of one cloud.

**The music** is assembled as a single list of events positioned in beats.
Each nebula's dominant colours become a chord progression; each star becomes a
note, pitched from its colour index, placed in time from its vertical
position, panned by its horizontal position, and fitted to whichever chord is
sounding underneath it.

---

## Requirements

- Python 3.11 or later
- macOS, Linux or Windows
- A DAW that accepts virtual MIDI ports, for live playback

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

SciPy is optional in practice — connected-component labelling falls back to a
pure-numpy implementation if it is missing, just more slowly.

---

## Usage

```bash
python src/main.py conf.json img/space.jpg
```

That analyses the image, writes `output/space.mid`, and plays it live while
sending MIDI clock.

| flag | effect |
|---|---|
| `-o DIR` | where the `.mid` and preview images go (default `output`) |
| `--mode live` | real time only, nothing written |
| `--mode file` | write the `.mid` only, no MIDI ports opened |
| `--midi-name NAME` | name for the `.mid` (default: the image's name) |

Two artefacts are written next to the run so detection can be checked by eye:
`stars_detected.png` marks small stars in blue, big ones in gold and rejected
sources in red; `nebula_debug.png` boxes each detected region.

### Connecting Ableton Live

Kosmos exposes four virtual ports: `kosmos_stars`, `kosmos_nebula`,
`kosmos_clock` and `kosmos_bass` (reserved).

For **live playback**, in Live: Preferences → Link/Tempo/MIDI, set **Sync: On**
for `kosmos_clock`, then put the transport in **EXT**. Live follows Kosmos'
tempo, start and stop. On macOS, enable the IAC Driver in Audio MIDI Setup
first if your setup needs it.

For **exact timing**, use `--mode file` and drag the `.mid` into a clip
instead. Live playback is limited by how precisely a general-purpose operating
system can wake a thread — a few milliseconds of jitter that no amount of
Python removes. In a file the events are numbers on a grid and Live's own
engine places them. Live playback is for exploring; the file is for producing.

---

## Calibration

Every threshold below was chosen from measurements, not by ear. The tool that
produced them is in the repository:

```bash
python tools/survey.py conf.json img/*.jpg
```

It runs the real detectors with no MIDI and prints one row per image: how many
sources, how they split between layers, how many were rejected, the footprint
and flux distributions, how many stars have usable colour, and how much of the
frame the nebulae cover. Use it to choose values, and to check that a change
to a detector improved things rather than guessing.

```bash
# sweep a threshold without editing conf.json
python tools/survey.py conf.json img/*.jpg --set star_detector.detection_sigma=6
```

---

## Configuration

All lengths are **fractions of the image's longest side**, not pixels, so
`images.working_size` can change without recalibrating everything else.

### `images`

| key | meaning |
|---|---|
| `working_size` | the longest side is resized to this before analysis. `0` disables resizing |
| `saturation_boost` | saturation multiplier used for colour sampling |

Resizing matters more than it looks. With absolute pixel radii, the same
photograph at 450, 900 and 1800 px produced 142, 961 and 4,121 stars — the
number of notes was a property of which file had been downloaded.

### `star_detector`

| key | meaning |
|---|---|
| `background_radius_frac` | blur scale used to estimate the local sky |
| `detection_sigma` | threshold in units of MAD noise above that sky |
| `minimum_contrast` | absolute floor for the threshold |
| `minimum_brightness` | absolute luminance floor, 0–255 |
| `minimum_area_px` | regions smaller than this are noise |
| `max_area_frac` | regions larger than this fraction of the frame are not stars |
| `roundness_min` | minimum area ÷ bounding-box area; rejects ragged wisps |
| `max_elongation` | maximum bounding-box aspect ratio; rejects solid bars |
| `roundness_area_px` | only test shape above this area |
| `big_star_flux_percentile` | the layer split. `98` puts the brightest 2% in the low layer |
| `aperture_radius_px` | radius of the colour-sampling aperture |

Both shape gates are needed: a bar fills its bounding box completely and passes
the roundness test on its own.

### `nebula_detector`

| key | meaning |
|---|---|
| `star_suppression_frac` | median filter applied before the band, to remove stars. `0` disables |
| `small_radius_frac` | upper edge of the band; large enough to erase stars |
| `large_radius_frac` | lower edge; must be clearly larger than the biggest structure you want to keep |
| `seed_sigma` | high threshold: where a region may start |
| `grow_mode` | `sigma` or `percentile` — how the low threshold is chosen |
| `grow_sigma` | low threshold in noise units, for `grow_mode: sigma` |
| `grow_percentile` | low threshold as a percentile of the band, for `grow_mode: percentile` |
| `max_cover_frac` | safety stop: growth never masks more than this share of the frame |
| `max_star_flux_share` | discard a region when this share of its light comes from point sources |
| `min_area_frac` | smallest region worth a musical phrase |
| `max_area_frac` | `0` disables the upper limit |
| `saturation_threshold` | `0` accepts colourless structure |
| `dominant_colors` | how many representative colours per region |

`large_radius_frac` is the one to reach for first if a large nebula is detected
only as scattered bright patches: too small a radius and the nebula ends up
inside its own background estimate and subtracts itself.

### `stars`

| key | meaning |
|---|---|
| `small_low_note` / `small_high_note` | MIDI range of the small-star layer |
| `big_low_note` / `big_high_note` | MIDI range of the big-star layer |
| `small_duration_beats` / `big_duration_beats` | note length per layer |
| `small_channel` / `big_channel` / `chord_channel` | MIDI channels; all three must differ |
| `pan_cc` | controller used for stereo position. `10` is the MIDI standard; `7` works if mapped by hand in the DAW |
| `shuffle` | randomise order within a layer, seeded so runs repeat |

### `transport`

| key | meaning |
|---|---|
| `send_clock` | emit MIDI beat clock so a DAW can follow |
| `send_song_position` | send a song-position pointer of 0 before start |
| `grid_subdivision` | the rhythmic grid, in divisions of a beat. `4` is sixteenths |
| `quantise_strength` | how far notes are pulled onto that grid. `1.0` snaps, `0.0` leaves them free |
| `notes_per_slice` | **density cap**: how many star notes may start in one slice. `0` keeps everything |
| `star_duration_scale` | multiplies both layers' note lengths |
| `fit_stars_to_chord` | move each star note to the nearest pitch of the chord sounding under it |
| `count_in_beats` | silence before the first event, so a DAW has time to lock |

`notes_per_slice` is the control that decides whether the piece sounds like
music or like a cloud. A detector finding thousands of stars otherwise
produces thousands of notes: on one image that measured 8.4 notes per second.
Thinning keeps the loudest note of each slice, so quiet parts of the image
stay quiet instead of being flattened.

**To make the stars slower**, lower `grid_subdivision` and `notes_per_slice`
together:

| `grid_subdivision` | `notes_per_slice` | result |
|---|---|---|
| 4 | 2 | 6.8 notes/s |
| 2 | 1 | 2.8 notes/s |
| 1 | 1 | 1.6 notes/s |

### `tempo` and `harmony`

| key | meaning |
|---|---|
| `tempo.bpm` | tempo in beats per minute |
| `tempo.subdivision` | beat subdivision |
| `harmony.nebula_total_duration_beats` | phrase length given to each nebula |
| `harmony.octave_offset` | octave shift for harmonic roots |

---

## Layout

```text
src/
  main.py               CLI
  pipeline/             analyse -> compose -> play / export
  image/                load and resize
  detection/            star_detector, nebula_detector, labeling
  models/               Star, Nebula, Color, Chord — data only
  mapping/              star_mapper, timeline — every musical decision
  midi/                 transport, messages, midi_creator, harmony
  _legacy/              superseded modules, imported by nothing
tools/survey.py         calibration
tests/                  58 tests on synthetic images
```

The line between `detection/` and `mapping/` is the one rule worth keeping: a
detector returns measurements and never decides a note, so a change to how the
music sounds never means editing a detector.

---

## Development

```bash
python3 -m unittest discover -s tests
python3 -m compileall -q src tools tests
python3 -m json.tool conf.json > /dev/null
```

Tests run on synthetic images with known contents — planted stars at known
positions, a bar that must be rejected, a cloud that must survive the star
filter — so a failure points at the algorithm rather than at a judgement call
about a photograph. The `.mid` export is verified with an independent SMF
parser rather than the library that wrote it.

---

## Notes

- Detection is heuristic and calibrated against the images in `img/`. It is
  not a scientific classifier.
- Nebula chord roots are currently pitch classes 0–11, so chords sound in the
  bottom MIDI octave. Known, and the next thing to fix.
