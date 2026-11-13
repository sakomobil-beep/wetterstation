#!/usr/bin/env python3
"""Erstellt jeden Morgen das Facebook-Vorhersagebild + Text für die Private Wetterstation Bad König.
Ausgabe: fb/post.jpg, fb/post.txt, fb/post.json
Quellen: Präzisions-Vorhersage wie auf der Website (0–48 h DWD ICON-D2 + MOSMIX, lernende Korrektur mit Messwerten der Station IBADKN33), danach DWD ICON (Open-Meteo),
amtliche Warnungen des DWD (Bright Sky)."""
import json, os, sys, math, statistics, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont


# --- Sicherung: Texte passen immer ins Bild (gilt für alle Tafeln, Grafiken und Facebook-Bilder) ---
# Ragt ein Text links oder rechts aus dem Bild, wird die Schrift schrittweise verkleinert, bis er mit Rand hineinpasst.
_PIL_TEXT = ImageDraw.ImageDraw.text
def _text_passend(self, xy, text, fill=None, font=None, anchor=None, *a, **k):
    try:
        if font is not None and hasattr(font, 'font_variant') and isinstance(text, str) and '\n' not in text:
            W_ = self.im.size[0]; rand = 6; sw = k.get('stroke_width', 0)
            bb = self.textbbox(xy, text, font=font, anchor=anchor, stroke_width=sw)
            n = font.size
            while (bb[0] < rand or bb[2] > W_ - rand) and n > 10 and bb[2] - bb[0] > 0:
                n -= 1; font = font.font_variant(size=n)
                bb = self.textbbox(xy, text, font=font, anchor=anchor, stroke_width=sw)
                if anchor in (None, 'la', 'ls', 'lt', 'lm', 'lb') and bb[0] < rand: break   # linksbündig: nur rechts kürzen
    except Exception:
        pass
    return _PIL_TEXT(self, xy, text, fill, font, anchor, *a, **k)
ImageDraw.ImageDraw.text = _text_passend

LAT, LON = 49.750, 9.017
STATION, WU_KEY = 'IBADKN33', '43a8f308d89b471ba8f308d89b671b69'
TZ = ZoneInfo('Europe/Berlin')
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'fb')
DEMO = '--demo' in sys.argv
# Odenwaldkreis: Täler = Station Bad König (an die Messwerte angepasst), Höhen = Mischung der Modelle für die Höhe des Ortes
HOEHEN = [('Oberzent', 49.567, 8.976, 430), ('Mossautal', 49.667, 8.937, 380)]
TAELER = [('Breuberg', 49.818, 9.040, 160), ('Höchst', 49.799, 8.994, 170), ('Bad König', 49.743, 9.006, 185), ('Michelstadt', 49.678, 9.004, 208)]
KREIS_PUNKTE = [(LAT, LON), (49.567, 8.976), (49.678, 9.004)]   # Bad König, Oberzent, Michelstadt
MODELLE = ('icon_d2', 'meteofrance_arome_france_hd', 'ecmwf_ifs025', 'icon_eu')
TAGE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de facebook-bot'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


# ---------- Daten ----------
def load():
    om = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=icon_seamless'
             '&hourly=temperature_2m,weather_code,precipitation_probability,cloud_cover,wind_speed_10m,precipitation,wind_gusts_10m&past_days=5&forecast_days=8'
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
        sys.path.insert(0, os.path.dirname(__file__))
        import kreis   # Warnungen für alle Gemeinden des Odenwaldkreises
        for a in kreis.warnungen(get):
            if a.get('severity') in ('moderate', 'severe', 'extreme') or a.get('event_de'):
                w_ = a.get('headline_de') or a.get('event_de')
                if a.get('gebiet') and a['gebiet'] != 'ganzer Odenwaldkreis': w_ += ' für ' + a['gebiet']   # für wen sie gilt
                if w_ not in warn: warn.append(w_)
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
        # Nacht vor diesem Tag (Vortag 20 Uhr bis 8 Uhr): Wolken und Wind – Bodenfrost nur bei klar + windstill
        _vt = (dt.date.fromisoformat(D['time'][i]) - dt.timedelta(days=1)).isoformat()
        _nk = [k for k, t in enumerate(Hh['time']) if (t[:10] == _vt and int(t[11:13]) >= 20) or (t[:10] == D['time'][i] and int(t[11:13]) < 8)]
        _c = [Hh['cloud_cover'][k] for k in _nk if Hh['cloud_cover'][k] is not None]
        _w = [Hh['wind_speed_10m'][k] for k in _nk if Hh['wind_speed_10m'][k] is not None]
        days[-1]['nacht_klar'] = bool(_c) and sum(_c) / len(_c) <= 30 and (not _w or sum(_w) / len(_w) <= 10)
        # Abgleich: Wettersymbol „Regen/Niesel/Schauer“, aber laut Präzisions-Vorhersage kaum Regen → kein Regen
        t_ = days[-1]
        if t_['code'] in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82) and t_['regen'] < 0.3 and t_['rp'] < 30:
            t_['code'] = 1 if t_['sonne'] >= 7 else 2 if t_['sonne'] >= 4 else 3
    for d in days[:3]:   # Stundenwerte für die Wettergrafiken in den Videos (Station Bad König)
        try: d['stunden'] = stundenwerte(Hh, stunden, d['datum'].isoformat())
        except Exception as e: print('Stundenwerte nicht möglich:', e)
    sicherheit(days)
    hoehen(days)
    try: days[0]['gestern'] = rueckblick(st)
    except Exception as e: print('Rückblick nicht möglich:', e)
    try: days[0]['heute_mess'] = heute_gemessen(st)
    except Exception as e: print('Rückblick nicht möglich:', e)
    for d in days[:2]:
        try: d['fenster'] = fenster(KREIS_OM or om, d)
        except Exception as e: print('Zeitfenster nicht möglich:', e)
    try: days[0]['himmel'] = himmel(om)
    except Exception as e: print('Himmel nicht möglich:', e)
    return days, warn


def stundenwerte(Hh, stunden, tag):
    """24 Stunden eines Tages: Temperatur (korrigiert bzw. gemessen), Regenrisiko, Regenmenge, Böen, Wettercode."""
    idx = [k for k, t in enumerate(Hh['time']) if t[:10] == tag]
    kor = stunden.get(tag) or []
    out = []
    for j, k in enumerate(idx):
        tm = Hh['temperature_2m'][k]
        if tm is None: continue
        t = kor[j] if len(kor) == len(idx) else tm
        out.append(dict(h=int(Hh['time'][k][11:13]), t=round(t, 1), rp=Hh['precipitation_probability'][k] or 0,
                        mm=round((Hh.get('precipitation') or [0] * len(Hh['time']))[k] or 0, 1),
                        boe=round((Hh.get('wind_gusts_10m') or [0] * len(Hh['time']))[k] or 0), code=Hh['weather_code'][k] or 0))
    return out


REK_START = '2026-01-20'   # Messbeginn der Station IBADKN33


