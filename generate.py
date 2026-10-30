#!/usr/bin/env python3
"""
Quran Reels generator.

Picks a random short passage, downloads per-verse recitation audio from
everyayah.com and Uthmani text from api.alquran.cloud, and renders a
1080x1920 vertical video with the text shown verse by verse.

Outputs (in --out, default ./out):
  reel.mp4      the video
  caption.txt   ready-to-post caption
  meta.json     what was chosen (surah, verses, reciter, durations)

Usage:
  python generate.py                       # random passage, random reciter
  python generate.py --surah 112 --start 1 --end 4 --reciter alafasy
"""
import argparse, datetime, json, os, random, shutil, subprocess, sys, tempfile, time
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
FPS = 30

# everyayah.com folder names -> Arabic display name
RECITERS = {
    "alafasy":   ("Alafasy_128kbps", "مشاري راشد العفاسي"),
    "husary":    ("Husary_128kbps", "محمود خليل الحصري"),
    "minshawy":  ("Minshawy_Murattal_128kbps", "محمد صديق المنشاوي"),
    "abdulbasit": ("Abdul_Basit_Murattal_192kbps", "عبد الباسط عبد الصمد"),
    "maher":     ("MaherAlMuaiqly128kbps", "ماهر المعيقلي"),
    "sudais":    ("Abdurrahmaan_As-Sudais_192kbps", "عبد الرحمن السديس"),
    "shuraym":   ("Saood_ash-Shuraym_128kbps", "سعود الشريم"),
    "dussary":   ("Yasser_Ad-Dussary_128kbps", "ياسر الدوسري"),
}

# number of verses per surah (standard Hafs count)
AYAH_COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,
112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,
18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,
40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,
4,5,6]
assert len(AYAH_COUNTS) == 114

UA = {"User-Agent": "quran-reels/1.0"}


# ---------------------------------------------------------------- network

def http_get(url, binary=False, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else data.decode("utf-8")
        except Exception as e:  # retry with backoff
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed: {url}: {last}")


def fetch_verse(surah, ayah, translation=None):
    eds = "quran-uthmani" + (f",{translation}" if translation else "")
    j = json.loads(http_get(f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/editions/{eds}"))
    data = j["data"]
    ar = data[0]
    text = ar["text"].strip()
    # alquran.cloud prefixes verse 1 of each surah (except 1 and 9) with the basmala
    if ayah == 1 and surah not in (1, 9) and text.startswith("بِسْمِ"):
        text = " ".join(text.split(" ")[4:]).strip()
    tr = data[1]["text"].strip() if translation and len(data) > 1 else None
    return {
        "surah": surah, "ayah": ayah, "text": text, "translation": tr,
        "surah_name_ar": ar["surah"]["name"], "surah_name_en": ar["surah"]["englishName"],
    }


def fetch_audio(folder, surah, ayah, dest):
    url = f"https://everyayah.com/data/{folder}/{surah:03d}{ayah:03d}.mp3"
    with open(dest, "wb") as f:
        f.write(http_get(url, binary=True))
    return dest


def duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path]).decode().strip()
    return float(out)


# ---------------------------------------------------------------- selection

def load_history(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def choose_passage(rng, history, min_sec, max_sec, folder, tmp, translation):
    """Pick a random start verse and extend forward until min_sec is reached
    (never exceeding max_sec). Skips verses that are too long on their own."""
    used = {(h["surah"], h["start"]) for h in history[-365:]}
    for attempt in range(40):
        surah = rng.randint(1, 114)
        n = AYAH_COUNTS[surah - 1]
        start = rng.randint(1, n)
        if (surah, start) in used:
            continue
        verses, total = [], 0.0
        a = start
        while a <= n:
            v = fetch_verse(surah, a, translation)
            if len(v["text"]) > 420:          # too long for one screen
                break
            mp3 = fetch_audio(folder, surah, a, os.path.join(tmp, f"{surah:03d}{a:03d}.mp3"))
            d = duration(mp3)
            if total + d > max_sec:
                break
            v["audio"], v["dur"] = mp3, d
            verses.append(v)
            total += d
            if total >= min_sec:
                break
            a += 1
        if verses and total >= min_sec * 0.5:
            return verses
    raise RuntimeError("could not find a suitable passage")


def fixed_passage(surah, start, end, folder, tmp, translation):
    verses = []
    for a in range(start, end + 1):
        v = fetch_verse(surah, a, translation)
        mp3 = fetch_audio(folder, surah, a, os.path.join(tmp, f"{surah:03d}{a:03d}.mp3"))
        v["audio"], v["dur"] = mp3, duration(mp3)
        verses.append(v)
    return verses


# ---------------------------------------------------------------- drawing

def font(name, size):
    return ImageFont.truetype(os.path.join(HERE, "fonts", name), size)


def text_w(draw, s, f):
    b = draw.textbbox((0, 0), s, font=f, direction="rtl", language="ar")
    return b[2] - b[0]


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_w(draw, t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text, fname, box_w, box_h, start=96, minimum=44, spacing=1.75):
    size = start
    while size >= minimum:
        f = font(fname, size)
        lines = wrap(draw, text, f, box_w)
        lh = int(size * spacing)
        if len(lines) * lh <= box_h:
            return f, lines, lh
        size -= 4
    f = font(fname, minimum)
    return f, wrap(draw, text, f, box_w), int(minimum * spacing)


def draw_centered(draw, y, s, f, fill, rtl=True, shadow=True):
    kw = {"direction": "rtl", "language": "ar"} if rtl else {}
    b = draw.textbbox((0, 0), s, font=f, **kw)
    x = (W - (b[2] - b[0])) // 2 - b[0]
    if shadow:
        draw.text((x + 3, y + 3), s, font=f, fill=(0, 0, 0, 170), **kw)
    draw.text((x, y), s, font=f, fill=fill, **kw)


def make_background(path_or_none, rng, dest):
    """Use a photo from backgrounds/ if available, otherwise a generated gradient."""
    if path_or_none:
        im = Image.open(path_or_none).convert("RGB")
        s = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
        l, t = (im.width - W) // 2, (im.height - H) // 2
        im = im.crop((l, t, l + W, t + H))
    else:
        palettes = [((12, 32, 46), (40, 90, 96)), ((24, 18, 40), (88, 60, 110)),
                    ((10, 30, 22), (52, 104, 78)), ((40, 22, 12), (140, 92, 48)),
                    ((8, 16, 36), (36, 64, 120))]
        c1, c2 = rng.choice(palettes)
        im = Image.new("RGB", (W, H))
        px = ImageDraw.Draw(im)
        for y in range(H):
            k = y / H
            px.line([(0, y), (W, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3)))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        for _ in range(26):
            r = rng.randint(30, 140)
            x, y = rng.randint(0, W), rng.randint(0, H)
            g.ellipse([x - r, y - r, x + r, y + r], fill=(255, 240, 210, rng.randint(14, 40)))
        glow = glow.filter(ImageFilter.GaussianBlur(40))
        im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
    # darken for legibility
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 105))
    im = Image.alpha_composite(im.convert("RGBA"), shade).convert("RGB")
    im.save(dest, quality=95)
    return dest


