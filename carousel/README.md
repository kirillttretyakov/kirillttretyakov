# Вещи, которые я понял после 30

Карусель для Instagram / TikTok: одно полотно `10800×1920` (10 вертикальных кадров `1080×1920`), фото и цветные поля живут на швах.

## Что постить

Загружай **10 файлов по порядку**, не один широкий JPEG:

`export/slides/01.jpg` … `export/slides/10.jpg`

Мастер для проверки склейки: `export/master.jpg`.

## Собрать заново

```bash
python3 carousel/render.py
```

Нужны Chrome и Pillow. Шрифты лежат в `carousel/fonts/`.

## Шрифты

В гайде главный display — Fabric Grotesk. Файла в среде не было (коммерческий Fontfabric), поэтому заголовки и номера собраны на **Inter Tight** (editorial-пара из того же гайда) + **Onest** на пояснениях.

Если есть лицензия Fabric Grotesk, положи `ttf` в `fonts/` и поменяй `--display` в `index.html`.
