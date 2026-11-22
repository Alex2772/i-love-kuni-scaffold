"""Tiny numpy synth / sequencer for "I love Kuni".

Everything is synthesized from scratch: oscillators, envelopes, FM electric piano,
additive pad, noise generators, convolution reverb, filters and loop helpers.

Conventions:
  * mono signals are 1-D float arrays, stereo signals are (n, 2) arrays;
  * time is in seconds, pitch is MIDI note number unless stated otherwise;
  * "circular" processing treats the buffer as one period of an infinite loop,
    so the result loops seamlessly by construction.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100
TAU = 2 * np.pi


# ---------------------------------------------------------------- basics

def n_samples(sec: float) -> int:
    return int(round(sec * SR))


def t_axis(n: int) -> np.ndarray:
    return np.arange(n) / SR


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def db(x: float) -> float:
    return 10 ** (x / 20)


def stereo(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 2 else np.stack([x, x], axis=1)


def pan(x: np.ndarray, p: float) -> np.ndarray:
    """Equal-power pan of a mono signal, p in [-1, 1]."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)) + 1e-20))


# ---------------------------------------------------------------- oscillators

def sine(freq, n: int, phase: float = 0.0) -> np.ndarray:
    """freq may be a scalar or a per-sample array (then it is integrated)."""
    if np.isscalar(freq):
        return np.sin(TAU * freq * t_axis(n) + phase)
    return np.sin(TAU * np.cumsum(freq) / SR + phase)


def additive_saw(freq: float, n: int, rolloff: float = 1.0, max_hz: float = 8000.0,
                 phase_seed: int | None = None) -> np.ndarray:
    """Band-limited saw-like tone: sum of harmonics with 1/k^rolloff amplitudes."""
    rng = np.random.default_rng(phase_seed)
    t = t_axis(n)
    out = np.zeros(n)
    k = 1
    while k * freq < max_hz:
        out += np.sin(TAU * k * freq * t + rng.uniform(0, TAU)) / k ** rolloff
        k += 1
    return out


def triangle(freq: float, n: int) -> np.ndarray:
    return signal.sawtooth(TAU * freq * t_axis(n), 0.5)


# ---------------------------------------------------------------- envelopes

def adsr(gate: float, a: float, d: float, s: float, r: float) -> np.ndarray:
    """Linear attack, exponential decay to sustain, exponential release after gate."""
    ng, nr = n_samples(gate), n_samples(r)
    t = t_axis(ng)
    env = np.where(t < a, t / max(a, 1e-6),
                   s + (1 - s) * np.exp(-(t - a) / max(d, 1e-6)))
    last = env[-1] if ng else 0.0
    rel = last * np.exp(-t_axis(nr) / max(r / 5, 1e-6))
    return np.concatenate([env, rel])


def exp_decay(n: int, t60: float) -> np.ndarray:
    return np.exp(-6.9 * t_axis(n) / t60)


def release_tail(n_gate: int, n_total: int, r: float) -> np.ndarray:
    env = np.ones(n_total)
    k = n_total - n_gate
    if k > 0:
        env[n_gate:] = np.exp(-6.9 * t_axis(k) / max(r, 1e-4))
    return env


def fade(x: np.ndarray, fin: float = 0.002, fout: float = 0.005) -> np.ndarray:
    x = x.copy()
    a, b = n_samples(fin), n_samples(fout)
    if a:
        x[:a] *= np.linspace(0, 1, a)[:, None] if x.ndim == 2 else np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b)[:, None] if x.ndim == 2 else np.linspace(1, 0, b)
    return x


# ---------------------------------------------------------------- instruments

def epiano(m: float, dur: float, vel: float = 0.7, rel: float = 0.4,
           bright: float = 1.0) -> np.ndarray:
    """2-operator FM electric piano (tine-ish). Returns mono."""
    f = midi_hz(m)
    ng = n_samples(dur)
    n = ng + n_samples(rel)
    t = t_axis(n)
    t60 = float(np.clip(5.5 * (261.6 / f) ** 0.5, 1.0, 8.0))
    amp = np.exp(-6.9 * t / t60) * (1 - np.exp(-t / 0.0015))
    index = bright * (0.3 + 1.4 * vel) * np.exp(-t / 0.22) + 0.12 * vel
    body = np.sin(TAU * f * t + index * np.sin(TAU * f * t))
    body += 0.18 * np.sin(TAU * 2 * f * t) * np.exp(-t / (t60 * 0.25))
    if f * 14 < 15000:  # short metallic "tine" bark
        body += 0.06 * vel * bright * np.sin(TAU * f * 14 * t) * np.exp(-t / 0.01)
    return body * amp * release_tail(ng, n, rel) * vel ** 1.4


