#!/usr/bin/env python3
"""Lernende Stationskorrektur für die Vorhersage (läuft stündlich).
Speichert Stunde für Stunde: Messwert IBADKN33 + DWD ICON-D2 (Temperatur, Bewölkung, Wind) -> data/lernen/JJJJ-MM.json
Berechnet daraus die Korrektur je Wetterlage und Tageszeit -> data/lernen-bias.json
und prüft die Treffsicherheit der korrigierten 12-Stunden-Vorhersage.
Präzision 2.0: zusätzlich Temperatur und Regen von ICON-D2, AROME, ECMWF und ICON-EU je Stunde speichern
und daraus die Trefferquote je Modell (Temperatur-Fehler, Regen ja/nein) berechnen -> lernen-bias.json „modelle“.
Die Website gewichtet die Modelle danach."""
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
MODELLE = ('icon_d2', 'meteofrance_arome_france_hd', 'ecmwf_ifs025', 'icon_eu')
GUETE_TAGE = 14            # Trefferquote der Modelle über die letzten 14 Tage
NASS = 0.1                 # mm pro Stunde: ab hier zählt eine Stunde als nass


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

    st = get('https://api.weather.com/v2/pws/observations/hourly/7day?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s'
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

    # Regen der Station je Stunde (precipTotal ist die Tagessumme -> Differenz zur Vorstunde)
    letzt = {}
    for o in sorted(st, key=lambda o: o['epoch']):
        m = o.get('metric') or {}
        tot = m.get('precipTotal')
        if tot is None: continue
        t = dt.datetime.fromtimestamp(o['epoch'], TZ); k = stundenkey(t); tag = k[:10]
        vor = letzt.get(tag, 0.0)
        if k in rows and 'st' in rows[k]: rows[k]['sr'] = round(max(0.0, tot - vor), 2)
        letzt[tag] = tot

    # Mehrere Modelle je Stunde merken (für die Gewichtung nach Trefferquote)
    try:
        mm = get('https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&models=%s'
                 '&hourly=temperature_2m,precipitation&past_days=7&forecast_days=1&timezone=Europe%%2FBerlin'
                 % (LAT, LON, ','.join(MODELLE)))['hourly']
        for i, t in enumerate(mm['time']):
            r = rows.get(t[:13])
            if not r or 'st' not in r: continue
            mt, mp = {}, {}
            for m in MODELLE:
                a = mm.get('temperature_2m_' + m) or []; b = mm.get('precipitation_' + m) or []
                if i < len(a) and a[i] is not None: mt[m] = round(a[i], 1)
                if i < len(b) and b[i] is not None: mp[m] = round(b[i], 2)
            if mt: r['mt'] = mt
            if mp: r['mp'] = mp
    except Exception as e:
        print('Mehrmodell-Daten nicht abrufbar:', e)

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

    # Trefferquote je Modell: mittlerer Temperaturfehler (nach Abzug der eigenen Tageszeit-Abweichung) und Regen-Treffer
    seit_g = (jetzt - dt.timedelta(days=GUETE_TAGE)).strftime('%Y-%m-%dT%H')
    modelle = {}
    for m in MODELLE:
        bl = [[] for _ in range(6)]
        for k, r in rows.items():
            if k >= seit_g and 'st' in r and m in (r.get('mt') or {}):
                bl[int(k[11:13]) // 4].append(r['st'] - r['mt'][m])
        korr = [sorted(x)[len(x) // 2] if len(x) >= 4 else 0.0 for x in bl]
        fe, n, tr, fa, fl = 0.0, 0, 0, 0, 0
        for k, r in rows.items():
            if k < seit_g or 'st' not in r: continue
            if m in (r.get('mt') or {}):
                fe += abs(r['st'] - (r['mt'][m] + korr[int(k[11:13]) // 4])); n += 1
            if 'sr' in r and m in (r.get('mp') or {}):
                sn, mn = r['sr'] >= NASS, r['mp'][m] >= NASS
                if sn and mn: tr += 1
                elif sn: fa += 1
                elif mn: fl += 1
        nr = tr + fa + fl
        modelle[m] = {'n': n, 'mae': round(fe / n, 2) if n else None,
                      'nr': nr, 'rtreff': round(tr / nr, 2) if nr else None}
    out = {'erstellt': jetzt.isoformat(timespec='minutes'), 'tage': tage, 'bias': bias, 'anzahl': anzahl,
           'modelle': modelle,
           'treff': {'n': n, 'mae': round(fk / n, 2) if n else None, 'mae_roh': round(fr / n, 2) if n else None}}
    json.dump(out, open(os.path.join(DATA, 'lernen-bias.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
