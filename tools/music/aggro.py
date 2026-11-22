"""The author's hummed aggro.mid (hum/aggro.json) and what is built on it.

His song: 175 bpm, 12/8 shuffle (3 "slots" per beat, 12 per bar), F# minor / phrygian, 88 bars = 2:01, and its last
F#-E-F# is a pickup that runs straight back into bar 0. By bars:
    0-15  chug F/F# with C5 tritone stabs        40-47 breakdown: F#5/G5 hits, his tambourine
    16-19 B5/A5 stabs                            48-63 his sung line (half notes on 3 and 1) over the gallop:
    20-31 F5/C5, F#5 gallop                            F# hits on slots 0, 2, 5, long E D C B / E D# C B
    32-35 B5/A5 stabs                            64-79 low F# gallop
    36-39 F5 gallop                              80-87 E pedal, his last sung notes

Song wraps a Timeline in that grid and re-orchestrates his parts (band or chamber), Kuni's theme goes on top.
`swagger()` (half-time trap) and `assertive()` (his band, her circling around the listener) are the loops built on it.
"""
from __future__ import annotations

import collections
import functools
import json
import os

import numpy as np

import render as R
from synth import *  # noqa: F403

_HUM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "hum", "aggro.json")))
GTR, BASS, DRUMS, VOICE = ([tuple(n) for n in _HUM["tracks"][k]] for k in ("guitar", "bass", "drums", "voice"))


def take(track, src_bar, nbars):
    """His notes of bars [src_bar, src_bar + nbars) as (slot from the start of the range, midi, slots)."""
    a, b = src_bar * 12, (src_bar + nbars) * 12
    return [(s - a, p, ln) for s, p, ln in track if a <= s < b]


def chords_of(notes):
    """Group simultaneous notes: [(slot, sorted midis, slots)]."""
    g = collections.defaultdict(list)
    for s, p, ln in notes:
        g[s].append((p, ln))
    return [(s, sorted(p for p, _ in v), max(ln for _, ln in v)) for s, v in sorted(g.items())]


# ------------------------------------------------------------------ Kuni's theme in his key
TR = -3  # A minor / C major -> F# minor / A major


