#!/usr/bin/env python3
"""Erstellt jeden Morgen das Facebook-Vorhersagebild + Text für die Private Wetterstation Bad König.
Ausgabe: fb/post.jpg, fb/post.txt, fb/post.json
Quellen: Präzisions-Vorhersage wie auf der Website (0–48 h DWD ICON-D2 + MOSMIX, lernende Korrektur mit Messwerten der Station IBADKN33), danach DWD ICON (Open-Meteo),
amtliche Warnungen des DWD (Bright Sky)."""
import json, os, sys, math, statistics, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

LAT, LON = 49.750, 9.017
STATION, WU_KEY = 'IBADKN33', '43a8f308d89b471ba8f308d89b671b69'
TZ = ZoneInfo('Europe/Berlin')
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'fb')
DEMO = '--demo' in sys.argv
TAGE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de facebook-bot'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


# ---------- Daten ----------
def load():
    om = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=icon_seamless'
             '&hourly=temperature_2m,weather_code,precipitation_probability,cloud_cover,wind_speed_10m&past_days=5&forecast_days=8'
             '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,'
             'precipitation_probability_max,wind_gusts_10m_max,sunshine_duration,snowfall_sum&timezone=Europe%%2FBerlin' % (LAT, LON))
    # Stationskorrektur: Median-Abweichung Station – Modell der letzten Tage (Tag/Nacht getrennt)
    bias = {'tag': 0.0, 'nacht': 0.0}
    try:
        st = get('https://api.weather.com/v2/pws/observations/hourly/7day?stationId=%s&format=json&units=m&apiKey=%s'
                 % (STATION, WU_KEY)).get('observations') or []
        idx = {t: i for i, t in enumerate(om['hourly']['time'])}
        d, n = [], []
        for o in st:
            t = dt.datetime.fromtimestamp(o['epoch'], TZ).replace(minute=0).strftime('%Y-%m-%dT%H:00')
            i = idx.get(t); v = (o.get('metric') or {}).get('tempAvg')
            if i is None or v is None or om['hourly']['temperature_2m'][i] is None: continue
            h = int(t[11:13]); diff = v - om['hourly']['temperature_2m'][i]
            (d if 9 <= h <= 18 else n).append(diff)
        if len(d) >= 8: bias['tag'] = max(-3, min(3, statistics.median(d)))
        if len(n) >= 8: bias['nacht'] = max(-3, min(3, statistics.median(n)))
    except Exception as e:
        print('Stationskorrektur nicht möglich:', e)
        st = []
    nah, wf = praezision(om, st)
    stunden = korrigierte_stunden(om, st, nah)
    warn = []
    try:
        al = get('https://api.brightsky.dev/alerts?lat=%s&lon=%s' % (LAT, LON)).get('alerts') or []
        for a in al:
            if a.get('severity') in ('moderate', 'severe', 'extreme') or a.get('event_de'):
                warn.append(a.get('headline_de') or a.get('event_de'))
    except Exception as e:
        print('Warnungen nicht abrufbar:', e)
    today = dt.datetime.now(TZ).date().isoformat()
    D = om['daily']; i0 = D['time'].index(today)
    days = []
    Hh = om['hourly']
    for i in range(i0, min(i0 + 7, len(D['time']))):
        def teil(a, b, _d=D['time'][i]):
            v = [Hh['precipitation_probability'][k] or 0 for k, t in enumerate(Hh['time']) if t[:10] == _d and a <= int(t[11:13]) < b]
            return max(v) if v else 0
        days.append(dict(
            datum=dt.date.fromisoformat(D['time'][i]),
            code=(2 if D['weather_code'][i] == 3 and (D['sunshine_duration'][i] or 0) >= 4 * 3600 else 1 if D['weather_code'][i] in (2, 3) and (D['sunshine_duration'][i] or 0) >= 7 * 3600 else D['weather_code'][i]),
            tmax=round(max(stunden[D['time'][i]]) if stunden.get(D['time'][i]) else D['temperature_2m_max'][i] + bias['tag']),
            tmin=round(min(stunden[D['time'][i]]) if stunden.get(D['time'][i]) else D['temperature_2m_min'][i] + bias['nacht']),
            regen=tagwert(nah, D['time'][i], 'regen', sum, D['precipitation_sum'][i] or 0),
            rp=D['precipitation_probability_max'][i] or 0,
            boe=tagwert(nah, D['time'][i], 'boe', max, D['wind_gusts_10m_max'][i] or 0, wf),
            sonne=(D['sunshine_duration'][i] or 0) / 3600,
            schnee=D['snowfall_sum'][i] or 0, rp_vm=teil(6, 12), rp_nm=teil(12, 18), rp_ab=teil(18, 24)))
        # Abgleich: Wettersymbol „Regen/Niesel/Schauer“, aber laut Präzisions-Vorhersage kaum Regen → kein Regen
        t_ = days[-1]
        if t_['code'] in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82) and t_['regen'] < 0.3 and t_['rp'] < 30:
            t_['code'] = 1 if t_['sonne'] >= 7 else 2 if t_['sonne'] >= 4 else 3
    sicherheit(days)
    return days, warn


