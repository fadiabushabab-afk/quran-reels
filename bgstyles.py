"""
Islamic background styles, drawn in code (original artwork, no external images).

Styles:
  twilight_mosque  domes and minarets against a dusk sky, crescent and stars
  lanterns         hanging Ramadan lanterns with a warm glow
  gold_frame       ornate gold frame with corner rosettes on a deep background
  geometric        8-pointed star lattice with a mihrab arch (the original style)

The verse text sits in the middle (y ~ 520-1600), so every style keeps that area calm.
"""
import math, random
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
GOLD = (212, 175, 95)


# ---------------------------------------------------------------- helpers

def vgradient(stops):
    """stops: list of (position 0..1, (r,g,b))"""
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= t <= p1:
                k = (t - p0) / (p1 - p0 or 1)
                d.line([(0, y), (W, y)], fill=tuple(int(c0[i] + (c1[i] - c0[i]) * k) for i in range(3)))
                break
    return im.convert("RGBA")


def glow(im, x, y, r, color, alpha):
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([x - r, y - r, x + r, y + r], fill=color + (alpha,))
    return Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(r * 0.6)))


def stars(im, rng, n, y_max, color=(255, 248, 225)):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        x, y = rng.randint(0, W), rng.randint(0, int(y_max))
        r = rng.choice([1, 1, 1, 2, 2, 3])
        d.ellipse([x - r, y - r, x + r, y + r], fill=color + (rng.randint(90, 230),))
    soft = layer.filter(ImageFilter.GaussianBlur(2))
    return Image.alpha_composite(Image.alpha_composite(im, soft), layer)


def crescent(im, cx, cy, r, color=(255, 236, 180)):
    im = glow(im, cx, cy, int(r * 2.2), color, 70)
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    off = r * 0.42
    d.ellipse([cx - r + off, cy - r - off * 0.35, cx + r + off, cy + r - off * 0.35], fill=0)
    solid = Image.new("RGBA", (W, H), color + (255,))
    im.paste(solid, (0, 0), m)
    return im


def vignette(im, strength=255):
    v = Image.new("L", (W, H), 0)
    ImageDraw.Draw(v).ellipse([-320, -220, W + 320, H + 220], fill=strength)
    v = v.filter(ImageFilter.GaussianBlur(170))
    return Image.composite(im, Image.new("RGBA", (W, H), (0, 0, 0, 255)), v)


def text_panel(im, top=500, bottom=1640, alpha=110):
    """Gentle darkening behind the verse text."""
    p = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(p).rounded_rectangle([70, top, W - 70, bottom], radius=60, fill=(0, 0, 0, alpha))
    return Image.alpha_composite(im, p.filter(ImageFilter.GaussianBlur(40)))


def star8(cx, cy, R, r, rot=0.0):
    return [(cx + (R if k % 2 == 0 else r) * math.cos(rot + k * math.pi / 8),
             cy + (R if k % 2 == 0 else r) * math.sin(rot + k * math.pi / 8)) for k in range(16)]


def pointed_arch(x0, x1, y_apex, y_bottom, ratio=0.78, n=60):
    w = x1 - x0
    R = ratio * w
    cx = (x0 + x1) / 2
    th_end = math.acos((w / 2 - R) / R)
    ys = y_apex + R * math.sin(th_end)
    left = [(x0 + R + R * math.cos(th), ys - R * math.sin(th))
            for th in [math.pi - (math.pi - th_end) * i / n for i in range(n + 1)]]
    right = [(2 * cx - x, y) for x, y in left]
    return [(x0, y_bottom)] + left + right[::-1] + [(x1, y_bottom)]


# ---------------------------------------------------------------- mosque silhouette

def dome(d, cx, base_y, w, h, fill):
    """Onion-ish dome with a pointed tip and a small finial."""
    pts = []
    for i in range(41):
        t = i / 40                       # 0 left base -> 1 tip
        x = cx - w / 2 + (w / 2) * t
        bulge = math.sin(math.pi * min(1, t * 1.25)) * 0.12 * w
        y = base_y - h * (1 - (1 - t) ** 2.2)
        pts.append((x - bulge * (1 - t), y))
    pts += [(2 * cx - x, y) for x, y in reversed(pts)]
    d.polygon(pts, fill=fill)
    d.rectangle([cx - w * 0.52, base_y - 4, cx + w * 0.52, base_y + h * 0.18], fill=fill)
    d.line([(cx, base_y - h), (cx, base_y - h - h * 0.28)], fill=fill, width=max(3, int(w * 0.02)))
    r = max(5, int(w * 0.035))
    d.ellipse([cx - r, base_y - h - h * 0.28 - r * 2, cx + r, base_y - h - h * 0.28], fill=fill)