def bell(m: float, dur: float, vel: float = 0.6, rel: float = 1.0) -> np.ndarray:
    """Soft music-box-ish FM bell (ratio 3.5) mixed with a sine. Mono."""
    f = midi_hz(m)
    ng = n_samples(dur)
    n = ng + n_samples(rel)
    t = t_axis(n)
    amp = np.exp(-6.9 * t / 3.0) * (1 - np.exp(-t / 0.002))
    index = 1.2 * vel * np.exp(-t / 0.4)
    tone = 0.6 * np.sin(TAU * f * t + index * np.sin(TAU * 3.5 * f * t))
    tone += 0.4 * np.sin(TAU * f * t)
    return tone * amp * release_tail(ng, n, rel) * vel ** 1.3


def pad(m: float, dur: float, vel: float = 0.5, attack: float = 1.2,
        rel: float = 2.0, seed: int = 0) -> np.ndarray:
    """Warm detuned additive pad. Returns stereo."""
    f = midi_hz(m)
    env = adsr(dur, attack, 1.0, 0.8, rel)
    n = len(env)
    voices = []
    for i, cents in enumerate((-7, 0, 6)):
        fi = f * 2 ** (cents / 1200)
        voices.append(additive_saw(fi, n, rolloff=1.6, max_hz=3500, phase_seed=seed + i))
    left = voices[0] + 0.7 * voices[1]
    right = voices[2] + 0.7 * voices[1]
    out = np.stack([left, right], axis=1) * env[:, None] * vel * 0.25
    return out


def soft_bass(m: float, dur: float, vel: float = 0.6) -> np.ndarray:
    f = midi_hz(m)
    env = adsr(dur, 0.012, 0.5, 0.55, 0.12)
    n = len(env)
    t = t_axis(n)
    x = np.sin(TAU * f * t) + 0.25 * np.sin(TAU * 2 * f * t) + 0.08 * np.sin(TAU * 3 * f * t)
    return x * env * vel


def kick(vel: float = 0.6) -> np.ndarray:
    n = n_samples(0.35)
    t = t_axis(n)
    freq = 48 + 70 * np.exp(-t / 0.03)
    return sine(freq, n) * np.exp(-t / 0.09) * (1 - np.exp(-t / 0.002)) * vel


def hat(vel: float = 0.3, seed: int | None = None) -> np.ndarray:
    n = n_samples(0.08)
    x = np.random.default_rng(seed).standard_normal(n)
    x = sos_filter(x, "highpass", 7000, order=4)
    return x * np.exp(-t_axis(n) / 0.018) * vel


def brush(vel: float = 0.3, seed: int | None = None) -> np.ndarray:
    n = n_samples(0.25)
    x = np.random.default_rng(seed).standard_normal(n)
    x = sos_filter(x, "bandpass", (1500, 6000), order=2)
    t = t_axis(n)
    return x * (1 - np.exp(-t / 0.006)) * np.exp(-t / 0.07) * vel


# ---------------------------------------------------------------- filters

def sos_filter(x: np.ndarray, kind: str, fc, order: int = 2) -> np.ndarray:
    """Causal Butterworth filter (for one-shots). kind: lowpass/highpass/bandpass."""
    sos = signal.butter(order, fc, btype=kind, fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def butter_mag(freqs: np.ndarray, kind: str, fc, order: int = 2) -> np.ndarray:
    f = np.maximum(freqs, 1e-3)
    if kind == "lowpass":
        return 1 / np.sqrt(1 + (f / fc) ** (2 * order))
    if kind == "highpass":
        return 1 / np.sqrt(1 + (fc / f) ** (2 * order))
    if kind == "bandpass":
        lo, hi = fc
        return butter_mag(f, "highpass", lo, order) * butter_mag(f, "lowpass", hi, order)
    raise ValueError(kind)


def circ_filter(x: np.ndarray, kind: str, fc, order: int = 2) -> np.ndarray:
    """Zero-phase Butterworth-magnitude filter applied circularly via FFT.
    The buffer is treated as one period, so loops stay seamless."""
    n = x.shape[0]
    freqs = np.fft.rfftfreq(n, 1 / SR)
    h = butter_mag(freqs, kind, fc, order)
    if x.ndim == 2:
        h = h[:, None]
    return np.fft.irfft(np.fft.rfft(x, axis=0) * h, n, axis=0)


# ---------------------------------------------------------------- noise

def colored_noise(n: int, shape=None, seed: int | None = None, channels: int = 1,
                  correlation: float = 0.0) -> np.ndarray:
    """Periodic (perfectly loopable) noise built in the frequency domain.

    shape(freqs) -> magnitude weights. Built-ins: 'white', 'pink', 'brown'.
    correlation in [0,1] mixes a common component into both channels."""
    rng = np.random.default_rng(seed)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    f = np.maximum(freqs, 10.0)
    if shape is None or shape == "white":
        w = np.ones_like(f)
    elif shape == "pink":
        w = 1 / np.sqrt(f)
    elif shape == "brown":
        w = 1 / f
    else:
        w = shape(freqs)
    w = w.copy()
    w[0] = 0

    def one():
        spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) * w
        x = np.fft.irfft(spec, n)
        return x / rms(x)

    if channels == 1:
        return one()
    common = one()
    chans = [np.sqrt(1 - correlation) * one() + np.sqrt(correlation) * common
             for _ in range(channels)]
    return np.stack(chans, axis=1)


