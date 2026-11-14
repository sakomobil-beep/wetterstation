#!/usr/bin/env python3
"""„Wetterwissen mit Max“ – eigene Rubrik (seit 14.11.2026, ca. 45 Sekunden), Mo–Fr um 15 Uhr, vorerst von Hand posten.
Ablauf: Aufhänger – Erklärung in 3 Schritten (Grafik baut sich mit auf) – Odenwald-Bezug mit echten Werten unserer Station – Abschluss.
Max sitzt in seinem Wissenszimmer (Schubladenschrank, großer Fernseher, Bücher, Lampen, Globus) und erklärt ein
Wetter-Phänomen – passend zu Wetter und Jahreszeit (Einstufung wie im Morgenvideo), dasselbe Thema frühestens nach 365 Tagen
(bzw. wenn der Vorrat aufgebraucht ist: das am längsten zurückliegende). Max trägt täglich wechselnd Hemd oder Pulli.
Ausgabe: fb/wissen.mp4 + fb/wissen.json (Titel, Skript, Beitragstext).   Test ohne Ton:  python wissen_video.py --demo"""
import os, re, sys, json, math, random, subprocess, tempfile, datetime as dt
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wetter_video as V
from wetter_video import F, sprich, dauer, pegel, moderator, FPS, W, H, FB, ROOT
DEMO = '--demo' in sys.argv
LOG = os.path.join(FB, 'wissen_log.json')
MUSIK = os.path.join(ROOT, 'video', 'musik', 'hintergrund.mp3')

O = (40, 30, 22)
TV = (400, 395, 880, 665)        # Bildschirm im alten Röhrenfernseher (Hintergrund-Koordinaten 1000x1500)

def holz(d, box, c, fuge=None):
    d.rectangle(box, fill=c, outline=O, width=4)