def minaret(d, cx, base_y, height, w, fill):
    d.rectangle([cx - w / 2, base_y - height, cx + w / 2, base_y], fill=fill)
    for f in (0.55, 0.8):                         # balconies
        y = base_y - height * f
        d.rectangle([cx - w * 0.85, y - 10, cx + w * 0.85, y + 6], fill=fill)
    top = base_y - height
    d.polygon([(cx - w * 0.62, top), (cx + w * 0.62, top), (cx, top - w * 2.1)], fill=fill)
    d.line([(cx, top - w * 2.1), (cx, top - w * 2.8)], fill=fill, width=3)


def mosque(d, cx, base_y, scale, fill):
    s = scale
    d.rectangle([cx - 330 * s, base_y - 150 * s, cx + 330 * s, H], fill=fill)
    dome(d, cx, base_y - 150 * s, 330 * s, 250 * s, fill)
    for side in (-1, 1):
        dome(d, cx + side * 215 * s, base_y - 150 * s, 130 * s, 100 * s, fill)
        minaret(d, cx + side * 390 * s, base_y + 10, 640 * s, 46 * s, fill)


def twilight_mosque(rng):
    skies = [
        [(0, (10, 14, 40)), (0.45, (44, 36, 92)), (0.68, (150, 78, 100)), (0.8, (238, 150, 96)), (1, (238, 150, 96))],
        [(0, (4, 10, 30)), (0.5, (16, 40, 90)), (0.7, (44, 100, 140)), (0.8, (110, 170, 185)), (1, (110, 170, 185))],
        [(0, (12, 8, 26)), (0.45, (56, 22, 62)), (0.68, (160, 62, 62)), (0.8, (244, 174, 92)), (1, (244, 174, 92))],
        [(0, (2, 18, 22)), (0.5, (8, 54, 60)), (0.7, (34, 106, 100)), (0.8, (160, 196, 164)), (1, (160, 196, 164))],
    ]
    im = vgradient(rng.choice(skies))
    im = stars(im, rng, 160, H * 0.62)
    side = rng.choice([-1, 1])
    im = crescent(im, W // 2 + side * 300, 400, 60)
    far = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mosque(ImageDraw.Draw(far), W / 2 - side * 260, 1830, 0.7, (0, 0, 0, 110))
    far = far.filter(ImageFilter.GaussianBlur(3))
    im = Image.alpha_composite(im, far)
    near = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    nd = ImageDraw.Draw(near)
    mosque(nd, W / 2 + side * 60, 1960, 1.05, (6, 6, 14, 255))
    im = Image.alpha_composite(im, near)
    im = text_panel(im, 480, 1500, 85)
    return vignette(im)


# ---------------------------------------------------------------- lanterns

def lantern(d, cx, top, w, line_col, body_col, light_col):
    """A fanous: cap, faceted body with windows, base, finial."""
    h = w * 1.9
    d.line([(cx, 0), (cx, top)], fill=line_col, width=3)
    ring = w * 0.09
    d.ellipse([cx - ring, top - ring, cx + ring, top + ring], outline=line_col, width=3)
    cap_top, cap_bot = top + ring, top + h * 0.22
    d.polygon([(cx, cap_top), (cx + w * 0.42, cap_bot), (cx - w * 0.42, cap_bot)], fill=body_col)
    b0, b1 = cap_bot, cap_bot + h * 0.55
    body = [(cx - w * 0.42, b0), (cx + w * 0.42, b0), (cx + w * 0.5, b0 + (b1 - b0) * 0.5),
            (cx + w * 0.42, b1), (cx - w * 0.42, b1), (cx - w * 0.5, b0 + (b1 - b0) * 0.5)]
    d.polygon(body, fill=light_col)
    for fx in (-0.21, 0.21):                     # window bars
        d.line([(cx + w * fx, b0), (cx + w * fx, b1)], fill=body_col, width=max(3, int(w * 0.05)))
    d.line([(cx - w * 0.5, (b0 + b1) / 2), (cx + w * 0.5, (b0 + b1) / 2)], fill=body_col, width=max(3, int(w * 0.04)))
    d.polygon(body, outline=body_col, width=max(3, int(w * 0.05)))
    base = b1 + h * 0.13
    d.polygon([(cx - w * 0.42, b1), (cx + w * 0.42, b1), (cx + w * 0.2, base), (cx - w * 0.2, base)], fill=body_col)
    d.line([(cx, base), (cx, base + h * 0.1)], fill=body_col, width=3)
    return (cx, (b0 + b1) / 2, h)


def lanterns(rng):
    bgs = [
        [(0, (4, 12, 32)), (0.5, (10, 30, 62)), (1, (4, 10, 26))],     # navy
        [(0, (2, 22, 16)), (0.5, (8, 50, 38)), (1, (2, 18, 12))],      # emerald
        [(0, (20, 6, 14)), (0.5, (52, 16, 34)), (1, (16, 4, 10))],     # plum
    ]
    im = vgradient(rng.choice(bgs))
    im = stars(im, rng, 110, H)
    spots = []
    for side in (-1, 1):
        # keep clear of the centred header (x ~ 270..810)
        for off, top_rng, w_rng in ((430, (90, 380), (85, 110)), (335, (70, 200), (70, 90))):
            spots.append((W / 2 + side * off, rng.randint(*top_rng), rng.randint(*w_rng)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    centres = []
    for x, top, w in spots:
        centres.append(lantern(ld, x, top, w, GOLD + (220,), (150, 112, 52, 255), (255, 190, 90, 255)))
    for cx, cy, h in centres:                     # warm glow behind each lantern
        im = glow(im, cx, cy, int(h * 0.9), (255, 170, 70), 120)
    im = Image.alpha_composite(im, layer)
    im = text_panel(im, 600, 1640, 80)
    return vignette(im)


# ---------------------------------------------------------------- gold frame

def rosette(d, cx, cy, R, col):
    d.polygon(star8(cx, cy, R, R * 0.55), outline=col, width=3)
    d.polygon(star8(cx, cy, R * 0.55, R * 0.32, math.pi / 8), outline=col, width=2)
    d.ellipse([cx - R * 0.16, cy - R * 0.16, cx + R * 0.16, cy + R * 0.16], fill=col)


def gold_frame(rng):
    bgs = [((6, 34, 26), (12, 62, 46)), ((8, 18, 42), (18, 40, 80)),
           ((34, 8, 14), (70, 18, 30)), ((14, 14, 16), (40, 36, 30))]
    dark, light = rng.choice(bgs)
    im = vgradient([(0, dark), (0.45, light), (1, dark)])
    # faint lattice outside the frame
    pat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pat)
    T = 135
    for gy in range(0, H + T, T):
        for gx in range(0, W + T, T):
            pd.polygon(star8(gx, gy, T * 0.5, T * 0.27), outline=GOLD + (34,), width=2)
    im = Image.alpha_composite(im, pat)
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fr)
    x0, y0, x1, y1 = 60, 420, W - 60, H - 290
    d.rectangle([x0, y0, x1, y1], fill=dark + (215,))
    gold = GOLD + (235,)
    d.rectangle([x0, y0, x1, y1], outline=gold, width=5)
    d.rectangle([x0 + 18, y0 + 18, x1 - 18, y1 - 18], outline=GOLD + (140,), width=2)
    # crest arch above the frame's top edge
    crest = pointed_arch(W / 2 - 150, W / 2 + 150, y0 - 105, y0)
    d.polygon(crest, fill=dark + (235,))
    d.line(crest, fill=gold, width=5)
    rosette(d, W / 2, y0 - 32, 38, gold)
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        d.ellipse([cx - 58, cy - 58, cx + 58, cy + 58], fill=dark + (255,))
        rosette(d, cx, cy, 54, gold)
    for cx, cy in ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), (W / 2, y1)):
        q = 22
        d.polygon([(cx, cy - q), (cx + q, cy), (cx, cy + q), (cx - q, cy)], fill=gold)
    im = Image.alpha_composite(im, fr)
    return vignette(im)