def make_overlay(v, header, reciter_ar, handle, dest, show_translation):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gold = (238, 202, 120, 255)
    white = (255, 255, 255, 255)

    # header pill: surah name + verse range
    hf = font("Amiri-Bold.ttf", 54)
    hw = text_w(d, header, hf) + 90
    d.rounded_rectangle([(W - hw) // 2, 150, (W + hw) // 2, 250], radius=50, fill=(0, 0, 0, 120))
    draw_centered(d, 158, header, hf, gold, shadow=False)
    rf = font("Amiri-Regular.ttf", 40)
    draw_centered(d, 275, "القارئ: " + reciter_ar, rf, (235, 235, 235, 255))

    # verse text block
    box_w, box_h = W - 150, 900 if show_translation else 1100
    f, lines, lh = fit_text(d, f"{v['text']} ﴿{to_ar_digits(v['ayah'])}﴾", "AmiriQuran.ttf", box_w, box_h)
    top = 420 + (box_h - len(lines) * lh) // 2
    for i, ln in enumerate(lines):
        draw_centered(d, top + i * lh, ln, f, white)

    if show_translation and v.get("translation"):
        tf = font("Amiri-Regular.ttf", 36)
        words, tl, cur = v["translation"].split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=tf) <= W - 180 or not cur:
                cur = t
            else:
                tl.append(cur); cur = w
        if cur:
            tl.append(cur)
        y = 1380
        for ln in tl[:6]:
            draw_centered(d, y, ln, tf, (220, 220, 220, 255), rtl=False)
            y += 50

    if handle:
        draw_centered(d, H - 170, handle, font("Amiri-Regular.ttf", 36), (230, 230, 230, 200), rtl=False, shadow=False)
    img.save(dest)
    return dest


def to_ar_digits(n):
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


# ---------------------------------------------------------------- render

def render(verses, bg, reciter_ar, handle, out_mp4, tmp, show_translation):
    s, a1, a2 = verses[0]["surah"], verses[0]["ayah"], verses[-1]["ayah"]
    rng_txt = to_ar_digits(a1) if a1 == a2 else f"{to_ar_digits(a1)}–{to_ar_digits(a2)}"
    header = f"{verses[0]['surah_name_ar']} · {rng_txt}"

    # audio: concatenate verse files
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for v in verses:
            f.write(f"file '{v['audio']}'\n")
    audio = os.path.join(tmp, "audio.m4a")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", audio], check=True)
    total = duration(audio)

    inputs = ["-loop", "1", "-framerate", str(FPS), "-i", bg]
    filt, t, last = [], 0.0, "bg"
    # slow push-in on background
    filt.append(f"[0:v]scale={int(W*1.12)}:-2,"
                f"crop={W}:{H}:'(in_w-{W})/2+sin(t/9)*20':'(in_h-{H})/2',setsar=1[bg]")
    for i, v in enumerate(verses):
        ov = make_overlay(v, header, reciter_ar, handle, os.path.join(tmp, f"ov{i}.png"), show_translation)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", ov]
        st, en = t, t + v["dur"]
        fade = min(0.35, v["dur"] / 4)
        filt.append(f"[{i+1}:v]format=rgba,fade=in:st={st:.3f}:d={fade:.2f}:alpha=1,"
                    f"fade=out:st={en-fade:.3f}:d={fade:.2f}:alpha=1[o{i}]")
        filt.append(f"[{last}][o{i}]overlay=0:0:enable='between(t,{st:.3f},{en:.3f})'[v{i}]")
        last = f"v{i}"
        t = en
    filt.append(f"[{last}]format=yuv420p[vout]")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-i", audio,
           "-filter_complex", ";".join(filt),
           "-map", "[vout]", "-map", f"{len(verses)+1}:a",
           "-t", f"{total:.3f}", "-r", str(FPS),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)
    return total