def bg_wissen(seed=1):
    BW, BH = 1000, 1500
    r = random.Random(seed)
    im = V.verlauf(BW, BH, (120, 128, 132), (92, 96, 100)).convert('RGB'); d = ImageDraw.Draw(im)
    # warmes Licht von der Stehlampe links
    gl = Image.new('RGBA', (BW, BH), (0, 0, 0, 0)); g = ImageDraw.Draw(gl)
    for k in range(18, 0, -1): g.ellipse([150 - k * 26, 620 - k * 30, 150 + k * 26, 620 + k * 30], fill=(255, 210, 140, 7))
    im = Image.alpha_composite(im.convert('RGBA'), gl).convert('RGB'); d = ImageDraw.Draw(im)
    # Stehlampe (Papierschirm) links
    d.rounded_rectangle([110, 330, 230, 860], radius=24, fill=(250, 226, 170), outline=(200, 170, 110), width=3)
    for y in range(350, 850, 26): d.line([(118, y), (222, y + 6)], fill=(236, 205, 140), width=2)
    # Wandregal mit Büchern oberhalb des Fernsehers
    d.rectangle([400, 300, 960, 318], fill=(120, 86, 52), outline=O, width=3)
    for bx in (420, 930): d.polygon([(bx, 318), (bx + 14, 318), (bx + 7, 345)], fill=(90, 64, 40))
    x = 430
    for k in range(17):
        c = [(70, 110, 160), (200, 200, 190), (60, 140, 110), (180, 60, 50), (230, 230, 220), (90, 90, 120), (210, 160, 60)][k % 7]
        h = r.randint(95, 130); w = r.randint(16, 26)
        if k == 9: x += 60; d.rectangle([x - 50, 200, x - 6, 296], fill=(225, 215, 195), outline=(120, 90, 50), width=5); d.polygon([(x - 44, 290), (x - 28, 230), (x - 12, 290)], fill=(90, 130, 90))
        d.rectangle([x, 300 - h, x + w, 300], fill=c, outline=O, width=2); x += w + 3
    # kleinerer Schubladenschrank (Apothekerschrank) – trägt den Fernseher
    sx0, sy0, sx1 = 330, 790, 990
    holz(d, [sx0, sy0, sx1, 1180], (150, 112, 70))
    d.rectangle([sx0 - 10, sy0 - 16, sx1 + 10, sy0 + 4], fill=(120, 86, 52), outline=O, width=3)   # Abdeckplatte
    for y in range(sy0 + 14, 1170, 72):
        for x in range(sx0 + 14, sx1 - 14, 164):
            d.rectangle([x + 4, y + 4, x + 160, y + 68], fill=(162, 122, 78), outline=(110, 80, 48), width=3)
            cx = x + 82; d.rounded_rectangle([cx - 24, y + 22, cx + 24, y + 38], radius=4, fill=(205, 205, 210), outline=(110, 110, 120), width=2)
            d.rectangle([cx - 12, y + 42, cx + 12, y + 50], fill=(235, 235, 225), outline=(140, 140, 140), width=1)
    # Bücherstapel auf dem Schrank links neben dem Fernseher
    x = 345
    for k, c in enumerate([(60, 140, 110), (180, 60, 50), (70, 110, 160), (230, 230, 220)]):
        h = 120 - k * 6; d.rectangle([x, sy0 - 16 - h, x + 20, sy0 - 16], fill=c, outline=O, width=2); x += 22
    d.rectangle([340, sy0 - 52, 400, sy0 - 16], fill=(120, 60, 40), outline=O, width=2); d.rectangle([336, sy0 - 76, 404, sy0 - 52], fill=(40, 70, 110), outline=O, width=2)
    # großer Flachbildfernseher (LCD) auf dem Schrank
    tx0, ty0, tx1, ty1 = TV
    d.rounded_rectangle([tx0 - 14, ty0 - 14, tx1 + 14, ty1 + 14], radius=8, fill=(22, 22, 24), outline=(10, 10, 10), width=3)
    d.rectangle([tx0, ty0, tx1, ty1], fill=(24, 36, 48))
    mx_ = (tx0 + tx1) // 2
    d.rectangle([mx_ - 14, ty1 + 14, mx_ + 14, sy0 - 40], fill=(40, 40, 44)); d.polygon([(mx_ - 90, sy0 - 16), (mx_ + 90, sy0 - 16), (mx_ + 60, sy0 - 40), (mx_ - 60, sy0 - 40)], fill=(40, 40, 44))
    d.ellipse([tx1 - 22, ty1 + 2, tx1 - 14, ty1 + 10], fill=(220, 60, 60))
    # Schreibtischlampe oben links (Arm + Schirm)
    d.line([(0, 140), (170, 60)], fill=(170, 170, 175), width=12)
    d.polygon([(130, 40), (300, 70), (270, 210), (110, 170)], fill=(190, 192, 196), outline=O)
    d.ellipse([140, 150, 280, 230], fill=(255, 245, 210))
    return im.filter(ImageFilter.SMOOTH)

def desk_wissen():
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); top = V.STUDIO_TISCH
    d.rectangle([0, top, W, top + 46], fill=(92, 60, 38, 255)); d.rectangle([0, top + 46, W, top + 58], fill=(70, 46, 28, 255))
    d.rectangle([0, top + 58, W, H], fill=(56, 38, 24, 255))
    for y in range(top + 90, H, 34): d.line([(0, y), (W, y)], fill=(46, 30, 18, 255), width=2)
    # Globus links
    d.ellipse([-120, top - 200, 60, top - 20], fill=(225, 225, 215, 255), outline=O + (255,), width=4)
    for k in range(5): d.arc([-120 + k * 18, top - 200, 60 - k * 18, top - 20], 0, 360, fill=(170, 170, 160, 255), width=2)
    d.arc([-150, top - 228, 90, top + 8], 200, 340, fill=(60, 60, 60, 255), width=8); d.rectangle([-30, top - 20, 20, top + 6], fill=(60, 60, 60, 255))
    # Stiftebecher
    d.rectangle([340, top - 70, 390, top + 4], fill=(40, 40, 45, 255), outline=O + (255,), width=3)
    for k, c in enumerate([(220, 60, 50), (240, 200, 60), (60, 120, 200), (220, 60, 50)]): d.line([(350 + k * 10, top - 70), (345 + k * 13, top - 120)], fill=c + (255,), width=5)
    # Sanduhr
    d.polygon([(398, top - 60), (422, top - 60), (410, top - 30)], fill=(250, 250, 250, 200), outline=O + (255,)); d.polygon([(398, top), (422, top), (410, top - 30)], fill=(250, 250, 250, 200), outline=O + (255,))
    d.polygon([(402, top - 4), (418, top - 4), (410, top - 18)], fill=(220, 80, 60, 255))
    # orange Tasse
    d.rounded_rectangle([430, top - 34, 500, top + 20], radius=8, fill=(240, 120, 40, 255), outline=O + (255,), width=4)
    d.arc([488, top - 22, 522, top + 10], 270, 90, fill=O + (255,), width=5)
    # Sternglobus
    d.ellipse([540, top - 110, 640, top - 10], fill=(40, 60, 120, 255), outline=O + (255,), width=4)
    rr = random.Random(3)
    for _ in range(18): x, y = rr.randint(555, 625), rr.randint(int(top) - 95, int(top) - 25); d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(240, 240, 255, 255))
    d.rectangle([575, top - 10, 605, top + 4], fill=(30, 30, 30, 255))
    # Blatt Papier
    d.polygon([(470, top + 30), (690, top + 26), (700, top + 44), (460, top + 48)], fill=(245, 245, 240, 255))
    d.text((W / 2, top + 150), 'WETTERWISSEN', font=V.F(34), fill=(215, 180, 130, 255), anchor='mm')
    return im

