#!/usr/bin/env python3
"""Daten für das Wetter-Widget (w.html): alle 10 Minuten EIN Abruf bei Weather Underground,
damit Widgets auf fremden Seiten nicht gegen das WU-Limit zählen und der API-Schlüssel verborgen bleibt.
Ausgabe: data/widget.json"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from fb_post import get, LAT, LON, STATION, WU_KEY, TZ

OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'widget.json')


LIVE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'live.json')
H_KEYS = ('obsTimeLocal', 'epoch', 'humidityHigh', 'humidityLow', 'humidityAvg', 'winddirAvg', 'uvHigh', 'solarRadiationHigh')


def live_speichern(cur):
    """Live-Werte + heutiger Tagesverlauf für die Website (data/live.json) – Besucher müssen dann nicht selbst bei WU abrufen."""
    try:
        h = get('https://api.weather.com/v2/pws/observations/all/1day?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s'
                % (STATION, WU_KEY)).get('observations') or []
        hist = [dict({k: x[k] for k in H_KEYS if x.get(k) is not None}, metric=x.get('metric') or {}) for x in h]
        json.dump({'cur': cur, 'hist': {'observations': hist}, 'erstellt': dt.datetime.now(TZ).isoformat(timespec='seconds')},
                  open(LIVE, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    except Exception as e:
        print('Live-Datei nicht geschrieben:', e)


def main():
    now = dt.datetime.now(TZ)
    d = {'stand': None, 'live': None, 'tage': [], 'warn': []}
    try:
        cur = get('https://api.weather.com/v2/pws/observations/current?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s'
                  % (STATION, WU_KEY))
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
    try:
        om = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=icon_seamless&current=weather_code,is_day'
                 '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&forecast_days=3&timezone=Europe%%2FBerlin' % (LAT, LON))
        d['code'], d['tag'] = om['current']['weather_code'], om['current']['is_day']
        D = om['daily']
        d['tage'] = [dict(datum=D['time'][i], code=D['weather_code'][i], max=round(D['temperature_2m_max'][i]),
                          min=round(D['temperature_2m_min'][i]), rp=D['precipitation_probability_max'][i] or 0) for i in range(len(D['time']))]
    except Exception as e:
        print('Vorhersage nicht erreichbar:', e)
    try:
        for a in get('https://api.brightsky.dev/alerts?lat=%s&lon=%s' % (LAT, LON)).get('alerts') or []:
            if a.get('event_de'): d['warn'].append(dict(text=a['event_de'], stufe=a.get('severity')))
    except Exception as e:
        print('Warnungen nicht abrufbar:', e)
    if d['live'] is None and not d['tage']:
        print('Keine Daten – alte Datei bleibt.'); return
    if d['live'] is None:  # alte Live-Werte behalten statt leeren
        try:
            alt = json.load(open(OUT, encoding='utf-8')); d['live'], d['stand'] = alt.get('live'), alt.get('stand')
        except Exception:
            pass
    d['erstellt'] = now.isoformat(timespec='minutes')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(d, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps(d, ensure_ascii=False))


if __name__ == '__main__':
    main()
