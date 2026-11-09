#!/usr/bin/env python3
"""Themenvideo „Max erklärt“ (Querformat 1280×720, ca. 9–10 Minuten): Der Rekord-El-Niño 2026.
Sachlicher Ton, eigene Grafiken (keine fremden Bilder), Zahlen von der El-Niño-Seite der Website (NOAA, JMA, WMO, DWD, WFP).
Ausgabe: fb/thema.mp4 + fb/thema.json (Titel, Dauer, Kapitel, Beitragstext zum Teilen)."""
import os, sys, json, math, random, subprocess, tempfile, datetime as dt
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wetter_video as WV
from wetter_video import F, sprich, dauer, pegel, moderator, FPS

W, H = 1280, 720
FB = WV.FB
MUSIK = os.path.join(WV.ROOT, 'video', 'musik', 'hintergrund.mp3')
DEMO = '--demo' in sys.argv          # ohne Sprachausgabe, kurz (zum Testen)
STAND = 'Stand: Ende Oktober 2026'

ROT, BLAU, GELB = (215, 60, 40), (40, 110, 200), (245, 190, 40)
DUNKEL, HELL = (18, 32, 52), (240, 246, 252)

# ---------------------------------------------------------------- Drehbuch
# Jedes Kapitel: Titel, Szene (Zeichenfunktion) und Abschnitte (Sprechtext, Karte die dabei erscheint)
KAPITEL = [
    dict(titel='Der Rekord-El-Niño 2026', szene='pazifik_glut', teile=[
        ('Hallo und herzlich willkommen zu einer neuen Folge von „Max erklärt“. Heute geht es um ein Thema, das gerade weltweit Wetterdienste beschäftigt: den El Niño im Pazifik.', None),
        ('Im September hat die Weltorganisation für Meteorologie erklärt, dass ein sehr starker El Niño bis mindestens Februar 2027 nahezu sicher ist.', ('WMO, 3. September 2026', 'Sehr starker El Niño bis mind. Februar 2027 nahezu sicher')),
        ('Und die Messwerte bestätigen das. Der Japanische Wetterdienst meldete für September im tropischen Ostpazifik eine Abweichung von plus vier Grad. So viel wie nie seit Beginn seiner Messreihe im Jahr 1949.', ('JMA, 9. Oktober 2026', '+4,0 °C im Ostpazifik – Rekord seit 1949')),
        ('Damit liegt dieser El Niño schon jetzt über den bekannten Extremjahren 1997 und 2015 – und der Höhepunkt wird erst zwischen November und Januar erwartet.', ('Höhepunkt erwartet', 'November 2026 bis Januar 2027')),
        ('In diesem Video schauen wir uns an, wie El Niño entsteht, wie außergewöhnlich die Zahlen sind, welche Folgen es weltweit gibt und was das für Europa und für uns hier im Odenwald bedeutet.', None),
    ]),
    dict(titel='1. Wie El Niño funktioniert', szene='walker_normal', teile=[
        ('Fangen wir mit den Grundlagen an. Im Normalzustand wehen über dem tropischen Pazifik kräftige Passatwinde von Ost nach West.', ('Normalzustand', 'Passatwinde wehen von Ost nach West')),
        ('Sie schieben das warme Oberflächenwasser Richtung Indonesien und Australien. Dort steigt feuchte Luft auf, es bilden sich Wolken und kräftiger Regen.', ('Westpazifik', 'warmes Wasser, viel Regen')),
        ('Vor der Küste Südamerikas quillt dafür kaltes, nährstoffreiches Wasser aus der Tiefe auf. Davon leben die großen Fischbestände vor Peru.', ('Ostpazifik', 'kaltes Auftriebswasser vor Peru')),
        ('Diese großräumige Luftzirkulation über dem Pazifik nennt man Walker-Zirkulation.', ('Fachbegriff', 'Walker-Zirkulation')),
    ]),
    dict(titel='1. Wie El Niño funktioniert', szene='walker_nino', teile=[
        ('Bei El Niño gerät dieses System aus dem Gleichgewicht. Die Passatwinde werden schwächer, manchmal drehen sie sogar.', ('El Niño', 'Passatwinde schwächeln oder drehen')),
        ('Das warme Wasser schwappt zurück nach Osten, und mit ihm wandern die Regengebiete. Vor Südamerika wird das Meer mehrere Grad zu warm.', ('Folge', 'Warmwasser und Regen wandern nach Osten')),
        ('Im Westen, also in Indonesien und Australien, wird es dagegen trocken.', ('Westpazifik', 'Trockenheit')),
        ('El Niño ist ein natürlicher Vorgang. Er tritt etwa alle zwei bis sieben Jahre auf. Den Namen gaben peruanische Fischer: El Niño heißt „das Christkind“, weil das warme Wasser oft um Weihnachten ankam.', ('Name', '„El Niño“ = das Christkind')),
        ('Gemessen wird er vor allem im Gebiet Niño 3.4 im mittleren Pazifik. Liegt die Meerestemperatur dort mehrere Monate mindestens ein halbes Grad über dem Mittel, spricht man von El Niño. Ab eineinhalb Grad gilt er als stark, ab zwei Grad als sehr stark.', ('Messgebiet Niño 3.4', 'ab +0,5 °C El Niño · ab +2,0 °C sehr stark')),
        ('Wichtig ist dabei: Dieser El Niño trifft auf Meere, die durch den Klimawandel ohnehin wärmer sind als früher. Das natürliche Phänomen läuft also auf einem höheren Grundniveau ab.', ('Hintergrund', 'wärmere Ozeane durch den Klimawandel')),
    ]),
    dict(titel='2. Die Zahlen: ein Rekord', szene='balken', teile=[
        ('Kommen wir zu den Zahlen. Sehr starke El Niños gibt es nur alle fünfzehn bis zwanzig Jahre. Die bekanntesten Ereignisse seht ihr hier im Vergleich.', None),
        ('Gemessen wurde jeweils der höchste Dreimonatswert im Gebiet Niño 3.4. 1997 und 98, der sogenannte Godzilla-El-Niño, kam auf 2,4 Grad. 2015 und 16 waren es 2,6 Grad.', ('1997/98 und 2015/16', '+2,4 °C und +2,6 °C')),
        ('Für 1877 und 78 gibt es nur eine Rekonstruktion aus alten Schiffsmessungen: rund 2,7 Grad. Damals lösten Dürren in Indien, China und Brasilien schwere Hungersnöte aus.', ('1877/78', 'ca. +2,7 °C (Rekonstruktion)')),
        ('Und jetzt 2026: Die Vorhersagesysteme erwarten im Mittel einen Spitzenwert von rund vier Grad im Monatsmittel. Die meisten Rechenläufe liegen zwischen 3,4 und 4,6 Grad.', ('Prognose 2026/27', 'Spitze ca. +4 °C (3,4 bis 4,6 °C)')),
    ]),
    dict(titel='2. Die Zahlen: ein Rekord', szene='zeitleiste', teile=[
        ('So schnell wie in diesem Jahr ging es selten. Im Juni hat die US-Wetterbehörde NOAA El Niño offiziell ausgerufen.', None),
        ('Anfang September lag das Meer im Gebiet Niño 3.4 schon mehr als drei Grad über dem Mittel. 1997 und 2015 waren es um diese Zeit erst etwa 1,9 Grad.', None),
        ('Am 21. September erreichte der Tageswert 3,11 Grad und brach damit den bisherigen Rekord vom November 2015 – drei Monate vor dem üblichen Höhepunkt.', None),
        ('Im Oktober gab die NOAA eine Chance von 83 Prozent für ein historisches Ereignis an, also stärker als alle El Niños seit 1950.', None),
        ('Die Erwärmung erreicht ihren Höhepunkt jetzt um den Jahreswechsel. Die Folgen werden uns aber bis weit ins Jahr 2027 begleiten, denn die weltweite Temperatur reagiert mit drei bis vier Monaten Verzögerung.', None),
    ]),
    dict(titel='3. Folgen weltweit', szene='welt', teile=[
        ('El Niño verändert die Wetterlagen auf der ganzen Erde. Einige typische Folgen sind in diesem Jahr bereits eingetreten.', None),
        ('In Indonesien herrschen Dürre und Wassermangel. Auf Java droht die Reisernte zu vertrocknen, dazu kommen Waldbrände, deren Rauch die Luftqualität stark verschlechtert.', ('Indonesien', 'Dürre, Waldbrände, Rauch')),
        ('Auch auf den Philippinen und in Australien ist es zu trocken, in Australien steigt die Gefahr von Buschfeuern.', ('Philippinen und Australien', 'Dürre, Buschfeuergefahr')),
        ('Ganz anders an der Westküste Südamerikas: Das Küstenmeer ist warm, die Fischbestände gehen zurück, und in sonst trockenen Gegenden fällt Starkregen.', ('Peru und Ecuador', 'Starkregen, weniger Fisch')),
        ('In Mittelamerika haben Panama und El Salvador im August wegen Dürre und Wassermangel den nationalen Notstand ausgerufen.', ('Mittelamerika', 'Notstand in Panama und El Salvador')),
        ('Und in Ostafrika, etwa in Somalia und im Südsudan, kommt es zu Starkregen und Überschwemmungen.', ('Ostafrika', 'Überschwemmungen')),
        ('Das Welternährungsprogramm der Vereinten Nationen rechnet mit bis zu fünfzig Millionen betroffenen Menschen.', ('Welternährungsprogramm', 'bis zu 50 Millionen Betroffene')),
    ]),
    dict(titel='4. Europa und der Odenwald', szene='europa', teile=[
        ('Und was bedeutet das für Europa und für uns hier im Odenwald? Vorweg das Wichtigste: Der Pazifik ist weit weg. Auf unser Wetter wirkt El Niño nur indirekt und schwach. Das Wetter über dem Atlantik ist für uns meist entscheidender.', ('Wichtig', 'Wirkung auf Europa nur indirekt')),
        ('Der Weg führt über die großen Druckgebiete, also vor allem das Azorenhoch und das Islandtief, und über die Nordatlantische Oszillation.', ('Atlantik', 'Azorenhoch und Islandtief')),
        ('Bei früheren starken El Niños war der Frühwinter in Mittel- und Westeuropa meist mild und nass. Der Dezember 2015 war mit 3,6 Grad im Schnitt der wärmste seit 1881.', ('Erfahrung', 'Frühwinter oft mild und nass')),
        ('Der Deutsche Wetterdienst sieht eine Chance von 66 Prozent für einen wärmeren November bis Januar und 65 Prozent für Dezember bis Februar.', ('DWD-Prognose', '66 % bzw. 65 % Chance auf wärmer')),
        ('Es gibt aber eine zweite Seite. Ein starker El Niño kann die Chance erhöhen, dass der Polarwirbel gestört wird. Dann sind im Spätwinter auch Kaltluftvorstöße möglich. Der Winter 2009 und 10 war trotz El Niño kalt und schneereich.', ('Aber', 'Spätwinter: Kaltluft möglich')),
        ('Für den Odenwald heißt das: In tiefen und mittleren Lagen fällt bei milden Lagen eher Regen als Schnee. Eine Garantie für einen bestimmten Winter gibt El Niño aber nicht.', ('Odenwald', 'eher Regen als Schnee – keine Garantie')),
        ('Spürbar werden kann El Niño auch indirekt über die Wirtschaft. Ernteausfälle bei Reis, Kaffee oder Kakao und Probleme in der Fischerei können die Weltmarktpreise steigen lassen.', ('Wirtschaft', 'mögliche höhere Lebensmittelpreise')),
    ]),
    dict(titel='Fazit', szene='odenwald', teile=[
        ('Fassen wir zusammen. El Niño ist ein natürlicher Rhythmus im Pazifik. In diesem Jahr ist er außergewöhnlich stark, und er trifft auf Meere, die ohnehin wärmer sind als früher.', None),
        ('Die Folgen sind vor allem in den Tropen zu spüren. Bei uns in Europa wirkt er nur indirekt, am ehesten über einen milderen und nasseren Frühwinter.', None),
        ('Die nächsten Lageberichte kommen vom Japanischen Wetterdienst und von der NOAA. Alle aktuellen Zahlen, Grafiken und Quellen findet ihr auf wetter badkoenig punkt de unter El Niño.', None),
        ('Was meint ihr zu diesen Werten? Schreibt es gern in die Kommentare. Danke fürs Zuschauen, und bis zum nächsten Mal bei „Max erklärt“!', None),
    ]),
]
TITEL = 'Max erklärt: Der Rekord-El-Niño 2026'
QUELLEN = 'Quellen: NOAA · JMA · WMO · DWD · Welternährungsprogramm (WFP) · wetter-badkoenig.de/elnino.html'


