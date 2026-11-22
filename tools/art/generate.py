#!/usr/bin/env python3
"""Generate story art from docs/art/*.md (format: docs/art/README.md).

An id is `<doc>/<name>`: `### room` in docs/art/prologue.md is `prologue/room` (KN_IMAGE(prologue, room)); `edit` and
`refs` may name an image of the same doc by its short name. Images used by the game (KN_IMAGE ids from
`i_love_kuni --dump-images`) go to data/img/<id>.webp, helper images (bases for edits) to art/base/<id>.webp. Every image gets a json with the spec it was made from, so an
image is regenerated only when its description changed: art/spec/<id>.json for game images (data/ ships with the game,
the prompts stay out of it), art/base/<id>.json for bases. The layout hints the engine reads (avoid boxes, censor boxes,
character head points, screens), and nothing else, are written into data/img/<id>.json on every run, without
regenerating anything.

    python3 -I tools/art/generate.py                  # everything missing or stale
    python3 -I tools/art/generate.py prologue/room    # these ids (regenerated even if up to date)
    python3 -I tools/art/generate.py --list           # status only
    python3 -I tools/art/generate.py --adopt prologue/city  # accept the existing file as matching its description
    python3 -I tools/art/generate.py --review ch1/sofa_sleep  # self-review sheet: the lines over the image + checklist
    # `- frozen: <why>` in a spec: a hand-made file, never regenerated (batch run skips it, by id refuses); `--adopt` it after a hand edit
    python3 -I tools/art/generate.py --lint           # text vs `- shows:` and banned prompt phrases (README `- ban:`)
"""
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "art"
GAME_DIR = ROOT / "data" / "img"
BASE_DIR = ROOT / "art" / "base"
EXTRAS_DIR = ROOT / "extras" / "img"   # originals of the censored pictures (tools/art/split_extras.py)
SPEC_DIR = ROOT / "art" / "spec"   # specs (prompts) of the game images: kept out of data/, which ships
SDXL = Path.home() / ".claude" / "skills" / "sdxl" / "generate.py"
OPENROUTER = next((p for p in (ROOT / ".claude" / "skills" / "openrouter-image" / "generate.py",
                   Path.home() / ".claude" / "skills" / "openrouter-image" / "generate.py") if p.exists()),
                  ROOT / ".claude" / "skills" / "openrouter-image" / "generate.py")
SDXL_NEGATIVE = "(text:2), (signature:2), raw photo"   # the default of the sdxl skill; `- negative:` adds to it
# `gen: closeup`: what gemini is told before the picture's own prompt (what is in the piece)
CLOSEUP = ("The first image is a small piece of a larger picture of the same anime manga, scaled up, so it is blurry and "
           "pixelated. Redraw it as a sharp, clean, detailed close-up at full resolution: exactly the same framing and "
           "composition, the same characters in the same poses with the same expressions, the same clothes, colours, "
           "lighting and art style (soft painterly anime, clean line work). Only add the fine detail a real close-up "
           "drawing has: crisp eyes, hair strands, fabric folds, clean edges. Do not add, remove or move anything; what "
           "the edge of the image cuts stays cut there. No text, no letters, no speech bubbles, no frames.")
CLOSEUP_REFS = (" The other images are references of the characters: their faces, hair colours and clothes must match "
                "them exactly (do not change the framing for them).")
LOCAL_ENV = dict(os.environ, no_proxy="localhost,127.0.0.1", NO_PROXY="localhost,127.0.0.1")


# ------------------------------------------------------------------------------------------------------ parsing

