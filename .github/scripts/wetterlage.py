#!/usr/bin/env python3
"""Wetterlage für Max (22.11.2026, Kingman: Ideen 1 + 2 + vorsichtige Namen).
1) Luftdruck über Europa (Open-Meteo, ein Abruf, ca. 90 Punkte) -> wo liegen Hoch und Tief?
2) Wetterlage-Text des DWD für Deutschland (opendata.dwd.de, VHDL54_DWOG) -> Strömung und Luftmasse, in Max' eigenen Worten.
3) Namen von Hoch/Tief nur, wenn der DWD-Text sie selbst nennt UND sie in der Namensliste der FU Berlin stehen.
Alles mit Zeitlimit; bei jedem Fehler kommt einfach kein Wetterlage-Satz."""
import json, re, urllib.request

def _hole(url, t=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de'}), timeout=t) as r: return r.read()


def gebiet(la, lo):
    """Grobe Region mit Präposition („über der Nordsee“)."""
    if la >= 62 and lo < 5: return 'über dem Nordmeer'
    if la >= 57 and 5 <= lo < 30: return 'über Skandinavien'
    if la >= 55 and lo >= 30: return 'über Russland'
    if 50 <= la < 62 and lo < -12: return 'über dem Atlantik'
    if 50 <= la < 60 and -12 <= lo < -1: return 'über den Britischen Inseln'
    if 52 <= la < 58 and -1 <= lo < 9: return 'über der Nordsee'
    if 53 <= la < 58 and 9 <= lo < 30: return 'über der Ostsee'
    if 47 <= la < 53 and 5 <= lo < 16: return 'über Deutschland'
    if 45 <= la < 50 and -5 <= lo < 5: return 'über Frankreich'
    if 43 <= la < 50 and lo < -5: return 'über der Biskaya' if lo > -12 else 'über dem Atlantik'
    if 45 <= la < 55 and 16 <= lo < 30: return 'über Osteuropa'
    if 45 <= la < 55 and lo >= 30: return 'über der Ukraine und Russland'
    if 45 <= la < 47 and 5 <= lo < 16: return 'über den Alpen'
    if la < 45 and lo < -15: return 'bei den Azoren'
    if la < 45 and lo < 0: return 'über Spanien und Portugal'
    if la < 45 and lo < 20: return 'über dem Mittelmeer'
    if la < 45: return 'über dem Balkan'
    return 'über Europa'


def druck_zentren():
    """Tiefstes und höchstes Druckzentrum über Europa (aktuell, Meereshöhe)."""
    la, lo = [], []
    for y in range(36, 69, 6):   # 6 x 8 = 48 Punkte (Open-Meteo zählt jeden Punkt als Abruf)
        for x in range(-30, 41, 10): la.append(y); lo.append(x)
    d = json.loads(_hole('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&current=pressure_msl' % (','.join(map(str, la)), ','.join(map(str, lo)))))
    P = sorted((x['current']['pressure_msl'], x['latitude'], x['longitude']) for x in d if x.get('current', {}).get('pressure_msl'))
    return P[0], P[-1]


def dwd_text():
    t = _hole('https://opendata.dwd.de/weather/text_forecasts/html/VHDL54_DWOG_LATEST_html').decode('latin1')
    t = re.sub(r'<[^>]+>', ' ', t); t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^.*?Letzte Aktualisierung: [\d.]+, [\d.]+ Uhr\s*', '', t)
    return re.split(r'\s[A-ZÄÖÜ/ ]{5,}:', t)[0].strip()   # nur der Wetterlage-Absatz vor „FROST/GLÄTTE:“ usw.


def fu_namen():
    n = set()
    for k in ('hoch', 'tief'):
        t = _hole('https://page.met.fu-berlin.de/wetterpate/static/%s_aktuell.html' % k).decode('utf-8', 'ignore')
        n |= {(k, x) for x in re.findall(r'<td>\s*([A-ZÄÖÜ][a-zäöüß]+)\s*</td>', t)}
    return n


RICHTUNG = [('nordwestlich', 'aus Nordwest'), ('südwestlich', 'aus Südwest'), ('nordöstlich', 'aus Nordost'), ('südöstlich', 'aus Südost'),
            ('nördlich', 'aus Norden'), ('südlich', 'aus Süden'), ('westlich', 'aus Westen'), ('östlich', 'aus Osten')]
LUFT = [('Polarluft', 'kalte Polarluft'), ('Arktikluft', 'sehr kalte Luft aus der Arktis'), ('Kaltluft', 'kalte Luft'), ('Meeresluft', 'feuchte Meeresluft'),
        ('Mittelmeer', 'milde Luft vom Mittelmeer'), ('subtropisch', 'sehr milde Luft aus dem Süden'), ('Warmluft', 'mildere Luft'), ('Festlandsluft', 'trockene Festlandsluft')]


def wetterlage_satz(rnd=None):
    """Ein bis zwei Sätze zur Wetterlage oder '' (nie ein Fehler)."""
    teile = []
    try: tief, hoch = druck_zentren()
    except Exception as e: print('Wetterlage: Druckkarte nicht abrufbar:', e); tief = hoch = None
    try: txt = dwd_text()
    except Exception as e: print('Wetterlage: DWD-Text nicht abrufbar:', e); txt = ''
    print('Wetterlage DWD:', txt[:300])
    # Namen nur, wenn der DWD-Text sie nennt und die FU-Liste sie kennt
    name = {}
    try:
        gen = set(re.findall(r'\b(Hoch|Tief)\s+([A-ZÄÖÜ][a-zäöüß]{2,})', txt))
        if gen:
            fu = fu_namen()
            for art, n in gen:
                if (art.lower(), n) in fu: name[art] = n
    except Exception as e: print('Wetterlage: Namen nicht prüfbar:', e)
    h_ok = hoch and hoch[0] >= 1025; t_ok = tief and tief[0] <= 1005
    H = ('Hoch %s' % name['Hoch']) if 'Hoch' in name else 'einem Hoch'
    T = ('Tief %s' % name['Tief']) if 'Tief' in name else 'einem Tief'
    H1 = H if 'Hoch' in name else 'ein Hoch'; T1 = T if 'Tief' in name else 'ein Tief'
    if h_ok and t_ok and gebiet(*hoch[1:]) != gebiet(*tief[1:]):
        teile.append('Zwischen %s %s und %s %s' % (H, gebiet(*hoch[1:]), T, gebiet(*tief[1:])))
    elif h_ok: teile.append('%s %s bestimmt das Wetter' % (H1[0].upper() + H1[1:], gebiet(*hoch[1:])))
    elif t_ok: teile.append('%s %s bestimmt das Wetter' % (T1[0].upper() + T1[1:], gebiet(*tief[1:])))
    r = next((b for a, b in RICHTUNG if re.search(a + r'\w* Strömung', txt)), None)
    l = next((b for a, b in LUFT if a in txt), None)
    if teile and teile[0].startswith('Zwischen'):
        s = teile[0] + (' kommt mit einer Strömung %s %s zu uns.' % (r, l) if r and l else ' strömt %s zu uns.' % l if l else ' liegt Deutschland.' if not r else ' weht der Wind %s zu uns.' % r)
    elif teile:
        s = teile[0] + ('. Mit einer Strömung %s kommt %s zu uns.' % (r, l) if r and l else '.')
    elif r and l: s = 'Mit einer Strömung %s kommt %s zu uns.' % (r, l)
    else: return ''
    if re.search(r'Hochdruckeinfluss|Hochdruckgebiet', txt) and 'Hoch' not in s: s += ' Bei uns sorgt Hochdruck für ruhiges Wetter.'
    elif re.search(r'Tiefausläufer|Tiefdruck|Front', txt) and 'Tief' not in s and not re.search(r'streif', txt): s += ' Dazu ziehen Tiefausläufer durch.'
    return 'Zur Wetterlage: ' + s


if __name__ == '__main__': print(wetterlage_satz())
