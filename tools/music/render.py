#!/usr/bin/env python3
"""Render all prologue music, ambiences and SFX into data/music and data/sound.

Usage (from repo root):
    ~/.local/bin/uv run --with numpy --with scipy tools/music/render.py [name ...]
Without arguments renders everything. Names are the keys of LOOPS and SFX at the bottom
(see tools/music/README.md and docs/AUDIO.md for what each one is for).
"""
from __future__ import annotations

import functools
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import *  # noqa: E402,F403

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MUSIC = os.path.join(ROOT, "data", "music")
SOUND = os.path.join(ROOT, "data", "sound")

# ============================================================== harmony / melody
# Voicings are rootless-ish EP chords (MIDI); bass root separate.
CH = {
    "Fmaj9": ([53, 57, 64, 67], 41),
    "Em7": ([52, 59, 62, 67], 40),
    "Am9": ([57, 60, 67, 71], 45),
    "Dm9": ([53, 57, 60, 64], 38),
    "G9sus": ([53, 57, 60, 62], 43),
    "Bbmaj9": ([50, 57, 60, 65], 46),
    "Am7": ([52, 55, 60, 64], 45),
    "Esus": ([52, 57, 59, 64], 40),
    "E7b9": ([56, 59, 62, 65], 40),
}
# per bar: list of (beat, chord)
PROG_A = [[(0, "Fmaj9")], [(0, "Em7")], [(0, "Am9")], [(0, "Dm9"), (2, "G9sus")]]
PROG_B = [[(0, "Bbmaj9")], [(0, "Am7")], [(0, "Dm9")], [(0, "Esus"), (2, "E7b9")]]

# Kuni's theme. per bar: list of (beat, midi, beats)
MEL_A = [
    [(1, 76, .5), (1.5, 79, .5), (2, 81, 1.5), (3.5, 79, .5)],
    [(0, 76, 2), (2, 74, .5), (2.5, 76, .5), (3, 71, 1)],
    [(0, 72, 1.5), (1.5, 71, .5), (2, 72, .5), (2.5, 76, 1.5)],
    [(0, 74, 1.5), (1.5, 72, .5), (2, 71, 1), (3, 74, 1)],
    [(1, 76, .5), (1.5, 79, .5), (2, 84, 1.5), (3.5, 83, .5)],
    [(0, 81, 1), (1, 79, 1), (2, 76, 1.5), (3.5, 74, .5)],
    [(0, 76, 1), (1, 72, 1), (2, 71, .5), (2.5, 72, .5), (3, 69, 1)],
    [(0, 69, 2), (2, 71, 1), (3, 74, 1)],
]
MEL_B = [
    [(0, 77, 1.5), (1.5, 74, .5), (2, 81, 2)],
    [(0, 79, 1.5), (1.5, 76, .5), (2, 72, 2)],
    [(0, 77, 1), (1, 76, 1), (2, 74, 1), (3, 69, 1)],
    [(0, 69, 2), (2, 68, 2)],
    [(0, 74, .5), (.5, 77, .5), (1, 81, 1), (2, 84, 1.5), (3.5, 81, .5)],
    [(0, 79, 2), (2, 76, 1), (3, 79, 1)],
    [(0, 77, 1.5), (1.5, 76, .5), (2, 74, 1), (3, 72, 1)],
    [(0, 71, 2), (2, 68, 1), (3, 71, 1)],
]
MEL_OUTRO = [
    [(2, 76, 2)],
    [(1, 74, 2), (3, 71, 1)],
    [(0, 72, 3)],
    [],
]


def human(rng, amount=0.012):
    return rng.normal(0, amount)


def play_chords(tl, rng, bars, start_bar, bpm, vel=0.42, rhythm="lofi", pad_gain=0.0,
                bass_gain=0.0, transpose=0):
    spb = 60 / bpm
    for bi, bar in enumerate(bars):
        t0 = (start_bar + bi) * 4 * spb
        for si, (beat, name) in enumerate(bar):
            seg_end = bar[si + 1][0] if si + 1 < len(bar) else 4
            seg = seg_end - beat
            notes, root = CH[name]
            notes = [n + transpose for n in notes]
            root += transpose
            at = t0 + beat * spb
            hits = [(0, seg, vel)]
            if rhythm == "lofi" and seg >= 4:
                hits = [(0, 2.5, vel), (2.5, 1.5, vel * 0.7)]
            for off, ln, v in hits:
                for k, m in enumerate(notes):  # gentle strum
                    tl.add(epiano(m, ln * spb * 0.95, v * rng.uniform(0.9, 1.05), bright=0.8),
                           at + off * spb + k * 0.014 + human(rng, 0.006), 0.5,
                           (k - 1.5) * 0.25)
            if pad_gain:
                for m in notes:
                    tl.add(pad(m, seg * spb, 0.5, attack=0.8, rel=1.5, seed=int(m)), at, pad_gain)
            if bass_gain:
                b = [(0, min(seg, 2.4) * 0.9)]
                if seg >= 4:
                    b.append((2.5, 1.3))
                for off, ln in b:
                    tl.add(soft_bass(root, ln * spb, 0.6), at + off * spb + human(rng, 0.005),
                           bass_gain)


def play_melody(tl, rng, bars, start_bar, bpm, inst, gain=0.6, transpose=0, vel=0.72):
    spb = 60 / bpm
    for bi, bar in enumerate(bars):
        t0 = (start_bar + bi) * 4 * spb
        for beat, m, ln in bar:
            v = vel * rng.uniform(0.88, 1.0) * (1.08 if beat == 0 else 1.0)
            tl.add(inst(m + transpose, ln * spb, v), t0 + beat * spb + human(rng), gain, 0.05)


# ============================================================== music

def night_code():
    bpm = 70
    spb = 60 / bpm
    bars = 24
    rng = np.random.default_rng(3)
    tl = Timeline(bars * 4 * spb)
    prog = PROG_A + PROG_A * 2 + PROG_B * 2 + PROG_A  # intro, A, B, outro
    play_chords(tl, rng, prog, 0, bpm, vel=0.40, pad_gain=0.05, bass_gain=0.0)
    # bass only under the melody sections
    bass_tl = Timeline(bars * 4 * spb)
    play_chords(bass_tl, rng, prog[4:20], 4, bpm, vel=0.0, rhythm="block", bass_gain=0.32)
    lead = Timeline(bars * 4 * spb)
    play_melody(lead, rng, MEL_A + MEL_B + MEL_OUTRO, 4, bpm,
                lambda m, d, v: epiano(m, d, v, bright=1.1), gain=0.7)
    lead_buf = lead.loop()
    lead_buf = lead_buf + delay_echo(lead_buf, spb * 0.75, 0.3, 3) * 0.5
    # soft drums in bars 5-20
    drums = Timeline(bars * 4 * spb)
    for b in range(4, 20):
        t0 = b * 4 * spb
        drums.add(kick(0.55), t0 + human(rng, 0.004))
        drums.add(kick(0.4), t0 + 2.5 * spb + human(rng, 0.004))
        drums.add(brush(0.18, seed=b), t0 + 1 * spb, pan_pos=0.1)
        drums.add(brush(0.2, seed=b + 99), t0 + 3 * spb, pan_pos=0.1)
        for e in range(8):
            sw = 0.09 if e % 2 else 0.0
            drums.add(hat(0.06 if e % 2 else 0.09, seed=b * 8 + e),
                      t0 + (e * 0.5 + sw) * spb + human(rng, 0.004), pan_pos=-0.3)
    drum_buf = circ_filter(drums.loop(), "lowpass", 6000, 1)
    music = tl.loop() + lead_buf + bass_tl.loop() * 1.0 + drum_buf * 0.8
    music = circ_filter(music, "highpass", 35, 2)
    music = reverb(music, reverb_ir(2.4, damp_hz=3500), wet=0.28)
    # lo-fi: tape warmth + darker top + vinyl bed with crackles
    music = np.tanh(music * 1.6) / 1.6
    music = circ_filter(music, "lowpass", 9000, 2)
    n = len(music)
    vinyl = circ_filter(colored_noise(n, "pink", seed=11, channels=2, correlation=0.6),
                        "bandpass", (300, 7000), 1) * 0.004
    crack = np.zeros((n, 2))
    pos = rng.integers(0, n, size=int(n / SR * 3))
    crack[pos, 0] = rng.uniform(-1, 1, len(pos)) * 0.08
    crack[pos, 1] = crack[pos, 0] * rng.uniform(0.5, 1, len(pos))
    crack = circ_filter(crack, "bandpass", (1000, 6000), 2)
    return music + vinyl + crack


def menu():
    bpm = 72
    spb = 60 / bpm
    bars = 16
    tr = 2  # up a whole tone: warmer, brighter
    rng = np.random.default_rng(5)
    tl = Timeline(bars * 4 * spb)
    prog = PROG_A + PROG_A * 2 + PROG_B
    # arpeggiated EP + pad bed + bass
    for bi, bar in enumerate(prog):
        t0 = bi * 4 * spb
        for si, (beat, name) in enumerate(bar):
            seg_end = bar[si + 1][0] if si + 1 < len(bar) else 4
            notes = [m + tr for m in CH[name][0]]
            pattern = [0, 1, 2, 3, 2, 1, 2, 3]
            for k in range(int((seg_end - beat) * 2)):
                m = notes[pattern[k % 8]] + (12 if k % 8 == 3 else 0)
                tl.add(epiano(m, 1.4 * spb, 0.36 * rng.uniform(0.9, 1.05), bright=0.7),
                       t0 + (beat + k * 0.5) * spb + human(rng, 0.006), 0.45,
                       0.4 * np.sin(k * 0.8))
            for m in notes:
                tl.add(pad(m, (seg_end - beat) * spb, 0.5, attack=1.0, rel=1.8, seed=m), t0 + beat * spb, 0.06)
            tl.add(soft_bass(CH[name][1] + tr, (seg_end - beat) * spb * 0.9, 0.55), t0 + beat * spb, 0.28)
    # melody variation of Kuni's theme: anticipations, higher climax, new cadences
    var_a = [
        [(0.5, 76, .5), (1, 79, .5), (1.5, 81, 2), (3.5, 79, .5)],
        [(0, 76, 1.5), (1.5, 74, .5), (2, 76, 1), (3, 79, 1)],
        [(0, 72, 1), (1, 71, .5), (1.5, 72, .5), (2, 76, 2)],
        [(0, 74, 2), (2, 71, 1), (3, 67, 1)],
        [(0.5, 76, .5), (1, 79, .5), (1.5, 86, 1.5), (3, 84, .5), (3.5, 83, .5)],
        [(0, 81, 1.5), (1.5, 79, .5), (2, 76, 2)],
        [(0, 76, 1), (1, 72, 1), (2, 71, 1), (3, 72, 1)],
        [(0, 69, 3), (3, 71, 1)],
    ]
    var_b = [
        [(0, 77, 1.5), (1.5, 81, .5), (2, 84, 2)],
        [(0, 83, 1), (1, 79, 1), (2, 76, 2)],
        [(0, 77, 1), (1, 76, 1), (2, 74, 1), (3, 72, 1)],
        [(0, 71, 2), (2, 68, 2)],
    ]
    lead = Timeline(bars * 4 * spb)
    play_melody(lead, rng, var_a + var_b, 4, bpm, bell, gain=0.55, transpose=tr, vel=0.7)
    play_melody(lead, rng, var_a + var_b, 4, bpm, lambda m, d, v: epiano(m - 12, d, v * 0.8),
                gain=0.3, transpose=tr)
    music = tl.loop() + lead.loop()
    music = circ_filter(music, "highpass", 35, 2)
    music = reverb(music, reverb_ir(3.0, damp_hz=4500, seed=3), wet=0.35)
    music = np.tanh(music * 1.3) / 1.3
    return circ_filter(music, "lowpass", 11000, 2)


# ============================================================== ambiences

def fan_layer(n, seed=21, loop_len=None):
    """PC fans: broadband whoosh + two blade tones beating against each other.
    Tone frequencies are chosen so every component is periodic over n samples."""
    sec = n / SR
    t = t_axis(n)
    whoosh = colored_noise(n, lambda f: 1 / np.sqrt(np.maximum(f, 20)) *
                           butter_mag(f, "bandpass", (60, 1800), 2), seed=seed,
                           channels=2, correlation=0.7)
    # slow drowsy swell (integer cycles)
    swell = 1 + 0.12 * periodic_lfo(n, 2) + 0.06 * periodic_lfo(n, 5, 1.3)
    whoosh *= swell[:, None]
    tones = np.zeros(n)
    for f0, amp, wob_c, wob_depth, ph in ((140.0, 1.0, 1, 0.9, 0.0), (163.2, 0.6, 3, 0.6, 2.0)):
        f0 = round(f0 * sec) / sec  # integer cycles over the loop
        for h, ha in ((1, 1.0), (2, 0.35), (3, 0.12)):
            # FM wobble of ±wob_depth Hz with an integer number of cycles per loop
            phase = TAU * f0 * h * t + h * wob_depth / (wob_c / sec) * \
                np.sin(TAU * wob_c * t / sec + ph)
            tones += amp * ha * np.sin(phase)
    tones *= 1 + 0.25 * periodic_lfo(n, 3, 0.5)
    tones /= rms(tones)
    hum = pan(tones, -0.1) * 0.18
    return whoosh * 0.9 + hum


def fans():
    n = n_samples(24.0)
    return fan_layer(n)


def rain_layer(n, seed=31, thunder_at: float | None = 13.0, loop=True):
    rng = np.random.default_rng(seed)
    sec = n / SR
    # steady wide rain hiss
    hiss = colored_noise(n, lambda f: butter_mag(f, "bandpass", (500, 9000), 2) /
                         np.maximum(f, 50) ** 0.25, seed=seed, channels=2, correlation=0.15)
    # heavy roar on the roof / walls
    roar = colored_noise(n, lambda f: butter_mag(f, "bandpass", (60, 600), 2) /
                         np.maximum(f, 30) ** 0.5, seed=seed + 1, channels=2, correlation=0.5)
    gust = 1 + 0.25 * smooth_random(n, 6, seed=seed + 2) + 0.1 * periodic_lfo(n, 3)
    # gutter/stream: band-limited, gently fluctuating
    stream = colored_noise(n, lambda f: butter_mag(f, "bandpass", (250, 1200), 3),
                           seed=seed + 3, channels=2, correlation=0.3)
    stream *= (0.6 + 0.4 * smooth_random(n, 30, seed=seed + 4))[:, None]
    base = hiss * 0.55 * gust[:, None] + roar * 0.6 * gust[:, None] + stream * 0.18
    tl = Timeline(sec, tail=10)
    # dense tiny droplets
    for _ in range(int(sec * 90)):
        f = rng.uniform(2500, 7000)
        d = n_samples(rng.uniform(0.004, 0.015))
        tt = t_axis(d)
        drop = np.sin(TAU * f * tt * (1 + 0.6 * tt / tt[-1])) * np.exp(-tt / (tt[-1] / 4))
        tl.add(drop, rng.uniform(0, sec), rng.uniform(0.02, 0.07), rng.uniform(-0.9, 0.9))
    # heavier drips on windowsill / tin (closer, woody "tok")
    t = 0.0
    while t < sec:
        t += rng.exponential(0.45)
        d = n_samples(0.06)
        tt = t_axis(d)
        f = rng.uniform(700, 1600)
        tok = np.sin(TAU * f * tt) * np.exp(-tt / 0.012) + \
            0.3 * noise(d, rng.integers(1 << 30)) * np.exp(-tt / 0.003)
        tl.add(tok, t % sec, rng.uniform(0.05, 0.14), rng.uniform(-0.6, 0.6))
    drops = tl.loop() if loop else tl.buf[:n]
    out = base + circ_filter(drops, "highpass", 300, 1)
    if thunder_at is not None:
        m = n_samples(9.0)
        tt = t_axis(m)
        rum = colored_noise(m, lambda f: butter_mag(f, "bandpass", (25, 140), 2) /
                            np.maximum(f, 20), seed=seed + 5, channels=2, correlation=0.6)
        env = (1 - np.exp(-tt / 0.7)) * np.exp(-tt / 2.6)
        env *= 0.7 + 0.3 * (1 + np.sin(TAU * tt * 0.9 + 1)) / 2 + 0.2 * np.exp(-((tt - 1.8) / 0.4) ** 2)
        rum = rum * env[:, None] * 1.6
        th = Timeline(sec, tail=10)
        th.add(rum, thunder_at)
        out = out + (th.loop() if loop else th.buf[:n])
    return out


def rain():
    n = n_samples(40.0)
    return rain_layer(n)


# ============================================================== SFX

def key_press(rng, firm=1.0, kind="key"):
    """One keyboard keystroke: top click + plastic body + low thock + release click."""
    n = n_samples(0.18)
    t = t_axis(n)
    pitch = rng.uniform(0.85, 1.2) * (0.8 if kind == "enter" else 1.0)
    click = sos_filter(noise(n, rng.integers(1 << 30)), "highpass", 3500, 2) * np.exp(-t / 0.0015)
    body = sos_filter(noise(n, rng.integers(1 << 30)), "bandpass",
                      (1200 * pitch, 3500 * pitch), 2) * np.exp(-t / 0.012)
    thock = np.sin(TAU * 260 * pitch * t * (1 - 0.3 * t)) * np.exp(-t / 0.02) * (1 - np.exp(-t / 0.001))
    x = click * 0.6 + body * 1.3 + thock * 0.5 * firm
    # release (key coming back up)
    rel_at = n_samples(rng.uniform(0.05, 0.09))
    m = n - rel_at
    tr = t_axis(m)
    rel = sos_filter(noise(m, rng.integers(1 << 30)), "bandpass", (2000, 6000), 2) * np.exp(-tr / 0.004)
    x[rel_at:] += rel * 0.35
    if kind == "enter":  # stabilizer bar rattle
        k = n_samples(0.008)
        x[k:] += 0.5 * x[:-k] * np.exp(-t_axis(n - k) / 0.03)
    return x * firm


def room(x, t60=0.25, wet=0.18):
    return reverb(x, reverb_ir(t60, predelay=0.004, damp_hz=5000, seed=9), wet, loop=False)


def keys():
    rng = np.random.default_rng(41)
    tl = Timeline(1.3, tail=0.5)
    t = 0.02
    while t < 1.12:
        tl.add(key_press(rng, rng.uniform(0.6, 1.0)), t, 1.0, rng.uniform(-0.35, 0.35))
        gap = rng.choice([rng.uniform(0.05, 0.11), rng.uniform(0.12, 0.2), rng.uniform(0.22, 0.3)],
                         p=[0.55, 0.35, 0.10])
        t += gap
    return fade(room(tl.oneshot()), 0.001, 0.05)[: n_samples(1.25)]


def backspace():
    rng = np.random.default_rng(42)
    tl = Timeline(0.85, tail=0.5)
    base = np.random.default_rng(7)
    for i in range(7):
        k = key_press(np.random.default_rng(1000), 0.85)  # same key each time
        tl.add(k * rng.uniform(0.85, 1.0), 0.02 + i * 0.105 + rng.normal(0, 0.006), 1.0, 0.3)
    del base
    return fade(room(tl.oneshot()), 0.001, 0.05)[: n_samples(0.85)]


def enter():
    rng = np.random.default_rng(43)
    tl = Timeline(0.3, tail=0.3)
    tl.add(key_press(rng, 1.4, "enter"), 0.01, 1.0, 0.25)
    return fade(room(tl.oneshot(), 0.3, 0.22), 0.001, 0.05)[: n_samples(0.32)]


