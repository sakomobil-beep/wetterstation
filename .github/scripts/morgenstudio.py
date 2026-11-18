#!/usr/bin/env python3
"""Morgenmagazin-Studio für das Morgenvideo mit Max (18.11.2026, Entwurf D – von Kingman gewählt; überarbeitet 18.11.2026 abends).
Kontrastreiches Studio wie im Frühstücksfernsehen: dunkelgraue Rückwand (Anthrazit, Kingmans Wahl A) mit weißen Lichtleisten, Deckenscheinwerfer, Pflanzen,
große LED-Wand, orange Logo „GUTEN MORGEN, ODENWALD!“ und weiß-oranger Stehtisch „ODENWALD AM MORGEN“ mit Kaffeebecher.
LED-Wand: Kingmans gemalte Odenwald-Bilder passend zum Wetter, ganz auf die Wand eingepasst, mit eigenen Wetter-Effekten
(Regen, Schnee, Nebel, Sturm, Gewitter, Frost); die Wetterhinweise (Tafeln) erscheinen ebenfalls auf der LED-Wand.
Max zieht sich im Studio nicht nach Wetter um – Outfit siehe OUTFITS (im Advent die Weihnachtspullis).
  basis(weihnacht)        -> Studio ohne Wandinhalt (RGBA, W x H)
  wand(bild, fx, t, p)    -> (Bild der LED-Wand, Maske, Position) – Wetterbild mit Effekten und langsamer Kamerafahrt
  tisch()                 -> Stehtisch als Vordergrund (RGBA, verdeckt Max' Beine), Dampf-Position TASSE"""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

W, H = 720, 1280
WAND = (34, 196, 686, 650)        # LED-Wand
TISCH = 940                       # Oberkante Stehtisch
TASSE = (470, TISCH - 76)         # Dampf über dem Kaffeebecher
ORANGE = (255, 132, 24)
NAVY = (16, 28, 58)
_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_R = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def _f(n, bold=True):
    from PIL import ImageFont
    return ImageFont.truetype(_B if bold else _R, n)


def _verlauf(w, h, a, b):
    g = Image.new('RGB', (w, h)); d = ImageDraw.Draw(g)
    for y in range(h):
        q = y / h; d.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * q) for i in range(3)))
    return g


def _pflanze(d, x, y, s=1.0):
    d.rounded_rectangle([x - 34 * s, y - 70 * s, x + 34 * s, y], radius=10, fill=(245, 245, 245), outline=(30, 30, 40), width=3)
    r = random.Random(int(x))
    for k in range(9):
        a = math.radians(-160 + k * 18 + r.uniform(-6, 6)); l = r.uniform(90, 150) * s
        ex, ey = x + math.cos(a) * l, y - 70 * s + math.sin(a) * l
        d.line([(x, y - 70 * s), (ex, ey)], fill=(40, 130, 70), width=max(2, int(5 * s)))
        d.ellipse([ex - 16 * s, ey - 9 * s, ex + 16 * s, ey + 9 * s], fill=(70, 175, 95), outline=(25, 90, 50), width=2)


