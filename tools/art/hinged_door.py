#!/usr/bin/env python3
"""Hinged door in perspective: composes `prologue/wr_slam` / `ai2_door_slam` bases (see docs/art/README.md,
«Геометрию считаем сами»). Run: uv run --with numpy --with pillow --with scipy tools/art/hinged_door.py <out_dir>
Output: comp_wr.png (empty room) and comp_ai.png (girl in front): the leaf rotated around the hinge edge in 3 phases,
ghosts at 42% / 30% opacity. The model then only adds speed lines/dust (prompts in docs/art/README.md)."""
import math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

IMG = Path(__file__).resolve().parents[2] / 'data/img/prologue'
wr = Image.open(IMG / 'wr_door.webp').convert('RGB')
ai = Image.open(IMG / 'ai2_door.webp').convert('RGB')
CX, CY, Z0 = 608, 455, 970        # vanishing point (picture centre) and camera distance in px, picked by eye


def coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return [float(v) for v in np.linalg.solve(np.array(A, float), np.array(B, float))]


def compose(room, leaf, xh, w, top, bot, keep=None):
    """xh: hinge x, w: leaf width, top/bot: leaf edges (px). keep: mask of what stands in front of the door."""
    W, H = room.size
    src = [(0, 0), (w, 0), (w, bot - top), (0, bot - top)]
    out = room.copy()
    ImageDraw.Draw(out).rectangle((xh - 1, top, xh + w + 1, bot), fill=(232, 232, 232))   # empty doorway

    def quad(deg):
        t = math.radians(deg)
        x_free = xh + w * math.cos(t)               # free edge: moves toward the camera as the door opens
        s = Z0 / (Z0 - w * math.sin(t))             # nearer = bigger
        x = CX + (x_free - CX) * s
        return [(xh, top), (x, CY + (top - CY) * s), (x, CY + (bot - CY) * s), (xh, bot)]

    for deg, alpha in ((20, 1.0), (45, .42), (70, .30)):   # the main leaf last-closed, ghosts wider open
        q = quad(deg)
        warped = leaf.transform((W, H), Image.PERSPECTIVE, coeffs(q, src), Image.BICUBIC, fillcolor=(255, 255, 255))
        m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon(q, fill=int(255 * alpha))
        out.paste(warped, (0, 0), m)
        g = int(255 - 230 * alpha)
        ImageDraw.Draw(out).line(q + [q[0]], fill=(g, g, g), width=3 if alpha > .8 else 2)
    if keep is not None:
        out.paste(room, (0, 0), keep)
    return out


out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
compose(wr, wr.crop((519, 188, 737, 719)), 519, 219, 188, 719).save(out / 'comp_wr.png')
# the girl: the dark connected blob that contains her hair, holes filled (the handle is a separate blob)
g = np.array(ai.convert('L')) < 170
lab, _ = ndi.label(ndi.binary_dilation(g, iterations=3))
girl = lab == lab[300, 605]
xs, ys = np.arange(ai.width)[None, :], np.arange(ai.height)[:, None]
girl &= (xs > 524) & (xs < 735) & (ys > 240)
girl = ndi.binary_dilation(ndi.binary_fill_holes(ndi.binary_closing(girl, iterations=6)), iterations=1)
compose(ai, wr.crop((519, 188, 737, 719)).resize((212, 528)), 522, 212, 185, 713,
        Image.fromarray((girl * 255).astype('uint8'))).save(out / 'comp_ai.png')