# ---------------------------------------------------------------- Zeichnen
def verlauf(w, h, oben, unten):
    a = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(oben)[None, None, :] * (1 - a) + np.array(unten)[None, None, :] * a).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, w, axis=1), 'RGB')


def pfeil(d, x1, y1, x2, y2, col, w=6, kopf=18):
    d.line([x1, y1, x2, y2], fill=col, width=w)
    a = math.atan2(y2 - y1, x2 - x1)
    d.polygon([(x2, y2), (x2 - kopf * math.cos(a - 0.45), y2 - kopf * math.sin(a - 0.45)), (x2 - kopf * math.cos(a + 0.45), y2 - kopf * math.sin(a + 0.45))], fill=col)


def wolke(d, x, y, k, col=(245, 248, 252)):
    for dx, dy, r in ((-0.9, 0.2, 0.55), (-0.3, -0.2, 0.75), (0.45, 0, 0.6), (0.95, 0.3, 0.45)):
        d.ellipse([x + (dx - r) * k, y + (dy - r) * k, x + (dx + r) * k, y + (dy + r) * k], fill=col)


def regen(d, x, y, k, t):
    for i in range(6):
        xx = x - k + i * k * 0.4; yy = y + ((t * 120 + i * 37) % (k * 1.6))
        d.line([xx, yy, xx - 6, yy + 18], fill=(90, 150, 230), width=3)


