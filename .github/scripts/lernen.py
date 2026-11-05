#!/usr/bin/env python3
"""Lernende Stationskorrektur für die Vorhersage (läuft stündlich).
Speichert Stunde für Stunde: Messwert IBADKN33 + DWD ICON-D2 (Temperatur, Bewölkung, Wind) -> data/lernen/JJJJ-MM.json
Berechnet daraus die Korrektur je Wetterlage und Tageszeit -> data/lernen-bias.json
und prüft die Treffsicherheit der korrigierten 12-Stunden-Vorhersage."""
import json, os, math, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

LAT, LON = 49.750, 9.017
STATION, WU_KEY = 'IBADKN33', '43a8f308d89b471ba8f308d89b671b69'
TZ = ZoneInfo('Europe/Berlin')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(ROOT, 'data')
TAGE_HALTEN = 365
HALBWERT = 21.0            # Tage: jüngere Daten zählen mehr
LAGEN = ('klar', 'wolkig', 'windig')
GRENZE = {'tag': 4.0, 'nacht': 7.0}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de lernen'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def lage(cc, wind):
    """Wetterlage einer Stunde: windig (>= 15 km/h), klar & ruhig (< 35 % Wolken), sonst wolkig."""
    if wind is not None and wind >= 15: return 'windig'
    if cc is not None and cc < 35: return 'klar'
    return 'wolkig'


def block(h):  # 6 Blöcke à 4 Stunden
    return h // 4


def ist_nacht(b):
    return b in (0, 1, 5)


def stundenkey(d):
    return d.astimezone(TZ).strftime('%Y-%m-%dT%H')


def main():
    os.makedirs(DATA, exist_ok=True)
    LD = os.path.join(DATA, 'lernen'); os.makedirs(LD, exist_ok=True)
    rows = {}
    for f in sorted(os.listdir(LD)):   # eine Datei je Monat, damit jede Speicherung klein bleibt
        if f.endswith('.json'):
            try: rows.update(json.load(open(os.path.join(LD, f), encoding='utf-8')))
            except Exception: pass

    om = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=icon_d2'
             '&hourly=temperature_2m,cloud_cover,wind_speed_10m&past_days=7&forecast_days=2&timezone=Europe%%2FBerlin' % (LAT, LON))
    Hh = om['hourly']
    modell = {}
    for i, t in enumerate(Hh['time']):
        modell[t[:13]] = (Hh['temperature_2m'][i], Hh['cloud_cover'][i], Hh['wind_speed_10m'][i])

    st = get('https://api.weather.com/v2/pws/observations/hourly/7day?stationId=%s&format=json&units=m&apiKey=%s'
             % (STATION, WU_KEY)).get('observations') or []
    jetzt = dt.datetime.now(TZ)
    for o in st:
        m = o.get('metric') or {}
        if m.get('tempAvg') is None: continue
        k = stundenkey(dt.datetime.fromtimestamp(o['epoch'], TZ))
        md = modell.get(k)
        if not md or md[0] is None: continue
        r = rows.get(k, {})
        r.update({'st': round(m['tempAvg'], 1), 'md': md[0], 'cc': md[1], 'wm': md[2], 'ws': m.get('windspeedAvg')})
        rows[k] = r

    # Treffsicherheit: korrigierte Vorhersage für in 12 h festhalten (einmal je Zielstunde)
    bias_alt = None
    try: bias_alt = json.load(open(os.path.join(DATA, 'lernen-bias.json'), encoding='utf-8'))
    except Exception: pass
    ziel = jetzt + dt.timedelta(hours=12)
    zk = stundenkey(ziel)
    md = modell.get(zk)
    if md and md[0] is not None:
        r = rows.setdefault(zk, {})
        if 'p12' not in r:
            kor = 0.0
            if bias_alt:
                kor = bias_alt['bias'][lage(md[1], md[2])][block(ziel.hour)]
            r['p12'] = round(md[0] + kor, 1); r['r12'] = md[0]

    grenze = (jetzt - dt.timedelta(days=TAGE_HALTEN)).strftime('%Y-%m-%dT%H')
    rows = {k: v for k, v in sorted(rows.items()) if k >= grenze}
    monate = {}
    for k, v in rows.items(): monate.setdefault(k[:7], {})[k] = v
    for f in os.listdir(LD):
        if f.endswith('.json') and f[:7] not in monate: os.remove(os.path.join(LD, f))
    for m, inhalt in monate.items():
        ziel_f = os.path.join(LD, m + '.json'); neu = json.dumps(inhalt, separators=(',', ':'))
        try: alt = open(ziel_f, encoding='utf-8').read()
        except Exception: alt = ''
        if alt != neu: open(ziel_f, 'w', encoding='utf-8').write(neu)

    # Korrektur lernen: gewichteter Mittelwert (Halbwertszeit 21 Tage), robust durch Kappen von Ausreißern
    summe = {l: [[0.0, 0.0] for _ in range(6)] for l in LAGEN}
    alle = [[0.0, 0.0] for _ in range(6)]
    anzahl = {l: [0] * 6 for l in LAGEN}
    for k, r in rows.items():
        if 'st' not in r or r.get('md') is None: continue
        t = dt.datetime.strptime(k, '%Y-%m-%dT%H').replace(tzinfo=TZ)
        if t > jetzt: continue
        alter = (jetzt - t).total_seconds() / 86400
        w = 0.5 ** (alter / HALBWERT)
        d = max(-10, min(10, r['st'] - r['md']))
        b = block(t.hour); l = lage(r.get('cc'), r.get('wm'))
        summe[l][b][0] += w * d; summe[l][b][1] += w; anzahl[l][b] += 1
        alle[b][0] += w * d; alle[b][1] += w
    bias = {}
    for l in LAGEN:
        bias[l] = []
        for b in range(6):
            g = GRENZE['nacht' if ist_nacht(b) else 'tag']
            allg = alle[b][0] / alle[b][1] if alle[b][1] else 0.0
            s, wsum = summe[l][b]
            # wenig Daten für diese Lage -> zum allgemeinen Wert hin ziehen
            v = (s + 3.0 * allg) / (wsum + 3.0) if wsum else allg
            bias[l].append(round(max(-g, min(g, v)), 2))

    # Treffsicherheit der letzten 7 Tage (korrigiert vs. reines Modell)
    seit = (jetzt - dt.timedelta(days=7)).strftime('%Y-%m-%dT%H')
    fk, fr, n = 0.0, 0.0, 0
    for k, r in rows.items():
        if k >= seit and 'p12' in r and 'st' in r:
            fk += abs(r['st'] - r['p12']); fr += abs(r['st'] - r['r12']); n += 1
    tage = len({k[:10] for k, r in rows.items() if 'st' in r})
    out = {'erstellt': jetzt.isoformat(timespec='minutes'), 'tage': tage, 'bias': bias, 'anzahl': anzahl,
           'treff': {'n': n, 'mae': round(fk / n, 2) if n else None, 'mae_roh': round(fr / n, 2) if n else None}}
    json.dump(out, open(os.path.join(DATA, 'lernen-bias.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