def swing(bars):
    """Straight eighths -> his shuffle: an "and" moves to the last triplet of the beat."""
    def sw(x):
        i = int(x // 1)
        f = x - i
        return i + {0: 0, .5: 2 / 3}.get(round(f, 3), f)
    return [[(sw(b), m, sw(b + ln) - sw(b)) for b, m, ln in bar] for bar in bars]


def theme(bars, transpose=TR, k=1, swung=True):
    out = R.stretch(bars, k) if k != 1 else bars
    out = swing(out) if swung else out
    return [[(b, m + transpose, ln) for b, m, ln in bar] for bar in out]


def chord_tr(name, tr=TR):
    v, r = R.CH[name]
    return [m + tr for m in v], r + tr


# the breakdown: he hits, she answers in the empty bars (a music-box lick each, an octave up)
LICKS = theme([R.MEL_A[0], R.MEL_A[4], R.MEL_A[0],
               [(0, 81, .5), (.5, 79, .5), (1, 76, .5), (1.5, 74, .5), (2, 76, 2)]], TR + 12)

# ------------------------------------------------------------------ instruments
@functools.lru_cache(maxsize=None)
def b808(m, dur, vel):
    """808-ish sub: sine with a pitch drop at the hit, a little drive."""
    f = midi_hz(m)
    ng = n_samples(dur)
    n = ng + n_samples(0.08)
    t = t_axis(n)
    fi = f * (1 + 0.6 * np.exp(-t / 0.025))
    x = np.sin(TAU * np.cumsum(fi) / SR)
    env = np.exp(-t / max(0.35, dur * 0.9)) * (1 - np.exp(-t / 0.002)) * release_tail(ng, n, 0.08)
    return np.tanh(2.2 * x * env) / np.tanh(2.2) * vel


def clap(vel=0.6, seed=0):
    n = n_samples(0.3)
    t = t_axis(n)
    nz = sos_filter(noise(n, seed), "bandpass", (900, 5000), 2)
    env = sum(np.where(t >= d, np.exp(-(t - d) / 0.006), 0) for d in (0, 0.011, 0.022))
    env = env + np.where(t >= 0.03, 0.6 * np.exp(-(t - 0.03) / 0.07), 0)
    return nz * env * vel


@functools.lru_cache(maxsize=None)
def spicc(m, dur, vel):
    """Short bowed note (spiccato), a two-voice section. Cached."""
    return strings(m, dur, vel, attack=0.012, rel=0.07, voices=2, seed=3)


@functools.lru_cache(maxsize=None)
def pizz_c(m, vel):
    return pizz(m, vel)


@functools.lru_cache(maxsize=None)
def harp_c(m, dur, vel):
    return harpsichord(m, dur, vel)


@functools.lru_cache(maxsize=None)
def chip_c(m, dur, vel):
    return R.chip(m, dur, vel)


@functools.lru_cache(maxsize=None)
def bell_c(m, dur, vel):
    return bell(m, dur, vel, rel=1.0)


def violin(m, d, v):
    return strings(m, d, v, attack=0.05, rel=0.3, solo=True, seed=8)


def jingles(seed):
    return [stereo(R.jingle(np.random.default_rng(seed + k), f0=3300.0 + 120 * k, strikes=2,
                            spacing=(0.012, 0.025), decay=0.6)) for k in range(4)]


def glide_line(notes, timbre="strings", vel=0.8, seed=0):
    """One legato phrase with portamento, like R.lead_guitar but not a guitar. notes: [(sec, midi, sec, art)].
    art: "s" slide from the previous note, "b" scoop up a tone into it, "g" the glance: a quick scoop, a harder
    accent and a tighter vibrato (a growl on "cat"), "f" fall off the end.
    timbre: "strings" (a section, three bows), "violin" (solo), "cat" (a filtered saw lead). Stereo."""
    rng = np.random.default_rng(seed)
    end = notes[-1][0] + notes[-1][2] + (0.3 if notes[-1][3] == "f" else 0.15)
    n = n_samples(end) + 1
    t = t_axis(n)
    pitch = np.full(n, float(notes[0][1]))
    acc = np.zeros(n)     # accent at each onset
    since = np.zeros(n)   # time since the note began
    glance = np.zeros(n)  # 1 inside a "g" note
    prev = notes[0][1]
    for i, (s, m, d, art) in enumerate(notes):
        a, b = n_samples(s), min(n, n_samples(s + d))
        tt = t[a:b] - s
        p = np.full(b - a, float(m))
        if art in ("b", "g"):
            p -= (2.0 if art == "b" else 1.0) * np.clip(1 - tt / (0.12 if art == "b" else 0.07), 0, 1) ** 2
        elif i > 0:
            p += (prev - m) * np.exp(-tt / (0.06 if art == "s" else 0.014))
        pitch[a:b] = p
        acc[a:b] = (1.0 if art == "g" else 0.5) * np.exp(-tt / 0.09)
        since[a:b] = tt
        glance[a:b] = 1.0 if art == "g" else 0.0
        prev = m
    s, m, d, art = notes[-1]
    a = min(n, n_samples(s + d))
    tail = t[a:] - (s + d)
    since[a:] = d + tail
    if art == "f":
        pitch[a:] = m - 4 * (tail / 0.3) ** 1.5
    else:
        pitch[a:] = pitch[a - 1]
    vib_depth = {"strings": 0.0035, "violin": 0.0055, "cat": 0.004}[timbre]
    env = 0.72 + acc
    env *= 1 - np.exp(-np.maximum(t - notes[0][0], 0) / (0.03 if timbre == "cat" else 0.05))
    env *= np.where(t < s + d, 1.0, np.exp(-np.maximum(t - (s + d), 0) / (0.05 if art != "f" else 0.12)))
    env = R.signal.sosfilt(R.signal.butter(1, 60, "lowpass", fs=SR, output="sos"), env)
    out = np.zeros((n, 2))
    voices = {"strings": (-7, 0, 6), "violin": (0,), "cat": (-5, 5)}[timbre]
    for vi, cents in enumerate(voices):
        vr = rng.uniform(5.2, 6.0) * (1 + 0.25 * glance)
        vib = vib_depth * np.clip((since - 0.18) / 0.3, 0, 1) * np.sin(TAU * vr * t + rng.uniform(0, TAU))
        f = 440.0 * 2 ** ((pitch - 69) / 12) * 2 ** (cents / 1200) * (1 + vib)
        ph = TAU * np.cumsum(f) / SR
        fmax = float(f.max())
        x = np.zeros(n)
        if timbre == "cat":
            # saw through a lowpass that opens on every accent (and wide on a glance), a sub-octave growl on a glance
            fc = 1400 + 3800 * acc + 1500 * glance
            for k in range(1, int(9000 / fmax) + 1):
                g = 1 / np.sqrt(1 + (k * f / fc) ** 4)
                x += g * np.sin(k * ph + rng.uniform(0, TAU)) / k
            x += 0.35 * glance * np.tanh(3 * np.sin(ph / 2)) * (0.5 + 0.5 * np.sin(TAU * 31 * t))
            x = np.tanh(1.6 * x) / 1.2
        else:
            kmax = int((7000 if timbre == "violin" else 5500) / fmax)
            k = np.arange(1, kmax + 1)
            w = R.butter_mag(k * fmax, "bandpass", (250, 3500), 1) / k ** (0.9 if timbre == "violin" else 1.05)
            bright = 1 + 0.6 * acc
            for i in range(kmax):
                x += w[i] * np.sin(k[i] * ph + rng.uniform(0, TAU)) * (bright if i > 2 else 1)
            x /= np.sum(w) * 0.5
        p = 0.0 if len(voices) == 1 else -0.5 + vi / (len(voices) - 1)
        out += pan(x * env, p) / np.sqrt(len(voices))
    if timbre != "cat":
        bow = sos_filter(noise(n, seed + 5), "bandpass", (1500, 6000), 2) * (0.02 + 0.05 * acc)
        out += stereo(bow * env)
    return fade(out * vel * 0.5, 0.002, 0.02)


@functools.lru_cache(maxsize=None)
def guitar_chord(root, dur, muted, vel, intervals=(0, 7, 12)):
    """R.power_chord with a choice of intervals: (0, 12) is his hummed single note, doubled an octave up."""
    if intervals == (0, 7, 12):
        return R.power_chord(root, dur, muted, vel)
    sr2 = 2 * SR
    ring = dur + (0.05 if muted else 0.25)
    n = int(ring * sr2)
    t = np.arange(n) / sr2
    x = np.zeros(n)
    for k, iv in enumerate(intervals):
        f = midi_hz(root + iv) * (1 + 0.0015 * (k - 1))
        ph = TAU * f * t + k * 1.3
        x += sum(np.sin(j * ph) / j for j in range(1, int(6000 / f) + 1))
    x *= 1.5 / len(intervals)
    env = np.exp(-t / (0.09 if muted else 0.9)) * (1 - np.exp(-t / 0.0015))
    env *= np.clip((ring - t) / 0.03, 0, 1)
    x *= env * vel
    if muted:
        x = R.signal.sosfilt(R.signal.butter(2, 900, "lowpass", fs=sr2, output="sos"), x)
    y = R.amp_cab(x, 5.0, sr2, tone_hz=3800.0)
    return fade(y / 1.6, 0.001, 0.01)


# ------------------------------------------------------------------ a song in his grid
class Song:
    def __init__(self, bpm, bars, seed):
        self.bpm, self.spb = bpm, 60 / bpm
        self.slot = self.spb / 3
        self.bars = bars
        self.rng = np.random.default_rng(seed)
        self.tl = Timeline(bars * 4 * self.spb)

    def t(self, bar, slot=0.0):
        return bar * 4 * self.spb + slot * self.slot

    def h(self, a=0.003):
        return R.human(self.rng, a)

    def melody(self, bars, at_bar, inst, gain, pan_pos=0.0, vel=0.75, legato=1.0):
        R.place(self.tl, self.rng, bars, at_bar, self.bpm, inst, gain=gain, vel=vel, pan_pos=pan_pos,
                legato=legato, jitter=0.004)

    def lead(self, bars, at_bar, gain, seed=0, vel=0.8):
        """Overdriven lead guitar over a melody given in bars of (beat, midi, beats)."""
        notes = [(bi * 4 + b, m, ln, "b" if ln >= 2.5 else "") for bi, bar in enumerate(bars) for b, m, ln in bar]
        phrases, starts = R.solo_phrases(notes, self.spb)
        for ph, b0 in zip(phrases, starts):
            self.tl.add(R.lead_guitar(ph, vel, seed=seed + int(b0 * 4)), self.t(at_bar) + b0 * self.spb + self.h(),
                        gain)

    def glide(self, notes, at_bar, timbre, gain, transpose=0, vel=0.8, pan_pos=0.0, seed=0):
        """notes: [(slot from at_bar, midi, slots, art)], played as glide_line phrases split at rests."""
        ph, cur = [], []
        for nt in notes:
            if cur and nt[0] - (cur[-1][0] + cur[-1][2]) > 0:
                ph.append(cur)
                cur = []
            cur.append(nt)
        ph.append(cur)
        for p in ph:
            s0 = p[0][0]
            line = [((s - s0) * self.slot, m + transpose, ln * self.slot, art) for s, m, ln, art in p]
            x = glide_line(line, timbre, vel, seed=seed + s0)
            self.tl.add(x if pan_pos == 0 else x * np.array([1 - pan_pos, 1 + pan_pos]),
                        self.t(at_bar, s0) + self.h(), gain)

    # -- his parts, re-orchestrated
    def guitar(self, src, dst, nbars, gain=0.13, fifths=True):
        """fifths=False: his single hummed notes as root + octave (no fifth to rub against a melody on top)."""
        for s, ms, ln in chords_of(take(GTR, src, nbars)):
            root = ms[0] + (12 if ms[0] < 36 else 0)
            muted = ln == 1 and root <= 42
            vel = 0.95 if s % 3 == 0 else 0.85
            iv = (0, 7, 12) if fifths or len(ms) > 1 else (0, 12)
            self.tl.add(stereo(guitar_chord(root, round(ln * self.slot * (0.9 if muted else 0.85), 3), muted,
                                            vel, iv)), self.t(dst, s) + self.h(), gain)

    def chamber_guitar(self, src, dst, nbars, gain=1.0, fifths=True):
        """His guitar on the mansion's band: the chug on cellos pizzicato, power chords spiccato + harpsichord,
        long notes held by the low strings, timpani under the long ones."""
        for sl, ms, ln in chords_of(take(GTR, src, nbars)):
            root = ms[0] + (12 if ms[0] < 36 else 0)
            at = self.t(dst, sl) + self.h()
            vel = 0.85 if sl % 3 == 0 else 0.7
            if len(ms) == 1 and ln == 1:
                self.tl.add(pizz_c(root + 12, vel), at, 0.32 * gain, 0.15)
                self.tl.add(spicc(root + 12, round(0.6 * self.slot, 3), round(vel * 0.7, 2)), at, 0.1 * gain)
                continue
            d = round(min(ln, 3) * self.slot * 0.8, 3)
            iv = (0, 7, 12) if fifths or len(ms) > 1 else (0, 12)
            for j, m in enumerate(root + 12 + i for i in iv):
                self.tl.add(spicc(m, d, round(vel, 2)), at + j * 0.003, 0.18 * gain, -0.35 + 0.35 * j)
                self.tl.add(harp_c(m + 12, d, round(vel * 0.8, 2)), at, 0.1 * gain, 0.3 - 0.3 * j)
            if ln >= 6:  # held: cellos and basses sustain it
                for j, m in enumerate(root + i for i in iv):
                    self.tl.add(strings(m, ln * self.slot * 0.95, 0.6, attack=0.04, rel=0.25, voices=2, seed=j),
                                at, 0.12 * gain, -0.3 + 0.3 * j)
            if ln >= 2:
                self.tl.add(timpani(root - 12 if root >= 40 else root, 0.75), at, 0.5 * gain)

    def bass(self, src, dst, nbars, gain=0.6, inst="soft"):
        for s, p, ln in take(BASS, src, nbars):
            d = ln * self.slot * 0.9
            if inst == "soft":
                x = soft_bass(p, d, 0.85 if s % 3 == 0 else 0.7)
            elif inst == "808":
                x = b808(p if p >= 28 else p + 12, round(d, 3), 0.9)
            else:  # pizzicato basses an octave up
                x = pizz_c(p + 12, 0.8 if s % 3 == 0 else 0.65)
            self.tl.add(x, self.t(dst, s) + self.h(), gain, -0.05)

    def drums(self, src, dst, nbars, kit="rock", gain=1.0, jingle_set=None, track=None):
        js = jingle_set or jingles(1750)
        for i, (s, p, ln) in enumerate(take(track or DRUMS, src, nbars)):
            at = self.t(dst, s) + (self.h(0.002) if p not in (35, 36) else 0)
            seed = dst * 100 + s
            if p in (35, 36):
                self.tl.add(R.kick(0.55 if kit == "chamber" else 0.85 if s % 12 == 0 else 0.72), at,
                            (0.7 if kit == "chamber" else 1.0) * gain)
            elif p == 38:
                x = brush(0.6, seed) if kit == "chamber" else R.snare(0.6, seed)
                self.tl.add(x, at, 0.45 * gain, 0.05)
            elif p == 39:
                self.tl.add(clap(0.6, seed), at, 0.4 * gain, -0.1)
            elif p in (42, 44):
                x = brush(0.25, seed) if kit == "chamber" else hat(0.22 if p == 42 else 0.14, seed)
                self.tl.add(x, at, 0.35 * gain, -0.3)
            elif p == 46:
                x = R.woodblock(s % 3 == 0, 0.35, seed) if kit == "chamber" else R.open_hat(0.25, seed)
                self.tl.add(x, at, 0.28 * gain, 0.3 if kit == "chamber" else -0.3)
            elif p in (49, 57):
                self.tl.add(stereo(R.crash(0.45, seed)), at, (0.12 if kit == "chamber" else 0.2) * gain)
            elif p == 54:  # his tambourine is Kuni's collar bell
                self.tl.add(js[i % 4], at, 0.16 * gain)

    def voice(self, src, dst, nbars, top, pad_gain=0.0):
        """His sung chords: the top note goes to `top(slot, midi, slots)`, the rest to a string pad."""
        for s, ms, ln in chords_of(take(VOICE, src, nbars)):
            top(s, ms[-1], ln)
            if pad_gain:
                for j, m in enumerate(ms[:-1] if len(ms) > 1 else ms):
                    self.tl.add(strings(m, ln * self.slot, 0.5, attack=0.2, rel=0.5, voices=2, seed=j),
                                self.t(dst, s), pad_gain, -0.3 + 0.3 * j)

    def roll(self, bar, slots=6, gain=0.4):
        """Snare triplet roll into `bar`."""
        for k in range(slots):
            self.tl.add(R.snare(0.25 + 0.06 * k, 7000 + bar * 10 + k), self.t(bar, -slots + k), gain)

    def master(self, rev=1.5, wet=0.17, echo=0.1):
        music = circ_filter(self.tl.loop(), "highpass", 35, 2)
        if echo:
            music = music + echo * delay_echo(music, 0.75 * self.spb, feedback=0.3, taps=3, lp_hz=3500)
        music = reverb(music, reverb_ir(rev, damp_hz=5000, seed=74), wet=wet)
        return circ_filter(np.tanh(music * 1.2) / 1.2, "lowpass", 13000, 2)


# ================================================================== swagger (unused)
# Half time at 175 (clap on beat 3), 88 bars = 2:01. Trap-ish: 808 on his bass line, triplet hats with rolls, his
# sung section as the hook on a chip lead with e-piano chords; her theme as the verse; his guitars only in the drop;
# her collar bell on the backbeat. Good as a background, but not the mood of her cheeky scenes: kept, not used.
#   0-7   intro: his chords (bars 48-55) on e-piano, no drums, the bell
#   8-23  hook: his sung melody on the chip, his chords on e-piano, 808 on his E D C B / E D# C B
#   24-39 verse A: her theme A stretched on e-piano/bell over PROG_A in F# minor, flute doubles the second half
#   40-47 verse B: theme B first half stretched over PROG_B
#   48-63 drop: his B5/A5 stabs (16-19) and low gallop (64-75) on guitar + 808; chip plays her theme A swung
#   64-79 hook again, bell an octave up, collar bell on the backbeat
#   80-87 his breakdown hits (40-47) and her music-box answers, into the intro
def swagger():
    s = Song(175, 88, 1751)
    js = jingles(1751)
    ep = lambda m, d, v: epiano(m, d, v, bright=0.7)

    def hook(dst, lead_gain, bell_gain):
        def top(sl, m, ln):
            s.tl.add(chip_c(m + 12, round(ln * s.slot * 0.92, 3), 0.8), s.t(dst, sl) + s.h(), lead_gain, 0.05)
            if bell_gain:
                s.tl.add(bell_c(m + 24, round(min(ln * s.slot, 1.0), 3), 0.55), s.t(dst, sl) + 0.01, bell_gain,
                         -0.3)
        s.voice(48, dst, 16, top)
        for sl, ms, ln in chords_of(take(VOICE, 48, 16)):
            for j, m in enumerate(ms):
                s.tl.add(ep(m, ln * s.slot * 0.95, 0.5), s.t(dst, sl) + j * 0.012, 0.35, -0.4 + 0.3 * j)
        s.bass(48, dst, 16, gain=0.42, inst="808")

    def trap(b, heavy=False, roll=False):
        t0 = lambda sl: s.t(b, sl)
        for k in ((0, 7, 10) if b % 2 == 0 else (0, 5, 8)):
            s.tl.add(R.kick(0.85), t0(k), 0.7)
        s.tl.add(clap(0.6, b), t0(6) + s.h(0.002), 0.4, -0.05)
        s.tl.add(R.snare(0.5, b), t0(6), 0.25 if heavy else 0.15, 0.05)
        sub = 2 if roll and b % 4 == 3 else 1
        for k in range(12 * sub):
            sl = k / sub
            if sub == 2 and sl < 6 and k % 2:
                continue
            s.tl.add(hat(0.2 if sl % 3 == 0 else 0.13, b * 30 + k), t0(sl) + s.h(0.002), 0.35, -0.3)
        if b % 4 == 3:
            s.tl.add(R.open_hat(0.25, b), t0(10), 0.25, 0.3)
        s.tl.add(js[b % 4], t0(6) + s.h(0.002), 0.045)  # quiet: on every bar it gets into the ears

    # intro
    for sl, ms, ln in chords_of(take(VOICE, 48, 8)):
        for j, m in enumerate(ms):
            s.tl.add(ep(m, ln * s.slot * 0.95, 0.45), s.t(0, sl) + j * 0.012, 0.35, -0.4 + 0.3 * j)
        s.tl.add(bell_c(ms[-1] + 24, round(min(ln * s.slot, 1.0), 3), 0.5), s.t(0, sl) + 0.01, 0.12, 0.3)
    for b in range(4, 8):
        for k in range(0, 12, 3):
            s.tl.add(hat(0.15, b * 12 + k), s.t(b, k), 0.3, -0.3)
    hook(8, 0.22 * 1.4, 0.0)
    # verse A/B: her theme
    for b in range(24, 48):
        trap(b, roll=True)
    va = theme(R.MEL_A, TR, k=2, swung=False)
    vb = theme(R.MEL_B[:4], TR, k=2, swung=False)
    s.melody(va, 24, lambda m, d, v: epiano(m, d, v, bright=1.0), 0.55, 0.1)
    s.melody([[nt for nt in bar if nt[2] >= 1.5] for bar in va], 24,
             lambda m, d, v: bell_c(m + 12, round(min(d, 1.0), 3), round(v, 2)), 0.1, -0.3, vel=0.55)
    s.melody(va[8:], 32, lambda m, d, v: flute(m + 12, d, v, seed=9), 0.25, 0.25)
    s.melody(vb, 40, lambda m, d, v: flute(m + 12, d, v, seed=9), 0.36, 0.2)
    s.melody(vb, 40, lambda m, d, v: epiano(m, d, v, bright=1.0), 0.3, -0.1)
    for start, prog in ((24, R.PROG_A * 2), (40, R.PROG_B)):
        for bi, beat, seg, name in R.segments(prog):
            v, r = chord_tr(name)
            at = s.t(start + bi * 2, beat * 2 * 3)
            for j, m in enumerate(v):
                s.tl.add(ep(m, seg * 2 * s.spb * 0.95, 0.42), at + j * 0.014, 0.3, -0.4 + 0.25 * j)
            r = r if r >= 30 else r + 12
            s.tl.add(b808(r, round(seg * 2 * s.spb * 0.7, 3), 0.9), at, 0.42)
            if seg * 2 >= 4:
                s.tl.add(b808(r, round(0.6 * s.spb, 3), 0.8), at + 2.67 * s.spb, 0.3)
    # drop: his guitars. The stabs (bars 48-51) go with his own bass and drums: the 808 and the trap kicks against
    # their syncopation were a mess
    s.guitar(16, 48, 4, gain=0.16)
    s.bass(16, 48, 4, gain=0.38)
    s.drums(16, 48, 4, gain=0.8, jingle_set=js)
    s.guitar(64, 52, 12, gain=0.16)
    s.bass(64, 52, 12, gain=0.4, inst="808")
    for b in range(52, 64):
        trap(b, heavy=True, roll=True)
    s.melody(theme(R.MEL_A, TR + 12), 52, chip_c, 0.32, 0.2)
    s.melody(theme(R.MEL_A, TR + 24), 56, lambda m, d, v: bell_c(m, round(min(d, 0.5), 3), round(v, 2)), 0.08, -0.3)
    for b in range(8, 24):
        trap(b, roll=b >= 16)
    hook(64, 0.22 * 1.4, 0.09)
    for b in range(64, 80):
        trap(b, heavy=True, roll=True)
    # outro: his breakdown hits, her answers
    s.guitar(40, 80, 8, gain=0.12)
    s.bass(40, 80, 8, gain=0.4, inst="808")
    s.drums(40, 80, 8, jingle_set=js)
    mb = lambda m, d, v: bell_c(m, round(min(d, 0.8), 3), round(v, 2))
    for k, b in enumerate((81, 83, 85, 87)):
        s.melody([LICKS[k]], b, mb, 0.3, 0.15 * (-1) ** k, vel=0.7)
        s.melody([LICKS[k]], b, lambda m, d, v: ep(m, d, v), 0.2, -0.2, vel=0.6)
    for b in (8, 24, 48, 64, 80):
        s.tl.add(stereo(R.crash(0.45, b)), s.t(b), 0.18)
    return s.master(rev=1.3, wet=0.14, echo=0.12)


# ================================================================== assertive: her cheeky scenes
# 175 bpm, 96 bars = 2:12. His band as he hummed it (his chug intro and his outro left out), the mansion's
# harpsichord as her voice on his line, and Kuni herself on a bus of her own that walks around the listener's head.
# His bars -> ours:
#   0-15  lead-in = his 16-31: B5/A5 stabs, her theme A on the chip, his F5/C5/F# gallop
#   16-19 his 32-35 stabs, theme A second half
#   20-23 his 36-39 F5 gallop (his fill at 35-36 cleaned: ASSERTIVE_DRUMS)
#   24-31 his breakdown 40-47: he hits, her music box answers in the empty bars, his tambourine = her collar bell
#   32-47 his gallop 48-63 (tritones, lows): his sung line on her harpsichord in octaves, pizzicato on the attack,
#         triplet arpeggios of his chord filling each held note, a quiet violin holding it; timpani under his stabs
#   48-63 his low F# gallop 64-79: her theme stretched on the lead guitar, bells on its long notes; his snare put
#         back under his 69-72 (they had only kick and hat: no push)
#   64-71 breakdown again, the answers climbing (ASSERTIVE_WINK)
#   72-87 his gallop 48-63 again, whole
#   88-95 ending: his low gallop 64-67 with her theme's opening on her own instrument, then stop hits on F#5 at each
#         downbeat (a pedal hat keeps the grid), she answers a step higher each time and lands on the high F# with
#         the last hit, his triplet snare climbs back into the lead-in. Up, on the tonic, in front of you
# Width: every guitar hit is two takes (+-6 cents), hard left/right, each with its own 3-14 ms delay (one fixed late
# side made the band lean to the other: precedence effect); the lead is two takes at 80 %.
# Her bus (her instrument, answers, chip theme, the bells, the collar) is mono-summed and moved around the head with
# interaural delay (0.7 ms), level and head shadow on the far ear, darker behind, almost dry (close: "her whiskers
# tickle the ears"). ASSERTIVE_PATH: clockwise, whole turns per section, so the loop seam does not jump.
ASSERTIVE_BARS = 96
ASSERTIVE_PLAN = [(16, 0, 16), (32, 16, 4), (36, 20, 4), (40, 24, 8), (48, 32, 16), (64, 48, 16), (40, 64, 8),
                  (48, 72, 16), (64, 88, 4)]  # (his bar, our bar, bars)
# (first bar, turns until the next entry): her four breakdown answers come from four sides, the ending's answers
# from the right, from behind, from the left, and the landing is in front
ASSERTIVE_PATH = [(0, 2), (16, 1), (24, 1), (32, 4), (48, 2), (64, 1), (72, 4), (88, 1), (92, 1), (95, 0), (96, 0)]
# his fill at 35:11-36:5 had snares on three neighbouring triplets and another on 36:3, a flam that reads as a
# stumble: bar 36 goes like his bar 37 instead (crash + kick on the one, kicks under the chug, snare on beat 3)
ASSERTIVE_DRUMS = [nt for nt in DRUMS if not (35 * 12 + 11 <= nt[0] < 36 * 12 + 6 and nt[1] == 38)] + [(36 * 12, 49, 1)]
ASSERTIVE_WINK = theme([R.MEL_A[0], R.MEL_A[4], R.MEL_A[0],
                        [(0, 76, .5), (.5, 79, .5), (1, 81, .5), (1.5, 84, .5), (2, 88, 2)]], TR + 12)
ASSERTIVE_ANSWERS = [  # the ending: (bar, [(slot, midi, slots)])
    (92, [(4, 73, 1), (5, 76, 1), (6, 78, 4)]),
    (93, [(4, 76, 1), (5, 78, 1), (6, 81, 4)]),
    (94, [(4, 78, 1), (5, 81, 1), (6, 85, 2), (8, 88, 2), (10, 85, 1), (11, 88, 1)]),
    (95, [(0, 90, 9)]),
]


@functools.lru_cache(maxsize=None)
def guitar_take(root, dur, muted, vel, intervals, cents, phase):
    """One take of a power chord (as guitar_chord), detuned by `cents`, its partials at their own phases."""
    sr2 = 2 * SR
    ring = dur + (0.05 if muted else 0.25)
    n = int(ring * sr2)
    t = np.arange(n) / sr2
    x = np.zeros(n)
    for k, iv in enumerate(intervals):
        f = midi_hz(root + iv) * (1 + 0.0015 * (k - 1)) * 2 ** (cents / 1200)
        ph = TAU * f * t + k * 1.3 + phase
        x += sum(np.sin(j * ph + 0.4 * j * phase) / j for j in range(1, int(6000 / f) + 1))
    if intervals != (0, 7, 12):
        x *= 1.5 / len(intervals)
    env = np.exp(-t / (0.09 if muted else 0.9)) * (1 - np.exp(-t / 0.0015))
    env *= np.clip((ring - t) / 0.03, 0, 1)
    x *= env * vel
    if muted:
        x = R.signal.sosfilt(R.signal.butter(2, 900, "lowpass", fs=sr2, output="sos"), x)
    y = R.amp_cab(x, 5.0, sr2, tone_hz=3800.0)
    return fade(y / 1.6, 0.001, 0.01)


def wide_chord(tl, rng, root, dur, muted, vel, at, gain, intervals=(0, 7, 12)):
    """Double-tracked: two takes hard left and right, each with its own small delay."""
    left = guitar_take(root, dur, muted, vel, intervals, -6.0, 0.0)
    right = guitar_take(root, dur, muted, round(vel * 0.97, 3), intervals, 6.0, 1.7)
    tl.add(np.stack([left, 0.1 * left], axis=1), at + rng.uniform(0.003, 0.014), gain * 1.25)
    tl.add(np.stack([0.1 * right, right], axis=1), at + rng.uniform(0.003, 0.014), gain * 1.25)


class WideSong(Song):
    """Song with double-tracked rhythm and lead guitars."""

    def guitar(self, src, dst, nbars, gain=0.13, fifths=True):
        for s, ms, ln in chords_of(take(GTR, src, nbars)):
            root = ms[0] + (12 if ms[0] < 36 else 0)
            muted = ln == 1 and root <= 42
            iv = (0, 7, 12) if fifths or len(ms) > 1 else (0, 12)
            wide_chord(self.tl, self.rng, root, round(ln * self.slot * (0.9 if muted else 0.85), 3), muted,
                       0.95 if s % 3 == 0 else 0.85, self.t(dst, s) + self.h(), gain, iv)

    def lead(self, bars, at_bar, gain, seed=0, vel=0.8):
        notes = [(bi * 4 + b, m, ln, "b" if ln >= 2.5 else "") for bi, bar in enumerate(bars) for b, m, ln in bar]
        phrases, starts = R.solo_phrases(notes, self.spb)
        for ph, b0 in zip(phrases, starts):
            at = self.t(at_bar) + b0 * self.spb + self.h()
            rng = np.random.default_rng(seed + int(b0 * 4))
            takes = []
            for cents in (-0.06, 0.06):  # each take a hair off in pitch, each note a few ms off
                p = [(max(0.0, s + (rng.normal(0, 0.007) if i else 0)), m + cents, d, art)
                     for i, (s, m, d, art) in enumerate(ph)]
                takes.append(R.lead_guitar(p, vel).mean(1))
            n = max(map(len, takes))
            l, r = (np.pad(x, (0, n - len(x))) for x in takes)
            dl, dr = n_samples(rng.uniform(0.002, 0.01)), n_samples(rng.uniform(0.002, 0.01))
            l = np.concatenate([np.zeros(dl), l, np.zeros(dr)])
            r = np.concatenate([np.zeros(dr), r, np.zeros(dl)])
            w = 0.8
            self.tl.add(np.stack([l * (1 + w) / 2 + r * (1 - w) / 2, r * (1 + w) / 2 + l * (1 - w) / 2], axis=1)
                        * 1.15, at, gain)

    def stop_hit(self, at, dur, vel, gain):
        """A tutti F#5 hit, double-tracked."""
        wide_chord(self.tl, self.rng, 42, round(dur, 3), False, vel, at, gain)


def azimuth(n, bar_len, path):
    """Clockwise angle (0 in front, pi/2 to the right) for every sample, from [(bar, turns until the next)]."""
    bars, turns, acc = [], [], 0.0
    for b, k in path:
        bars.append(b)
        turns.append(acc)
        acc += k
    assert float(acc).is_integer(), "whole turns only, or the loop seam jumps"
    return TAU * np.interp(np.arange(n) / SR / bar_len, bars, turns)


def orbit(bus, theta, itd=0.0007):
    """Place the mono-summed bus at azimuth theta(t) around a listener on headphones: interaural delay, level and
    head shadow on the far ear, darker behind the head. Circular (loop-safe)."""
    n = len(bus)
    m = bus.mean(1)
    shadow = circ_filter(m, "lowpass", 2200, 2)
    behind = np.clip(-np.cos(theta), 0, 1) * 0.5
    src = m * (1 - behind) + circ_filter(m, "lowpass", 5500, 2) * behind
    s = np.sin(theta)
    idx = np.arange(n, dtype=float)
    out = np.zeros((n, 2))
    for ch, side in ((0, -1), (1, 1)):  # left ear, right ear
        far, near = np.clip(-side * s, 0, 1), np.clip(side * s, 0, 1)
        x = np.interp(idx - far * itd * SR, idx, src * (1 - 0.75 * far) + shadow * 0.75 * far, period=n)
        out[:, ch] = x * (1 - 0.55 * far + 0.2 * near)
    return out


def his_line(src, nbars):
    """His sung top line [(slot, midi, slots, art)] ("g" a glance on his C and G naturals, the notes that rub
    against the F# gallop; "b" a scoop on the long ones) and his chords {slot: midis}."""
    notes, chords = [], {}
    for s, ms, ln in chords_of(take(VOICE, src, nbars)):
        notes.append((s, ms[-1], ln, "g" if ms[-1] % 12 in (0, 7) else "b" if ln >= 6 else ""))
        chords[s] = ms
    return notes, chords


def harpsichord_line(s, notes, chords, at_bar, octave=12):
    """Her mansion voice on his line: harpsichord in octaves, pizzicato on the attack, each held note filled with
    triplet arpeggios of his chord, a quiet violin holding the line."""
    for sl, m, ln, art in notes:
        at = s.t(at_bar, sl) + s.h()
        d = ln * s.slot
        m += octave
        s.tl.add(harp_c(m, round(min(d, 0.9), 3), 0.75), at, 0.45, 0.1)
        s.tl.add(harp_c(m - 12, round(min(d, 0.9), 3), 0.6), at, 0.24, -0.15)
        s.tl.add(pizz_c(m - 12, 0.7), at, 0.18, 0.2)
        arp = sorted({c + 12 for c in chords[sl]} | {m})
        arp = [a for a in arp if a <= m] or [m]
        for k in range(1, ln):
            a = arp[(len(arp) - 1 - k) % len(arp)] if k % 2 else arp[k % len(arp)]
            s.tl.add(harp_c(a, round(s.slot * 1.3, 3), 0.5), s.t(at_bar, sl + k) + s.h(0.002), 0.18,
                     0.35 * np.sin(k + sl))
    s.glide([(sl, m + octave, ln, "") for sl, m, ln, art in notes], at_bar, "violin", 0.28, vel=0.6, seed=at_bar + 3)


def harpsichord_note(s, m, at, d):
    s.tl.add(harp_c(m, round(min(d, 1.2), 3), 0.8), at, 0.45, 0.1)
    s.tl.add(harp_c(m - 12, round(min(d, 1.2), 3), 0.65), at, 0.26, -0.15)
    s.tl.add(violin(m, d, 0.7), at, 0.25, -0.1)


def assertive():
    """Her cheeky scenes: see the section comment above."""
    s = WideSong(175, ASSERTIVE_BARS, 4600)
    band = s.tl
    her = Timeline(ASSERTIVE_BARS * 4 * s.spb)
    js = jingles(4600)
    silent = [np.zeros((1, 2))] * 4
    # ---- the band
    for src, dst, n in ASSERTIVE_PLAN:
        s.guitar(src, dst, n, gain=0.18)
        s.bass(src, dst, n, gain=0.38)
        s.drums(src, dst, n, gain=0.8, jingle_set=silent, track=ASSERTIVE_DRUMS)
        for i, (sl, p, ln) in enumerate(take(ASSERTIVE_DRUMS, src, n)):  # his tambourine: her collar, on her bus
            if p == 54:
                her.add(js[i % 4], s.t(dst, sl) + s.h(0.002), 0.16 * 0.8)
        for sl, ms, ln in chords_of(take(GTR, src, n)):  # timpani under his held stabs
            if ln >= 3:
                root = ms[0] + (12 if ms[0] < 36 else 0)
                band.add(timpani(root - 12 if root >= 40 else root, 0.7), s.t(dst, sl), 0.35)
    for b in range(53, 57):  # his snare back under his 69-72, on 1 and 3 like the bars around them
        for sl in (0, 6):
            band.add(R.snare(0.6, 5300 + b * 12 + sl), s.t(b, sl) + s.h(0.002), 0.36, 0.05)
    tlong = theme(R.MEL_A, TR, k=2, swung=False)
    for at in (32, 72):
        s.voice(48, at, 16, lambda *a: None, pad_gain=0.05)
    s.lead(tlong, 48, 0.3, seed=640)
    s.roll(64)
    for b in range(92, 96):  # the ending's stop hits, a pedal hat keeping the grid
        s.stop_hit(s.t(b), 3 * s.slot * 0.9, 0.95, 0.2)
        band.add(soft_bass(30, 3 * s.slot, 0.9), s.t(b), 0.45)
        band.add(R.kick(0.9), s.t(b), 0.8)
        band.add(stereo(R.crash(0.5 if b in (92, 95) else 0.3, b)), s.t(b), 0.18 if b in (92, 95) else 0.1)
        for beat in range(1, 4):
            band.add(hat(0.14, b * 4 + beat), s.t(b, beat * 3), 0.35, -0.3)
    s.stop_hit(s.t(95), 6 * s.slot * 0.9, 1.0, 0.12)  # the last hit rings
    for k in range(6):  # his triplet snare climbs back into the lead-in
        band.add(R.snare(0.3 + 0.08 * k, 9500 + k), s.t(95, 6 + k) + s.h(0.002), 0.42)
    for sl in (6, 9):
        band.add(R.kick(0.8), s.t(95, sl), 0.8)
    # ---- Kuni, on her own bus
    s.tl = her
    ta = theme(R.MEL_A, TR + 12)
    bell_up = lambda m, d, v: bell_c(m + 12, round(min(d, 0.5), 3), round(v, 2))
    for half, at in ((ta[:4], 0), (ta[4:], 16)):  # the lead-in: her theme on the chip, the collar on 2 and 4
        s.melody(half, at, chip_c, 0.34, 0.1)
        s.melody(half, at, bell_up, 0.08, -0.3)
        for k in range(4):
            for beat in (1, 3):
                s.tl.add(js[(at + k + beat) % 4], s.t(at + k, beat * 3) + s.h(0.002), 0.05)
    mb = lambda m, d, v: bell_c(m, round(min(d, 0.8), 3), round(v, 2))
    for licks, bars in ((LICKS, (25, 27, 29, 31)), (ASSERTIVE_WINK, (65, 67, 69, 71))):  # her answers
        for k, b in enumerate(bars):
            s.melody([licks[k]], b, mb, 0.3, 0.0, vel=0.7)
            s.melody([licks[k]], b, chip_c, 0.08, 0.0, vel=0.6)
    notes, chords = his_line(48, 16)
    for at in (32, 72):
        harpsichord_line(s, notes, chords, at)
    s.melody([[nt for nt in bar if nt[2] >= 2] for bar in tlong], 48,
             lambda m, d, v: bell_c(m + 12, round(min(d, 1.0), 3), round(v, 2)), 0.14, 0.0, vel=0.6)
    for bi, bar in enumerate(tlong[:4]):  # the ending: her theme's opening on her own instrument
        for b, m, ln in bar:
            harpsichord_note(s, m + 12, s.t(88 + bi) + b * s.spb + s.h(), ln * s.spb)
    for b, ln in ASSERTIVE_ANSWERS:
        for sl, m, d in ln:
            harpsichord_note(s, m, s.t(b, sl) + s.h(), d * s.slot)
        s.tl.add(js[b % 4], s.t(b, 4), 0.05)
    s.tl.add(bell_c(102, 1.2, 0.6), s.t(95) + 0.01, 0.12)
    s.tl.add(js[0], s.t(95), 0.1)
    s.tl = band
    # ---- mix: the band in its room, her close and moving
    music = circ_filter(band.loop(), "highpass", 35, 2)
    music = music + 0.1 * delay_echo(music, 0.75 * s.spb, feedback=0.3, taps=3, lp_hz=3500)
    music = reverb(music, reverb_ir(1.5, damp_hz=5000, seed=74), wet=0.17)
    h = her.loop()
    h = orbit(h, azimuth(len(h), 4 * s.spb, ASSERTIVE_PATH)) * 1.25
    h = reverb(h, reverb_ir(0.8, damp_hz=6000, seed=75), wet=0.06)
    return circ_filter(np.tanh((music + h) * 1.2) / 1.2, "lowpass", 13000, 2)