# --- Kleidung im Wissenszimmer: Hemd oder Pulli im Wechsel ---------------------------
def kleidung_muster(name):
    PX0, PX1, PY0, PY1 = V._PX0, V._PX1, V._PY0, V._PY1
    farben = {'hemd_hellblau': (150, 190, 230), 'hemd_kariert': (180, 60, 60), 'hemd_weiss': (240, 242, 245),
              'pulli_dunkelblau': (35, 55, 95), 'pulli_bordeaux': (120, 30, 45), 'pulli_grau': (120, 125, 130), 'pulli_gruen': (60, 95, 70)}
    g = farben[name]; p = Image.new('RGBA', (380, 760), g + (255,)); d = ImageDraw.Draw(p); cx = (PX0 + PX1) // 2
    if name == 'hemd_kariert':
        for x in range(0, 380, 26): d.rectangle([x, 0, x + 9, 760], fill=(140, 40, 45))
        for y in range(0, 760, 26): d.rectangle([0, y, 380, y + 9], fill=(150, 45, 50))
        for x in range(13, 380, 26): d.line([(x, 0), (x, 760)], fill=(235, 220, 200), width=2)
    if name.startswith('hemd'):
        d.line([(cx, PY0), (cx, PY1)], fill=tuple(max(0, c - 50) for c in g), width=3)            # Knopfleiste
        for y in range(PY0 + 30, PY1, 42): d.ellipse([cx - 5, y - 5, cx + 5, y + 5], fill=(250, 250, 250), outline=(90, 90, 90))
        d.rectangle([PX0 + 30, PY0 + 70, PX0 + 85, PY0 + 120], outline=tuple(max(0, c - 50) for c in g), width=3)   # Brusttasche
    else:
        for y in range(PY0, PY1, 10): d.line([(0, y), (380, y)], fill=tuple(max(0, c - 14) for c in g), width=2)   # Strickrippen
        if name == 'pulli_grau':
            for x in (cx - 50, cx, cx + 50):   # Zopfmuster
                for y in range(PY0 + 10, PY1, 30): d.arc([x - 14, y, x + 14, y + 30], 200, 340, fill=(160, 165, 170), width=4); d.arc([x - 14, y + 15, x + 14, y + 45], 20, 160, fill=(95, 100, 105), width=4)
        d.rectangle([0, PY1 - 26, 380, PY1], fill=tuple(max(0, c - 25) for c in g))   # Bund
    tex = Image.effect_noise((380, 760), 30).convert('L').point(lambda v: int(v * 0.05))
    return Image.composite(Image.new('RGBA', p.size, (0, 0, 0, 255)), p, tex)

KLEIDUNG = ['hemd_hellblau', 'pulli_dunkelblau', 'hemd_kariert', 'pulli_bordeaux', 'hemd_weiss', 'pulli_grau', 'pulli_gruen']

def anziehen(name):
    V._PULLI_CACHE[name] = kleidung_muster(name); V.PULLI[0] = name

