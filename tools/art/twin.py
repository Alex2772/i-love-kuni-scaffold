#!/usr/bin/env python3
"""Distorted twins of Kuni's «empty» VN sprite (data/img/edge/kuni_twin_{1,2,3}.webp), «На краю контекста».

img2img on the local SDXL WebUI, WITHOUT resize (the sprite is only padded to a multiple of 8): the denoise is 0.45..0.55 and
the CFG goes up from twin to twin, so the SDXL artifacts grow: empty black eyes, an extra eye, an extra arm, blood.
The twins are the same size as kuni_sprite_empty, so a one-frame flicker (kn::VnArgs::flicker) does not shift her.

    python3 -I tools/art/twin.py [--endpoint http://localhost:7860/] [--out DIR]
"""
import argparse, base64, json, subprocess, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data/img/edge/kuni_sprite_empty.webp"
TWINS = [  # prompt, cfg, denoise, seed
    ("1girl solo, creepy, unsettling, dead empty eyes, wrong anatomy", 12, 0.45, 11),
    ("1girl solo, creepy, horror, empty black eyes, extra eye, distorted face, uncanny, glitch", 18, 0.50, 22),
    ("1girl solo, creepy, horror, (extra eyes:1.4), (extra arm:1.3), blood, melting, screaming, uncanny valley, deformed", 26, 0.55, 33),
    ("1girl solo, creepy, (hollow black eye sockets:1.3), (long neck:1.2), stretched smile, unsettling, uncanny", 14, 0.50, 44),
    ("1girl solo, horror, (mouth too wide:1.4), (sharp teeth:1.3), empty eyes, cracked porcelain face", 20, 0.50, 55),
    ("1girl solo, horror, (no eyes:1.4), tears of black ink, melting face, drooling, glitch art", 22, 0.55, 66),
    ("1girl solo, horror, (extra head:1.3), (extra eyes:1.3), (multiple arms:1.4), deformed, twisted, bloody", 28, 0.60, 77),
    ("1girl solo, creepy, (faceless:1.3), (scribbled out face:1.4), static noise, corrupted, red eyes", 16, 0.55, 88),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://localhost:7860/")
    ap.add_argument("--out", default=str(ROOT / "data/img/edge"))
    ap.add_argument("--from", dest="first", type=int, default=1, help="make only the twins from this number on")
    a = ap.parse_args()
    w, h = map(int, subprocess.run(["magick", "identify", "-format", "%w %h", str(SRC)], capture_output=True, text=True,
                                   check=True).stdout.split())
    pw, ph = (w + 7) // 8 * 8, (h + 7) // 8 * 8   # padded canvas, no resize
    with tempfile.TemporaryDirectory() as tmp:
        init = Path(tmp) / "init.png"
        subprocess.run(["magick", str(SRC), "-background", "white", "-alpha", "remove", "-alpha", "off", "-gravity", "center",
                        "-extent", f"{pw}x{ph}", str(init)], check=True)
        for i, (prompt, cfg, denoise, seed) in enumerate(TWINS, 1):
            if i < a.first:
                continue
            body = {"init_images": [base64.b64encode(init.read_bytes()).decode()], "prompt": prompt,
                    "negative_prompt": "(text:2), (signature:2)", "denoising_strength": denoise, "cfg_scale": cfg, "steps": 30,
                    "width": pw, "height": ph, "seed": seed, "resize_mode": 0}
            req = urllib.request.Request(a.endpoint.rstrip("/") + "/sdapi/v1/img2img", json.dumps(body).encode(),
                                         {"Content-Type": "application/json"})
            png = Path(tmp) / f"t{i}.png"
            png.write_bytes(base64.b64decode(json.load(urllib.request.urlopen(req, timeout=600))["images"][0]))
            # back to the sprite's size, white -> alpha (flood fill from the corners)
            cmd = ["magick", str(png), "-gravity", "center", "-crop", f"{w}x{h}+0+0", "+repage", "-alpha", "set", "-fuzz", "12%",
                   "-fill", "none"]
            for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
                cmd += ["-draw", f"color {x},{y} floodfill"]
            cmd += ["-channel", "A", "-morphology", "Erode", "Disk:1", "-blur", "0x0.7", "+channel",
                    "-define", "webp:alpha-quality=100", "-quality", "92", str(Path(a.out) / f"kuni_twin_{i}.webp")]
            subprocess.run(cmd, check=True)
            print(f"kuni_twin_{i}.webp  cfg {cfg}  denoise {denoise}  seed {seed}")


if __name__ == "__main__":
    main()
