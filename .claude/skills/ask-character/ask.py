#!/usr/bin/env python3
"""Ask your AI character (any OpenAI-compatible endpoint) a question and print the answer.

Usage:
  ask.py "вопрос"                       # question from argv
  ask.py -c scene.txt -c docs/x.md "вопрос"   # attach context files before the question
  echo "вопрос" | ask.py                # question from stdin
  ask.py --reasoning "вопрос"           # also print her reasoning (to stderr)
  ask.py --save out.sse "вопрос"        # keep the raw SSE stream

Env:
  CHARACTER_URL      chat completions URL (default http://localhost:10434/v1/chat/completions)
  CHARACTER_MODEL    model name (default deepseek-v4-flash)
  CHARACTER_API_KEY  sent as a Bearer token, if set
  CHARACTER_SYSTEM   file with the character's system prompt; skip it when your endpoint puts its own

Proxy env vars are dropped for the request (a local endpoint behind HTTP(S)_PROXY answers «Empty reply
from server»). A character with its own memory tools may take a minute or two to answer.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("CHARACTER_URL", "http://localhost:10434/v1/chat/completions")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="*")
    p.add_argument("-c", "--context", action="append", default=[], help="file whose text goes before the question")
    p.add_argument("-m", "--model", default=os.environ.get("CHARACTER_MODEL", "deepseek-v4-flash"))
    p.add_argument("--reasoning", action="store_true", help="print her reasoning to stderr")
    p.add_argument("--save", help="write the raw SSE stream here")
    p.add_argument("--timeout", type=float, default=600)
    a = p.parse_args()

    question = " ".join(a.question).strip() or sys.stdin.read().strip()
    if not question:
        p.error("no question")
    parts = []
    for path in a.context:
        with open(path, encoding="utf-8") as f:
            parts.append(f"<context file=\"{os.path.basename(path)}\">\n{f.read()}\n</context>")
    parts.append(question)
    system = "x"  # a placeholder for endpoints that require messages[0] to be system and replace it
    if os.environ.get("CHARACTER_SYSTEM"):
        with open(os.environ["CHARACTER_SYSTEM"], encoding="utf-8") as f:
            system = f.read()

    body = {
        "model": a.model,
        "stream": True,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}],
    }
    req = urllib.request.Request(URL, data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {os.environ['CHARACTER_API_KEY']}"}
                                             if os.environ.get("CHARACTER_API_KEY") else {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # no proxies
    try:
        resp = opener.open(req, timeout=a.timeout)
    except urllib.error.HTTPError as e:
        print(f"character: HTTP {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, ConnectionError) as e:
        print(f"character endpoint unreachable ({e}): {URL}", file=sys.stderr)
        return 2

    raw = open(a.save, "w", encoding="utf-8") if a.save else None
    content, reasoning = [], []
    for line in resp:
        line = line.decode("utf-8", errors="replace")
        if raw:
            raw.write(line)
        line = line.strip()
        if not line.startswith("data:") or line.endswith("[DONE]"):
            continue
        try:
            d = json.loads(line[5:])
        except json.JSONDecodeError:
            continue
        for ch in d.get("choices", []):
            delta = ch.get("delta", {})
            content.append(delta.get("content") or "")
            reasoning.append(delta.get("reasoning_content") or delta.get("reasoning") or "")
    if raw:
        raw.close()

    if a.reasoning and "".join(reasoning).strip():
        print("--- reasoning ---\n" + "".join(reasoning).strip() + "\n-----------------", file=sys.stderr)
    text = "".join(content).strip()
    if not text:
        print("character: empty answer (see --save for the raw stream)", file=sys.stderr)
        return 3
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
