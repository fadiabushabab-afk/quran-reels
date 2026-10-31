"""
Gentle, seamlessly looping motion for a still background image:
  - slow camera drift / breathing zoom
  - dust motes drifting in the light (only visible where the image is bright)
  - light that softly brightens and dims
Every motion has period LOOP seconds, so the clip loops without a jump.

Usage as a module:  make_motion_video(image_path, seconds, out_mp4)
Command line:       python motion.py image.jpg out.mp4 [seconds]
"""
import math, random, subprocess, sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

W, H, FPS = 1080, 1920, 30
LOOP = 12.0                 # seconds; all motion repeats exactly every LOOP seconds
OVERSCAN = 1.10             # image is prepared slightly larger than the frame for drift


def _prepare(path):
    im = Image.open(path).convert("RGB")
    tw, th = int(W * OVERSCAN), int(H * OVERSCAN)
    s = max(tw / im.width, th / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    l, t = (im.width - tw) // 2, (im.height - th) // 2
    return im.crop((l, t, l + tw, t + th))


def _sprite(r):
    """Soft round dust mote."""
    size = r * 6
    sp = Image.new("L", (size, size), 0)
    ImageDraw.Draw(sp).ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], fill=255)
    return sp.filter(ImageFilter.GaussianBlur(r * 0.9))


def make_motion_video(image_path, seconds, out_mp4, seed=1, n_motes=220, crf=20):
    rng = random.Random(seed)
    base = _prepare(image_path)
    bw, bh = base.size
    # brightness map decides where dust is visible (sunbeams)
    lum = base.convert("L").filter(ImageFilter.GaussianBlur(12))
    lum = lum.point(lambda v: max(0, min(255, int((v - 60) * 3.0))))
    # a slightly brighter, warmer version for the "breathing light"
    bright = ImageEnhance.Brightness(base).enhance(1.12)
    bright = Image.blend(bright, Image.new("RGB", base.size, (255, 214, 150)), 0.06)
    light_mask = base.convert("L").point(lambda v: int(max(0, v - 90) * 1.6)).filter(ImageFilter.GaussianBlur(20))

    sprites = {r: _sprite(r) for r in (2, 3, 4, 6)}
    motes = []
    for _ in range(n_motes):
        r = rng.choice([2, 2, 2, 3, 3, 4, 6])
        motes.append({
            "x": rng.uniform(0, bw), "y": rng.uniform(0, bh), "r": r,
            "dir": rng.choice([-1, -1, 1]),                                  # mostly drifting upward
            "ax": rng.uniform(10, 45), "kx": rng.choice([1, 2]), "ph": rng.uniform(0, 2 * math.pi),
            "tw": rng.choice([1, 2, 3]), "tph": rng.uniform(0, 2 * math.pi),
            "a": rng.uniform(0.35, 0.95),
        })

    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_mp4],
        stdin=subprocess.PIPE)
    n = int(round(seconds * FPS))
    for f in range(n):
        t = f / FPS
        ph = 2 * math.pi * (t % LOOP) / LOOP
        # breathing light
        k = 0.5 + 0.5 * math.sin(ph)
        frame = Image.composite(bright, base, light_mask.point(lambda v, k=k: int(v * k * 0.55)))
        # dust motes (positions are periodic in LOOP)
        dust = Image.new("L", (bw, bh), 0)
        for m in motes:
            y = (m["y"] + m["dir"] * bh * (t % LOOP) / LOOP) % bh
            x = (m["x"] + m["ax"] * math.sin(m["kx"] * ph + m["ph"])) % bw
            a = m["a"] * (0.55 + 0.45 * math.sin(m["tw"] * ph + m["tph"]))
            sp = sprites[m["r"]]
            dust.paste(int(255 * a), (int(x - sp.width / 2), int(y - sp.height / 2)), sp)
        dust = ImageChops.multiply(dust, lum)
        frame = Image.composite(Image.new("RGB", frame.size, (255, 238, 205)), frame, dust)
        # slow drift and breathing zoom
        z = 1.0 + 0.025 * (0.5 - 0.5 * math.cos(ph))
        cw, ch = (bw / OVERSCAN) / z, (bh / OVERSCAN) / z
        cx = bw / 2 + (bw - cw) * 0.30 * math.sin(ph)
        cy = bh / 2 + (bh - ch) * 0.20 * math.sin(2 * ph)
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        frame = frame.resize((W, H), Image.BILINEAR, box=box)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed while writing motion background")
    return out_mp4


if __name__ == "__main__":
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else LOOP
    make_motion_video(sys.argv[1], secs, sys.argv[2])
