# hermes-skill-translated-video-subtitles

Скилл [Hermes Agent](https://hermes-agent.nousresearch.com/docs) для полного цикла: вырезать фрагмент видео, локально распознать речь, перевести её, встроить русские субтитры в картинку и проверить итоговый MP4.

Скачивание и нарезка делегируются скиллу [yt-dlp](https://github.com/vokasug/hermes-skill-yt-dlp), распознавание речи — [mlx-whisper](https://github.com/vokasug/hermes-skill-mlx-whisper). Этот скилл отвечает за перевод, тайминги, правила субтитров, рендер и проверку.

## Что умеет

- **Точный срез видео** — сначала скачивается мастер до 1080p, затем интервал вырезается ffmpeg с CRF 18 (без `--force-keyframes-at-cuts`, который пережимает весь фрагмент дефолтным x264). Если 1080p недоступен, агент спрашивает, какое качество взять
- **Локальная расшифровка** — MLX Whisper с word timestamps, без отправки аудио наружу
- **Перевод субтитров** — cues строятся по границам слов и реплик, а не по произвольным кускам
- **Контроль читаемости** — минимум 2 секунды на субтитр, ручные переносы строк, запрет «сиротских» слов
- **Запрет длинных тире** — `—` и `–` в тексте субтитров отклоняются конвертером
- **Crop/scale перед наложением** — чёрные поля измеряются `cropdetect`, субтитры накладываются на активную картинку, а не в letterbox-зону
- **Встроенные субтитры без libass** — если ffmpeg собран без `subtitles`/`drawtext`, используется fallback: прозрачные PNG через AppKit + timed overlays
- **Проверка результата** — `ffprobe`, полное декодирование, сравнение audio hash, визуальные кадры начала/середины/финала

## Правила субтитров

Эти правила встроены в скрипты и SKILL.md:

- субтитр не может быть короче 2.0 секунды;
- субтитры не должны пересекаться по времени;
- длинные тире `—` и `–` запрещены, используйте дефис `-` или перестраивайте фразу;
- для мобильного 720p базовый стиль: Arial Bold 51 pt, нижний отступ 28 px, чёрная оконтовка 8 px;
- толстая оконтовка рисуется как многосмещённый чёрный слой с белой заливкой сверху, а не через большой отрицательный `strokeWidth` (он заливает внутренности букв).

## Установка на чистый Mac

### 1. Hermes Agent

Установите и настройте Hermes Agent по [документации](https://hermes-agent.nousresearch.com/docs).

### 2. Системные зависимости

```bash
brew install ffmpeg node uv
```

Для рендера PNG-оверлеев нужен Swift из Xcode Command Line Tools. Если `swift --version` не работает:

```bash
xcode-select --install
```

### 3. Скилл yt-dlp и сам yt-dlp

```bash
mkdir -p $HERMES_HOME/skills/media
git clone https://github.com/vokasug/hermes-skill-yt-dlp $HERMES_HOME/skills/media/yt-dlp
```

Затем выполните установку yt-dlp по README этого репозитория. Критичный флаг для YouTube: `--js-runtimes node`.

### 4. Скилл mlx-whisper и модели

```bash
git clone https://github.com/vokasug/hermes-skill-mlx-whisper $HERMES_HOME/skills/media/mlx-whisper
```

Затем установите `mlx-whisper` и модели по README этого репозитория: `whisper-podlodka-turbo-MLX-q8` (русский) и `whisper-large-v3-turbo-8bit` (все остальные языки — без неё не-русские клипы распознаются ru-специализированной моделью с потерей качества).

### 5. Этот скилл

```bash
git clone https://github.com/vokasug/hermes-skill-translated-video-subtitles \
  $HERMES_HOME/skills/media/translated-video-subtitles
```

Hermes подхватывает скилл автоматически. Проверка: `hermes skills list`.

## Использование

Обычный путь — просто попросить Hermes, например:

> Скачай из этого видео интервал 3:44-5:48, расшифруй аудио, переведи на русский и наложи субтитры.

Если нужно запустить только механическую часть вручную:

```bash
SKILL_DIR=$HERMES_HOME/skills/media/translated-video-subtitles

# SRT -> cues.json; отклоняет cue < 2 с и длинные тире
python3 "$SKILL_DIR/scripts/srt_to_cues.py" translated.srt cues.json --min-duration 2.0

# cues.json -> прозрачные PNG для 1280x720
swift "$SKILL_DIR/scripts/render_subtitle_cues.swift" cues.json cue_pngs 1280 720 51 28 8

# PNG -> встроенные субтитры; --crop нужен только при встроенных чёрных полях
python3 "$SKILL_DIR/scripts/burn_cue_pngs.py" \
  --video input.mp4 --cues cues.json --png-dir cue_pngs \
  --out final.mp4 --width 1280 --height 720 --crop '856:484:212:118'
```

## Настройка под себя

- В примерах результат скачивания использует `$HOME/result-yt-dlp/`; замените на свою папку результатов.
- Пути `~/.local/bin/yt-dlp` и `~/.local/share/models/...` соответствуют инструкциям компонентных скиллов; если инструменты установлены иначе, замените пути в `SKILL.md`.
- Базовый стиль субтитров меняется аргументами `render_subtitle_cues.swift`: width, height, font size, bottom margin, outline radius.

## Структура репозитория

```
├── README.md
├── LICENSE
├── .gitignore
├── SKILL.md
└── scripts/
    ├── srt_to_cues.py             # SRT -> cue JSON + проверки длительности и тире
    ├── render_subtitle_cues.swift # cue JSON -> прозрачные PNG с оконтовкой
    └── burn_cue_pngs.py           # timed overlays -> итоговый MP4
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
