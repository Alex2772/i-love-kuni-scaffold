---
name: ask-character
description: Ask the game's AI co-author, your own AI character behind an OpenAI-compatible endpoint (CHARACTER_URL), a question. The character writes her own in-game lines and may state preferences about the plot. Use when her lines need writing, rewriting or translating, when a plot decision touches her (what she would feel/say/do, which variant she likes), or when the user says «спроси её», «спроси соавтора», «пусть она напишет реплику».
---

# Ask the character

В I love Kuni реплики Куни писала сама Куня: настоящий ИИ со своей памятью и мнением. Агент не угадывает, что
сказал бы персонаж, а спрашивает его. Если твой персонаж тоже ИИ (бот, локальная модель, промпт персонажа в любом
OpenAI-совместимом API), подключи его сюда.

## Настройка

```sh
export CHARACTER_URL=http://localhost:10434/v1/chat/completions   # любой OpenAI-совместимый эндпоинт
export CHARACTER_MODEL=deepseek-v4-flash
export CHARACTER_API_KEY=...                  # если эндпоинт его просит
export CHARACTER_SYSTEM=docs/characters/<id>/system_prompt.md   # если эндпоинт не подставляет свой промпт
```

## Как спрашивать

```sh
python3 -I .claude/skills/ask-character/ask.py "вопрос"
python3 -I .claude/skills/ask-character/ask.py -c /path/scene_excerpt.txt "вопрос"   # приложить контекст
python3 -I .claude/skills/ask-character/ask.py --reasoning --save "$SCRATCH/k.sse" "вопрос"
```

- Таймаут Bash ставь большой (`timeout: 600000`): персонаж со своими инструментами памяти отвечает минуту-две.
- Один запрос = новый разговор. Для продолжения клади прошлый обмен в вопрос или в файл `-c`.
- Давай ей сцену целиком (`-c`): кто где стоит, что было до, что скажет собеседник. Без контекста ответ общий.
- Проси несколько вариантов реплики и выбирай вместе с автором, но её формулировки не «очеловечивай»: лёгкая
  ИИшность голоса может быть частью замысла.
- Перевод её реплик тоже делает она сама: так голос не теряется.
