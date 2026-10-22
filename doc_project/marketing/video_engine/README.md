# Видеодвижок роликов (моушен-дизайн)

Ролик = HTML-страница `ad.html` 1080×1920 с функцией `render(t)`: она выставляет кадр на момент `t` секунд.
`render.js` (Playwright/Chromium) снимает 30 кадров/с, ffmpeg собирает mp4 с музыкой.

```bash
# ad_template.html — универсальный шаблон: товары задаются списком PRODUCTS (любое число сцен, фото-вырезка или интерьер)
node render.js preview 2.4,13,39   # контрольные кадры prev_*.jpg
node render.js full                 # все кадры в frames/
ffmpeg -framerate 30 -i frames/%05d.jpg -i music40.m4a -map 0:v -map 1:a \
  -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart -c:a copy -shortest out.mp4
```

Музыка короче ролика: зацикливается через `acrossfade`, в конце `afade` (обложку mp3 отключать: `-map "[a]" -vn`).
Шрифты: Russo One, Montserrat (OFL). Первый ролик: ТВ Витязь 50", LG F2Y1HS3W, Бирюса 240KVS, 2026-10-20.
