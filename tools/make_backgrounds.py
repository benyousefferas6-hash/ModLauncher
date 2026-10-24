"""Generates the original blocky pixel-art backgrounds in assets/backgrounds (run: python tools/make_backgrounds.py)."""
import math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

W, H, C = 480, 270, 6
GW, GH = W // C, H // C
OUT = Path(__file__).resolve().parent.parent / "assets" / "backgrounds"


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sky(d, top, bot, steps=16):
    for i in range(steps):
        y0, y1 = i * H // steps, (i + 1) * H // steps
        d.rectangle([0, y0, W, y1], fill=lerp(top, bot, i / (steps - 1)))


def block(d, gx, gy, col, r):
    x, y = gx * C, gy * C
    d.rectangle([x, y, x + C - 1, y + C - 1], fill=col)
    for _ in range(3):
        sx, sy = x + r.randrange(0, C, 2), y + r.randrange(0, C, 2)
        d.rectangle([sx, sy, sx + 1, sy + 1], fill=shade(col, r.choice((0.86, 0.93, 1.08, 1.14))))


def heights(r, base=0.64, amp=3.0):
    ph = r.random() * 6
    return [int(GH * base + amp * math.sin(g * 0.17 + ph) + 2 * math.sin(g * 0.06 + ph * 2) + r.choice((0, 0, 1)))
            for g in range(GW)]


def terrain(d, r, hs, grass, dirt, stone, trees=True, leaf=(58, 140, 52), log=(102, 78, 46)):
    for gx, top in enumerate(hs):
        for gy in range(top, GH):
            col = grass if gy == top else dirt if gy < top + 4 else stone
            if col == stone and r.random() < 0.022:
                col = r.choice([(40, 40, 44), (190, 160, 130), (110, 200, 215)])
            block(d, gx, gy, col, r)
    if trees:
        gx = 4
        while gx < GW - 4:
            top = hs[gx]
            for dy, wd in ((5, 2), (4, 2), (6, 1), (7, 1)):
                for dx in range(-wd, wd + 1):
                    block(d, gx + dx, top - dy, leaf, r)
            for dy in range(1, 5):
                block(d, gx, top - dy, log, r)
            gx += r.randint(8, 15)


def clouds(img, r, n=6, alpha=215):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for _ in range(n):
        gx, gy, wd = r.randint(0, GW - 10), r.randint(2, 11), r.randint(5, 10)
        for row in range(2):
            off = r.randint(0, 2)
            d.rectangle([(gx + off) * C, (gy + row) * C, (gx + wd - off) * C, (gy + row + 1) * C - 1], fill=(255, 255, 255, alpha))
    img.alpha_composite(ov)


def glow(img, cx, cy, rad, col, alpha=130):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ov).ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col + (alpha,))
    img.alpha_composite(ov.filter(ImageFilter.GaussianBlur(rad / 2.2)))


def save(img, name):
    img.convert("RGB").resize((W * 4, H * 4), Image.NEAREST).save(OUT / f"{name}.png", optimize=True)
    print("wrote", name)


def plains_day():
    r = random.Random(7)
    img = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(img)
    sky(d, (96, 165, 235), (190, 225, 250))
    glow(img, 380, 40, 70, (255, 240, 170), 120); d = ImageDraw.Draw(img)
    d.rectangle([368, 28, 392, 52], fill=(255, 248, 200))
    clouds(img, r); d = ImageDraw.Draw(img)
    terrain(d, r, heights(r), (96, 170, 60), (134, 96, 67), (125, 125, 128))
    save(img, "plains_day")


def sunset_hills():
    r = random.Random(21)
    img = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(img)
    sky(d, (70, 50, 110), (250, 150, 80), 20)
    glow(img, 150, 170, 110, (255, 190, 90), 150); d = ImageDraw.Draw(img)
    d.rectangle([138, 150, 168, 180], fill=(255, 225, 130))
    clouds(img, r, 5, 120); d = ImageDraw.Draw(img)
    terrain(d, r, heights(r, 0.68, 4), (52, 110, 62), (88, 62, 52), (76, 76, 92), leaf=(36, 92, 50), log=(70, 52, 40))
    save(img, "sunset_hills")


def starry_night():
    r = random.Random(33)
    img = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(img)
    sky(d, (8, 12, 36), (28, 42, 86), 14)
    for _ in range(140):
        x, y = r.randrange(W), r.randrange(int(H * 0.6))
        d.rectangle([x, y, x + r.choice((0, 1)), y + r.choice((0, 1))], fill=r.choice(((255, 255, 255), (200, 215, 255))))
    glow(img, 360, 48, 60, (200, 215, 255), 80); d = ImageDraw.Draw(img)
    d.rectangle([350, 38, 372, 60], fill=(232, 236, 248)); d.rectangle([356, 44, 360, 48], fill=(200, 205, 225))
    terrain(d, r, heights(r, 0.66, 3), (34, 78, 66), (58, 46, 52), (52, 56, 72), leaf=(24, 62, 56), log=(50, 40, 40))
    save(img, "starry_night")


def deep_caves():
    r = random.Random(5)
    img = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(img)
    ph = r.random() * 6
    air = set()
    for gx in range(GW):
        for gy in range(GH):
            v = math.sin(gx * 0.21 + ph) + math.cos(gy * 0.33 - ph) + math.sin((gx + gy) * 0.12) + 0.3 * math.sin(gx * 0.5)
            if v > 1.35:
                air.add((gx, gy))
    for gx in range(GW):
        for gy in range(GH):
            if (gx, gy) in air:
                col = (18, 18, 24) if gy < GH - 7 else (240, 110, 20)
            else:
                col = (112, 112, 116) if (gx + gy) % 7 else (100, 100, 105)
                x = r.random()
                col = (36, 36, 40) if x < 0.02 else (205, 170, 140) if x < 0.032 else (120, 210, 225) if x < 0.038 else col
            block(d, gx, gy, col, r)
    walls = [(g, gy) for (g, gy) in air if (g + 1, gy) not in air and gy < GH - 9]
    for gx, gy in r.sample(walls, min(5, len(walls))):
        block(d, gx + 1, gy, (255, 210, 90), r)
        glow(img, gx * C + 9, gy * C + 3, 38, (255, 190, 80), 120); d = ImageDraw.Draw(img)
    save(img, "deep_caves")


def icons():
    s = 256
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, s - 1, s - 1], 56, fill=(22, 24, 28))
    d.polygon([(128, 40), (204, 84), (204, 172), (128, 216), (52, 172), (52, 84)], fill=(27, 217, 106))
    d.polygon([(128, 40), (204, 84), (128, 128), (52, 84)], fill=(108, 240, 164))
    d.polygon([(128, 128), (128, 216), (52, 172), (52, 84)], fill=(20, 168, 80))
    im.save(OUT.parent / "icon.png")
    im.save(OUT.parent / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (plains_day, sunset_hills, starry_night, deep_caves):
        fn()
    icons()
