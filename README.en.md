# I love Kuni: prompts

[Русский](README.md) · **English**

The prompts, skills and agent instructions used to make the manga novel
[I love Kuni](https://github.com/Alex2772/i-love-kuni). Take them, change them, and build your dream game with your
own characters. The code, prompts and tools are [MIT](LICENSE). Kuni and the examples from the game in `docs/`
are [CC BY-NC-SA 4.0](LICENSE-ASSETS): fan games with her are welcome, non-commercial, credited as "Kuni by Alex2772"
and marked unofficial.

## What's here

| File | What it is |
|---|---|
| [INITIAL_PROMPT.md](INITIAL_PROMPT.md) | the very first prompt of the project, verbatim, and what turned out differently |
| [LESSONS.md](LESSONS.md) | what we learned: working with agents, art, lettering, story, translation |
| [CLAUDE.md](CLAUDE.md) | a template of agent instructions for your own game |
| [.claude/agents/reader.md](.claude/agents/reader.md) | a reader agent with only `Read`: it can't peek into the code |
| [.claude/skills/mangaka](.claude/skills/mangaka) | manga lettering and paneling rules with examples: show don't tell, balloons, pauses, panel shapes (in Russian) |
| [.claude/skills/reader-review](.claude/skills/reader-review) | blind review: readers with random personas, plus a letterer |
| [.claude/skills/openrouter-image](.claude/skills/openrouter-image) | image generation and editing via OpenRouter |
| [.claude/skills/ask-character](.claude/skills/ask-character) | ask your own AI character (any OpenAI-compatible API) |
| [.claude/skills/music](.claude/skills/music) | music and sound effects synthesized from scratch |
| [.claude/skills/aui-remote](.claude/skills/aui-remote) | build, run and click through an AUI app |
| [.claude/skills/cpp-style](.claude/skills/cpp-style) | C++ style |
| [tools/art](tools/art) | the art generator from `docs/art/*.md` descriptions (OpenRouter), close-ups, gesture frames |
| [tools/music](tools/music) | music and sound effects synthesized with numpy, no samples |
| [tools/review](tools/review) | page dumps and prompts for the blind readers (needs the game's engine) |
| [docs/](docs) | the docs layout: story, chapters, characters, places, props, art |
| [docs/characters/kuni](docs/characters/kuni) | Kuni: canon, voice, references — take her into your fan game |
| [docs/locations/kitchen](docs/locations/kitchen), [docs/props/oracle](docs/props/oracle) | an example place and prop with a plan and a reference |
| [docs/art/example.md](docs/art/example.md) | example picture descriptions: Kuni in the kitchen, manpu, the Oracle |

## Getting started

1. Fork the repo (or copy it into an empty folder).
2. Fill in `docs/`: `STORY.md`, your characters, places and props, following Kuni, the kitchen and the Oracle. Want a
   fan game with Kuni? She is already in `docs/characters/kuni/`.
3. Rewrite [INITIAL_PROMPT.md](INITIAL_PROMPT.md) for your game and give it to an agent
   ([Claude Code](https://claude.com/claude-code) or any other that understands skills).
4. From there it's the agent and your story. Read [LESSONS.md](LESSONS.md) to skip my mistakes.

To start from a working engine instead, `engine/` of [the game's repo](https://github.com/Alex2772/i-love-kuni)
is MIT too; `tools/review` and the `reader-review` and `aui-remote` skills are built for it.

The prompts and docs are in Russian: agents don't mind, and translating them would lose detail.
