# Quran Reels generator

Makes a daily 1080x1920 Quran video.

- **Daily order:** groups rotate (virtue passage → short surah → thematic passage); Fridays use
  the first or last ten verses of Al-Kahf, alternating.
- **Two reels a day (since 18 Nov 2026, 2-week test):** Saturday–Thursday a MORNING reel at 08:07
  and an EVENING reel at 18:07 Baghdad; Friday stays at one (Al-Kahf, 09:07). Each continues the
  same group rotation and background cycle. Morning reels get no Story and sometimes a morning
  hook («آيةٌ تبدأ بها يومك»). One reel per slot: a second run for the same slot does not post
  (manual runs choose the slot and can add "force" to override). Each history entry carries
  `slot` (`morning` / `evening`; older entries without it are evening). To go back to one a day,
  delete the two morning `cron` lines (`7 5 …` and `37 6 …`) in `.github/workflows/daily-reel.yml`.
- **Length:** weekday reels are at most 30 s (since 5 Nov 2026; was 60 s), comforting and short passages are tried first (`COMFORT` in `passages.py`) (Fridays up to ~3 min for Al-Kahf; on Facebook these go out as a regular Page video,
  since Facebook Reels stop at 90 s). A longer passage is posted one complete ruku' section at a time (the
  traditional thematic divisions of the mushaf), continuing with the next section the next time
  the passage comes round. A passage with no section short enough is skipped.
- **Passages:** chosen from `passages.py`: short surahs in full (opened with the basmala) and
  well-known verses of great virtue, always complete in meaning. Every passage is used once
  before any repeats. Edit `passages.py` to add or remove passages.
- **Caption:** hook line (Arabic | English) → title → virtue with its source (if any) → reflection
  quoted from التفسير الميسر with its source → verses in Arabic → Saheeh International English →
  surah and reciter → «اكتب آمين» / share as sadaqah jariyah → "Follow @… for daily verses" →
  5 hashtags (Instagram's limit), rotated at random each reel: a big-reach tag (`#quran` / `#islam` /
  `#muslim` / `#القران_الكريم`), the surah (`#surah<name>`), a mood tag (by group; `#jumuah` on Fridays,
  `#dua` for du'a passages), a discovery tag (Arabic or English) and `#صدقة_جارية` / `#sadaqahjariyah`.
  The pools are at the top of `hashtags_for` in `generate.py`.
  Kept under 2,100 characters (the English is dropped first if a passage is long).
- **Reciter:** random each day from 20 reciters, all 128–192 kbps; a reciter whose audio is missing is skipped (if a passage is too long with one reciter,
  another is tried).
- **Cover:** the Instagram cover is a frame from the first verse (not the basmala), and the very
  first frame already shows the text (Facebook uses it as the cover), so covers
  differ from reel to reel.
- **Stories:** right after the reel goes out on Instagram and on the Facebook Page, the same video
  is shared to that account's Story (no caption; stories last 24 h). A story is only posted where
  the reel succeeded. No stories for the morning reel, on Fridays (the Al-Kahf reels), or for any video over 60 s. A failed story
  never blocks the reel or the history entry; it shows as an error note on the run. Turn stories
  off with the repository variable `STORIES=false`, untick "story" on a manual run, or add
  `nostory` to the platforms box. Story links are saved under `stories` in `history.json`.
- **Automatic retry:** if a scheduled run fails (making the video or posting it), the workflow
  waits 45 minutes and runs again, up to 2 times (repository variables `MAX_RETRIES`, and
  `RETRY_DELAY_SEC` = 2700, change this). If nothing went out, a new video is made. If the reel
  already went out on one platform, the same video is posted only where it failed, so nothing is
  posted twice, and the existing `history.json` record is completed. Manual test runs are not
  retried. GitHub still emails you about the failed run; a later green run means the retry worked.
- **Trends:** the "Verse trends" workflow (`trends.py`, daily 14:23 Baghdad) reads our own reels'
  views, reach, saves, shares, likes and comments, plus the top posts of 8 Quran hashtags on
  Instagram (surah names, verse references and "آية الكرسي"-style names in their captions), and
  writes `trends.json`. Inside the day's group and freshness band, passages in the top quarter of
  those scores are picked first. Saves and shares count most. Change the hashtags with the
  repository variable `TREND_TAGS` (Instagram allows 30 unique hashtags per 7 days). Hashtag
  reading needs the "Instagram Public Content Access" feature on the Meta app; without it only our
  own results are used. TikTok has no official API for this, so it is not included.
- **Background:** an image from `backgrounds/` (the user's library, synced from their
  "Holy Quran" folder). Backgrounds rotate in full cycles: none is reused until every image and clip in the library has been used once, then the cycle starts again (least recently used first). Each image is
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

## TikTok

Posting code: `tiktok.py` (Direct Post, file upload). TikTok gets the reel only (no story), and only
when the repository variable `PLATFORMS` includes `tiktok` and these are set:

| Name | Kind | What |
|---|---|---|
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` | secrets | from the TikTok developer app |
| `TIKTOK_REDIRECT_URI` | variable | the redirect URI registered under Login Kit |
| `GH_ADMIN_TOKEN` | secret | fine-grained GitHub token, this repo only, Secrets: read and write (saves TikTok's rotating refresh token) |
| `TIKTOK_REFRESH_TOKEN` | secret | written by the **TikTok connect** workflow; do not set by hand |
| `TIKTOK_PRIVACY` | variable | optional, default `PUBLIC_TO_EVERYONE` |

Until TikTok audits the developer app, every post is private (visible only to the account) and the
account itself must be set to private. After the audit, posts go out public.

## On-time posting (external trigger)

Since 16 Nov 2026 GitHub has been starting the scheduled runs 7–9 hours late (or not at all), so the guard skips them and nothing is posted. The fix is an outside scheduler that starts the workflow on time; GitHub's own crons stay as a backup.

1. Create a fine-grained GitHub token: repository access **quran-reels only**, permission **Actions: Read and write**.
2. On cron-job.org (free), add one job per reel, time zone **Asia/Baghdad**:
   - URL: `https://api.github.com/repos/fadiabushabab-afk/quran-reels/actions/workflows/daily-reel.yml/dispatches`, method **POST**
   - Headers: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`
   - Body, morning (Sat–Thu 08:07): `{"ref":"main","inputs":{"auto":"true","slot":"morning"}}`
   - Body, evening (Sat–Thu 18:07, Friday 09:07): `{"ref":"main","inputs":{"auto":"true","slot":"evening"}}`

A run with `auto=true` is treated like a scheduled run: it only posts inside its window, never twice per slot, and is retried after a failure.
