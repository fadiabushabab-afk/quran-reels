# Quran Reels generator

Makes a daily 1080x1920 Quran video.

- **Passages:** chosen from `passages.py`: short surahs in full (opened with the basmala) and
  well-known verses of great virtue, always complete in meaning. Every passage is used once
  before any repeats. Edit `passages.py` to add or remove passages.
- **Reciter:** random each day from 8 reciters (if a passage is longer than 88 s with one
  reciter, another is tried; Facebook Reels allow up to 90 s).
- **Background:** generated Islamic geometric pattern (8-pointed star lattice) with a mihrab arch,
  in one of five colour schemes. Photos you add to `backgrounds/` are used on about half of the days.

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
