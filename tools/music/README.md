# tools/music

Audio for "I love Kuni" (prologue, dream chapters, interludes, epilogues), synthesized from scratch with numpy/scipy
(no samples, no external synths). Output goes straight into `data/`. The one exception is `rec/`: sounds the author
recorded himself (the spoon in his tea), cut and varied by `render.py` like any other.

- `synth.py`: the small synth/sequencer library. It has oscillators, ADSR, FM e-piano, bell,
  additive pad, bass, drums, noise (periodic/loopable), circular FFT filters,
  convolution reverb, echo, `Timeline` mix bus, `fold_loop`/`crossfade_loop`,
  loudness mastering (ffmpeg `ebur128`), ogg encoding, and the loop seam check.
- `render.py`: the track and SFX definitions plus the render driver.
- `aggro.py` + `hum/aggro.json`: the author's hummed `aggro.mid` (175 bpm shuffle, F# minor), quantized, and the
  helpers to re-orchestrate it under Kuni's theme (`Song`, `glide_line`).
- `unused/`: finished loops the game doesn't use yet (`render.py` `UNUSED`, rendered only by name), outside `data/` so
  they are not packed. Empty for now.

## Run (from repo root)

    ~/.local/bin/uv run --with numpy --with scipy tools/music/render.py           # everything
    ~/.local/bin/uv run --with numpy --with scipy tools/music/render.py rain page # selected

Alternatively you can use the local venv:

    ~/.local/bin/uv venv tools/music/.venv && VIRTUAL_ENV=tools/music/.venv ~/.local/bin/uv pip install numpy scipy
    tools/music/.venv/bin/python tools/music/render.py

Requires `ffmpeg` with libvorbis. A full render takes about 4–5 minutes (the bowed strings are slow) and is deterministic (fixed seeds).

## Outputs