def jahresrekorde(gestern, g):
    """Jahresrekorde (wärmster/kältester/nassester Tag, stärkste Böe) in fb/rekorde.json fortschreiben.
    Gibt die gestern neu aufgestellten Rekorde zurück (Liste) und schickt eine Push-Nachricht."""
    p = os.path.join(OUT, 'rekorde.json'); jahr = gestern[:4]
    try: R = json.load(open(p, encoding='utf-8'))
    except Exception: R = {}
    if R.get('jahr') != jahr:
        R = {'jahr': jahr, 'bis': None}
        d = max(dt.date.fromisoformat(jahr + '-01-01'), dt.date.fromisoformat(REK_START)); ende = dt.date.fromisoformat(gestern)
        while d < ende:   # erstmalig: alle Tage des Jahres bis vorgestern von Weather Underground holen
            try:
                o = (get('https://api.weather.com/v2/pws/history/daily?stationId=%s&format=json&units=m&date=%s&apiKey=%s'
                         % (STATION, d.strftime('%Y%m%d'), WU_KEY)).get('observations') or [])
                m = (o[-1].get('metric') or {}) if o else {}
                for k, w, besser in (('hi', m.get('tempHigh'), max), ('lo', m.get('tempLow'), min), ('regen', m.get('precipTotal'), max), ('boe', m.get('windgustHigh'), max)):
                    if w is None: continue
                    if k not in R or besser(w, R[k]['v']) == w and w != R[k]['v']: R[k] = {'v': round(w, 1), 'd': d.isoformat()}
            except Exception as e: print('Rekorde: Tag', d, 'nicht abrufbar:', e)
            d += dt.timedelta(days=1)
        R['bis'] = (ende - dt.timedelta(days=1)).isoformat()
    if R.get('bis') and R['bis'] >= gestern: return R.get('neu_' + gestern, [])
    neu = []
    for k, w, besser, txt in (('hi', g['tmax'], max, 'Wärmster Tag'), ('lo', g['tmin'], min, 'Kältester Tag'),
                              ('regen', g['regen'], max, 'Nassester Tag'), ('boe', g.get('boe'), max, 'Stärkste Böe')):
        if w is None or (k == 'regen' and w < 1): continue
        if k not in R or (besser(w, R[k]['v']) == w and w != R[k]['v']):
            if k in R: neu.append({'art': k, 'name': txt, 'wert': w, 'alt': R[k]['v'], 'alt_d': R[k]['d']})
            R[k] = {'v': w, 'd': gestern}
    R['bis'] = gestern; R = {k: v for k, v in R.items() if not k.startswith('neu_')}; R['neu_' + gestern] = neu
    json.dump(R, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if neu:
        E = {'hi': '°C', 'lo': '°C', 'regen': 'l/m²', 'boe': 'km/h'}
        txt = '\n'.join('%s %s: %s %s (bisher %s)' % (n['name'], jahr, n['wert'], E[n['art']], n['alt']) for n in neu)
        topic = os.environ.get('NTFY_TOPIC')
        if topic:
            try:
                urllib.request.urlopen(urllib.request.Request('https://ntfy.sh/' + topic, data=txt.encode('utf-8'), headers={
                    'Title': 'Neuer Rekord an der Station Bad König'.encode('utf-8').decode('latin-1'), 'Tags': 'trophy',
                    'Click': 'https://wetter-badkoenig.de/'}), timeout=20).read()
                print('Rekord-Push gesendet')
            except Exception as e: print('Rekord-Push fehlgeschlagen:', e)
    return neu


def heute_gemessen(st):
    """Heute bisher an der Station Bad König gemessen (Höchst, Regen, Böe) – für „Der Tag in Zahlen“ im Abendvideo."""
    heute = dt.datetime.now(TZ).date().isoformat()
    hi, regen, boe = [], 0.0, []
    for o in st:
        if dt.datetime.fromtimestamp(o['epoch'], TZ).date().isoformat() != heute: continue
        m = o.get('metric') or {}
        if m.get('tempHigh') is not None: hi.append(m['tempHigh'])
        if m.get('precipTotal') is not None: regen = max(regen, m['precipTotal'])
        if m.get('windgustHigh') is not None: boe.append(m['windgustHigh'])
    if not hi: return None
    return dict(tmax=round(max(hi), 1), regen=round(regen, 1), boe=round(max(boe)) if boe else None)


def rueckblick(st):
    """Gestern an der Station Bad König gemessen (Höchst, Tiefst, Regen) + kälteste/wärmste Nacht seit … aus dem Lern-Archiv."""
    gestern = (dt.datetime.now(TZ) - dt.timedelta(days=1)).date().isoformat()
    hi, lo, regen, boe = [], [], 0.0, []
    for o in st:
        if dt.datetime.fromtimestamp(o['epoch'], TZ).date().isoformat() != gestern: continue
        m = o.get('metric') or {}
        if m.get('tempHigh') is not None: hi.append(m['tempHigh'])
        if m.get('tempLow') is not None: lo.append(m['tempLow'])
        if m.get('precipTotal') is not None: regen = max(regen, m['precipTotal'])
        if m.get('windgustHigh') is not None: boe.append(m['windgustHigh'])
    if not hi or not lo: return None
    out = dict(tmax=round(max(hi), 1), tmin=round(min(lo), 1), regen=round(regen, 1), boe=round(max(boe)) if boe else None, rekord=None)
    try: out['jahr'] = jahresrekorde(gestern, out)
    except Exception as e: print('Jahresrekorde nicht möglich:', e)
    # Nacht-Tiefstwerte (0–9 Uhr) aus data/lernen/*.json, um „kälteste Nacht seit …“ zu finden
    heute = dt.datetime.now(TZ).date().isoformat()
    LD = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'lernen'); nacht = {}
    for f in sorted(os.listdir(LD)) if os.path.isdir(LD) else []:
        if not f.endswith('.json'): continue
        for k, r in json.load(open(os.path.join(LD, f), encoding='utf-8')).items():
            if 'st' in r and int(k[11:13]) <= 9: nacht[k[:10]] = min(nacht.get(k[:10], 99), r['st'])
    # Fix 13.11.2026: zusätzlich das komplette Stundenarchiv (data/archiv, ab Messbeginn 20.01.2026) einbeziehen –
    # vorher kannte die Suche nur das Lern-Archiv (ab Oktober) und meldete fälschlich „seit Beginn der Aufzeichnungen“.
    AD = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'archiv')
    for f in sorted(os.listdir(AD)) if os.path.isdir(AD) else []:
        if not f.startswith('stunden-'): continue
        try:
            for tag, obs in json.load(open(os.path.join(AD, f), encoding='utf-8')).get('tage', {}).items():
                for o in obs:
                    v = (o.get('metric') or {}).get('tempLow'); h = int(str(o.get('obsTimeLocal', ''))[11:13] or 99)
                    if v is not None and h <= 9: nacht[tag] = min(nacht.get(tag, 99), v)
        except Exception as e: print('Archiv', f, 'nicht lesbar:', e)
    for o in st:
        t = dt.datetime.fromtimestamp(o['epoch'], TZ); v = (o.get('metric') or {}).get('tempLow')
        if v is not None and t.hour <= 9: nacht[t.date().isoformat()] = min(nacht.get(t.date().isoformat(), 99), v)
    if heute in nacht and len(nacht) >= 10:
        jetzt_n = nacht[heute]; frueher = sorted(d for d in nacht if d < heute)
        kaelter = [d for d in frueher if nacht[d] <= jetzt_n]
        seit = kaelter[-1] if kaelter else None
        tage = (dt.date.fromisoformat(heute) - dt.date.fromisoformat(seit or frueher[0])).days
        if tage >= 10:
            # „seit Beginn“ nur, wenn das Archiv wirklich ab Messbeginn reicht – sonst lieber gar keine Aussage
            if seit or frueher[0] <= REK_START:
                out['rekord'] = dict(wert=round(jetzt_n, 1), seit=seit, beginn=frueher[0], tage=tage)
    return out


def fenster(om, d):
    """Bestes 2-Stunden-Fenster für draußen (9–17 Uhr): wenig Regen, wenig Wolken, eher warm."""
    H = om['hourly']; tag = d['datum'].isoformat(); kand = []
    for i, t in enumerate(H['time']):
        if t[:10] != tag or not 9 <= int(t[11:13]) <= 15: continue
        if i + 1 >= len(H['time']): continue
        p = max(H['precipitation_probability'][i] or 0, H['precipitation_probability'][i + 1] or 0)
        c = ((H['cloud_cover'][i] or 0) + (H['cloud_cover'][i + 1] or 0)) / 2
        T = ((H['temperature_2m'][i] or 0) + (H['temperature_2m'][i + 1] or 0)) / 2
        kand.append((p * 2 + c * 0.5 - T, int(t[11:13]), p, c))
    if not kand: return None
    sc, h, p, c = min(kand)
    if p >= 50: return None
    if dt.datetime.now(TZ).date().isoformat() == tag and h + 2 <= dt.datetime.now(TZ).hour: return None
    return dict(von=h, bis=h + 2, sonnig=c < 50)


def himmel(om):
    """Besonderes am Himmel heute Nacht: Polarlicht-Chance (NOAA Kp), Vollmond, klare Sternennacht."""
    H = om['hourly']; heute = dt.datetime.now(TZ).date().isoformat()
    wolken = [H['cloud_cover'][i] for i, t in enumerate(H['time']) if t[:10] == heute and int(t[11:13]) >= 20 and H['cloud_cover'][i] is not None]
    klar = bool(wolken) and sum(wolken) / len(wolken) < 30
    ref = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)   # Neumond als Bezug
    alter = ((dt.datetime.now(dt.timezone.utc).replace(hour=21) - ref).total_seconds() / 86400) % 29.530589
    vollmond = abs(alter - 14.77) < 1.0
    kp = 0
    try:
        rows = get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json')
        bis = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=18)).strftime('%Y-%m-%d %H')
        ab = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H')
        for r in rows:   # NOAA liefert je nach Version Listen ([Zeit, Kp, …]) oder Objekte ({time_tag, kp, …})
            if isinstance(r, dict): z, v = str(r.get('time_tag') or ''), r.get('kp')
            elif isinstance(r, list) and r and r[0] != 'time_tag': z, v = str(r[0]), r[1]
            else: continue
            z = z.replace('T', ' ')
            if ab <= z[:13] <= bis and v is not None: kp = max(kp, float(v))
    except Exception as e:
        print('Kp-Vorhersage nicht abrufbar:', e)
    return dict(klar=klar, vollmond=vollmond, kp=kp)