def parse_docs():
    """{id: spec}. spec: gen ('sdxl'|'edit'), cutout, width, height, seed, source, prompt, avoid, anchors, doc."""
    images = {}
    for md in sorted(DOCS.glob("*.md")):
        if md.name == "README.md":
            continue
        defines, cur = {}, None
        for n, line in enumerate(md.read_text().splitlines(), 1):
            where = f"{md.relative_to(ROOT)}:{n}"
            if m := re.match(r"^- define (\w+):\s*(.+)$", line):
                defines[m.group(1)] = m.group(2).strip()
            elif m := re.match(r"^### `?(\w+)`?\s*$", line):
                img_id = f"{md.stem}/{m.group(1)}"
                if img_id in images:
                    sys.exit(f"{where}: duplicate image {img_id}")
                cur = images[img_id] = {"id": img_id, "doc": where, "avoid": [], "censor": [], "anchors": {}, "defines": defines}
            elif line.startswith("#"):
                cur = None
            elif cur is not None and (m := re.match(r"^- (\w+):\s*(.*)$", line)):
                key, val = m.group(1), m.group(2).strip()
                if key == "gen":
                    parse_gen(cur, val, where)
                    if cur.get("source"):
                        cur["source"] = qualify(cur["source"], md)
                elif key == "prompt":
                    cur["prompt"] = val
                elif key == "negative":
                    cur["negative"] = val
                elif key == "refs":
                    cur["refs"] = [qualify(r, md) for r in val.split()]
                elif key == "frozen":
                    # a hand-picked/hand-drawn file (a copy of a repo reference): never remade from the prompt, not in spec
                    cur["frozen"] = val
                elif key in ("avoid", "censor"):
                    # censor: nudity, painted black by the engine with «Цензурировать наготу»; layout, not spec
                    for box in filter(None, (b.strip() for b in val.split(";"))):
                        nums = [float(x) for x in box.split()]
                        if len(nums) != 4:
                            sys.exit(f"{where}: {key} box needs x y w h, got {box!r}")
                        cur[key].append(nums)
                elif key == "shows":
                    # what the panel text claims and the picture must show; checked by eye (`--review`), linted
                    # against the story text (`--lint`); not part of the spec, so it never makes an image stale
                    cur["shows"] = [x.strip().lower() for x in val.split(",") if x.strip()]
                elif key == "time":
                    # time of day of the picture (morning|day|evening|night, none = no light cue), read by ArtContinuityTest; not in spec
                    if val not in ("morning", "day", "evening", "night", "none"):
                        sys.exit(f"{where}: time is morning|day|evening|night|none")
                    cur["time"] = val
                elif key == "world":
                    # house (Kuni's world) | irl, read by ArtContinuityTest: one page never mixes them; not in spec
                    if val not in ("house", "irl"):
                        sys.exit(f"{where}: world is house|irl")
                    cur["world"] = val
                elif key == "outfit":
                    # `outfit: hidden` = Kuni's clothes are not in the picture: no `_conf` twin (her own look) needed
                    if val != "hidden":
                        sys.exit(f"{where}: outfit is hidden")
                    cur["outfit"] = val
                elif key == "hair":
                    # `hair: hidden` = Kuni's hair ends are not in the picture, so no PINK_HAIR twin is needed
                    # (ArtContinuityTest.PinkHairTwins); not in spec
                    if val != "hidden":
                        sys.exit(f"{where}: hair is hidden")
                    cur["hair"] = val
                elif key == "bell":
                    # `bell: none` = Kuni's choker in the picture has no bell; a line that rings it may not be shown
                    # over it (story/tests/EdgeTest.cpp TheBellRingsOnlyOverAPictureWithTheBell); not in spec
                    if val != "none":
                        sys.exit(f"{where}: bell is none")
                    cur["bell"] = val
                elif key in ("has", "needs"):
                    # continuity facts read by story/tests/ArtContinuityTest.cpp, never part of the spec:
                    # `has: cat` = a cat is drawn in it; `needs: deck` = shows what is introduced by ch?/deck
                    cur[key] = val.split()
                elif key == "purpose":
                    # why the reader needs this panel (docs/STORY_API.md «Панель с объектом внимания»); not in spec
                    cur["purpose"] = val
                elif key == "screen":
                    nums = [float(x) for x in val.split()]
                    if len(nums) not in (4, 5):
                        sys.exit(f"{where}: screen needs x y w h [angle]")
                    cur["screen"] = nums
                else:
                    nums = val.split()
                    if len(nums) != 2:
                        sys.exit(f"{where}: unknown key {key!r} (an anchor needs `x y`)")
                    cur["anchors"][key] = [float(x) for x in nums]
    for img in images.values():
        if "gen" not in img or "prompt" not in img:
            sys.exit(f"{img['doc']}: {img['id']} needs `gen` and `prompt`")
        defs = img.pop("defines")
        img["prompt"] = re.sub(r"\{(\w+)\}", lambda m: defs.get(m.group(1), m.group(0)), img["prompt"])
        if re.search(r"\{\w+\}", img["prompt"]):
            sys.exit(f"{img['doc']}: undefined placeholder in prompt of {img['id']}")
        if img["gen"] in ("edit", "closeup") and img["source"] not in images:
            sys.exit(f"{img['doc']}: {img['id']} edits unknown image {img['source']}")
        img.setdefault("refs", [])
        if img["gen"] in ("sdxl", "text") and img["refs"]:
            sys.exit(f"{img['doc']}: {img['id']}: `refs` work with `edit` and `ref` only")
        if img["gen"] == "ref" and not img["refs"]:
            sys.exit(f"{img['doc']}: {img['id']}: `gen: ref` needs `- refs: <id> ...`")
        for ref in img["refs"]:
            if is_file_ref(ref):
                if not (ROOT / ref).is_file():
                    sys.exit(f"{img['doc']}: {img['id']} refers to missing file {ref}")
            elif ref not in images:
                sys.exit(f"{img['doc']}: {img['id']} refers to unknown image {ref}")
    return images