def basis(weihnacht=False):
    fr = _verlauf(W, H, (28, 30, 34), (62, 64, 70)).convert('RGBA')       # dunkelgraue Rückwand (Anthrazit)
    d = ImageDraw.Draw(fr)
    for x in (12, W - 12):                                                 # senkrechte Lichtleisten
        d.rounded_rectangle([x - 5, 180, x + 5, 1000], radius=5, fill=(235, 235, 240))
    gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(gl)
    for x in (12, W - 12): gd.rounded_rectangle([x - 22, 170, x + 22, 1010], radius=20, fill=(235, 235, 240, 60))
    gd.ellipse([W / 2 - 360, 120, W / 2 + 360, 520], fill=(255, 150, 60, 46))    # warmer Morgen-Schein hinter der Wand
    fr.alpha_composite(gl.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(fr)
    fl = _verlauf(W, H - 1000, (44, 48, 62), (20, 22, 30)).convert('RGBA')   # glänzender dunkler Boden
    fr.paste(fl, (0, 1000))
    d.line([(0, 1000), (W, 1000)], fill=ORANGE, width=4)
    for k in range(7):                                                     # Deckenscheinwerfer
        x = 50 + k * 105; d.ellipse([x - 15, 174, x + 15, 192], fill=(255, 250, 235)); d.line([(x, 166), (x, 176)], fill=(140, 140, 150), width=4)
    lk = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(lk)
    for k in range(7):
        x = 50 + k * 105; ld.polygon([(x - 14, 190), (x + 14, 190), (x + 70, 1000), (x - 70, 1000)], fill=(255, 245, 220, 16))
    fr.alpha_composite(lk.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(fr)
    x0, y0, x1, y1 = WAND
    d.rounded_rectangle([x0 - 9, y0 - 9, x1 + 9, y1 + 9], radius=28, fill=(6, 8, 14), outline=(70, 80, 100), width=2)
    d.rounded_rectangle([370, 672, 704, 732], radius=30, fill=ORANGE)                      # Logo
    d.text((537, 701), 'GUTEN MORGEN, ODENWALD!', font=_f(18), fill=(255, 255, 255), anchor='mm')
    _pflanze(d, 655, 1000, 1.0); _pflanze(d, 30, 1000, 0.7)
    if weihnacht:   # Advent: Lichterkette über der Wand, kleiner Baum rechts
        r = random.Random(7)
        for k in range(26):
            x = x0 + 10 + k * (x1 - x0 - 20) / 25; y = y0 - 14 + 8 * math.sin(k * 0.9)
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=r.choice([(255, 80, 80), (255, 210, 80), (120, 200, 255), (130, 230, 130)]))
        tx, ty = 600, 1000
        for i, (bw, hh) in enumerate(((90, 110), (70, 95), (48, 80))):
            yb = ty - 40 - i * 70; d.polygon([(tx - bw, yb), (tx + bw, yb), (tx, yb - hh)], fill=(30, 120, 60), outline=(20, 70, 40))
        d.rectangle([tx - 12, ty - 40, tx + 12, ty], fill=(110, 70, 40))
        d.polygon([(tx, ty - 262), (tx + 9, ty - 244), (tx - 9, ty - 244)], fill=(255, 210, 60))
        for k in range(14):
            d.ellipse([tx - 70 + r.uniform(0, 140) - 5, ty - 220 + k * 13 - 5, tx - 70 + r.uniform(0, 140) + 5, ty - 220 + k * 13 + 5], fill=r.choice([(220, 40, 40), (255, 210, 60), (240, 240, 250)]))
    return fr


_C = {}


def _maske():
    if 'm' not in _C:
        x0, y0, x1, y1 = WAND; w, h = x1 - x0, y1 - y0
        m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w, h], radius=22, fill=255)
        r = Image.new('RGBA', (w, h), (0, 0, 0, 0)); rd = ImageDraw.Draw(r)
        for x in range(0, w, 4): rd.line([(x, 0), (x, h)], fill=(0, 0, 0, 7))
        for y in range(0, h, 4): rd.line([(0, y), (w, y)], fill=(0, 0, 0, 7))
        rnd = random.Random(2)
        _C.update(m=m, raster=r, tropfen=[(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(10, 20)) for _ in range(90)],
                  flocken=[(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(2, 4.5), rnd.uniform(0, 6)) for _ in range(110)])
    return _C['m'], _C['raster']


