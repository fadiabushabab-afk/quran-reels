#!/usr/bin/env python3
"""
Quran Reels generator.

Each run picks a complete, well-known passage from passages.py (short surahs
in full, and famous verses of great virtue), a random reciter, and an Islamic
geometric background, then renders a 1080x1920 vertical video.

Audio: everyayah.com (one MP3 per verse).  Text: api.alquran.cloud (Uthmani).

Outputs (in --out, default ./out):
  reel.mp4      the video
  caption.txt   ready-to-post caption
  meta.json     what was chosen

Usage:
  python generate.py                                   # next passage, random reciter
  python generate.py --surah 112 --start 1 --end 4 --reciter alafasy
"""
import argparse, datetime, json, math, os, random, shutil, subprocess, sys, tempfile, time
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from passages import PASSAGES
import bgstyles, motion

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
FPS = 30

# everyayah.com folder names -> Arabic display name
RECITERS = {
    "alafasy":    ("Alafasy_128kbps", "مشاري راشد العفاسي"),
    "husary":     ("Husary_128kbps", "محمود خليل الحصري"),
    "minshawy":   ("Minshawy_Murattal_128kbps", "محمد صديق المنشاوي"),
    "abdulbasit": ("Abdul_Basit_Murattal_192kbps", "عبد الباسط عبد الصمد"),
    "maher":      ("MaherAlMuaiqly128kbps", "ماهر المعيقلي"),
    "sudais":     ("Abdurrahmaan_As-Sudais_192kbps", "عبد الرحمن السديس"),
    "shuraym":    ("Saood_ash-Shuraym_128kbps", "سعود الشريم"),
    "dussary":    ("Yasser_Ad-Dussary_128kbps", "ياسر الدوسري"),
}

# number of verses per surah (Hafs)
AYAH_COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,
112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,
18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,
40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,
4,5,6]
assert len(AYAH_COUNTS) == 114

UA = {"User-Agent": "quran-reels/1.0"}
CHUNK_CHARS = 170      # long verses are shown in parts of about this many characters


# ---------------------------------------------------------------- network