def sonne(d, x, y, r, t):
    for i in range(12):
        a = i * math.pi / 6 + t * 0.4
        d.line([x + math.cos(a) * r * 1.3, y + math.sin(a) * r * 1.3, x + math.cos(a) * r * 1.75, y + math.sin(a) * r * 1.75], fill=GELB, width=5)
    d.ellipse([x - r, y - r, x + r, y + r], fill=GELB)


def flamme(d, x, y, k, t):
    f = 1 + 0.12 * math.sin(t * 9 + x)
    d.polygon([(x, y - 1.3 * k * f), (x + 0.6 * k, y), (x, y + 0.35 * k), (x - 0.6 * k, y)], fill=(240, 120, 30))
    d.polygon([(x, y - 0.75 * k * f), (x + 0.32 * k, y), (x, y + 0.2 * k), (x - 0.32 * k, y)], fill=(255, 210, 60))


# vereinfachte Kontinente (Länge, Breite) – nur als Orientierung, schematisch
KONT = {
    'Amerika N': [(-168, 66), (-140, 70), (-95, 72), (-60, 60), (-55, 48), (-80, 30), (-97, 18), (-80, 8), (-105, 22), (-125, 40), (-150, 58)],
    'Amerika S': [(-80, 8), (-60, 10), (-35, -6), (-40, -22), (-58, -38), (-70, -54), (-75, -40), (-71, -18), (-81, -5)],
    'Europa/Asien': [(-10, 36), (-10, 58), (25, 71), (70, 75), (140, 72), (180, 66), (160, 55), (140, 40), (120, 22), (105, 10), (95, 20), (78, 8), (68, 24), (50, 28), (35, 32), (25, 40), (5, 43)],
    'Afrika': [(-17, 15), (-5, 36), (32, 31), (44, 12), (51, 11), (40, -15), (32, -28), (20, -35), (12, -18), (9, 4), (-8, 5)],
    'Australien': [(114, -22), (130, -12), (142, -11), (153, -28), (146, -39), (135, -34), (115, -34)],
    'Indonesien': [(95, 5), (106, -6), (118, -8), (126, -9), (141, -6), (150, -6), (140, -2), (124, 1), (110, 2)],
}


