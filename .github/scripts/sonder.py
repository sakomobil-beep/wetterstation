#!/usr/bin/env python3
"""Wetter-Sondermeldungen für Facebook (Gewitter, Schnee, Glätte, Sturm, Starkregen, Hitze, strenger Frost, Nebel).
Prüft amtliche DWD-Warnungen (Bright Sky) und die ICON-Vorhersage (Open-Meteo) für die nächsten 24 Stunden.
Ausgabe: fb/sonder.json + fb/sonder-<typ>.jpg – werden in der Zentrale (Bereich Facebook) zum Teilen angeboten.
Test ohne Internet:  python sonder.py --demo"""
import json, os, sys, glob, datetime as dt
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from fb_post import get, font, icon, LAT, LON, TZ, OUT, TAGE

ARTEN = {  # typ: (Titel, Emoji, Wettercode fürs Symbol, Bandfarbe, Hashtag, Schlagwörter im DWD-Ereignis)
    'gewitter':   ('Gewitter',   '⛈️', 95, (183, 28, 28),  '#Gewitter',   ('GEWITTER',)),
    'schnee':     ('Schneefall',         '❄️', 73, (30, 90, 170),  '#Schnee',     ('SCHNEE',)),
    'glaette':    ('Glätte',             '🧊', 73, (60, 80, 160),  '#Glätte',     ('GLÄTTE', 'GLATTEIS', 'GLAETTE')),
    'sturm':      ('Sturm',              '🌪️', 3,  (120, 60, 160), '#Sturm',      ('WIND', 'STURM', 'ORKAN')),
    'starkregen': ('Starkregen',         '🌧️', 63, (20, 110, 160), '#Starkregen', ('REGEN',)),
    'hitze':      ('Hitze',              '🥵', 0,  (220, 90, 20),  '#Hitze',      ('HITZE',)),
    'frost':      ('Strenger Frost',     '🥶', 0,  (40, 100, 180), '#Frost',      ('FROST',)),
    'nebel':      ('Dichter Nebel',      '🌫️', 45, (100, 110, 125), '#Nebel',     ('NEBEL',)),
}
DWD_STUFE = {'minor': 'Stufe 1 – Wetterwarnung', 'moderate': 'Stufe 2 – Markantes Wetter',
             'severe': 'Stufe 3 – Unwetter', 'extreme': 'Stufe 4 – Extremes Unwetter'}


def uhr(iso):
    t = dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(TZ)
    heute = dt.datetime.now(TZ).date()
    tag = 'heute' if t.date() == heute else 'morgen' if t.date() == heute + dt.timedelta(days=1) else TAGE[t.weekday()]
    return '%s %s Uhr' % (tag, t.strftime('%H:%M'))


def laden():
    alerts, ids = [], set()
    for la, lo in ((LAT, LON), (49.567, 8.976), (49.678, 9.004)):   # ganzer Odenwaldkreis: Bad König, Oberzent, Michelstadt
        for a in get('https://api.brightsky.dev/alerts?lat=%s&lon=%s' % (la, lo)).get('alerts') or []:
            k = a.get('alert_id') or a.get('id') or (a.get('headline_de'), a.get('onset'))
            if k not in ids: ids.add(k); alerts.append(a)
    om = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=icon_seamless'
             '&hourly=temperature_2m,weather_code,precipitation,snowfall,wind_gusts_10m,visibility'
             '&forecast_days=2&timezone=Europe%%2FBerlin' % (LAT, LON))
    return alerts, om['hourly']


def demo():
    j = dt.datetime.now(dt.timezone.utc)
    al = [dict(event_de='SCHWERES GEWITTER mit STARKREGEN', severity='severe', headline_de='Amtliche UNWETTERWARNUNG vor SCHWEREM GEWITTER',
               onset=(j + dt.timedelta(hours=3)).isoformat(), expires=(j + dt.timedelta(hours=7)).isoformat(),
               instruction_de='Schließen Sie Fenster und Türen! Sichern Sie Gegenstände im Freien.')]
    H = {'time': [], 'temperature_2m': [], 'weather_code': [], 'precipitation': [], 'snowfall': [], 'wind_gusts_10m': [], 'visibility': []}
    t0 = dt.datetime.now(TZ).replace(minute=0, second=0, microsecond=0)
    for k in range(48):
        H['time'].append((t0 + dt.timedelta(hours=k)).strftime('%Y-%m-%dT%H:00'))
        H['temperature_2m'].append(-1 if k > 30 else 4); H['weather_code'].append(95 if 4 <= k <= 6 else 73 if k > 30 else 3)
        H['precipitation'].append(6 if 4 <= k <= 6 else 0.5); H['snowfall'].append(0.8 if k > 30 else 0)
        H['wind_gusts_10m'].append(70 if k == 5 else 30); H['visibility'].append(20000)
    return al, H


