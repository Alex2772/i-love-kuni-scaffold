#!/usr/bin/env bash
# Renders sandboxes along fixed routes into one continuous run for a blind reader review.
# usage: tools/review/dump.sh [--keep-shared] <run> <sandbox[:choices]>...   e.g. dump.sh ch1 prologue ch1:0,2,0,0
# The sandboxes are concatenated in the given order (the reader reads from the start of the book).
# Two routes of one story share their opening: the pages of a route that repeat the previous route's opening page by page
# are left out, one marker page «другая ветка, расходится со сцены …» stands in their place (reader wave 2: w2g pp. 50–78 and
# w2f_crisis pp. 27–35 were the same pages twice). The pages are compared by their json (what the reader sees), not by choice
# indices: two sandboxes ask different menus (w3h p46 named the Mei choice, the routes split at Workshop). Later runs of
# ≥ 2 pages the previous route already showed become one «N стр. как в первой ветке» page (w3h pp. 52–73). `--keep-shared` keeps them.
# Every page is PAGE_W×PAGE_H whatever the window got from the compositor (kn::DUMP_PAGE_SIZE, PageDumpTest).
# The binary: $KN_BIN, build/bin/i_love_kuni by default. The language: $KN_LANG (ru|en), the system's by default.
# The window opens in a headless mutter (tools/review/headless.sh), not on the desktop; KN_DUMP_VISIBLE=1 shows it.
# Result: out/review/<run>/pages/001.jpg ... (no code addresses in names), out/review/<run>/routes.json
set -euo pipefail
cd "$(dirname "$0")/../.."
skip_shared=1
[[ ${1:-} == --keep-shared ]] && { skip_shared=0; shift; }
run=${1:?run name}; shift
bin=${KN_BIN:-build/bin/i_love_kuni}
if [ "${KN_DUMP_VISIBLE:-}" != 1 ]; then
  source tools/review/headless.sh || { echo "dump.sh: no headless mutter, KN_DUMP_VISIBLE=1 to dump in a visible window" >&2; exit 1; }
