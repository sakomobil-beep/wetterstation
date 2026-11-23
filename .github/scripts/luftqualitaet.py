#!/usr/bin/env python3
"""Luftqualität (22.11.2026): amtliche Messstation Michelstadt (HLNUG DEHE045, über die Schnittstelle des Umweltbundesamts)
und privater Feinstaubsensor in Bad König (Sensor.Community, SPS30 Nr. 92602 + BME280 Nr. 63787 für die Feuchte).
Schreibt data/luft.json. Läuft im 10-Minuten-Lauf, ruft aber höchstens alle 30 Minuten ab.
Index wie beim Umweltbundesamt: 0 sehr gut, 1 gut, 2 mäßig, 3 schlecht, 4 sehr schlecht.
Billige Feinstaubsensoren messen bei hoher Luftfeuchte (Nebel) deutlich zu viel – ab 80 % Feuchte gilt der Bad-König-Wert als unsicher."""
import json, os, sys, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
DATEI = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'luft.json')
UBA_STATION = '673'   # DEHE045 Michelstadt
KOMP = {1: 'pm10', 9: 'pm25', 5: 'no2', 3: 'o3', 4: 'so2'}
SC_FEINSTAUB, SC_KLIMA = 92602, 63787
INDEX_TEXT = ['sehr gut', 'gut', 'mäßig', 'schlecht', 'sehr schlecht']


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de (Kontakt über wetter-badkoenig.de/impressum.html)'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode())


def pm10_index(v):   # Grenzen des Umweltbundesamts (Stundenwert PM10)
    return None if v is None else 0 if v <= 20 else 1 if v <= 35 else 2 if v <= 50 else 3 if v <= 100 else 4


def pm25_index(v):
    return None if v is None else 0 if v <= 10 else 1 if v <= 20 else 2 if v <= 25 else 3 if v <= 50 else 4


def uba(jetzt):
    heute, gestern = jetzt.date().isoformat(), (jetzt.date() - dt.timedelta(days=1)).isoformat()
    d = get('https://luftdaten.umweltbundesamt.de/api/air-data/v3/airquality/json?date_from=%s&time_from=1&date_to=%s&time_to=24&station=%s&lang=de'
            % (gestern, heute, UBA_STATION)).get('data', {}).get(UBA_STATION, {})
    if not d: return None
    verlauf = []
    for start in sorted(d):
        z = d[start]; w = {KOMP[c[0]]: c[1] for c in z[3:] if isinstance(c, list) and c[0] in KOMP}
        verlauf.append(dict(zeit=z[0][:16].replace(' ', 'T'), index=z[1], unvollstaendig=bool(z[2]), **w))
    letzt = verlauf[-1]
    return dict(name='Michelstadt', quelle='Luftmessstation des Landes Hessen (HLNUG), über das Umweltbundesamt', amtlich=True,
                index_text=INDEX_TEXT[letzt['index']] if letzt.get('index') is not None and 0 <= letzt['index'] <= 4 else None,
                verlauf=[{k: v[k] for k in ('zeit', 'pm10', 'pm25') if k in v} for v in verlauf[-24:]], **letzt)


def sensor(sid):
    L = get('https://data.sensor.community/airrohr/v1/sensor/%d/' % sid)
    if not L: return None, None
    x = max(L, key=lambda r: r['timestamp'])
    return {v['value_type']: float(v['value']) for v in x['sensordatavalues'] if v['value'] not in (None, '')}, \
        dt.datetime.fromisoformat(x['timestamp']).replace(tzinfo=dt.timezone.utc).astimezone(TZ)


def badkoenig():
    w, z = sensor(SC_FEINSTAUB)
    if not w: return None
    k, _ = sensor(SC_KLIMA)
    rh = round(k['humidity']) if k and 'humidity' in k else None
    pm10, pm25 = round(w.get('P1'), 1) if 'P1' in w else None, round(w.get('P2'), 1) if 'P2' in w else None
    i = max([x for x in (pm10_index(pm10), pm25_index(pm25)) if x is not None], default=None)
    return dict(name='Bad König', quelle='privater Feinstaubsensor (Sensor.Community)', amtlich=False, zeit=z.isoformat(timespec='minutes'),
                pm10=pm10, pm25=pm25, rh=rh, unsicher=rh is not None and rh >= 80, index=i, index_text=INDEX_TEXT[i] if i is not None else None)


def main():
    jetzt = dt.datetime.now(TZ)
    try: alt = json.load(open(DATEI, encoding='utf-8'))
    except Exception: alt = {}
    if alt.get('stand') and (jetzt - dt.datetime.fromisoformat(alt['stand'])).total_seconds() < 28 * 60 and '--jetzt' not in sys.argv:
        print('Luftqualität: noch aktuell'); return
    out = dict(stand=jetzt.isoformat(timespec='minutes'))
    for k, f in (('michelstadt', lambda: uba(jetzt)), ('badkoenig', badkoenig)):
        try: out[k] = f()
        except Exception as e: print(k, 'nicht abrufbar:', e); out[k] = alt.get(k)
    json.dump(out, open(DATEI, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('Luftqualität:', json.dumps(out, ensure_ascii=False)[:400])


if __name__ == '__main__':
    main()