def noise(n: int, seed: int | None = None) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n)


def periodic_lfo(n: int, cycles: int, phase: float = 0.0) -> np.ndarray:
    """Sine LFO with an integer number of cycles over the buffer (loop-safe)."""
    return np.sin(TAU * cycles * np.arange(n) / n + phase)


def smooth_random(n: int, points: int, seed: int | None = None, circular: bool = True) -> np.ndarray:
    """Slowly varying random curve in [-1, 1] (cosine-interpolated control points)."""
    rng = np.random.default_rng(seed)
    pts = rng.uniform(-1, 1, points + 1)
    if circular:
        pts[-1] = pts[0]
    pos = np.arange(n) / n * points
    i = np.floor(pos).astype(int)
    fr = pos - i
    w = (1 - np.cos(np.pi * fr)) / 2
    return pts[i] * (1 - w) + pts[np.minimum(i + 1, points)] * w


# ---------------------------------------------------------------- reverb

def reverb_ir(t60: float = 2.0, predelay: float = 0.02, damp_hz: float = 4000,
              seed: int = 7, length: float | None = None) -> np.ndarray:
    """Synthetic stereo impulse response: decaying decorrelated noise that gets
    darker over time. Energy-normalised."""
    length = length or t60 * 1.1
    n = n_samples(length)
    t = t_axis(n)
    raw = colored_noise(n, "white", seed=seed, channels=2)
    dark = circ_filter(raw, "lowpass", damp_hz, order=1)
    darker = circ_filter(raw, "lowpass", damp_hz / 4, order=1)
    mix = np.clip(t / t60, 0, 1)[:, None]
    ir = (dark * (1 - mix) + darker * mix) * np.exp(-6.9 * t / t60)[:, None]
    ir *= (1 - np.exp(-t / 0.01))[:, None]
    pd = np.zeros((n_samples(predelay), 2))
    ir = np.concatenate([pd, ir])
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


def convolve(x: np.ndarray, ir: np.ndarray, loop: bool) -> np.ndarray:
    x = stereo(x)
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1)
    return fold_loop(y, len(x)) if loop else y


def reverb(x: np.ndarray, ir: np.ndarray, wet: float = 0.25, loop: bool = True) -> np.ndarray:
    x = stereo(x)
    w = convolve(x, ir, loop)
    if not loop:
        x = np.concatenate([x, np.zeros((len(w) - len(x), 2))])
    return x * (1 - wet * 0.5) + w * wet


# ---------------------------------------------------------------- sequencing

class Timeline:
    """Stereo mix bus with sample-accurate placement. For loops, render onto a
    buffer of length `loop` and anything that rings past the end is folded back
    onto the start (exactly what a looping player would sound like)."""

    def __init__(self, seconds: float, tail: float = 12.0):
        self.n = n_samples(seconds)
        self.buf = np.zeros((self.n + n_samples(tail), 2))

    def add(self, x: np.ndarray, at: float, gain: float = 1.0, pan_pos: float = 0.0):
        x = pan(x, pan_pos) if x.ndim == 1 else x
        s = n_samples(at) % self.n if at >= 0 else n_samples(at) % self.n
        e = min(s + len(x), len(self.buf))
        self.buf[s:e] += x[: e - s] * gain
        if s + len(x) > len(self.buf):  # very long sound: wrap remainder
            self.add(x[e - s:], (e % self.n) / SR, gain, 0.0)

    def loop(self) -> np.ndarray:
        return fold_loop(self.buf, self.n)

    def oneshot(self) -> np.ndarray:
        nz = np.nonzero(np.max(np.abs(self.buf), axis=1) > 1e-5)[0]
        end = (nz[-1] + 1) if len(nz) else self.n
        return self.buf[: max(end, self.n)]