def wand(bild, fx=None, t=0.0, p=0.0, dunkel=False):
    """Das Wetterbild ganz auf die LED-Wand eingepasst (füllt die Wand, schneidet nur wenig ab), mit sanfter Kamerafahrt
    und Wetter-Effekten. dunkel=True: abgedunkelt als Hintergrund für eine Tafel."""
    x0, y0, x1, y1 = WAND; w, h = x1 - x0, y1 - y0
    m, raster = _maske()
    key = (id(bild), w, h)
    if key not in _C:
        z = 1.08   # Platz für die Kamerafahrt
        s = max(w * z / bild.width, h * z / bild.height)
        _C[key] = bild.convert('RGB').resize((int(bild.width * s) + 1, int(bild.height * s) + 1), Image.BILINEAR)
    b = _C[key]
    ox = int((b.width - w) * (0.2 + 0.6 * p)); oy = int((b.height - h) * 0.5)
    im = b.crop((ox, oy, ox + w, oy + h)).convert('RGBA')
    d = ImageDraw.Draw(im)
    if fx in ('regen', 'gewitter', 'sturm', 'schauer'):
        schraeg = 160 if fx == 'sturm' else 60
        for (x, y, l) in _C['tropfen']:
            yy = (y + t * 700) % h; xx = (x - t * schraeg) % w
            d.line([xx, yy, xx - 3 - schraeg / 50, yy + l], fill=(215, 228, 245, 190), width=2)
        if fx == 'gewitter' and (t % 2.7) < 0.18:
            im = Image.blend(im, Image.new('RGBA', im.size, (255, 255, 240, 255)), 0.45); d = ImageDraw.Draw(im)
    elif fx == 'schnee':
        for (x, y, r_, ph) in _C['flocken']:
            yy = (y + t * 45 * r_) % h; xx = (x + 14 * math.sin(t + ph)) % w
            d.ellipse([xx - r_, yy - r_, xx + r_, yy + r_], fill=(255, 255, 255, 230))
    elif fx == 'nebel':
        n = Image.new('RGBA', im.size, (0, 0, 0, 0)); nd = ImageDraw.Draw(n)
        for j in range(4):
            yy = 80 + j * 110; xx = ((t * 18 + j * 220) % (w + 400)) - 200
            nd.ellipse([xx - 380, yy - 60, xx + 380, yy + 60], fill=(235, 238, 242, 80))
        im.alpha_composite(n.filter(ImageFilter.GaussianBlur(20)))
    elif fx == 'frost':
        for k, (x, y, r_, ph) in enumerate(_C['flocken'][:40]):
            a_ = int(255 * max(0, math.sin(t * 3 + ph * 2)))
            if a_ > 60: d.line([x - r_ * 2, y, x + r_ * 2, y], fill=(255, 255, 255, a_), width=2); d.line([x, y - r_ * 2, x, y + r_ * 2], fill=(255, 255, 255, a_), width=2)
    if dunkel:
        im = Image.alpha_composite(ImageEnhance.Brightness(im).enhance(0.55).convert('RGBA'), Image.new('RGBA', im.size, (10, 20, 45, 70)))
    im.alpha_composite(raster)
    return im, m, (x0, y0)


