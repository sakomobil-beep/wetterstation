#!/usr/bin/env python3
"""Morgenmagazin-Studio für das Morgenvideo mit Max (18.11.2026, Entwurf D – von Kingman gewählt).
Helles, modernes Studio wie im Frühstücksfernsehen: Deckenscheinwerfer, Pflanzen, große LED-Wand,
orange Logo „GUTEN MORGEN, ODENWALD!“ und weiß-oranger Stehtisch „ODENWALD AM MORGEN“ mit Kaffeebecher.
Auf der LED-Wand läuft das Wetter des Tages: dasselbe Bild samt Regen/Schnee/Nebel-Effekten, das früher
draußen hinter Max stand (Kingmans gemalte Odenwald-Bilder). Max steht hinter dem Stehtisch.
  basis(weihnacht)  -> Studio ohne Wandinhalt (RGBA, W x H)
  wand(fr_draussen) -> fertiges Bild der LED-Wand aus dem bisherigen Draußen-Bild
  tisch()           -> Stehtisch als Vordergrund (RGBA, verdeckt Max' Beine), Tassen-Position TASSE"""
import math, random
from PIL import Image, ImageDraw, ImageFilter

W, H = 720, 1280
WAND = (40, 200, 680, 640)        # LED-Wand
TISCH = 930                       # Oberkante Stehtisch
TASSE = (470, TISCH - 76)         # Dampf über dem Kaffeebecher
ORANGE = (255, 140, 40)
_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_R = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def _f(n, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(_B if bold else _R, n)


def _verlauf(a, b):
    g = Image.new('RGB', (W, H)); d = ImageDraw.Draw(g)
    for y in range(H):
        q = y / H; d.line([(0, y), (W, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * q) for i in range(3)))
    return g


def _pflanze(d, x, y, s=1.0):
    d.rounded_rectangle([x - 34 * s, y - 70 * s, x + 34 * s, y], radius=10, fill=(245, 245, 245), outline=(60, 60, 70), width=3)
    r = random.Random(int(x))
    for k in range(9):
        a = math.radians(-160 + k * 18 + r.uniform(-6, 6)); l = r.uniform(90, 150) * s
        ex, ey = x + math.cos(a) * l, y - 70 * s + math.sin(a) * l
        d.line([(x, y - 70 * s), (ex, ey)], fill=(46, 120, 70), width=max(2, int(5 * s)))
        d.ellipse([ex - 16 * s, ey - 9 * s, ex + 16 * s, ey + 9 * s], fill=(70, 160, 90), outline=(40, 100, 60), width=2)


def basis(weihnacht=False):
    fr = _verlauf((214, 232, 250), (250, 246, 238)).convert('RGBA')
    d = ImageDraw.Draw(fr)
    d.rectangle([0, 1000, W, H], fill=(228, 222, 214))                        # heller Boden
    for k in range(7):                                                         # Deckenscheinwerfer
        x = 50 + k * 105; d.ellipse([x - 16, 176, x + 16, 196], fill=(250, 250, 245)); d.line([(x, 168), (x, 178)], fill=(80, 80, 90), width=4)
    lk = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(lk)
    for k in range(7):
        x = 50 + k * 105; ld.polygon([(x - 14, 192), (x + 14, 192), (x + 90, 900), (x - 90, 900)], fill=(255, 250, 230, 20))
    fr.alpha_composite(lk.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(fr)
    x0, y0, x1, y1 = WAND
    d.rounded_rectangle([x0 - 8, y0 - 8, x1 + 8, y1 + 8], radius=28, fill=(40, 46, 60))   # Rahmen der LED-Wand
    d.rounded_rectangle([380, 668, 700, 728], radius=30, fill=ORANGE)                       # Logo
    d.text((540, 697), 'GUTEN MORGEN, ODENWALD!', font=_f(20), fill=(255, 255, 255), anchor='mm')
    _pflanze(d, 650, 1000, 1.0); _pflanze(d, 30, 1000, 0.7)
    if weihnacht:   # Advent: Lichterkette über der Wand, kleiner Baum rechts
        r = random.Random(7)
        for k in range(26):
            x = x0 + 10 + k * (x1 - x0 - 20) / 25; y = y0 - 14 + 8 * math.sin(k * 0.9)
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=r.choice([(255, 80, 80), (255, 210, 80), (120, 200, 255), (130, 230, 130)]))
        tx, ty = 600, 1000
        for i, (bw, hh) in enumerate(((90, 110), (70, 95), (48, 80))):
            yb = ty - 40 - i * 70; d.polygon([(tx - bw, yb), (tx + bw, yb), (tx, yb - hh)], fill=(30, 110, 60), outline=(20, 70, 40))
        d.rectangle([tx - 12, ty - 40, tx + 12, ty], fill=(110, 70, 40))
        d.polygon([(tx, ty - 262), (tx + 9, ty - 244), (tx - 9, ty - 244)], fill=(255, 210, 60))
        for k in range(14):
            d.ellipse([tx - 70 + r.uniform(0, 140) - 5, ty - 220 + k * 13 - 5, tx - 70 + r.uniform(0, 140) + 5, ty - 220 + k * 13 + 5], fill=r.choice([(220, 40, 40), (255, 210, 60), (240, 240, 250)]))
    return fr


_MASKE = []


def wand(fr_draussen):
    """Das bisherige Draußen-Bild (mit Wetter-Effekten) verkleinert auf die LED-Wand, mit feinem LED-Raster."""
    x0, y0, x1, y1 = WAND; w, h = x1 - x0, y1 - y0
    src = fr_draussen.convert('RGBA')
    s = max(w / src.width, h / src.height)
    b = src.resize((int(src.width * s) + 1, int(src.height * s) + 1), Image.BILINEAR)
    oy = int((b.height - h) * 0.45)   # oberer Bildteil (Himmel, Landschaft) – unten stand früher der Weg
    b = b.crop(((b.width - w) // 2, oy, (b.width - w) // 2 + w, oy + h))
    if not _MASKE:
        m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w, h], radius=22, fill=255)
        r = Image.new('RGBA', (w, h), (0, 0, 0, 0)); rd = ImageDraw.Draw(r)
        for x in range(0, w, 4): rd.line([(x, 0), (x, h)], fill=(0, 0, 0, 7))
        for y in range(0, h, 4): rd.line([(0, y), (w, y)], fill=(0, 0, 0, 7))
        _MASKE.extend([m, r])
    b.alpha_composite(_MASKE[1])
    return b, _MASKE[0], (x0, y0)


def tisch():
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); top = TISCH
    d.polygon([(0, top), (560, top), (530, H), (0, H)], fill=(250, 250, 252, 255), outline=(60, 64, 80, 255))
    d.rectangle([0, top - 22, 590, top + 6], fill=ORANGE + (255,))
    d.text((270, top + 62), 'ODENWALD', font=_f(40), fill=ORANGE + (255,), anchor='mm')
    d.text((270, top + 106), 'AM MORGEN', font=_f(30), fill=(70, 80, 100, 255), anchor='mm')
    O = (25, 30, 40, 255)
    d.rounded_rectangle([444, top - 74, 496, top - 22], radius=6, fill=(255, 255, 255, 255), outline=O, width=3)   # Kaffeebecher
    d.rectangle([446, top - 60, 494, top - 46], fill=ORANGE + (255,))
    d.rounded_rectangle([330, top - 36, 420, top - 22], radius=4, fill=(40, 46, 60, 255))                        # Tablet
    return im
