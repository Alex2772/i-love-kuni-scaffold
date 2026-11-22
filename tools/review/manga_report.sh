#!/usr/bin/env bash
# Manga visual-language metrics by part of the story vs the hand-polished baseline (prologue + ch1 + ch2).
# usage: tools/review/manga_report.sh  -> out/review/manga_language.md
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p out/review
ninja -C build Tests >/dev/null
env -u HTTP_PROXY -u HTTPS_PROXY KN_MANGA_REPORT="$PWD/out/review/manga_language.md" build/bin/Tests --gtest_filter='Story.MangaLanguageReport' >/dev/null
cat out/review/manga_language.md