def gewicht(m, n):
    """Grundgewicht je Modell nach Vorhersagetag (wie auf der Website)."""
    if n < 2: return {'icon_d2': 0.40, 'meteofrance_arome_france_hd': 0.30, 'ecmwf_ifs025': 0.15, 'icon_eu': 0.15}[m]
    if n < 5: return {'ecmwf_ifs025': 0.55, 'icon_eu': 0.45}.get(m, 0)
    return {'ecmwf_ifs025': 0.65, 'icon_eu': 0.35}.get(m, 0)


ORT_CACHE = {}
ORT_KEY = {'Breuberg': 'breuberg', 'Höchst': 'hoechst', 'Bad König': 'badkoenig', 'Michelstadt': 'michelstadt', 'Oberzent': 'oberzent', 'Mossautal': 'mossautal'}


def lern_kreis():
    """Gelernte Korrektur je Ort und Modell (data/lernen-kreis.json) – erst ab 3 Tagen Daten."""
    try: O = json.load(open(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'lernen-kreis.json'), encoding='utf-8'))['orte']
    except Exception: return {}
    out = {}
    for k, E in O.items():
        if E.get('unbrauchbar') or E.get('tage', 0) < 3 or not E.get('mae'): continue
        ms = sorted(E['mae'].values()); med = ms[len(ms) // 2]
        out[k] = {'bias': E['bias'], 'f': {m: max(0.5, min(2.0, (med / v) ** 2)) for m, v in E['mae'].items() if v}}
    return out


LERN = None
KREIS_OM = None


def ort_daten(name, la, lo, el):
    """Tages- und Stundenwerte eines Ortes für alle vier Modelle (einmal je Lauf abgerufen)."""
    if name not in ORT_CACHE:
        url = ('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&elevation=%s&models=%s'
               '&daily=temperature_2m_max,temperature_2m_min,weather_code,snowfall_sum,precipitation_sum,wind_gusts_10m_max,sunshine_duration'
               '&hourly=precipitation,cloud_cover,temperature_2m,snowfall,weather_code,relative_humidity_2m,dew_point_2m,wind_speed_10m&forecast_days=8&timezone=Europe%%2FBerlin' % (la, lo, el, ','.join(MODELLE)))
        ORT_CACHE[name] = None
        for v in range(3):   # kurze Aussetzer (Zeitüberschreitung) nicht gleich den ganzen Ort kosten
            try:
                ORT_CACHE[name] = get(url); break
            except Exception as e:
                print('Vorhersage %s nicht abrufbar (Versuch %d):' % (name, v + 1), e)
                if v < 2: time.sleep(4)
    return ORT_CACHE[name]


def orte_mix(liste, days):
    """Mischung aus ICON-D2, AROME, ECMWF, ICON-EU für mehrere Orte (je mit seiner Höhe), wie die Odenwald-Vorhersage der Website.
    Je Tag: tmax (Mittel), tmin (kältester Ort), code (Mehrheit), schnee, regen (Mittel), boe (stärkster Ort), sonne (Mittel),
    rp / rp_vm / rp_nm / rp_ab (Anteil der Orte×Modelle mit Regen, in %)."""
    global LERN
    if LERN is None: LERN = lern_kreis()
    orte = [(x, LERN.get(ORT_KEY.get(o[0]), {})) for o, x in ((o, ort_daten(*o)) for o in liste) if x]
    out = []
    for n, d in enumerate(days):
        tag = d['datum'].isoformat(); tx, tn, sn, rg, gb, so, stim = [], [], [], [], [], [], {}
        nass = {'tag': [0.0, 0.0], 'vm': [0.0, 0.0], 'nm': [0.0, 0.0], 'ab': [0.0, 0.0]}
        for O, L in orte:
            D, H = O['daily'], O.get('hourly') or {}
            if tag not in D['time']: continue
            i = D['time'].index(tag); sw = vx = vn = vs = vr = vg = vo = 0.0
            def v(k, m, idx=i, Q=D): a = Q.get(k + '_' + m); return a[idx] if a and idx < len(a) else None
            for m in MODELLE:
                w = gewicht(m, n); a, b = v('temperature_2m_max', m), v('temperature_2m_min', m)
                if not w or a is None or b is None: continue
                if L.get('bias', {}).get(m):   # gelernte Korrektur dieses Modells an diesem Ort: Nachmittag für Höchst-, früher Morgen für Tiefstwert
                    a += L['bias'][m][3]; b += L['bias'][m][1]; w *= L['f'].get(m, 1.0)
                sw += w; vx += w * a; vn += w * b; vs += w * (v('snowfall_sum', m) or 0)
                vr += w * (v('precipitation_sum', m) or 0); vg += w * (v('wind_gusts_10m_max', m) or 0); vo += w * (v('sunshine_duration', m) or 0)
                c = v('weather_code', m)
                if c is not None and m != 'meteofrance_arome_france_hd': stim[c] = stim.get(c, 0) + w
                p = v('precipitation_sum', m)
                if p is not None: nass['tag'][0] += w; nass['tag'][1] += w if p >= 1 else 0
                for key, a_, b_ in (('vm', 6, 12), ('nm', 12, 18), ('ab', 18, 24)):
                    hs = [H.get('precipitation_' + m, [None] * len(H.get('time', [])))[k] for k, t in enumerate(H.get('time', []))
                          if t[:10] == tag and a_ <= int(t[11:13]) < b_]
                    hs = [x for x in hs if x is not None]
                    if hs: nass[key][0] += w; nass[key][1] += w if max(hs) >= 0.1 else 0
            if sw: tx.append(vx / sw); tn.append(vn / sw); sn.append(vs / sw); rg.append(vr / sw); gb.append(vg / sw); so.append(vo / sw)
        if not tx: out.append(None); continue
        code = max(stim, key=stim.get) if stim else d['code']
        schnee = max(sn) >= 0.5 or 71 <= code <= 77 or code in (85, 86)
        pr = lambda k: round(100 * nass[k][1] / nass[k][0]) if nass[k][0] else 0
        out.append(dict(tmax=round(sum(tx) / len(tx)), tmin=round(sum(tn) / len(tn)), tmin_kalt=round(min(tn)), code=code, schnee=bool(schnee), schnee_cm=round(sum(sn) / len(sn), 1),
                        regen=round(sum(rg) / len(rg), 1), boe=round(max(gb)), sonne=round(sum(so) / len(so) / 3600, 1),
                        rp=pr('tag'), rp_vm=pr('vm'), rp_nm=pr('nm'), rp_ab=pr('ab')))
    return out


def orte_einzeln(days):
    """Werte je Ort des Odenwaldkreises (für die Reliefkarte im Abendvideo) – gleiche Modellmischung
    und gelernte Korrektur wie die Odenwald-Vorhersage, nur ohne Mittelung über die Orte.
    Die Abrufe liegen schon im Cache (orte_mix), kostet also keine zusätzlichen Anfragen."""
    out = {}
    for o in TAELER + HOEHEN:
        try:
            w = orte_mix([o], days)
            out[o[0]] = [None if x is None else {k: x[k] for k in ('tmax', 'tmin', 'tmin_kalt', 'code', 'schnee')} for x in w]
        except Exception as e:
            print('Ortswerte %s nicht möglich:' % o[0], e)
    return out


def orte_rest(heute, ab=None, bis=19):
    """Werte je Ort für den Rest des Tages (Mittagskarte): höchste Stundentemperatur von jetzt bis `bis` Uhr
    und der Anteil der Modelle mit Regen in dem Fenster. Nutzt die schon abgerufenen Stundenwerte."""
    jetzt = dt.datetime.now(TZ)
    ab = ab if ab is not None else max(12, jetzt.hour)
    tag = heute.isoformat()
    out = {}
    for name, la, lo, el in TAELER + HOEHEN:
        O = ort_daten(name, la, lo, el)
        if not O or not O.get('hourly'): continue
        H = O['hourly']; idx = [k for k, t in enumerate(H['time']) if t[:10] == tag and ab <= int(t[11:13]) <= bis]
        if not idx: continue
        sw = tmax = 0.0; nass = [0.0, 0.0]; warm = None
        for m in MODELLE:
            w = gewicht(m, 0)
            T = H.get('temperature_2m_' + m); P = H.get('precipitation_' + m)
            if not w or not T: continue
            vals = [T[k] for k in idx if k < len(T) and T[k] is not None]
            if not vals: continue
            sw += w; tmax += w * max(vals)
            if P:
                ps = [P[k] for k in idx if k < len(P) and P[k] is not None]
                if ps: nass[0] += w; nass[1] += w if max(ps) >= 0.1 else 0
        if sw: out[name] = dict(tmax=round(tmax / sw), rp=round(100 * nass[1] / nass[0]) if nass[0] else 0, von=ab, bis=bis)
    return out


def live_station():
    """Aktueller Messwert der eigenen Station aus data/live.json (vom Widget-Lauf gefüllt)."""
    try:
        o = json.load(open(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'live.json'), encoding='utf-8'))['cur']['observations'][0]
        t = dt.datetime.fromisoformat(o['obsTimeUtc'].replace('Z', '+00:00')).astimezone(TZ)
        if (dt.datetime.now(TZ) - t).total_seconds() > 3600: print('Messwert ist älter als eine Stunde – wird nicht gezeigt.'); return None
        return dict(temp=o['metric']['temp'], feuchte=o.get('humidity'), wind=o['metric'].get('windSpeed'),
                    boe=o['metric'].get('windGust'), zeit=t.strftime('%H:%M'))
    except Exception as e:
        print('Live-Messwert nicht verfügbar:', e); return None


