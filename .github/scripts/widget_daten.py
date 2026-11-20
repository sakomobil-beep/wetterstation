#!/usr/bin/env python3
"""Live-Werte der eigenen Station für die Website (data/live.json) und Daten für das Wetter-Widget (w.html, data/widget.json) – alle 10 Minuten.
(Widget am 18.11.2026 entfernt, am 20.11.2026 wiederhergestellt.)"""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from fb_post import station_direkt, get, LAT, LON, STATION, WU_KEY, TZ

OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'widget.json')


LIVE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'live.json')
H_KEYS = ('obsTimeLocal', 'epoch', 'humidityHigh', 'humidityLow', 'humidityAvg', 'winddirAvg', 'uvHigh', 'solarRadiationHigh')


def tag_archivieren(L, laufend=False):
    """19.11.2026: Abgeschlossenen Tag aus dem eigenen Tagesverlauf ins Archiv (data/archiv) schreiben, falls er dort fehlt –
    so bleibt das Archiv vollständig, auch wenn WU nachts nicht liefert. Das nächtliche WU-Archiv überspringt vorhandene Tage."""
    if not L: return
    tag = str(L[0].get('obsTimeLocal', ''))[:10]
    D = os.path.join(os.path.dirname(LIVE), 'archiv')
    def num(o, k, top=False): v = (o if top else (o.get('metric') or {})).get(k); return v if isinstance(v, (int, float)) else None
    def zus(G, stamp):
        f = lambda k, fn, top=False: (lambda v: round(fn(v), 2) if v else None)([x for x in (num(o, k, top) for o in G) if x is not None])
        av = lambda v: sum(v) / len(v)
        m = {'tempHigh': f('tempHigh', max), 'tempLow': f('tempLow', min), 'tempAvg': f('tempAvg', av), 'dewptAvg': f('dewptAvg', av), 'windspeedHigh': f('windspeedHigh', max) or f('windspeedAvg', max),
             'windspeedAvg': f('windspeedAvg', av), 'windgustHigh': f('windgustHigh', max), 'pressureMax': f('pressureMax', max), 'pressureMin': f('pressureMin', min),
             'precipRate': f('precipRate', max), 'precipTotal': f('precipTotal', max)}
        x = {'obsTimeLocal': stamp, 'epoch': G[-1].get('epoch'), 'metric': {k: v for k, v in m.items() if v is not None}, 'quelle_eigen': True}
        for k, fn in (('humidityHigh', max), ('humidityLow', min), ('humidityAvg', av), ('solarRadiationHigh', max), ('uvHigh', max)):
            v = f(k, fn, True)
            if v is not None: x[k] = v
        if G[-1].get('winddirAvg') is not None: x['winddirAvg'] = G[-1]['winddirAvg']
        return x
    try:
        ps = os.path.join(D, 'stunden-%s.json' % tag[:7])
        try: S = json.load(open(ps, encoding='utf-8'))
        except Exception: S = {'station': STATION, 'tage': {}}
        if tag not in S['tage'] or (laufend and all(o.get('quelle_eigen') for o in S['tage'][tag])):
            std = {}
            for o in L: std.setdefault(str(o.get('obsTimeLocal'))[11:13], []).append(o)
            S['tage'][tag] = [zus(G, str(G[-1].get('obsTimeLocal'))) for h, G in sorted(std.items())]
            S['tage'] = dict(sorted(S['tage'].items())); json.dump(S, open(ps, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            if not laufend: print('Archiv: Stundenwerte %s aus eigenen Daten (%d Stunden)' % (tag, len(S['tage'][tag])))
        pt = os.path.join(D, 'tage-%s.json' % tag[:4])
        try: T = json.load(open(pt, encoding='utf-8'))
        except Exception: T = {'station': STATION, 'tage': []}
        alt_t = [t for t in T['tage'] if str(t.get('obsTimeLocal'))[:10] == tag]
        if laufend and alt_t and all(t.get('quelle_eigen') for t in alt_t): T['tage'] = [t for t in T['tage'] if t not in alt_t]; alt_t = []
        if not alt_t:
            T['tage'].append(zus(L, tag + ' 23:59:59')); T['tage'].sort(key=lambda t: t['obsTimeLocal'])
            json.dump(T, open(pt, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            print('Archiv: Tageswerte %s aus eigenen Daten' % tag)
    except Exception as e: print('Tag nicht archiviert:', e)


def live_speichern(cur):
    """Live-Werte + heutiger Tagesverlauf für die Website (data/live.json) – Besucher müssen dann nicht selbst bei WU abrufen."""
    try:
        if cur['observations'][0].get('quelle') == 'station': raise RuntimeError('Direktwerte – Tagesverlauf wird selbst geführt, kein WU-Abruf')   # 19.11.2026
        h = get('https://api.weather.com/v2/pws/observations/all/1day?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s'
                % (STATION, WU_KEY)).get('observations') or []
        hist = [dict({k: x[k] for k in H_KEYS if x.get(k) is not None}, metric=x.get('metric') or {}) for x in h]
    except Exception as e:   # WU nicht erreichbar: bisherigen Tagesverlauf behalten und den aktuellen Wert anhängen (18.11.2026)
        print('Tagesverlauf aus eigenen Werten:', e)
        try:
            alt = json.load(open(LIVE, encoding='utf-8'))['hist']['observations']
            o = cur['observations'][0]; heute = dt.datetime.now(TZ).date().isoformat()
            vortag = [x for x in alt if str(x.get('obsTimeLocal', ''))[:10] < heute]
            if vortag: tag_archivieren([x for x in vortag if str(x.get('obsTimeLocal', ''))[:10] == str(vortag[-1].get('obsTimeLocal', ''))[:10]])
            hist = [x for x in alt if str(x.get('obsTimeLocal', ''))[:10] == heute]
            if not hist or hist[-1].get('epoch') != o['epoch']:
                m = o.get('metric') or {}
                hist.append({'obsTimeLocal': o.get('obsTimeLocal'), 'epoch': o['epoch'], 'humidityAvg': o.get('humidity'), 'humidityHigh': o.get('humidity'), 'humidityLow': o.get('humidity'),
                             'winddirAvg': o.get('winddir'), 'uvHigh': o.get('uv'), 'solarRadiationHigh': o.get('solarRadiation'),
                             'metric': {'tempAvg': m.get('temp'), 'tempHigh': m.get('temp'), 'tempLow': m.get('temp'), 'dewptAvg': m.get('dewpt'), 'windspeedAvg': m.get('windSpeed'),
                                        'windgustHigh': m.get('windGust'), 'pressureMax': m.get('pressure'), 'pressureMin': m.get('pressure'), 'precipRate': m.get('precipRate'), 'precipTotal': m.get('precipTotal')}})
        except Exception as e2: print('Kein alter Tagesverlauf:', e2); return
    if cur['observations'][0].get('quelle') == 'station':   # 19.11.2026: Live-Daten laufend in die eigene Datenbank (heutiger Tag, alle 10 Min. erneuert)
        tag_archivieren([x for x in hist if str(x.get('obsTimeLocal', ''))[:10] == dt.datetime.now(TZ).date().isoformat()], laufend=True)
    try:
        json.dump({'cur': cur, 'hist': {'observations': hist}, 'erstellt': dt.datetime.now(TZ).isoformat(timespec='seconds')},
                  open(LIVE, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    except Exception as e:
        print('Live-Datei nicht geschrieben:', e)


def station_wache():
    """19.11.2026: Push, wenn die Station seit über 15 Minuten nichts mehr direkt sendet (Strom/WLAN weg), und wenn sie wieder da ist."""
    import urllib.request, time
    p = os.path.join(os.path.dirname(LIVE), 'station-status.json')
    try: S = json.load(open(p, encoding='utf-8'))
    except Exception: S = {'aus': False}
    alter = None
    try:
        # Hauptadresse statt /roh: /roh liegt nur im Speicher des Rechenzentrums, das die Station anfunkt – GitHub läuft woanders (Fehlalarm 19.11.2026 0:37)
        with urllib.request.urlopen(urllib.request.Request('https://wetter-badkoenig.sakomobil.workers.dev/', headers={'User-Agent': 'wetter-badkoenig.de'}), timeout=15) as r:
            o = json.loads(r.read().decode())['observations'][0]
        if o.get('quelle') == 'station': alter = time.time() - o['epoch']
    except Exception as e: print('Station-Wache: Empfänger nicht erreichbar:', e); return
    aus = alter is None or alter > 15 * 60
    topic = os.environ.get('NTFY_TOPIC')
    def push(titel, txt, tags):
        if not topic: return
        try: urllib.request.urlopen(urllib.request.Request('https://ntfy.sh/' + topic, data=txt.encode('utf-8'), headers={'Title': titel.encode('utf-8').decode('latin-1'), 'Tags': tags, 'Priority': 'high' if tags == 'warning' else 'default'}), timeout=20).read()
        except Exception as e: print('Push fehlgeschlagen:', e)
    if aus and not S.get('aus'):
        push('Station sendet nicht', 'Deine Wetterstation hat seit %s keine Werte mehr geschickt. Strom oder WLAN prüfen. Die Website nutzt solange Weather Underground als Reserve.'
             % ('%d Minuten' % (alter // 60) if alter else 'einiger Zeit'), 'warning')
        S = {'aus': True, 'seit': dt.datetime.now(TZ).isoformat(timespec='minutes')}
    elif not aus and S.get('aus'):
        push('Station wieder da', 'Deine Wetterstation sendet wieder (ausgefallen seit %s Uhr).' % str(S.get('seit', ''))[11:16], 'white_check_mark')
        S = {'aus': False}
    else: return
    json.dump(S, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    print('Station-Wache:', S)


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
    try:   # 20.11.2026: Zusatzangaben (Trend, Höchst/Tiefst, Verlauf, Regen-Hinweis, Frost, Max-Satz, Warnungen, Sonne)
        import widget_extra
        try: alt = json.load(open(OUT, encoding='utf-8'))
        except Exception: alt = None
        widget_extra.ergaenzen(d, now, LAT, LON, alt)
    except Exception as e:
        print('Widget-Zusatzangaben nicht möglich:', e)
    d['erstellt'] = now.isoformat(timespec='minutes')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(d, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps(d, ensure_ascii=False))

if __name__ == '__main__':
    main()
    station_wache()
