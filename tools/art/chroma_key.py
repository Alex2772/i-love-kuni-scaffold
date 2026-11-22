"""Chroma-key cutout of a sprite: a flat green (#00FF00) background -> alpha, despilled, trimmed, scaled to a height.

The white-background floodfill of generate.py (`cutout`) leaves a white rim between thin hair strands and white islands
it cannot reach (between the legs): reader wave 3 E #1 / F #1 on `edge/kuni_corridor`. For a sprite with loose hair ask
gemini to repaint only the background flat green, then cut it out here:

    python3 -I tools/art/chroma_key.py green.png data/img/edge/kuni_corridor.webp 1188
"""
import sys

from PIL import Image

LO, HI = 40, 140   # green excess (g - max(r, b)) where the alpha starts to fall and where it is gone


def alpha_of(excess):
    if excess <= LO:
        return 255
    if excess >= HI:
        return 0
    return int(255 * (HI - excess) / (HI - LO))


def main(src, dst, height):
    im = Image.open(src).convert("RGB")
    px = im.load()
    out = Image.new("RGBA", im.size)
    po = out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            excess = g - max(r, b)
            po[x, y] = (r, min(g, max(r, b)), b, alpha_of(excess))   # despill: no green tint on the edges
    out = out.crop(out.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox())
    out = out.resize((round(out.width * height / out.height), height), Image.LANCZOS)
    out.save(dst, quality=92, alpha_quality=100)
    print(f"{dst}: {out.size[0]}x{out.size[1]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