def sicherheit(days):
    """Präzision 2.0: Wie einig sind sich ICON-D2, AROME, ECMWF und ICON-EU? -> d['sicher'] = hoch / mittel / gering,
    d['modelle_nass'] = Anteil der Modelle mit Regen (>= 1 mm). Gleiche Schwellen wie auf der Website."""
    try:
        mm = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=icon_d2,meteofrance_arome_france_hd,ecmwf_ifs025,icon_eu'
                 '&daily=temperature_2m_max,precipitation_sum&forecast_days=8&timezone=Europe%%2FBerlin' % (LAT, LON))['daily']
    except Exception as e:
        print('Modellvergleich nicht möglich:', e); return
    for d in days:
        tag = d['datum'].isoformat()
        if tag not in mm['time']: continue
        i = mm['time'].index(tag)
        tx, rr = [], []
        for m in ('icon_d2', 'meteofrance_arome_france_hd', 'ecmwf_ifs025', 'icon_eu'):
            a = (mm.get('temperature_2m_max_' + m) or [None] * (i + 1))[i]
            b = (mm.get('precipitation_sum_' + m) or [None] * (i + 1))[i]
            if a is not None: tx.append(a)
            if b is not None: rr.append(b)
        if len(tx) < 2: continue
        streu = statistics.pstdev(tx)
        p = sum(1 for x in rr if x >= 1) / len(rr) if rr else 0
        dis = 4 * p * (1 - p)
        d['sicher'] = 'gering' if streu >= 2.2 or dis >= 0.95 else 'mittel' if streu >= 1.2 or dis >= 0.7 else 'hoch'
        d['modelle_nass'] = round(p, 2)


def praezision(om, st):
    """Wie die Präzisions-Vorhersage der Website: für 0–48 h DWD ICON-D2 (70 %) + DWD MOSMIX (30 %),
    Regen 60/40, Böen mit dem an der Station gelernten Windfaktor. Liefert {'JJJJ-MM-TTTHH': {...}}, Windfaktor."""
    nah, wf = {}, 1.0
    try:
        d2 = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=icon_d2'
                 '&hourly=temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m&past_days=1&forecast_days=2'
                 '&timezone=Europe%%2FBerlin' % (LAT, LON))['hourly']
    except Exception as e:
        print('ICON-D2 nicht abrufbar:', e); return nah, wf
    mos = {}
    try:
        h = dt.datetime.now(TZ).date()
        for r in get('https://api.brightsky.dev/weather?lat=%s&lon=%s&date=%s&last_date=%s&tz=Europe/Berlin'
                     % (LAT, LON, (h - dt.timedelta(days=1)).isoformat(), (h + dt.timedelta(days=2)).isoformat())).get('weather') or []:
            mos[r['timestamp'][:13]] = r
    except Exception as e:
        print('MOSMIX nicht abrufbar:', e)
    def mix(a, b, wa):
        if a is None: return b
        return a if b is None else wa * a + (1 - wa) * b
    for k, t in enumerate(d2['time']):
        m = mos.get(t[:13], {})
        nah[t[:13]] = dict(t2=d2['temperature_2m'][k], tm=m.get('temperature'),
                           regen=mix(d2['precipitation'][k], m.get('precipitation'), 0.6),
                           boe=mix(d2['wind_gusts_10m'][k], m.get('wind_gust_speed'), 0.7))
    # Windfaktor: Stationswind / Modellwind der letzten 7 Tage (wie auf der Website)
    try:
        idx = {t[:13]: i for i, t in enumerate(om['hourly']['time'])}
        sw = mw = 0
        for o in st:
            i = idx.get(dt.datetime.fromtimestamp(o['epoch'], TZ).strftime('%Y-%m-%dT%H'))
            v = (o.get('metric') or {}).get('windspeedAvg'); mv = om['hourly']['wind_speed_10m'][i] if i is not None else None
            if v is not None and mv is not None and mv > 3: sw += v; mw += mv
        if mw > 20: wf = max(0.4, min(1.5, sw / mw))
    except Exception:
        pass
    return nah, wf


