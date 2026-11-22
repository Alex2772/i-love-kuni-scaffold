#!/usr/bin/env python3
"""A tarot card face of the minigame (docs/art/tarot.md, «Карты»): the illustration `art/base/tarot/ill_<card>.webp`
is painted into the window of the empty face `data/img/tarot/card_face.webp`, its edges fade into the parchment. The
frame is never redrawn by the model, so it is the same on every card. The numeral and the name are drawn by the engine
(above and below the window), the keywords on the paper under the card.

    python3 -I tools/art/tarot_card.py fool hermit     # these cards
    python3 -I tools/art/tarot_card.py                 # every ill_* there is
then `python3 -I tools/art/generate.py --adopt tarot/card_<card>`.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
FACE = ROOT / "data" / "img" / "tarot" / "card_face.webp"
BASE = ROOT / "art" / "base" / "tarot"
OUT = ROOT / "data" / "img" / "tarot"
# the window on the 832x1216 face: between the star (numeral under it) and the band of the name above the moon
X0, Y0, X1, Y1 = 92, 205, 740, 990
TRIM = 0.035   # the model's own edges of the illustration


def compose(ill_path, out_path):
    face = Image.open(FACE).convert("RGB")
    ill = Image.open(ill_path).convert("RGB")
    W, H = X1 - X0, Y1 - Y0
    w, h = ill.size
    ill = ill.crop((int(w * TRIM), int(h * TRIM), int(w * (1 - TRIM)), int(h * (1 - TRIM))))
    w, h = ill.size
    k = max(W / w, H / h)
    ill = ill.resize((round(w * k), round(h * k)), Image.LANCZOS)
    left, top = (ill.width - W) // 2, (ill.height - H) // 2
    ill = ill.crop((left, top, left + W, top + H))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((26, 26, W - 27, H - 27), 60, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(22))
    # a little of the parchment grain shows through the paint
    base = face.crop((X0, Y0, X1, Y1))
    painted = Image.blend(ill, Image.composite(ill, base, Image.new("L", (W, H), 235)), 0.5)
    face.paste(painted, (X0, Y0), mask)
    face.save(out_path, quality=88)


def main():
    names = sys.argv[1:] or sorted(p.stem.removeprefix("ill_") for p in BASE.glob("ill_*.webp"))
    for name in names:
        compose(BASE / f"ill_{name}.webp", OUT / f"card_{name}.webp")
        print(OUT / f"card_{name}.webp")


if __name__ == "__main__":
    main()
