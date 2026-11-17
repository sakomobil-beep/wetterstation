#!/usr/bin/env python3
"""Weihnachtsdeko für Max' Studio (Abendvideo, Wochenausblick, Monats-/Jahresrückblick), 23.11.–27.12. – Variante B „Festlich“
(von Kingman am 17.11.2026 ausgewählt): bunte Lichterkette rund um den Bildschirm, Tannengirlande mit roten Schleifen über dem
Fenster, geschmückter Baum rechts hinter dem Tisch, Adventskranz (je Adventssonntag eine Kerze mehr) und Geschenke auf dem Tisch.
Gezeichnet wird in Bildkoordinaten des fertigen Videos (720 x 1280), doppelt so groß und dann verkleinert (glatte Kanten).
  hintergrund(bg)        -> Deko auf die Studiowand (Bild 1000 x 1500 aus wetter_video.bg_studio)
  funkeln()              -> 3 durchsichtige Ebenen, die im Video abwechselnd über der Wand liegen (Lichter funkeln)
  tisch(im, top, kerzen) -> Adventskranz und Geschenke auf die Tisch-Ebene
  advent_kerzen(datum)   -> 0–4"""
import math, random, datetime as dt
from PIL import Image, ImageDraw, ImageFilter

S = 2
W, H = 720, 1280
BILDSCHIRM = (366, 142, 714, 618)        # Rahmen des Studio-Bildschirms im fertigen Bild
FARBEN = [(255, 196, 70), (230, 60, 60), (90, 190, 110), (255, 196, 70), (90, 150, 235)]


def advent_kerzen(d):
    """Wie viele Kerzen brennen? 4. Advent = letzter Sonntag vor dem 25.12."""
    h = dt.date(d.year, 12, 24); vierter = h - dt.timedelta(days=(h.weekday() + 1) % 7)
    return sum(1 for k in range(4) if d >= vierter - dt.timedelta(days=7 * k))