def _anziehen_voll(im, name):
    """Wie V.pulli_anziehen, aber auch die Ärmel (erhobener Arm beim Zeigen/Winken) bekommen Hemd/Pulli."""
    a = np.array(im); r_, g_, b_ = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int); al = a[:, :, 3] > 200
    tuerkis = (g_ - r_ > 35) & (b_ - r_ > 25)
    futter = (abs(r_ - 58) <= 6) & (abs(g_ - 68) <= 6) & (abs(b_ - 83) <= 6)
    schild = (r_ > 225) & (g_ > 225) & (b_ > 225); schild[:V._PY0 + 30, :] = False; schild[V._PY1 + 30:, :] = False
    m_ = (tuerkis | futter | schild) & al
    M = Image.fromarray((m_ * 255).astype('uint8')).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
    inner = Image.fromarray((al * 255).astype('uint8')).filter(ImageFilter.MinFilter(9))
    M = Image.fromarray(np.minimum(np.array(M), np.array(inner)))
    out = im.copy(); out.paste(V.pulli_muster(name), (0, 0), M); return out
V.pulli_anziehen = _anziehen_voll


def kategorien(a, heute):
    w = V.wort(a['code']); m = heute.month; kat = []
    if a['code'] in (45, 48): kat.append('nebel')
    if w == 'Schnee' or a.get('schnee', 0) >= 1: kat.append('schnee')
    if w == 'Gewitter': kat.append('gewitter')
    if a.get('boe', 0) >= 50: kat.append('sturm')
    if a['tmin'] <= 0: kat.append('frost')
    if w in ('Regen', 'Nieselregen', 'Schauer') or V.nass_tag(a): kat.append('regen')
    if w in ('sonnig', 'heiter bis wolkig'): kat.append('sonne')
    kat.append({12: 'winter', 1: 'winter', 2: 'winter', 3: 'fruehling', 4: 'fruehling', 5: 'fruehling', 6: 'sommer', 7: 'sommer', 8: 'sommer'}.get(m, 'herbst'))
    return kat + ['wolken', 'allgemein']


def thema_waehlen(a, heute, rnd):
    L = json.load(open(os.path.join(ROOT, 'data', 'wetterwissen_max.json'), encoding='utf-8'))
    try: log = json.load(open(LOG, encoding='utf-8'))
    except Exception: log = []
    zuletzt = {e['t']: e['d'] for e in log}
    grenze = (heute - dt.timedelta(days=365)).isoformat()
    for k in kategorien(a, heute):
        frei = [x for x in L if x['k'] == k and zuletzt.get(x['t'], '0') < grenze]
        if frei: x = rnd.choice(frei); break
    else:   # alles schon gezeigt: das am längsten zurückliegende passende Thema
        kand = [x for x in L if x['k'] in kategorien(a, heute)] or L
        x = min(kand, key=lambda x: zuletzt.get(x['t'], '0'))
    log = [e for e in log if e['t'] != x['t']] + [dict(d=heute.isoformat(), t=x['t'])]
    return x, log


