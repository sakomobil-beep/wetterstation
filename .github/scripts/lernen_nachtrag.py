#!/usr/bin/env python3
"""Einmaliger Nachtrag für das Kreis-Lernen (22.11.2026): 3 Monate (ab 24.08.2026) Messwerte + Modellwerte
+ Bewölkung/Wind (für die Wetterlagen klar / wolkig / windig) für alle Orte aus lernen_kreis.ORTE.
Läuft nur, solange data/lernen-nachtrag.an existiert (nachts nach dem WU-Tageswechsel), löscht die Datei danach.
Messwerte: WU-Stundenwerte (history/hourly), eigene Station aus data/archiv, DWD über Bright Sky.
Modelle, Bewölkung, Wind: Open-Meteo (gleiche Abfrage wie lernen_kreis.py, nur rückwirkend).
Bereits gesammelte Stunden behalten ihre Werte, bekommen nur Bewölkung/Wind dazu."""
import json, os, sys, glob, time, urllib.request, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from lernen_kreis import ORTE, MODELLE, WU_KEY, LD, TZ, ROOT

AN = os.path.join(ROOT, 'data', 'lernen-nachtrag.an')
START = dt.date(2026, 8, 24)


def get(url, versuche=4):
    for v in range(versuche):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de lernen-nachtrag'}), timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if getattr(e, 'code', None) in (401, 403) or v == versuche - 1: raise
            print('  Wiederholung:', e); time.sleep(20 * (v + 1))


def eigene():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'archiv', 'stunden-*.json'))):
        for L in json.load(open(f, encoding='utf-8')).get('tage', {}).values():
            for o in L:
                v = (o.get('metric') or {}).get('tempAvg')
                if v is not None: out[dt.datetime.fromtimestamp(o['epoch'], TZ).strftime('%Y-%m-%dT%H')] = round(v, 1)
    return out


def wu_tage(sid, tage):
    out = {}
    for d in tage:
        for o in get('https://api.weather.com/v2/pws/history/hourly?stationId=%s&format=json&units=m&numericPrecision=decimal&date=%s&apiKey=%s'
                     % (sid, d.strftime('%Y%m%d'), WU_KEY)).get('observations') or []:
            v = (o.get('metric') or {}).get('tempAvg')
            if v is not None and o.get('qcStatus', 1) != -1: out[dt.datetime.fromtimestamp(o['epoch'], TZ).strftime('%Y-%m-%dT%H')] = round(v, 1)
        time.sleep(2.5)   # WU: höchstens ~30 Abfragen pro Minute
    return out


def dwd(sid, bis):
    out, d = {}, START
    while d < bis:
        e = min(d + dt.timedelta(days=10), bis)
        for r in get('https://api.brightsky.dev/weather?dwd_station_id=%s&date=%s&last_date=%s&tz=Europe/Berlin' % (sid, d, e)).get('weather') or []:
            if r.get('temperature') is not None:
                out[dt.datetime.fromisoformat(r['timestamp']).astimezone(TZ).strftime('%Y-%m-%dT%H')] = round(r['temperature'], 1)
        d = e
    return out


def main():
    if not os.path.exists(AN): print('Kein Nachtrag angefordert.'); return
    gestern = dt.datetime.now(TZ).date() - dt.timedelta(days=1)
    rows = {}
    for f in sorted(glob.glob(os.path.join(LD, '*.json'))):
        for o, d in json.load(open(f, encoding='utf-8')).items(): rows.setdefault(o, {}).update(d)
    fertig = True
    for ort, (la, lo, el, q) in ORTE.items():
        R = rows.setdefault(ort, {})
        try:
            art, sid = q.split(':', 1)
            if sid == 'IBADKN33': st = eigene()
            elif art == 'dwd': st = dwd(sid, gestern + dt.timedelta(days=1))
            else:   # nur Tage ohne gesammelte Stunden bei WU abfragen (spart Abfragen)
                tage, d = [], START
                while d <= gestern:
                    if sum(1 for h in range(24) if '%sT%02d' % (d.isoformat(), h) in R) < 20: tage.append(d)
                    d += dt.timedelta(days=1)
                print(ort, sid, len(tage), 'Tage von WU')
                st = wu_tage(sid, tage)
            H = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&elevation=%s&models=%s'
                    '&hourly=temperature_2m,cloud_cover,wind_speed_10m&start_date=%s&end_date=%s&timezone=Europe%%2FBerlin'
                    % (la, lo, el, ','.join(MODELLE), START.isoformat(), gestern.isoformat()))['hourly']
        except Exception as e:
            print(ort, 'Fehler:', e); fertig = False; continue
        neu = erg = 0
        for i, t in enumerate(H['time']):
            k = t[:13]
            def wert(var):
                return next((H[var + '_' + x][i] for x in ('icon_d2', 'icon_eu') if H.get(var + '_' + x) and H[var + '_' + x][i] is not None), None)
            cc, ws = wert('cloud_cover'), wert('wind_speed_10m')
            if k in R:
                if 'cc' not in R[k]: R[k]['cc'], R[k]['ws'] = cc, ws; erg += 1
                continue
            if k not in st: continue
            m = {x: round(H['temperature_2m_' + x][i], 1) for x in MODELLE if H.get('temperature_2m_' + x) and H['temperature_2m_' + x][i] is not None}
            if m: R[k] = {'st': st[k], 'm': m, 'cc': cc, 'ws': ws}; neu += 1
        print(ort, neu, 'Stunden neu,', erg, 'mit Bewölkung/Wind ergänzt,', len(R), 'gesamt')
        time.sleep(5)
    monate = {}
    for ort, R in rows.items():
        for k, v in R.items(): monate.setdefault(k[:7], {}).setdefault(ort, {})[k] = v
    for mo, inhalt in monate.items():
        json.dump(inhalt, open(os.path.join(LD, mo + '.json'), 'w', encoding='utf-8'), separators=(',', ':'))
    if fertig: os.remove(AN); print('Nachtrag fertig.')
    else: print('Nicht alles geschafft – nächste Nacht weiter.')


if __name__ == '__main__':
    main()