def kreis_stunden(liste):
    """Stundenwerte der Talorte gemittelt (für das beste Zeitfenster): Regen-Anteil in %, Wolken, Temperatur."""
    orte = [x for x in (ort_daten(*o) for o in liste) if x and x.get('hourly')]
    if not orte: return None
    T = orte[0]['hourly']['time']; out = {'time': T, 'precipitation_probability': [], 'cloud_cover': [], 'temperature_2m': []}
    for k in range(len(T)):
        nw = n = 0; cc = []; tt = []
        for O in orte:
            H = O['hourly']
            for m in MODELLE:
                p = (H.get('precipitation_' + m) or [None] * len(T))[k]; c = (H.get('cloud_cover_' + m) or [None] * len(T))[k]
                t = (H.get('temperature_2m_' + m) or [None] * len(T))[k]
                if p is not None: n += 1; nw += p >= 0.1
                if c is not None: cc.append(c)
                if t is not None: tt.append(t)
        out['precipitation_probability'].append(round(100 * nw / n) if n else None)
        out['cloud_cover'].append(sum(cc) / len(cc) if cc else None); out['temperature_2m'].append(sum(tt) / len(tt) if tt else None)
    return {'hourly': out}


def hoehen(days):
    """Odenwald-Wetter für den ganzen Kreis (Facebook-Beiträge und Videos):
    Täler (Breuberg, Höchst, Bad König, Michelstadt) -> Hauptwerte des Tages, Höhen (Oberzent, Mossautal) -> d['hoch'],
    Regen, Böen, Sonne über alle sechs Orte. Die ursprünglichen, an die Station Bad König angepassten Werte bleiben in d['bk']."""
    global KREIS_OM
    for d, h in zip(days, orte_mix(HOEHEN, days)):
        if h: d['hoch'] = h
    alle = orte_mix(TAELER + HOEHEN, days)
    for d, t, a in zip(days, orte_mix(TAELER, days), alle):
        if not t or not a: continue
        d['tal'] = t
        d['bk'] = {k: d[k] for k in ('tmax', 'tmin', 'code', 'regen', 'rp', 'boe', 'sonne')}
        d['frost_min'] = t['tmin_kalt']   # kältester Talort – nur für Frost-Hinweise
        d.update(tmax=t['tmax'], tmin=t['tmin'], code=t['code'], regen=a['regen'], rp=a['rp'], rp_vm=a['rp_vm'], rp_nm=a['rp_nm'], rp_ab=a['rp_ab'],
                 boe=a['boe'], sonne=t['sonne'], schnee=a['schnee_cm'])
    try: KREIS_OM = kreis_stunden(TAELER)
    except Exception as e: print('Kreis-Stundenwerte nicht möglich:', e)
    try: niederschlag(days)
    except Exception as e: print('Niederschlags-Einstufung nicht möglich:', e)
    try: lage_winter(days)
    except Exception as e: print('Nebel-/Glätte-Einstufung nicht möglich:', e)


GLAETTE_REIHE = ('keine', 'reif', 'naesse', 'schnee', 'glatteis')


