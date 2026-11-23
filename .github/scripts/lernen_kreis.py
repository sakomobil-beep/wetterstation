#!/usr/bin/env python3
"""Lernkurve für den Odenwaldkreis (läuft mit dem Lern-Job alle 3 Stunden).
Je Ort: stündlich die vier Modelle (ICON-D2, AROME, ECMWF, ICON-EU, für die Höhe des Ortes) neben der Messung einer Station speichern
-> data/lernen-kreis/JJJJ-MM.json. Daraus je Ort und Modell: Abweichung je Tageszeit (6 Blöcke à 4 h) und mittlerer Fehler
-> data/lernen-kreis.json. Website, Facebook und Max korrigieren damit jedes Modell und gewichten die Modelle nach Trefferquote."""
import json, os, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LD = os.path.join(ROOT, 'data', 'lernen-kreis')
WU_KEY = '43a8f308d89b471ba8f308d89b671b69'
MODELLE = ('icon_d2', 'meteofrance_arome_france_hd', 'ecmwf_ifs025', 'icon_eu')
# Ort: (lat, lon, Höhe, Messquelle)  – dwd:<Stations-ID> oder wu:<Weather-Underground-ID>
ORTE = {
    'badkoenig':   (49.743, 9.006, 185, 'wu:IBADKN33'),
    'breuberg':    (49.818, 9.040, 160, 'wu:IBREUB7'),
    'hoechst':     (49.799, 8.994, 170, 'wu:IHCHST74'),
    'michelstadt': (49.678, 9.004, 208, 'dwd:03284'),
    'mossautal':   (49.667, 8.937, 315, 'wu:IMOSSA13'),   # 22.11.2026: private Station im Ort (vorher DWD 03287 Michelstadt-Vielbrunn, 453 m)
    'oberzent':    (49.567, 8.976, 430, 'dwd:00330'),   # Oberzent-Beerfelden, 455 m
    'reichelsheim': (49.713, 8.838, 215, 'wu:IREICH180'),   # 19.11.2026: private Station, 0,3 km von der Ortsmitte
    'brombachtal': (49.733, 8.945, 250, 'wu:IBROMB4'),   # 19.11.2026: private Station, 1,6 km von der Ortsmitte
}
# Verzögerung: Messungen werden sofort gesammelt, die Korrektur wird erst ab diesem Tag verwendet (Kingman 19.11.2026: 6 Tage)
LERNEN_AB = {}   # 22.11.2026, 16:30 Uhr: Brombachtal, Reichelsheim, Mossautal ab 01.11. nachgetragen (WU-Stundenwerte + Open-Meteo) – keine Wartezeit mehr
TAGE_HALTEN, GUETE_TAGE, HALBWERT = 120, 21, 14.0
# 22.11.2026: Lernen nach Wetterlage wie bei Bad König (klar / wolkig / windig aus ICON-D2-Bewölkung und -Wind).
# Korrektur aus bis zu 90 Tagen (Halbwertszeit 30 Tage), Trefferquote (mae) weiter aus den letzten 21 Tagen.
LAGE_TAGE, LAGE_HALBWERT, LAGE_MIN = 90, 30.0, 8   # LAGE_MIN: so viele Stunden je Lage und Tageszeit-Block, sonst gilt die allgemeine Korrektur


def lage(cc, ws):
    """Wetterlage einer Stunde (gleich wie lernen.py): windig ab 15 km/h, klar unter 35 % Wolken, sonst wolkig."""
    if ws is not None and ws >= 15: return 'windig'
    if cc is not None and cc < 35: return 'klar'
    return 'wolkig'


def get(url):
    try:   # 19.11.2026: eigene Station aus eigenen Daten statt WU
        from eigene_daten import ersatz
        e = ersatz(url)
        if e is not None: return e
    except ImportError: pass
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de lernen-kreis'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def messung(quelle, jetzt):
    art, sid = quelle.split(':', 1); out = {}
    if art == 'wu':
        for o in get('https://api.weather.com/v2/pws/observations/hourly/7day?stationId=%s&format=json&units=m&apiKey=%s' % (sid, WU_KEY)).get('observations') or []:
            v = (o.get('metric') or {}).get('tempAvg')
            if v is not None: out[dt.datetime.fromtimestamp(o['epoch'], TZ).strftime('%Y-%m-%dT%H')] = round(v, 1)
    else:
        von = (jetzt - dt.timedelta(days=6)).date().isoformat()
        for r in get('https://api.brightsky.dev/weather?dwd_station_id=%s&date=%s&last_date=%s&tz=Europe/Berlin'
                     % (sid, von, (jetzt + dt.timedelta(days=1)).date().isoformat())).get('weather') or []:
            if r.get('temperature') is None: continue
            t = dt.datetime.fromisoformat(r['timestamp'])
            if t <= jetzt: out[t.astimezone(TZ).strftime('%Y-%m-%dT%H')] = round(r['temperature'], 1)
    return out