def fold_loop(x: np.ndarray, n: int) -> np.ndarray:
    """Wrap everything beyond n samples back onto the head (circular sum)."""
    out = x[:n].copy()
    tail = x[n:]
    while len(tail):
        k = min(n, len(tail))
        out[:k] += tail[:k]
        tail = tail[k:]
    return out


def crossfade_loop(x: np.ndarray, n: int, xf: int, equal_power: bool = True) -> np.ndarray:
    """Make a loop of n samples from a longer buffer (len >= n + xf) by crossfading
    the material that follows the loop end (the tail) into the head."""
    assert len(x) >= n + xf, "buffer too short for crossfade"
    out = x[:n].copy()
    th = np.linspace(0, np.pi / 2, xf)
    if equal_power:
        fin, fout = np.sin(th), np.cos(th)
    else:
        fin = th / (np.pi / 2)
        fout = 1 - fin
    if x.ndim == 2:
        fin, fout = fin[:, None], fout[:, None]
    out[:xf] = x[n:n + xf] * fout + x[:xf] * fin
    return out


def delay_echo(x: np.ndarray, delay: float, feedback: float = 0.35, taps: int = 4,
               pingpong: bool = True, loop: bool = True, lp_hz: float = 3000) -> np.ndarray:
    """Simple tape-ish echo; each repeat is darker. Circular when loop=True."""
    x = stereo(x)
    d = n_samples(delay)
    n = len(x)
    out = np.zeros((n + d * taps, 2)) if not loop else np.zeros_like(x)
    cur = x
    for k in range(1, taps + 1):
        cur = circ_filter(cur, "lowpass", lp_hz, 1) if loop else sos_filter(cur, "lowpass", lp_hz, 1)
        g = feedback ** k
        tap = cur[:, ::-1] if (pingpong and k % 2) else cur
        if loop:
            out += np.roll(tap, d * k, axis=0) * g
        else:
            out[d * k:d * k + n] += tap * g
    return out


# ---------------------------------------------------------------- mastering / io

def soft_limit(x: np.ndarray, ceiling: float) -> np.ndarray:
    """Memoryless soft knee: transparent below 70% of ceiling (keeps loops exact)."""
    thr = 0.7 * ceiling
    a = np.abs(x)
    over = a > thr
    y = x.copy()
    y[over] = np.sign(x[over]) * (thr + (ceiling - thr) * np.tanh((a[over] - thr) / (ceiling - thr)))
    return y


def write_wav(path: str, x: np.ndarray):
    wavfile.write(path, SR, stereo(x).astype(np.float32))


def measure_lufs(x: np.ndarray, loop: bool = False) -> float:
    """Integrated loudness via ffmpeg's ebur128 filter."""
    if loop:
        x = np.concatenate([x, x])
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.wav")
        write_wav(p, x)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", p, "-af",
                            "ebur128=framelog=quiet", "-f", "null", "-"],
                           capture_output=True, text=True, check=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1])


def master_loudness(x: np.ndarray, target_lufs: float, ceiling_db: float = -1.0,
                    loop: bool = True) -> np.ndarray:
    ceiling = db(ceiling_db)
    for _ in range(3):
        x = x * db(target_lufs - measure_lufs(x, loop))
        x = soft_limit(x, ceiling)
    return x


def master_peak(x: np.ndarray, peak_db: float = -3.0) -> np.ndarray:
    return x * (db(peak_db) / np.max(np.abs(x)))


def encode_ogg(x: np.ndarray, out_path: str, quality: int = 10):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.wav")
        write_wav(p, x)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", p,
                        "-c:a", "libvorbis", "-q:a", str(quality), out_path], check=True)


def decode(path: str) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path,
                        "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2)


def seam_ratio(x: np.ndarray) -> float:
    """Loop seam discontinuity |x[0]-x[-1]| relative to the 99.9th percentile of
    ordinary sample-to-sample steps. <~1.5 means the seam is indistinguishable
    from normal signal motion (no click)."""
    x = stereo(x)
    steps = np.abs(np.diff(x, axis=0))
    ref = np.percentile(steps, 99.9, axis=0) + 1e-9
    jump = np.abs(x[0] - x[-1])
    return float(np.max(jump / ref))


