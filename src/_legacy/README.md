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
