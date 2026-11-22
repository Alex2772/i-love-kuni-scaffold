# Арт: пример

Пример файла описаний для `tools/art/generate.py` (формат — [README.md](README.md)): одна локация, один персонаж, один
предмет. `### kitchen_maid` получит id `example/kitchen_maid` и ляжет в `data/img/example/kitchen_maid.webp`.

    python3 -I tools/art/generate.py --list                     # что есть, что устарело
    python3 -I tools/art/generate.py example/kitchen_maid       # нарисовать одну (всегда с id!)

Нужен `OPENROUTER_API_KEY` в окружении.

## Общее

- define STYLE: New panel for the same anime manga. Use the attached images as references and keep exactly their soft painterly anime art style, line work and colour palette. This is a dream in an old 18th-century style manor: warm candlelight and firelight, deep warm brown shadows, no cold blue light indoors. No text, no letters, no logos, no speech bubbles, no frames.
- define EDIT_STYLE: Keep the exact same anime art style, colours, lighting, camera angle and composition as the input image. Change only what is asked.
- define KUNI: a petite adult anime catgirl, long dark navy-blue hair with lighter sky-blue ends, blue cat ears, thin cat whiskers on her cheeks, a small fang, bright blue eyes, black choker with a small golden bell, long blue cat tail
- define ORACLE: exactly the Oracle machine from the reference docs/props/oracle/oracle.webp: a brass automaton on a dark wooden cabinet with one drawer; NO glass dome, no glass cover — the brass gears on top are open; two round clear glass lamps on curved brass arms at the front left and front right; exactly ONE opening, a wide horizontal paper slot with a brass lip in the front of the case below the lamps (no vertical side slot, no paper strip sticking out, no coin slot); one brass lever with a dark wooden knob on a round hub on the RIGHT side; a low round brass base with a blank brass plate

### kitchen_maid
Персонаж в известном месте: `gen: ref` с референсами места и персонажа. В промпте прямо сказано, что должно совпасть.
- gen: ref, 1216x832
- refs: docs/locations/kitchen/kitchen.webp docs/characters/kuni/kuni-maid.png docs/characters/kuni/kuni-face.png
- prompt: {STYLE} The same kitchen as in the first image, from the same camera position, morning: grey rainy light from the tall east window straight ahead, drizzle on the glass. Behind the long scrubbed oak island stands the girl from the second and third images ({KUNI}, black maid dress with SHORT PUFFED BLACK SLEEVES (puff sleeves) trimmed with a white frill at the shoulder, bare forearms, no cuffs, black bow, white frilled apron, white frilled maid headband, black stockings, black mary jane shoes) — the maid uniform exactly as in the second image, including the short puff sleeves. She stands a little awkwardly, shy proud smile with a small fang, her bare forearms and hands dusted with flour. On the island in front of her: a plate of slightly burnt toast, a white porcelain teapot and two cups of perfectly brewed tea, a bag of flour. Her blue tail sways behind her.
- shows: подгоревшие тосты; две чашки чая; мука на руках
- time: morning

### kitchen_maid_sweat
Манпу рисует модель поверх готовой картинки, как мангака: отдельный вариант через `edit`.
- gen: edit kitchen_maid
- prompt: {EDIT_STYLE} Add manga sweat drops: two or three large hand-inked teardrop-shaped sweat drops with a white highlight and a thin dark outline flying off beside her head, as a mangaka draws a nervous shock. Nothing else changes: keep her face, hair, ears, the toast, the tea and the background exactly.
- shows: капли пота у головы
- time: morning

### oracle_paper
Предмет по канону: референс предмета + референс персонажа, устройство предмета названо в промпте целиком.
- gen: ref, 832x1216
- refs: docs/props/oracle/oracle.webp docs/characters/kuni/kuni-face.png
- prompt: {STYLE} A close-up at night by candlelight: {ORACLE}. The girl from the second image ({KUNI}) slides a small folded paper note into the wide horizontal paper slot at the front with two fingers, her other hand already on the lever on the RIGHT side. Both lamps are still dark. We see her hands, part of her face in profile, the bell on her choker.
- shows: бумажка в щели; рука на рычаге справа; лампы не горят
- time: night
