#!/usr/bin/env python3
"""Einmalige Suche: Messstationen im Odenwaldkreis für die Lernkurve je Ort.
Weather Underground (private Stationen nahe jedem Ort) + DWD-Stationen (Bright Sky). Ergebnis -> data/stationen-kandidaten.json"""
import json, os, urllib.request, datetime as dt

KEY = '43a8f308d89b471ba8f308d89b671b69'
ORTE = [('Breuberg', 49.818, 9.040, 160), ('Höchst', 49.799, 8.994, 170), ('Michelstadt', 49.678, 9.004, 208),
        ('Mossautal', 49.667, 8.937, 380), ('Oberzent', 49.567, 8.976, 430), ('Bad König', 49.743, 9.006, 185)]


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de stationssuche'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode() or 'null')


def pruefe(sid):
    try:
        obs = (get('https://api.weather.com/v2/pws/observations/hourly/7day?stationId=%s&format=json&units=m&apiKey=%s' % (sid, KEY)) or {}).get('observations') or []
    except Exception as e:
        return {'fehler': str(e)[:80]}
    t = [o for o in obs if (o.get('metric') or {}).get('tempAvg') is not None]
    r = [o for o in obs if (o.get('metric') or {}).get('precipTotal') is not None]
    info = {'stunden': len(t), 'mit_regen': len(r)}
    if obs:
        o = obs[-1]; info.update(name=o.get('neighborhood'), lat=o.get('lat'), lon=o.get('lon'), letzte=o.get('obsTimeLocal'))
    try:
        c = get('https://api.weather.com/v2/pws/observations/current?stationId=%s&format=json&units=m&apiKey=%s' % (sid, KEY))
        info['hoehe'] = ((c or {}).get('observations') or [{}])[0].get('metric', {}).get('elev')
    except Exception:
        pass
    return info


out = {'erstellt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes'), 'orte': {}}
for name, la, lo, el in ORTE:
    e = {'wu': [], 'dwd': []}
    try:
        L = (get('https://api.weather.com/v3/location/near?geocode=%s,%s&product=pws&format=json&apiKey=%s' % (la, lo, KEY)) or {}).get('location') or {}
        for k, sid in enumerate((L.get('stationId') or [])[:8]):
            e['wu'].append(dict(id=sid, km=(L.get('distanceKm') or [None] * 9)[k], qc=(L.get('qcStatus') or [None] * 9)[k], **pruefe(sid)))
    except Exception as ex:
        e['wu_fehler'] = str(ex)[:120]
    try:
        S = (get('https://api.brightsky.dev/sources?lat=%s&lon=%s&max_dist=25000' % (la, lo)) or {}).get('sources') or []
        for s in S:
            if s.get('observation_type') in ('synop', 'current', 'historical'):
                e['dwd'].append({k: s.get(k) for k in ('id', 'dwd_station_id', 'station_name', 'observation_type', 'height', 'distance', 'last_record')})
    except Exception as ex:
        e['dwd_fehler'] = str(ex)[:120]
    out['orte'][name] = e
os.makedirs('data', exist_ok=True)
json.dump(out, open('data/stationen-kandidaten.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