fi
rm -rf "out/review/$run"; mkdir -p "out/review/$run/pages"
echo "[]" > "out/review/$run/routes.json"
prev=""
for spec in "$@"; do
  sandbox=${spec%%:*}; choices=""; [[ $spec == *:* ]] && choices=${spec#*:}
  # one raw dir per route: the same sandbox twice (ch6 ch6:0,0,2) must not overwrite the first route's pages, or the
  # second route is compared with itself and comes out whole with no branch card (w7e2 pp. 37–52)
  raw=out/review/$run/raw_$sandbox; k=1
  while [ -e "$raw" ]; do k=$((k + 1)); raw=out/review/$run/raw_${sandbox}_$k; done
  mkdir -p "$raw"
  args=(--dump "$raw" --sandbox "$sandbox"); [ -n "$choices" ] && args+=(--choices "$choices")
  [ -n "${KN_LANG:-}" ] && args+=(--lang "$KN_LANG")
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy "$bin" "${args[@]}" 2>&1 | grep -E "\[ERROR\]|no such" || true
  # JPEG for the reader: a 2/3-size PNG page is ~350 KB, 60 of them overflow the reader's context ("media removed")
  python3 -I - "$run" "$sandbox" "$raw" "$prev" "$skip_shared" "$spec" <<'PY'
import glob, json, os, sys
from PIL import Image, ImageDraw, ImageFont
run, sb, raw, prev, skip, spec = sys.argv[1:]
out = f"out/review/{run}"
pages = sorted(glob.glob(f"{raw}/*.png"))
route = json.load(open(f"{raw}/route.json"))
# what the reader sees on a page: its json without the file name (the number differs between routes, the content does not)
# and without the choices taken so far (the path to the page, not on it)
def content(png):
    d = json.load(open(png[:-4] + ".json")); d.pop("file", None); d.pop("choices", None)
    return json.dumps(d, ensure_ascii=False, sort_keys=True)
scene = lambda p: os.path.basename(p).split("_")[1].split("-", 1)[-1]   # 0002_ch7-FourCouples_730ef1.png -> FourCouples
def first_line(png):
    texts = [b["text"] for b in json.load(open(png[:-4] + ".json"))["bubbles"] if b["text"].strip()]
    return texts[0] if texts else ""
mine = [content(p) for p in pages]
before = sorted(glob.glob(f"{prev}/*.png")) if prev and skip == "1" else []
theirs = [content(p) for p in before]
seen = set(theirs)
# the opening shared page by page, then the later runs (≥ 2 pages) of pages the previous route already showed
shared = 0
while shared < min(len(mine), len(theirs)) and mine[shared] == theirs[shared]:
    shared += 1
runs = []   # (start, end) of the later runs
i = shared
while i < len(mine):
    j = i
    while j < len(mine) and mine[j] in seen: j += 1
    if j - i >= 2: runs.append((i, j))
    i = max(j, i + 1)
if before and shared + sum(e - s for s, e in runs) == len(mine):
    shared, runs = 0, []   # the same route twice: nothing to tell apart, keep it whole
n = len(glob.glob(f"{out}/pages/*.jpg"))
def put(image):
    global n
    n += 1
    image.convert("RGB").save(f"{out}/pages/{n:03d}.jpg", quality=88)
# the cards in the reader's language: a Russian card in the English dump (reader review w11 c EN)
EN = {"ДРУГАЯ ВЕТКА": "ANOTHER BRANCH", "расходится со сцены": "it parts at the scene", "в первой ветке тут была сцена": "in the first branch this was the scene",
      "стр. до развилки те же, что в начале, их нет": "pages before the fork are the same as before, left out", "стр. как в первой ветке": "pages as in the first branch",
      "сцены": "scenes", "предыдущая ветка на этом кончилась": "the previous branch ended here", "эта снова идёт с главы": "this one starts again at chapter",
      "КОНЦОВКА": "ENDING", "псевдоконцовка: игра вернёт к последнему выбору": "pseudo-ending: the game returns to the last choice",
      "ПЕРЕСКАЗ": "RECAP", "следующая страница есть только в песочнице: она повторяет развилку, сыгранную раньше": "the next page exists only in the sandbox: it replays a fork played earlier",
      "тут было взято": "taken here:", "дальше история идёт без этой ветки": "the story goes on without this branch", "[запретное слово]": "[forbidden word]"}
def tr(t):
    if os.environ.get("KN_LANG") != "en": return t
    for k in sorted(EN, key=len, reverse=True): t = t.replace(k, EN[k])
    return t
def marker(lines):
    lines = [(tr(t), k) for t, k in lines]
    size = Image.open(pages[0]).size
    page = Image.new("RGB", size, (250, 247, 242))
    d = ImageDraw.Draw(page)
    font = lambda k: ImageFont.truetype("data/fonts/Heroika-Regular.otf", int(size[0] * k))
    def wrap(text, f, width):
        rows, cur = [], ""
        for w in text.split(" "):
            nxt = (cur + " " + w).strip()
            if cur and d.textlength(nxt, font=f) > width: rows.append(cur); cur = w
            else: cur = nxt
        return rows + [cur]
    rows = [(r, font(k)) for t, k in lines for r in wrap(t, font(k), size[0] * 0.8)]
    y = size[1] * 0.5 - sum(f.size * 1.4 for _, f in rows) / 2
    for r, f in rows:
        d.text(((size[0] - d.textlength(r, font=f)) / 2, y), r, font=f, fill=(20, 20, 22))
        y += f.size * 1.4
    put(page)
# the card font has no «■»: the censored name reads as a word there
def en_of():
    d, ru = {}, None
    for line in open("data/lang/en.txt", encoding="utf-8"):
        if line.startswith("ru "): ru = line[3:].rstrip("\n")
        elif line.startswith("en ") and ru is not None: d.setdefault(ru, line[3:].rstrip("\n")); ru = None
    return d
LANG_EN = en_of() if os.environ.get("KN_LANG") == "en" else {}
quote = lambda s: (lambda t: "«" + t + "»" if not t.startswith("«") else t)(re.sub("■+", "[запретное слово]", LANG_EN.get(s, s)))
import re
if shared:
    # the marker: the first page this route shows differently from the previous one, named by its scene and its first line
    # no sandbox id on the card: «route_paw» read as technical junk in the book (reader review w12 e, both readers)
    lines = [("ДРУГАЯ ВЕТКА", 0.075)]
    if shared < len(pages):
        lines += [("расходится со сцены", 0.045), (scene(pages[shared]), 0.045)]
        if first_line(pages[shared]): lines += [(quote(first_line(pages[shared])), 0.035)]
        if shared < len(before) and scene(before[shared]) != scene(pages[shared]):
            lines += [("", 0.03), (f"в первой ветке тут была сцена {scene(before[shared])}", 0.035)]
    lines += [("", 0.04), (f"{shared} стр. до развилки те же, что в начале, их нет", 0.035)]
    marker(lines)
# a route that starts again at a chapter the previous route already reached is another branch, not the sequel: a bad end
# (ch6 «Ассистентка») followed by the good route read as two «Глава 9» in a row (reader review w10 e, both readers)
import re
chapter_no = lambda png: next(iter(re.findall(r"(\d+)", json.load(open(png[:-4] + ".json")).get("chapter", "") or "")), None)
if not shared and prev:
    reached = [int(c) for c in map(chapter_no, sorted(glob.glob(f"{prev}/*.png"))) if c]
    mine_no = next((int(c) for c in map(chapter_no, pages) if c), None)
    if reached and mine_no is not None and mine_no <= max(reached):
        marker([("ДРУГАЯ ВЕТКА", 0.075), ("", 0.03),
                ("предыдущая ветка на этом кончилась", 0.04), (f"эта снова идёт с главы {mine_no}", 0.04)])
# a sandbox opens with a «Ранее.» page that replays an earlier menu: it is not in the game, and three b readers of w11
# read it as a flashback of the story (pp. 26, 53). A card before it says so.
recap = lambda p: first_line(p).startswith(("Ранее.", "Previously."))
i = shared
for s, e in runs + [(len(pages), len(pages))]:
    for p in pages[i:s]:
        if recap(p): marker([("ПЕРЕСКАЗ", 0.075), ("", 0.03), ("следующая страница есть только в песочнице: она повторяет развилку, сыгранную раньше", 0.035)])
        put(Image.open(p))
    if e > s:
        names = list(dict.fromkeys(scene(p) for p in pages[s:e] if scene(p) != "chapter"))   # chapter = a title page
        marker([(f"{e - s} стр. как в первой ветке", 0.06), ("", 0.03), ("сцены " + ", ".join(names), 0.035)])
    i = e
# the ending card the game shows (the walk stops on it, no page of its own)
if os.path.exists(f"{raw}/ending.json"):
    e = json.load(open(f"{raw}/ending.json"))
    lines = [("КОНЦОВКА", 0.075), (quote(e["title"]), 0.05)]
    if e.get("pseudo"):
        # name the choice it returns to: «какой выбор? я его не видел» (reader review w11 c, both readers)
        lines += [("", 0.03), ("псевдоконцовка: игра вернёт к последнему выбору", 0.035)]
        if route:
            last = route[-1]
            opts = " / ".join(quote(o) for o in last["options"])
            lines += [(opts, 0.035), (f"тут было взято {quote(last['options'][last['taken']])}", 0.035)]
        lines += [("", 0.03), ("дальше история идёт без этой ветки", 0.035)]
    marker(lines)
f = f"{out}/routes.json"
d = json.load(open(f))
d.append({"sandbox": sb, "choices": route, "sharedOpeningSkipped": shared,
          "sameAsPreviousSkipped": [[s + 1, e] for s, e in runs]})
json.dump(d, open(f, "w"), ensure_ascii=False, indent=1)
if shared or runs:
    print(f"{sb}: {shared} pages of the shared opening and {sum(e - s for s, e in runs)} later pages as in the previous route left out (--keep-shared keeps them)")
PY
  prev=$raw
done
echo "$(ls "out/review/$run/pages" | wc -l) pages -> out/review/$run/pages ; routes: out/review/$run/routes.json ; raw_* (json with file:line) is for us only"