def welt_xy(lo, la, box):
    x0, y0, x1, y1 = box
    lo = lo % 360   # pazifikzentriert: 0° … 360°
    return x0 + lo / 360 * (x1 - x0), y0 + (75 - la) / 135 * (y1 - y0)


def weltkarte(d, box, anomalie=0.0, t=0.0):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=(26, 74, 128))
    if anomalie:   # Warmwasserzunge im äquatorialen Ostpazifik
        for k in range(10, 0, -1):
            f = k / 10; puls = 1 + 0.05 * math.sin(t * 2)
            cx, cy = welt_xy(-120, 0, box); w_ = (x1 - x0) * 0.18 * f * puls * anomalie; h_ = (y1 - y0) * 0.06 * f
            c = (int(80 + 160 * (1 - f) * anomalie), int(70 + 40 * f), int(120 - 80 * (1 - f)))
            d.ellipse([cx - w_, cy - h_, cx + w_ * 0.55, cy + h_], fill=c)
    for name, pts in KONT.items():
        P = [welt_xy(lo, la, box) for lo, la in pts]
        # Kontinente, die über die 180°-Kante laufen, nicht verzerren
        if max(p[0] for p in P) - min(p[0] for p in P) > (x1 - x0) * 0.6: P = [(p[0] - (x1 - x0) if p[0] > (x0 + x1) / 2 else p[0], p[1]) for p in P]
        d.polygon(P, fill=(92, 140, 92))
    d.line([x0, welt_xy(0, 0, box)[1], x1, welt_xy(0, 0, box)[1]], fill=(120, 160, 200), width=1)


