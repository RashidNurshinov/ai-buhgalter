# Озвучка роликов (RouterAI)

Ключ — переменная окружения `ROUTERAI_API_KEY` (в репозиторий ключ не кладём).

```
cd voice && python3 voice.py gem google/gemini-3.8-flash-tts Fenrir pcm   # дёшево, ~1 ₽/ролик
python3 voice.py el elevenlabs/eleven-v3 Adam mp3                        # дороже, ~5 ₽/ролик
```
Тексты и тайминги сцен — список `SEG` в `voice.py` (тайминги из `ad_template.html`).
Результат `<name>_voice.wav` (60 с) сводится с роликом, музыка приглушается под голос:
```
ffmpeg -i ролик.mp4 -i gem_voice.wav -filter_complex "[1:a]aresample=48000,volume=1.6,asplit=2[vk][vo];[0:a]aresample=48000,volume=0.8[m];[m][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];[md][vo]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k out.mp4
```
