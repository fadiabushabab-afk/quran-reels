# Quran Reels generator

Makes a daily 1080x1920 Quran video.

- **Daily order:** groups rotate (virtue passage → short surah → thematic passage); Fridays use
  the first or last ten verses of Al-Kahf, alternating. One post per day: a second run on the same
  day does not post (manual runs can tick "force" to override).
- **Length:** weekday reels are at most 30 s (since 5 Nov 2026; was 60 s), comforting and short passages are tried first (`COMFORT` in `passages.py`) (Fridays up to ~3 min for Al-Kahf; Facebook only receives
  videos of 90 s or less). A longer passage is posted one complete ruku' section at a time (the
  traditional thematic divisions of the mushaf), continuing with the next section the next time
  the passage comes round. A passage with no section short enough is skipped.
- **Passages:** chosen from `passages.py`: short surahs in full (opened with the basmala) and
  well-known verses of great virtue, always complete in meaning. Every passage is used once
  before any repeats. Edit `passages.py` to add or remove passages.
- **Caption:** hook line (Arabic | English) → title → virtue with its source (if any) → reflection
  quoted from التفسير الميسر with its source → verses in Arabic → Saheeh International English →
  surah and reciter → «اكتب آمين» / share as sadaqah jariyah → "Follow @… for daily verses" →
  5 hashtags (Instagram's limit): `#quran #القرآن_الكريم #surah<name> #<theme> #explore`.
  Kept under 2,100 characters (the English is dropped first if a passage is long).
- **Reciter:** random each day from 8 reciters (if a passage is too long with one reciter,
  another is tried).
- **Cover:** the Instagram cover is a frame from the first verse (not the basmala), and the very
  first frame already shows the text (Facebook uses it as the cover), so covers
  differ from reel to reel.
- **Background:** an image from `backgrounds/` (the user's library, synced from their
  "Holy Quran" folder). The least recently used image is chosen, so all get a turn, and no image is reused within 10 days. Each image is
  animated by `motion.py`: soft warm light rays from above, dust floating almost still in the light,
  breathing light and a very slow camera drift, looping seamlessly every 30 s. Text is white on dark images and dark brown on light ones, with a soft glow
  behind the verses. If the folder is empty, a drawn Islamic style from `bgstyles.py` is used.

- Audio: everyayah.com (per-verse MP3, choice of reciters)
- Text: api.alquran.cloud — Uthmani script, Saheeh International English (`en.sahih`, shown under each verse and in the caption) and التفسير الميسر (`ar.muyassar`, the caption's reflection line)
- Font: Amiri Quran (SIL Open Font License, see fonts/OFL.txt)

## Requirements
Python 3.9+, ffmpeg on PATH, Pillow with libraqm (`pip install -r requirements.txt`).

## Run
    python generate.py                                  # random passage, random reciter
    python generate.py --reciter alafasy --handle @mypage
    python generate.py --surah 112 --start 1 --end 4    # a specific passage
    python generate.py --verses 73:1-20                 # same, short form

Output goes to `out/`: reel.mp4, caption.txt, meta.json.
Put your own photos (jpg/png) or video clips (mp4, prepared by `sync_backgrounds.py` as 1080x1920 seamless loops) in `backgrounds/` to use them instead of the generated gradient. Names in `background_exclude.txt` are never synced.
`history.json` remembers used passages.