# ---------------------------------------------------------------- dream (XVIII c.) instruments

def pluck(m: float, dur: float, vel: float = 0.7, pos: float = 0.13, t60: float | None = None,
          rolloff: float = 0.8, max_hz: float = 11000.0, hf_damp: float = 0.15,
          rel: float = 0.08, chorus_cents: float = 0.0, seed: int | None = None) -> np.ndarray:
    """Additive plucked string. `pos` is the pluck position (0.5 = middle, small = bright and
    nasal), higher harmonics decay faster (`hf_damp`), the damper stops the note `rel` s after
    `dur`. With chorus_cents a second detuned string is added (two-choir harpsichord). Mono."""
    f = midi_hz(m)
    rng = np.random.default_rng(seed if seed is not None else int(m * 1000 + dur * 100))
    if t60 is None:
        t60 = float(np.clip(3.2 * (261.6 / f) ** 0.6, 0.6, 6.0))
    ring = min(dur, t60 * 1.2)
    ng = n_samples(ring)
    n = ng + n_samples(rel)
    t = t_axis(n)
    kmax = max(1, int(max_hz / f))
    k = np.arange(1, kmax + 1)
    amps = np.abs(np.sin(np.pi * k * pos)) / k ** rolloff
    decays = t60 / (1 + hf_damp * (k - 1))
    out = np.zeros(n)
    for c, cents in enumerate((0.0, chorus_cents) if chorus_cents else (0.0,)):
        fc = f * 2 ** (cents / 1200)
        ph = rng.uniform(0, TAU, len(k))
        g = 1.0 if c == 0 else 0.6
        for j in range(0, len(k), 16):  # chunks keep memory bounded for low, long notes
            ks = slice(j, j + 16)
            out += g * np.sum(amps[ks, None] * np.sin(TAU * fc * k[ks, None] * t[None, :] + ph[ks, None])
                              * np.exp(-6.9 * t[None, :] / decays[ks, None]), axis=0)
    out /= np.sum(amps) * 0.6
    out *= 1 - np.exp(-t / 0.0007)
    return out * release_tail(ng, n, rel) * vel ** 1.2


def harpsichord(m: float, dur: float, vel: float = 0.7, bright: float = 1.0) -> np.ndarray:
    """Two-choir harpsichord: bright pluck + quill click. bright<1 is the softer 'lute' stop."""
    pos = 0.11 + 0.12 * (1 - bright)
    x = pluck(m, dur, vel, pos=pos, rolloff=0.75 + 0.5 * (1 - bright), hf_damp=0.12 + 0.1 * (1 - bright),
              max_hz=6000 + 6000 * bright, chorus_cents=3.5, rel=0.06)
    n = len(x)
    q = min(n, n_samples(0.02))
    click = sos_filter(noise(q, int(m * 7)), "bandpass", (2500, 9000), 2) * np.exp(-t_axis(q) / 0.002)
    x[:q] += click * 0.06 * bright * vel
    return x


def pizz(m: float, vel: float = 0.7) -> np.ndarray:
    """Pizzicato cello/bass: round pluck, short ring."""
    f = midi_hz(m)
    return pluck(m, 0.9, vel, pos=0.27, t60=float(np.clip(0.9 * (110 / f) ** 0.3, 0.35, 1.2)),
                 rolloff=1.5, hf_damp=0.5, max_hz=2500, rel=0.1)


def _bowed(f0: float, n: int, rng, vib_rate: float, vib_depth: float, vib_delay: float,
           max_hz: float, rolloff: float) -> np.ndarray:
    t = t_axis(n)
    vib = vib_depth * np.clip((t - vib_delay) / 0.4, 0, 1) * np.sin(TAU * vib_rate * t + rng.uniform(0, TAU))
    wander = 0.0015 * smooth_random(n, max(2, int(n / SR * 2)), seed=int(rng.integers(1 << 30)), circular=False)
    fi = f0 * (1 + vib + wander)
    phase = TAU * np.cumsum(fi) / SR
    kmax = max(1, int(max_hz / f0))
    k = np.arange(1, kmax + 1)
    fk = f0 * k
    # violin-ish body: dip below 250 Hz, broad hump 400-3500 Hz, rolled-off top
    w = butter_mag(fk, "bandpass", (250, 3500), 1) / k ** rolloff
    ph = rng.uniform(0, TAU, kmax)
    out = np.zeros(n)
    for i in range(kmax):  # loop keeps memory low for long notes
        out += w[i] * np.sin(k[i] * phase + ph[i])
    return out / (np.sum(w) * 0.5)


