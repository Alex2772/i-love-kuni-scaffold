---
name: openrouter-image
description: Generate an image from a text prompt via OpenRouter (default model google/gemini-3.1-flash-image) and view the result. Use when the user asks to generate/draw/create an image or picture ("сгенерь изображение", "нарисуй", "generate an image"), optionally with a model, aspect ratio or resolution.
---

# OpenRouter image generation

Uses `OPENROUTER_API_KEY` (from the environment, falling back to `export OPENROUTER_API_KEY=` in `~/.zshrc`). Never print the key.

## Usage

```
python3 -I .claude/skills/openrouter-image/generate.py "<prompt>" [--model M] [--aspect 16:9] [--size 2K] [--out PATH] [--image IN.png ...]

`--image` (repeatable) sends input image(s) for editing / reference.
```

Defaults: model `google/gemini-3.1-flash-image`, aspect `16:9`, size `2K`, out `/tmp/orimg/out-<timestamp>.png`.
The script prints the saved path (or the API error). Takes ~30-60 s.

## Steps

1. Take the prompt from the user (pass verbatim; translate only if asked). Map any JSON they paste (`model`, `prompt`, `resolution`, `aspect_ratio`) to the flags above.
2. Run the script (Bash timeout ~180000 ms).
3. Read the resulting PNG with the Read tool so the user (and you) can see it, then briefly describe how well it matches the prompt (e.g. text rendered correctly, unwanted extra text).
4. Offer to regenerate with a tweaked prompt if something is off.

## Notes

- API: `POST https://openrouter.ai/api/v1/chat/completions` with `modalities: ["image","text"]` and `image_config: {aspect_ratio, image_size}`; the image comes back as a base64 data URL in `choices[0].message.images[0].image_url.url`.
- Models that output images are listed at https://openrouter.ai/models?output_modalities=image.
