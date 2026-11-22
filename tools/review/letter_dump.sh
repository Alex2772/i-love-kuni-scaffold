#!/usr/bin/env bash
# Pages for the letterer (the lettering-only reviewer, .claude/skills/reader-review/letterer_prompt.md): every page of the
# given sandboxes in Russian and English side by side, one layout for both (data/lang/en.txt).
# usage: tools/review/letter_dump.sh <run> <sandbox[:choices]>...   e.g. letter_dump.sh lp1 prologue ch1
# Result: out/review/<run>/letter/001.jpg ..., out/review/<run>/letter_index.txt (page -> panels file:line and texts, for
# us only: the letterer gets the pictures), out/review/<run>/prompt_letterer_<k>.txt (prompts of KN_LETTER_CHUNK=18 pages each; their paths printed).
set -euo pipefail
cd "$(dirname "$0")/../.."
run=${1:?run name}; shift
bin=${KN_BIN:-build/bin/i_love_kuni}
out=out/review/$run
source tools/review/headless.sh
rm -rf "$out/letter" "$out"/lraw_*; mkdir -p "$out/letter"
for spec in "$@"; do
  sandbox=${spec%%:*}; choices=""; [[ $spec == *:* ]] && choices=${spec#*:}
  for lang in ru en; do
    raw=$out/lraw_${lang}_$sandbox
    args=(--dump "$raw" --sandbox "$sandbox" --lang "$lang"); [ -n "$choices" ] && args+=(--choices "$choices")
    env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy "$bin" "${args[@]}" 2>&1 | grep -E "\[ERROR\]|no such" || true
  done
done
python3 -I - "$out" "$@" <<'PY'
import glob, json, sys
from PIL import Image, ImageDraw
out, specs = sys.argv[1], sys.argv[2:]
n, index = 0, []
for spec in specs:
    sb = spec.split(":")[0]
    ru = sorted(glob.glob(f"{out}/lraw_ru_{sb}/*.png")); en = sorted(glob.glob(f"{out}/lraw_en_{sb}/*.png"))
    for r, e in zip(ru, en):
        j = json.load(open(r[:-4] + ".json"))
        if not j.get("bubbles"): continue   # chapter cards and pictures without text: nothing to letter
        n += 1
        a, b = Image.open(r).convert("RGB"), Image.open(e).convert("RGB")
        w, h = a.size
        page = Image.new("RGB", (w * 2 + 16, h + 26), "white")
        page.paste(a, (0, 26)); page.paste(b, (w + 16, 26))
        d = ImageDraw.Draw(page); d.text((6, 6), f"стр {n}   RU", fill="black"); d.text((w + 22, 6), "EN", fill="black")
        page.save(f"{out}/letter/{n:03d}.jpg", quality=86)
        panels = ", ".join(p.replace("story/src/story/", "") for p in j["panels"])
        index.append(f"стр {n}: {panels}\n" + "\n".join(f"   [{x['speaker'] or '-'}] {x['text']}" for x in j["bubbles"]))
open(f"{out}/letter_index.txt", "w").write("\n".join(index) + "\n")
print(n, "pages")
PY
# a letterer reads at most CHUNK pages (two-page-wide pictures fill its context fast): one prompt per chunk
chunk=${KN_LETTER_CHUNK:-18}
pages=("$PWD/$out"/letter/*.jpg)
for ((i = 0, k = 1; i < ${#pages[@]}; i += chunk, k++)); do
  f=$out/prompt_letterer_$k.txt
  { cat .claude/skills/reader-review/letterer_prompt.md
    echo; echo "## Страницы по порядку"
    printf '%s\n' "${pages[@]:i:chunk}"; } > "$f"
  echo "$PWD/$f"
done