def tisch():
    """Stehtisch Variante C (Kingmans Wahl 18.11.2026): warme Holzfront, dunkelblaue Platte, blaues Schild."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); top = TISCH; O = (25, 30, 40, 255)
    d.polygon([(0, top), (560, top), (530, H), (0, H)], fill=(120, 82, 50, 255))
    for k in range(0, 560, 28): d.line([(k, top + 8), (k - 10, H)], fill=(100, 68, 40, 255), width=3)
    d.rectangle([0, top - 20, 590, top + 6], fill=NAVY + (255,))
    d.rounded_rectangle([110, top + 30, 430, top + 140], radius=14, fill=NAVY + (235,))
    d.text((270, top + 66), 'ODENWALD', font=_f(38), fill=ORANGE + (255,), anchor='mm')
    d.text((270, top + 108), 'AM MORGEN', font=_f(28), fill=(235, 240, 250, 255), anchor='mm')
    d.rounded_rectangle([444, top - 74, 496, top - 22], radius=6, fill=(255, 255, 255, 255), outline=O, width=3)   # Kaffeebecher
    d.rectangle([446, top - 60, 494, top - 46], fill=ORANGE + (255,))
    d.rounded_rectangle([330, top - 36, 420, top - 22], radius=4, fill=(40, 46, 60, 255))                        # Tablet
    return im


# --- Outfits im Morgenstudio (Kingmans Wahl 18.11.2026: alle vier wechseln täglich; Advent: Weihnachtspullis) ---
OUTFITS = ['jacke', 'sakko', 'polo_orange', 'hemd']
HEMDEN = ['hemd_hellblau', 'pulli_dunkelblau', 'hemd_kariert', 'pulli_bordeaux', 'hemd_weiss', 'pulli_grau', 'pulli_gruen']
_HEMD_FARBE = {'hemd_hellblau': (150, 190, 230), 'hemd_kariert': (180, 60, 60), 'hemd_weiss': (240, 242, 245),
               'pulli_dunkelblau': (35, 55, 95), 'pulli_bordeaux': (120, 30, 45), 'pulli_grau': (120, 125, 130), 'pulli_gruen': (60, 95, 70)}


def outfit_fuer(heute):
    """Outfit des Tages: None = türkise Max-Jacke, sonst Name eines Musters (sakko, polo_orange oder ein Hemd/Pulli)."""
    o = OUTFITS[heute.toordinal() % len(OUTFITS)]
    if o == 'jacke': return None
    if o == 'hemd': return HEMDEN[(heute.toordinal() // len(OUTFITS)) % len(HEMDEN)]
    return o


def muster(name, V):
    PX0, PX1, PY0, PY1 = V._PX0, V._PX1, V._PY0, V._PY1; cx = (PX0 + PX1) // 2
    if name == 'polo_orange':
        p = Image.new('RGBA', (380, 760), (245, 128, 30, 255)); d = ImageDraw.Draw(p)
        d.rectangle([cx - 14, PY0, cx + 14, PY0 + 110], fill=(225, 105, 15))
        for y in (PY0 + 30, PY0 + 70): d.ellipse([cx - 5, y - 5, cx + 5, y + 5], fill=(255, 255, 255))
        d.rectangle([0, PY1 - 22, 380, PY1], fill=NAVY)
        d.rounded_rectangle([PX0 + 28, PY0 + 70, PX0 + 92, PY0 + 98], radius=6, fill=NAVY)
        d.text((PX0 + 60, PY0 + 84), 'GMO', font=_f(16), fill=(255, 255, 255), anchor='mm')
        return p
    if name == 'sakko':
        p = Image.new('RGBA', (380, 760), (28, 40, 78, 255)); d = ImageDraw.Draw(p)
        d.polygon([(cx - 55, PY0 - 40), (cx + 55, PY0 - 40), (cx, PY0 + 170)], fill=(245, 247, 250))
        d.polygon([(cx - 9, PY0 + 5), (cx + 9, PY0 + 5), (cx + 14, PY0 + 130), (cx, PY0 + 150), (cx - 14, PY0 + 130)], fill=ORANGE)
        d.line([(cx - 55, PY0 - 40), (cx - 8, PY0 + 175)], fill=(14, 22, 48), width=5); d.line([(cx + 55, PY0 - 40), (cx + 8, PY0 + 175)], fill=(14, 22, 48), width=5)
        for y in (PY0 + 200, PY0 + 250): d.ellipse([cx + 10, y - 6, cx + 22, y + 6], fill=(10, 16, 36))
        d.rectangle([PX0 + 26, PY0 + 90, PX0 + 80, PY0 + 96], fill=(14, 22, 48))
        return p
    g = _HEMD_FARBE[name]; p = Image.new('RGBA', (380, 760), g + (255,)); d = ImageDraw.Draw(p)
    if name == 'hemd_kariert':
        for x in range(0, 380, 26): d.rectangle([x, 0, x + 9, 760], fill=(140, 40, 45))
        for y in range(0, 760, 26): d.rectangle([0, y, 380, y + 9], fill=(150, 45, 50))
        for x in range(13, 380, 26): d.line([(x, 0), (x, 760)], fill=(235, 220, 200), width=2)
    if name.startswith('hemd'):
        d.line([(cx, PY0), (cx, PY1)], fill=tuple(max(0, c - 50) for c in g), width=3)
        for y in range(PY0 + 30, PY1, 42): d.ellipse([cx - 5, y - 5, cx + 5, y + 5], fill=(250, 250, 250), outline=(90, 90, 90))
        d.rectangle([PX0 + 30, PY0 + 70, PX0 + 85, PY0 + 120], outline=tuple(max(0, c - 50) for c in g), width=3)
    else:
        for y in range(PY0, PY1, 10): d.line([(0, y), (380, y)], fill=tuple(max(0, c - 14) for c in g), width=2)
        d.rectangle([0, PY1 - 26, 380, PY1], fill=tuple(max(0, c - 25) for c in g))
    return p


def anziehen_voll(V):
    """Liefert eine Anzieh-Funktion, die auch die Ärmel (erhobener Arm beim Winken/Zeigen) mit umfärbt."""
    import numpy as np
    def f(im, name):
        a = np.array(im); r_, g_, b_ = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int); al = a[:, :, 3] > 200
        tuerkis = (g_ - r_ > 35) & (b_ - r_ > 25)
        futter = (abs(r_ - 58) <= 6) & (abs(g_ - 68) <= 6) & (abs(b_ - 83) <= 6)
        schild = (r_ > 225) & (g_ > 225) & (b_ > 225); schild[:V._PY0 + 30, :] = False; schild[V._PY1 + 30:, :] = False
        m_ = (tuerkis | futter | schild) & al
        M = Image.fromarray((m_ * 255).astype('uint8')).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
        inner = Image.fromarray((al * 255).astype('uint8')).filter(ImageFilter.MinFilter(9))
        M = Image.fromarray(np.minimum(np.array(M), np.array(inner)))
        out = im.copy(); out.paste(V.pulli_muster(name), (0, 0), M); return out
    return f
