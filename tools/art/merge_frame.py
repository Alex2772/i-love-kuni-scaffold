#!/usr/bin/env python3
"""A frame of a gesture (gesture::Tap/Stir `frames`, docs/STORY_API.md «Жесты на панели») onto its base picture.

An edit by the model redraws the whole picture a few px off (shifted, a little scaled): swapped in place of the base,
the room trembles. This aligns the frame to the base by what did not change (outside `zone`), then takes only the
`zone` from it, feathered, over the base: outside it the frame IS the base, pixel for pixel.

    tools/music/.venv/bin/python tools/art/merge_frame.py data/img/ch1/clock_cat.webp data/img/ch1/clock_cat_swing_l.webp 0.45 0.38 0.2 0.3

`zone` is x y w h in fractions of the picture: what moves (the pendulum in its glass, the cup with the hand). The frame
is rewritten in place; mark its spec `- frozen:` so generate.py does not draw it over again.
"""
import argparse
import subprocess

import numpy as np
from scipy import ndimage


def load(path):
    w, h = map(int, subprocess.check_output(["magick", "identify", "-format", "%w %h", path]).split())
    raw = subprocess.check_output(["magick", path, "-depth", "8", "rgb:-"])
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32)


def save(path, img):
    h, w, _ = img.shape
    data = np.clip(img + 0.5, 0, 255).astype(np.uint8).tobytes()
    subprocess.run(["magick", "-size", f"{w}x{h}", "-depth", "8", "rgb:-", "-quality", "92", path], input=data, check=True)


def warp(img, scale, dx, dy):
    """The picture scaled about its center and shifted by (dx, dy) px: out(p) = img((p - c - d) / s + c)."""
    h, w = img.shape[:2]
    c = np.array([h, w], np.float32) * 0.5
    matrix = np.eye(2) / scale
    offset = c - (c + np.array([dy, dx])) / scale
    if img.ndim == 2:
        return ndimage.affine_transform(img, matrix, offset, order=1, mode="nearest")
    return np.stack([ndimage.affine_transform(img[..., k], matrix, offset, order=1, mode="nearest") for k in range(3)], -1)


def zone_mask(h, w, zone, feather):
    x, y, zw, zh = zone
    m = np.zeros((h, w), np.float32)
    m[int(y * h):int((y + zh) * h), int(x * w):int((x + zw) * w)] = 1
    return ndimage.gaussian_filter(m, feather * w) if feather > 0 else m


def align(base, frame, keep):
    """(scale, dx, dy) of the frame that matches the base best where `keep` is 1, coarse to fine on gray pictures."""
    gray = lambda a: a.mean(-1)
    best = (1.0, 0.0, 0.0)
    for factor, scales, shifts in ((4, np.linspace(0.97, 1.03, 13), np.arange(-16, 17, 2)),
                                   (2, np.linspace(-0.004, 0.004, 5), np.arange(-3, 4, 1)),
                                   (1, np.linspace(-0.001, 0.001, 3), np.arange(-1.5, 1.6, 0.5))):
        b = gray(base)[::factor, ::factor]
        f = gray(frame)[::factor, ::factor]
        k = keep[::factor, ::factor]
        s0, x0, y0 = best
        if factor == 4:   # the whole range, then finer and finer round the best so far
            candidates = [(s, sx, sy) for s in scales for sx in shifts for sy in shifts]
        else:
            candidates = [(s0 + ds, x0 + sx, y0 + sy) for ds in scales for sx in shifts for sy in shifts]
        score = lambda c: float((np.abs(warp(f, c[0], c[1] / factor, c[2] / factor) - b) * k).sum())
        best = min(candidates, key=score)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("frame")
    ap.add_argument("zone", nargs=4, type=float, help="x y w h fractions: what moves")
    ap.add_argument("--feather", type=float, default=0.02, help="of the picture width")
    a = ap.parse_args()
    base, frame = load(a.base), load(a.frame)
    h, w = base.shape[:2]
    m = zone_mask(h, w, a.zone, a.feather)
    s, dx, dy = align(base, frame, 1 - zone_mask(h, w, a.zone, 0.05))
    print(f"{a.frame}: scale {s:.4f}, shift {dx:+.1f} {dy:+.1f} px")
    aligned = warp(frame, s, dx, dy)
    save(a.frame, base * (1 - m[..., None]) + aligned * m[..., None])


if __name__ == "__main__":
    main()