def szene_bild(name, t, p):
    """t = Sekunden im Kapitel, p = Fortschritt 0…1"""
    if name == 'pazifik_glut':
        im = verlauf(W, H, (10, 20, 40), (30, 40, 70)); d = ImageDraw.Draw(im)
        weltkarte(d, (30, 90, 1010, 620), anomalie=min(1, 0.3 + t / 8), t=t)
        d.text((520, 650), 'Meerestemperatur-Abweichung (schematisch): Ostpazifik deutlich zu warm', font=F(20, False), fill=(200, 215, 235), anchor='mm')
        return im
    if name in ('walker_normal', 'walker_nino'):
        nino = name == 'walker_nino'
        im = verlauf(W, H, (120, 180, 230), (200, 228, 248)); d = ImageDraw.Draw(im)
        meer = 420
        d.rectangle([0, meer, W, H], fill=(30, 90, 150))
        # Warmwasser-Linse (wandert bei El Niño nach Osten)
        mitte = 0.25 + (0.35 * min(1, t / 6) if nino else 0)
        for k in range(8, 0, -1):
            f = k / 8
            d.ellipse([W * (mitte - 0.28 * f), meer - 10, W * (mitte + 0.28 * f), meer + 90 * f], fill=(int(120 + 120 * (1 - f)), int(90 + 40 * f), int(80 + 40 * f)))
        if not nino:   # kaltes Auftriebswasser vor Peru
            for k in range(5):
                y = meer + 140 - ((t * 40 + k * 30) % 140)
                pfeil(d, W - 330, y + 30, W - 330, y, (150, 210, 255), 4, 12)
        # Thermokline
        pts = [(x, meer + (60 + 80 * x / W if not nino else 110)) for x in range(0, W + 1, 40)]
        d.line(pts, fill=(170, 210, 240), width=3)
        d.text((40, meer + 175), 'Sprungschicht (Thermokline)', font=F(16, False), fill=(200, 225, 245))
        # Passatwinde
        st = 0.25 if nino else 1.0
        for k in range(4):
            x = W - 380 - ((t * 140 * st + k * 240) % (W - 520))
            pfeil(d, x + 120, meer - 40 - k * 6, x, meer - 40 - k * 6, (255, 255, 255), max(3, int(7 * st)), 20)
        d.text((W - 470, meer - 85), 'Passat' + (' (schwach)' if nino else ''), font=F(22), fill=(255, 255, 255))
        # Walker-Zirkulation (Aufsteigen über Warmwasser)
        xa = W * mitte
        d.arc([xa - 40, 150, W - 330, meer - 60], 180, 360, fill=(255, 255, 255), width=3)
        wolke(d, xa, 200, 70)
        regen(d, xa, 240, 60, t)
        if not nino: sonne(d, W - 360, 160, 34, t)
        else: sonne(d, 160, 160, 34, t)
        d.text((40, meer + 14), 'Indonesien / Australien', font=F(22), fill=(255, 255, 255))
        d.text((W - 300, meer + 14), 'Südamerika (Peru)', font=F(22), fill=(255, 255, 255), anchor='ra')
        d.text((520, 90), 'El-Niño-Zustand' if nino else 'Normalzustand (Walker-Zirkulation)', font=F(30), fill=DUNKEL, anchor='mm')
        return im
    if name == 'balken':
        im = verlauf(W, H, (245, 248, 252), (215, 228, 242)); d = ImageDraw.Draw(im)
        daten = [('1877/78', 2.7, '≈'), ('1972/73', 2.1, ''), ('1982/83', 2.2, ''), ('1997/98', 2.4, ''), ('2015/16', 2.6, ''), ('2023/24', 2.0, ''), ('2026/27', 4.0, 'P')]
        x0, y0, bw, sk = 110, 600, 100, 105
        d.line([x0 - 20, y0, x0 + len(daten) * 130, y0], fill=DUNKEL, width=3)
        for g in (1, 2, 3, 4):
            y = y0 - g * sk; d.line([x0 - 20, y, x0 + len(daten) * 130, y], fill=(200, 210, 225), width=1)
            d.text((x0 - 30, y), '+%d °C' % g, font=F(18, False), fill=(90, 105, 125), anchor='rm')
        y2 = y0 - 2 * sk; d.text((x0 + len(daten) * 130, y2 - 4), 'sehr stark', font=F(16, False), fill=ROT, anchor='rb')
        for i, (n, v, art) in enumerate(daten):
            wachs = max(0, min(1, (t - i * 0.8) / 1.5)); x = x0 + i * 130; h_ = v * sk * wachs
            col = ROT if art == 'P' else (BLAU if art == '' else (120, 140, 170))
            if art == 'P':
                d.rectangle([x, y0 - 4.6 * sk * wachs, x + bw, y0 - 3.4 * sk * wachs], fill=(250, 200, 190))
            d.rectangle([x, y0 - h_, x + bw, y0], fill=col)
            if wachs > 0.95:
                d.text((x + bw / 2, y0 - h_ - 18), ('ca. ' if art else '+') + ('%.1f' % v).replace('.', ',') + ' °C', font=F(20), fill=DUNKEL, anchor='mm')
            d.text((x + bw / 2, y0 + 24), n + ('\nPrognose' if art == 'P' else ''), font=F(17, art == 'P'), fill=DUNKEL, anchor='mm')
        d.text((520, 90), 'Stärke früherer El Niños (höchster Dreimonatswert, Niño 3.4)', font=F(26), fill=DUNKEL, anchor='mm')
        d.text((520, H - 22), 'Quelle: NOAA (ONI) · 1877/78 Rekonstruktion · 2026/27 Monatsmittel-Prognose, nur grob vergleichbar', font=F(16, False), fill=(90, 105, 125), anchor='mm')
        return im
    if name == 'zeitleiste':
        im = verlauf(W, H, (20, 30, 55), (40, 60, 95)); d = ImageDraw.Draw(im)
        ev = [('11. Juni', 'NOAA ruft El Niño aus'), ('Anfang Sept.', 'Niño 3.4 über +3 °C\n(1997/2015: ca. +1,9 °C)'),
              ('21. Sept.', 'Tagesrekord +3,11 °C\n(alt: +3,08 °C, 2015)'), ('8. Okt.', 'NOAA: 83 % Chance auf\nhistorisches Ereignis'), ('Nov.–Jan.', 'erwarteter Höhepunkt')]
        y = 330; d.line([80, y, W - 300, y], fill=(200, 215, 235), width=4)
        for i, (wann, was) in enumerate(ev):
            sicht = min(1, max(0, (t - i * 6) / 1.0)); x = 130 + i * (W - 460) / 4
            if sicht <= 0: continue
            r = 14 * sicht; d.ellipse([x - r, y - r, x + r, y + r], fill=ROT if i in (2, 4) else GELB)
            oben = i % 2 == 0   # abwechselnd über und unter der Linie, damit sich nichts überlappt
            d.text((x, y - 40 if oben else y + 40), wann, font=F(24), fill=(255, 255, 255), anchor='mm')
            d.multiline_text((x, y - 70 if oben else y + 70), was, font=F(18, False), fill=(220, 230, 245), anchor='md' if oben else 'ma', align='center')
        d.text((520, 95), 'El Niño 2026 – ungewöhnlich früh, ungewöhnlich stark', font=F(30), fill=(255, 255, 255), anchor='mm')
        return im
    if name == 'welt':
        im = verlauf(W, H, (10, 20, 40), (25, 35, 60)); d = ImageDraw.Draw(im)
        box = (30, 90, 1010, 630); weltkarte(d, box, anomalie=0.9, t=t)
        orte = [(110, -3, 'tro'), (140, -25, 'tro'), (125, 12, 'tro'), (-78, -8, 'reg'), (-82, 10, 'tro'), (45, 3, 'reg')]
        for i, (lo, la, art) in enumerate(orte):
            if t < 4 + i * 6: continue
            x, y = welt_xy(lo, la, box)
            if art == 'tro':
                sonne(d, x, y, 16, t); flamme(d, x + 26, y + 10, 18, t) if i in (0, 1) else None
            else:
                wolke(d, x, y - 10, 22, (200, 210, 225)); regen(d, x, y + 4, 18, t)
        d.text((520, 72), 'Typische Folgen eines starken El Niño', font=F(30), fill=(255, 255, 255), anchor='mm')
        d.text((520, 660), '☀ Dürre / Brände    ☁ Starkregen / Überschwemmung   (schematische Karte)', font=F(18, False), fill=(200, 215, 235), anchor='mm')
        return im
    if name == 'europa':
        im = verlauf(W, H, (230, 240, 250), (205, 222, 240)); d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W, H], fill=(60, 120, 180))
        land = [(560, 120), (700, 90), (900, 110), (1100, 160), (1250, 200), (1250, 720), (700, 720), (640, 600), (560, 560), (600, 470), (520, 420), (600, 330), (560, 260)]
        d.polygon(land, fill=(110, 160, 105))
        d.polygon([(470, 160), (520, 140), (530, 250), (480, 270)], fill=(110, 160, 105))   # Britische Inseln
        d.polygon([(250, 130), (360, 120), (380, 175), (280, 185)], fill=(230, 240, 245))     # Island
        # Druckgebiete (pulsierend), Westwind
        r = 70 + 6 * math.sin(t * 2)
        d.ellipse([200 - r, 440 - r, 200 + r, 440 + r], outline=(230, 60, 50), width=5); d.text((200, 440), 'H', font=F(70), fill=(230, 60, 50), anchor='mm')
        d.ellipse([320 - r, 210 - r, 320 + r, 210 + r], outline=(40, 70, 200), width=5); d.text((320, 210), 'T', font=F(70), fill=(40, 70, 200), anchor='mm')
        d.text((200, 530), 'Azorenhoch', font=F(20), fill=(255, 255, 255), anchor='mm'); d.text((320, 305), 'Islandtief', font=F(20), fill=(255, 255, 255), anchor='mm')
        for k in range(5):
            x = 380 + ((t * 120 + k * 160) % 520); pfeil(d, x, 360 + k * 6, x + 70, 350 + k * 6, (255, 255, 255), 4, 14)
        ox, oy = 870, 330   # Odenwald
        d.ellipse([ox - 9, oy - 9, ox + 9, oy + 9], fill=ROT); d.text((ox + 16, oy), 'Odenwald', font=F(22), fill=(255, 255, 255), anchor='lm')
        d.text((560, 90), 'Der Weg nach Europa: über Atlantik und Westwind', font=F(28), fill=(255, 255, 255), anchor='mm')
        return im
    # Fazit: Odenwald-Landschaft
    bg = WV.bg_land('herbst', 7).convert('RGB')
    s_ = W / bg.width; bg = bg.resize((W, int(bg.height * s_)))
    y = int((bg.height - H) * 0.55); im = bg.crop((0, y, W, y + H)).filter(ImageFilter.GaussianBlur(1.5))
    d = ImageDraw.Draw(im); d.rectangle([0, 0, W, H], fill=None)
    return im