def is_file_ref(name):
    """A reference that is a file of the repo (character or location reference), not an image id:
    `docs/characters/kuni/kuni-maid.png`, `docs/locations/mansion/hall.webp`."""
    return Path(name).suffix.lower() in (".png", ".webp", ".jpg", ".jpeg")


def qualify(name, md):
    """`room` in prologue.md -> `prologue/room`; a full id (`prologue/room`) names an image of another doc;
    a path with an image extension (`docs/characters/kuni/kuni-maid.png`) is a file relative to the repo root."""
    return name if "/" in name or is_file_ref(name) else f"{md.stem}/{name}"


def parse_gen(cur, val, where):
    if m := re.match(r"^sdxl( cutout)?,\s*(\d+)x(\d+),\s*seed\s+(\d+)$", val):
        cur.update(gen="sdxl", cutout=bool(m.group(1)), width=int(m.group(2)), height=int(m.group(3)),
                   seed=int(m.group(4)))
    elif m := re.match(r"^edit\s+([\w/]+)( cutout)?$", val):
        cur.update(gen="edit", source=m.group(1), cutout=bool(m.group(2)))
    elif m := re.match(r"^closeup\s+([\w/]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)( censored)?$", val):
        # a close-up of a piece of another picture (story/tests/ArtDensityTest.cpp): the piece x y w h (fractions of
        # the source) is cut out, scaled up to 1K and redrawn by gemini at full detail, instead of a panel zoomed into
        # the same pixels
        crop = [float(m.group(k)) for k in range(2, 6)]
        if crop[0] < 0 or crop[1] < 0 or crop[2] <= 0 or crop[3] <= 0 or crop[0] + crop[2] > 1.0001 or crop[1] + crop[3] > 1.0001:
            sys.exit(f"{where}: closeup piece {crop} is not inside the picture")
        # `censored`: cut from the black-boxed copy in data/, not the extras/ original (gemini refuses nudity); the prompt
        # says what to draw over the boxes (README «Bikini base, author retouches»)
        cur.update(gen="closeup", source=m.group(1), crop=crop, cutout=False, censored=bool(m.group(6)))
    elif m := re.match(r"^ref( cutout)?,\s*(\d+)x(\d+)$", val):
        cur.update(gen="ref", cutout=bool(m.group(1)), width=int(m.group(2)), height=int(m.group(3)))
    elif m := re.match(r"^text,\s*(\d+)x(\d+)$", val):
        # gemini from the prompt alone, no picture to follow: the textures of a minigame (docs/art/race.md), not panels
        cur.update(gen="text", cutout=False, width=int(m.group(1)), height=int(m.group(2)))
    else:
        sys.exit(f"{where}: bad gen {val!r} (want `sdxl[ cutout], WxH, seed N`, `edit <id>[ cutout]` "
                 f"`closeup <id> x y w h`, `ref[ cutout], WxH` or `text, WxH`)")


