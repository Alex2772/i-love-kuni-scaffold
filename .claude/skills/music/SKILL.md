---
name: music
description: Make or change the game's music loops and sound effects by synthesizing them from scratch with the project's numpy synth (tools/music), with no samples or external synths. Use when a scene needs a new track or SFX (music("id") / sound("id") with no data/music|sound/<id>.ogg), when the user asks to write, re-render, tweak or fix music/sounds ("сделай музыку", "нужен звук", "переделай трек", "щёлкает на стыке", "тише/громче"), or to check audio levels and loop seams.
---

# Music and SFX for I love Kuni

All audio is code. `tools/music/synth.py` is a small synth and sequencer library. `tools/music/render.py` defines
every track and SFX, renders them into `data/music/<id>.ogg` (loops) and `data/sound/<id>.ogg` (one-shots), and
checks them. There are no samples, no MIDI and no fluidsynth/timidity, because none of them are installed. Never copy
existing melodies: write original ones.

The story uses audio by id: `music("night_code")` loops `data/music/night_code.ogg` with a ~0.7 s crossfade,
`sound("keys")` plays `data/sound/keys.ogg` once. A missing file only logs `Audio: missing ...`, so grep the game's
stdout for that after playing a scene.

## 1. Find out what is needed

- Missing ids: `grep -rhoE '(music|sound)\("[a-z_0-9]+"\)' story engine | sort -u`, then compare with
  `ls data/music data/sound`.
- Read the scene where the id is used (and `docs/CHAPTERS.md` for that chapter): mood, what is on screen, how long
  the reader stays there. A loop plays under several pages. A SFX goes with one text box.

## 2. Write it in render.py

Read `tools/music/README.md` and the existing definitions in `render.py` first, and reuse their pieces.

- **Loops** are functions that return a stereo buffer of exactly the loop length. Build them on a
  `Timeline(seconds)` and take `.loop()`: anything ringing past the end (notes, reverb, echo) is folded back onto the
  head, which is exactly what a looping player sounds like. Use `circ_filter` (FFT, circular) instead of
  `sos_filter`, `colored_noise`/`noise` (periodic by construction), `reverb(..., loop=True)`, and give every LFO or
  steady tone an integer number of cycles per loop (`periodic_lfo(n, cycles)`). A loop that breaks these rules clicks
  at the seam.
- Length is a whole number of bars: `bars * 4 * 60 / bpm`. Music is 45–90 s, ambience 20–45 s.
- **Theme**: Kuni's theme is `MEL_A`/`MEL_B` over `PROG_A`/`PROG_B`. New tracks with an emotional role (tender,
  tension, bad end) should vary it (transpose, change the instrument, rhythm or harmony) rather than invent unrelated
  material. That way the soundtrack hangs together.
- **SFX** are functions that return a one-shot buffer (`Timeline(...).oneshot()` or a plain array), with `fade()` at
  both ends.
- Register the function in `LOOPS` (`name: (fn, target_LUFS)`) or `SFX` (`name: fn`).
- Use fixed seeds (`np.random.default_rng(N)`, `seed=` arguments): renders must be deterministic.

Levels: music -16 LUFS. Ambience under dialogue is quieter: rain -18, fans -21. SFX are peak-normalized to -3 dBFS by
the driver.

## 3. Render

From the repo root, with only the names you changed:

```bash
~/.local/bin/uv run --with numpy --with scipy tools/music/render.py <name> [<name>...]
```

Without names it renders everything (~1 min). It needs ffmpeg with libvorbis (installed). The system python has no
numpy, so always go through `uv` (or `tools/music/.venv`). The driver asserts that the decoded ogg has the exact
sample length and that the loop seam jump is below 1.5 (a ratio to normal sample steps; anything below is
inaudible). It prints LUFS, peak and the seam for every file. An assertion is a bug in the track: fix the track,
don't loosen the check.

## 4. Check it

You can't listen, so check what you can and say so in the report:

- the numbers the driver printed: LUFS on target, peak below -1 dBFS for loops and around -3 dBFS for SFX, seam < 1.5;
- the spectrogram, which shows silence, clipping, a harsh top or muddy bass at a glance:
  `ffmpeg -v error -y -i data/music/<id>.ogg -lavfi showspectrumpic=s=1200x400:legend=1 <scratchpad>/<id>.png`,
  then Read the PNG;
- in the game, if a scene uses it: play the scene through aui-remote (`aui-remote` skill) and grep the stdout for
  `Audio`.

Then tell the user what to listen for (for example "the thunder at 13 s", "is the hum too loud under the text").
Their ear is the real test, so never claim that a track "sounds good".

## Rules

- Write only to `tools/music/` and `data/music|sound/`. `tools/music/.venv` and `__pycache__` are gitignored.
- Keep `tools/music/README.md`'s outputs table in sync when you add or change a file.
- Commit only when the user asks.