def karte_bild(kopf, text):
    f1, f2 = F(20), F(26)
    dr0 = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    zeilen, cur = [], ''
    for w_ in text.split():
        if dr0.textlength((cur + ' ' + w_).strip(), font=f2) > 470: zeilen.append(cur); cur = w_
        else: cur = (cur + ' ' + w_).strip()
    zeilen.append(cur)
    h = 56 + len(zeilen) * 34 + 14
    im = Image.new('RGBA', (520, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 520, h], radius=18, fill=(255, 255, 255, 238))
    d.rounded_rectangle([0, 0, 8, h], radius=4, fill=ROT + (255,))
    d.text((24, 16), kopf.upper(), font=f1, fill=ROT)
    for i, z in enumerate(zeilen): d.text((24, 48 + i * 34), z, font=f2, fill=DUNKEL)
    return im


def kopfband(kap):
    im = Image.new('RGBA', (W, 54), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 50], fill=(15, 25, 45, 220)); d.rectangle([0, 50, W, 54], fill=GELB + (255,))
    d.text((20, 25), 'MAX ERKLÄRT', font=F(24), fill=GELB, anchor='lm')
    d.text((205, 25), '·  ' + kap, font=F(22, False), fill=(255, 255, 255), anchor='lm')
    d.text((W - 20, 25), 'Private Wetterstation Bad König · ' + STAND, font=F(16, False), fill=(190, 205, 225), anchor='rm')
    return im