def erkennen(alerts, H):
    gefunden = {}
    def add(typ, quelle, details, zeit=None, stufe=None, rat=None):
        g = gefunden.setdefault(typ, dict(typ=typ, quellen=[], details=[], zeit=None, stufe=None, rat=None))
        if quelle not in g['quellen']: g['quellen'].append(quelle)
        for d in details:
            if d not in g['details']: g['details'].append(d)
        g['zeit'] = g['zeit'] or zeit; g['stufe'] = g['stufe'] or stufe; g['rat'] = g['rat'] or rat
    # 1) amtliche DWD-Warnungen
    for a in alerts:
        ev = (a.get('event_de') or '').upper()
        for typ, (_, _, _, _, _, worte) in ARTEN.items():
            if any(w in ev for w in worte):
                if typ == 'frost' and 'STRENG' not in ev: continue      # normaler Frost kommt schon im Tagesbeitrag
                zeit = None
                if a.get('onset') and a.get('expires'): zeit = 'Gültig von %s bis %s' % (uhr(a['onset']), uhr(a['expires']))
                add(typ, 'dwd', ['DWD: ' + (a.get('headline_de') or a.get('event_de'))], zeit, DWD_STUFE.get(a.get('severity')),
                    (a.get('instruction_de') or '').split('\n')[0][:220] or None)
                break                                                   # eine Warnung = eine Meldung
    # 2) Vorhersage der nächsten 24 Stunden
    jetzt = dt.datetime.now(TZ).strftime('%Y-%m-%dT%H:00')
    idx = [i for i, t in enumerate(H['time']) if t >= jetzt][:24]
    def wert(k, i): return H[k][i] if H[k][i] is not None else 0
    def ab(i): t = dt.datetime.fromisoformat(H['time'][i]); return ('heute' if t.date() == dt.datetime.now(TZ).date() else 'morgen') + ' ab %d Uhr' % t.hour
    gw = [i for i in idx if wert('weather_code', i) >= 95]
    if gw: add('gewitter', 'modell', ['Gewitter möglich %s' % ab(gw[0])])
    sn = sum(wert('snowfall', i) for i in idx)
    if sn >= 1: add('schnee', 'modell', ['Bis zu %.0f cm Neuschnee in 24 Stunden' % sn, 'Schneefall %s' % ab(next(i for i in idx if wert('snowfall', i) > 0))])
    gl = [i for i in idx if wert('temperature_2m', i) <= 0.5 and wert('precipitation', i) > 0.1 and wert('snowfall', i) == 0]
    if gl: add('glaette', 'modell', ['Gefrierender Regen / Glätte möglich %s' % ab(gl[0])])
    gu = max((wert('wind_gusts_10m', i) for i in idx), default=0)
    if gu >= 65: add('sturm', 'modell', ['Sturmböen bis %d km/h' % round(gu)])
    rr = sum(wert('precipitation', i) for i in idx)
    rmax = max((wert('precipitation', i) for i in idx), default=0)
    if rr >= 25 or rmax >= 10: add('starkregen', 'modell', ['Bis zu %.0f l/m² in 24 Stunden' % rr])
    tx = max((wert('temperature_2m', i) for i in idx), default=0); tn = min((wert('temperature_2m', i) for i in idx), default=0)
    if tx >= 30: add('hitze', 'modell', ['Bis zu %.0f °C' % tx])
    if tn <= -8: add('frost', 'modell', ['Strenger Frost bis %.0f °C' % tn])
    nb = [i for i in idx if H['visibility'][i] is not None and H['visibility'][i] < 200]
    if nb: add('nebel', 'modell', ['Sichtweiten unter 200 m %s' % ab(nb[0])])
    return list(gefunden.values())


def text(m):
    titel, emo, _, _, tag, _ = ARTEN[m['typ']]
    z = ['%s WETTER-SONDERMELDUNG für den Odenwald: %s %s' % (emo, titel, emo), '']
    if m['stufe']: z.append('⚠️ ' + m['stufe'])
    z += ['• ' + d for d in m['details'][:4]]
    if m['zeit']: z.append('🕒 ' + m['zeit'])
    if m['rat']: z += ['', '👉 ' + m['rat']]
    if 'dwd' not in m['quellen']: z += ['', '(Hinweis nach Vorhersagemodell – noch keine amtliche Warnung)']
    z += ['', 'Live-Werte, Radar & Warnungen 👉 https://wetter-badkoenig.de', '#Odenwald #Odenwaldkreis #BadKönig #Wetter %s #Unwetter' % tag]
    return '\n'.join(z)


