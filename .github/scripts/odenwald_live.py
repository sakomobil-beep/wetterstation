#!/usr/bin/env python3
"""Live-Werte der 6 Kartenorte im Odenwaldkreis für die Seite „Aktuell Odenwald“ (15.11.2026).
Läuft im 10-Minuten-Lauf (widget.yml) und schreibt data/odenwald-live.json:
stand, orte[name, el, lat, lon, quelle, t, rh, w, g, r (Regen heute), p, zeit], verlauf{name: [[HH:MM, t], ...]} für heute."""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from fb_post import get, WU_KEY, TZ

ORTE = [('Breuberg', 160, 'wu', 'IBREUB3', 49.818, 9.040), ('Höchst i. Odw.', 170, 'wu', 'IHCHST74', 49.799, 8.994),
        ('Bad König', 185, 'wu', 'IBADKN33', 49.743, 9.006), ('Michelstadt', 228, 'wu', 'IMICHELS20', 49.678, 9.004),
        ('Mossautal', 315, 'wu', 'IMOSSA13', 49.667, 8.937), ('Oberzent', 461, 'wu', 'IBEERFEL4', 49.567, 8.976)]
# 15.11.2026: Michelstadt (vorher DWD 03284, ohne Wind), Mossautal (vorher DWD 03287 = in Wahrheit Michelstadt-Vielbrunn!)
# und Oberzent (vorher DWD 00330, ohne Wind) auf private WU-Stationen umgestellt. dwd() bleibt als Reserve.
DATEI = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'odenwald-live.json')
r1 = lambda v: None if v is None else round(float(v), 1)


def wu(sid):
    o = (get('https://api.weather.com/v2/pws/observations/current?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s' % (sid, WU_KEY)).get('observations') or [None])[0]
    if not o: return None
    m = o.get('metric') or {}
    return dict(t=r1(m.get('temp')), rh=o.get('humidity'), w=r1(m.get('windSpeed')), g=r1(m.get('windGust')), r=r1(m.get('precipTotal')),
                p=r1(m.get('pressure')), zeit=dt.datetime.fromtimestamp(o['epoch'], TZ).isoformat(timespec='minutes'))


def dwd(sid, heute):
    w = get('https://api.brightsky.dev/current_weather?dwd_station_id=%s&tz=Europe/Berlin' % sid).get('weather') or {}
    if w.get('temperature') is None: return None
    r = None
    try:   # Regen heute: Stundenwerte seit Mitternacht
        h = get('https://api.brightsky.dev/weather?dwd_station_id=%s&date=%s&tz=Europe/Berlin' % (sid, heute)).get('weather') or []
        bis = dt.datetime.now(TZ).isoformat()
        r = round(sum((x.get('precipitation') or 0) for x in h if x.get('timestamp', '')[:10] == heute and x['timestamp'] <= bis), 1)
    except Exception as e: print('Regen heute %s:' % sid, e)
    return dict(t=r1(w.get('temperature')), rh=w.get('relative_humidity'), w=r1(w.get('wind_speed_10')), g=r1(w.get('wind_gust_speed_10')),
                r=r, p=r1(w.get('pressure_msl')), zeit=dt.datetime.fromisoformat(w['timestamp']).astimezone(TZ).isoformat(timespec='minutes'))


def archiv(orte, jetzt):
    """Messwert-Datenbank: jeder 10-Minuten-Wert jeder Station dauerhaft in data/odenwald-archiv/JJJJ-MM.json
    (Format: {station: {zeit: [t, rh, w, g, r]}}), damit nichts verloren geht."""
    d = os.path.join(os.path.dirname(DATEI), 'odenwald-archiv'); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, jetzt.strftime('%Y-%m') + '.json')
    try: A = json.load(open(f, encoding='utf-8'))
    except Exception: A = {}
    for o in orte:
        z = o.get('zeit')
        if not z or z[:7] != jetzt.strftime('%Y-%m') or o.get('t') is None: continue
        A.setdefault(o['name'], {})[z[:16]] = [o.get('t'), o.get('rh'), o.get('w'), o.get('g'), o.get('r')]
    json.dump(A, open(f, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


def main():
    jetzt = dt.datetime.now(TZ); heute = jetzt.date().isoformat()
    try: alt = json.load(open(DATEI, encoding='utf-8'))
    except Exception: alt = {}
    verlauf = alt.get('verlauf') if alt.get('datum') == heute else {}
    verlauf = verlauf or {}
    orte = []
    for n, el, art, sid, la, lo in ORTE:
        try: v = wu(sid) if art == 'wu' else dwd(sid, heute)
        except Exception as e: print('Station %s nicht abrufbar:' % n, e); v = None
        alt_o = next((o for o in alt.get('orte', []) if o['name'] == n), None) if alt.get('datum') == heute else None
        if not v and alt_o: v = {k: alt_o.get(k) for k in ('t', 'rh', 'w', 'g', 'r', 'p', 'zeit')}
        o = dict(name=n, el=el, lat=la, lon=lo, quelle='eigene Station' if sid == 'IBADKN33' else 'privat (WU)' if art == 'wu' else 'DWD', **(v or {}))
        orte.append(o)
        if v and v.get('t') is not None and (v.get('zeit') or '')[:10] == heute:
            L = verlauf.setdefault(n, []); hm = v['zeit'][11:16]
            if not L or L[-1][0] != hm: L.append([hm, v['t']])
    archiv(orte, jetzt)
    json.dump(dict(stand=jetzt.isoformat(timespec='minutes'), datum=heute, orte=orte, verlauf=verlauf),
              open(DATEI, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('Odenwald live:', [(o['name'], o.get('t')) for o in orte])


if __name__ == '__main__':
    main()