| file | kind | notes |
|---|---|---|
| `data/music/night_code.ogg` | loop 82.3 s | 70 bpm lo-fi, Kuni's theme (24 bars), -16 LUFS |
| `data/music/menu.ogg` | loop 53.3 s | theme variation, +2 semitones, bell lead, -16 LUFS |
| `data/music/rain.ogg` | loop 40 s | rain + drips + one distant thunder, -18 LUFS |
| `data/music/fans.ogg` | loop 24 s | fan whoosh + beating hum at 140 Hz and 163 Hz, -21 LUFS |
| `data/music/daily.ogg` | loop 55.4 s | 104 bpm gavotte: theme on ornamented harpsichord, alberti, pizzicato, strings, flute; -16 LUFS |
| `data/music/tender.ogg` | loop 72.7 s | 66 bpm, lute-stop harpsichord arpeggios, theme on solo violin, flute outro; -16 LUFS |
| `data/music/tender_fire.ogg` | loop 72.7 s | `tender` with the fireplace bed baked in (-14 dB); -16 LUFS |
| `data/music/tension.ogg` | loop 54.5 s | 88 bpm A minor, 3+3+2 low-string ostinato, timpani, harpsichord stabs, theme bent to minor; -16 LUFS |
| `data/music/mystery.ogg` | loop 48 s | 60 bpm glass harmonica, celesta motif 0-3-4-7, reversed swells, clock tick; -17 LUFS |
| `data/music/tarot.ogg` | loop 58.2 s | 66 bpm, D dorian: bell arpeggio over glass pads and a low string drone, reversed swells, no drums; -17 LUFS |
| `data/music/night_kuni.ogg` | loop 64 s | 60 bpm music-box lullaby of the theme over e-piano + strings, -2 st; -17 LUFS |
| `data/music/night_kuni_rev.ogg` | loop 64 s | the same lullaby played backwards (the horror rounds of «На краю контекста»); -18 LUFS |
| `data/music/morning.ogg` | loop 75.8 s | 76 bpm, +2 st, violin then flute, harpsichord, birds; last 4 bars e-piano only; -16 LUFS |
| `data/music/jump.ogg` | loop 49.7 s | 116 bpm, string ostinato, harpsichord 16ths, timpani, theme in octaves; -15 LUFS |
| `data/music/bad_end.ogg` | loop 53.3 s | 54 bpm, theme in C minor on a detuned music box, cold drone; -18 LUFS |
| `data/music/ending.ogg` | loop 60.7 s | credits song, 166 bpm piano-pop band: E-major intro/verse/pre (03:47 motif on bell), chorus drops to C with Kuni's theme at half speed on violin + flute, bell outro, 2 bars ring-out; -16 LUFS |
| `data/music/game.ogg` | loop 121.4 s | 174 bpm, the only fast loop (the first tic-tac-toe loop, renamed): woodblock tic-tac intro, theme A on a pulse chip lead + piano and theme B on flute (note values doubled), then a 36-bar bridge on the author's hummed C#-minor riff and half-time groove (kawaii.mid) with a written overdriven lead (his F#-B lick, Kuni's theme +4, a climb to G#6) and his 4-bar drum break (A B E E7 into Fmaj9), then the theme on the lead guitar; bells only in the second half (glockenspiel chimes on the riff's stabs and the solo's long notes, arpeggios two octaves up in the reprise, Kuni's collar-bell jingle on 2 and 4 from bridge bar 17); -16 LUFS |
| `data/music/tictactoe.ogg` | loop 132 s | 80 bpm, the calm tic-tac-toe loop: e-piano, brushes, a quiet woodblock tic-tac; theme A on e-piano, theme B on flute, a bridge in turns (e-piano moves, flute answers, a woodblock knock puts the piece down; Bb C/Bb Am7 Dm9 Gm9 C9sus F, Bbm6 D7b9, thirds into E7b9), then the theme on the music box with glockenspiel (bells only there); -17 LUFS |
| `data/music/fireplace.ogg` | loop 30 s | fire roar, crackles, pops; -20 LUFS |
| `data/music/car.ogg` | loop 24 s | inside an old V8 car: burble, road roar, bumps; -20 LUFS |
| `data/music/swagger.ogg` | loop 120.7 s | 175 bpm half-time trap on the author's hum (aggro.mid, `aggro.py`): his sung section as the hook on chip + e-piano, 808 on his bass, her theme as the verse, his guitars in the drop (the stabs on his own bass and drums), breakdown with music-box answers, a quiet collar bell on beat 3; -15 LUFS |
| `data/music/assertive.ogg` | loop 131.7 s | 175 bpm, the author's hum as a band (aggro.mid, `aggro.py` `assertive()`): his B5/A5 stabs with her theme on chip as the lead-in, his breakdowns with her music-box answers, his gallop with his sung line on her harpsichord (octaves, triplet arpeggios, pizzicato, violin, timpani), her theme on the lead guitar over his low gallop, an 8-bar ending in the grid landing on the high F#; double-tracked guitars (random 3-14 ms per take, no lean), Kuni's bus binaurally circling the listener (ITD 0.7 ms, head shadow, `ASSERTIVE_PATH`); -15 LUFS |
| `data/sound/*.ogg` | one-shots | prologue: keys, backspace, enter, fans_to_rain, page, buzz, bell; dream: rain_to_fans, pop, remember, purr, bell_collar, door, door_close, clock_tick, clock_start, thunder, oracle_sat, oracle_unsat, doorbell, dishes, glitch, shimmer, ringback; «Край»: heartbeat, ink_vanish, name_crunch, whisper_breath, tinnitus; gestures on the panel (`gesture::*::sound`, each step of the hand): spoon_clink_1…5 (each half turn of the tea, one take at random: the author's recording rec/sugar_mix, a little higher or lower each time), spoon_done (the spoon knocked off on the rim after it, rec/sugar_mix_end), pendulum_nudge, glass_wipe_1…3 (each stroke on the mirror, a damp swish with no tone), fur_rub (each stroke behind her ear), porcelain_lid (the sugar bowl found), pencil_strike, key_turn, airbrush, laptop_shut (the Oracle lever is oracle_unsat, her hand is heartbeat); achievement (the «получено достижение» card: E G A of the theme on bells over Fmaj9 glass). Peak -3 dBFS, except dense ones set lower in `SFX` (remember/purr/oracle_sat/doorbell/dishes/shimmer -5, bell_collar -7, glitch -9, ringback -14, heartbeat -6, ink_vanish/name_crunch -8, whisper_breath -10, tinnitus -16, glass_wipe -9, fur_rub/airbrush -9, pencil_strike -6, spoon_clink/spoon_done -4, achievement -6) |

The full list with moods and where to use each id is in `docs/AUDIO.md`.

## Does the stack play real music

Yes. It was checked by ear on popular melodies: a two-hand piano arrangement transcribed from sheet music (numbered
notation, 45 bars) was sequenced on a `Timeline` with `epiano` and `reverb`, mastered with `master_loudness`, and
the author recognized the tune. So pitch, timing, chords, ties and triplets come out right; if a track sounds wrong,
look at its notes, not at the synth.

The test material was somebody else's song, so neither the script nor the render is in the repo, and none of it may
be added. Tracks in `render.py` are original.

## How the loops stay seamless

Loops are rendered circularly. Notes and reverb tails that run past the loop end are
folded back onto the start, noise is generated in the frequency domain (periodic
by construction), filters are applied via FFT, and every LFO or tone frequency has an
integer number of cycles per loop. `render.py` asserts that the decoded ogg has the
exact sample length and that the seam jump `|x[0]-x[-1]|` is below 1.5x the
99.9th percentile of normal sample steps.