def titelkarte(text, sub=''):
    im = verlauf(W, H, (15, 25, 45), (60, 30, 30)); d = ImageDraw.Draw(im)
    d.text((W / 2, H / 2 - 30), text, font=F(54), fill=(255, 255, 255), anchor='mm')
    if sub: d.text((W / 2, H / 2 + 40), sub, font=F(26, False), fill=GELB, anchor='mm')
    return im


# ---------------------------------------------------------------- Bauen
def main():
    tmp = tempfile.mkdtemp()
    teile = []   # (kapitelindex, text, karte, audio, dauer)
    kap = KAPITEL if not DEMO else [dict(k, teile=k['teile'][:1]) for k in KAPITEL]
    echt = True
    for ki, k in enumerate(kap):
        for ti, (txt, karte) in enumerate(k['teile']):
            a = os.path.join(tmp, 'a%02d_%02d.mp3' % (ki, ti))
            if DEMO:
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '%.2f' % max(2.0, len(txt) / 40), a], check=True); echt = False
            else:
                echt = sprich(txt, a, '-4%') and echt
            teile.append(dict(k=ki, text=txt, karte=karte, audio=a, dauer=dauer(a) + 0.45))
    # Ton zusammensetzen (mit kurzen Pausen) + leise Musik
    liste = os.path.join(tmp, 'liste.txt')
    with open(liste, 'w') as f:
        for i, t in enumerate(teile):
            p = os.path.join(tmp, 'p%03d.wav' % i)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', t['audio'], '-af', 'apad=pad_dur=0.45', '-ar', '24000', '-ac', '1', p], check=True)
            t['dauer'] = dauer(p); f.write("file '%s'\n" % p)
    vor = 3.0   # Titelkarte vorne
    still = os.path.join(tmp, 'still.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', str(vor), still], check=True)
    sprach = os.path.join(tmp, 'sprache.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', liste, '-c', 'copy', sprach], check=True)
    ton = os.path.join(tmp, 'ton.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', still, '-i', sprach, '-filter_complex', '[0][1]concat=n=2:v=0:a=1', ton], check=True)
    gesamt = dauer(ton) + 2.5
    N = int(gesamt * FPS)
    lv = pegel(ton, N) if echt else np.array([0.8 + 0.6 * math.sin(i * 1.7) for i in range(N)])
    if os.path.exists(MUSIK):
        mix = os.path.join(tmp, 'mix.wav')
        fk = ('[0:a]aformat=sample_rates=44100:channel_layouts=stereo,apad,atrim=0:%.2f,asplit[v][sc];'
              '[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.025,afade=t=in:d=2,afade=t=out:st=%.2f:d=2.5,atrim=0:%.2f[m];'
              '[m][sc]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=500[md];[v][md]amix=inputs=2:duration=first:normalize=0'
              % (gesamt, max(0, gesamt - 2.5), gesamt))
        try:
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', ton, '-stream_loop', '-1', '-i', MUSIK, '-filter_complex', fk, mix], check=True); ton = mix
        except Exception as e: print('Musik übersprungen:', e)
    # Zeitplan
    t0 = vor; plan = []
    for t in teile: t['start'] = t0; t0 += t['dauer']
    kstart = {}
    for t in teile: kstart.setdefault(t['k'], t['start'])
    # Moderator vorbereiten (verkleinert, rechts unten)
    MODS = {}
    for m in range(4):
        for b_ in (0, 1):
            for z in (0, 1, 2):
                im_ = moderator(m, b_, z, 0, 'kuehl'); MODS[(m, b_, z)] = im_.resize((int(im_.width * 0.5), int(im_.height * 0.5)), Image.LANCZOS)
    KARTEN = {}; KOPF = {}; SZ = {}
    ziel = os.path.join(FB, 'thema.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-i', ton, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
                           '-shortest', '-movflags', '+faststart', ziel], stdin=subprocess.PIPE)
    titel = titelkarte('Der Rekord-El-Niño 2026', 'Max erklärt · Private Wetterstation Bad König')
    ende = titelkarte('wetter-badkoenig.de/elnino.html', QUELLEN.replace('Quellen: ', 'Quellen: ').split(' · wetter')[0])
    rnd = random.Random(5)
    for i in range(N):
        zt = i / FPS
        if zt < vor - 0.4:
            fr = titel.copy()
        elif zt > t0 + 0.3:
            fr = ende.copy()
        else:
            akt = max([t for t in teile if t['start'] <= zt] or teile[:1], key=lambda t: t['start'])
            k = akt['k']; tk = zt - kstart[k]
            # Szene (statische Szenen zwischenspeichern, animierte jedes Bild neu)
            name = kap[k]['szene']
            if name == 'odenwald':
                if name not in SZ: SZ[name] = szene_bild(name, 0, 0)
                fr = SZ[name].copy()
            else:
                fr = szene_bild(name, tk, 0)
            fr = fr.convert('RGBA')
            if k not in KOPF: KOPF[k] = kopfband(kap[k]['titel'])
            fr.alpha_composite(KOPF[k], (0, 0))
            # Karten des Kapitels: bis zu drei neueste untereinander links unten
            sichtbar = [t for t in teile if t['k'] == k and t['karte'] and t['start'] <= zt]
            y = H - 30
            for t in reversed(sichtbar[-2:]):
                key = id(t)
                if key not in KARTEN: KARTEN[key] = karte_bild(*t['karte'])
                kb = KARTEN[key]; ein = min(1, (zt - t['start']) / 0.4)
                y -= kb.height + 10
                fr.alpha_composite(kb, (int(30 - (1 - ein) * 560), int(y)))
            # Kapitel-Einblendung beim Kapitelwechsel
            if tk < 2.2 and (k == 0 or kap[k]['titel'] != kap[k - 1]['titel']):
                a = int(230 * min(1, (2.2 - tk) / 0.5))
                ov = Image.new('RGBA', (W, 90), (15, 25, 45, a)); od = ImageDraw.Draw(ov)
                od.text((W / 2, 45), kap[k]['titel'], font=F(40), fill=(255, 255, 255, min(255, a + 25)), anchor='mm')
                fr.alpha_composite(ov, (0, H // 2 - 45))
            # Max
            lev = lv[i] if i < len(lv) else 0
            mund = 0 if lev < 0.15 else 1 if lev < 0.45 else 2 if lev < 0.8 else 3
            blink = 1 if (i % 97) < 3 else 0
            zeig = 1 if akt['karte'] and zt - akt['start'] < 2.5 else 0
            mo = MODS[(mund, blink, zeig)]
            fr.alpha_composite(mo, (W - mo.width - 20, H - mo.height + 20))
        ff.stdin.write(fr.convert('RGB').tobytes())
    ff.stdin.close(); ff.wait()
    text = ' '.join(t['text'] for t in teile)
    beitrag = '\n'.join(['🎓 Neues Themenvideo: ' + TITEL, '',
                         'Der El Niño 2026 bricht Rekorde: Was passiert gerade im Pazifik, wie stark ist er im Vergleich zu 1997 und 2015, welche Folgen hat er weltweit – und was bedeutet das für Europa und den Odenwald?', '',
                         '📖 Kapitel:'] + ['• ' + k['titel'] for i_, k in enumerate(kap) if i_ == 0 or k['titel'] != kap[i_ - 1]['titel']] +
                        ['', '📊 Alle Zahlen und Grafiken: https://wetter-badkoenig.de/elnino.html', QUELLEN.split(' · wetter')[0],
                         '', '#ElNiño #Klima #Wetter #Odenwald #MaxErklärt'])
    json.dump({'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'titel': TITEL, 'dauer': round(gesamt, 1),
               'stimme': echt, 'skript': text, 'beitrag': beitrag,
               'kapitel': [dict(zeit=round(kstart[i_]), titel=k['titel']) for i_, k in enumerate(kap) if i_ == 0 or k['titel'] != kap[i_ - 1]['titel']]}, open(os.path.join(FB, 'thema.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('Themenvideo fertig: %.0f s' % gesamt)


if __name__ == '__main__':
    main()
