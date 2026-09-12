# Legacy modules

Not imported by anything. Kept because they record decisions worth
remembering, moved out of the live packages so that `src/detection`,
`src/midi` and the rest contain only code that runs.

- `utils.py` — pixel-by-pixel star tests from before the array rewrite. The
  detector now works on whole arrays; the per-pixel version took minutes on a
  16 Mpx image.
- `quantizer.py` — set `star.duration` in ticks, which the player then
  overwrote in beats. One field, two units. Note length is now decided once,
  in `mapping/`.
- `setup_image.py`, `setup_player.py` — never importable: undefined names and
  an import path that does not resolve.
- `cloud_detector.py`, `cloud_utils.py` — the first nebula detector, with
  fixed thresholds on raw luminance. It called 29% to 99.9% of a frame one
  nebula. Superseded by the band-pass in `detection/nebula_detector.py`.
  `cloud_utils._get_filter_curve` lives on, reimplemented and vectorised, as
  `NebulaDetector._filter_curve`.
- `clock.py` — the original MIDI clock. It slept a fixed interval between
  pulses, so every overshoot accumulated: measured, it lost 1.82 s over 20 s,
  about 8 beats per minute. Replaced by `midi/transport.py`, which schedules
  each pulse against an absolute origin (about 5 ms per minute).
- `star_player.py`, `realtime_player.py` — one thread per layer, each sleeping
  its own note lengths, so the layers drifted apart from each other as well as
  from the clock. Replaced by a single `Sequencer` reading one timeline.