def caption(verses, reciter_ar, hashtags):
    v0, v1 = verses[0], verses[-1]
    rng_txt = f"{v0['ayah']}" if v0["ayah"] == v1["ayah"] else f"{v0['ayah']}-{v1['ayah']}"
    body = " ".join(f"{v['text']} ﴿{to_ar_digits(v['ayah'])}﴾" for v in verses)
    if len(body) > 900:
        body = body[:900].rsplit(" ", 1)[0] + " …"
    return (f"{body}\n\n"
            f"📖 {v0['surah_name_ar']} ({v0['surah_name_en']}) — الآيات {rng_txt}\n"
            f"🎙️ القارئ: {reciter_ar}\n\n{hashtags}\n")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--reciter", default="random", help="key from RECITERS, or 'random'")
    ap.add_argument("--surah", type=int); ap.add_argument("--start", type=int); ap.add_argument("--end", type=int)
    ap.add_argument("--min-sec", type=float, default=25); ap.add_argument("--max-sec", type=float, default=58)
    ap.add_argument("--translation", default="", help="e.g. en.sahih; empty = Arabic only")
    ap.add_argument("--handle", default="", help="text shown at the bottom, e.g. @myaccount")
    ap.add_argument("--hashtags", default="#قرآن #القرآن_الكريم #تلاوة #quran #islam #reels")
    ap.add_argument("--history", default=os.path.join(HERE, "history.json"))
    ap.add_argument("--seed", default=None)
    args = ap.parse_args()

    seed = args.seed or datetime.date.today().isoformat() + str(time.time_ns())
    rng = random.Random(seed)
    key = rng.choice(list(RECITERS)) if args.reciter == "random" else args.reciter
    folder, reciter_ar = RECITERS[key]

    os.makedirs(args.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="qr_")
    try:
        if args.surah:
            verses = fixed_passage(args.surah, args.start or 1, args.end or args.start or 1,
                                   folder, tmp, args.translation or None)
        else:
            history = load_history(args.history)
            verses = choose_passage(rng, history, args.min_sec, args.max_sec, folder, tmp,
                                    args.translation or None)

        bg_dir = os.path.join(HERE, "backgrounds")
        bgs = [os.path.join(bg_dir, f) for f in sorted(os.listdir(bg_dir))
               if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))] if os.path.isdir(bg_dir) else []
        bg = make_background(rng.choice(bgs) if bgs else None, rng, os.path.join(tmp, "bg.jpg"))

        mp4 = os.path.join(args.out, "reel.mp4")
        total = render(verses, bg, reciter_ar, args.handle, mp4, tmp, bool(args.translation))
        cap = caption(verses, reciter_ar, args.hashtags)
        with open(os.path.join(args.out, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(cap)
        meta = {"date": datetime.date.today().isoformat(), "surah": verses[0]["surah"],
                "surah_name": verses[0]["surah_name_en"], "start": verses[0]["ayah"],
                "end": verses[-1]["ayah"], "reciter": key, "seconds": round(total, 2)}
        with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        if not args.surah and args.history:
            hist = load_history(args.history) + [meta]
            with open(args.history, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, indent=1)
        print(json.dumps(meta, ensure_ascii=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