# --- Grafik im Fernseher (640 x 360), leicht animiert ------------------------------------------
def szene(k, titel, t, kurz=None, schritt=-1):
    im = V.verlauf(640, 360, (30, 70, 120), (110, 160, 210)).convert('RGBA'); d = ImageDraw.Draw(im)
    if k in ('nebel', 'herbst'):
        d.polygon([(0, 360), (0, 150), (150, 90), (260, 230), (380, 230), (500, 80), (640, 150), (640, 360)], fill=(70, 110, 80))
        for j in range(5):
            y = 225 + j * 18; x = (t * 25 + j * 70) % 120 - 60
            d.rounded_rectangle([60 + x, y, 580 + x, y + 26], radius=13, fill=(235, 238, 242, 200))
        for x0 in (60, 560): d.line([(x0, 120), (x0 + (90 if x0 < 300 else -90), 210)], fill=(150, 200, 255), width=6)
    elif k in ('frost', 'winter'):
        d.rectangle([0, 270, 640, 360], fill=(225, 235, 245))
        for j in range(40): x = (j * 53) % 640; y = (j * 37 + t * 30) % 260; d.text((x, y), '*', font=F(26), fill=(255, 255, 255))
        d.rounded_rectangle([290, 40, 350, 260], radius=30, fill=(245, 245, 245), outline=(40, 40, 40), width=4)
        h = 60 + 30 * math.sin(t); d.rectangle([308, 240 - h, 332, 240], fill=(60, 120, 230)); d.ellipse([295, 225, 345, 275], fill=(60, 120, 230))
        d.text((400, 150), '0 °C', font=F(48), fill='white', anchor='lm')
    elif k == 'schnee':
        d.rectangle([0, 280, 640, 360], fill=(245, 248, 252))
        for j in range(70): x = (j * 47 + 15 * math.sin(t + j)) % 640; y = (j * 29 + t * 60) % 280; d.ellipse([x - 4, y - 4, x + 4, y + 4], fill='white')
    elif k in ('regen', 'wolken', 'fruehling'):
        for cx in (180, 380):
            for dx, r in ((-50, 40), (0, 60), (55, 45)): d.ellipse([cx + dx - r, 110 - r, cx + dx + r, 110 + r], fill=(230, 235, 242))
        if k != 'wolken':
            for j in range(40): x = (j * 41) % 560 + 50; y = 160 + (j * 23 + t * 220) % 190; d.line([(x, y), (x - 6, y + 18)], fill=(120, 180, 255), width=4)
    elif k in ('gewitter', 'sturm'):
        im = V.verlauf(640, 360, (35, 35, 55), (95, 90, 110)).convert('RGBA'); d = ImageDraw.Draw(im)
        for dx, r in ((-80, 60), (0, 85), (90, 65)): d.ellipse([320 + dx - r, 110 - r, 320 + dx + r, 110 + r], fill=(80, 80, 95))
        if k == 'gewitter' and (t % 1.6) < 0.2: d.polygon([(330, 170), (280, 260), (320, 260), (290, 350), (380, 230), (335, 230), (370, 170)], fill=(255, 235, 90))
        if k == 'sturm':
            for j in range(6): y = 200 + j * 25; x = (t * 300 + j * 90) % 760 - 120; d.line([(x, y), (x + 120, y)], fill=(220, 225, 235), width=5)
    else:   # sonne, sommer, allgemein
        r = 70 + 5 * math.sin(t * 2); d.ellipse([320 - r, 160 - r, 320 + r, 160 + r], fill=(250, 205, 60))
        for j in range(12):
            an = j * math.pi / 6 + t * 0.4; d.line([(320 + 95 * math.cos(an), 160 + 95 * math.sin(an)), (320 + 125 * math.cos(an), 160 + 125 * math.sin(an))], fill=(250, 205, 60), width=8)
    band = Image.new('RGBA', (640, 64), (15, 25, 45, 220)); ImageDraw.Draw(band).text((320, 32), titel, font=F(28), fill='white', anchor='mm')
    im.alpha_composite(band, (0, 0))
    if kurz and schritt >= 0:   # Schritte bauen sich nacheinander auf
        ov = Image.new('RGBA', (640, 360), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.rectangle([0, 220, 640, 360], fill=(10, 20, 40, 200))
        for n_, z in enumerate(kurz[:schritt + 1]):
            akt = n_ == schritt
            od.ellipse([20, 232 + n_ * 42, 52, 264 + n_ * 42], fill=(215, 160, 20) if akt else (90, 110, 140))
            od.text((36, 248 + n_ * 42), str(n_ + 1), font=F(20), fill=(30, 20, 5) if akt else 'white', anchor='mm')
            od.text((66, 248 + n_ * 42), z, font=F(26), fill='white' if akt else (190, 200, 215), anchor='lm')
        im.alpha_composite(ov)
    return im


def wertekarte(titel, text):
    im = V.verlauf(640, 360, (20, 60, 40), (40, 110, 70)).convert('RGBA'); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 640, 64], fill=(15, 25, 45, 230)); d.text((320, 32), 'Station Bad König – gemessen', font=F(28), fill='white', anchor='mm')
    zeilen, z = [], ''
    for w_ in text.split():
        if len(z + ' ' + w_) > 30: zeilen.append(z); z = w_
        else: z = (z + ' ' + w_).strip()
    zeilen.append(z)
    for n_, zl in enumerate(zeilen[:6]): d.text((320, 100 + n_ * 42), zl, font=F(28), fill='white', anchor='mm')
    return im