def http_get(url, binary=False, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return data if binary else data.decode("utf-8")
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed: {url}: {last}")


def fetch_verse(surah, ayah):
    j = json.loads(http_get(f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/quran-uthmani"))
    d = j["data"]
    text = d["text"].strip()
    # alquran.cloud prefixes verse 1 of each surah (except 1 and 9) with the basmala
    if ayah == 1 and surah not in (1, 9) and text.startswith("بِسْمِ"):
        text = " ".join(text.split(" ")[4:]).strip()
    return {"surah": surah, "ayah": ayah, "text": text,
            "surah_name_ar": d["surah"]["name"], "surah_name_en": d["surah"]["englishName"]}


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


def order_candidates(rng, history):
    """Passages never used first (shuffled), then the least recently used."""
    last_used = {}
    for i, h in enumerate(history):
        last_used[(h["surah"], h["start"], h["end"])] = i
    unused = [p for p in PASSAGES if (p[0], p[1], p[2]) not in last_used]
    used = [p for p in PASSAGES if (p[0], p[1], p[2]) in last_used]
    rng.shuffle(unused)
    used.sort(key=lambda p: last_used[(p[0], p[1], p[2])])
    return unused + used


def build_passage(surah, start, end, reciter_key, tmp, max_sec):
    """Download text + audio. Returns (verses, total_sec) or None if too long."""
    folder = RECITERS[reciter_key][0]
    verses, total = [], 0.0
    full_surah = start == 1 and surah not in (1, 9)
    if full_surah:   # open with the basmala (text and audio of 1:1)
        b = fetch_verse(1, 1)
        mp3 = fetch_audio(folder, 1, 1, os.path.join(tmp, f"{reciter_key}_basmala.mp3"))
        b.update(audio=mp3, dur=duration(mp3), marker=False)
        verses.append(b); total += b["dur"]
    for a in range(start, end + 1):
        v = fetch_verse(surah, a)
        mp3 = fetch_audio(folder, surah, a, os.path.join(tmp, f"{reciter_key}_{surah:03d}{a:03d}.mp3"))
        v.update(audio=mp3, dur=duration(mp3), marker=True)
        verses.append(v); total += v["dur"]
        if total > max_sec:
            return None
    return verses, total


def choose(rng, history, reciter_arg, tmp, max_sec, fixed=None):
    """Pick passage + reciter. If the recitation is longer than max_sec,
    try the other reciters, then the next passage."""
    keys = list(RECITERS)
    candidates = [fixed] if fixed else order_candidates(rng, history)
    for p in candidates[:60]:
        surah, start, end = p[0], p[1], p[2]
        title = p[3] if len(p) > 3 else ""
        if reciter_arg != "random":
            order = [reciter_arg]
        else:
            order = keys[:]; rng.shuffle(order)
            order = order if fixed else order[:2]      # long passages: one retry, then move on
        for rk in order:
            res = build_passage(surah, start, end, rk, tmp, max_sec)
            if res:
                return p, title, rk, res[0], res[1]
            print(f"  {surah}:{start}-{end} too long with {rk}, trying another", file=sys.stderr)
    raise RuntimeError("no passage fits within the time limit")


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
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text, fname, box_w, box_h, start=92, minimum=46, spacing=1.8):
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



def pick_photo(photos, history):
    """Least recently used image first, so every image gets a turn before any repeats."""
    last = {}
    for i, h in enumerate(history):
        bg = h.get("background", "")
        if bg.startswith("photo: "):
            last[bg[7:]] = i
    return min(photos, key=lambda p: (last.get(os.path.basename(p), -1), os.path.basename(p)))


def theme_for(path):
    """White text on dark images, dark text on light ones (judged on the verse area)."""
    im = Image.open(path).convert("L")
    w, h = im.size
    centre = im.crop((int(w * 0.1), int(h * 0.25), int(w * 0.9), int(h * 0.85)))
    mean = sum(i * c for i, c in enumerate(centre.histogram())) / (centre.width * centre.height)
    theme = dict(bgstyles.DARK_TEXT if mean > 165 else bgstyles.LIGHT_TEXT)
    theme["light_bg"] = mean > 165
    return theme

def make_photo_background(path, dest):
    im = Image.open(path).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((l, t, l + W, t + H))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    Image.alpha_composite(im.convert("RGBA"), shade).convert("RGB").save(dest, quality=95)
    return dest


def to_ar_digits(n):
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def split_long(text, limit=CHUNK_CHARS):
    """Split a long verse into parts of roughly `limit` characters at word breaks."""
    if len(text) <= limit * 1.3:
        return [text]
    words, parts, cur = text.split(), [], ""
    n_parts = math.ceil(len(text) / limit)
    target = len(text) / n_parts
    for w in words:
        if cur and len(cur) + 1 + len(w) > target and len(parts) < n_parts - 1:
            parts.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        parts.append(cur)
    return parts


def segments_from(verses):
    """One screen per verse; long verses split into parts timed by length."""
    segs, t = [], 0.0
    for v in verses:
        parts = split_long(v["text"])
        total_chars = sum(len(p) for p in parts)
        for i, p in enumerate(parts):
            d = v["dur"] * len(p) / total_chars
            last = i == len(parts) - 1
            label = p
            if v["marker"] and last:
                label = f"{p} ﴿{to_ar_digits(v['ayah'])}﴾"
            segs.append({"text": label, "start": t, "end": t + d})
            t += d
    return segs


def _soft_shadow(layer, color, radius=10, strength=170):
    a = layer.split()[3].filter(ImageFilter.GaussianBlur(radius)).point(lambda v: min(255, v * strength // 100))
    sh = Image.new("RGBA", layer.size, color + (0,))
    sh.putalpha(a)
    return Image.alpha_composite(sh, layer)


def make_static_overlay(header, title, reciter_ar, handle, theme, dest):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gold = (238, 206, 128, 255)
    hf = font("Amiri-Bold.ttf", 54)
    hw = text_w(d, header, hf) + 90
    d.rounded_rectangle([(W - hw) // 2, 120, (W + hw) // 2, 218], radius=49, fill=(0, 0, 0, 140))
    draw_centered(d, 127, header, hf, gold, shadow=False)
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    t = ImageDraw.Draw(txt)
    draw_centered(t, 232, "بصوت القارئ " + reciter_ar, font("Amiri-Regular.ttf", 40), theme["sub"] + (255,), shadow=False)
    if title:
        draw_centered(t, 1700, title, font("Amiri-Bold.ttf", 44), theme["title"] + (255,), shadow=False)
    if handle:
        draw_centered(t, H - 130, handle, font("Amiri-Regular.ttf", 34), theme["sub"] + (230,), rtl=False, shadow=False)
    txt = _soft_shadow(txt, theme["shadow"], 6, 150)
    Image.alpha_composite(img, txt).save(dest)
    return dest


def make_text_overlay(text, theme, dest):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box_w, box_h = W - 260, 1000
    f, lines, lh = fit_text(d, text, "AmiriQuran.ttf", box_w, box_h)
    top = 560 + (box_h - len(lines) * lh) // 2
    for i, ln in enumerate(lines):
        draw_centered(d, top + i * lh, ln, f, theme["verse"] + (255,), shadow=False)
    _soft_shadow(img, theme["shadow"], 14, 230).save(dest)
    return dest


# ---------------------------------------------------------------- render

def render(verses, title, bg, theme, reciter_ar, handle, out_mp4, tmp, animate=False):
    real = [v for v in verses if v["marker"]]
    a1, a2 = real[0]["ayah"], real[-1]["ayah"]
    rng_txt = to_ar_digits(a1) if a1 == a2 else f"{to_ar_digits(a1)}–{to_ar_digits(a2)}"
    header = f"{real[0]['surah_name_ar']} · {rng_txt}"

    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for v in verses:
            f.write(f"file '{v['audio']}'\n")
    audio = os.path.join(tmp, "audio.m4a")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-af", "apad=pad_dur=1.2", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", audio],
                   check=True)
    total = duration(audio)
    segs = segments_from(verses)

    if animate:
        # photo/AI image -> gentle looping motion (dust in the light, breathing light, slow drift)
        # render one seamless loop and repeat it (much faster than rendering every second)
        bgvid = motion.make_motion_video(bg, motion.LOOP, os.path.join(tmp, "bg.mp4"))
        # soft dark glow behind the verse area so text stays readable on busy images
        scrim = Image.new("L", (W, H), 0)
        ImageDraw.Draw(scrim).rounded_rectangle([40, 470, W - 40, 1660], radius=200, fill=150)
        scrim = scrim.filter(ImageFilter.GaussianBlur(90))
        scrim_rgb = (250, 244, 232) if theme.get("light_bg") else (0, 0, 0)
        sc = Image.new("RGBA", (W, H), scrim_rgb + (0,)); sc.putalpha(scrim)
        scrim_png = os.path.join(tmp, "scrim.png"); sc.save(scrim_png)
        inputs = ["-stream_loop", "-1", "-i", bgvid, "-loop", "1", "-framerate", str(FPS), "-i", scrim_png]
        grade = ("eq=saturation=1.03" if theme.get("light_bg")
                 else "eq=brightness=-0.04:saturation=1.05,vignette=angle=PI/4.5")
        filt = [f"[0:v]{grade},setsar=1[bg0]",
                "[bg0][1:v]overlay=0:0[bg]"]
    else:
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", bg]
        filt = [f"[0:v]scale={int(W*1.08)}:-2,"
                f"crop={W}:{H}:'(in_w-{W})/2+sin(t/10)*18':'(in_h-{H})/2+cos(t/12)*12',setsar=1[bg]"]
    last = "bg"
    base = 2 if animate else 1          # index of the first verse overlay input
    for i, s in enumerate(segs):
        ov = make_text_overlay(s["text"], theme, os.path.join(tmp, f"ov{i}.png"))
        inputs += ["-loop", "1", "-framerate", str(FPS), "-i", ov]
        st = s["start"]
        en = total if i == len(segs) - 1 else s["end"]
        fade = min(0.35, (en - st) / 4)
        filt.append(f"[{i+base}:v]format=rgba,fade=in:st={st:.3f}:d={fade:.2f}:alpha=1,"
                    f"fade=out:st={en-fade:.3f}:d={fade:.2f}:alpha=1[o{i}]")
        filt.append(f"[{last}][o{i}]overlay=0:0:enable='between(t,{st:.3f},{en:.3f})'[v{i}]")
        last = f"v{i}"
    static = make_static_overlay(header, title, reciter_ar, handle, theme, os.path.join(tmp, "static.png"))
    inputs += ["-loop", "1", "-framerate", str(FPS), "-i", static]
    filt.append(f"[{last}][{len(segs)+base}:v]overlay=0:0,"
                f"fade=in:st=0:d=0.6,fade=out:st={total-0.8:.3f}:d=0.8,format=yuv420p[vout]")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-i", audio,
           "-filter_complex", ";".join(filt),
           "-map", "[vout]", "-map", f"{len(segs)+base+1}:a",
           "-t", f"{total:.3f}", "-r", str(FPS),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)
    return total


def caption(verses, title, reciter_ar, hashtags, virtue=None):
    real = [v for v in verses if v["marker"]]
    v0, v1 = real[0], real[-1]
    rng_txt = f"{v0['ayah']}" if v0["ayah"] == v1["ayah"] else f"{v0['ayah']}-{v1['ayah']}"
    body = " ".join(f"{v['text']} ﴿{to_ar_digits(v['ayah'])}﴾" for v in real)
    if len(body) > 1200:
        body = body[:1200].rsplit(" ", 1)[0] + " …"
    head = f"✨ {title}\n" if title else ""
    if virtue:
        head += f"📜 {virtue}\n"
    head += "\n" if head else ""
    return (f"{head}{body}\n\n"
            f"📖 {v0['surah_name_ar']} ({v0['surah_name_en']}) — الآيات {rng_txt}\n"
            f"🎙️ بصوت القارئ {reciter_ar}\n\n{hashtags}\n")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--reciter", default="random", help="key from RECITERS, or 'random'")
    ap.add_argument("--surah", type=int); ap.add_argument("--start", type=int); ap.add_argument("--end", type=int)
    ap.add_argument("--max-sec", type=float, default=88, help="Facebook Reels limit is 90 s")
    ap.add_argument("--handle", default="", help="text shown at the bottom, e.g. @myaccount")
    ap.add_argument("--hashtags", default="#قرآن #القرآن_الكريم #تلاوة #آيات #quran #islam #reels")
    ap.add_argument("--history", default=os.path.join(HERE, "history.json"))
    ap.add_argument("--seed", default=None)
    ap.add_argument("--bg-style", default="", help="force a drawn style instead of photos: " + ", ".join(bgstyles.ALL_STYLES))
    args = ap.parse_args()

    rng = random.Random(args.seed or time.time_ns())
    if args.reciter != "random" and args.reciter not in RECITERS:
        sys.exit(f"unknown reciter {args.reciter}; choose from {', '.join(RECITERS)}")

    os.makedirs(args.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="qr_")
    try:
        history = load_history(args.history)
        fixed = None
        if args.surah:
            st = args.start or 1
            en = args.end or (st if args.start else AYAH_COUNTS[args.surah - 1])
            match = [p for p in PASSAGES if p[:3] == (args.surah, st, en)]
            fixed = match[0] if match else (args.surah, st, en, "", None)
        p, title, rk, verses, _ = choose(rng, history, args.reciter, tmp, args.max_sec, fixed)
        reciter_ar = RECITERS[rk][1]

        bg_dir = os.path.join(HERE, "backgrounds")
        photos = [os.path.join(bg_dir, f) for f in sorted(os.listdir(bg_dir))
                  if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))] if os.path.isdir(bg_dir) else []
        animate, bg_style = False, None
        if photos and not args.bg_style:
            bgfile = pick_photo(photos, history)
            theme = theme_for(bgfile)
            bg_style, animate = "photo: " + os.path.basename(bgfile), True
        else:
            bgfile = os.path.join(tmp, "bg.jpg")
            bg_style, theme = bgstyles.make_themed(rng, bgfile, args.bg_style or None)

        mp4 = os.path.join(args.out, "reel.mp4")
        total = render(verses, title, bgfile, theme, reciter_ar, args.handle, mp4, tmp, animate)
        with open(os.path.join(args.out, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(caption(verses, title, reciter_ar, args.hashtags, p[4] if len(p) > 4 else None))
        meta = {"date": datetime.date.today().isoformat(), "surah": p[0], "start": p[1], "end": p[2],
                "title": title, "reciter": rk, "background": bg_style, "seconds": round(total, 2)}
        with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        if not args.surah and args.history:
            with open(args.history, "w", encoding="utf-8") as f:
                json.dump(history + [meta], f, ensure_ascii=False, indent=1)
        print(json.dumps(meta, ensure_ascii=False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
