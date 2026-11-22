#!/usr/bin/env python3
"""Nudity goes to extras/ (kn/Resources.h): an art with `censor` boxes (data/img/<id>.json, from docs/art) keeps its
original in extras/img/<id>.webp, which is not in the repository (extras.zip, uploaded to itch.io by hand), and data/
gets the same picture with the boxes painted black. Without extras.zip, or with «Цензурировать наготу», the game
shows the data/ one.

Run it after an art with `censor` is made or retouched in data/img, or after its boxes change: a picture already in
extras/ is the original (a new data/ one replaces it there, see --from-data), the data/ one is painted from it anew.

    python3 -I tools/art/split_extras.py [--from-data ID ...] [--check]
"""
import argparse, json, shutil, sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/img"
EXTRAS = ROOT / "extras/img"
QUALITY = 92


def censored():
    """(id, boxes) of every art with censor boxes."""
    for layout in sorted(DATA.rglob("*.json")):
        boxes = json.loads(layout.read_text()).get("censor") or []
        if boxes:
            yield layout.relative_to(DATA).with_suffix("").as_posix(), boxes


def paint(original: Path, boxes, out: Path):
    with Image.open(original) as img:
        img = img.convert("RGB")
        w, h = img.size
        draw = ImageDraw.Draw(img)
        for x, y, bw, bh in boxes:
            # as the game drew them: outward to whole pixels, nothing of the box left uncovered
            draw.rectangle([int(x * w), int(y * h), int((x + bw) * w + 0.999) - 1, int((y + bh) * h + 0.999) - 1], fill="black")
        img.save(out, "WEBP", quality=QUALITY, method=6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-data", nargs="*", default=[], metavar="ID",
                    help="the data/ picture of these ids is a new original (made or retouched there): it replaces extras/")
    ap.add_argument("--check", action="store_true", help="only tell what has no original in extras/")
    a = ap.parse_args()
    missing = []
    for id, boxes in censored():
        data, extra = DATA / f"{id}.webp", EXTRAS / f"{id}.webp"
        if not data.exists():
            print(f"{id}: no {data.relative_to(ROOT)}", file=sys.stderr)
            continue
        if a.check:
            if not extra.exists():
                missing.append(id)
            continue
        if id in a.from_data or not extra.exists():
            extra.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(data, extra)
            print(f"{id}: original -> {extra.relative_to(ROOT)}")
        paint(extra, boxes, data)
        print(f"{id}: censored -> {data.relative_to(ROOT)}")
    if missing:
        print("no original in extras/: " + " ".join(missing), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
