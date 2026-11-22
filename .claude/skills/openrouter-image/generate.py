import argparse, base64, json, os, re, sys, time, urllib.request, urllib.error

p = argparse.ArgumentParser()
p.add_argument("prompt")
p.add_argument("--model", default="google/gemini-3.1-flash-image")
p.add_argument("--aspect", default="16:9")
p.add_argument("--size", default="2K")
p.add_argument("--out")
p.add_argument("--image", action="append", default=[], help="input image(s) for editing/reference")
a = p.parse_args()

key = os.environ.get("OPENROUTER_API_KEY")
if not key:
    try:
        m = re.search(r'^export OPENROUTER_API_KEY=["\']?([^"\'\s]+)', open(os.path.expanduser("~/.zshrc")).read(), re.M)
        key = m and m.group(1)
    except OSError:
        pass
if not key:
    sys.exit("OPENROUTER_API_KEY not found")

out = a.out or f"/tmp/orimg/out-{int(time.time())}.png"
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

import mimetypes
content = [{"type": "text", "text": a.prompt}]
for img in a.image:
    mt = mimetypes.guess_type(img)[0] or "image/png"
    content.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64," + base64.b64encode(open(img, "rb").read()).decode()}})
if not a.image:
    content = a.prompt

body = {
    "model": a.model,
    "modalities": ["image", "text"],
    "messages": [{"role": "user", "content": content}],
    "image_config": {"aspect_ratio": a.aspect, "image_size": a.size},
}
def post(path, payload):
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/" + path,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=290))
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_err": e.read().decode()[:500]}

r = post("chat/completions", body)
if r.get("_http") == 404 and "/api/v1/images" in r.get("_err", ""):
    # image-only models (flux, gpt-image, ...) use the images endpoint
    ib = {"model": a.model, "prompt": a.prompt, "aspect_ratio": a.aspect}
    if a.image:
        ib["input_references"] = [c for c in content if c["type"] == "image_url"]
    r = post("images", ib)
if "_http" in r:
    sys.exit(f"HTTP {r['_http']}: {r['_err']}")

def find_img(o):
    if isinstance(o, dict):
        for k in ("b64_json", "url"):
            v = o.get(k)
            if isinstance(v, str) and (k == "b64_json" or v.startswith(("data:", "http"))):
                return k, v
        for v in o.values():
            f = find_img(v)
            if f: return f
    elif isinstance(o, list):
        for v in o:
            f = find_img(v)
            if f: return f

f = find_img(r.get("data") or r.get("choices") or r)
if not f:
    sys.exit("No image in response: " + json.dumps(r)[:500])
k, v = f
if k == "b64_json":
    data = base64.b64decode(v)
elif v.startswith("data:"):
    data = base64.b64decode(v.split(",", 1)[1])
else:
    data = urllib.request.urlopen(v, timeout=120).read()
open(out, "wb").write(data)
print(out)