def tagwert(nah, tag, feld, fn, ersatz, faktor=1.0):
    """Tageswert aus den Präzisionsstunden – nur wenn der Tag komplett abgedeckt ist, sonst Tageswert des Modells."""
    v = [x[feld] for t, x in nah.items() if t[:10] == tag and x[feld] is not None]
    if len(v) < 24: return ersatz
    return round(fn(v) * faktor, 1)


def korrigierte_stunden(om, st, nah=None):
    """Stündliche Temperaturen je Tag: vergangene Stunden = Messwerte der Station,
    künftige = Modell + gelernte Korrektur nach Wetterlage (data/lernen-bias.json) + Anker am aktuellen Messwert."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from lernen import lage, block
        B = json.load(open(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'lernen-bias.json'), encoding='utf-8'))
        if B.get('tage', 0) < 3: return {}
    except Exception as e:
        print('Keine gelernte Korrektur:', e); return {}
    Hh = om['hourly']; jetzt = dt.datetime.now(TZ)
    gemessen = {}
    for o in st:
        v = (o.get('metric') or {}).get('tempAvg')
        if v is not None: gemessen[dt.datetime.fromtimestamp(o['epoch'], TZ).strftime('%Y-%m-%dT%H')] = v
    try:
        cur = get('https://api.weather.com/v2/pws/observations/current?stationId=%s&format=json&units=m&apiKey=%s' % (STATION, WU_KEY))
        jetzt_t = cur['observations'][0]['metric']['temp']
    except Exception:
        jetzt_t = None
    out, anker = {}, None
    for k, t in enumerate(Hh['time']):
        m = Hh['temperature_2m'][k]
        if m is None: continue
        zt = dt.datetime.fromisoformat(t).replace(tzinfo=TZ)
        if zt <= jetzt - dt.timedelta(hours=1) and t[:13] in gemessen:
            v = gemessen[t[:13]]
        else:
            b_ = B['bias'][lage(Hh['cloud_cover'][k], Hh['wind_speed_10m'][k])][block(zt.hour)]
            p_ = (nah or {}).get(t[:13]) or {}
            if p_.get('t2') is not None:   # 0–48 h: ICON-D2 korrigiert 70 % + MOSMIX 30 %
                v = p_['t2'] + b_ if p_.get('tm') is None else 0.7 * (p_['t2'] + b_) + 0.3 * p_['tm']
            else:
                v = m + b_
            dh = (zt - jetzt).total_seconds() / 3600
            if anker is None and jetzt_t is not None and dh >= -1:
                anker = max(-8, min(8, jetzt_t - v))
            if anker is not None:
                v += anker * math.exp(-max(0, dh) / 5)
        out.setdefault(t[:10], []).append(v)
    return out


def demo():
    t = dt.datetime.now(TZ).date()
    base = [dict(code=2, tmax=11, tmin=-2, regen=0, rp=10, boe=25, sonne=5.2, schnee=0, rp_vm=0, rp_nm=10, rp_ab=5),
            dict(code=61, tmax=9, tmin=3, regen=4.2, rp=80, boe=48, sonne=0.5, schnee=0, rp_vm=20, rp_nm=80, rp_ab=60)]
    return [dict(base[k % 2], datum=t + dt.timedelta(days=k)) for k in range(7)], (['Amtliche WARNUNG vor FROST'] if '--demo-warn' in sys.argv else [])


# ---------- Wettertexte ----------
def wort(c):
    if c == 0: return 'sonnig'
    if c in (1, 2): return 'heiter bis wolkig'
    if c == 3: return 'bedeckt'
    if c in (45, 48): return 'neblig'
    if 51 <= c <= 57: return 'Nieselregen'
    if 61 <= c <= 67: return 'Regen'
    if 71 <= c <= 77 or c in (85, 86): return 'Schnee'
    if 80 <= c <= 82: return 'Schauer'
    if c >= 95: return 'Gewitter'
    return 'wechselhaft'


def emoji(c):
    return {'sonnig': '☀️', 'heiter bis wolkig': '⛅', 'bedeckt': '☁️', 'neblig': '🌫️', 'Nieselregen': '🌦️',
            'Regen': '🌧️', 'Schnee': '❄️', 'Schauer': '🌦️', 'Gewitter': '⛈️'}.get(wort(c), '🌤️')


def hinweise(d):
    h = []
    if d['tmin'] <= 0: h.append('Frost bis %d °C – Scheiben kratzen!' % d['tmin'])
    elif d['tmin'] <= 3: h.append('Bodenfrost möglich')
    if d['boe'] >= 60: h.append('Sturmböen bis %d km/h' % round(d['boe']))
    elif d['boe'] >= 45: h.append('Windböen bis %d km/h' % round(d['boe']))
    if d['regen'] >= 10: h.append('viel Regen (%.0f l/m²)' % d['regen'])
    return h


def text(days, warn):
    a, b = days[:2]
    gruss = 'Guten Morgen Bad König! %s' % emoji(a['code'])
    zeilen = [gruss, '',
              'Heute (%s): %s, %d bis %d °C%s.' % (TAGE[a['datum'].weekday()], wort(a['code']), a['tmin'], a['tmax'],
                                                    ', Regenrisiko %d %%' % a['rp'] if a['rp'] >= 30 else ', meist trocken')]
    for x in hinweise(a): zeilen.append('⚠️ ' + x)
    zeilen.append('Morgen (%s): %s %s, %d bis %d °C.' % (TAGE[b['datum'].weekday()], emoji(b['code']), wort(b['code']), b['tmin'], b['tmax']))
    for w in warn[:3]: zeilen.append('🚨 DWD: ' + w)
    zeilen += ['', 'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de', '#BadKönig #Odenwald #Wetter']
    return '\n'.join(zeilen)


# ---------- Bild ----------
def font(size, bold=False):
    for p in (['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold else ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']):
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def icon(dr, cx, cy, s, c):
    w = wort(c)
    sun, cloud, dark = (250, 190, 50), (255, 255, 255), (150, 165, 185)
    def wolke(x, y, k, col):
        dr.ellipse([x - 0.9 * k, y - 0.2 * k, x - 0.1 * k, y + 0.5 * k], fill=col)
        dr.ellipse([x - 0.45 * k, y - 0.6 * k, x + 0.45 * k, y + 0.4 * k], fill=col)
        dr.ellipse([x + 0.05 * k, y - 0.25 * k, x + 0.85 * k, y + 0.5 * k], fill=col)
        dr.rounded_rectangle([x - 0.9 * k, y + 0.05 * k, x + 0.85 * k, y + 0.5 * k], radius=0.22 * k, fill=col)
    if w == 'sonnig':
        r = s * 0.42
        for k in range(12):
            import math
            a = k * math.pi / 6
            dr.line([cx + math.cos(a) * r * 1.25, cy + math.sin(a) * r * 1.25, cx + math.cos(a) * r * 1.6, cy + math.sin(a) * r * 1.6], fill=sun, width=int(s * 0.07))
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=sun)
        return
    if w in ('heiter bis wolkig', 'Schauer'):
        r = s * 0.32; dr.ellipse([cx - r + s * 0.18, cy - r - s * 0.22, cx + r + s * 0.18, cy + r - s * 0.22], fill=sun)
    col = dark if w in ('Regen', 'Gewitter', 'Nieselregen', 'bedeckt', 'neblig') else cloud
    wolke(cx, cy, s * 0.6, (120, 135, 155))  # Schatten
    wolke(cx - s * 0.03, cy - s * 0.04, s * 0.6, col if col != dark else (205, 212, 222))
    if w in ('Regen', 'Schauer', 'Nieselregen', 'Gewitter'):
        for k in range(-1, 2):
            x = cx + k * s * 0.25
            dr.line([x, cy + s * 0.42, x - s * 0.08, cy + s * 0.62], fill=(60, 130, 220), width=int(s * 0.06))
    if w == 'Schnee':
        for k in range(-1, 2):
            x = cx + k * s * 0.25; dr.ellipse([x - s * 0.05, cy + s * 0.45, x + s * 0.05, cy + s * 0.55], fill=(120, 170, 230))
    if w == 'Gewitter':
        dr.polygon([(cx, cy + s * 0.3), (cx - s * 0.12, cy + s * 0.6), (cx, cy + s * 0.58), (cx - s * 0.06, cy + s * 0.82), (cx + s * 0.14, cy + s * 0.48), (cx + s * 0.02, cy + s * 0.5)], fill=(250, 200, 40))
    if w == 'neblig':
        for k in range(3):
            y = cy + s * (0.5 + k * 0.1); dr.line([cx - s * 0.5, y, cx + s * 0.5, y], fill=(170, 180, 195), width=int(s * 0.05))


def bild(days, warn, path, labels=('HEUTE', 'MORGEN'), kopf=None, nacht=False):
    W = H = 1200
    im = Image.new('RGB', (W, H))
    dr = ImageDraw.Draw(im)
    for y in range(H):  # heller Himmelverlauf wie die Website
        t = y / H
        if nacht:  # Abendhimmel: tiefes Nachtblau -> Violett -> Dämmerungsorange am Horizont
            fill = (int(14 + t * 60), int(22 + t * 30), int(58 + t * 50)) if t < 0.8 else (int(74 + (t - .8) * 600), int(52 + (t - .8) * 180), int(108 - (t - .8) * 150))
        else:
            fill = (int(62 + t * 120), int(140 + t * 85), int(205 + t * 40))
        dr.line([(0, y), (W, y)], fill=fill)
    if nacht:
        import random
        rnd = random.Random(7)
        for _ in range(140):
            x, y, r = rnd.randint(0, W), rnd.randint(0, H - 200), rnd.choice((1, 1, 1.5, 2, 2.5))
            g = rnd.randint(170, 255); dr.ellipse([x - r, y - r, x + r, y + r], fill=(g, g, min(255, g + 15)))
        mx, my, mr = 62, 62, 30   # Mondsichel
        dr.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(255, 238, 180))
        dr.ellipse([mx - mr + 16, my - mr - 6, mx + mr + 16, my + mr - 6], fill=(17, 24, 61))
        dr.rectangle([0, H - 150, W, H], fill=(28, 36, 72))
    else:
        dr.rectangle([0, H - 150, W, H], fill=(229, 210, 178))
    a = days[0]
    dat = '%s, %d. %s %d' % (TAGE[a['datum'].weekday()], a['datum'].day, MONATE[a['datum'].month - 1], a['datum'].year)
    def ct(t, y, f, fill=(255, 255, 255), sh=True):
        w = dr.textlength(t, font=f)
        if sh: dr.text(((W - w) / 2 + 2, y + 3), t, font=f, fill=(30, 60, 100))
        dr.text(((W - w) / 2, y), t, font=f, fill=fill)
    ct('Private Wetterstation Bad König', 50, font(60, True))
    ct(kopf or dat, 140, font(40))
    # zwei Karten
    for k, d in enumerate(days[:2]):
        x0 = 60 + k * 555; y0 = 230; x1 = x0 + 525; y1 = 870
        dr.rounded_rectangle([x0, y0, x1, y1], radius=36, fill=(255, 255, 255))
        cx = (x0 + x1) / 2
        lab = labels[k]
        f = font(40, True); w = dr.textlength(lab, font=f); dr.text((cx - w / 2, y0 + 30), lab, font=f, fill=(57, 73, 171) if nacht else (60, 110, 170))
        f = font(30); t = TAGE[d['datum'].weekday()]; w = dr.textlength(t, font=f); dr.text((cx - w / 2, y0 + 80), t, font=f, fill=(110, 125, 145))
        dr.rounded_rectangle([x0 + 110, y0 + 135, x1 - 110, y0 + 335], radius=30, fill=(92, 107, 192) if nacht else (120, 175, 225))
        icon(dr, cx, y0 + 215, 160, d['code'])
        f = font(96, True); t = '%d°' % d['tmax']; w = dr.textlength(t, font=f); dr.text((cx - w / 2 - 70, y0 + 355), t, font=f, fill=(230, 100, 40))
        f = font(64, True); t = '%d°' % d['tmin']; w = dr.textlength(t, font=f); dr.text((cx + 50, y0 + 385), t, font=f, fill=(60, 120, 200))
        f = font(34, True); t = wort(d['code']).capitalize(); w = dr.textlength(t, font=f); dr.text((cx - w / 2, y0 + 485), t, font=f, fill=(40, 55, 75))
        f = font(28)
        info = ('Regen %d %%  ·  %.1f l/m²' % (d['rp'], d['regen'])).replace('.', ',')
        w = dr.textlength(info, font=f); dr.text((cx - w / 2, y0 + 540), info, font=f, fill=(90, 105, 125))
        info = 'Böen %d km/h  ·  Sonne %.0f h' % (round(d['boe']), d['sonne'])
        w = dr.textlength(info, font=f); dr.text((cx - w / 2, y0 + 580), info, font=f, fill=(90, 105, 125))
    # Hinweisband
    h = (['DWD: ' + w for w in warn[:1]] + hinweise(a))[:2]
    if h:
        dr.rounded_rectangle([60, 900, W - 60, 1020], radius=28, fill=(255, 243, 205) if not warn else (255, 222, 210))
        f = font(36, True); t = '⚠  ' if False else ''
        y = 960 - 24 * len(h)
        for line in h:
            w = dr.textlength(line, font=f); dr.text(((W - w) / 2, y), line, font=f, fill=(150, 70, 20)); y += 48
    ct('wetter-badkoenig.de', H - 105, font(52, True), fill=(255, 220, 140) if nacht else (70, 95, 140), sh=False)
    im.save(path, quality=90)


def regenwort(p):
    return 'trocken' if p < 20 else 'vereinzelt Schauer möglich' if p < 40 else 'Regen möglich' if p < 70 else 'nass'


def tagesablauf(d):
    return 'Vormittag %s, Nachmittag %s, Abend %s' % (regenwort(d['rp_vm']), regenwort(d['rp_nm']), regenwort(d['rp_ab']))


def details(d):
    t = []
    t.append('☀️ Sonne: etwa %.0f Stunden' % d['sonne'] if d['sonne'] >= 1 else '☁️ Kaum Sonne')
    t.append('💨 Wind: Böen bis %d km/h' % round(d['boe']) + (' – ruhig' if d['boe'] < 25 else ''))
    if d['regen'] >= 0.5: t.append(('🌧️ Regenmenge: etwa %.1f l/m²' % d['regen']).replace('.', ','))
    if d['schnee'] >= 0.5: t.append(('❄️ Neuschnee: etwa %.0f cm' % d['schnee']))
    return t


def tipp(d):
    w = wort(d['code'])
    if d['schnee'] >= 1: return 'Schnee im Odenwald – warm anziehen, auf den Höhen kann es glatt werden. ⛄'
    if w == 'Gewitter': return 'Bei Gewitter Wanderungen lieber verschieben und rechtzeitig Schutz suchen.'
    if d['tmin'] <= 0: return 'Morgens Scheiben kratzen einplanen und auf Glätte achten! 🧊'
    if d['rp'] >= 70: return 'Ein guter Tag für drinnen – oder mit Regenjacke raus. ☔'
    if d['sonne'] >= 5 and d['rp'] < 30: return 'Ideales Wetter für eine Runde im Odenwald – raus an die frische Luft! 🥾'
    if d['rp'] < 40: return 'Für einen Spaziergang passt es, eine Jacke sollte aber mit.'
    return 'Schirm griffbereit halten – Schauer sind möglich.'


def text_abend(paar, wochenende, warn, rest=()):
    a, b = paar
    zeilen = ['Guten Abend Bad König! 🌙 ' + ('Euer Wochenendwetter für den Odenwald:' if wochenende else 'Hier kommt der Wetterausblick für morgen:'), '']
    zeilen.append('🌃 Heute Nacht: Tiefstwerte um %d °C%s.' % (a['tmin'], ' – Frost!' if a['tmin'] <= 0 else ', Bodenfrost möglich' if a['tmin'] <= 3 else ''))
    zeilen.append('')
    for name, d in ((('Samstag', a), ('Sonntag', b)) if wochenende else (('Morgen', a),)):
        zeilen.append('📅 %s (%s): %s %s, %d bis %d °C' % (name, TAGE[d['datum'].weekday()], emoji(d['code']), wort(d['code']), d['tmin'], d['tmax']))
        zeilen.append('🕒 ' + tagesablauf(d))
        zeilen += details(d)
        zeilen.append('👉 Tipp: ' + tipp(d))
        zeilen.append('')
    if not wochenende:
        zeilen.append('📅 Übermorgen (%s): %s %s, %d bis %d °C%s.' % (TAGE[b['datum'].weekday()], emoji(b['code']), wort(b['code']), b['tmin'], b['tmax'],
                      ', Regenrisiko %d %%' % b['rp'] if b['rp'] >= 30 else ', meist trocken'))
    if rest:
        zeilen.append('📈 Danach: ' + ' · '.join('%s %s %d°' % (TAGE[d['datum'].weekday()][:2], emoji(d['code']), d['tmax']) for d in rest))
    for w in warn[:3]: zeilen.append('🚨 DWD: ' + w)
    zeilen += ['', 'Gute Nacht und bis morgen früh beim Wettervideo! 🎬',
               'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de', '#BadKönig #Odenwald #Wetter #Wetterbericht']
    return '\n'.join(zeilen)


def abend(now):
    """Abendbeitrag (ca. 18 Uhr): Ausblick auf morgen/übermorgen, freitags aufs Wochenende -> fb/abend.jpg + fb/abend.json"""
    if '--nur-abends' in sys.argv:
        if now.hour < 18:
            print('Noch vor 18 Uhr Ortszeit (%s) – übersprungen.' % now.strftime('%H:%M')); return
        try:
            alt = dt.datetime.fromisoformat(json.load(open(os.path.join(OUT, 'abend.json'), encoding='utf-8'))['erstellt']).astimezone(TZ)
            if alt.date() == now.date() and alt.hour >= 18: print('Abendbeitrag heute schon erstellt – übersprungen.'); return
        except Exception:
            pass
    days, warn = demo() if DEMO else load()
    wochenende = days[0]['datum'].weekday() == 4   # Freitag
    paar = days[1:3]
    labels = ('SAMSTAG', 'SONNTAG') if wochenende else ('MORGEN', 'ÜBERMORGEN')
    kopf = 'Wochenendwetter' if wochenende else 'Ausblick auf %s, %d. %s' % (TAGE[paar[0]['datum'].weekday()], paar[0]['datum'].day, MONATE[paar[0]['datum'].month - 1])
    os.makedirs(OUT, exist_ok=True)
    bild(paar, warn, os.path.join(OUT, 'abend.jpg'), labels, kopf, nacht=True)
    txt = text_abend(paar, wochenende, warn, days[3:6])
    open(os.path.join(OUT, 'abend.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'erstellt': now.isoformat(timespec='minutes'), 'text': txt}, open(os.path.join(OUT, 'abend.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(txt)


def main():
    now = dt.datetime.now(TZ)
    if '--abend' in sys.argv: return abend(now)
    if '--nur-um-6' in sys.argv:
        if now.hour < 6:
            print('Noch vor 6 Uhr Ortszeit (%s) – übersprungen.' % now.strftime('%H:%M')); return
        try:
            alt = dt.datetime.fromisoformat(json.load(open(os.path.join(OUT, 'post.json'), encoding='utf-8'))['erstellt']).astimezone(TZ)
            if alt.date() == now.date() and alt.hour >= 6:   # nachts (z. B. durch Änderungen) erstellte Beiträge zählen nicht
                print('Heute schon erstellt – übersprungen.'); return
        except Exception:
            pass
    days, warn = demo() if DEMO else load()
    os.makedirs(OUT, exist_ok=True)
    bild(days, warn, os.path.join(OUT, 'post.jpg'))
    txt = text(days, warn)
    open(os.path.join(OUT, 'post.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'erstellt': now.isoformat(timespec='minutes'), 'warn': warn, 'tage': [dict(d, datum=d['datum'].isoformat()) for d in days]},
              open(os.path.join(OUT, 'daten.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'erstellt': now.isoformat(timespec='minutes'), 'text': txt}, open(os.path.join(OUT, 'post.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(txt)


if __name__ == '__main__':
    main()