def spec_of(img, images):
    s = {k: img.get(k) for k in ("gen", "cutout", "width", "height", "seed", "source", "prompt")}
    if img.get("crop"):
        s["crop"] = img["crop"]
    if img.get("censored"):
        s["censored"] = True
    if img.get("negative"):   # only when set: images without it keep their spec (not stale)
        s["negative"] = img["negative"]
    if img["gen"] in ("edit", "closeup"):   # an edit is stale when its source changed
        s["source_spec"] = spec_of(images[img["source"]], images)
    if img.get("refs"):
        # only the ids: a changed reference does not regenerate this image by itself (gemini can't repeat a picture
        # that was picked by hand), `--list` warns about it instead
        s["refs"] = img["refs"]
    return s


# ------------------------------------------------------------------------------------------------------ files

def game_ids(binary):
    out = subprocess.run([str(binary), "--dump-images"], capture_output=True, text=True, check=True).stdout
    # the engine logs to stdout too: the id list is the line that is a JSON array
    line = next(l for l in reversed(out.splitlines()) if l.startswith('["'))
    return set(json.loads(line))


def path_of(img_id, used):
    if is_file_ref(img_id):
        return ROOT / img_id
    return (GAME_DIR if img_id in used else BASE_DIR) / f"{img_id}.webp"


def original_of(img_id, used):
    """The picture as drawn: the extras/ original of a censored one (tools/art/split_extras.py), else path_of."""
    path = path_of(img_id, used)
    if path.is_relative_to(GAME_DIR) and (extra := EXTRAS_DIR / path.relative_to(GAME_DIR)).exists():
        return extra
    return path


def closeup_size(img, images, used):
    """1K on the long side (README «Максимум 1K»), the aspect of the piece."""
    w, h = image_size(original_of(img["source"], used))
    cw, ch = img["crop"][2] * w, img["crop"][3] * h
    k = 1216 / max(cw, ch)
    return max(8, round(cw * k / 8) * 8), max(8, round(ch * k / 8) * 8)


def spec_file(path):
    """Where the spec an image was made from is kept: art/spec/<id>.json for game images (data/ ships with the game,
    the prompts do not), next to the image for bases in art/base."""
    if path.is_relative_to(GAME_DIR):
        return SPEC_DIR / path.relative_to(GAME_DIR).with_suffix(".json")
    return path.with_suffix(".json")


def read_json(file):
    try:
        return json.loads(file.read_text())
    except (OSError, ValueError):
        return {}