# ---------------------------------------------------------------- geometric (original)

PALETTES = [((6, 38, 28), (14, 70, 52), GOLD), ((8, 20, 46), (20, 46, 92), GOLD),
            ((40, 10, 18), (82, 24, 36), (222, 186, 110)), ((5, 44, 48), (12, 84, 88), (236, 222, 186)),
            ((22, 16, 10), (58, 42, 26), GOLD)]


def geometric(rng):
    dark, light, line = rng.choice(PALETTES)
    im = vgradient([(0, dark), (0.45, light), (1, dark)])
    pat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(pat)
    T = rng.choice([150, 170, 190])
    off = rng.randint(0, T)
    for gy in range(-T, H + T, T):
        for gx in range(-T, W + T, T):
            cx, cy = gx + off, gy + off
            g.polygon(star8(cx, cy, T * 0.5, T * 0.27), outline=line + (70,), width=3)
            g.polygon(star8(cx, cy, T * 0.26, T * 0.16, math.pi / 8), outline=line + (45,), width=2)
            qx, qy, q = cx + T / 2, cy + T / 2, T * 0.17
            g.polygon([(qx, qy - q), (qx + q, qy), (qx, qy + q), (qx - q, qy)], outline=line + (55,), width=2)
    im = Image.alpha_composite(im, pat)
    arch = pointed_arch(90, W - 90, 330, 1640)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(arch, fill=dark + (205,))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(6)))
    bd = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bdd = ImageDraw.Draw(bd)
    bdd.line(arch + [arch[0]], fill=line + (190,), width=4)
    inner = pointed_arch(112, W - 112, 362, 1618)
    bdd.line(inner + [inner[0]], fill=line + (90,), width=2)
    im = Image.alpha_composite(im, bd)
    return vignette(im)


STYLES = {
    "twilight_mosque": twilight_mosque,
    "lanterns": lanterns,
    "gold_frame": gold_frame,
    "geometric": geometric,
}


def make(rng, dest, style=None):
    name = style or rng.choice(list(STYLES))
    STYLES[name](rng).convert("RGB").save(dest, quality=95)
    return name