def strings(m: float, dur: float, vel: float = 0.6, attack: float = 0.25, rel: float = 0.6,
            voices: int = 3, solo: bool = False, seed: int = 0) -> np.ndarray:
    """Bowed strings. voices>1 = section (detuned, spread), solo=True = one expressive violin
    with stronger vibrato and a touch of bow noise. Returns stereo."""
    rng = np.random.default_rng(seed + int(m * 31))
    f = midi_hz(m)
    env = adsr(dur, attack, 0.6, 0.85, rel)
    n = len(env)
    if solo:
        voices = 1
    out = np.zeros((n, 2))
    spreads = np.linspace(-0.6, 0.6, voices) if voices > 1 else [0.0]
    for i, p in enumerate(spreads):
        cents = 0.0 if voices == 1 else rng.uniform(-9, 9)
        x = _bowed(f * 2 ** (cents / 1200), n, rng, vib_rate=rng.uniform(5.0, 6.2),
                   vib_depth=(0.0045 if solo else 0.0028), vib_delay=0.15 if solo else 0.05,
                   max_hz=7000 if solo else 5000, rolloff=0.9 if solo else 1.05)
        out += pan(x, p)
    if solo:
        bow = sos_filter(noise(n, seed + 5), "bandpass", (min(f * 2, 5000), min(f * 5, 9000)), 2)
        out += stereo(bow * 0.012)
    out /= np.sqrt(voices)
    return out * env[:, None] * vel * 0.5


def flute(m: float, dur: float, vel: float = 0.6, seed: int = 0) -> np.ndarray:
    """Wooden traverso-ish flute: near-sine with breath. Mono."""
    f = midi_hz(m)
    env = adsr(dur, 0.06, 0.3, 0.8, 0.18)
    n = len(env)
    t = t_axis(n)
    rng = np.random.default_rng(seed + int(m))
    vib = 0.004 * np.clip((t - 0.25) / 0.5, 0, 1) * np.sin(TAU * 4.8 * t + rng.uniform(0, TAU))
    phase = TAU * np.cumsum(f * (1 + vib)) / SR
    tone = np.sin(phase) + 0.22 * np.sin(2 * phase + 0.4) + 0.07 * np.sin(3 * phase + 1.1)
    breath = sos_filter(noise(n, seed + int(m) * 3), "bandpass", (min(f * 1.5, 7000), min(f * 4, 10000)), 2)
    chiff = np.exp(-t / 0.04)
    x = tone * (1 + 0.04 * np.sin(TAU * 0.9 * t)) + breath * (0.06 + 0.25 * chiff)
    return x * env * vel * 0.6


def timpani(m: float, vel: float = 0.7, dur: float = 2.0) -> np.ndarray:
    """Kettle drum: inharmonic membrane partials + felt mallet thump. Mono."""
    f = midi_hz(m)
    n = n_samples(dur)
    t = t_axis(n)
    drop = 1 + 0.03 * np.exp(-t / 0.05)
    out = np.zeros(n)
    for r, a, d in ((1.0, 1.0, 0.9), (1.5, 0.5, 0.6), (1.98, 0.3, 0.45), (2.44, 0.18, 0.3), (0.5, 0.25, 0.25)):
        out += a * sine(f * r * drop, n) * np.exp(-t / d)
    thump = sos_filter(noise(n, int(m)), "lowpass", 400, 2) * np.exp(-t / 0.02)
    out = out + thump * 0.8
    return out * (1 - np.exp(-t / 0.002)) * vel * 0.6


def glass(m: float, dur: float, vel: float = 0.5, attack: float = 0.4, rel: float = 1.5) -> np.ndarray:
    """Glass harmonica: pure sine pair with slow beating, soft attack. Mono."""
    f = midi_hz(m)
    env = adsr(dur, attack, 1.0, 0.9, rel)
    n = len(env)
    x = sine(f, n) + 0.6 * sine(f * 1.0015, n, 1.0) + 0.12 * sine(2 * f, n, 0.3) + 0.05 * sine(3.01 * f, n)
    return x * env * vel * 0.4


def tone_loop(freq: float, n: int, phase: float = 0.0) -> np.ndarray:
    """Steady sine rounded to an integer number of cycles over n samples (loop-safe drone)."""
    cyc = max(1, round(freq * n / SR))
    return np.sin(TAU * cyc * np.arange(n) / n + phase)
