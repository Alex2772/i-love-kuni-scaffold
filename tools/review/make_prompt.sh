#!/usr/bin/env bash
# usage: tools/review/make_prompt.sh <run> <persona-file> [extra-note-file]  -> writes out/review/<run>/prompt_<persona>.txt, prints its path
set -euo pipefail
cd "$(dirname "$0")/../.."
run=$1; persona=$2; note=${3:-}
out=out/review/$run/prompt_$(basename "$persona" .md).txt
{
cat .claude/skills/reader-review/reader_prompt.md
echo; echo "## Кто ты"; cat "$persona"
[ -n "$note" ] && { echo; cat "$note"; }
echo; echo "## Страницы по порядку (читай каждую Read-ом, в этом порядке, ничего другого не открывай)"
for f in "$PWD"/out/review/$run/pages/*.jpg; do echo "$f"; done
} > "$out"
echo "$PWD/$out"
