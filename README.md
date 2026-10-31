# Quran Reels generator

Makes a daily 1080x1920 Quran video.

- **Passages:** chosen from `passages.py`: short surahs in full (opened with the basmala) and
  well-known verses of great virtue, always complete in meaning. Every passage is used once
  before any repeats. Edit `passages.py` to add or remove passages.
- **Reciter:** random each day from 8 reciters (if a passage is longer than 88 s with one
  reciter, another is tried; Facebook Reels allow up to 90 s).
- **Background:** a fresh AI image every day from OpenAI's image API (the model behind ChatGPT
  images), in the warm golden style of the user's mood board (`genbg.py` lists the scenes).
  The image is then animated (`motion.py`): dust drifting in the light, breathing light and a slow
  camera drift, all looping seamlessly. Needs the repository secret `OPENAI_API_KEY`.
  If no key is set or the API fails, a photo from `backgrounds/` is used (also animated), and
  failing that a drawn Islamic style from `bgstyles.py`.
  Settings (repository variables): `OPENAI_IMAGE_MODEL` (default gpt-image-2),
  `OPENAI_IMAGE_QUALITY` (low / medium / high, default medium).

- Audio: everyayah.com (per-verse MP3, choice of reciters)
- Text: api.alquran.cloud (Uthmani script)
- Font: Amiri Quran (SIL Open Font License, see fonts/OFL.txt)

## Requirements
Python 3.9+, ffmpeg on PATH, Pillow with libraqm (`pip install -r requirements.txt`).

## Run
    python generate.py                                  # random passage, random reciter
    python generate.py --reciter alafasy --handle @mypage
    python generate.py --surah 112 --start 1 --end 4    # a specific passage

Output goes to `out/`: reel.mp4, caption.txt, meta.json.
Put your own photos in `backgrounds/` (any jpg/png) to use them instead of the generated gradient.
`history.json` remembers used passages.
