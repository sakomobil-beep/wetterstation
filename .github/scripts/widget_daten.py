#!/usr/bin/env python3
"""Live-Werte der eigenen Station für die Website (data/live.json): alle 10 Minuten bei Weather Underground.
(Das Wetter-Widget w.html / data/widget.json wurde am 18.11.2026 entfernt.)"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from fb_post import station_direkt, get, LAT, LON, STATION, WU_KEY, TZ

OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'widget.json')


LIVE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'live.json')
H_KEYS = ('obsTimeLocal', 'epoch', 'humidityHigh', 'humidityLow', 'humidityAvg', 'winddirAvg', 'uvHigh', 'solarRadiationHigh')


def live_speichern(cur):
    """Live-Werte + heutiger Tagesverlauf für die Website (data/live.json) – Besucher müssen dann nicht selbst bei WU abrufen."""
    try:
        h = get('https://api.weather.com/v2/pws/observations/all/1day?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s'
                % (STATION, WU_KEY)).get('observations') or []
        hist = [dict({k: x[k] for k in H_KEYS if x.get(k) is not None}, metric=x.get('metric') or {}) for x in h]
    except Exception as e:   # WU nicht erreichbar: bisherigen Tagesverlauf behalten und den aktuellen Wert anhängen (18.11.2026)
        print('Tagesverlauf bei WU nicht abrufbar:', e)
        try:
            alt = json.load(open(LIVE, encoding='utf-8'))['hist']['observations']
            o = cur['observations'][0]; heute = dt.datetime.now(TZ).date().isoformat()
            hist = [x for x in alt if str(x.get('obsTimeLocal', ''))[:10] == heute]
            if not hist or hist[-1].get('epoch') != o['epoch']:
                m = o.get('metric') or {}
                hist.append({'obsTimeLocal': o.get('obsTimeLocal'), 'epoch': o['epoch'], 'humidityAvg': o.get('humidity'), 'humidityHigh': o.get('humidity'), 'humidityLow': o.get('humidity'),
                             'winddirAvg': o.get('winddir'), 'uvHigh': o.get('uv'), 'solarRadiationHigh': o.get('solarRadiation'),
                             'metric': {'tempAvg': m.get('temp'), 'tempHigh': m.get('temp'), 'tempLow': m.get('temp'), 'dewptAvg': m.get('dewpt'), 'windspeedAvg': m.get('windSpeed'),
                                        'windgustHigh': m.get('windGust'), 'pressureMax': m.get('pressure'), 'pressureMin': m.get('pressure'), 'precipRate': m.get('precipRate'), 'precipTotal': m.get('precipTotal')}})
        except Exception as e2: print('Kein alter Tagesverlauf:', e2); return
    try:
        json.dump({'cur': cur, 'hist': {'observations': hist}, 'erstellt': dt.datetime.now(TZ).isoformat(timespec='seconds')},
                  open(LIVE, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    except Exception as e:
        print('Live-Datei nicht geschrieben:', e)


def main():
    now = dt.datetime.now(TZ)
    d = {'stand': None, 'live': None, 'tage': [], 'warn': []}
    try:
        cur = station_direkt() or get('https://api.weather.com/v2/pws/observations/current?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s'
                  % (STATION, WU_KEY))   # 18.11.2026: zuerst direkt von der Station
        o = cur['observations'][0]
        live_speichern(cur)
        m = o.get('metric') or {}
        d['stand'] = dt.datetime.fromtimestamp(o['epoch'], TZ).isoformat(timespec='minutes')
        d['live'] = {k: m.get(s) for k, s in (('temp', 'temp'), ('gefuehlt', 'windChill'), ('wind', 'windSpeed'), ('boe', 'windGust'),
                                               ('regen', 'precipTotal'), ('druck', 'pressure'))}
        d['live'].update(feuchte=o.get('humidity'), richtung=o.get('winddir'), uv=o.get('uv'))
        if d['live']['temp'] is not None and d['live']['temp'] > 10: d['live']['gefuehlt'] = m.get('heatIndex')
    except Exception as e:
        print('WU nicht erreichbar:', e)
    # 18.11.2026: Wetter-Widget (w.html, data/widget.json) entfernt – der Lauf schreibt nur noch data/live.json für die Website
    print('Live-Datei aktualisiert:', d['stand'])

if __name__ == '__main__':
    main()