def zeilen(dr, t, f, breite):
    w, out = '', []
    for wort in t.split():
        if dr.textlength((w + ' ' + wort).strip(), font=f) > breite and w: out.append(w); w = wort
        else: w = (w + ' ' + wort).strip()
    return out + ([w] if w else [])


def bild(m, path):
    titel, _, code, farbe, _, _ = ARTEN[m['typ']]
    W = H = 1200
    im = Image.new('RGB', (W, H)); dr = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; dr.line([(0, y), (W, y)], fill=tuple(int(c * (0.55 + 0.25 * t)) for c in farbe))
    def ct(t, y, f, fill=(255, 255, 255)):
        w = dr.textlength(t, font=f); dr.text(((W - w) / 2 + 2, y + 3), t, font=f, fill=(20, 20, 30)); dr.text(((W - w) / 2, y), t, font=f, fill=fill)
    dr.rectangle([0, 0, W, 110], fill=(250, 200, 40))
    f = font(52, True); t = 'WETTER-SONDERMELDUNG'; w = dr.textlength(t, font=f); dr.text(((W - w) / 2, 26), t, font=f, fill=(60, 30, 10))
    ct('Odenwald · Private Wetterstation Bad König', 140, font(38))
    ct(titel, 200, font(84, True))
    dr.rounded_rectangle([W / 2 - 150, 320, W / 2 + 150, 560], radius=40, fill=(255, 255, 255))
    icon(dr, W / 2, 430 if m['typ'] != 'sturm' else 400, 190, code)
    if m['typ'] == 'sturm':
        for k, (x0, x1) in enumerate(((-110, 90), (-80, 120), (-120, 60))):
            yy = 480 + k * 24; dr.line([W / 2 + x0, yy, W / 2 + x1, yy], fill=(120, 60, 160), width=10)
    if m['typ'] in ('hitze', 'frost'):
        f = font(60, True); t = 'HEISS' if m['typ'] == 'hitze' else 'KALT'; w = dr.textlength(t, font=f)
        dr.text((W / 2 - w / 2, 505), t, font=f, fill=(220, 80, 20) if m['typ'] == 'hitze' else (40, 100, 200))
    st = m['stufe'] or ('Amtliche DWD-Warnung' if 'dwd' in m['quellen'] else 'Hinweis laut Vorhersage')
    def inhalt(zeichnen, y):
        f = font(36, True); w = dr.textlength(st, font=f)
        if zeichnen: dr.text(((W - w) / 2, y), st, font=f, fill=farbe)
        y += 60; f = font(34)
        for d in m['details'][:4] + ([m['zeit']] if m['zeit'] else []):
            for z in zeilen(dr, d, f, W - 200)[:2]:
                if y > 1000: break
                w = dr.textlength(z, font=f)
                if zeichnen: dr.text(((W - w) / 2, y), z, font=f, fill=(40, 50, 70))
                y += 46
            y += 10
        return y
    hoch = inhalt(False, 0) + 50
    y0 = 600 + max(0, (450 - hoch) // 2)
    dr.rounded_rectangle([60, y0, W - 60, y0 + hoch], radius=32, fill=(255, 255, 255))
    inhalt(True, y0 + 30)
    ct('wetter-badkoenig.de', H - 110, font(54, True))
    im.save(path, quality=90)


def main():
    alerts, H = demo() if '--demo' in sys.argv else laden()
    meld = erkennen(alerts, H)
    os.makedirs(OUT, exist_ok=True)
    for f in glob.glob(os.path.join(OUT, 'sonder-*.jpg')): os.remove(f)
    aus = []
    for m in sorted(meld, key=lambda m: ('dwd' not in m['quellen'], list(ARTEN).index(m['typ']))):
        bild(m, os.path.join(OUT, 'sonder-%s.jpg' % m['typ']))
        aus.append(dict(typ=m['typ'], titel=ARTEN[m['typ']][0], emoji=ARTEN[m['typ']][1], amtlich='dwd' in m['quellen'],
                        stufe=m['stufe'], bild='sonder-%s.jpg' % m['typ'], text=text(m)))
    neu = dict(erstellt=dt.datetime.now(TZ).isoformat(timespec='minutes'), meldungen=aus)
    p = os.path.join(OUT, 'sonder.json')
    try:  # nur neu schreiben, wenn sich inhaltlich etwas geändert hat (spart Commits)
        alt = json.load(open(p, encoding='utf-8'))
        if alt.get('meldungen') == aus: return
    except Exception:
        pass
    json.dump(neu, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(neu, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