def kopf(text):
    im = Image.new('RGBA', (W, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 20, W - 20, 100], radius=18, fill=(215, 160, 20, 235))
    d.text((W / 2, 60), text, font=F(34), fill=(40, 25, 5), anchor='mm')
    return im


def main():
    heute = dt.date.today()
    tage = json.load(open(os.path.join(FB, 'daten.json'), encoding='utf-8'))['tage']
    a = tage[0]
    rnd = random.Random('wissen' + heute.isoformat())
    x, log = thema_waehlen(a, heute, rnd)
    kl = KLEIDUNG[heute.toordinal() % len(KLEIDUNG)]
    if not (V.pulli_zeit(heute)): anziehen(kl)
    else: V.PULLI[0] = V.PULLI_NAMEN[heute.toordinal() % len(V.PULLI_NAMEN)]   # Advent: Weihnachtspulli wie im Studio
    intro = V.frisch(rnd, 'wissen_intro', ['Hallo zusammen, hier ist Max – Zeit für Wetterwissen!', 'Wetterwissen mit Max – heute eine spannende Frage:',
                                           'Hallo Odenwald! Hier ist euer Max mit einem Stück Wetterwissen.', 'Willkommen zu Wetterwissen mit Max!'])
    g = (a.get('gestern') or {}); werte = dict(g_tmin=g.get('tmin'), g_tmax=g.get('tmax'), g_regen=g.get('regen'), g_boe=g.get('boe'), sonne=a.get('sonne'))
    def fmt(v):
        v = float(v); t_ = str(int(round(v))) if abs(v - round(v)) < 0.05 else ('%.1f' % v).replace('.', ',')
        return t_.replace('-', 'minus ')
    bezug = None
    try:
        noetig = re.findall(r'\{(\w+)\}', x['bezug'])
        if all(werte.get(k_) is not None for k_ in noetig): bezug = x['bezug'].format(**{k_: fmt(werte[k_]) for k_ in noetig})
    except Exception as e: print('Bezug nicht möglich:', e)
    schluss = V.frisch(rnd, 'wissen_ende', ['Wieder was gelernt? Dann folgt uns für mehr Wetterwissen aus dem Odenwald!',
                                            'Habt ihr das gewusst? Schreibt’s mir in die Kommentare!',
                                            ('Am Montag gibt’s das nächste Wetterwissen – schönes Wochenende!' if heute.weekday() >= 4 else 'Morgen gibt’s das nächste Wetterwissen – bis dann!'),
                                            'Welches Wetter-Rätsel soll ich als Nächstes lösen? Schreibt’s mir!'])
    teile = [('intro', intro + ' ' + x['hook'])] + [('s%d' % n_, st) for n_, st in enumerate(x['schritte'])]
    if bezug: teile.append(('bezug', bezug))
    teile.append(('ende', schluss))
    tmp = tempfile.mkdtemp(); echt = True; dat = []
    for n, (art, txt) in enumerate(teile):
        p = os.path.join(tmp, 'a%d.mp3' % n)
        if DEMO: subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '%.2f' % max(1.5, len(txt) / 16), p], check=True); echt = False
        else: echt = sprich(txt, p, '+0%') and echt
        q = os.path.join(tmp, 'p%d.wav' % n)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', p, '-af', 'apad=pad_dur=0.35', '-ar', '24000', '-ac', '1', q], check=True)
        dat.append(dict(art=art, text=txt, wav=q, dauer=dauer(q)))
    liste = os.path.join(tmp, 'l.txt'); open(liste, 'w').write(''.join("file '%s'\n" % t['wav'] for t in dat))
    ton = os.path.join(tmp, 'ton.wav'); subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', liste, ton], check=True)
    gesamt = dauer(ton) + 1.2; N = int(gesamt * FPS)
    lv = pegel(ton, N) if echt else np.array([0.8 + 0.6 * math.sin(i * 1.7) for i in range(N)])
    if os.path.exists(MUSIK):
        mix = os.path.join(tmp, 'mix.wav')
        fk = ('[0:a]aformat=sample_rates=44100:channel_layouts=stereo,apad,atrim=0:%.2f[v];[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.02,afade=t=out:st=%.2f:d=1.5,atrim=0:%.2f[m];[v][m]amix=inputs=2:duration=first:normalize=0' % (gesamt, max(0, gesamt - 1.5), gesamt))
        try: subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', ton, '-stream_loop', '-1', '-i', MUSIK, '-filter_complex', fk, mix], check=True); ton = mix
        except Exception as e: print('Musik übersprungen:', e)
    t0 = 0
    for t in dat: t['start'] = t0; t0 += t['dauer']
    # Kulisse vorbereiten
    bg = bg_wissen(); bw, bh = bg.size; cw = int(min(bw, bh * W / H)); x0 = (bw - cw) // 2; sc = W / cw
    basis = bg.crop((x0, 0, x0 + cw, int(cw * H / W))).resize((W, H)).convert('RGBA')
    tx0, ty0, tx1, ty1 = TV; rx, ry, rw, rh = int((tx0 - x0) * sc), int(ty0 * sc), int((tx1 - tx0) * sc), int((ty1 - ty0) * sc)
    desk = desk_wissen(); KOPF = kopf('WETTERWISSEN MIT MAX')
    MODS = {}
    ziel = os.path.join(FB, 'wissen.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-i', ton, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
                           '-shortest', '-movflags', '+faststart', ziel], stdin=subprocess.PIPE)
    for i in range(N):
        zt = i / FPS
        akt = max([t for t in dat if t['start'] <= zt] or dat[:1], key=lambda t: t['start'])
        fr = basis.copy()
        if akt['art'] == 'bezug':
            if 'WK' not in MODS: MODS['WK'] = wertekarte(x['t'], akt['text'])
            sz = MODS['WK'].resize((rw, rh))
        else:
            sch = int(akt['art'][1]) if akt['art'].startswith('s') else (2 if akt['art'] == 'ende' else -1)
            sz = szene(x['k'], x['t'], zt, x.get('kurz'), sch).resize((rw, rh))
        ein = min(1, zt / 0.6); 
        if ein < 1: sz = Image.blend(Image.new('RGBA', sz.size, (24, 36, 48, 255)), sz, ein)
        fr.alpha_composite(sz, (rx, ry))
        lev = lv[i] if i < len(lv) else 0
        mund = 0 if lev < 0.15 else 1 if lev < 0.45 else 2 if lev < 0.8 else 3
        blink = 1 if (i % 97) < 3 else 0
        zeig = 1 if akt['art'] in ('s0', 's1', 's2', 'bezug') and zt - akt['start'] < 1.8 else 3 if akt['art'] == 'intro' and zt < 1.6 else 0
        key = (mund, blink, zeig)
        if key not in MODS: MODS[key] = moderator(mund, blink, zeig, 0, studio=True)
        mm = MODS[key]; bob = int(2 * math.sin(zt * 2.2))
        fr.alpha_composite(mm, (10, V.STUDIO_TISCH - int(mm.height * 0.70) + bob))
        fr.alpha_composite(desk)
        if zt < 3.0: fr.alpha_composite(KOPF, (0, 30))
        ff.stdin.write(fr.convert('RGB').tobytes())
    ff.stdin.close(); ff.wait()
    beitrag = '\n'.join(['💡 Wetterwissen mit Max: ' + x['t'], '', x['hook'], '', ' '.join(x['schritte']), '',
                         'Jeden Montag bis Freitag erklärt Max ein Stück Wetter – folgt uns, um nichts zu verpassen!',
                         '🌦️ Live-Werte aus Bad König: https://wetter-badkoenig.de', '', '#Wetterwissen #Odenwald #BadKönig #Wetter #MaxErklärt'])
    json.dump(dict(erstellt=dt.datetime.now().astimezone().isoformat(timespec='minutes'), datum=heute.isoformat(), titel=x['t'], kategorie=x['k'],
                   kleidung=V.PULLI[0], dauer=round(gesamt, 1), stimme=echt, skript=' '.join(t['text'] for t in dat), beitrag=beitrag),
              open(os.path.join(FB, 'wissen.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not DEMO: json.dump(log[-400:], open(LOG, 'w', encoding='utf-8'), ensure_ascii=False)
    if not DEMO: V.saetze_speichern()
    print('Wetterwissen fertig: %s (%.0f s)' % (x['t'], gesamt))


if __name__ == '__main__':
    main()