def fans_to_rain():
    dur = 6.0
    n = n_samples(dur)
    t = t_axis(n) / dur
    fan = fan_layer(n, seed=51)
    fan_dark = circ_filter(fan, "lowpass", 250, 2)
    morph = np.clip(t / 0.6, 0, 1)[:, None]  # fan gets duller ...
    fan_m = fan * (1 - morph) + fan_dark * morph
    rainx = rain_layer(n, seed=52, thunder_at=None, loop=False)
    rain_dark = circ_filter(rainx, "lowpass", 600, 2)
    open_ = np.clip((t - 0.3) / 0.6, 0, 1)[:, None]  # ... rain opens up
    rain_m = rain_dark * (1 - open_) + rainx * open_
    th = np.clip((t - 0.2) / 0.65, 0, 1) * np.pi / 2  # equal-power crossfade
    out = fan_m * 0.8 * np.cos(th)[:, None] + rain_m * 0.7 * np.sin(th)[:, None]
    return fade(out, 0.3, 0.6)


def rain_to_fans():
    """Chapter 8: the reverse of fans_to_rain. Rain closes up and dulls, PC fans come back."""
    dur = 6.0
    n = n_samples(dur)
    t = 1 - t_axis(n) / dur  # same curves as fans_to_rain, run backwards
    fan = fan_layer(n, seed=53)
    fan_dark = circ_filter(fan, "lowpass", 250, 2)
    morph = np.clip(t / 0.6, 0, 1)[:, None]
    fan_m = fan * (1 - morph) + fan_dark * morph
    rainx = rain_layer(n, seed=54, thunder_at=None, loop=False)
    rain_dark = circ_filter(rainx, "lowpass", 600, 2)
    open_ = np.clip((t - 0.3) / 0.6, 0, 1)[:, None]
    rain_m = rain_dark * (1 - open_) + rainx * open_
    th = np.clip((t - 0.2) / 0.65, 0, 1) * np.pi / 2
    out = fan_m * 0.8 * np.cos(th)[:, None] + rain_m * 0.7 * np.sin(th)[:, None]
    return fade(out, 0.3, 0.6)


def page():
    rng = np.random.default_rng(61)
    dur = 0.5
    n = n_samples(dur)
    t = t_axis(n)
    env = np.sin(np.pi * np.clip(t / 0.42, 0, 1)) ** 1.5
    crinkle = np.ones(n)
    for _ in range(18):  # little crackles of paper
        c = n_samples(rng.uniform(0.03, 0.4))
        w = n_samples(rng.uniform(0.003, 0.012))
        crinkle[c:c + w] += rng.uniform(0.5, 1.6)
    x = noise(n, 1)
    # band sweeps up as the page swishes over
    lo = sos_filter(x, "bandpass", (900, 3000), 2)
    hi = sos_filter(x, "bandpass", (3000, 9000), 2)
    sweep = np.clip(t / 0.35, 0, 1)
    swish = lo * (1 - sweep) + hi * sweep * 0.8
    flap_at = n_samples(0.40)
    flap = np.zeros(n)
    ft = t_axis(n - flap_at)
    flap[flap_at:] = sos_filter(noise(n - flap_at, 2), "lowpass", 500, 2) * np.exp(-ft / 0.03) * 2.0
    mono = swish * env * crinkle + flap
    st = np.stack([mono, sos_filter(mono, "lowpass", 7000, 1)], axis=1)
    return fade(room(st, 0.2, 0.12), 0.003, 0.03)[: n_samples(0.55)]


def buzz():
    """Phone vibrating on a wooden desk: two short buzzes."""
    dur = 1.0
    n = n_samples(dur)
    t = t_axis(n)
    gate = np.zeros(n)
    for s, e in ((0.03, 0.40), (0.55, 0.92)):
        a, b = n_samples(s), n_samples(e)
        g = np.ones(b - a)
        r = n_samples(0.02)
        g[:r] = np.linspace(0, 1, r)
        g[-r:] = np.linspace(1, 0, r)
        gate[a:b] = g
    f = 168 + 6 * np.sin(TAU * 7 * t)  # motor speed jitter
    ph = TAU * np.cumsum(f) / SR
    motor = np.tanh(3 * np.sin(ph))  # clipped -> rich harmonics (rattle)
    rattle = noise(n, 3) * (np.sin(ph) > 0.6) * 0.5  # case knocking the wood
    x = motor + rattle
    wood = sos_filter(x, "bandpass", (150, 2500), 2) + 0.6 * sos_filter(x, "bandpass", (380, 520), 2)
    mono = wood * gate
    return fade(room(stereo(mono), 0.22, 0.15), 0.002, 0.04)[: n_samples(1.05)]


def bell_sfx():
    """Small silver jingle bell (cat choker), one soft distant jingle."""
    rng = np.random.default_rng(71)
    tl = Timeline(1.5, tail=2.0)
    ratios = np.array([1.0, 1.52, 2.11, 2.68, 3.33])
    amps = np.array([1.0, 0.6, 0.45, 0.25, 0.15])
    decays = np.array([0.7, 0.45, 0.3, 0.2, 0.12])
    f0 = 3100.0
    t = 0.02
    strikes = 0
    while strikes < 6:  # pellet bouncing inside the shell
        n = n_samples(1.2)
        tt = t_axis(n)
        v = 0.75 ** strikes * rng.uniform(0.8, 1.0)
        tone = sum(a * np.sin(TAU * f0 * r * rng.uniform(0.998, 1.002) * tt + rng.uniform(0, TAU))
                   * np.exp(-tt / d) for r, a, d in zip(ratios, amps, decays))
        tone += 0.4 * noise(n, strikes) * np.exp(-tt / 0.001)
        tl.add(tone * v, t, 0.3, rng.uniform(-0.25, 0.25))
        t += rng.uniform(0.04, 0.11) * (1 + 0.3 * strikes)
        strikes += 1
    x = sos_filter(tl.oneshot(), "lowpass", 7000, 2)  # distance
    x = reverb(x, reverb_ir(1.4, predelay=0.02, damp_hz=5000, seed=12), wet=0.55, loop=False)
    return fade(x, 0.001, 0.25)[: n_samples(1.5)]


# ============================================================== dream: chapters 1-8 and epilogues
# The dream is a XVIII-century mansion, so its music is harpsichord, strings, flute, timpani.
# Everything still grows out of Kuni's theme (MEL_A/MEL_B over PROG_A/PROG_B).

# plain triads (baroque voicing) for the jazzy chords of PROG_A/PROG_B
TRI = {
    "Fmaj9": ([53, 57, 60], 41), "Em7": ([52, 55, 59], 40), "Am9": ([52, 57, 60], 45),
    "Dm9": ([50, 53, 57], 38), "G9sus": ([50, 55, 59], 43), "Bbmaj9": ([50, 53, 58], 46),
    "Am7": ([52, 57, 60], 45), "Esus": ([52, 56, 59], 40), "E7b9": ([50, 56, 59], 40),
}
C_MAJOR = (0, 2, 4, 5, 7, 9, 11)


def segments(prog):
    """(bar index, beat, length in beats, chord name) for every chord of a progression."""
    for bi, bar in enumerate(prog):
        for si, (beat, name) in enumerate(bar):
            end = bar[si + 1][0] if si + 1 < len(bar) else 4
            yield bi, beat, end - beat, name


def place(tl, rng, bars, start_bar, bpm, inst, gain=0.6, transpose=0, vel=0.7, pan_pos=0.0,
          legato=1.0, jitter=0.012):
    """Like play_melody, but with pan, legato and any instrument (mono or stereo)."""
    spb = 60 / bpm
    for bi, bar in enumerate(bars):
        t0 = (start_bar + bi) * 4 * spb
        for beat, m, ln in bar:
            v = vel * rng.uniform(0.88, 1.0) * (1.08 if beat == 0 else 1.0)
            tl.add(inst(m + transpose, ln * spb * legato, v), t0 + beat * spb + human(rng, jitter),
                   gain, pan_pos)


def upper_neighbour(m, scale=C_MAJOR):
    for d in (1, 2):
        if (m + d) % 12 in scale:
            return m + d
    return m + 2


def ornament(bars, rng, every=0.6, scale=C_MAJOR):
    """Baroque mordents on long notes: main - upper neighbour - main, then hold."""
    out = []
    for bar in bars:
        nb = []
        for beat, m, ln in bar:
            if ln >= 1.5 and rng.uniform() < every:
                u = upper_neighbour(m, scale)
                nb += [(beat, m, .125), (beat + .125, u, .125), (beat + .25, m, ln - .25)]
            else:
                nb.append((beat, m, ln))
        out.append(nb)
    return out


def minorize(bars, mapping):
    return [[(b, m + mapping.get(m % 12, 0), ln) for b, m, ln in bar] for bar in bars]


def daily():
    """Everyday life in the mansion: a sunny gavotte. Theme on ornamented harpsichord, alberti
    left hand, walking pizzicato, strings join in B, flute doubles the reprise."""
    bpm = 104
    spb = 60 / bpm
    bars = 24
    rng = np.random.default_rng(101)
    tl = Timeline(bars * 4 * spb)
    prog = PROG_A * 2 + PROG_B * 2 + PROG_A * 2
    mel = MEL_A + MEL_B + MEL_A
    hp = lambda m, d, v: harpsichord(m, d, v, bright=1.0)
    place(tl, rng, ornament(mel, rng), 0, bpm, hp, gain=0.55, vel=0.72, pan_pos=0.1, jitter=0.006)
    place(tl, rng, MEL_A, 16, bpm, lambda m, d, v: flute(m, d * 0.92, v, seed=3), gain=0.35, pan_pos=-0.25)
    for bi, beat, seg, name in segments(prog):
        notes, root = TRI[name]
        t0 = bi * 4 * spb + beat * spb
        a, b, c = notes
        for e in range(int(seg * 2)):  # alberti eighths
            m = (a, c, b, c)[e % 4]
            tl.add(harpsichord(m, 0.5 * spb, 0.5 * rng.uniform(0.85, 1.0), bright=0.8),
                   t0 + e * 0.5 * spb + human(rng, 0.004), 0.32, -0.2)
        walk = (root, root + 7, root + 12, root + 7)
        for q in range(int(seg)):
            tl.add(pizz(walk[q], 0.75 if q % 2 == 0 else 0.6), t0 + q * spb + human(rng, 0.004), 0.5, -0.05)
        if bi >= 8:  # strings bed in B and the reprise
            for k, m in enumerate(notes):
                tl.add(strings(m, seg * spb * 0.98, 0.5, attack=0.25, rel=0.5, voices=2, seed=k),
                       t0, 0.16)
    music = circ_filter(tl.loop(), "highpass", 40, 2)
    music = reverb(music, reverb_ir(1.6, damp_hz=5000, seed=21), wet=0.22)
    music = np.tanh(music * 1.2) / 1.2
    return circ_filter(music, "lowpass", 12000, 2)


def tender():
    """Tender scenes with Kuni: slow, lute-stop harpsichord arpeggios, soft strings, the theme on
    a solo violin, flute closes the phrase."""
    bpm = 66
    spb = 60 / bpm
    bars = 20
    rng = np.random.default_rng(102)
    tl = Timeline(bars * 4 * spb)
    prog = PROG_A + PROG_A * 2 + PROG_B + PROG_A
    for bi, beat, seg, name in segments(prog):
        notes, root = CH[name]
        notes = sorted(notes)
        t0 = bi * 4 * spb + beat * spb
        pattern = (0, 1, 2, 3, 2, 1, 2, 3)
        for e in range(int(seg * 2)):
            tl.add(harpsichord(notes[pattern[e % 8]], 1.6 * spb, 0.42 * rng.uniform(0.85, 1.0), bright=0.3),
                   t0 + e * 0.5 * spb + human(rng, 0.008), 0.34, 0.3 * np.sin(e * 0.9))
        for k, m in enumerate(notes):
            tl.add(strings(m, seg * spb, 0.45, attack=1.0, rel=1.4, voices=2, seed=10 + k), t0, 0.1)
        tl.add(strings(root, seg * spb, 0.5, attack=0.6, rel=1.2, voices=2, seed=20), t0, 0.16)
    violin = lambda m, d, v: strings(m, d, v, attack=0.18, rel=0.6, solo=True, seed=7)
    place(tl, rng, MEL_A + MEL_B[:4], 4, bpm, violin, gain=0.5, vel=0.7, jitter=0.01)
    place(tl, rng, MEL_OUTRO, 16, bpm, lambda m, d, v: flute(m, d, v, seed=5), gain=0.4, pan_pos=0.15)
    music = circ_filter(tl.loop(), "highpass", 40, 2)
    music = reverb(music, reverb_ir(2.6, damp_hz=4000, seed=22), wet=0.32)
    return circ_filter(np.tanh(music * 1.1) / 1.1, "lowpass", 10000, 2)


TEN_CH = {  # strings triad, bass root, timpani note
    "Am": ([57, 60, 64], 45, 45), "F": ([57, 60, 65], 41, 41), "Dm": ([57, 62, 65], 38, 50),
    "E": ([56, 59, 64], 40, 40), "Bb": ([58, 62, 65], 46, 46),
}
TEN_MEL = [  # the theme's contour bent into A minor (G# leading tone)
    [(1, 76, .5), (1.5, 79, .5), (2, 81, 1.5), (3.5, 79, .5)],
    [(0, 77, 2), (2, 76, .5), (2.5, 77, .5), (3, 72, 1)],
    [(0, 74, 1.5), (1.5, 72, .5), (2, 74, .5), (2.5, 77, 1.5)],
    [(0, 76, 1.5), (1.5, 74, .5), (2, 71, 1), (3, 68, 1)],
    [(1, 76, .5), (1.5, 79, .5), (2, 84, 1.5), (3.5, 83, .5)],
    [(0, 81, 1), (1, 77, 1), (2, 76, 1.5), (3.5, 74, .5)],
    [(0, 74, 1), (1, 77, 1), (2, 76, .5), (2.5, 74, .5), (3, 72, 1)],
    [(0, 71, 2), (2, 68, 2)],
]


def tension():
    """Jealousy, Mei's scam, the locked room: 3+3+2 staccato ostinato in the low strings,
    timpani, sharp harpsichord stabs, the theme twisted into A minor on a solo violin."""
    bpm = 88
    spb = 60 / bpm
    prog = ["Am", "Am", "F", "F", "Dm", "Dm", "E", "E",
            "Am", "F", "Bb", "E", "Am", "F", "Dm", "E",
            "Am", "Am", "E", "E"]
    bars = len(prog)
    rng = np.random.default_rng(103)
    tl = Timeline(bars * 4 * spb)
    accents = (1.0, .45, .5, 1.0, .45, .5, .9, .5)
    for bi, name in enumerate(prog):
        notes, root, timp = TEN_CH[name]
        t0 = bi * 4 * spb
        thin = bi >= 16
        for e in range(8):
            v = accents[e] * (0.6 if thin else 0.8)
            tl.add(strings(root, 0.32 * spb, v, attack=0.008, rel=0.07, voices=2, seed=e),
                   t0 + e * 0.5 * spb + human(rng, 0.003), 0.3, -0.1)
            if accents[e] > 0.8 and not thin:
                tl.add(strings(root - 12, 0.3 * spb, v, attack=0.01, rel=0.08, voices=2, seed=e + 9),
                       t0 + e * 0.5 * spb, 0.2, -0.2)
        if bi == 0 or prog[bi - 1] != name:
            tl.add(timpani(timp, 0.8), t0, 0.5, 0.1)
        if name == "E" and (bi + 1 >= bars or prog[bi + 1] != "E"):
            for r in range(4):  # little roll into the next bar
                tl.add(timpani(timp, 0.35 + 0.1 * r, 0.6), t0 + (3 + r * 0.25) * spb, 0.45, 0.1)
        if 8 <= bi < 16:
            for at in (1.5, 3.0):
                for k, m in enumerate(notes):
                    tl.add(harpsichord(m + 12, 0.2 * spb, 0.6, bright=1.0), t0 + at * spb + k * 0.008, 0.26, 0.3)
        # high, thin, uneasy: chord top an octave up rubbing against its upper semitone
        top = notes[-1] + 12
        tl.add(strings(top, 4 * spb, 0.35, attack=1.2, rel=1.0, voices=3, seed=bi), t0, 0.05)
        if name in ("E", "F", "Bb"):
            tl.add(strings(top + 1, 4 * spb, 0.3, attack=1.6, rel=1.0, voices=2, seed=bi + 40), t0, 0.035)
    violin = lambda m, d, v: strings(m, d, v, attack=0.06, rel=0.4, solo=True, seed=8)
    place(tl, rng, TEN_MEL, 8, bpm, violin, gain=0.42, vel=0.72)
    music = circ_filter(tl.loop(), "highpass", 35, 2)
    music = reverb(music, reverb_ir(2.0, damp_hz=4000, seed=23), wet=0.25)
    return circ_filter(np.tanh(music * 1.4) / 1.4, "lowpass", 10000, 2)


def tick_sound(rng, tock=False):
    """One hall-clock escapement tick (tock is lower). Mono, ~0.3 s."""
    n = n_samples(0.3)
    t = t_axis(n)
    k = 0.8 if tock else 1.0
    click = sos_filter(noise(n, rng.integers(1 << 30)), "highpass", 2500, 2) * np.exp(-t / 0.0012)
    ring = (np.sin(TAU * 2900 * k * t) * 0.5 + np.sin(TAU * 4100 * k * t) * 0.3) * np.exp(-t / 0.025)
    body = np.sin(TAU * 520 * k * t) * np.exp(-t / 0.018) + 0.6 * sos_filter(
        noise(n, rng.integers(1 << 30)), "bandpass", (300, 1200), 2) * np.exp(-t / 0.006)
    return (click * 0.7 + ring * 0.35 + body * 0.6) * (1 - np.exp(-t / 0.0003))


MYS = {  # chord: (glass voicing, bass, motif root)  -- motif is 0-3-4-7 ("03:47")
    "Em": ([64, 67, 71, 75], 40, 76), "C": ([64, 67, 71, 78], 36, 72), "Ab": ([63, 68, 72, 79], 44, 68),
    "F": ([65, 69, 72, 76], 41, 77), "B": ([63, 66, 71, 75], 47, 71),
}


def mystery():
    """Magic: the Oracle, mirrors, the Governess, the clock stuck at 03:47. Glass harmonica,
    celesta motif 0-3-4-7, reversed swells, a slow clock tick under everything."""
    bpm = 60
    spb = 60 / bpm
    prog = ["Em", "Em", "C", "C", "Ab", "Ab", "Em", "Em", "F", "F", "B", "B"]
    bars = len(prog)
    rng = np.random.default_rng(104)
    tl = Timeline(bars * 4 * spb)
    bells = Timeline(bars * 4 * spb)
    for bi in range(0, bars, 2):
        name = prog[bi]
        voicing, bass, mr = MYS[name]
        t0 = bi * 4 * spb
        for k, m in enumerate(voicing):
            tl.add(glass(m, 8 * spb, 0.5, attack=1.5, rel=2.0), t0 + k * 0.3, 0.16, (k - 1.5) * 0.4)
        tl.add(strings(bass, 8 * spb, 0.5, attack=2.0, rel=2.0, voices=2, seed=bi), t0, 0.2)
        # reversed swell into the chord change
        sw = glass(voicing[-1] + 12, 1.8, 0.6, attack=0.01, rel=0.2)[::-1]
        tl.add(sw, t0 - len(sw) / SR, 0.12, 0.3)
        motif = [(0, mr, 0.7), (0.75, mr + 3, 0.7), (1.5, mr + 4, 1.4), (3, mr + 7, 1.8)]
        for beat, m, ln in motif:
            bells.add(bell(m, ln * spb, 0.6 * rng.uniform(0.85, 1.0), rel=2.0), t0 + beat * spb + human(rng),
                      0.4, rng.uniform(-0.3, 0.3))
        for beat, m in ((5, mr + 7), (6.5, mr + 4)):
            bells.add(bell(m + 12, spb, 0.4, rel=2.0), t0 + beat * spb + human(rng), 0.25, 0.4)
    bl = bells.loop()
    bl = bl + delay_echo(bl, spb * 0.75, 0.35, 4, lp_hz=4000) * 0.6
    clock = Timeline(bars * 4 * spb)
    for b in range(bars * 4):
        clock.add(tick_sound(rng, tock=b % 2 == 1), b * spb, 0.07, -0.35)
    music = tl.loop() + bl + reverb(clock.loop(), reverb_ir(1.2, damp_hz=5000, seed=25), wet=0.3)
    music = circ_filter(music, "highpass", 35, 2)
    music = reverb(music, reverb_ir(4.0, damp_hz=4000, seed=24), wet=0.45)
    return circ_filter(music, "lowpass", 11000, 2)


