#!/usr/bin/env bash
# usage: tools/review/pick_personas.sh  -> 2 distinct random personas: one from the core audience, one from the rest (/dev/urandom)
set -euo pipefail
cd "$(dirname "$0")/../.."
d=.claude/skills/reader-review/personas
core=$(ls $d/01-*.md $d/04-*.md $d/06-*.md $d/08-*.md | shuf --random-source=/dev/urandom | head -1)
rest=$(ls $d/*.md | grep -v "/01-\|/04-\|/06-\|/08-" | shuf --random-source=/dev/urandom | head -1)
echo "$core"; echo "$rest"