def lage_winter(days):
    """EINE Grundlage für Nebel, Kaltluft in den Tälern und Glätte (Max, Facebook, Instagram) – wie die Regen-Einstufung.
    Stundenwerte der Talorte (Breuberg, Höchst, Bad König, Michelstadt) bzw. der Höhen × Modelle, gewichtet wie die Vorhersage.
    Zeitraum: die Nacht vor dem Tag und der Vormittag (Vortag 18 Uhr bis 10 Uhr). Je Ort×Modell wird geprüft:
      Nebel    – Wettercode 45/48 oder Luftfeuchte >= 97 % bei Wind <= 6 km/h (zwischen 4 und 10 Uhr)
      Glätte   – Glatteis (gefrierender Regen, Code 56/57/66/67) > Schnee (Schneefall bei <= 1 °C)
                 > überfrierende Nässe (<= 0,5 °C und in den 6 Stunden davor nass) > Reif (<= 0 °C, Taupunkt nah, klar, windstill)
    Stufe = Anteil der Ort×Modell-Kombinationen (gewichtet): Nebel >= 50 % „wahrscheinlich“, >= 25 % „moeglich“;
    Glätte: schwerste Art mit >= 30 % Anteil (Glatteis schon ab 20 %).
    Kaltluft: klare, windstille Nacht und der kälteste Talort ist so kalt wie die Höhen oder kälter (sonst sind die Täler ~1,5 Grad wärmer).
    Ergebnis: d['lage'] = {nebel, nebel_p, nebel_bis, glaette, glaette_p, glaette_hoch, kaltluft, kalt_diff}."""
    def auswerten(liste, n, tag, vt):
        nb = [0.0, 0.0]; bis = []; gl = {k: 0.0 for k in GLAETTE_REIHE}; gsum = 0.0
        for o in liste:
            O = ort_daten(*o)
            if not O or not O.get('hourly'): continue
            H = O['hourly']; T = H['time']
            idx = [k for k, t in enumerate(T) if (t[:10] == vt and int(t[11:13]) >= 18) or (t[:10] == tag and int(t[11:13]) <= 10)]
            if not idx: continue
            for m in MODELLE:
                w = gewicht(m, n)
                tt = H.get('temperature_2m_' + m)
                if not w or not tt: continue
                g = lambda k_, key: (H.get(key + '_' + m) or [None] * len(T))[k_]
                nebel_h = []; art = 'keine'
                for k in idx:
                    t_ = tt[k]
                    if t_ is None: continue
                    c, rh, wi = g(k, 'weather_code'), g(k, 'relative_humidity_2m'), g(k, 'wind_speed_10m')
                    stunde = int(T[k][11:13]); morgen = T[k][:10] == tag and 4 <= stunde <= 10
                    if morgen and (c in (45, 48) or (rh is not None and rh >= 97 and (wi or 0) <= 6)): nebel_h.append(stunde)
                    pr, sn, td, cc = g(k, 'precipitation') or 0, g(k, 'snowfall') or 0, g(k, 'dew_point_2m'), g(k, 'cloud_cover')
                    nass_vorher = any((g(j, 'precipitation') or 0) >= 0.1 for j in range(max(0, k - 6), k + 1))
                    if c in (56, 57, 66, 67): neu = 'glatteis'
                    elif sn > 0 and t_ <= 1: neu = 'schnee'
                    elif t_ <= 0.5 and nass_vorher: neu = 'naesse'
                    elif t_ <= 0 and td is not None and td >= t_ - 1 and (wi or 0) <= 8 and (cc is None or cc <= 40): neu = 'reif'
                    else: neu = 'keine'
                    if GLAETTE_REIHE.index(neu) > GLAETTE_REIHE.index(art): art = neu
                nb[0] += w; gsum += w
                if nebel_h: nb[1] += w; bis.append(max(nebel_h))
                gl[art] += w
        if not gsum: return None
        p_nebel = round(100 * nb[1] / nb[0])
        anteil = {k: round(100 * v / gsum) for k, v in gl.items()}
        glaette = 'keine'
        for k in reversed(GLAETTE_REIHE[1:]):   # schwerste Art zuerst; Anteil zählt inkl. schwererer Arten
            ab = sum(anteil[x] for x in GLAETTE_REIHE[GLAETTE_REIHE.index(k):])
            if ab >= (20 if k == 'glatteis' else 30): glaette = k; break
        return dict(nebel='wahrscheinlich' if p_nebel >= 50 else 'moeglich' if p_nebel >= 25 else 'keiner', nebel_p=p_nebel,
                    nebel_bis=(sorted(bis)[len(bis) // 2] + 1) if bis else None,
                    glaette=glaette, glaette_p=sum(anteil[x] for x in GLAETTE_REIHE[1:]))
    for n, d in enumerate(days):
        tag = d['datum'].isoformat(); vt = (d['datum'] - dt.timedelta(days=1)).isoformat()
        tal = auswerten(TAELER, n, tag, vt)
        if not tal: continue
        hoch = auswerten(HOEHEN, n, tag, vt) or {}
        T_, H_ = d.get('tal'), d.get('hoch')
        diff = round(H_['tmin'] - T_['tmin_kalt']) if T_ and H_ else 0
        tal.update(glaette_hoch=hoch.get('glaette', 'keine'), kaltluft=bool(d.get('nacht_klar') and diff >= 0), kalt_diff=diff)
        d['lage'] = tal
        print('Lage %s: Nebel %s (%d %%, bis %s Uhr), Glätte Tal %s / Höhen %s, Kaltluft %s (%+d)' % (
            tag, tal['nebel'], tal['nebel_p'], tal['nebel_bis'], tal['glaette'], tal['glaette_hoch'], tal['kaltluft'], diff))


NASS_CODES = (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99)
STUFEN = ('trocken', 'vereinzelt', 'schauer', 'regen', 'gewitter')


def stufe_aus(P, S, G):
    """Einheitliche Regen-Einstufung aus max. Regen-Anteil P (%), Menge S (l/m²) und Gewitter-Anteil G (%)."""
    if P < 10 or (P < 20 and S < 0.05): return 'trocken'
    if G >= 30 and P >= 30: return 'gewitter'
    if P < 30: return 'vereinzelt'
    if P >= 60 and S >= 1: return 'regen'
    return 'schauer'


def niederschlag(days):
    """EINE Grundlage für alles, was über Regen gesagt/gezeigt wird (Max, Facebook, Instagram, Grafiken):
    Stundenwerte aller sechs Kreis-Orte × Modelle (gewichtet wie die Vorhersage).
    Je Stunde: p = Anteil mit Niederschlag >= 0,1 l/m², mm = gewichtetes Mittel, Schnee-Anteil Tal/Höhen, Gewitter-Anteil.
    Ergebnis: d['nied'] (Stufe für Tag, Vormittag, Nachmittag, Abend; Schnee Tal/Höhen) – und rp, rp_vm/nm/ab, regen,
    code sowie die Stundenwerte der Grafik werden daran angeglichen, damit nichts mehr widersprüchlich ist."""
    orte = [(o[0] in [h[0] for h in HOEHEN], ort_daten(*o)) for o in TAELER + HOEHEN]
    orte = [(hoch, x['hourly']) for hoch, x in orte if x and x.get('hourly')]
    if not orte: return
    for n, d in enumerate(days):
        tag = d['datum'].isoformat(); std = {}
        for hoch, H in orte:
            T = H.get('time') or []
            for k, t in enumerate(T):
                if t[:10] != tag: continue
                h = int(t[11:13]); e = std.setdefault(h, dict(w=0.0, nw=0.0, mm=0.0, g=0.0, sn_t=[0.0, 0.0], sn_h=[0.0, 0.0]))
                for m in MODELLE:
                    w = gewicht(m, n); p = (H.get('precipitation_' + m) or [None] * len(T))[k]
                    if not w or p is None: continue
                    sf = (H.get('snowfall_' + m) or [None] * len(T))[k] or 0; c = (H.get('weather_code_' + m) or [None] * len(T))[k] or 0
                    e['w'] += w; e['mm'] += w * p
                    if p >= 0.1:
                        e['nw'] += w; e['g'] += w if c >= 95 else 0
                        z = e['sn_h'] if hoch else e['sn_t']; z[0] += w; z[1] += w if sf > 0 else 0
        if not std: continue
        H_ = {h: dict(p=round(100 * e['nw'] / e['w']), mm=e['mm'] / e['w'], g=100 * e['g'] / e['w'],
                      sn_t=(e['sn_t'][1] / e['sn_t'][0]) if e['sn_t'][0] else 0, sn_h=(e['sn_h'][1] / e['sn_h'][0]) if e['sn_h'][0] else 0)
              for h, e in std.items() if e['w']}
        def teil(a, b):
            x = [v for h, v in H_.items() if a <= h < b]
            if not x: return dict(stufe='trocken', p=0, mm=0.0)
            P = max(v['p'] for v in x); S = sum(v['mm'] for v in x); G = max(v['g'] for v in x)
            nass = [v for v in x if v['p'] >= 30]
            return dict(stufe=stufe_aus(P, S, G), p=P, mm=round(S, 1),
                        schnee_tal=bool(nass) and sum(v['sn_t'] for v in nass) / len(nass) >= 0.5,
                        schnee_hoch=bool(nass) and sum(v['sn_h'] for v in nass) / len(nass) >= 0.5)
        N = dict(tag=teil(6, 24), vm=teil(6, 12), nm=teil(12, 18), ab=teil(18, 24), nacht=teil(0, 6))
        d['nied'] = dict(stufe=N['tag']['stufe'], vm=N['vm']['stufe'], nm=N['nm']['stufe'], ab=N['ab']['stufe'],
                         p=N['tag']['p'], mm=N['tag']['mm'], schnee_tal=N['tag'].get('schnee_tal', False), schnee_hoch=N['tag'].get('schnee_hoch', False))
        d['rp'], d['rp_vm'], d['rp_nm'], d['rp_ab'] = N['tag']['p'], N['vm']['p'], N['nm']['p'], N['ab']['p']
        d['regen'] = round(sum(v['mm'] for v in H_.values()), 1)
        st_ = d['nied']['stufe']; c = d['code']
        # Wettersymbol an die Einstufung angleichen: nass nur, wenn es wirklich nach Regen aussieht
        if st_ in ('trocken', 'vereinzelt') and c in NASS_CODES:
            if d['nied']['schnee_tal'] and st_ == 'vereinzelt': pass
            else: c = 1 if d.get('sonne', 0) >= 7 else 2 if d.get('sonne', 0) >= 4 else 3
        elif st_ == 'gewitter': c = 95
        elif st_ in ('schauer', 'regen'):
            if d['nied']['schnee_tal']: c = 73 if st_ == 'regen' else 85
            elif st_ == 'regen' and (c not in NASS_CODES or c >= 80): c = 63 if d['nied']['mm'] >= 5 else 61
            elif st_ == 'schauer' and (c not in NASS_CODES or c >= 95 or 71 <= c <= 77 or c in (85, 86)): c = 80
        if c != d['code']: print('Wettersymbol %s angeglichen: %s -> %s (Regen-Stufe %s, %s %%)' % (tag, d['code'], c, st_, d['rp']))
        d['code'] = c
        if d.get('tal'): d['tal']['code'] = c
        if d.get('hoch') and d['nied']['schnee_hoch']: d['hoch']['schnee'] = True   # im Tal Regen, oben Schnee
        # Stundenwerte der Grafik: Regenrisiko/-menge aus derselben Grundlage, Symbole passend
        for x in d.get('stunden') or []:
            v = H_.get(x['h'])
            if not v: continue
            x['rp'] = v['p']; x['mm'] = round(v['mm'], 1)
            if v['p'] < 30 and x.get('code', 0) in NASS_CODES: x['code'] = 3
            elif v['p'] >= 30 and x.get('code', 0) not in NASS_CODES: x['code'] = 80


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
    fm = d.get('frost_min', d['tmin'])   # Frost: vorsichtig nach dem kältesten Talort
    L = d.get('lage') or {}
    if L.get('glaette') == 'glatteis': h.insert(0, 'Glatteis möglich')
    elif L.get('glaette') in ('naesse', 'reif'): h.append('Glätte möglich')
    if L.get('nebel') == 'wahrscheinlich': h.append('morgens Nebel in den Tälern')
    if fm <= 0: h.append('Frost bis %d °C – Scheiben kratzen!' % fm)
    elif fm <= 3 and d.get('nacht_klar'): h.append('Bodenfrost möglich')   # nur klare, windstille Nacht
    if d['boe'] >= 60: h.append('Sturmböen bis %d km/h' % round(d['boe']))
    elif d['boe'] >= 45: h.append('Windböen bis %d km/h' % round(d['boe']))
    if d['regen'] >= 10: h.append('viel Regen (%.0f l/m²)' % d['regen'])
    H = d.get('hoch')
    if H and H['schnee']: h.insert(0, 'Schnee auf den Höhen – Glätte möglich')
    elif L.get('glaette_hoch') in ('naesse', 'reif', 'glatteis') and L.get('glaette') == 'keine': h.append('Glätte auf den Höhen möglich')
    elif H and H['tmin'] <= 0 < d['tmin']: h.append('Frost auf den Höhen bis %d °C' % H['tmin'])
    return h


def hoehe_txt(d):
    H = d.get('hoch')
    if not H: return ''
    return ' Höhen (z. B. Oberzent): %d bis %d °C%s.' % (H['tmin'], H['tmax'], ', Schnee möglich ❄️' if H['schnee'] else '')


def text(days, warn):
    a, b = days[:2]
    gruss = 'Mahlzeit, Odenwald! %s Euer Wetter für den Rest des Tages:' % emoji(a['code'])
    rest = [n for n, p in (('am Nachmittag', a['rp_nm']), ('am Abend', a['rp_ab'])) if p >= 40]
    zeilen = [gruss, '',
              'Heute Nachmittag (%s): %s, in den Tälern bis %d °C%s.%s' % (TAGE[a['datum'].weekday()], wort(a['code']), a['tmax'],
                  (', Regen vor allem ' + ' und '.join(rest)) if rest else ', meist trocken',
                  (' Auf den Höhen um %d °C%s.' % (a['hoch']['tmax'], ', Schnee möglich ❄️' if a['hoch']['schnee'] else '')) if a.get('hoch') else ''),
              '🌃 Heute Nacht: Täler um %d °C%s.' % (b['tmin'], (', Höhen um %d °C' % b['hoch']['tmin']) if b.get('hoch') else '')]
    # mittags zählt der Frost der kommenden Nacht (Tiefstwert von morgen früh), nicht der von heute früh
    nacht = dict(a, tmin=b['tmin'], frost_min=b.get('frost_min', b['tmin']), hoch=(dict(a['hoch'], tmin=b['hoch']['tmin']) if a.get('hoch') and b.get('hoch') else a.get('hoch')))
    for x in hinweise(nacht): zeilen.append('⚠️ ' + x.replace('Frost bis', 'Heute Nacht Frost bis'))
    zeilen.append('Morgen (%s): %s %s, Täler %d bis %d °C%s' % (TAGE[b['datum'].weekday()], emoji(b['code']), wort(b['code']), b['tmin'], b['tmax'],
                  (', Höhen um %d °C.' % b['hoch']['tmax']) if b.get('hoch') else '.'))
    for w in warn[:3]: zeilen.append('🚨 DWD: ' + w)
    zeilen += ['', '📍 Vorhersage für den Odenwaldkreis (Täler und Höhen) aus vier Wettermodellen – Messwerte von unserer Station in Bad König.',
               'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de', '#Odenwald #Odenwaldkreis #BadKönig #Wetter']
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
    ct('Odenwald-Wetter', 40, font(64, True))
    ct(kopf or ('Mittagswetter · ' + dat), 125, font(38))
    ct('Private Wetterstation Bad König', 180, font(28), fill=(235, 242, 252))
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
        w = dr.textlength(info, font=f); dr.text((cx - w / 2, y0 + (525 if d.get('hoch') else 540)), info, font=f, fill=(90, 105, 125))
        info = 'Böen %d km/h  ·  Sonne %.0f h' % (round(d['boe']), d['sonne'])
        w = dr.textlength(info, font=f); dr.text((cx - w / 2, y0 + (562 if d.get('hoch') else 580)), info, font=f, fill=(90, 105, 125))
        if d.get('hoch'):   # Täler (oben, große Zahlen) und Höhen (Oberzent/Mossautal)
            f = font(26, True); t = 'TAL'; dr.text((x0 + 40, y0 + 380), t, font=font(22, True), fill=(150, 160, 175))
            info = 'Höhen: %d° / %d°%s' % (d['hoch']['tmax'], d['hoch']['tmin'], '  ·  Schnee' if d['hoch']['schnee'] else '')
            w = dr.textlength(info, font=f); dr.text((cx - w / 2, y0 + 598), info, font=f, fill=(57, 73, 171))
    # Hinweisband
    ah = a
    if not nacht and kopf is None and len(days) > 1:   # Mittagsbeitrag: Frost der kommenden Nacht
        b_ = days[1]; ah = dict(a, tmin=b_['tmin'], frost_min=b_.get('frost_min', b_['tmin']), hoch=(dict(a['hoch'], tmin=b_['hoch']['tmin']) if a.get('hoch') and b_.get('hoch') else a.get('hoch')))
    h = (['DWD: ' + w for w in warn[:1]] + [x.replace('Frost bis', 'Nachts Frost bis') if ah is not a else x for x in hinweise(ah)])[:2]
    if h:
        dr.rounded_rectangle([60, 900, W - 60, 1020], radius=28, fill=(255, 243, 205) if not warn else (255, 222, 210))
        f = font(36, True); t = '⚠  ' if False else ''
        y = 960 - 24 * len(h)
        for line in h:
            w = dr.textlength(line, font=f); dr.text(((W - w) / 2, y), line, font=f, fill=(150, 70, 20)); y += 48
    ct('wetter-badkoenig.de', H - 105, font(52, True), fill=(255, 220, 140) if nacht else (70, 95, 140), sh=False)
    im.save(path, quality=90)


def regenwort(p):
    return 'trocken' if p < 10 else 'vereinzelt Schauer möglich' if p < 30 else 'örtlich Schauer möglich' if p < 60 else 'nass'


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
    if d.get('hoch') and d['hoch']['schnee'] and d['schnee'] < 1: return 'Auf den Höhen kann es schneien – Richtung Beerfelden und Oberzent vorsichtig fahren! 🚗❄️'
    if d['schnee'] >= 1: return 'Schnee im Odenwald – warm anziehen, auf den Höhen kann es glatt werden. ⛄'
    if w == 'Gewitter': return 'Bei Gewitter Wanderungen lieber verschieben und rechtzeitig Schutz suchen.'
    gl = (d.get('lage') or {}).get('glaette', 'keine')
    if gl == 'glatteis': return 'Achtung, Glatteis möglich – morgens langsam fahren und vorsichtig gehen! 🧊'
    if gl in ('naesse', 'schnee', 'reif'): return 'Morgens Scheiben kratzen einplanen und auf Glätte achten! 🧊'
    if d.get('frost_min', d['tmin']) <= 0: return 'Morgens Scheiben kratzen einplanen! 🧊'
    if d.get('nied', {}).get('stufe') == 'regen' or d['rp'] >= 70: return 'Ein guter Tag für drinnen – oder mit Regenjacke raus. ☔'
    if d['sonne'] >= 5 and d['rp'] < 30: return 'Ideales Wetter für eine Runde im Odenwald – raus an die frische Luft! 🥾'
    if d['rp'] < 30: return 'Für einen Spaziergang passt es, eine Jacke sollte aber mit.'
    return 'Schirm griffbereit halten – Schauer sind möglich.'


def text_abend(paar, wochenende, warn, rest=()):
    a, b = paar
    zeilen = ['Guten Abend Odenwald! 🌙 ' + ('Euer Wochenendwetter für den Odenwald:' if wochenende else 'Hier kommt der Wetterausblick für morgen:'), '']
    zeilen.append('🌃 Heute Nacht: in den Tälern um %d °C%s%s.' % (a['tmin'], ' – Frost!' if a['tmin'] <= 0 else ', Bodenfrost möglich' if a['tmin'] <= 3 and a.get('nacht_klar') else '',
                  (', auf den Höhen um %d °C' % a['hoch']['tmin']) if a.get('hoch') else ''))
    zeilen.append('')
    for name, d in ((('Samstag', a), ('Sonntag', b)) if wochenende else (('Morgen', a),)):
        zeilen.append('📅 %s (%s): %s %s, Täler %d bis %d °C' % (name, TAGE[d['datum'].weekday()], emoji(d['code']), wort(d['code']), d['tmin'], d['tmax']))
        if d.get('hoch'): zeilen.append('⛰️ Höhen (Oberzent, Mossautal): %d bis %d °C%s' % (d['hoch']['tmin'], d['hoch']['tmax'], ' – Schnee möglich ❄️' if d['hoch']['schnee'] else ''))
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
               '📍 Vorhersage für den Odenwaldkreis aus vier Wettermodellen – Messwerte von unserer Station in Bad König.',
               'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de', '#Odenwald #Odenwaldkreis #BadKönig #Wetter #Wetterbericht']
    return '\n'.join(zeilen)


def treffer_merken(days, now):
    """Trefferquote: Vorhersage für Bad König (Vorabend ab 18 Uhr / früh vor 10 Uhr) und Messwert von gestern -> fb/treffer.json"""
    p = os.path.join(OUT, 'treffer.json')
    try: T = json.load(open(p, encoding='utf-8'))
    except Exception: T = {}
    def v(x):
        b = x.get('bk') or x
        return {'tmax': b['tmax'], 'tmin': b['tmin'], 'regen': round(b.get('regen') or 0, 1), 'rp': b.get('rp'), 'am': now.isoformat(timespec='minutes')}
    try:
        heute = now.date()
        for x in days[:2]:
            D = x['datum']; k = D.isoformat()
            if D == heute + dt.timedelta(days=1) and now.hour >= 18: T.setdefault(k, {})['abend'] = v(x)
            elif D == heute and now.hour < 10 and 'morgen' not in T.get(k, {}): T.setdefault(k, {})['morgen'] = v(x)
        g = days[0].get('gestern') if days and days[0]['datum'] == heute else None
        if g and g.get('tmax') is not None:
            T.setdefault((heute - dt.timedelta(days=1)).isoformat(), {})['ist'] = {'tmax': g['tmax'], 'tmin': g['tmin'], 'regen': g.get('regen')}
        grenze = (heute - dt.timedelta(days=60)).isoformat()
        T = {k: T[k] for k in sorted(T) if k >= grenze}
        json.dump(T, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception as e:
        print('Trefferquote nicht gespeichert:', e)


ORTE_KARTE = [('Breuberg', 49.818, 9.040, 'r'), ('Höchst', 49.799, 8.994, 'l'), ('Bad König', 49.743, 9.006, 'r'),
              ('Mossautal', 49.667, 8.937, 'l'), ('Michelstadt', 49.678, 9.004, 'r'), ('Oberzent', 49.567, 8.976, 'r')]


def mittagskarte(days, warn, path):
    """Mittagsbeitrag (1200x1200): Reliefkarte des Odenwaldkreises mit den Werten für den Rest des Tages,
    dazu der aktuelle Messwert der eigenen Station in Bad König."""
    W = H = 1200
    d = days[0]
    rest = orte_rest(d['datum'])
    live = live_station()
    im = Image.new('RGB', (W, H), (238, 242, 247)); dr = ImageDraw.Draw(im)
    for y in range(170):   # Kopfband
        dr.line([0, y, W, y], fill=(int(22 + 16 * y / 170), int(70 + 22 * y / 170), int(130 + 30 * y / 170)))
    dr.rectangle([0, 170, W, 178], fill=(245, 175, 40))
    dr.text((40, 58), 'NACHMITTAG IM ODENWALDKREIS', font=font(52, True), fill=(255, 255, 255))
    dr.text((40, 118), '%s, %d. %s' % (TAGE[d['datum'].weekday()], d['datum'].day, MONATE[d['datum'].month - 1]), font=font(36), fill=(205, 222, 245))
    # Reliefkarte mittig
    KW, KH = 520, 841
    KX, KY = 410, 215
    DAT = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
    G = json.load(open(os.path.join(DAT, 'odenwald-relief.json'), encoding='utf-8'))
    (lo0, lo1), (la0, la1) = G['lo'], G['la']
    try:   # Relief auf die echte Kreisgrenze zuschneiden (kein Rechteck)
        grenze = json.load(open(os.path.join(DAT, 'odenwald-grenze.json'), encoding='utf-8'))['punkte']
        rand = [((lo - lo0) / (lo1 - lo0) * KW, (la1 - la) / (la1 - la0) * KH) for lo, la in grenze]
        rel = Image.open(os.path.join(DAT, 'odenwald-relief.png')).convert('RGBA').resize((KW, KH), Image.LANCZOS)
        maske = Image.new('L', (KW, KH), 0); ImageDraw.Draw(maske).polygon(rand, fill=255)
        rel.putalpha(maske)
        im.paste(rel, (KX, KY), rel)
        dr.line([(KX + x, KY + y) for x, y in rand] + [(KX + rand[0][0], KY + rand[0][1])],
                fill=(70, 85, 105), width=4, joint='curve')
    except Exception as e:
        print('Reliefkarte nicht gezeichnet:', e)
    fn, fw = font(26), font(40, True)
    for name, la, lo, seite in ORTE_KARTE:
        r = rest.get(name)
        if not r: continue
        x = KX + (lo - lo0) / (lo1 - lo0) * KW
        y = KY + (la1 - la) / (la1 - la0) * KH
        txt = '%d°' % r['tmax']
        bw = max(dr.textlength(name, font=fn), dr.textlength(txt, font=fw)) + 36
        bx = x + 22 if seite == 'r' else x - 22 - bw
        bx = max(8, min(bx, W - bw - 8)); by = max(190, min(y - 44, H - 260))
        dr.rounded_rectangle([bx, by, bx + bw, by + 88], radius=18, fill=(214, 88, 36))
        dr.text((bx + bw / 2, by + 24), name, font=fn, fill=(255, 232, 220), anchor='mm')
        dr.text((bx + bw / 2, by + 62), txt, font=fw, fill=(255, 255, 255), anchor='mm')
        dr.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(255, 255, 255), outline=(40, 50, 70), width=4)
    # Messwert der eigenen Station
    if live:
        dr.rounded_rectangle([40, 230, 380, 520], radius=28, fill=(255, 255, 255))
        dr.text((210, 272), 'JETZT GEMESSEN', font=font(28, True), fill=(120, 135, 155), anchor='mm')
        dr.text((210, 350), ('%.1f°' % live['temp']).replace('.', ','), font=font(104, True), fill=(214, 88, 36), anchor='mm')
        dr.text((210, 428), 'Station Bad König', font=font(30, True), fill=(35, 55, 85), anchor='mm')
        dr.text((210, 470), '%s Uhr · 184,5 m' % live['zeit'], font=font(26), fill=(110, 125, 145), anchor='mm')
    y0 = 560 if live else 240
    dr.rounded_rectangle([40, y0, 380, y0 + 250], radius=28, fill=(255, 255, 255))
    dr.text((210, y0 + 40), 'REST DES TAGES', font=font(28, True), fill=(120, 135, 155), anchor='mm')
    zz = [wort(d['code']).capitalize(), 'Regen %d %%' % d['rp'] if d['rp'] >= 20 else 'meist trocken']
    if d.get('hoch'): zz.append('Höhen bis %d°' % d['hoch']['tmax'])
    for i, z in enumerate(zz[:3]):
        dr.text((210, y0 + 100 + i * 52), z, font=font(32, True), fill=(35, 55, 85), anchor='mm')
    if warn:
        fz = font(24); zl, cur = [], ''
        for wd in warn[0].split():
            if dr.textlength((cur + ' ' + wd).strip(), font=fz) > 290: zl.append(cur); cur = wd
            else: cur = (cur + ' ' + wd).strip()
        zl.append(cur)
        dr.rounded_rectangle([40, 860, 380, 860 + 80 + len(zl[:3]) * 34], radius=28, fill=(200, 45, 45))
        dr.text((210, 900), 'DWD-WARNUNG', font=font(30, True), fill=(255, 255, 255), anchor='mm')
        for i, z in enumerate(zl[:3]):
            dr.text((210, 945 + i * 34), z, font=fz, fill=(255, 230, 230), anchor='mm')
    dr.text((W / 2, H - 92), 'Messwert aus Bad König · übrige Orte aus der Modellmischung', font=font(26), fill=(95, 110, 130), anchor='mm')
    dr.text((W / 2, H - 52), 'Live-Werte & Vorhersage: wetter-badkoenig.de', font=font(34, True), fill=(25, 85, 160), anchor='mm')
    im.save(path, quality=90)
    return rest, live


def text_mittag(days, rest, live, warn):
    d = days[0]
    z = ['🗺️ Nachmittag im Odenwaldkreis – so geht der Tag weiter:', '']
    if live: z += ['🌡️ Jetzt an unserer Station in Bad König: %s °C (%s Uhr)' % (('%.1f' % live['temp']).replace('.', ','), live['zeit']), '']
    teile = ['%s %d°' % (n, rest[n]['tmax']) for n, *_ in ORTE_KARTE if rest.get(n)]
    if teile: z += ['📍 Höchstwerte bis zum Abend: ' + ' · '.join(teile), '']
    z.append('%s %s%s.' % (emoji(d['code']), wort(d['code']).capitalize(),
                           ', Regenrisiko %d %%' % d['rp'] if d['rp'] >= 30 else ', meist trocken'))
    if d.get('hoch'): z.append('⛰️ Auf den Höhen (Oberzent, Mossautal) bis %d °C.' % d['hoch']['tmax'])
    for w in warn[:2]: z.append('🚨 DWD: ' + w)
    z += ['', 'Gemessen wird in Bad König, die übrigen Orte kommen aus unserer Modellmischung (ICON-D2, AROME, ECMWF, ICON-EU) – je Ort mit seiner Höhe.',
          'Live-Werte, Radar & Vorhersage 👉 https://wetter-badkoenig.de',
          '#Odenwald #Odenwaldkreis #BadKönig #Wetter #Michelstadt #Erbach #Höchst #Breuberg']
    return '\n'.join(z)


def story(days, warn, path, abends=False):
    """Instagram-Story (1080x1920). morgens: das Wetter von heute (fb/story.jpg),
    abends: der Ausblick auf morgen in Abendfarben (fb/abendstory.jpg)."""
    d = days[1] if abends else days[0]
    W, H = 1080, 1920
    im = Image.new('RGB', (W, H)); dr = ImageDraw.Draw(im)
    for y in range(H):   # Verlauf: morgens Morgenhimmel, abends Abendhimmel
        t = y / H
        dr.line([0, y, W, y], fill=(int(30 + 60 * t), int(35 + 55 * t), int(90 + 60 * t)) if abends
                else (int(40 + 90 * t), int(110 + 80 * t), int(200 + 30 * t)))
    def mitte(y, txt, f, col=(255, 255, 255)):
        w = dr.textlength(txt, font=f); dr.text(((W - w) / 2, y), txt, font=f, fill=col)
    mitte(150, 'ODENWALD-WETTER', font(64, True), (255, 230, 150))
    mitte(235, ('Morgen, ' if abends else '') + '%s, %d. %s' % (TAGE[d['datum'].weekday()], d['datum'].day, MONATE[d['datum'].month - 1]), font(52))
    icon(dr, W / 2, 560, 380, d['code'])
    mitte(830, wort(d['code']).capitalize() if wort(d['code'])[:1].islower() else wort(d['code']), font(64, True))
    mitte(940, '%d° / %d°' % (d['tmax'], d['tmin']), font(170, True))
    mitte(1135, 'Täler Höchst / Tiefst', font(40), (225, 235, 250))
    y = 1240
    dr.rounded_rectangle([90, y, W - 90, y + 330], radius=40, fill=(255, 255, 255))
    zeilen = ['☔ Regenrisiko %d %%' % d['rp'] if d['rp'] >= 20 else '☀ meist trocken',
              '💨 Böen bis %d km/h' % round(d['boe']) if d.get('boe') else '',
              ('⛰ Höhen %d° / %d°' % (d['hoch']['tmax'], d['hoch']['tmin'])) if d.get('hoch') else '']
    zeilen = [z for z in zeilen if z][:3]
    for i, z in enumerate(zeilen):
        z = z.replace('☔ ', '').replace('☀ ', '').replace('💨 ', '').replace('⛰ ', '')
        mitte(y + 40 + i * 95, z, font(56, True), (30, 60, 110))
    if d.get('frost_min', d['tmin']) <= 0: mitte(1610, 'Morgens Scheiben kratzen!', font(54, True), (255, 245, 200))
    elif warn: mitte(1610, 'DWD-Warnung beachten!', font(54, True), (255, 220, 200))
    mitte(1730, 'Live-Werte & Vorhersage', font(42), (230, 240, 255))
    mitte(1790, 'wetter-badkoenig.de', font(58, True))
    im.save(path, quality=90)


def mittagstory(src, path):
    """Mittags-Story (1080x1920) für Facebook + Instagram: die quadratische Mittagskarte im Hochformat,
    oben und unten Rahmen, damit in der Story nichts abgeschnitten wird."""
    W, H = 1080, 1920
    im = Image.new('RGB', (W, H)); dr = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        dr.line([0, y, W, y], fill=(int(22 + 30 * t), int(70 + 50 * t), int(130 + 60 * t)))
    def mitte(y, txt, f, col=(255, 255, 255)):
        w = dr.textlength(txt, font=f); dr.text(((W - w) / 2, y), txt, font=f, fill=col)
    mitte(190, 'ODENWALD-WETTER', font(64, True), (255, 230, 150))
    mitte(275, 'Mittags-Update', font(52))
    karte = Image.open(src).convert('RGB').resize((W - 60, W - 60))
    im.paste(karte, (30, 420))
    mitte(1530, 'So geht der Tag weiter', font(54, True))
    mitte(1730, 'Live-Werte & Vorhersage', font(42), (230, 240, 255))
    mitte(1790, 'wetter-badkoenig.de', font(58, True))
    im.save(path, quality=90)


def abend(now):
    """Abendlauf (19 Uhr): Text und Bild für den Ausblick auf morgen/übermorgen (freitags Wochenende)
    -> fb/abend.jpg + fb/abend.json (Text ist die Beschreibung des Abendvideos) sowie die Abend-Story fb/abendstory.jpg."""
    if '--nur-abends' in sys.argv:
        if now.hour < 19:
            print('Noch vor 19 Uhr Ortszeit (%s) – übersprungen.' % now.strftime('%H:%M')); return
        try:
            alt = dt.datetime.fromisoformat(json.load(open(os.path.join(OUT, 'abend.json'), encoding='utf-8'))['erstellt']).astimezone(TZ)
            if alt.date() == now.date() and alt.hour >= 19: print('Abendbeitrag heute schon erstellt – übersprungen.'); return
        except Exception:
            pass
    days, warn = demo() if DEMO else load()
    if not DEMO: treffer_merken(days, now)
    wochenende = days[0]['datum'].weekday() == 4   # Freitag
    paar = days[1:3]
    labels = ('SAMSTAG', 'SONNTAG') if wochenende else ('MORGEN', 'ÜBERMORGEN')
    kopf = 'Wochenendwetter' if wochenende else 'Ausblick auf %s, %d. %s' % (TAGE[paar[0]['datum'].weekday()], paar[0]['datum'].day, MONATE[paar[0]['datum'].month - 1])
    os.makedirs(OUT, exist_ok=True)
    bild(paar, warn, os.path.join(OUT, 'abend.jpg'), labels, kopf, nacht=True)
    txt = text_abend(paar, wochenende, warn, days[3:6])
    open(os.path.join(OUT, 'abend.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'erstellt': now.isoformat(timespec='minutes'), 'text': txt}, open(os.path.join(OUT, 'abend.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    try:   # Abend-Story für Instagram: das Wetter von morgen
        story(days, warn, os.path.join(OUT, 'abendstory.jpg'), abends=True)
        json.dump({'erstellt': now.isoformat(timespec='minutes'), 'datum': days[0]['datum'].isoformat()},
                  open(os.path.join(OUT, 'abendstory.json'), 'w', encoding='utf-8'))
    except Exception as e: print('Abend-Story nicht erstellt:', e)
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
    if not DEMO: treffer_merken(days, now)
    bild(days, warn, os.path.join(OUT, 'post.jpg'))
    try:
        story(days, warn, os.path.join(OUT, 'story.jpg'))
        json.dump({'erstellt': now.isoformat(timespec='minutes'), 'datum': days[0]['datum'].isoformat()}, open(os.path.join(OUT, 'story.json'), 'w', encoding='utf-8'))
    except Exception as e: print('Story nicht erstellt:', e)
    txt = text(days, warn)
    open(os.path.join(OUT, 'post.txt'), 'w', encoding='utf-8').write(txt)
    json.dump({'erstellt': now.isoformat(timespec='minutes'), 'warn': warn, 'tage': [dict(d, datum=d['datum'].isoformat()) for d in days],
               'orte': {} if DEMO else orte_einzeln(days)},
              open(os.path.join(OUT, 'daten.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({'erstellt': now.isoformat(timespec='minutes'), 'text': txt}, open(os.path.join(OUT, 'post.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    if '--mittag' in sys.argv:   # Mittagsbeitrag: Reliefkarte des Kreises mit dem Rest des Tages
        try:
            rest, live = mittagskarte(days, warn, os.path.join(OUT, 'mittag.jpg'))
            mtxt = text_mittag(days, rest, live, warn)
            open(os.path.join(OUT, 'mittag.txt'), 'w', encoding='utf-8').write(mtxt)
            json.dump({'erstellt': now.isoformat(timespec='minutes'), 'datum': days[0]['datum'].isoformat(), 'text': mtxt},
                      open(os.path.join(OUT, 'mittag.json'), 'w', encoding='utf-8'), ensure_ascii=False)
            print(mtxt)
            try:   # Mittags-Story (Hochformat) für Facebook + Instagram
                mittagstory(os.path.join(OUT, 'mittag.jpg'), os.path.join(OUT, 'mittagstory.jpg'))
                json.dump({'erstellt': now.isoformat(timespec='minutes'), 'datum': days[0]['datum'].isoformat()},
                          open(os.path.join(OUT, 'mittagstory.json'), 'w', encoding='utf-8'))
            except Exception as e: print('Mittags-Story nicht erstellt:', e)
        except Exception as e:
            print('Mittagskarte nicht erstellt:', e)
    print(txt)


if __name__ == '__main__':
    main()