def tarot():
    """The tarot minigame (her desk, a candle): a slow bell arpeggio in D dorian over glass pads and a low string
    drone, a faint reversed shimmer into every second chord. 66 bpm, 16 bars, no drums."""
    bpm = 66
    spb = 60 / bpm
    bars = 16
    rng = np.random.default_rng(111)
    # (voicing, bass) per two bars; the arpeggio takes the voicing up and down
    prog = [([57, 62, 65, 69], 38), ([55, 62, 65, 70], 34), ([55, 60, 64, 67], 36), ([57, 61, 64, 67], 33)] * 2
    tl = Timeline(bars * 4 * spb)
    arp = Timeline(bars * 4 * spb)
    for i, (voicing, bass) in enumerate(prog):
        t0 = i * 8 * spb
        for k, m in enumerate(voicing):
            tl.add(glass(m, 8 * spb, 0.5, attack=1.6, rel=2.0), t0 + k * 0.35, 0.15, (k - 1.5) * 0.4)
        tl.add(strings(bass, 8 * spb, 0.5, attack=2.0, rel=2.0, voices=2, seed=60 + i), t0, 0.2)
        if i % 2 == 1:
            sw = glass(voicing[-1] + 12, 1.8, 0.6, attack=0.01, rel=0.2)[::-1]
            tl.add(sw, t0 - len(sw) / SR, 0.1, 0.3)
        order = [0, 1, 2, 3, 2, 1, 2, 3] if i % 2 == 0 else [3, 2, 1, 0, 1, 2, 1, 2]
        for step, idx in enumerate(order * 2):
            m = voicing[idx] + 12
            arp.add(bell(m, spb, 0.5 * rng.uniform(0.8, 1.0), rel=1.6), t0 + step * spb * 0.5 + human(rng, 0.006),
                    0.32 if step % 4 == 0 else 0.22, 0.3 * ((step % 3) - 1))
    ab = arp.loop()
    ab = ab + delay_echo(ab, spb * 0.75, 0.3, 4, lp_hz=3800) * 0.5
    music = circ_filter(tl.loop() + ab, "highpass", 35, 2)
    music = reverb(music, reverb_ir(3.6, damp_hz=4000, seed=27), wet=0.45)
    return circ_filter(music, "lowpass", 10000, 2)


def night_kuni():
    """Kuni's interludes: alone in the house at night. A music-box lullaby of her theme over soft
    e-piano (her code side) and bowed strings (her dream side). No drums."""
    bpm = 60
    spb = 60 / bpm
    bars = 16
    tr = -2
    rng = np.random.default_rng(105)
    tl = Timeline(bars * 4 * spb)
    prog = PROG_A * 2 + PROG_B * 2
    for bi, beat, seg, name in segments(prog):
        notes, root = CH[name]
        t0 = bi * 4 * spb + beat * spb
        for k, m in enumerate(notes):
            tl.add(epiano(m + tr, seg * spb * 0.95, 0.3 * rng.uniform(0.9, 1.05), bright=0.6),
                   t0 + k * 0.03 + human(rng, 0.008), 0.45, (k - 1.5) * 0.3)
            tl.add(strings(m + tr, seg * spb, 0.4, attack=1.4, rel=1.6, voices=2, seed=30 + k), t0, 0.07)
        tl.add(soft_bass(root + tr, seg * spb * 0.9, 0.5), t0, 0.16)
    lead = Timeline(bars * 4 * spb)
    mel = MEL_A + MEL_B
    place(lead, rng, mel, 0, bpm, lambda m, d, v: bell(m, d, v, rel=1.5), gain=0.55, transpose=tr, vel=0.65)
    lb = lead.loop()
    lb = lb + delay_echo(lb, spb * 1.5, 0.3, 3, lp_hz=3500) * 0.45
    music = circ_filter(tl.loop() + lb, "highpass", 35, 2)
    music = reverb(music, reverb_ir(3.4, damp_hz=3500, seed=26), wet=0.4)
    return circ_filter(np.tanh(music * 1.2) / 1.2, "lowpass", 9000, 2)


def bird(rng):
    """A short garden bird phrase: 2-6 quick chirps. Mono."""
    tl = Timeline(1.2, tail=0.5)
    t = 0.0
    base = rng.uniform(2800, 4200)
    for _ in range(rng.integers(2, 7)):
        d = rng.uniform(0.04, 0.09)
        n = n_samples(d)
        tt = t_axis(n)
        sweep = base * (1 + rng.uniform(-0.25, 0.35) * tt / d)
        tone = sine(sweep * (1 + 0.04 * np.sin(TAU * 60 * tt)), n)
        tl.add(tone * np.sin(np.pi * tt / d) ** 2, t)
        t += d + rng.uniform(0.02, 0.09)
    return tl.oneshot()


def morning():
    """Chapter 8 and the good morning: rain is gone, sun in the garden. Theme on violin, then flute,
    harpsichord arpeggios; in the last bars only the prologue's e-piano is left (the dream fades)."""
    bpm = 76
    spb = 60 / bpm
    bars = 24
    tr = 2
    rng = np.random.default_rng(106)
    tl = Timeline(bars * 4 * spb)
    prog = PROG_A + PROG_A * 2 + PROG_B * 2 + PROG_A
    for bi, beat, seg, name in segments(prog):
        notes, root = CH[name]
        notes = sorted(m + tr for m in notes)
        root += tr
        t0 = bi * 4 * spb + beat * spb
        dream = bi < 20
        if dream:
            for e in range(int(seg * 2)):
                m = notes[(0, 2, 1, 3, 2, 1, 3, 2)[e % 8]] + (12 if e % 4 == 3 else 0)
                tl.add(harpsichord(m, 1.2 * spb, 0.4 * rng.uniform(0.85, 1.0), bright=0.6),
                       t0 + e * 0.5 * spb + human(rng, 0.006), 0.3, 0.35 * np.sin(e * 0.7))
            for k, m in enumerate(notes):
                tl.add(strings(m, seg * spb, 0.45, attack=0.9, rel=1.2, voices=2, seed=40 + k), t0, 0.09)
            tl.add(pizz(root, 0.7), t0, 0.4)
            if seg >= 4:
                tl.add(pizz(root + 7, 0.55), t0 + 2 * spb, 0.35)
        if bi >= 12:  # the prologue's e-piano wakes up
            for k, m in enumerate(notes):
                tl.add(epiano(m, seg * spb * 0.95, 0.32 * rng.uniform(0.9, 1.05), bright=0.7),
                       t0 + k * 0.016, 0.42 if bi >= 20 else 0.3, (k - 1.5) * 0.25)
            if bi >= 20:
                tl.add(soft_bass(root, seg * spb * 0.9, 0.55), t0, 0.22)
    violin = lambda m, d, v: strings(m, d, v, attack=0.15, rel=0.6, solo=True, seed=9)
    place(tl, rng, MEL_A, 4, bpm, violin, gain=0.45, transpose=tr, vel=0.7)
    place(tl, rng, MEL_B, 12, bpm, lambda m, d, v: flute(m, d, v, seed=6), gain=0.4, transpose=tr, pan_pos=0.2)
    place(tl, rng, MEL_B, 12, bpm, violin, gain=0.3, transpose=tr - 12, vel=0.6)
    place(tl, rng, MEL_OUTRO, 20, bpm, lambda m, d, v: epiano(m, d, v, bright=1.0), gain=0.6, transpose=tr)
    music = circ_filter(tl.loop(), "highpass", 40, 2)
    music = reverb(music, reverb_ir(2.4, damp_hz=4500, seed=27), wet=0.3)
    music = np.tanh(music * 1.1) / 1.1
    birds = Timeline(bars * 4 * spb)
    t = 1.0
    while t < bars * 4 * spb - 1:
        if t < 20 * 4 * spb or rng.uniform() < 0.3:
            birds.add(bird(rng), t, rng.uniform(0.04, 0.09), rng.uniform(-0.8, 0.8))
        t += rng.uniform(2.5, 7.0)
    birds_buf = reverb(birds.loop(), reverb_ir(1.5, damp_hz=6000, seed=28), wet=0.4)
    return circ_filter(music, "lowpass", 12000, 2) + birds_buf


def jump():
    """Chapter 7, the climax: 'this time you don't jump alone'. Driving string ostinato,
    harpsichord sixteenths, timpani, the theme in octaves."""
    bpm = 116
    spb = 60 / bpm
    bars = 24
    tr = 2
    rng = np.random.default_rng(107)
    tl = Timeline(bars * 4 * spb)
    prog = PROG_A + PROG_A * 2 + PROG_B * 2 + PROG_A
    timp_of = lambda r: 40 + (r - 40) % 12  # keep the drums in E2..D#3
    for bi, beat, seg, name in segments(prog):
        notes, root = CH[name]
        notes = sorted(m + tr for m in notes)
        root += tr
        t0 = bi * 4 * spb + beat * spb
        build = min(1.0, 0.5 + 0.15 * bi) if bi < 4 else 1.0
        walk = (root + 12, root + 19, root + 24, root + 19)
        for e in range(int(seg * 2)):
            v = (0.85 if e % 2 == 0 else 0.6) * build
            tl.add(strings(walk[e % 4], 0.34 * spb, v, attack=0.01, rel=0.07, voices=2, seed=e),
                   t0 + e * 0.5 * spb + human(rng, 0.003), 0.26, -0.15)
        tl.add(pizz(root, 0.8 * build), t0, 0.45)
        if seg >= 4:
            tl.add(pizz(root, 0.6 * build), t0 + 2 * spb, 0.4)
        if bi >= 4:
            for s in range(int(seg * 4)):
                m = notes[(0, 1, 2, 3, 2, 1, 2, 3)[s % 8]] + 12
                tl.add(harpsichord(m, 0.35 * spb, 0.42 * rng.uniform(0.85, 1.0)),
                       t0 + s * 0.25 * spb + human(rng, 0.003), 0.2, 0.35 * np.sin(s * 0.6))
            for q in range(0, int(seg), 2):
                tl.add(kick(0.5), t0 + q * spb, 0.5)
            for q in range(1, int(seg), 2):
                tl.add(brush(0.3, seed=bi * 4 + q), t0 + q * spb, 0.5, 0.1)
        if beat == 0:
            tl.add(timpani(timp_of(root), 0.85), t0, 0.5, 0.1)
        if bi >= 12:
            for k, m in enumerate(notes):
                tl.add(strings(m, seg * spb, 0.5, attack=0.4, rel=0.8, voices=3, seed=50 + k), t0, 0.08)
    for r in range(8):  # roll at the end of the build
        tl.add(timpani(timp_of(CH["Dm9"][1] + tr), 0.3 + 0.08 * r, 0.5), (3 * 4 + 2 + r * 0.25) * spb, 0.4, 0.1)
    sect = lambda m, d, v: strings(m, d, v, attack=0.05, rel=0.35, voices=3, seed=11)
    place(tl, rng, MEL_A, 4, bpm, sect, gain=0.4, transpose=tr, vel=0.8)
    place(tl, rng, MEL_A, 4, bpm, sect, gain=0.25, transpose=tr - 12, vel=0.75)
    place(tl, rng, MEL_B, 12, bpm, sect, gain=0.38, transpose=tr, vel=0.85)
    place(tl, rng, MEL_B, 12, bpm, lambda m, d, v: flute(m, d, v, seed=7), gain=0.3, transpose=tr, pan_pos=0.25)
    place(tl, rng, MEL_OUTRO, 20, bpm, lambda m, d, v: strings(m, d, v, attack=0.1, rel=0.6, solo=True, seed=12),
          gain=0.45, transpose=tr)
    music = circ_filter(tl.loop(), "highpass", 35, 2)
    music = reverb(music, reverb_ir(2.2, damp_hz=4500, seed=29), wet=0.25)
    return circ_filter(np.tanh(music * 1.3) / 1.3, "lowpass", 12000, 2)


BAD_CH = {  # the same progression, emptied: major chords turned minor / diminished
    "Fmaj9": ([53, 56, 60, 63], 41), "Em7": ([51, 55, 58, 62], 39), "Am9": ([56, 60, 63, 67], 44),
    "Dm9": ([50, 53, 56, 60], 38), "G9sus": ([53, 55, 59, 62], 43),
}


def bad_end():
    """The 💀 ending: 'Your tea, my lord'. Kuni's theme in C minor on a slightly out-of-tune
    music box, cold drone, empty reverb. Nothing warm is left."""
    bpm = 54
    spb = 60 / bpm
    bars = 12
    rng = np.random.default_rng(108)
    sec = bars * 4 * spb
    tl = Timeline(sec)
    prog = PROG_A * 3
    for bi, beat, seg, name in segments(prog):
        notes, root = BAD_CH[name]
        t0 = bi * 4 * spb + beat * spb
        for k, m in enumerate(notes):
            tl.add(pad(m, seg * spb, 0.45, attack=2.5, rel=3.0, seed=60 + k), t0, 0.05)
        tl.add(glass(root + 24, seg * spb, 0.4, attack=1.5, rel=2.5), t0, 0.08, -0.3)
    mel = minorize(MEL_A, {4: -1, 9: -1, 11: -1})  # E->Eb, A->Ab, B->Bb
    box = Timeline(sec)
    for bi, bar in enumerate(mel):
        t0 = (4 + bi) * 4 * spb
        for beat, m, ln in bar:
            m = m + rng.uniform(-0.18, 0.18)  # worn music box comb
            box.add(bell(m, ln * spb, 0.55 * rng.uniform(0.8, 1.0), rel=2.5), t0 + beat * spb + human(rng, 0.02),
                    0.5, 0.1)
    n = tl.n
    drone = 0.06 * (tone_loop(midi_hz(36), n) + 0.5 * tone_loop(midi_hz(43), n, 1.0))
    drone *= 0.75 + 0.25 * periodic_lfo(n, 3)
    wind = circ_filter(colored_noise(n, "pink", seed=81, channels=2, correlation=0.3), "bandpass", (200, 900), 2)
    wind *= (0.012 * (1 + 0.5 * periodic_lfo(n, 2, 0.7)))[:, None]
    music = tl.loop() + box.loop() + stereo(drone) + wind
    music = circ_filter(music, "highpass", 30, 2)
    music = reverb(music, reverb_ir(5.0, damp_hz=3000, seed=30), wet=0.5)
    return circ_filter(music, "lowpass", 7000, 2)


# ============================================================== ending song (credits page)
# 166 bpm piano-pop band, 40 bars + 2 bars of ring-out before it loops:
#   intro  8  E: staccato eighths, an E5 pedal over an inner voice sinking by semitones; bars 5-8 add the
#             "03:47" motif 0-3-4-7 on bell (E G G# B)
#   verse  8  E | B/D# | C#m | A | E | B/D# | A | B
#   pre    4  C#m | A | F#m | B -> G7 (pivot), dotted syncopation
#   chorus 16 drops a major third into C: Kuni's theme MEL_A in its home key, note values doubled, over PROG_A
#             doubled (IV iii vi ii V); violin + flute an octave up
#   outro  4  the 03:47 motif in C (C Eb E G) on bell, Fmaj9 - G9sus - C

END_BPM = 166
END_SPB = 60 / END_BPM
END_E = {  # name: (voicing, bass root)
    "E": ([59, 64, 68], 40), "B/D#": ([59, 63, 66], 39), "C#m": ([61, 64, 68], 37),
    "A": ([61, 64, 69], 33), "F#m": ([61, 66, 69], 42), "B": ([59, 63, 66], 35),
    "G7": ([59, 62, 65], 43), "C": ([55, 60, 64], 36),
}
END_INNER = [71, 71, 70, 69, 68, 68, 69, 70]  # intro inner voice per half-bar
END_MOTIF = [0, 3, 4, 7]  # 03:47
END_VERSE = [
    [(.5, 68, .5), (1, 71, .5), (1.5, 68, .5), (2, 66, 1), (3, 64, .5), (3.5, 66, .5)],
    [(0, 68, 1.5), (1.5, 66, .5), (2, 63, 1.5), (3.5, 71, .5)],
    [(0, 73, .5), (.5, 71, .5), (1, 68, .5), (1.5, 71, .5), (2, 73, 1), (3, 75, .5), (3.5, 76, .5)],
    [(0, 73, 2), (2, 71, 1.5), (3.5, 68, .5)],
    [(.5, 68, .5), (1, 71, .5), (1.5, 76, .5), (2, 75, 1), (3, 73, .5), (3.5, 71, .5)],
    [(0, 71, 1.5), (1.5, 68, .5), (2, 66, 2)],
    [(0, 69, .5), (.5, 71, .5), (1, 73, .5), (1.5, 76, 1), (2.5, 75, .5), (3, 73, 1)],
    [(0, 71, 3), (3.5, 71, .5)],
]
END_VERSE_CH = ["E", "B/D#", "C#m", "A", "E", "B/D#", "A", "B"]
END_PRE = [
    [(0, 76, .75), (.75, 75, .75), (1.5, 73, 1), (2.5, 71, .5), (3, 73, .5), (3.5, 75, .5)],
    [(0, 76, .75), (.75, 75, .75), (1.5, 73, 1), (2.5, 76, .5), (3, 78, .5), (3.5, 80, .5)],
    [(0, 81, .75), (.75, 80, .75), (1.5, 78, 1), (2.5, 76, .5), (3, 78, .5), (3.5, 80, .5)],
    [(0, 78, 2), (2, 79, .5), (2.5, 77, .5), (3, 74, .5), (3.5, 71, .5)],
]
END_PRE_CH = [[(0, "C#m")], [(0, "A")], [(0, "F#m")], [(0, "B"), (2, "G7")]]
END_OUTRO = [[(0, 72, 1), (1, 75, 1), (2, 76, 1), (3, 79, 1)], [(0, 76, 4)], [(0, 74, 2), (2, 71, 2)], [(0, 72, 4)]]
END_INTRO, END_VERSE_AT, END_PRE_AT, END_CHORUS_AT, END_OUTRO_AT, END_BARS = 0, 8, 16, 20, 36, 40
END_LOOP_BARS = END_BARS + 2  # the last C rings out before the intro comes back


