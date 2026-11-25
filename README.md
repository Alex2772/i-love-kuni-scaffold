# I love Kuni: промпты

[Русский](README.md) · [English](README.en.md)

Промпты, скиллы и инструкции для агентов, с которыми сделана манга-новелла
[I love Kuni](https://github.com/Alex2772/i-love-kuni). Бери, меняй под себя и делай игру мечты со своими
персонажами. Код, промпты и инструменты под [MIT](LICENSE). Куня и примеры из игры в `docs/` под
[CC BY-NC-SA 4.0](LICENSE-ASSETS): фан-игры с ней можно, некоммерчески, с указанием «Kuni by Alex2772» и пометкой,
что игра неофициальная.

## Что здесь

| Файл | Что это |
|---|---|
| [INITIAL_PROMPT.md](INITIAL_PROMPT.md) | самый первый промпт, с которого начался проект, дословно, и что потом пошло иначе |
| [LESSONS.md](LESSONS.md) | чему научились: процесс с агентами, арт, вёрстка, сюжет, перевод |
| [CLAUDE.md](CLAUDE.md) | шаблон инструкций агенту для своей игры |
| [.claude/agents/reader.md](.claude/agents/reader.md) | агент-читатель с одним инструментом `Read`: не может подсмотреть в код |
| [.claude/skills/mangaka](.claude/skills/mangaka) | правила манга-вёрстки с примерами: показывать, а не рассказывать, баблы, паузы, форма панелей |
| [.claude/skills/reader-review](.claude/skills/reader-review) | слепая рецензия: читатели со случайными портретами и леттерер |
| [.claude/skills/openrouter-image](.claude/skills/openrouter-image) | генерация и правка картинок через OpenRouter |
| [.claude/skills/ask-character](.claude/skills/ask-character) | спросить своего ИИ-персонажа (любой OpenAI-совместимый API) |
| [.claude/skills/music](.claude/skills/music) | музыка и звуки синтезом с нуля |
| [.claude/skills/aui-remote](.claude/skills/aui-remote) | собрать, запустить и покликать AUI-приложение |
| [.claude/skills/cpp-style](.claude/skills/cpp-style) | стиль C++ |
| [tools/art](tools/art) | генератор арта по описаниям `docs/art/*.md` (OpenRouter), крупные планы, кадры жестов |
| [tools/music](tools/music) | музыка и звуки синтезом на numpy, без сэмплов |
| [tools/review](tools/review) | дамп страниц и промпты для слепых читателей (нужен движок игры) |
| [docs/](docs) | структура документации: сюжет, главы, персонажи, места, предметы, арт |
| [docs/characters/kuni](docs/characters/kuni) | Куня: канон, голос, референсы — бери в свою фан-игру |
| [docs/locations/kitchen](docs/locations/kitchen), [docs/props/oracle](docs/props/oracle) | пример места и предмета с планом и референсом |
| [docs/art/example.md](docs/art/example.md) | пример описаний картинок: Куня на кухне, манпу, Оракул |

## Как начать

1. Форкни репу (или скопируй её в пустую папку).
2. Заполни `docs/`: `STORY.md`, персонажей, места и предметы по образцу Куни, кухни и Оракула. Хочешь фан-игру с
   Куней — она уже лежит в `docs/characters/kuni/`.
3. Перепиши [INITIAL_PROMPT.md](INITIAL_PROMPT.md) под свою игру и отдай агенту
   ([Claude Code](https://claude.com/claude-code) или любому другому, который понимает скиллы).
4. Дальше — агент и твоя история. Прочитай [LESSONS.md](LESSONS.md), чтобы не наступать на мои грабли.

Хочешь не с нуля, а на готовом движке: `engine/` из [репы игры](https://github.com/Alex2772/i-love-kuni) тоже под
MIT. `tools/review` и скиллы `reader-review` и `aui-remote` рассчитаны на него.

Промпты и документация на русском: агенту всё равно, а переводить их — терять детали.