def write_json(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    # one line: AUI's AJson misreads a number followed by a newline (0.24\n] -> 2.4e10)
    file.write_text(json.dumps(data, ensure_ascii=False) + "\n")


def read_meta(path):
    return read_json(spec_file(path))


def write_meta(path, meta):
    write_json(spec_file(path), meta)


def status(img, images, used):
    path = path_of(img["id"], used)
    if not path.exists():
        return "missing"
    return "ok" if read_meta(path).get("spec") == spec_of(img, images) else "STALE"


def changed_refs(img, used):
    """References that were remade after this image."""
    path = path_of(img["id"], used)
    if not path.exists():
        return []
    return [r for r in img["refs"] if path_of(r, used).exists() and path_of(r, used).stat().st_mtime > path.stat().st_mtime]


def to_webp(src, dst, cutout, size=None):
    cmd = ["magick", str(src)]
    if size:   # edits come back in the model's own resolution: cover-fit to the source size
        cmd += ["-resize", f"{size[0]}x{size[1]}^", "-gravity", "center", "-extent", f"{size[0]}x{size[1]}"]
    if cutout:
        # white background -> alpha: flood fill from all four corners, soften the edge a bit
        cmd += ["-alpha", "set", "-fuzz", "12%", "-fill", "none"]
        for x, y in (("0", "0"), ("%[fx:w-1]", "0"), ("0", "%[fx:h-1]"), ("%[fx:w-1]", "%[fx:h-1]")):
            cmd += ["-draw", f"color {x},{y} floodfill"]
        cmd += ["-channel", "A", "-morphology", "Erode", "Disk:1", "-blur", "0x0.7", "+channel", "-trim", "+repage",
                "-define", "webp:alpha-quality=100", "-quality", "92"]
    else:
        cmd += ["-quality", "88"]
    subprocess.run(cmd + [str(dst)], check=True)


def image_size(path):
    out = subprocess.run(["magick", "identify", "-format", "%w %h", str(path)], capture_output=True, text=True,
                         check=True).stdout
    w, h = out.split()
    return int(w), int(h)


def aspect_for(w, h):
    ratios = {"1:1": 1, "3:2": 1.5, "2:3": 2 / 3, "16:9": 16 / 9, "9:16": 9 / 16, "4:3": 4 / 3, "3:4": 0.75, "4:5": 0.8, "5:4": 1.25}
    return min(ratios, key=lambda k: abs(ratios[k] - w / h))


def generate(img, images, used):
    if img.get("frozen"):
        sys.exit(f"{img['id']} is frozen ({img['frozen']}): it is a hand-made file, do not regenerate; "
                 f"edit it by hand or through a new `edit` image")
    dst = path_of(img["id"], used)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if img["gen"] == "sdxl":
            cmd = [sys.executable, "-I", str(SDXL), img["prompt"], "--width", str(img["width"]), "--height",
                   str(img["height"]), "--seed", str(img["seed"]), "--out", tmp]
            if img.get("negative"):
                cmd += ["--negative", SDXL_NEGATIVE + ", " + img["negative"]]
            # one SDXL job at a time: several agents may run this script in parallel on one GPU
            with open("/tmp/kn-sdxl.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                res = subprocess.run(cmd, capture_output=True, text=True, env=LOCAL_ENV)
            m = re.search(r"^(\S+\.png) seed=", res.stdout, re.M)
            if res.returncode != 0 or not m:
                raise RuntimeError(f"sdxl failed for {img['id']}:\n{res.stderr or res.stdout}")
            to_webp(m.group(1), dst, img["cutout"])
        else:
            # gemini via OpenRouter: the image to edit (if any) goes first, then the references
            inputs = ([img["source"]] if img["gen"] in ("edit", "closeup") else []) + img["refs"]
            pngs = []
            for k, ref in enumerate(inputs):
                src = path_of(ref, used)
                # only a missing input is made; a stale one is used as is: remaking it silently replaces art that
                # is on other pages and cannot be got back (data/img is not in git). Regenerate it by id if needed
                if is_file_ref(ref):
                    pass   # a reference file from docs/characters or docs/locations, used as is
                elif not src.exists():
                    generate(images[ref], images, used)
                elif status(images[ref], images, used) != "ok":
                    print(f"    warning: {ref} is stale, used as is (regenerate it by id if it must change)",
                          file=sys.stderr, flush=True)
                png = Path(tmp) / f"in{k}.png"
                if k == 0 and img["gen"] == "closeup":
                    # the piece, scaled up to the size of the close-up: gemini redraws it sharp
                    x, y, cw, ch = img["crop"]
                    piece = path_of(ref, used) if img.get("censored") else original_of(ref, used)
                    sw, sh = image_size(piece)
                    cw_, ch_ = closeup_size(img, images, used)
                    subprocess.run(["magick", str(piece), "-background", "white", "-flatten", "-crop",
                                    f"{round(cw * sw)}x{round(ch * sh)}+{round(x * sw)}+{round(y * sh)}", "+repage",
                                    "-filter", "Lanczos", "-resize", f"{cw_}x{ch_}!", str(png)], check=True)
                    pngs.append(png)
                    continue
                subprocess.run(["magick", str(original_of(ref, used)), "-background", "white", "-flatten", str(png)], check=True)
                pngs.append(png)
            w, h = image_size(pngs[0]) if img["gen"] in ("edit", "closeup") else (img["width"], img["height"])
            out = Path(tmp) / "out.png"
            prompt = img["prompt"]
            if img["gen"] == "closeup":
                prompt = CLOSEUP + (CLOSEUP_REFS if img["refs"] else "") + " In this piece: " + prompt
            cmd = [sys.executable, "-I", str(OPENROUTER), prompt, "--aspect", aspect_for(w, h), "--size", "1K",
                   "--out", str(out)]
            for png in pngs:
                cmd += ["--image", str(png)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0 or not out.exists():
                raise RuntimeError(f"openrouter failed for {img['id']}:\n{res.stderr or res.stdout}")
            to_webp(out, dst, img["cutout"], size=(w, h))
    write_meta(dst, {"spec": spec_of(img, images)})
    print(f"    -> {dst.relative_to(ROOT)}", flush=True)


def layout_of(img):
    """Only what the engine reads: data/img/<id>.json ships with the game."""
    layout = {"avoid": img["avoid"], "anchors": img["anchors"]}
    if img["censor"]:
        layout["censor"] = img["censor"]
    if "screen" in img:
        layout["screen"] = img["screen"]
    return layout


def write_layout(img, used):
    """Layout hints for the engine, refreshed without regenerating the image."""
    path = path_of(img["id"], used)
    if img["id"] not in used or not path.exists():
        return
    write_json(path.with_suffix(".json"), layout_of(img))


# ------------------------------------------------------------------------------------------------------ review / lint

STORY = ROOT / "story" / "src"
README = DOCS / "README.md"
# Words in the panel text that are a claim about the picture: a state of the face or body, a held or named prop,
# clothes. A stem found in a line over an image must be covered by that image's `- shows:` (someone looked and
# checked). Stems, so «рот»/«ртом», «вилка»/«вилкой» match. Add a stem whenever the author catches a new kind of miss.
CLAIMS = {   # label: regex over the lowercased line (and over `- shows:` items, to tell what is covered)
    "рот": r"\bрот|\bрт[аеоу]|\bгуб", "глаза": r"\bглаз", "улыбка": r"улыб", "слёзы": r"сл[её]з|плач",
    "румянец": r"красне|румян", "поза": r"\bсидя\b|\bстоя\b|\bл[её]жа\b|\bсид[ия]т|\bлеж[ия]т",
    "сон": r"\bспит|\bспя|засыпа|уснул", "вилка/ложка/нож": r"\bвилк|\bложк|\bнож",
    "посуда": r"кружк|чашк|тарел|контейнер", "пакет": r"\bпакет", "ноутбук": r"ноутбук", "телефон": r"телефон",
    "плед": r"\bплед|одеял", "одежда": r"рукав|рубашк|форм[аеуы]\b|фартук|полотенц", "колокольчик": r"колокольч",
    "босиком": r"босик", "мокрый": r"\bмокр", "бумажка/карандаш": r"бумажк|карандаш",
    "часы": r"\bчас(ы|ах|ов)\b|маятник|циферблат", "кот": r"\bкот(\b|а\b|у\b|ом\b)",
    "время суток": r"\bутр|\bноч|\bвечер|рассвет|закат", "свет": r"свеч|камин|фонар",
}
TEXT_RE = re.compile(r'co_await\s+\w+(?:\.\w+)?\(\s*"((?:[^"\\]|\\.)*)"|\.text\s*=\s*"((?:[^"\\]|\\.)*)"')


def story_lines():
    """{image id: [(where, text, ids of the other images on that page)]} by a static read of story/src: a line belongs
    to the last `panel(... .bg = img::doc::name ...)` above it, `page()` starts a new page. Heuristic (branches and
    helper scenes are not followed), good enough to put the text next to the picture."""
    out = {}
    for cpp in sorted(STORY.rglob("*.cpp")):
        if "debug" in cpp.parts:
            continue   # engine test scenes, not story
        bgs, page = [], []
        lines = cpp.read_text().splitlines()
        for n, line in enumerate(lines, 1):
            if re.search(r"\bpage\(\)", line) or re.match(r"^(Scene|KN_SANDBOX)", line):
                bgs, page = [], []
            if "panel(" in line:
                ids = [f"{a}/{b}" for a, b in re.findall(r"img::(\w+)::(\w+)", " ".join(lines[n - 1:n + 1]))]
                if ids:
                    bgs = ids
                    page += [i for i in ids if i not in page]
            for m in TEXT_RE.finditer(line):
                text = m.group(1) or m.group(2)
                for bg in bgs:
                    out.setdefault(bg, []).append((f"{cpp.relative_to(ROOT)}:{n}", text, page))
    return out


def bans():
    """`- ban: <phrase> → <why / what to write instead>` lines of docs/art/README.md."""
    return [(m.group(1).strip().lower(), m.group(2).strip()) for m in
            re.finditer(r"^- ban: (.+?)\s+→\s+(.+)$", README.read_text(), re.M)]


def claims_of(text):
    return [label for label, rx in CLAIMS.items() if re.search(rx, text.lower())]


def lint(images, only=()):
    """`only`: ids or doc prefixes (`ch1`, `inv1/trash`) to limit the report to."""
    pick = lambda i: not only or any(i == o or i.startswith(o.rstrip("/") + "/") for o in only)
    problems = 0
    for img in images.values():
        if not pick(img["id"]):
            continue
        for phrase, why in bans():
            if phrase in img["prompt"].lower():
                print(f"ban   {img['id']} ({img['doc']}): prompt has «{phrase}» — {why}")
                problems += 1
    for img in images.values():
        # an image drawn as an object of attention (focus lines) must say why the reader needs it
        if pick(img["id"]) and re.search(r"focus lines|speed lines", img["prompt"].lower()) and not img.get("purpose"):
            print(f"purpose {img['id']} ({img['doc']}): focus-line panel needs `- purpose:` (what it shows and why)")
            problems += 1
    for img in images.values():
        # every run rewrites data/img/<id>.json from docs: a hand edit of the json is lost on the next one (inv1/diary_line:
        # the line moved off the notebook onto the desk). Tune `- screen:`/`- avoid:` in docs/art instead
        file = GAME_DIR / f"{img['id']}.json"
        if pick(img["id"]) and file.exists() and read_json(file) != layout_of(img):
            print(f"layout {img['id']}: {file.relative_to(ROOT)} differs from {img['doc']} — the next run overwrites it, "
                  f"move the change into the docs")
            problems += 1
    lines = story_lines()
    for img_id in sorted(lines):
        if img_id not in images or not pick(img_id):
            continue
        shows = images[img_id].get("shows", [])
        for where, text, _ in lines[img_id]:
            missing = [c for c in claims_of(text) if not any(re.search(CLAIMS[c], x) for x in shows)]
            if missing:
                print(f"shows {img_id}: {where} «{text}» names {', '.join(missing)} — look at the picture, "
                      f"then add it to `- shows:` of {images[img_id]['doc']}")
                problems += 1
    print(f"{problems} to check")


REVIEW = """Self-review (docs/art/README.md «Самопроверка»). Open the picture with Read and answer each point in writing:
 1. Each line above, literally: every action, state and prop it names is in the picture AND inside the panel crop
    (mouth open/closed, eyes, tears, blush, sitting/lying, what is held, what lies where).
 2. Props fit the situation: delivery food = disposable plastic fork, takeaway box, paper bag; a manor = old things;
    the same prop looks the same as on the earlier panels that show it.
 3. Wardrobe = character canon (docs/characters/<id>/README.md): sleeve length, cuffs, buttons, accessories, which wrist.
 4. Neighbours on the page (listed above): the same moment has the same light and time of day; two panels side by
    side are two different shots (distance, angle, subject), not one picture twice.
 5. Anatomy (5 fingers), object geometry, no stray text, no second copy of a unique object.
Any «no» = fix via `gen: edit` (OpenRouter) and review again."""


def review(img_id, images):
    img = images[img_id]
    print(f"{img_id}  ({img['doc']}, data/img/{img_id}.webp)\nprompt: {img['prompt']}\n")
    print("shows: " + (", ".join(img.get("shows", [])) or "(none)"))
    seen = set()
    for where, text, page in story_lines().get(img_id, []):
        print(f"  {where}: «{text}»")
        seen.update(p for p in page if p != img_id)
    print("other images on the same page: " + (", ".join(sorted(seen)) or "(none)") + "\n")
    print(REVIEW)


# ------------------------------------------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ids", nargs="*", help="only these image ids")
    p.add_argument("--binary", default=str(ROOT / "build" / "bin" / "i_love_kuni"))
    p.add_argument("--list", action="store_true")
    p.add_argument("--adopt", action="store_true", help="mark existing files of `ids` as up to date")
    p.add_argument("--review", metavar="ID", help="print the self-review sheet of one image")
    p.add_argument("--lint", action="store_true", help="check story text against `- shows:` and README bans")
    a = p.parse_args()

    images = parse_docs()
    if a.review:
        if a.review not in images:
            sys.exit(f"unknown image id: {a.review}")
        return review(a.review, images)
    if a.lint:
        return lint(images, a.ids)
    # without a game binary that lists its KN_IMAGE ids, every described picture counts as a game one (data/img/)
    used = game_ids(Path(a.binary)) if Path(a.binary).exists() else set(images.keys())
    undocumented = sorted(i for i in used - images.keys() if not i.startswith("edge/kuni_twin_"))   # made by tools/art/twin.py
    if undocumented:
        sys.exit("KN_IMAGE without a description in docs/art: " + ", ".join(undocumented))
    sources = {i["source"] for i in images.values() if i["gen"] in ("edit", "closeup")}
    sources |= {r for i in images.values() for r in i["refs"]}
    for orphan in sorted(images.keys() - used - sources):
        print(f"warning: {orphan} is neither used by the game nor a source of an edit", file=sys.stderr)
    for unknown in set(a.ids) - images.keys():
        sys.exit(f"unknown image id: {unknown}")

    if a.list:
        for img_id in sorted(images):
            where = "game" if img_id in used else "base"
            refs = changed_refs(images[img_id], used)
            note = f"   (remade after it: {', '.join(refs)}; regenerate by id if it must match)" if refs else ""
            print(f"{status(images[img_id], images, used):7} {where} {img_id}{note}")
        return
    if a.adopt:
        for img_id in a.ids:
            path = path_of(img_id, used)
            if not path.exists():
                sys.exit(f"{path.relative_to(ROOT)} does not exist")
            write_meta(path, {**read_meta(path), "spec": spec_of(images[img_id], images)})
            print(f"adopted {path.relative_to(ROOT)}")
    else:
        todo = a.ids or [i for i in sorted(images) if status(images[i], images, used) != "ok" and not images[i].get("frozen")]
        for i in sorted(images):
            if not a.ids and images[i].get("frozen") and status(images[i], images, used) != "ok":
                print(f"warning: {i} is frozen but not up to date (`--adopt {i}` after checking the file)", file=sys.stderr)
        for n, img_id in enumerate(todo, 1):
            if not a.ids and status(images[img_id], images, used) == "ok":
                continue   # already made as the source of an earlier edit
            print(f"[{n}/{len(todo)}] {img_id} ({images[img_id]['gen']}) ...", flush=True)
            generate(images[img_id], images, used)
        if not todo:
            print("all images are up to date")
    for img in images.values():
        write_layout(img, used)


if __name__ == "__main__":
    main()
# Kuni was here 😸