def stretch(bars, k=2):
    """A melody with every note value multiplied by k (the 70-bpm theme sung at 166)."""
    out = [[] for _ in range(len(bars) * k)]
    for bi, bar in enumerate(bars):
        for b, m, ln in bar:
            B = b * k
            out[bi * k + int(B // 4)].append((B % 4, m, ln * k))
    return out


END_CHORUS = stretch(MEL_A)


def end_harmony():
    """[(abs beat, beats, voicing, bass root)] over the whole song."""
    out = [(b * 4, 4, END_E["E"][0], 40) for b in range(8)]
    for i, name in enumerate(END_VERSE_CH):
        out.append(((END_VERSE_AT + i) * 4, 4, *END_E[name]))
    for bi, beat, seg, name in segments(END_PRE_CH):
        out.append(((END_PRE_AT + bi) * 4 + beat, seg, *END_E[name]))
    for bi, beat, seg, name in segments(PROG_A * 2):
        v, r = CH[name]
        out.append(((END_CHORUS_AT + bi * 2) * 4 + beat * 2, seg * 2, sorted(v), r))
    for bi, name in enumerate(["Fmaj9", "G9sus"]):
        v, r = CH[name]
        out.append(((END_OUTRO_AT + bi) * 4, 4, sorted(v), r))
    out.append(((END_OUTRO_AT + 2) * 4, 8, *END_E["C"]))
    return out


def end_tune():
    """[(abs beat, midi, beats)]: verse, pre, chorus."""
    out = []
    for start, bars in ((END_VERSE_AT, END_VERSE), (END_PRE_AT, END_PRE), (END_CHORUS_AT, END_CHORUS)):
        for bi, bar in enumerate(bars):
            out += [((start + bi) * 4 + b, m, ln) for b, m, ln in bar]
    return out


@functools.lru_cache(maxsize=None)
def _piano(m, dur, vel):
    return pluck(m, dur, vel, pos=0.12, rolloff=1.05, hf_damp=0.22, max_hz=9000, chorus_cents=1.2, rel=0.12,
                 t60=float(np.clip(4.5 * (261.6 / midi_hz(m)) ** 0.55, 0.8, 7.0)))


def piano(m, dur, vel):
    """Plucked-string piano; cached, the band repeats the same chords a lot."""
    return _piano(int(m), round(dur, 3), round(vel * 20) / 20)


def snare(vel=0.6, seed=0):
    n = n_samples(0.22)
    t = t_axis(n)
    body = np.sin(TAU * 190 * t) * np.exp(-t / 0.04)
    nz = sos_filter(noise(n, seed), "bandpass", (1200, 8000), 2) * np.exp(-t / 0.08)
    return (body * 0.6 + nz * 1.4) * (1 - np.exp(-t / 0.001)) * vel


def crash(vel=0.5, seed=1):
    n = n_samples(2.0)
    return sos_filter(noise(n, seed), "highpass", 5000, 2) * np.exp(-t_axis(n) / 0.6) * vel


def ending():
    """Credits song: see the section comment above."""
    spb = END_SPB
    at = lambda beat: beat * spb
    rng = np.random.default_rng(1)
    tl = Timeline(END_LOOP_BARS * 4 * spb)
    H = end_harmony()
    # intro: staccato figure, the 03:47 motif, bass pulses
    for bar in range(8):
        for e in range(8):
            if bar % 2 == 0 and e < 2:  # a breath on beat 1 of every other bar
                continue
            m = 76 if e % 2 else END_INNER[(bar % 4) * 2 + e // 4]
            tl.add(piano(m, 0.28 * spb, (0.55 if m == 76 else 0.7) * rng.uniform(0.9, 1.0)),
                   at(bar * 4 + e * .5) + human(rng, 0.003), 0.55, 0.15 if m == 76 else -0.1)
    for bar in (4, 6):
        for i, d in enumerate(END_MOTIF):
            tl.add(bell(76 + d, 0.9 * spb, 0.7), at(bar * 4 + i), 0.35, 0.2)
    for bar in range(8):
        for off in (0, 2.5):
            tl.add(soft_bass((40 if off == 0 else 47) - 12, 0.4 * spb, 0.7), at(bar * 4 + off), 0.5)
    band = [(beat, ln, v, root) for beat, ln, v, root in H if END_VERSE_AT * 4 <= beat < END_OUTRO_AT * 4]
    # piano: a chord on every eighth, accents push the offbeats; an octave up in the chorus
    for beat, ln, v, root in band:
        up = 12 if beat >= END_CHORUS_AT * 4 else 0
        for e in range(int(ln * 2)):
            vel = (0.6, 0.35, 0.45, 0.55)[e % 4] * rng.uniform(0.9, 1.0)
            for k, m in enumerate(v):
                tl.add(piano(m + up, 0.3 * spb, vel), at(beat + e * .5) + k * 0.004 + human(rng, 0.003),
                       0.22, -0.25 + k * 0.15)
    # bass eighths, an octave jump at the end of each beat pair in the chorus
    for beat, ln, v, root in band:
        for e in range(int(ln * 2)):
            r = root + (12 if e % 4 == 3 and beat >= END_CHORUS_AT * 4 else 0)
            tl.add(soft_bass(r, 0.42 * spb, 0.75 if e % 2 == 0 else 0.6), at(beat + e * .5) + human(rng, 0.003), 0.5)
    # drums from the verse to the outro, a fill into the chorus, crashes on the sections
    for b in range(END_VERSE_AT, END_OUTRO_AT):
        t0 = b * 4
        chorus = b >= END_CHORUS_AT
        tl.add(kick(0.8), at(t0))
        tl.add(kick(0.6), at(t0 + 1.5 if chorus else t0 + 2.5))
        if chorus:
            tl.add(kick(0.7), at(t0 + 2))
        for s in (1, 3):
            tl.add(snare(0.55, b * 4 + s), at(t0 + s) + human(rng, 0.003), 0.45, 0.05)
        for e in range(8):
            tl.add(hat(0.16 if e % 2 else 0.24, b * 8 + e), at(t0 + e * .5) + human(rng, 0.003), 0.35, -0.3)
    for s in range(8):
        tl.add(snare(0.3 + 0.05 * s, 900 + s), at((END_CHORUS_AT - 1) * 4 + 2 + s * .25), 0.45)
    for b in (END_VERSE_AT, END_CHORUS_AT, END_CHORUS_AT + 8, END_OUTRO_AT):
        tl.add(stereo(crash(0.5, b)), at(b * 4), 0.25)
    # strings bed under the chorus
    for beat, ln, v, root in H:
        if END_CHORUS_AT * 4 <= beat:
            for k, m in enumerate(v):
                tl.add(strings(m, ln * spb, 0.5, attack=0.3, rel=0.8, voices=2, seed=k), at(beat), 0.05)
    # lead: e-piano sings the verse and pre, violin + flute (octave up) the chorus
    ep = lambda m, d, v: epiano(m, d, v, bright=1.2)
    violin = lambda m, d, v: strings(m, d, v, attack=0.06, rel=0.4, solo=True, seed=3)
    for beat, m, ln in end_tune():
        chorus = beat >= END_CHORUS_AT * 4
        tl.add((violin if chorus else ep)(m, ln * spb * 0.95, 0.72 * rng.uniform(0.9, 1.0)), at(beat) + human(rng, 0.006),
               0.55 if chorus else 0.6, 0.05)
    for beat, m, ln in end_tune():
        if beat >= END_CHORUS_AT * 4:
            tl.add(flute(m + 12, ln * spb * 0.95, 0.72 * rng.uniform(0.9, 1.0), seed=5), at(beat) + human(rng, 0.006),
                   0.28, 0.25)
    # outro: the motif in C on bell, then the chords ring
    for bi, bar in enumerate(END_OUTRO):
        for b, m, ln in bar:
            tl.add(bell(m + 12, ln * spb, 0.7), at((END_OUTRO_AT + bi) * 4 + b), 0.4, 0.15)
    for beat, ln, v, root in H:
        if beat >= END_OUTRO_AT * 4:
            for k, m in enumerate(v + [root + 12]):
                tl.add(piano(m, ln * spb * 0.95, 0.5), at(beat) + k * 0.02, 0.3, -0.3 + 0.2 * k)
    music = circ_filter(tl.loop(), "highpass", 35, 2)
    return reverb(music, reverb_ir(2.0, damp_hz=5000, seed=7), wet=0.22)


# ============================================================== game: the fast minigame loop (was the first tic-tac-toe loop)
# 174 bpm, 88 bars = 2:01, the only fast loop of the dream:
#   intro    4  Am9 Am9 Dm9 G9sus: woodblock "tic-tac" eighths, four on the floor, snare roll
#   theme A1 16 MEL_A with doubled note values over PROG_A (two bars per chord): chip lead + piano an octave down
#   theme B1 16 MEL_B the same way over PROG_B: flute, chip an octave up, strings bed; ends on E7b9
#   bridge   36 the author's hummed riff (kawaii.mid, 174 bpm, C# minor), kept as he sang it: power-chord + bass
#               stabs (GAME_RIFF: C#-C# on the one, the A-B climb back to C# a bar later, a bar of silence) over his
#               half-time groove (kick 1, "and" of 1, 2 and the last eighth, snare on 3, open hat on the "and" of 3
#               every other bar). Over it a written overdriven lead (GAME_SOLO): his opening F#-B lick, its answer,
#               runs, Kuni's theme in C# minor (MEL_A +4, bars 17-24), a climb to G#6. From bar 17 the snare goes to
#               2 and 4 and the hats to eighths. Bars 33-36 are his drum break (kicks on every beat, snare on the
#               "and" of 2 and 4): A B E E7 chugged in eighths, and the E7 falls deceptively into the theme's Fmaj9
#   theme A2 16 the theme on the lead guitar, chip an octave up, bell on the long notes, the full band; its G9sus
#               rolls into the intro's Am9
GAME_BPM = 174
GAME_SPB = 60 / GAME_BPM
GAME_VARIANT = "guitar"  # how the bridge and the reprise are played: guitar | chip | baroque
GAME_SECTIONS = [("intro", 4), ("a1", 16), ("b1", 16), ("bridge", 36), ("a2", 16)]
GAME_CH = {
    "C#m": ([56, 61, 64, 68], 37), "B": ([54, 59, 63, 66], 47), "A": ([57, 61, 64, 69], 45),
    "E": ([56, 59, 64, 68], 40), "E7": ([56, 59, 62, 64], 40), "E7b9": CH["E7b9"],
}
GAME_BRIDGE_HARM = [
    [(0, "C#m"), (1, {5: "E", 13: "E", 29: "B"}.get(i, "A")), (3, "B")] if i % 4 == 1 else [(0, "C#m")]
    for i in range(32)
] + [[(0, "A")], [(0, "B")], [(0, "E")], [(0, "E7")]]
# the author's riff as he hummed it (bass track of kawaii.mid; the guitar doubles it an octave up):
# (beat from the bridge, bass midi, beats)
GAME_RIFF = [
    (0, 37, .5), (.5, 37, .5), (5, 33, .5), (5.5, 35, .5), (6, 35, .5), (6.5, 33, .5), (7, 35, 1), (8, 37, .5),
    (8.5, 37, .5), (16, 37, .5), (16.5, 37, .5), (21, 32, .5), (21.5, 35, .5), (22, 35, 1), (23, 35, 1), (24, 37, .5),
    (24.5, 37, .5), (32, 37, .5), (32.5, 37, .5), (37, 33, .5), (37.5, 35, .5), (38, 35, .5), (38.5, 33, .5),
    (39, 35, 1), (40, 37, .5), (40.5, 37, .5), (48, 36, .5), (48.5, 37, .5), (53, 33, .5), (53.5, 35, .5), (54, 35, 1),
    (55, 35, 1), (56, 37, .5), (56.5, 37, .5), (64, 37, .5), (64.5, 37, .5), (69, 33, .5), (69.5, 35, 1),
    (70.5, 33, .5), (71, 35, 1), (72, 38, .5), (72.5, 37, .5), (80, 37, .5), (80.5, 37, .5), (85, 33, .5),
    (85.5, 36, .5), (86, 35, .5), (86.5, 33, .5), (87, 35, 1), (88, 37, .5), (88.5, 37, .5), (96, 37, .5),
    (96.5, 37, .5), (101, 33, .5), (101.5, 35, .5), (102, 35, .5), (102.5, 33, .5), (103, 35, 1), (104, 37, .5),
    (104.5, 37, .5), (112, 37, .5), (112.5, 37, .5), (117, 35, .5), (117.5, 35, .5), (118, 35, 1), (119, 35, 1),
    (120, 37, .5), (120.5, 37, .5),
]
# his drums per two bars (eighth -> "K" kick, "S" snare, "O" open hat); hats on every beat besides
GAME_GROOVE = ["KK.K...K", "KK..S.O."]
GAME_BREAK_GROOVE = ["..SS..S.", "..S...S."]  # bars 33-36: snares; kicks on every beat
# the lead over the riff: (beat from the bridge, midi, beats[, articulation]); "b" bend up a tone into the note,
# "h" half-tone bend, "s" slide from the previous note, "f" fall off the end. Bars 17-24 are the theme, added in
# game_solo()
GAME_SOLO_OWN = [
    # 1-4: his lick (the first bar of kawaii.mid) and its answer, in the riff's silences
    (1, 78, 1), (2, 83, 1), (3, 78, .5), (3.5, 83, .5), (4, 83, .5), (4.5, 83, 1, "b"),
    (9, 80, .5), (9.5, 83, .5), (10, 85, 1.5, "b"), (11.5, 83, .5),
    (12, 80, 1.5), (13.5, 78, .5), (14, 76, .5), (14.5, 73, 1.5, "f"),
    # 5-8: the lick again, answered higher, resting on G# over the E
    (17, 78, 1), (18, 83, 1), (19, 78, .5), (19.5, 83, .5), (20, 85, .5), (20.5, 87, .5), (21, 88, 2, "b"),
    (23, 87, .5), (23.5, 85, .5),
    (24, 83, 1), (25, 80, .5), (25.5, 83, .5), (26, 85, .5), (26.5, 83, .5), (27, 80, .5), (27.5, 78, .5),
    (28, 80, 3, "h"), (31, 76, .25), (31.25, 78, .25), (31.5, 80, .5),
    # 9-12: climbing eighths
    (32, 81, 1.5), (33.5, 80, .5), (34, 78, .5), (34.5, 80, .5), (35, 81, .5), (35.5, 83, .5),
    (36, 85, 2, "b"), (38, 83, .5), (38.5, 81, .5), (39, 83, 1),
    (40, 80, .5), (40.5, 76, .5), (41, 78, .5), (41.5, 80, .5), (42, 81, .5), (42.5, 83, .5), (43, 85, .5),
    (43.5, 87, .5),
    (44, 88, 1.5, "b"), (45.5, 87, .5), (46, 85, 1), (47, 83, .5), (47.5, 85, .5),
    # 13-16: a held C#, down to the theme's pickup
    (48, 85, 4, "h"), (52, 88, .5), (52.5, 87, .5), (53, 85, .5), (53.5, 83, .5), (54, 80, 1), (55, 83, 1),
    (56, 85, .5), (56.5, 83, .5), (57, 80, .5), (57.5, 78, .5), (58, 76, .5), (58.5, 78, .5), (59, 80, 1),
    (60, 80, 2), (62, 75, 1, "s"), (63, 76, .5), (63.5, 78, .5),
    # 25-28: sixteenth runs
    (96, 85, .5), (96.5, 88, .5), (97, 85, .25), (97.25, 83, .25), (97.5, 80, .25), (97.75, 78, .25), (98, 80, .25),
    (98.25, 83, .25), (98.5, 85, .25), (98.75, 88, .25), (99, 90, 1, "b"),
    (100, 88, .5), (100.5, 85, .5), (101, 83, .5), (101.5, 81, .5), (102, 83, 1.5, "h"), (103.5, 85, .5),
    (104, 88, .25), (104.25, 87, .25), (104.5, 85, .25), (104.75, 83, .25), (105, 85, .25), (105.25, 83, .25),
    (105.5, 80, .25), (105.75, 78, .25), (106, 80, .25), (106.25, 78, .25), (106.5, 76, .25), (106.75, 73, .25),
    (107, 76, 1),
    (108, 78, .5), (108.5, 80, .5), (109, 81, .5), (109.5, 83, .5), (110, 83, .5), (110.5, 84, .5), (111, 85, 1),
    # 29-32: the climb to G#6
    (112, 88, 3, "b"), (115, 90, .5), (115.5, 88, .5),
    (116, 87, 2, "h"), (118, 85, .5), (118.5, 87, .5), (119, 90, 1),
    (120, 92, 2, "b"), (122, 90, .5), (122.5, 88, .5), (123, 87, .5), (123.5, 85, .5),
    (124, 83, 1), (125, 85, 1), (126, 88, .5), (126.5, 87, .5), (127, 85, .5), (127.5, 83, .5),
    # 33-36: his drum break, A B E E7, into the theme's Fmaj9
    (128, 81, 2, "b"), (130, 85, .5), (130.5, 88, .5), (131, 85, .5), (131.5, 81, .5),
    (132, 83, 2, "b"), (134, 87, .5), (134.5, 90, .5), (135, 87, .5), (135.5, 83, .5),
    (136, 88, 3, "b"), (139, 86, .5), (139.5, 88, .5),
    (140, 92, 1, "h"), (141, 89, .5), (141.5, 88, .5), (142, 86, .5), (142.5, 83, .5), (143, 80, .5),
    (143.5, 76, .5, "f"),
]


def game_solo():
    """GAME_SOLO_OWN with Kuni's theme in C# minor (stretched MEL_A bars 1-4, +4 semitones) in bars 17-24."""
    theme = [(64 + bi * 4 + b, m + 4, ln, "b" if ln >= 2.5 else "")
             for bi, bar in enumerate(stretch(MEL_A[:4])) for b, m, ln in bar]
    return sorted(GAME_SOLO_OWN + theme, key=lambda nt: nt[0])


GAME_SOLO = game_solo()


def game_starts():
    out, bar = {}, 0
    for name, bars in GAME_SECTIONS:
        out[name] = bar
        bar += bars
    return out, bar


@functools.lru_cache(maxsize=None)
def _chip(m, dur, vel):
    f = midi_hz(m)
    env = adsr(dur, 0.004, 0.18, 0.7, 0.07)
    n = len(env)
    t = t_axis(n)
    vib = 0.005 * np.clip((t - 0.18) / 0.25, 0, 1) * np.sin(TAU * 5.5 * t)
    ph = TAU * np.cumsum(f * (1 + vib)) / SR
    duty = 0.3
    x = sum(np.sin(np.pi * k * duty) / k * np.sin(k * ph) for k in range(1, int(7000 / f) + 1))
    return x * env * vel * 0.5


def chip(m, dur, vel):
    """Band-limited 30% pulse lead with a little delayed vibrato: the "game" colour. Cached."""
    return _chip(float(m), round(dur, 3), round(vel * 20) / 20)


def woodblock(high=True, vel=0.6, seed=0):
    n = n_samples(0.12)
    t = t_axis(n)
    f = 1750.0 if high else 1180.0
    body = np.sin(TAU * f * t) * np.exp(-t / 0.018) + 0.4 * np.sin(TAU * f * 2.7 * t) * np.exp(-t / 0.008)
    click = sos_filter(noise(n, seed), "bandpass", (2000, 7000), 2) * np.exp(-t / 0.002)
    return (body + 0.5 * click) * (1 - np.exp(-t / 0.0005)) * vel


def open_hat(vel=0.3, seed=0):
    n = n_samples(0.3)
    x = sos_filter(noise(n, seed), "highpass", 6500, 4)
    return x * np.exp(-t_axis(n) / 0.09) * (1 - np.exp(-t_axis(n) / 0.001)) * vel


def amp_cab(x, drive, sr2, tone_hz=4200.0):
    """Overdrive and a 4x12-ish cabinet, run at 2x rate; returns at SR."""
    x = signal.sosfilt(signal.butter(1, 350, "highpass", fs=sr2, output="sos"), x)  # tight low end into the amp
    x = np.tanh(drive * x) + 0.08 * np.tanh(drive * 3 * x)
    x = signal.sosfilt(signal.butter(4, tone_hz, "lowpass", fs=sr2, output="sos"), x)
    x = signal.sosfilt(signal.butter(2, 90, "highpass", fs=sr2, output="sos"), x)
    x = signal.resample_poly(x, 1, 2)
    peak = signal.sosfilt(signal.butter(2, (1300, 2600), "bandpass", fs=SR, output="sos"), x)
    return x + 0.6 * peak


def lead_guitar(notes, vel=0.8, seed=0):
    """One legato phrase of an overdriven lead guitar. notes: [(sec, midi, sec, art)], art as in GAME_SOLO.
    The pitch glides between notes, bends rise into the note, long notes get a wide vibrato. Stereo."""
    sr2 = 2 * SR
    end = notes[-1][0] + notes[-1][2] + (0.35 if notes[-1][3] == "f" else 0.12)
    n = int(end * sr2) + 1
    t = np.arange(n) / sr2
    pitch = np.full(n, float(notes[0][1]))
    env = np.zeros(n)
    prev_m = notes[0][1]
    for i, (s, m, d, art) in enumerate(notes):
        a, b = int(s * sr2), min(n, int((s + d) * sr2))
        tt = t[a:b] - s
        p = np.full(b - a, float(m))
        if art in ("b", "h"):  # bend up into the note
            depth = 2.0 if art == "b" else 1.0
            p -= depth * np.clip(1 - tt / 0.11, 0, 1) ** 2
        elif art == "s" or i > 0:  # slide (long) or a quick legato glide from the previous note
            g = 0.07 if art == "s" else 0.012
            p += (prev_m - m) * np.exp(-tt / g)
        if d > 0.35:  # vibrato after the note settles
            p += 0.3 * np.clip((tt - 0.18) / 0.3, 0, 1) * np.sin(TAU * 5.6 * tt)
        pitch[a:b] = p
        # each note is picked: quick attack, settles, sustains (overdrive compresses it anyway)
        e = 0.75 + 0.25 * np.exp(-tt / 0.15)
        e *= 1 - 0.5 * np.exp(-tt / 0.004)
        env[a:b] = e * np.exp(-tt / 6.0)
        prev_m = m
    s, m, d, art = notes[-1]
    a = min(n, int((s + d) * sr2))
    tail = np.maximum(t[a:] - (s + d), 0)
    if art == "f":  # fall off the end: the pitch drops while the note dies
        pitch[a:] = m - 5 * (tail / 0.35) ** 1.5
        env[a:] = env[a - 1] * np.exp(-tail / 0.12)
    else:
        pitch[a:] = pitch[a - 1]
        env[a:] = env[a - 1] * np.exp(-tail / 0.025)
    env = signal.sosfilt(signal.butter(1, 400, "lowpass", fs=sr2, output="sos"), env)
    f = 440.0 * 2 ** ((pitch - 69) / 12)
    ph = TAU * np.cumsum(f) / sr2
    kmax = int(12000 / f.max())
    x = sum((np.sin(k * ph) / k) * (1.0 if k % 2 else 0.7) for k in range(1, kmax + 1))
    x = x * env * vel
    y = amp_cab(x, 6.0, sr2, tone_hz=4600.0)
    y = fade(y / 1.4, 0.002, 0.02)
    # double-tracked feel: a second take a few ms late and a few cents off, panned apart
    d = n_samples(0.011)
    z = np.concatenate([np.zeros(d), y])[: len(y)]
    return np.stack([y + 0.35 * z, 0.35 * y + z], axis=1) * 0.75


def solo_phrases(notes, spb):
    """Split a solo into legato phrases at rests longer than a sixteenth."""
    out, cur = [], []
    for nt in notes:
        b, m, ln = nt[:3]
        art = nt[3] if len(nt) > 3 else ""
        if cur and b - (cur[-1][0] + cur[-1][2]) > 0.3:
            out.append(cur)
            cur = []
        cur.append((b, m, ln, art))
    out.append(cur)
    return [[((b - ph[0][0]) * spb, m, ln * spb, art) for b, m, ln, art in ph] for ph in out], [ph[0][0] for ph in out]


@functools.lru_cache(maxsize=None)
def power_chord(root, dur, muted, vel):
    """Rhythm guitar: root, fifth and octave struck together through the amp. Palm-muted hits are short and dark."""
    sr2 = 2 * SR
    ring = dur + (0.05 if muted else 0.25)
    n = int(ring * sr2)
    t = np.arange(n) / sr2
    x = np.zeros(n)
    for k, iv in enumerate((0, 7, 12)):
        f = midi_hz(root + iv) * (1 + 0.0015 * (k - 1))
        ph = TAU * f * t + k * 1.3
        x += sum(np.sin(j * ph) / j for j in range(1, int(6000 / f) + 1))
    tau = 0.09 if muted else 0.9
    env = np.exp(-t / tau) * (1 - np.exp(-t / 0.0015))
    env *= np.clip((ring - t) / 0.03, 0, 1)
    x *= env * vel
    if muted:
        x = signal.sosfilt(signal.butter(2, 900, "lowpass", fs=sr2, output="sos"), x)
    y = amp_cab(x, 5.0, sr2, tone_hz=3800.0)
    return fade(y / 1.6, 0.001, 0.01)


def game_harmony():
    """[(abs beat, beats, voicing, bass root, section)] over the whole loop."""
    st, _ = game_starts()
    out = []
    for bi, beat, seg, name in segments([[(0, "Am9")], [(0, "Am9")], [(0, "Dm9")], [(0, "G9sus")]]):
        out.append(((st["intro"] + bi) * 4 + beat, seg, *CH[name], "intro"))
    for sec, prog in (("a1", PROG_A * 2), ("b1", PROG_B * 2), ("a2", PROG_A * 2)):
        for bi, beat, seg, name in segments(prog):
            out.append(((st[sec] + bi * 2) * 4 + beat * 2, seg * 2, *CH[name], sec))
    for bi, beat, seg, name in segments(GAME_BRIDGE_HARM):
        out.append(((st["bridge"] + bi) * 4 + beat, seg, *GAME_CH[name], "bridge"))
    return out


def game():
    """The fast minigame loop: see the section comment above."""
    spb = GAME_SPB
    at = lambda beat: beat * spb
    rng = np.random.default_rng(174)
    st, total = game_starts()
    tl = Timeline(total * 4 * spb)
    sec_of = {st[name] + b: name for name, bars in GAME_SECTIONS for b in range(bars)}
    H = game_harmony()
    chord_at = lambda beat: next(h for h in reversed(H) if h[0] <= beat + 1e-6)
    guitar_root = lambda r: 40 + (r - 40) % 12
    # ---- harmony instruments
    for beat, ln, v, root, sec in H:
        v = sorted(v)
        bridge = sec == "bridge"
        rb = beat / 4 - st["bridge"]
        if sec in ("b1", "bridge"):
            for j, m in enumerate(v):
                tl.add(strings(m + 12, ln * spb, 0.5, attack=0.3, rel=0.6, voices=2, seed=j), at(beat),
                       0.055 if sec == "b1" else 0.045, -0.4 + 0.25 * j)
        for e in range(int(ln * 2)):
            t = at(beat + e * .5)
            # piano: offbeat stabs (a chord on every eighth in theme B); none under the solo's first half
            if (e % 2 == 1 or sec == "b1") and not (bridge and rb < 16):
                vel = (0.5 if e % 2 else 0.35) * rng.uniform(0.9, 1.0)
                for j, m in enumerate(v):
                    tl.add(piano(m + 12, 0.22 * spb, vel), t + j * 0.004 + human(rng, 0.003),
                           0.16 if bridge else 0.2, -0.3 + j * 0.18)
            # bass eighths with octave kicks (the bridge's bass follows its kick, below)
            if not bridge and not (sec == "intro" and e % 2):
                r = root - 12 + (12 if e % 4 == 3 else 0)
                tl.add(soft_bass(r, 0.4 * spb, 0.8 if e % 2 == 0 else 0.6), t + human(rng, 0.003), 0.55)
            # rhythm guitar: palm-muted eighths under the reprise
            if GAME_VARIANT == "guitar" and sec == "a2":
                tl.add(stereo(power_chord(guitar_root(root), round(0.42 * spb, 3), True, 0.9)),
                       t + human(rng, 0.003), 0.14)
        if bridge and GAME_VARIANT != "guitar":  # sixteenth arpeggios: chip, or the harpsichord
            pat = (0, 1, 2, 3, 2, 1, 2, 3)
            for e in range(int(ln * 4)):
                m = v[pat[e % 8]] + 12
                t = at(beat + e * .25) + human(rng, 0.002)
                if GAME_VARIANT == "chip":
                    tl.add(chip(m, 0.2 * spb, 0.6 if e % 4 == 0 else 0.45), t, 0.1, 0.3 * np.sin(e * 0.7))
                else:
                    tl.add(harpsichord(m, 0.3 * spb, 0.5 * rng.uniform(0.85, 1.0)), t, 0.15, 0.35 * np.sin(e * 0.7))
        if sec in ("a1", "a2"):  # harpsichord eighth arpeggios drive theme A
            pat = (0, 1, 2, 3, 2, 3, 1, 2)
            for e in range(int(ln * 2)):
                tl.add(harpsichord(v[pat[e % 8]] + 12, 0.4 * spb, 0.45 * rng.uniform(0.85, 1.0)),
                       at(beat + e * .5) + human(rng, 0.003), 0.12 if sec == "a2" else 0.16, 0.35 * np.sin(e * 0.9))
    # ---- the bridge: the author's riff, his drums, the break
    br = st["bridge"] * 4
    if GAME_VARIANT == "guitar":
        for b0, m, ln in GAME_RIFF:  # stabs: open power chord + bass, cut short like he sang them
            t = at(br + b0) + human(rng, 0.003)
            vel = 0.95 if b0 % 1 == 0 else 0.85
            tl.add(stereo(power_chord(m + 12, round(ln * spb * 0.85, 3), False, vel)), t, 0.13)
            tl.add(soft_bass(m, ln * spb * 0.9, vel), t, 0.62)
        for i, name in enumerate(("A", "B", "E", "E7")):  # the break: eighth chugs, open on the beat
            root = 40 + (GAME_CH[name][1] - 40) % 12
            for e in range(8):
                t = at(br + (32 + i) * 4 + e * .5) + human(rng, 0.003)
                tl.add(stereo(power_chord(root, round(0.42 * spb, 3), e % 2 == 1, 0.9)), t, 0.12 if e % 2 else 0.11)
                tl.add(soft_bass(root - 12, 0.42 * spb, 0.8 if e % 2 == 0 else 0.6), t, 0.55)
    for b in range(total):
        t0, sec = b * 4, sec_of[b]
        if sec == "bridge":
            rb = b - st["bridge"]
            brk = rb >= 32
            groove = (GAME_BREAK_GROOVE if brk else GAME_GROOVE)[rb % 2]
            for e, c in enumerate(groove):
                t = at(t0 + e * .5)
                if c == "K" or brk and e % 2 == 0:
                    tl.add(kick(0.85 if e == 0 else 0.7), t)
                if c == "S" and (brk or rb < 16):
                    tl.add(snare(0.6, b * 8 + e), t + human(rng, 0.003), 0.45, 0.05)
                if c == "O":
                    tl.add(open_hat(0.3, b * 8 + e), t + human(rng, 0.002), 0.3, -0.3)
            if 16 <= rb < 32:  # the second half drives: backbeat on 2 and 4
                for s in (1, 3):
                    tl.add(snare(0.6, b * 4 + s), at(t0 + s) + human(rng, 0.003), 0.45, 0.05)
            if GAME_VARIANT == "baroque":
                _, _, _, root, _ = chord_at(t0)
                tl.add(timpani(root - 12 + (12 if root < 40 else 0), 0.8), at(t0), 0.5)
            if GAME_VARIANT == "chip":  # the tic-tac goes on under the chip solo
                for e in range(8):
                    tl.add(woodblock(e % 2 == 0, 0.3, b * 8 + e), at(t0 + e * .5) + human(rng, 0.002),
                           0.3, 0.45 if e % 2 == 0 else -0.45)
            steps = 4 if rb < 16 else 8
            for e in range(steps):
                pos = e * 4 / steps
                if groove[int(pos * 2)] == "O":
                    continue
                v = 0.2 if pos % 1 == 0 else 0.13
                tl.add(hat(v, b * 16 + e), at(t0 + pos) + human(rng, 0.002), 0.35, -0.3)
            continue
        kicks = {"intro": (0, 1, 2, 3), "a1": (0, 2.5), "b1": (0, 1.5, 2.5), "a2": (0, 1.5, 2, 2.5)}[sec]
        for kk in kicks:
            tl.add(kick(0.8 if kk == 0 else 0.65), at(t0 + kk))
        if sec != "intro":
            for s in (1, 3):
                tl.add(snare(0.55, b * 4 + s), at(t0 + s) + human(rng, 0.003), 0.42, 0.05)
        steps = 16 if sec == "a2" else 8
        for e in range(steps):
            pos = e * 4 / steps
            v = 0.22 if pos % 1 == 0 else 0.15 if pos % .5 == 0 else 0.1
            tl.add(hat(v, b * 16 + e), at(t0 + pos) + human(rng, 0.002), 0.35, -0.3)
        if sec == "intro":  # tic-tac: high on the beat, low off it
            for e in range(8):
                tl.add(woodblock(e % 2 == 0, 0.5, b * 8 + e), at(t0 + e * .5) + human(rng, 0.002),
                       0.3, 0.45 if e % 2 == 0 else -0.45)
    for name, bars in GAME_SECTIONS:  # a roll into every section, a crash on every downbeat of one
        end = st[name] + bars
        for s in range(8):
            tl.add(snare(0.25 + 0.05 * s, 700 + end * 8 + s), at(end * 4 - 2 + s * .25), 0.42)
        if name != "intro":
            tl.add(stereo(crash(0.45, st[name])), at(st[name] * 4), 0.22)
    for b in (8, 16, 24, 32):
        tl.add(stereo(crash(0.4, 900 + b)), at((st["bridge"] + b) * 4), 0.2)
    for b in (4, 8, 12):
        tl.add(stereo(crash(0.35, 950 + b)), at((st["a2"] + b) * 4), 0.18)
    # ---- the theme
    theme_a, theme_b = stretch(MEL_A), stretch(MEL_B)
    place(tl, rng, theme_a, st["a1"], GAME_BPM, chip, gain=0.32, vel=0.8, jitter=0.004)
    place(tl, rng, theme_a, st["a1"], GAME_BPM, lambda m, d, v: piano(m - 12, d, v), gain=0.3, vel=0.7, pan_pos=-0.1,
          jitter=0.004)
    place(tl, rng, theme_b, st["b1"], GAME_BPM, lambda m, d, v: flute(m, d, v, seed=9), gain=0.42, vel=0.8,
          pan_pos=0.15, jitter=0.004)
    place(tl, rng, theme_b, st["b1"], GAME_BPM, lambda m, d, v: chip(m + 12, d, v), gain=0.13, vel=0.7,
          pan_pos=-0.2, jitter=0.004)
    # ---- the solo, then the theme on the same instrument
    br, a2 = st["bridge"] * 4, st["a2"] * 4
    theme_notes = [(bi * 4 + b, m, ln) for bi, bar in enumerate(theme_a) for b, m, ln in bar]
    violin = lambda m, d, v: strings(m, d, v, attack=0.04, rel=0.3, solo=True, seed=8)
    if GAME_VARIANT == "guitar":
        phrases, starts = solo_phrases(GAME_SOLO, spb)
        for ph, b0 in zip(phrases, starts):
            tl.add(lead_guitar(ph, 0.8, seed=int(b0 * 4)), at(br + b0) + human(rng, 0.003), 0.26)
        phrases, starts = solo_phrases([(b, m - 12 if m > 82 else m, ln, "b" if ln >= 2.5 else "")
                                        for b, m, ln in theme_notes], spb)
        for ph, b0 in zip(phrases, starts):
            tl.add(lead_guitar(ph, 0.8, seed=500 + int(b0 * 4)), at(a2 + b0) + human(rng, 0.003), 0.22)
        place(tl, rng, theme_a, st["a2"], GAME_BPM, chip, gain=0.12, transpose=12, vel=0.7, pan_pos=0.25,
              jitter=0.004)
    else:
        for nt in GAME_SOLO:
            b0, m, ln = nt[:3]
            t = at(br + b0) + human(rng, 0.003)
            if GAME_VARIANT == "chip":
                tl.add(chip(m, ln * spb * 0.92, 0.8), t, 0.34, 0.05)
                tl.add(chip(m - 12, ln * spb * 0.92, 0.7), t + 0.008, 0.1, -0.3)
            else:
                tl.add(violin(m, ln * spb, 0.75), t, 0.5, 0.1)
                tl.add(harpsichord(m, min(ln, 1) * spb, 0.5), t, 0.12, -0.25)
        if GAME_VARIANT == "chip":
            place(tl, rng, theme_a, st["a2"], GAME_BPM, chip, gain=0.32, vel=0.8, jitter=0.004)
            place(tl, rng, theme_a, st["a2"], GAME_BPM, lambda m, d, v: piano(m - 12, d, v), gain=0.3, vel=0.7,
                  pan_pos=-0.1, jitter=0.004)
            place(tl, rng, theme_a, st["a2"], GAME_BPM, lambda m, d, v: chip(m + 12, d, v), gain=0.1, vel=0.7,
                  pan_pos=0.3, jitter=0.004)
        else:
            sect = lambda m, d, v: strings(m, d, v, attack=0.05, rel=0.35, voices=3, seed=11)
            place(tl, rng, theme_a, st["a2"], GAME_BPM, sect, gain=0.38, vel=0.8, jitter=0.004)
            place(tl, rng, theme_a, st["a2"], GAME_BPM, sect, gain=0.22, transpose=-12, vel=0.75, jitter=0.004)
    for nt in GAME_SOLO:  # the bell rings the solo's long notes two octaves up
        if nt[2] >= 1.5:
            tl.add(bell(nt[1] + 12, 1.0, 0.5, rel=1.2), at(br + nt[0]) + 0.02, 0.1, -0.35)
    sparkle = [[nt for nt in bar if nt[2] >= 2] for bar in theme_a]
    place(tl, rng, sparkle, st["a2"], GAME_BPM, lambda m, d, v: bell(m + 12, min(d, 1.0), v, rel=1.2), gain=0.22,
          vel=0.6, pan_pos=-0.3)
    # ---- bells, saved for the second half: they come in with the bridge's riff, and Kuni's collar bell shakes
    # like a tambourine from the middle of the bridge on; the intro and both first themes have none
    glock = lambda m, d, v: bell(m, min(d, 0.6), v, rel=0.9)
    for beat, ln, v, root, sec in H:  # the reprise: off-beat chord tones climbing and falling two octaves up
        if sec != "a2":
            continue
        top = sorted(v)[-3:]
        for e in range(int(ln)):
            tl.add(glock(top[(0, 1, 2, 1)[e % 4]] + 24, .5 * spb, 0.5 if e % 2 else 0.6),
                   at(beat + e + .5) + human(rng, 0.002), 0.06, 0.45 * np.sin(beat + e * 1.3))
    for b0, m, ln in GAME_RIFF:  # the bridge: a bell chimes with each C# stab of the riff, and in its silent bar
        if b0 % 8 == 0:
            for j, mm in enumerate((m + 36, m + 43, m + 48)):
                tl.add(glock(mm, spb, 0.55), at(br + b0 + 1 + j * .5) + human(rng, 0.002), 0.07, -0.4 + 0.4 * j)
    jingles = [stereo(jingle(np.random.default_rng(1740 + k), f0=3300.0 + 120 * k, strikes=2,
                             spacing=(0.012, 0.025), decay=0.6)) for k in range(4)]
    for b in range(total):  # the collar bell on 2 and 4 wherever the band plays its backbeat
        sec, rb = sec_of[b], b - st["bridge"]
        if sec == "a2" or sec == "bridge" and 16 <= rb < 32:
            for s in (1, 3):
                tl.add(jingles[(b * 2 + s) % 4], at(b * 4 + s) + human(rng, 0.002), 0.09 if sec == "a1" else 0.12)
    music = circ_filter(tl.loop(), "highpass", 35, 2)
    music = music + 0.12 * delay_echo(music, 0.75 * spb, feedback=0.3, taps=3, lp_hz=3500)
    music = reverb(music, reverb_ir(1.6, damp_hz=5000, seed=74), wet=0.18)
    return circ_filter(np.tanh(music * 1.2) / 1.2, "lowpass", 13000, 2)


# ============================================================== tic-tac-toe minigame (II.3½ `e2e4`): the calm one
# 80 bpm, 44 bars = 2:12. A board game at night, not a race: e-piano, brushes, a quiet woodblock tic-tac.
#   intro  4  PROG_A on e-piano, the tic-tac alone
#   A      8  MEL_A on a bright e-piano (original note values), brushes, swung hats, bass
#   B      8  MEL_B on flute over PROG_B, strings bed
#   bridge 16 new material, in turns like the game itself: one bar the e-piano "moves" (a short rising figure),
#             the next the flute answers (a falling one), and a woodblock knock after each move puts a piece down.
#             Bb - C/Bb - Am7 - Dm9 - Gm9 - C9sus - Fmaj7 - F/A, then the minor iv (Bbm6) and D7b9; in bars 13-16
#             the two play together in thirds over Gm9 C7sus Esus E7b9, and the E7b9 falls into the theme's Fmaj9.
#             Only a kick on the one under it, the drums thin out
#   A'     8  the theme on the music box (the bells come only now), flute an octave down, glockenspiel arpeggios
TTT_BPM = 80
TTT_SECTIONS = [("intro", 4), ("a", 8), ("b", 8), ("bridge", 16), ("a2", 8)]
TTT_CH = dict(CH) | {
    "Bbmaj7": ([53, 57, 58, 62], 46), "C/Bb": ([52, 55, 60, 64], 46), "Gm9": ([53, 57, 58, 62], 43),
    "C9sus": ([53, 55, 58, 62], 36), "Fmaj7": ([52, 57, 60, 64], 41), "F/A": ([52, 57, 60, 64], 45),
    "Bbm6": ([53, 55, 58, 61], 46), "D7b9": ([54, 57, 60, 63], 38), "C7sus": ([53, 55, 58, 60], 36),
}
TTT_BRIDGE_HARM = ["Bbmaj7", "C/Bb", "Am7", "Dm9", "Gm9", "C9sus", "Fmaj7", "F/A",
                   "Bbmaj7", "Bbm6", "Am7", "D7b9", "Gm9", "C7sus", "Esus", "E7b9"]
# per bridge bar: (e-piano notes, flute notes), each [(beat, midi, beats)]
TTT_BRIDGE_MEL = [
    ([(0, 74, .5), (.5, 77, .5), (1, 81, 2.5)], []),
    ([], [(0, 79, 1), (1, 76, 1), (2, 74, 2)]),
    ([(0, 72, .5), (.5, 76, .5), (1, 79, 2.5)], []),
    ([], [(0, 77, 1), (1, 76, 1), (2, 69, 2)]),
    ([(0, 70, .5), (.5, 74, .5), (1, 77, 1), (2, 81, 1.5)], []),
    ([], [(0, 79, 1.5), (1.5, 77, .5), (2, 74, 1), (3, 72, 1)]),
    ([(0, 76, .5), (.5, 77, .5), (1, 79, .5), (1.5, 81, 2)], []),
    ([], [(0, 84, 2), (2, 81, 1), (3, 79, 1)]),
    ([(0, 77, .5), (.5, 81, .5), (1, 84, 2.5)], []),
    ([], [(0, 82, 1), (1, 79, 1), (2, 77, 2)]),
    ([(0, 76, .5), (.5, 79, .5), (1, 84, 2.5)], []),
    ([], [(0, 81, 1), (1, 78, 1), (2, 75, 1), (3, 72, 1)]),
    ([(0, 74, 1), (1, 77, 1), (2, 81, 2)], [(0, 70, 1), (1, 74, 1), (2, 77, 2)]),
    ([(0, 79, 1), (1, 77, 1), (2, 74, 2)], [(0, 72, 1), (1, 74, 1), (2, 70, 2)]),
    ([(0, 76, 2), (2, 74, 1), (3, 71, 1)], [(0, 69, 4)]),
    ([(0, 68, 2), (2, 71, 1), (3, 74, 1)], [(0, 65, 2), (2, 68, 2)]),
]


def ttt_harmony():
    """[(abs beat, beats, voicing, bass root, section)] over the whole loop."""
    out, bar = [], 0
    for sec, bars in TTT_SECTIONS:
        prog = PROG_B * 2 if sec == "b" else [[(0, n)] for n in TTT_BRIDGE_HARM] if sec == "bridge" else \
            PROG_A * (bars // 4)
        for bi, beat, seg, name in segments(prog):
            v, r = TTT_CH[name]
            out.append(((bar + bi) * 4 + beat, seg, sorted(v), r, sec))
        bar += bars
    return out


def tictactoe():
    """The tic-tac-toe minigame with e2e4: see the section comment above."""
    spb = 60 / TTT_BPM
    at = lambda beat: beat * spb
    rng = np.random.default_rng(100)
    st, bar = {}, 0
    for name, bars in TTT_SECTIONS:
        st[name] = bar
        bar += bars
    total = bar
    sec_of = {st[name] + b: name for name, bars in TTT_SECTIONS for b in range(bars)}
    tl = Timeline(total * 4 * spb)
    lead = Timeline(total * 4 * spb)
    # ---- e-piano comping, bass, strings
    for beat, ln, v, root, sec in ttt_harmony():
        hits = [(0, min(ln, 2.5), 0.4), (2.5, 1.5, 0.28)] if ln >= 4 else [(0, ln, 0.38)]
        if sec == "bridge":
            hits = [(0, ln, 0.3)]  # one soft chord a bar: the turns have the room
        for off, hl, vel in hits:
            for k, m in enumerate(v):
                tl.add(epiano(m, hl * spb * 0.95, vel * rng.uniform(0.9, 1.05), bright=0.8),
                       at(beat + off) + k * 0.016 + human(rng, 0.006), 0.42, (k - 1.5) * 0.25)
        if sec != "intro" or beat >= 8:  # the bass comes in halfway through the intro
            bass = [(0, min(ln, 2.5) * 0.9, 0.65)] + ([(2.5, 1.3, 0.5)] if ln >= 4 and sec != "bridge" else [])
            for off, bl, vel in bass:
                tl.add(soft_bass(root, bl * spb, vel), at(beat + off) + human(rng, 0.005), 0.42)
        if sec in ("b", "bridge"):
            for j, m in enumerate(v):
                tl.add(strings(m + 12, ln * spb, 0.45, attack=0.5, rel=0.8, voices=2, seed=30 + j), at(beat),
                       0.04, -0.4 + 0.25 * j)
        if sec == "a2":  # glockenspiel: off-beat chord tones two octaves up
            top = v[-3:]
            for e in range(int(ln)):
                tl.add(bell(top[(0, 1, 2, 1)[e % 4]] + 24, 0.3, 0.5, rel=0.9),
                       at(beat + e + .5) + human(rng, 0.002), 0.05, 0.45 * np.sin(beat + e * 1.3))
    # ---- drums and the tic-tac
    for b in range(total):
        t0, sec = b * 4, sec_of[b]
        if sec == "intro" or sec == "bridge":  # tic-tac on the beats, high-low
            for e in range(4):
                tl.add(woodblock(e % 2 == 0, 0.35, b * 4 + e), at(t0 + e) + human(rng, 0.002),
                       0.3 if sec == "intro" else 0.14, 0.4 if e % 2 == 0 else -0.4)
        if sec == "intro":
            continue
        tl.add(kick(0.5), at(t0) + human(rng, 0.004))
        if sec == "bridge":
            continue
        tl.add(kick(0.38), at(t0 + 2.5) + human(rng, 0.004))
        tl.add(brush(0.2, seed=b), at(t0 + 1), 0.9, 0.1)
        tl.add(brush(0.22, seed=b + 99), at(t0 + 3), 0.9, 0.1)
        for e in range(8):
            sw = 0.09 if e % 2 else 0.0
            tl.add(hat(0.06 if e % 2 else 0.09, seed=b * 8 + e), at(t0 + e * .5 + sw) + human(rng, 0.004), 0.8,
                   -0.3)
    # ---- the theme
    ep = lambda m, d, v: epiano(m, d, v, bright=1.1)
    fl = lambda m, d, v: flute(m, d, v, seed=5)
    place(lead, rng, MEL_A, st["a"], TTT_BPM, ep, gain=0.62, pan_pos=0.05)
    place(lead, rng, MEL_B, st["b"], TTT_BPM, fl, gain=0.5, vel=0.75, pan_pos=0.1)
    place(lead, rng, MEL_A, st["a2"], TTT_BPM, lambda m, d, v: bell(m + 12, min(d, 1.2), v, rel=1.4), gain=0.42,
          vel=0.7, pan_pos=-0.1)
    place(lead, rng, MEL_A, st["a2"], TTT_BPM, fl, gain=0.3, transpose=-12, vel=0.65, pan_pos=0.2)
    # ---- the bridge: turns, a knock after each move
    for bi, (xs, os) in enumerate(TTT_BRIDGE_MEL):
        place(lead, rng, [xs], st["bridge"] + bi, TTT_BPM, ep, gain=0.6, pan_pos=-0.25)
        place(lead, rng, [os], st["bridge"] + bi, TTT_BPM, fl, gain=0.5, vel=0.75, pan_pos=0.25)
        if bi < 12:
            tl.add(woodblock(bi % 2 == 0, 0.55, 300 + bi), at((st["bridge"] + bi) * 4 + 3.5), 0.3,
                   -0.5 if bi % 2 == 0 else 0.5)
    lead_buf = lead.loop()
    lead_buf = lead_buf + 0.4 * delay_echo(lead_buf, spb * 0.75, 0.3, 3)
    music = circ_filter(tl.loop() + lead_buf, "highpass", 35, 2)
    music = reverb(music, reverb_ir(2.2, damp_hz=4500, seed=101), wet=0.26)
    return circ_filter(np.tanh(music * 1.3) / 1.3, "lowpass", 11000, 2)


def fire_layer(n, seed=91):
    """Fireplace: low roar, soft hiss, dense small crackles, a few louder pops. Loop-safe."""
    rng = np.random.default_rng(seed)
    sec = n / SR
    roar = colored_noise(n, lambda f: butter_mag(f, "bandpass", (40, 350), 2) / np.maximum(f, 20) ** 0.5,
                         seed=seed, channels=2, correlation=0.6)
    roar *= (1 + 0.3 * smooth_random(n, 14, seed=seed + 1))[:, None]
    hiss = colored_noise(n, lambda f: butter_mag(f, "bandpass", (1500, 6000), 2), seed=seed + 2,
                         channels=2, correlation=0.2)
    hiss *= (0.6 + 0.4 * smooth_random(n, 40, seed=seed + 3))[:, None]
    tl = Timeline(sec, tail=2)
    t = 0.0
    while t < sec:  # crackles come in little clusters
        t += rng.exponential(0.11)
        for _ in range(rng.integers(1, 4)):
            d = n_samples(rng.uniform(0.001, 0.006))
            c = sos_filter(noise(d + 200, rng.integers(1 << 30)), "highpass", rng.uniform(1200, 3500), 2)
            c *= np.exp(-t_axis(d + 200) / (d / SR / 2))
            tl.add(c, (t + rng.uniform(0, 0.03)) % sec, rng.exponential(0.12), rng.uniform(-0.7, 0.7))
    t = 0.0
    while t < sec:  # pops: a resin pocket bursting
        t += rng.exponential(2.4)
        m = n_samples(0.12)
        tt = t_axis(m)
        thump = np.sin(TAU * rng.uniform(140, 260) * tt) * np.exp(-tt / 0.012)
        burst = sos_filter(noise(m, rng.integers(1 << 30)), "highpass", 900, 2) * np.exp(-tt / 0.006)
        tl.add(thump * 0.5 + burst, t % sec, rng.uniform(0.35, 0.7), rng.uniform(-0.5, 0.5))
    return roar * 0.6 + hiss * 0.06 + tl.loop()


def fireplace():
    return fire_layer(n_samples(30.0))


def tender_fire():
    """`tender` with the fireplace under it (chapter 1, scene 1.4 and other evenings by the fire):
    the player has only one music channel, so the bed is baked in."""
    m = tender()
    f = fire_layer(len(m), seed=92)
    return m / rms(m) + f / rms(f) * db(-14)


def car_layer(n, seed=95):
    """Inside an old American car on a country road: V8 burble, road roar, tyre hiss, bumps."""
    rng = np.random.default_rng(seed)
    sec = n / SR
    t = t_axis(n)
    f0 = round(46.0 * sec) / sec  # crank-ish rate, integer cycles per loop
    eng = np.zeros(n)
    for h, a in ((1, 0.5), (2, 1.0), (3, 0.35), (4, 0.6), (6, 0.25), (8, 0.15)):
        ph = TAU * f0 * h * t + h * 0.6 / (2 / sec) * np.sin(TAU * 2 * t / sec + 0.4)
        eng += a * np.sin(ph)
    eng *= 1 + 0.15 * periodic_lfo(n, 5, 1.0)
    eng = circ_filter(eng / rms(eng), "lowpass", 900, 2)
    road = colored_noise(n, lambda f: butter_mag(f, "bandpass", (25, 450), 2) / np.maximum(f, 20) ** 0.4,
                         seed=seed, channels=2, correlation=0.8)
    road *= (1 + 0.2 * smooth_random(n, 8, seed=seed + 1))[:, None]
    tyre = colored_noise(n, lambda f: butter_mag(f, "bandpass", (400, 2500), 2), seed=seed + 2,
                         channels=2, correlation=0.4)
    tl = Timeline(sec, tail=2)
    t0 = 1.5
    while t0 < sec:
        m = n_samples(0.5)
        tt = t_axis(m)
        thud = np.sin(TAU * rng.uniform(45, 70) * tt) * np.exp(-tt / 0.1) * (1 - np.exp(-tt / 0.005))
        rattle = sos_filter(noise(m, rng.integers(1 << 30)), "bandpass", (700, 2500), 2) * np.exp(-tt / 0.04)
        tl.add(thud + rattle * 0.25, t0, rng.uniform(0.6, 1.0), rng.uniform(-0.2, 0.2))
        if rng.uniform() < 0.5:  # back wheels hit it too
            tl.add(thud * 0.7 + rattle * 0.2, t0 + 0.18, rng.uniform(0.4, 0.7))
        t0 += rng.uniform(3.0, 7.0)
    return stereo(eng) * 0.35 + road * 0.8 + tyre * 0.08 + tl.loop() * 0.9


def car():
    return car_layer(n_samples(24.0))


# ---------------------------------------------------------------- dream SFX

def pop():
    """Chat message bubble popping in: a soft rising blip."""
    n = n_samples(0.14)
    t = t_axis(n)
    f = 480 + 700 * (1 - np.exp(-t / 0.018))
    x = sine(f, n) * np.exp(-t / 0.035) + 0.25 * sine(2 * f, n) * np.exp(-t / 0.015)
    x *= 1 - np.exp(-t / 0.0015)
    return fade(room(stereo(x), 0.15, 0.1), 0.001, 0.02)[: n_samples(0.2)]


def remember():
    """The 'X will remember this.' plate: a falling fourth on two bells over a low glass swell."""
    tl = Timeline(3.2, tail=4)
    tl.add(bell(76, 0.6, 0.7, rel=2.0), 0.02, 0.5, 0.15)
    tl.add(bell(71, 1.2, 0.65, rel=2.5), 0.36, 0.55, -0.15)
    tl.add(glass(52, 1.0, 0.7, attack=0.25, rel=1.8), 0.0, 0.6)
    tl.add(glass(59, 1.0, 0.5, attack=0.35, rel=1.8), 0.05, 0.4)
    x = reverb(tl.oneshot(), reverb_ir(2.5, damp_hz=4000, seed=13), wet=0.45, loop=False)
    return fade(x, 0.002, 0.6)[: n_samples(3.2)]

def jingle(rng, f0=3300.0, strikes=3, spacing=(0.03, 0.07), decay=0.75):
    ratios = np.array([1.0, 1.52, 2.11, 2.68, 3.33])
    amps = np.array([1.0, 0.6, 0.45, 0.25, 0.15])
    decays = np.array([0.5, 0.32, 0.22, 0.15, 0.09])
    tl = Timeline(1.0, tail=1.5)
    t = 0.01
    for s in range(strikes):
        n = n_samples(0.9)
        tt = t_axis(n)
        v = decay ** s * rng.uniform(0.8, 1.0)
        tone = sum(a * np.sin(TAU * f0 * r * rng.uniform(0.998, 1.002) * tt + rng.uniform(0, TAU))
                   * np.exp(-tt / d) for r, a, d in zip(ratios, amps, decays))
        tone += 0.5 * noise(n, s + 100) * np.exp(-tt / 0.0008)
        tl.add(tone * v, t, 0.3, rng.uniform(-0.15, 0.15))
        t += rng.uniform(*spacing)
    return tl.oneshot()


def bell_collar():
    """Kuni's choker bell up close: a light, dry double tinkle (she moves / turns her head)."""
    rng = np.random.default_rng(72)
    x = sos_filter(jingle(rng, 3300.0, 3), "lowpass", 10000, 2)
    return fade(room(x, 0.3, 0.15), 0.001, 0.15)[: n_samples(0.9)]


def latch(rng, f=2200.0):
    n = n_samples(0.08)
    t = t_axis(n)
    return (sos_filter(noise(n, rng.integers(1 << 30)), "highpass", 1500, 2) * np.exp(-t / 0.002)
            + 0.4 * np.sin(TAU * f * t) * np.exp(-t / 0.015) + 0.3 * np.sin(TAU * f * 1.7 * t) * np.exp(-t / 0.01))


def creak(rng, dur=1.1, r0=70, r1=190):
    """Hinge creak: stick-slip pulse train through wooden resonances."""
    n = n_samples(dur)
    u = np.linspace(0, 1, n)
    rate = r0 + (r1 - r0) * np.sin(np.pi * u * 0.8) + 15 * smooth_random(n, 6, seed=int(rng.integers(99)),
                                                                          circular=False)
    phase = np.cumsum(rate) / SR
    train = (np.diff(np.floor(phase), prepend=0) > 0).astype(float)
    train *= rng.uniform(0.6, 1.0, n)
    res = sum(g * sos_filter(train, "bandpass", (f * 0.85, f * 1.15), 2)
              for f, g in ((650, 1.0), (1300, 0.7), (2500, 0.35)))
    env = np.sin(np.pi * u) ** 0.6
    return res * env


def door():
    """Old wooden door opening: latch, long hinge creak."""
    rng = np.random.default_rng(81)
    tl = Timeline(1.8, tail=1)
    tl.add(latch(rng), 0.02, 0.8, 0.2)
    tl.add(latch(rng, 1800), 0.09, 0.5, 0.2)
    c = creak(rng, 1.2)
    tl.add(c / np.max(np.abs(c)), 0.2, 0.75, 0.1)
    x = reverb(tl.oneshot(), reverb_ir(0.8, predelay=0.01, damp_hz=4000, seed=14), wet=0.3, loop=False)
    return fade(x, 0.001, 0.2)[: n_samples(1.9)]


def door_close():
    """Heavy wooden door shutting: push of air, thud, latch."""
    rng = np.random.default_rng(82)
    tl = Timeline(1.0, tail=1)
    n = n_samples(0.35)
    t = t_axis(n)
    air = sos_filter(noise(n, 3), "lowpass", 400, 2) * np.sin(np.pi * t / 0.35) ** 2 * 0.3
    tl.add(air, 0.0)
    m = n_samples(0.4)
    tt = t_axis(m)
    thud = (np.sin(TAU * 85 * tt) + 0.5 * np.sin(TAU * 170 * tt)) * np.exp(-tt / 0.07) + \
        sos_filter(noise(m, 4), "lowpass", 900, 2) * np.exp(-tt / 0.02)
    tl.add(thud, 0.32, 1.0)
    tl.add(latch(rng), 0.35, 0.6, 0.15)
    x = reverb(tl.oneshot(), reverb_ir(0.9, predelay=0.01, damp_hz=3500, seed=15), wet=0.35, loop=False)
    return fade(x, 0.002, 0.2)[: n_samples(1.2)]


def clock_tick():
    """Hall clock: tick-tock-tick-tock, one per second (chapter 8: the clock is running)."""
    rng = np.random.default_rng(83)
    tl = Timeline(4.0, tail=1)
    for i in range(4):
        tl.add(tick_sound(rng, tock=i % 2 == 1), 0.03 + i, 1.0, -0.1 if i % 2 else 0.1)
    x = reverb(tl.oneshot(), reverb_ir(1.2, damp_hz=5000, seed=16), wet=0.3, loop=False)
    return fade(x, 0.001, 0.3)[: n_samples(4.0)]


def clock_start():
    """The stuck clock starts: gears whirr, a clunk, the pendulum picks up. 'Часы пошли.'"""
    rng = np.random.default_rng(84)
    tl = Timeline(5.4, tail=1)
    t = 0.05
    gap = 0.11
    while t < 0.95:
        tl.add(tick_sound(rng) * 0.4, t, 0.5, rng.uniform(-0.2, 0.2))
        t += gap
        gap = max(0.028, gap * 0.85)
    m = n_samples(0.6)
    tt = t_axis(m)
    clunk = np.sin(TAU * 140 * tt) * np.exp(-tt / 0.06) + 0.5 * np.sin(TAU * 1150 * tt) * np.exp(-tt / 0.2) \
        + 0.3 * np.sin(TAU * 1730 * tt) * np.exp(-tt / 0.12)
    tl.add(clunk, 1.0, 0.9)
    for i in range(4):
        tl.add(tick_sound(rng, tock=i % 2 == 1), 1.7 + i, 0.6 + 0.12 * i, -0.1 if i % 2 else 0.1)
    x = reverb(tl.oneshot(), reverb_ir(1.4, damp_hz=5000, seed=17), wet=0.32, loop=False)
    return fade(x, 0.001, 0.3)[: n_samples(5.4)]


def thunder():
    """Close thunderclap: a tearing crack, then a long rolling rumble (~7 s)."""
    rng = np.random.default_rng(85)
    dur = 7.5
    n = n_samples(dur)
    t = t_axis(n)
    crack = np.zeros((n, 2))
    for i in range(5):
        at = n_samples(0.05 + i * rng.uniform(0.03, 0.08))
        m = n_samples(0.4)
        tt = t_axis(m)
        b = np.stack([noise(m, 10 + i), noise(m, 20 + i)], axis=1) * np.exp(-tt / rng.uniform(0.04, 0.12))[:, None]
        crack[at:at + m] += b * (0.8 ** i)
    crack = sos_filter(crack, "bandpass", (200, 7000), 2)
    rum = np.stack([noise(n, 31), noise(n, 32)], axis=1)
    rum = sos_filter(rum, "bandpass", (25, 220), 2)
    env = (1 - np.exp(-t / 0.15)) * np.exp(-t / 2.2)
    for c, w in ((0.7, 0.3), (1.6, 0.5), (2.6, 0.6), (3.8, 0.8)):  # rolling bumps
        env += 0.35 * np.exp(-((t - c) / w) ** 2) * np.exp(-t / 3.0)
    mid = sos_filter(np.stack([noise(n, 33), noise(n, 34)], axis=1), "bandpass", (150, 800), 2)
    x = rum * env[:, None] * 2.5 + mid * (np.exp(-t / 0.7) * 0.5)[:, None] + crack * 0.9
    x = reverb(x, reverb_ir(2.5, damp_hz=2500, seed=18), wet=0.35, loop=False)
    return fade(x, 0.001, 1.5)[: n]


def gears(rng, dur=0.7, rate=22.0):
    """Brass automaton gear train: small metallic clicks over a soft whirr. Mono."""
    tl = Timeline(dur, tail=0.5)
    t = 0.0
    while t < dur:
        n = n_samples(0.05)
        tt = t_axis(n)
        f = rng.uniform(2800, 4200)
        c = np.sin(TAU * f * tt) * np.exp(-tt / 0.006) + 0.6 * noise(n, rng.integers(1 << 30)) * np.exp(-tt / 0.001)
        tl.add(c, t, rng.uniform(0.3, 0.6))
        t += 1 / rate * rng.uniform(0.8, 1.2)
    n = n_samples(dur)
    whirr = sos_filter(noise(n, rng.integers(1 << 30)), "bandpass", (600, 2400), 2)
    whirr *= (0.5 + 0.5 * np.sin(TAU * 35 * t_axis(n))) * np.sin(np.pi * t_axis(n) / dur) * 0.15
    tl.add(whirr, 0.0)
    return tl.oneshot()


def lever(rng):
    n = n_samples(0.25)
    t = t_axis(n)
    return (np.sin(TAU * 210 * t) * np.exp(-t / 0.03) + 0.5 * np.sin(TAU * 950 * t) * np.exp(-t / 0.08)
            + sos_filter(noise(n, rng.integers(1 << 30)), "bandpass", (800, 5000), 2) * np.exp(-t / 0.004))


def oracle_sat():
    """The Oracle answers `sat`: lever, brass gears, a cam drops, a bright lamp bell rings."""
    rng = np.random.default_rng(86)
    tl = Timeline(3.0, tail=3)
    tl.add(lever(rng), 0.02, 0.7)
    tl.add(gears(rng, 0.75), 0.2, 0.8)
    tl.add(lever(rng) * 0.8, 1.0, 0.6)
    n = n_samples(2.5)
    t = t_axis(n)
    f = 1760.0
    ding = sum(a * np.sin(TAU * f * r * t + p) * np.exp(-t / d)
               for r, a, d, p in ((1, 1.0, 1.4, 0), (2.76, 0.45, 0.5, 1), (5.4, 0.25, 0.2, 2), (8.93, 0.1, 0.08, 3)))
    ding *= 1 - np.exp(-t / 0.0008)
    tl.add(ding, 1.12, 0.6, 0.1)
    x = reverb(tl.oneshot(), reverb_ir(1.6, damp_hz=5000, seed=19), wet=0.3, loop=False)
    return fade(x, 0.001, 0.4)[: n_samples(3.0)]


def oracle_unsat():
    """The Oracle answers `unsat`: same mechanism, then a dull damped clack, no ring."""
    rng = np.random.default_rng(87)
    tl = Timeline(1.7, tail=1)
    tl.add(lever(rng), 0.02, 0.7)
    tl.add(gears(rng, 0.75), 0.2, 0.8)
    n = n_samples(0.4)
    t = t_axis(n)
    clack = np.sin(TAU * 220 * t) * np.exp(-t / 0.05) + 0.4 * np.sin(TAU * 330 * t) * np.exp(-t / 0.03) + \
        sos_filter(noise(n, 9), "bandpass", (300, 1500), 2) * np.exp(-t / 0.01)
    tl.add(clack, 1.02, 0.9)
    x = reverb(tl.oneshot(), reverb_ir(1.0, damp_hz=4000, seed=20), wet=0.25, loop=False)
    return fade(x, 0.001, 0.3)[: n_samples(1.7)]


def doorbell():
    """Mansion door chime, ding-dong (guests, the courier)."""
    tl = Timeline(3.0, tail=3)
    for at, m in ((0.02, 79), (0.6, 76)):
        f = midi_hz(m)
        n = n_samples(2.6)
        t = t_axis(n)
        tone = sum(a * np.sin(TAU * f * r * t + p) * np.exp(-t / d)
                   for r, a, d, p in ((1, 1.0, 1.6, 0), (2.0, 0.3, 0.9, 1), (2.76, 0.35, 0.6, 2), (5.4, 0.12, 0.2, 3)))
        tone *= 1 - np.exp(-t / 0.001)
        tl.add(tone, at, 0.5, 0.15 if m == 79 else -0.15)
    x = reverb(tl.oneshot(), reverb_ir(1.6, damp_hz=4500, seed=21), wet=0.35, loop=False)
    return fade(x, 0.001, 0.5)[: n_samples(3.0)]


def dishes():
    """Porcelain cups and saucers clinking in the kitchen."""
    rng = np.random.default_rng(88)
    tl = Timeline(1.6, tail=1)
    t = 0.02
    for _ in range(6):
        n = n_samples(0.5)
        tt = t_axis(n)
        f0 = rng.uniform(1800, 3200)
        x = sum(a * np.sin(TAU * f0 * r * tt + rng.uniform(0, TAU)) * np.exp(-tt / d)
                for r, a, d in ((1, 1.0, 0.22), (2.32, 0.5, 0.12), (4.25, 0.3, 0.06), (6.63, 0.15, 0.03)))
        x += 0.5 * sos_filter(noise(n, rng.integers(1 << 30)), "highpass", 3000, 2) * np.exp(-tt / 0.002)
        tl.add(x, t, rng.uniform(0.4, 1.0), rng.uniform(-0.5, 0.5))
        t += rng.choice([rng.uniform(0.05, 0.1), rng.uniform(0.18, 0.35)])
    return fade(room(tl.oneshot(), 0.4, 0.2), 0.001, 0.2)[: n_samples(1.6)]


def glitch():
    """Digital failure: 'Платформа недоступна' (the 💸 cut) or the dream breaking. ~1 s."""
    rng = np.random.default_rng(89)
    out = []
    for i in range(14):
        d = n_samples(rng.uniform(0.025, 0.09))
        t = t_axis(d)
        kind = rng.integers(0, 4)
        if kind == 0:
            x = np.sign(np.sin(TAU * rng.uniform(300, 1800) * t)) * 0.5
        elif kind == 1:
            x = noise(d, i) * 0.6
        elif kind == 2:
            x = (np.sin(TAU * 440 * t) + np.sin(TAU * 659 * t)) * 0.4
        else:
            x = np.zeros(d)
        hold = rng.integers(2, 12)  # sample-rate crush
        x = np.repeat(x[::hold], hold)[:d]
        x = np.round(x * 6) / 6
        out.append(fade(x, 0.001, 0.001))
    x = sos_filter(np.concatenate(out), "lowpass", 9000, 2)
    return fade(np.stack([x, np.roll(x, n_samples(0.004))], axis=1), 0.001, 0.05)


def shimmer():
    """Magic happening: a rising sparkle (potion, mirror, the cat's door)."""
    tl = Timeline(3.0, tail=4)
    for i, m in enumerate((76, 80, 83, 87, 88, 92, 95)):
        tl.add(bell(m, 0.4, 0.5 + 0.05 * i, rel=1.5), 0.05 + i * 0.09, 0.35, -0.6 + 0.2 * i)
    n = n_samples(1.6)
    t = t_axis(n)
    sw = sos_filter(noise(n, 7), "highpass", 4000, 2) * np.sin(np.pi * t / 1.6) ** 2 * 0.08
    tl.add(sw, 0.0)
    tl.add(glass(88, 0.8, 0.5, attack=0.3, rel=1.5), 0.3, 0.25)
    x = reverb(tl.oneshot(), reverb_ir(3.0, damp_hz=6000, seed=22), wet=0.55, loop=False)
    return fade(x, 0.002, 0.8)[: n_samples(3.5)]


def slam():
    """Door slammed hard (prologue: «Не так!» / «Да блядь!»): a bang, a rattle of the frame, a short echo in an empty room."""
    rng = np.random.default_rng(91)
    tl = Timeline(1.2, tail=1)
    n = n_samples(0.5)
    t = t_axis(n)
    bang = (np.sin(TAU * 70 * t) + 0.6 * np.sin(TAU * 140 * t) + 0.3 * np.sin(TAU * 210 * t)) * np.exp(-t / 0.09)
    bang += sos_filter(noise(n, 5), "lowpass", 2500, 2) * np.exp(-t / 0.03) * 1.2
    tl.add(bang, 0.0, 1.0)
    m = n_samples(0.35)
    tt = t_axis(m)
    rattle = sos_filter(noise(m, 6), "bandpass", (500, 1800), 2) * np.exp(-tt / 0.08) * (0.6 + 0.4 * np.sin(TAU * 38 * tt))
    tl.add(rattle, 0.05, 0.3)
    tl.add(latch(rng), 0.12, 0.35, 0.1)
    x = reverb(tl.oneshot(), reverb_ir(1.4, predelay=0.012, damp_hz=5000, seed=17), wet=0.4, loop=False)
    return fade(x, 0.002, 0.3)[: n_samples(1.6)]


def wr_tone():
    """The white room switching on (prologue): one clean sterile chime and a very soft room tone that ends with a click."""
    tl = Timeline(2.4, tail=2)
    tl.add(glass(81, 0.9, 0.35, attack=0.01, rel=1.4), 0.0, 0.35)
    tl.add(glass(88, 0.9, 0.2, attack=0.01, rel=1.2), 0.04, 0.25)
    n = n_samples(2.0)
    t = t_axis(n)
    hum = np.sin(TAU * 220 * t) * 0.03 * np.sin(np.pi * t / 2.0) ** 2
    tl.add(hum, 0.0)
    click = np.zeros(n_samples(0.02))
    click[0] = 0.5
    tl.add(sos_filter(click, "highpass", 2000, 2), 1.9, 0.5)
    x = reverb(tl.oneshot(), reverb_ir(2.0, damp_hz=7000, seed=23), wet=0.3, loop=False)
    return fade(x, 0.002, 0.6)[: n_samples(2.8)]


def ringback():
    """Ringback heard in a phone earpiece (calling the police, chapter 1): two 425 Hz tones."""
    dur = 6.5
    n = n_samples(dur)
    t = t_axis(n)
    gate = np.zeros(n)
    for s in (0.2, 5.2):
        a, b = n_samples(s), n_samples(s + 1.0)
        g = np.ones(b - a)
        r = n_samples(0.01)
        g[:r], g[-r:] = np.linspace(0, 1, r), np.linspace(1, 0, r)
        gate[a:b] = g
    x = np.tanh(2 * np.sin(TAU * 425 * t)) * gate
    x = sos_filter(x, "bandpass", (300, 3400), 2) + 0.01 * sos_filter(noise(n, 4), "bandpass", (300, 3400), 2)
    return fade(stereo(x * 0.6), 0.01, 0.1)


# ============================================================== driver

# ============================================================== «На краю контекста»: horror (docs/chapters/05n-edge.md)
def night_kuni_rev():
    """Her lullaby played backwards: every note swells into its attack, the reverb tails come first. Plays when the music is
    «wrong» (the end of E.0б, the rounds). A loop that is seamless forward stays seamless reversed."""
    return night_kuni()[::-1].copy()


def heartbeat():
    """Two low thumps, lub-dub, slightly late and uneven. The weight of everything she has to hold in her head."""
    n = n_samples(1.5)
    out = np.zeros(n)
    for at, f0, g in ((0.0, 62.0, 1.0), (0.31, 54.0, 0.7)):
        d = n_samples(0.5)
        t = t_axis(d)
        f = 38.0 + (f0 - 38.0) * np.exp(-t / 0.05)
        ph = TAU * np.cumsum(f) / SR
        thump = np.sin(ph) * np.exp(-t / 0.09) * g
        thump += sos_filter(noise(d, 7), "lowpass", 160, 2) * np.exp(-t / 0.02) * 0.5 * g
        i = n_samples(at)
        out[i:i + d] += thump
    return fade(out, 0.002, 0.05)


def ink_vanish():
    """The pen scratches, then the ink goes into the paper: the scratch thins out and a soft inward hiss swallows it."""
    n = n_samples(2.4)
    t = t_axis(n)
    scratch_env = np.clip(1 - t / 1.1, 0, 1) * (0.5 + 0.5 * np.abs(np.sin(TAU * 5.5 * t)))
    scratch = sos_filter(noise(n, 11), "bandpass", (2200, 6500), 2) * scratch_env
    hiss_env = np.sin(np.pi * np.clip((t - 0.7) / 1.6, 0, 1)) ** 2
    hiss = sos_filter(noise(n, 12), "bandpass", (400, 1800), 2) * hiss_env * 0.35
    mono = scratch + hiss
    st = np.stack([mono, sos_filter(mono, "lowpass", 5500, 1)], axis=1)
    return fade(room(st, 0.2, 0.1), 0.004, 0.2)


def name_crunch():
    """Her name rotting: a falling tone eaten by bit crush and sample-rate decimation. ~0.9 s."""
    n = n_samples(0.9)
    t = t_axis(n)
    f = 900.0 * np.exp(-t * 2.6) + 70.0
    x = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    rng = np.random.default_rng(404)
    hold = np.interp(t, [0, 0.9], [2, 40]).astype(int)
    y = np.empty(n)
    i = 0
    while i < n:
        h = max(1, int(hold[min(i, n - 1)]))
        y[i:i + h] = x[i]
        i += h
    y = np.round(y * 5) / 5
    y += (rng.random(n) < 0.002) * rng.uniform(-0.8, 0.8, n)
    y = sos_filter(y, "lowpass", 7000, 2)
    return fade(np.stack([y, np.roll(y, n_samples(0.006))], axis=1), 0.002, 0.15)


def whisper_breath():
    """A breath near the ear, then a second one: shaped noise with two soft syllables. Nothing intelligible."""
    n = n_samples(2.6)
    t = t_axis(n)
    env = sum(np.exp(-((t - c) / w) ** 2) for c, w in ((0.7, 0.25), (1.05, 0.12), (1.75, 0.3)))
    x = sos_filter(noise(n, 21), "bandpass", (1200, 5200), 2) * env
    x += sos_filter(noise(n, 22), "bandpass", (250, 700), 2) * env * 0.25
    st = np.stack([x, sos_filter(np.roll(x, n_samples(0.0015)), "lowpass", 4500, 1)], axis=1)
    return fade(room(st, 0.35, 0.2), 0.01, 0.2)


def tinnitus():
    """A thin high tone and its beating neighbour swelling up and dying out. The silence being too loud."""
    n = n_samples(5.0)
    t = t_axis(n)
    env = np.sin(np.pi * t / 5.0) ** 2
    x = (np.sin(TAU * 6900 * t) + np.sin(TAU * 6913 * t)) * 0.5 * env
    return fade(np.stack([x, x * 0.9], axis=1), 0.05, 0.3)


LOOPS = {  # name: (fn, target LUFS)
    "night_code": (night_code, -16.0),
    "menu": (menu, -16.0),
    "rain": (rain, -18.0),
    "fans": (fans, -21.0),
    # dream (chapters 1-8, interludes, epilogues)
    "daily": (daily, -16.0),
    "tender": (tender, -16.0),
    "tender_fire": (tender_fire, -16.0),
    "tension": (tension, -16.0),
    "mystery": (mystery, -17.0),
    "tarot": (tarot, -17.0),
    "night_kuni": (night_kuni, -17.0),
    "night_kuni_rev": (night_kuni_rev, -18.0),
    "morning": (morning, -16.0),
    "jump": (jump, -15.0),
    "bad_end": (bad_end, -18.0),
    "ending": (ending, -16.0),
    "game": (game, -16.0),
    "tictactoe": (tictactoe, -17.0),
    "fireplace": (fireplace, -20.0),
    "car": (car, -20.0),
    "swagger": (lambda: __import__("aggro").swagger(), -15.0),  # the author's hum (hum/aggro.json), half-time trap
    "assertive": (lambda: __import__("aggro").assertive(), -15.0),  # his hum as a band, Kuni circling the listener
}
# finished but not used in the game: rendered into tools/music/unused/ (not data/, so not packed), kept to come back to
UNUSED = {  # name: (fn, target LUFS)
}
UNUSED_DIR = os.path.join(ROOT, "tools", "music", "unused")

# ---- the gestures of kn::interact (gesture::*::sound): each step of the hand, short, played many times over ----

def porcelain(rng, f0, decay=0.2, bright=1.0):
    """One hit on porcelain: inharmonic partials of a cup, a click of the hit."""
    n = n_samples(decay * 3)
    t = t_axis(n)
    x = sum(a * np.sin(TAU * f0 * r * t + rng.uniform(0, TAU)) * np.exp(-t / (decay * d))
            for r, a, d in ((1, 1.0, 1.0), (2.32, 0.55 * bright, 0.55), (4.25, 0.3 * bright, 0.3), (6.63, 0.12 * bright, 0.15)))
    return x + 0.4 * sos_filter(noise(n, rng.integers(1 << 30)), "highpass", 3500, 2) * np.exp(-t / 0.0015)


REC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rec")


@functools.cache
def recording(name):
    """tools/music/rec/<name>.ogg as stereo float at SR: the few real sounds the author recorded himself."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(REC, name + ".ogg"), "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def trimmed(x, start, end):
    """x from `start` to `end` s, the rumble under 90 Hz off, soft at both ends."""
    x = x[n_samples(start): n_samples(end)]
    return fade(np.stack([sos_filter(x[:, k], "highpass", 90, 2) for k in range(2)], -1), 0.003, 0.06)


# The takes of the spoon on the cup (gesture::Sound: one at random each half turn, never the same twice running): the
# author's own spoon in his own cup (rec/sugar_mix.ogg), a little higher or lower each time
SPOON_TAKES = (1.0, 1.035, 0.965, 1.065, 0.94)


def spoon_clink(take):
    """Stirring the tea (gesture::Stir, each half turn): the teaspoon on the cup, two taps."""
    x = trimmed(recording("sugar_mix"), 0.12, 0.55)
    rate = SPOON_TAKES[take]   # faster = higher and a little shorter, like a smaller cup
    t = np.arange(int(len(x) / rate)) * rate
    return np.stack([np.interp(t, np.arange(len(x)), x[:, k]) for k in range(2)], -1)


def spoon_done():
    """The tea stirred (after gesture::Stir): the spoon knocked off on the rim, a few quick taps (rec/sugar_mix_end.ogg)."""
    return trimmed(recording("sugar_mix_end"), 0.11, 0.72)


def porcelain_lid():
    """The sugar bowl found (gesture::Find): its lid lifts with a low porcelain knock and a ring."""
    rng = np.random.default_rng(303)
    tl = Timeline(0.8, tail=0.6)
    tl.add(porcelain(rng, 1650, 0.12, 0.6), 0.01, 1.0, -0.1)
    tl.add(porcelain(rng, 2300, 0.2), 0.11, 0.6, -0.1)
    return fade((room(tl.oneshot(), 0.35, 0.18))[: n_samples(0.8)], 0.001, 0.15)


def pendulum_nudge():
    """The stopped clock pushed (gesture::Tap): a wooden knock on the case, one swing out and back, a tick, a tock, the
    tock dies off. It does not go: «качнулся раз — и встал»."""
    rng = np.random.default_rng(304)
    tl = Timeline(1.6, tail=1)
    n = n_samples(0.2)
    t = t_axis(n)
    knock = np.sin(TAU * 180 * t) * np.exp(-t / 0.025) + 0.4 * sos_filter(noise(n, 305), "bandpass", (300, 2000), 2) * np.exp(-t / 0.006)
    tl.add(knock, 0.01, 0.8)
    tl.add(tick_sound(rng), 0.45, 0.8, 0.1)
    tl.add(tick_sound(rng, tock=True), 1.0, 0.45, -0.1)
    x = reverb(tl.oneshot(), reverb_ir(1.2, damp_hz=5000, seed=16), wet=0.3, loop=False)
    return fade((x)[: n_samples(1.6)], 0.001, 0.3)


def glass_wipe(take):
    """A palm wiping the steamed mirror (gesture::Wipe, each stroke; one take at random): a soft damp swish of skin on wet
    glass, the grain of the palm dragging over it. No tone at all: the squeak that slid in pitch whistled in the ears
    (the author, 2026-11-20)."""
    rng = np.random.default_rng(306 + 10 * take)
    dur = (0.42, 0.36, 0.48)[take]
    n = n_samples(dur)
    u = np.linspace(0, 1, n)
    env = np.sin(np.pi * u ** (0.8 + 0.15 * take)) ** 1.5
    # the body of the stroke: broad noise, warm, nothing above ~2.5 kHz to cut the ear
    swish = sos_filter(noise(n, 307 + 10 * take), "bandpass", (250, 2200), 2) * env
    # the grain: the palm sticks and slips on the wet glass, a soft flutter of the swish, not a pitch
    grain = 0.7 + 0.3 * np.clip(smooth_random(n, 40 + 8 * take, seed=308 + 10 * take, circular=False), -1, 1)
    # the thin wet film under the palm, very low
    film = sos_filter(noise(n, 309 + 10 * take), "lowpass", 3200, 2) * env * 0.12
    x = sos_filter(swish * grain + film, "lowpass", 2800, 2) * rng.uniform(0.9, 1.0)
    return fade(room(x, 0.2, 0.12), 0.01, 0.08)


def fur_rub():
    """Fingers scratching behind her ear (gesture::Rub, each stroke): a soft quick scratch through hair, there and back."""
    n = n_samples(0.36)
    u = np.linspace(0, 1, n)
    scr = colored_noise(n, seed=309)
    scr = sos_filter(scr, "bandpass", (1800, 7000), 2)
    grain = 0.6 + 0.4 * np.abs(np.sin(TAU * 38 * u * 0.36))   # the fingertips catch the hair, not a smooth hiss
    env = np.sin(np.pi * u) ** 1.2 * (0.7 + 0.3 * np.sin(TAU * u))
    return fade(scr * grain * env, 0.005, 0.05)


def pencil_strike():
    """The word struck through (gesture::Drag): a pencil scratched hard across paper, fast, with a stop at the end."""
    n = n_samples(0.42)
    u = np.linspace(0, 1, n)
    x = sos_filter(noise(n, 310), "bandpass", (2000, 8000), 2)
    rough = 0.6 + 0.4 * smooth_random(n, 40, seed=311, circular=False) ** 2
    env = np.clip(u / 0.08, 0, 1) * np.clip((1 - u) / 0.12, 0, 1)
    body = sos_filter(noise(n, 312), "bandpass", (300, 1000), 2) * 0.3   # the desk under the paper
    return fade(room((x * rough + body) * env, 0.2, 0.12), 0.002, 0.05)


def key_turn():
    """The key in the old lock turned (gesture::Stir, half a turn): a scrape of the bit on the wards, then the bolt goes
    with a heavy clack."""
    rng = np.random.default_rng(313)
    tl = Timeline(0.9, tail=0.8)
    n = n_samples(0.35)
    u = np.linspace(0, 1, n)
    scrape = sos_filter(noise(n, 314), "bandpass", (1200, 5000), 2) * np.sin(np.pi * u) * 0.35
    tl.add(scrape, 0.0, 1.0, 0.15)
    tl.add(latch(rng, 1400) * 1.0, 0.36, 1.0, 0.15)
    m = n_samples(0.3)
    t = t_axis(m)
    bolt = np.sin(TAU * 120 * t) * np.exp(-t / 0.04) + 0.5 * np.sin(TAU * 760 * t) * np.exp(-t / 0.05)
    tl.add(bolt, 0.37, 0.8, 0.15)
    return fade((room(tl.oneshot(), 0.45, 0.2))[: n_samples(0.9)], 0.002, 0.15)


def airbrush():
    """Yara's airbrush through the stencil (gesture::Hold, the finger put on): the hiss of the air, the paint in it, ~1.8 s."""
    n = n_samples(1.8)
    u = np.linspace(0, 1, n)
    air = sos_filter(noise(n, 315), "bandpass", (2500, 11000), 2)
    flutter = 0.9 + 0.1 * smooth_random(n, 25, seed=316, circular=False)
    env = np.clip(u / 0.06, 0, 1) * np.clip((1 - u) / 0.2, 0, 1)
    n2 = n_samples(0.05)
    click = sos_filter(noise(n2, 317), "highpass", 2000, 2) * np.exp(-t_axis(n2) / 0.004) * 0.6   # the trigger
    x = air * flutter * env * 0.5
    x[:n2] += click
    return fade(room(x, 0.2, 0.1), 0.002, 0.1)


def laptop_shut():
    """The laptop lid shut (gesture::Drag): the hinge's soft friction, then the lid meets the keyboard with a muffled
    plastic thump and a tiny magnet click."""
    rng = np.random.default_rng(318)
    tl = Timeline(0.7, tail=0.6)
    n = n_samples(0.2)
    u = np.linspace(0, 1, n)
    tl.add(sos_filter(noise(n, 319), "bandpass", (600, 2500), 2) * np.sin(np.pi * u) * 0.15, 0.0, 1.0)
    m = n_samples(0.25)
    t = t_axis(m)
    thump = np.sin(TAU * 95 * t) * np.exp(-t / 0.03) + 0.4 * sos_filter(noise(m, 320), "lowpass", 1200, 2) * np.exp(-t / 0.012)
    tl.add(thump, 0.2, 1.0)
    tl.add(latch(rng, 3200) * 0.25, 0.215, 1.0)
    return fade(room(tl.oneshot(), 0.3, 0.15)[: n_samples(0.7)], 0.002, 0.1)

# ---------------------------------------------------------------------------------------------------------------------
# 🌙 «гоночки» (kn::race, engine/src/kn/ui/RaceView.cpp): a cheap arcade racer by a guy from her chats. The engine itself
# is synthesized live by the game (its pitch follows the revs); these are the one-shots around it.


def race_beep():
    """3, 2, 1 of the start: a short square-ish arcade beep."""
    n = n_samples(0.18)
    t = t_axis(n)
    x = np.sign(sine(660, n)) * 0.35 + sine(660, n) * 0.5
    x = sos_filter(x, "lowpass", 4000, 2) * np.exp(-t / 0.09) * (1 - np.exp(-t / 0.002))
    return fade(stereo(x), 0.001, 0.03)


def race_go():
    """«Старт!»: the same beep an octave up, longer, with a rising shine."""
    n = n_samples(0.7)
    t = t_axis(n)
    x = np.sign(sine(1320, n)) * 0.3 + sine(1320, n) * 0.5 + 0.25 * sine(1320 * (1 + 0.5 * t), n)
    x = sos_filter(x, "lowpass", 6000, 2) * np.exp(-t / 0.35) * (1 - np.exp(-t / 0.002))
    return fade(room(stereo(x), 0.2, 0.15), 0.001, 0.1)[: n_samples(0.9)]


def race_bump():
    """A light knock of two karts or a kart and the rail: a dull plastic thud."""
    n = n_samples(0.25)
    t = t_axis(n)
    x = sine(110 * np.exp(-t / 0.08) + 60, n) * np.exp(-t / 0.05)
    x += sos_filter(noise(n, 31), "bandpass", (600, 2500), 2) * np.exp(-t / 0.02) * 0.6
    return fade(stereo(x), 0.001, 0.05)


def race_crash():
    """A hard hit: a metal bang, a crunch and sparks scraping off."""
    n = n_samples(0.8)
    t = t_axis(n)
    bang = (sine(90, n) + 0.5 * sine(187, n) + 0.3 * sine(413, n)) * np.exp(-t / 0.07)
    crunch = sos_filter(noise(n, 32), "bandpass", (900, 5000), 2) * np.exp(-t / 0.12)
    scrape = sos_filter(noise(n, 33), "highpass", 4000, 2) * np.exp(-t / 0.3) * (0.6 + 0.4 * np.sin(TAU * 23 * t)) * 0.4
    x = bang + crunch * 0.9 + scrape
    return fade(room(stereo(x), 0.25, 0.2), 0.001, 0.15)[: n_samples(1.0)]


def race_warp():
    """Put back on the road after being stuck: a quick sci-fi zip down and up."""
    n = n_samples(0.6)
    t = t_axis(n)
    f = 300 + 1500 * np.abs(np.cos(np.pi * t / 0.6))
    x = sine(f, n) * 0.6 + 0.3 * sine(f * 1.5, n)
    x *= np.sin(np.pi * t / 0.6) ** 2
    return fade(room(stereo(x), 0.3, 0.2), 0.002, 0.1)[: n_samples(0.8)]


def race_finish():
    """The finish line: a bright arcade fanfare, three rising notes and a chord."""
    tl = Timeline(2.0, tail=2)
    for i, (midi, at) in enumerate(((72, 0.0), (76, 0.12), (79, 0.24))):
        n = n_samples(0.14 if i < 2 else 1.2)
        t = t_axis(n)
        f = 440 * 2 ** ((midi - 69) / 12)
        x = (np.sign(sine(f, n)) * 0.25 + sine(f, n) * 0.5) * np.exp(-t / (0.08 if i < 2 else 0.5))
        tl.add(sos_filter(x, "lowpass", 5000, 2), at, 0.6)
    for midi in (84, 88, 91):
        n = n_samples(1.2)
        t = t_axis(n)
        tl.add(sine(440 * 2 ** ((midi - 69) / 12), n) * np.exp(-t / 0.5) * (1 - np.exp(-t / 0.01)), 0.24, 0.25)
    return fade(room(tl.oneshot(), 0.3, 0.2), 0.002, 0.3)[: n_samples(2.0)]


def achievement():
    """«Получено достижение» (the card at the bottom of the screen): the head of Kuni's theme (E G A, MEL_A) as quick
    bells, an octave E on top, over a soft Fmaj9 of glass (PROG_A's first chord)."""
    tl = Timeline(2.4, tail=3)
    for i, (m, at) in enumerate(((76, 0.0), (79, 0.08), (81, 0.16), (88, 0.3))):
        tl.add(bell(m, 0.5 if i < 3 else 1.2, 0.55 + 0.05 * i, rel=1.4), 0.02 + at, 0.4, -0.3 + 0.2 * i)
    for m, v in ((53, 0.5), (57, 0.4), (60, 0.35), (64, 0.3), (67, 0.25)):
        tl.add(glass(m, 1.2, v, attack=0.08, rel=1.4), 0.0, 0.3)
    x = reverb(tl.oneshot(), reverb_ir(2.0, predelay=0.015, damp_hz=6000, seed=33), wet=0.4, loop=False)
    return fade(x, 0.002, 0.6)[: n_samples(2.4)]


RACE_QUIETER = 20 * np.log10(0.8)   # dB: -20 % of the amplitude, the race's sounds

SFX = {
    **{f"spoon_clink_{k + 1}": (lambda k=k: spoon_clink(k), -4.0) for k in range(len(SPOON_TAKES))},
    "spoon_done": (spoon_done, -4.0),
    "porcelain_lid": porcelain_lid, "pendulum_nudge": pendulum_nudge,
    **{f"glass_wipe_{k + 1}": (lambda k=k: glass_wipe(k), -9.0) for k in range(3)},
    "fur_rub": (fur_rub, -9.0), "pencil_strike": (pencil_strike, -6.0),
    "key_turn": key_turn, "airbrush": (airbrush, -9.0), "laptop_shut": laptop_shut,
    "keys": keys, "backspace": backspace, "enter": enter, "fans_to_rain": fans_to_rain,
    "page": page, "buzz": buzz, "bell": bell_sfx,
    # dream SFX; a tuple is (fn, peak dBFS) for sounds that are dense and would be too loud at -3
    "rain_to_fans": rain_to_fans, "pop": pop, "remember": (remember, -5.0), "bell_collar": (bell_collar, -7.0),
    "door": door, "door_close": door_close, "clock_tick": clock_tick, "clock_start": clock_start,
    "thunder": thunder, "oracle_sat": (oracle_sat, -5.0), "oracle_unsat": oracle_unsat,
    "doorbell": (doorbell, -5.0), "dishes": (dishes, -5.0), "glitch": (glitch, -9.0),
    "shimmer": (shimmer, -5.0), "ringback": (ringback, -14.0),
    # prologue v5
    "slam": (slam, -4.0), "wr_tone": (wr_tone, -12.0),
    # «На краю контекста», horror
    "heartbeat": (heartbeat, -6.0), "ink_vanish": (ink_vanish, -8.0), "name_crunch": (name_crunch, -8.0),
    "whisper_breath": (whisper_breath, -10.0), "tinnitus": (tinnitus, -16.0),
    # 🌙 «гоночки»
    # the race is 20 % quieter than it was first made (RACE_QUIETER): with the volume at 100 % it was too loud
    "race_beep": (race_beep, -8.0 + RACE_QUIETER), "race_go": (race_go, -7.0 + RACE_QUIETER),
    "race_bump": (race_bump, -9.0 + RACE_QUIETER), "race_crash": (race_crash, -6.0 + RACE_QUIETER),
    "race_warp": (race_warp, -9.0 + RACE_QUIETER), "race_finish": (race_finish, -6.0 + RACE_QUIETER),
    # kn::achievement
    "achievement": (achievement, -6.0),
}


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=channels,sample_rate", "-of", "csv=p=0", path],
                       capture_output=True, text=True, check=True)
    return " ".join(r.stdout.split())


def main(names):
    loops = [(name, fn, lufs, MUSIC) for name, (fn, lufs) in LOOPS.items()]
    loops += [(name, fn, lufs, UNUSED_DIR) for name, (fn, lufs) in UNUSED.items()]
    for name, fn, lufs, out_dir in loops:
        if names and name not in names or not names and out_dir == UNUSED_DIR:
            continue
        x = master_loudness(stereo(fn()), lufs, ceiling_db=-1.5, loop=True)
        s_raw = seam_ratio(x)
        out = os.path.join(out_dir, f"{name}.ogg")
        encode_ogg(x, out)
        y = decode(out)
        s_ogg = seam_ratio(y)
        assert len(y) == len(x), f"{name}: decoded length {len(y)} != {len(x)}"
        assert s_raw < 1.5 and s_ogg < 1.5, f"{name}: loop seam click ({s_raw:.2f}/{s_ogg:.2f})"
        print(f"{name:13s} loop  {len(x) / SR:6.2f}s  {measure_lufs(y, True):6.1f} LUFS  "
              f"peak {20 * np.log10(np.max(np.abs(y))):5.1f} dBFS  seam {s_raw:.2f}/{s_ogg:.2f}  "
              f"[{probe(out)}]")
    for name, fn in SFX.items():
        if names and name not in names:
            continue
        fn, peak = fn if isinstance(fn, tuple) else (fn, -3.0)
        x = master_peak(stereo(fn()), peak)
        out = os.path.join(SOUND, f"{name}.ogg")
        encode_ogg(x, out)
        y = decode(out)
        print(f"{name:13s} sfx   {len(x) / SR:6.2f}s  peak {20 * np.log10(np.max(np.abs(y))):5.1f} dBFS  "
              f"[{probe(out)}]")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
