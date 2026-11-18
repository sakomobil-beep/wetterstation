#!/usr/bin/env python3
"""Eigene Daten statt Weather Underground für die eigene Station IBADKN33 (19.11.2026).
Aktuell → Cloudflare-Empfänger (Station sendet direkt), heute → data/live.json, früher → eigenes Archiv data/archiv (seit 20.01.2026).
ersatz(url) gibt eine Antwort im WU-Format zurück oder None – dann wird wie bisher bei WU abgerufen."""
import json, os, time, urllib.request, urllib.parse, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
DATA = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
DIREKT = 'https://wetter-badkoenig.sakomobil.workers.dev/'


def _lade(p):
    try: return json.load(open(os.path.join(DATA, p), encoding='utf-8'))
    except Exception: return None


def _heute():
    j = _lade('live.json') or {}
    L = (j.get('hist') or {}).get('observations') or []
    h = dt.datetime.now(TZ).date().isoformat()
    return [o for o in L if str(o.get('obsTimeLocal', ''))[:10] == h]


def _stunden(tag):
    j = _lade('archiv/stunden-%s.json' % tag[:7]) or {}
    return (j.get('tage') or {}).get(tag)


def _tage(von, bis):
    L = []
    for y in range(int(von[:4]), int(bis[:4]) + 1):
        L += [t for t in ((_lade('archiv/tage-%d.json' % y) or {}).get('tage') or []) if von <= str(t.get('obsTimeLocal'))[:10] <= bis and not t.get('quelle')]
    return L


def _summe(L, tag):
    def w(k, f):
        v = [(o.get('metric') or {}).get(k) for o in L]; v = [x for x in v if isinstance(x, (int, float))]
        return f(v) if v else None
    av = lambda v: sum(v) / len(v)
    h = [o.get('humidityAvg') for o in L if isinstance(o.get('humidityAvg'), (int, float))]
    return {'obsTimeLocal': tag + ' 23:59:59', 'epoch': L[-1].get('epoch') if L else 0, 'humidityHigh': max(h) if h else None, 'humidityLow': min(h) if h else None,
            'humidityAvg': av(h) if h else None,
            'metric': {'tempHigh': w('tempHigh', max), 'tempLow': w('tempLow', min), 'tempAvg': w('tempAvg', av), 'dewptAvg': w('dewptAvg', av), 'windgustHigh': w('windgustHigh', max),
                       'windspeedAvg': w('windspeedAvg', av), 'pressureMax': w('pressureMax', max), 'pressureMin': w('pressureMin', min), 'precipTotal': w('precipTotal', max)}}


def _tag(d): return '%s-%s-%s' % (d[:4], d[4:6], d[6:8])


def ersatz(url):
    try:
        u = urllib.parse.urlparse(url)
        if u.hostname != 'api.weather.com': return None
        q = dict(urllib.parse.parse_qsl(u.query))
        if q.get('stationId') != 'IBADKN33': return None
        p, heute = u.path, dt.datetime.now(TZ).date()
        gestern = (heute - dt.timedelta(days=1)).isoformat()
        if p == '/v2/pws/observations/current':
            with urllib.request.urlopen(urllib.request.Request(DIREKT, headers={'User-Agent': 'wetter-badkoenig.de'}), timeout=15) as r: j = json.loads(r.read().decode())
            o = j['observations'][0]
            return j if o.get('quelle') == 'station' and time.time() - o['epoch'] < 900 else None
        if p == '/v2/pws/observations/all/1day':
            L = _heute(); return {'observations': L} if L else None
        if p == '/v2/pws/observations/hourly/7day':
            L = []
            for i in range(6, 0, -1): L += _stunden((heute - dt.timedelta(days=i)).isoformat()) or []
            L += _heute()
            return {'observations': L} if len(L) >= 24 and _stunden(gestern) else None
        if p in ('/v2/pws/history/hourly', '/v2/pws/history/all') and q.get('date'):
            t = _tag(q['date']); L = _heute() if t == heute.isoformat() else _stunden(t)
            return {'observations': L} if L else None
        if p in ('/v2/pws/history/daily', '/v2/pws/dailysummary/7day'):
            if p == '/v2/pws/history/daily': von, bis = _tag(q.get('startDate') or q['date']), _tag(q.get('endDate') or q['date'])
            else: von, bis = (heute - dt.timedelta(days=6)).isoformat(), heute.isoformat()
            L = _tage(von, min(bis, gestern))
            if bis >= gestern and not any(str(t['obsTimeLocal'])[:10] == gestern for t in L) and von <= gestern: return None   # gestern noch nicht im Archiv
            if bis >= heute.isoformat():
                H = _heute()
                if H: L.append(_summe(H, heute.isoformat()))
            if not L: return None
            return {'summaries': L} if p.endswith('7day') else {'observations': L}
    except Exception as e:
        print('Eigene Daten nicht nutzbar (%s) – frage WU.' % e)
    return None