def _glow(L, x, y, r, col, a=120):
    g = Image.new('RGBA', L.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([x - r, y - r, x + r, y + r], fill=col + (a,))
    L.alpha_composite(g.filter(ImageFilter.GaussianBlur(r * 0.55)))


def _birnen():
    """Positionen (Bildkoordinaten) und Farben der Lichterkette rund um den Bildschirm."""
    x0, y0, x1, y1 = BILDSCHIRM; pts = []
    for ax, ay, bx, by in [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]:
        n = max(2, int(math.hypot(bx - ax, by - ay) / 34))
        for i in range(n): pts.append((ax + (bx - ax) * i / n, ay + (by - ay) * i / n))
    return [(x, y, FARBEN[i % len(FARBEN)]) for i, (x, y) in enumerate(pts)]


def _lichterkette(L):
    d = ImageDraw.Draw(L); B = _birnen()
    d.line([(x * S, y * S) for x, y, _ in B] + [(B[0][0] * S, B[0][1] * S)], fill=(40, 60, 40, 255), width=3)
    for x, y, c in B:
        _glow(L, x * S, y * S, 11 * S, c, 80); d = ImageDraw.Draw(L)
        d.ellipse([x * S - 5 * S, y * S - 5 * S, x * S + 5 * S, y * S + 5 * S], fill=c + (255,), outline=(255, 255, 255, 160))


def _girlande(L, x0, x1, y, haenge=22, bogen=2, seed=3):
    d = ImageDraw.Draw(L); rnd = random.Random(seed); pts = []
    for i in range(201):
        t = i / 200; pts.append(((x0 + (x1 - x0) * t) * S, (y + haenge * abs(math.sin(math.pi * bogen * t))) * S))
    for x, yy in pts:
        for _ in range(5):
            a = rnd.uniform(0, 2 * math.pi); l = rnd.uniform(9, 17) * S
            d.line([(x, yy), (x + math.cos(a) * l, yy + math.sin(a) * l * 0.8)], fill=rnd.choice([(28, 96, 58), (22, 80, 48), (40, 118, 70), (18, 66, 40)]) + (255,), width=3)
    for i, (x, yy) in enumerate(pts[6::13]):
        c = [(255, 200, 80), (255, 236, 170)][i % 2]; _glow(L, x, yy + 4 * S, 9 * S, c, 120); d = ImageDraw.Draw(L)
        d.ellipse([x - 3 * S, yy + S, x + 3 * S, yy + 7 * S], fill=c + (255,))
    for j in range(bogen + 1):   # rote Schleifen an den Aufhängepunkten
        x = (x0 + (x1 - x0) * j / bogen) * S; yy = y * S
        x = min(max(x, 14 * S), (x1 - 6) * S)
        for sx in (-1, 1):
            d.polygon([(x, yy), (x + sx * 17 * S, yy - 9 * S), (x + sx * 17 * S, yy + 9 * S)], fill=(196, 40, 48, 255), outline=(120, 20, 28, 255))
            d.polygon([(x, yy), (x + sx * 9 * S, yy + 22 * S), (x + sx * 2 * S, yy + 20 * S)], fill=(176, 32, 42, 255))
        d.ellipse([x - 5 * S, yy - 5 * S, x + 5 * S, yy + 5 * S], fill=(220, 60, 66, 255), outline=(120, 20, 28, 255))


def _baum_kugeln(cx=668, top=668, bot=905, seed=5):
    rnd = random.Random(seed); h = bot - top; out = []
    for i in range(22):
        t = rnd.uniform(0.12, 0.93); y = top + h * 0.86 * t; w = 14 + 78 * t
        out.append((cx + rnd.uniform(-w, w) * 0.8, y, i))
    return out


def _baum(L, cx=668, top=668, bot=905):
    d = ImageDraw.Draw(L); h = (bot - top) * S; X, T, B = cx * S, top * S, bot * S
    d.rectangle([X - 9 * S, B - 26 * S, X + 9 * S, B + 60 * S], fill=(96, 64, 38, 255))
    for i in range(5):
        y0 = T + h * 0.02 + (h * 0.80) * i / 5; y1 = y0 + h * 0.80 / 5 * 1.75; w = (26 + i * 17) * S
        d.polygon([(X, y0), (X + w, y1), (X - w, y1)], fill=[(30, 104, 62), (26, 92, 54)][i % 2] + (255,))
        for k in range(7):
            x = X - w + 2 * w * k / 6; d.ellipse([x - 5 * S, y1 - 6 * S, x + 5 * S, y1 + 3 * S], fill=(22, 80, 48, 255))
    cols = [(220, 50, 56), (255, 198, 70), (90, 150, 235), (240, 240, 245), (220, 50, 56), (255, 198, 70)]
    for x, y, i in _baum_kugeln(cx, top, bot):
        x *= S; y *= S
        if i % 3 == 1:
            _glow(L, x, y, 9 * S, (255, 214, 120), 100); d = ImageDraw.Draw(L); d.ellipse([x - 3 * S, y - 3 * S, x + 3 * S, y + 3 * S], fill=(255, 236, 170, 255))
        else:
            d.ellipse([x - 6 * S, y - 6 * S, x + 6 * S, y + 6 * S], fill=cols[i % len(cols)] + (255,), outline=(255, 255, 255, 120)); d.ellipse([x - 3 * S, y - 4 * S, x - S, y - 2 * S], fill=(255, 255, 255, 200))
    _glow(L, X, T, 20 * S, (255, 220, 110), 150); d = ImageDraw.Draw(L); st = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5; r = (15 if i % 2 == 0 else 6) * S; st.append((X + math.cos(a) * r, T + math.sin(a) * r))
    d.polygon(st, fill=(255, 208, 70, 255), outline=(200, 150, 30, 255))


def hintergrund(bg):
    """Deko auf die Studiowand. bg = Bild 1000 x 1500; im Video wird davon der mittlere Streifen (843 breit) gezeigt."""
    L = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    _girlande(L, -6, 312, 184); _baum(L); _lichterkette(L)
    bw, bh = bg.size; cw = int(min(bw, bh * W / H)); ch = int(cw * H / W)
    out = bg.convert('RGBA'); out.alpha_composite(L.resize((cw, ch), Image.LANCZOS), ((bw - cw) // 2, 0))
    return out.convert('RGB')


def funkeln():
    """Drei Ebenen (720 x 1280): je ein Drittel der Lichter leuchtet heller – im Wechsel ergibt das ein ruhiges Funkeln."""
    out = []
    for v in range(3):
        L = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
        for i, (x, y, c) in enumerate(_birnen()):
            if i % 3 == v: _glow(L, x * S, y * S, 15 * S, c, 150); ImageDraw.Draw(L).ellipse([x * S - 3 * S, y * S - 3 * S, x * S + 3 * S, y * S + 3 * S], fill=(255, 255, 255, 170))
        for x, y, i in _baum_kugeln():
            if i % 3 == 1 and (i // 3) % 3 == v: _glow(L, x * S, y * S, 12 * S, (255, 224, 140), 160)
        out.append(L.resize((W, H), Image.LANCZOS))
    return out


def _kranz(L, cx, y, an):
    d = ImageDraw.Draw(L); rnd = random.Random(9); X, Y = cx * S, y * S
    for _ in range(160):
        a = rnd.uniform(0, 2 * math.pi); x = X + math.cos(a) * 52 * S * rnd.uniform(.75, 1.05); yy = Y + math.sin(a) * 13 * S * rnd.uniform(.7, 1.1)
        l = rnd.uniform(6, 12) * S; b = rnd.uniform(0, 2 * math.pi)
        d.line([(x, yy), (x + math.cos(b) * l, yy + math.sin(b) * l * .6)], fill=rnd.choice([(28, 96, 58), (22, 80, 48), (40, 118, 70)]) + (255,), width=3)
    for i, dx in enumerate([-38, -13, 13, 38]):
        x = X + dx * S; yb = Y - 2 * S + (4 * S if i in (1, 2) else -2 * S)
        d.rounded_rectangle([x - 8 * S, yb - 44 * S, x + 8 * S, yb], radius=3 * S, fill=(200, 44, 52, 255), outline=(110, 20, 26, 255), width=S)
        d.rectangle([x - 8 * S, yb - 44 * S, x - 4 * S, yb], fill=(226, 90, 96, 255))
        d.line([(x, yb - 44 * S), (x, yb - 50 * S)], fill=(40, 30, 20, 255), width=S)
        if i < an:
            _glow(L, x, yb - 58 * S, 16 * S, (255, 200, 90), 150); d = ImageDraw.Draw(L)
            d.polygon([(x, yb - 72 * S), (x + 6 * S, yb - 56 * S), (x, yb - 49 * S), (x - 6 * S, yb - 56 * S)], fill=(255, 196, 60, 255)); d.ellipse([x - 3 * S, yb - 58 * S, x + 3 * S, yb - 51 * S], fill=(255, 244, 190, 255))
    for dx in (-26, 0, 26): d.ellipse([X + dx * S - 5 * S, Y + 6 * S, X + dx * S + 5 * S, Y + 16 * S], fill=(196, 40, 48, 255))


def _geschenke(L, x, y):
    d = ImageDraw.Draw(L)
    for dx, w, h, c, b in [(0, 34, 26, (196, 40, 48), (255, 208, 70)), (30, 28, 20, (40, 118, 70), (240, 240, 245)), (12, 24, 18, (60, 110, 190), (255, 208, 70))]:
        x0 = (x + dx) * S; y0 = (y - h) * S if dx != 12 else (y - 26 - h) * S
        d.rounded_rectangle([x0, y0, x0 + w * S, y0 + h * S], radius=3 * S, fill=c + (255,), outline=(30, 20, 20, 255), width=S)
        d.rectangle([x0 + w * S // 2 - 3 * S, y0, x0 + w * S // 2 + 3 * S, y0 + h * S], fill=b + (255,)); d.rectangle([x0, y0 + h * S // 2 - 3 * S, x0 + w * S, y0 + h * S // 2 + 3 * S], fill=b + (255,))


def tisch(im, top, kerzen):
    """Adventskranz (rechts neben der Tasse) und Geschenke (ganz rechts) auf die Tisch-Ebene (RGBA, 720 x 1280)."""
    L = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    _kranz(L, 580, top + 7, kerzen); _geschenke(L, 655, top)
    im.alpha_composite(L.resize((W, H), Image.LANCZOS))
    return im
