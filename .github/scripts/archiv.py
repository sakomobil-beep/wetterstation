#!/usr/bin/env python3
"""Eigenes Wetterarchiv der Station IBADKN33 (fortlaufend).
- data/archiv/tage-JJJJ.json        : ein Eintrag pro Tag (Tageszusammenfassung von Weather Underground)
- data/archiv/stunden-JJJJ-MM.json  : Stundenwerte je Monat (für Grafiken)
Erster Lauf holt alles seit Messbeginn (20.01.2026, davor 01.–19.01. von IBADKN32 als Fremddaten),
danach ergänzt jeder Lauf alle fehlenden abgeschlossenen Tage (normalerweise nur gestern).
Luftdruck vor dem 05.11.2026 9:05 Uhr wird wie auf der Website um +5,4 hPa korrigiert."""
import json, os, sys, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

STATION, FREMD, KEY = 'IBADKN33', 'IBADKN32', '43a8f308d89b471ba8f308d89b671b69'
START, FREMD_AB = dt.date(2026, 1, 20), dt.date(2026, 1, 1)
TZ = ZoneInfo('Europe/Berlin')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DIR = os.path.join(ROOT, 'data', 'archiv')
CUT_EP, OFF, TAG = dt.datetime(2026, 11, 5, 8, 5, tzinfo=dt.timezone.utc).timestamp(), 5.4, '2026-11-05'
M_KEYS = ('tempHigh', 'tempLow', 'tempAvg', 'dewptHigh', 'dewptLow', 'dewptAvg', 'windspeedHigh', 'windspeedAvg', 'windgustHigh', 'windgustAvg',
          'pressureMax', 'pressureMin', 'pressureTrend', 'precipRate', 'precipTotal', 'heatindexHigh', 'windchillLow')
T_KEYS = ('humidityHigh', 'humidityLow', 'humidityAvg', 'winddirAvg', 'solarRadiationHigh', 'uvHigh')
anz = 0


def get(path, **q):
    global anz
    q.update(stationId=q.pop('station', STATION), format='json', units='m', numericPrecision='decimal', apiKey=KEY)
    url = 'https://api.weather.com' + path + '?' + '&'.join('%s=%s' % kv for kv in q.items())
    for v in range(4):
        try:
            anz += 1
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de archiv'}), timeout=40) as r:
                b = r.read().decode()
                return json.loads(b) if b.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code == 204: return {}
            if e.code == 429: time.sleep(65); continue
            if v == 3: raise
        except Exception:
            if v == 3: raise
        time.sleep(5)
    return {}


def schlank(o, stunde):
    m = o.get('metric') or {}
    x = {'obsTimeLocal': o.get('obsTimeLocal'), 'epoch': o.get('epoch'), 'metric': {k: m[k] for k in M_KEYS if m.get(k) is not None}}
    x.update({k: o[k] for k in T_KEYS if o.get(k) is not None})
    mm = x['metric']
    if o.get('stationID', STATION) == STATION:
        if stunde:
            if (o.get('epoch') or 0) < CUT_EP:
                for k in ('pressureMax', 'pressureMin'):
                    if k in mm: mm[k] = round(mm[k] + OFF, 2)
        else:
            tag = str(o.get('obsTimeLocal'))[:10]
            if tag < TAG:
                for k in ('pressureMax', 'pressureMin'):
                    if k in mm: mm[k] = round(mm[k] + OFF, 2)
            elif tag == TAG and mm.get('pressureMax', 0) - mm.get('pressureMin', 0) > 3:
                mm['pressureMin'] = round(mm['pressureMin'] + OFF, 2)
    return x


def lade(p, leer):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return leer


def speichern(p, d):
    os.makedirs(DIR, exist_ok=True)
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


def tage_ergaenzen(bis):
    """Tageswerte: fehlende Tage monatsweise nachholen."""
    jahre = {}
    d = FREMD_AB
    while d <= bis:
        p = os.path.join(DIR, 'tage-%d.json' % d.year)
        if d.year not in jahre: jahre[d.year] = lade(p, {'station': STATION, 'tage': []})
        A = jahre[d.year]; da = {t['obsTimeLocal'][:10] for t in A['tage']}
        if d.isoformat() in da: d += dt.timedelta(days=1); continue
        st = FREMD if d < START else STATION
        ende = min((d.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1), bis)
        if st == FREMD: ende = min(ende, START - dt.timedelta(days=1))
        j = get('/v2/pws/history/daily', station=st, startDate=d.strftime('%Y%m%d'), endDate=ende.strftime('%Y%m%d'))
        for o in (j.get('observations') or j.get('summaries') or []):
            t = str(o.get('obsTimeLocal'))[:10]
            if t in da or not (d.isoformat() <= t <= ende.isoformat()): continue
            x = schlank(o, False)
            if st == FREMD: x['quelle'] = FREMD
            A['tage'].append(x); da.add(t)
        A['tage'].sort(key=lambda t: t['obsTimeLocal'])
        d = ende + dt.timedelta(days=1)
        time.sleep(1.2)
    for y, A in jahre.items():
        A['stand'] = dt.datetime.now(TZ).isoformat(timespec='minutes')
        speichern(os.path.join(DIR, 'tage-%d.json' % y), A)
        print('Tage %d: %d Einträge' % (y, len(A['tage'])))


def stunden_ergaenzen(bis, max_tage):
    """Stundenwerte: fehlende Tage einzeln holen (höchstens max_tage pro Lauf)."""
    mon, n = {}, 0
    d = START
    while d <= bis and n < max_tage:
        k = d.strftime('%Y-%m'); p = os.path.join(DIR, 'stunden-%s.json' % k)
        if k not in mon: mon[k] = lade(p, {'station': STATION, 'tage': {}})
        if d.isoformat() not in mon[k]['tage']:
            j = get('/v2/pws/history/hourly', date=d.strftime('%Y%m%d'))
            obs = [schlank(o, True) for o in (j.get('observations') or [])]
            if len(obs) >= 18 or d < bis - dt.timedelta(days=3): mon[k]['tage'][d.isoformat()] = obs
            n += 1; time.sleep(2.2)
        d += dt.timedelta(days=1)
    for k, A in mon.items():
        A['tage'] = dict(sorted(A['tage'].items())); A['stand'] = dt.datetime.now(TZ).isoformat(timespec='minutes')
        speichern(os.path.join(DIR, 'stunden-%s.json' % k), A)
    print('Stundenwerte: %d Tage neu geholt' % n)


def index():
    """Übersicht für Website und Zentrale (welche Dateien gibt es)."""
    f = sorted(x for x in os.listdir(DIR) if x.endswith('.json') and x != 'index.json')
    letzter = None
    for x in f:
        if x.startswith('tage-'):
            t = lade(os.path.join(DIR, x), {}).get('tage') or []
            if t: letzter = max(letzter or '', t[-1]['obsTimeLocal'][:10])
    speichern(os.path.join(DIR, 'index.json'), {'station': STATION, 'messbeginn': START.isoformat(), 'letzter_tag': letzter,
                                                 'stand': dt.datetime.now(TZ).isoformat(timespec='minutes'), 'dateien': f})


if __name__ == '__main__':
    gestern = dt.datetime.now(TZ).date() - dt.timedelta(days=1)
    tage_ergaenzen(gestern)
    stunden_ergaenzen(gestern, int(sys.argv[1]) if len(sys.argv) > 1 else 400)
    index()
    print('Abrufe bei Weather Underground:', anz)
