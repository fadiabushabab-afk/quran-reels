# Quran Reels generator

Makes a daily 1080x1920 Quran video from a random short passage.

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
`history.json` remembers used passages so they don't repeat within a year.