def main():
    os.makedirs(LD, exist_ok=True)
    rows = {}
    for f in sorted(os.listdir(LD)):
        if f.endswith('.json'):
            try:
                for o, d in json.load(open(os.path.join(LD, f), encoding='utf-8')).items(): rows.setdefault(o, {}).update(d)
            except Exception: pass
    jetzt = dt.datetime.now(TZ)
    for ort, (la, lo, el, q) in ORTE.items():
        try:
            st = messung(q, jetzt)
            H = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&elevation=%s&models=%s&hourly=temperature_2m,cloud_cover,wind_speed_10m'
                    '&past_days=7&forecast_days=1&timezone=Europe%%2FBerlin' % (la, lo, el, ','.join(MODELLE)))['hourly']
        except Exception as e:
            print(ort, 'nicht abrufbar:', e); continue
        R = rows.setdefault(ort, {})
        for i, t in enumerate(H['time']):
            k = t[:13]
            if k not in st: continue
            m = {x: round(H['temperature_2m_' + x][i], 1) for x in MODELLE if H.get('temperature_2m_' + x) and H['temperature_2m_' + x][i] is not None}
            if not m: continue
            cc = next((H['cloud_cover_' + x][i] for x in ('icon_d2', 'icon_eu') if H.get('cloud_cover_' + x) and H['cloud_cover_' + x][i] is not None), None)
            ws = next((H['wind_speed_10m_' + x][i] for x in ('icon_d2', 'icon_eu') if H.get('wind_speed_10m_' + x) and H['wind_speed_10m_' + x][i] is not None), None)
            R[k] = {'st': st[k], 'm': m, 'cc': cc, 'ws': ws}
        print(ort, len(st), 'Messungen,', len(R), 'Stunden gesamt')
    grenze = (jetzt - dt.timedelta(days=TAGE_HALTEN)).strftime('%Y-%m-%dT%H')
    monate = {}
    for ort, R in rows.items():
        for k, v in R.items():
            if k >= grenze: monate.setdefault(k[:7], {}).setdefault(ort, {})[k] = v
    for f in os.listdir(LD):
        if f.endswith('.json') and f[:7] not in monate: os.remove(os.path.join(LD, f))
    for mo, inhalt in monate.items():
        json.dump(inhalt, open(os.path.join(LD, mo + '.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    # Lernen: je Ort und Modell Abweichung je Tageszeit (gewichteter Median-ähnlicher Mittelwert, Ausreißer gekappt) + mittlerer Fehler danach
    seit = (jetzt - dt.timedelta(days=GUETE_TAGE)).strftime('%Y-%m-%dT%H')
    seitL = (jetzt - dt.timedelta(days=LAGE_TAGE)).strftime('%Y-%m-%dT%H')
    out = {'erstellt': jetzt.isoformat(timespec='minutes'), 'orte': {}}
    for ort, R in rows.items():
        H = {k: v for k, v in R.items() if k >= seit}
        if not H: continue
        if jetzt.date().isoformat() < LERNEN_AB.get(ort, ''): print(ort, 'sammelt noch, lernt ab', LERNEN_AB[ort]); continue
        # Stationsprüfung: weicht die Station im Mittel > 4 °C von allen Modellen ab, ist sie unbrauchbar (Sonne, Hauswand …)
        mit = [v['st'] - sum(v['m'].values()) / len(v['m']) for v in H.values()]
        if abs(sum(mit) / len(mit)) > 4: out['orte'][ort] = {'unbrauchbar': True, 'n': len(H)}; continue
        E = {'n': len(H), 'tage': len({k[:10] for k in H}), 'bias': {}, 'mae': {}, 'mae_roh': {}}   # mae_roh = Fehler reines Modell ohne Korrektur (19.11.2026)
        HL = {k: v for k, v in R.items() if k >= seitL}
        E['n_lang'] = len(HL); E['tage_lang'] = len({k[:10] for k in HL})
        def alter(k, hw): return 0.5 ** ((jetzt - dt.datetime.strptime(k, '%Y-%m-%dT%H').replace(tzinfo=TZ)).total_seconds() / 86400 / hw)
        def lernbias(D, m):
            s = [[0.0, 0.0, 0] for _ in range(6)]
            for k, v in D.items():
                if m not in v['m']: continue
                w = alter(k, LAGE_HALBWERT); b = int(k[11:13]) // 4
                s[b][0] += w * max(-8, min(8, v['st'] - v['m'][m])); s[b][1] += w; s[b][2] += 1
            return s
        # Wetterlagen
        LG = {'klar': {}, 'wolkig': {}, 'windig': {}}
        for k, v in HL.items():
            if 'cc' in v or 'ws' in v: LG[lage(v.get('cc'), v.get('ws'))][k] = v
        E['lagen'] = {}
        for lg, D in LG.items():
            if not D: continue
            L = {'n': [0] * 6, 'bias': {}}
            for m in MODELLE:
                s = lernbias(D, m)
                L['n'] = [max(a, x[2]) for a, x in zip(L['n'], s)]
                L['bias'][m] = [round(max(-5, min(5, a / g)), 2) if g and c >= LAGE_MIN else None for a, g, c in s]
            E['lagen'][lg] = L
        def kbias(k, v, m):   # Korrektur für eine Stunde: Lage, wenn genug Daten, sonst allgemein
            b = int(k[11:13]) // 4
            if 'cc' in v or 'ws' in v:
                x = (E['lagen'].get(lage(v.get('cc'), v.get('ws'))) or {}).get('bias', {}).get(m)
                if x and x[b] is not None: return x[b]
            return E['bias'][m][b]
        for m in MODELLE:
            s = lernbias(HL, m)
            bias = [round(max(-5, min(5, a / g)), 2) if g else 0.0 for a, g, c in s]
            E['bias'][m] = bias
            fe = [abs(v['st'] - (v['m'][m] + kbias(k, v, m))) for k, v in H.items() if m in v['m']]
            if fe: E['mae'][m] = round(sum(fe) / len(fe), 2)
            fr = [abs(v['st'] - v['m'][m]) for v in H.values() if m in v['m']]
            if fr: E['mae_roh'][m] = round(sum(fr) / len(fr), 2)
        out['orte'][ort] = E
    json.dump(out, open(os.path.join(ROOT, 'data', 'lernen-kreis.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False)[:1500])


if __name__ == '__main__':
    main()
