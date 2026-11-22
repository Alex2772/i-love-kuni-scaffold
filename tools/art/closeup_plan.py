#!/usr/bin/env python3
"""Close-ups for the panels that blow their art up into pixels (story/tests/ArtDensityTest.cpp).

Reads what each offending panel shows of its picture (KN_DENSITY_CROPS=<file> of the test) and plans `gen: closeup`
pictures: the panels of one picture whose pieces lie close together share one close-up, if it stays dense enough for
each of them. Writes, per doc, the docs/art blocks of its close-ups (with the `_pink` twin if the source has one, the
layout of the source moved into the piece) and edits.tsv: per panel, the close-up and the `.focus`/`.zoom` that show
the same piece.

    KN_DENSITY_CROPS=/tmp/crops.txt build/bin/Tests --gtest_filter=Story.ArtIsNotBlownUpIntoPixels
    python3 -I tools/art/closeup_plan.py /tmp/crops.txt --out /tmp/plan [--min 0.4]
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("generate", ROOT / "tools/art/generate.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

RATIOS = [1, 1.5, 2 / 3, 16 / 9, 9 / 16, 4 / 3, 3 / 4, 4 / 5, 5 / 4]   # what gemini draws (generate.aspect_for)
MARGIN = 0.06   # of the piece, on every side: room for gemini to move things a bit


def base(art):
    return art[:-5] if art.endswith("_pink") else art


def fit_aspect(r, size):
    """Grow piece r (fractions) to the nearest ratio gemini draws, inside the picture."""
    x, y, w, h = r
    sw, sh = size
    a = (w * sw) / (h * sh)
    want = min(RATIOS, key=lambda k: abs(k - a))
    if want > a:
        w = min(1, h * sh * want / sw)
    else:
        h = min(1, w * sw / want / sh)
    cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
    x = min(max(cx - w / 2, 0), 1 - w)
    y = min(max(cy - h / 2, 0), 1 - h)
    return [x, y, w, h]


def grow(r, m):
    x, y, w, h = r
    x0, y0 = max(0, x - w * m), max(0, y - h * m)
    x1, y1 = min(1, x + w * (1 + m)), min(1, y + h * (1 + m))
    return [x0, y0, x1 - x0, y1 - y0]


def union(a, b):
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return [x0, y0, x1 - x0, y1 - y0]


def piece_for(regions, size):
    r = regions[0]
    for o in regions[1:]:
        r = union(r, o)
    return fit_aspect(grow(r, MARGIN), size)


def scale_of(piece, size):
    """Close-up px per source px."""
    return 1216 / max(piece[2] * size[0], piece[3] * size[1])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("crops")
    p.add_argument("--min", type=float, default=0.4, help="density every panel gets from its close-up")
    p.add_argument("--out", required=True, help="folder for <doc>.md blocks to append to docs/art and edits.tsv")
    a = p.parse_args()

    panels = {}   # base art -> [(where, region, box, density, arts)]
    for line in Path(a.crops).read_text().splitlines():
        f = line.split()
        region, box, where, art, density = [float(v) for v in f[:4]], [float(v) for v in f[4:6]], f[6], f[7], float(f[8])
        rows = panels.setdefault(base(art), [])
        for row in rows:
            if row[0] == where:
                row[4].add(art)
                break
        else:
            rows.append((where, region, box, density, {art}))

    images = gen.parse_docs()
    blocks = {}   # doc -> [docs/art lines]
    edits = []    # (where, old art, new art, focus, zoom)
    for art, rows in sorted(panels.items()):
        size = gen.image_size(gen.GAME_DIR / f"{art}.webp")
        groups = []   # [[rows], piece]
        for row in sorted(rows, key=lambda r: r[3]):
            for g in groups:
                piece = piece_for([r[1] for r in g[0]] + [row[1]], size)
                k = scale_of(piece, size)
                if all(r[3] * k >= a.min for r in g[0] + [row]):
                    g[0].append(row)
                    g[1] = piece
                    break
            else:
                groups.append([[row], piece_for([row[1]], size)])
        doc, name = art.split("/")
        src = images[art]
        pink = images.get(art + "_pink")
        for n, (rows_, piece) in enumerate(groups, 1):
            cid = f"{name}_close" + (str(n) if len(groups) > 1 else "")
            k = scale_of(piece, size)
            out = blocks.setdefault(doc, [])
            layout = layout_lines(src, piece)
            out += [f"### {cid}",
                    f"Крупный план `{name}` для {', '.join(r[0] for r in rows_)}: zoom общего плана был мозаикой "
                    f"(story/tests/ArtDensityTest.cpp).",
                    f"- gen: closeup {name} " + " ".join(f"{v:.4f}" for v in piece)]
            out += tag_lines(src) + layout
            out += ["- prompt: the same as the first image.", ""]
            if pink:
                out += [f"### {cid}_pink", f"- gen: edit {cid}"] + tag_lines(pink) + layout
                out += [f"- prompt: {pink['prompt']}", ""]
            for where, region, box, density, arts in rows_:
                rx, ry = (region[0] - piece[0]) / piece[2], (region[1] - piece[1]) / piece[3]
                rw, rh = region[2] / piece[2], region[3] / piece[3]
                cw, ch = piece[2] * size[0] * k, piece[3] * size[1] * k
                zoom = (box[0] / rw) / (cw * max(box[0] / cw, box[1] / ch))
                edits.append((where, art, f"{doc}/{cid}", bool(pink), rx + rw / 2, ry + rh / 2, zoom, density, density * k))
    for doc, lines in sorted(blocks.items()):
        Path(a.out, f"{doc}.md").write_text("\n".join(lines))
    Path(a.out, "edits.tsv").write_text("".join(
        f"{w}\t{o}\t{n}\t{int(pk)}\t{fx:.4f}\t{fy:.4f}\t{z:.4f}\t{d0:.2f}\t{d1:.2f}\n" for w, o, n, pk, fx, fy, z, d0, d1 in edits))
    print(f"{sum(len([l for l in v if l.startswith('### ')]) for v in blocks.values())} pictures, {len(edits)} panels -> {a.out}")


def tag_lines(img):
    out = []
    for key in ("time", "world", "hair", "outfit", "bell"):
        if key in img:
            out.append(f"- {key}: {img[key]}")
    if "has" in img:
        out.append(f"- has: {' '.join(img['has'])}")
    return out


def layout_lines(img, piece):
    """The layout of the source moved into the piece: heads inside it, boxes clipped, the screen as is."""
    x, y, w, h = piece

    def box(b):
        x0, y0, x1, y1 = max(b[0], x), max(b[1], y), min(b[0] + b[2], x + w), min(b[1] + b[3], y + h)
        if x1 - x0 < 0.005 or y1 - y0 < 0.005:
            return None
        return [(x0 - x) / w, (y0 - y) / h, (x1 - x0) / w, (y1 - y0) / h]

    fmt = lambda b: " ".join(f"{v:.3f}" for v in b)
    out = []
    for key in ("avoid", "censor"):
        boxes = [b for b in map(box, img[key]) if b]
        if boxes:
            out.append(f"- {key}: " + "; ".join(map(fmt, boxes)))
    for who, (px, py) in img["anchors"].items():
        if x <= px <= x + w and y <= py <= y + h:
            out.append(f"- {who}: {(px - x) / w:.3f} {(py - y) / h:.3f}")
    if "screen" in img and box(img["screen"][:4]):
        # not clipped: the engine lays the text out over the whole screen, the panel cuts it as it cut the wide shot
        sx, sy, sw, sh = img["screen"][:4]
        out.append(f"- screen: {(sx - x) / w:.4f} {(sy - y) / h:.4f} {sw / w:.4f} {sh / h:.4f}" + "".join(f" {v:g}" for v in img["screen"][4:]))
    return out


if __name__ == "__main__":
    main()
