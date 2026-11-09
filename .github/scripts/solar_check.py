#!/usr/bin/env python3
"""Solarwetter-Check: prüft alle Datenquellen der Solarwetter-Seite (NOAA SWPC, NASA SDO, SOHO).
- Erreichbar (HTTP 200)? Inhalt nicht leer? Neuester Zeitstempel nicht zu alt?
- Bei Problemen ntfy-Push (Secret NTFY_TOPIC) – je Problem höchstens 1x pro Tag; Push „wieder OK“, wenn behoben.
- Ergebnis in fb/solar_check.json (für die Zentrale)."""
import gzip, json, os, re, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
B = 'https://services.swpc.noaa.gov/'
MERK = os.path.join(os.path.dirname(__file__), '..', '..', 'fb', 'solar_check.json')
# Name, URL, max. Alter in Stunden (None = nicht prüfen)
QUELLEN = [
    ('Sonnenwind (Plasma)', B + 'json/rtsw/rtsw_wind_1m.json', 2),
    ('Magnetfeld Bz', B + 'json/rtsw/rtsw_mag_1m.json', 2),
    ('Kp-Index', B + 'products/noaa-planetary-k-index.json', 8),
    ('Kp-Prognose', B + 'products/noaa-planetary-k-index-forecast.json', None),
    ('Kurzzeit-Kp', B + 'json/planetary_k_index_1m.json', 2),
    ('Flare-Wahrscheinlichkeiten', B + 'json/solar_probabilities.json', 36),
    ('Röntgenstrahlung GOES', B + 'json/goes/primary/xrays-1-day.json', 2),
    ('Protonen GOES', B + 'json/goes/primary/integral-protons-1-day.json', 2),
    ('Polarlicht OVATION', B + 'json/ovation_aurora_latest.json', 2),
    ('NOAA-Skalen', B + 'products/noaa-scales.json', None),
    ('NOAA-Meldungen', B + 'products/alerts.json', None),
    ('Sonnenzyklus', B + 'json/solar-cycle/observed-solar-cycle-indices.json', None),
    ('Polarlichtoval-Animation', B + 'products/animations/ovation_north_24h.json', 3),
    ('Sonnenbild SDO', 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_512_0193.jpg', None),
]
ZEIT = re.compile(r'"?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)')


def laden(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de Solarwetter-Check', 'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=40) as r:
        roh = r.read()
        if r.headers.get('Content-Encoding') == 'gzip': roh = gzip.decompress(roh)
        return r.status, roh


def neueste_zeit(text):
    zs = []
    for m in ZEIT.findall(text[-200000:] + text[:200000]):
        try: zs.append(dt.datetime.fromisoformat(m.replace(' ', 'T')).replace(tzinfo=dt.timezone.utc))
        except ValueError: pass
    jetzt = dt.datetime.now(dt.timezone.utc)
    zs = [z for z in zs if z <= jetzt + dt.timedelta(hours=1)]   # Prognosen in der Zukunft ignorieren
    return max(zs) if zs else None


def pruefe(name, url, max_h):
    try:
        st, roh = laden(url)
    except Exception as e:
        return 'nicht erreichbar (%s)' % str(e)[:80]
    if st != 200: return 'HTTP %s' % st
    if len(roh) < 50: return 'leere Antwort'
    if url.endswith('.jpg'): return None
    try: j = json.loads(roh)
    except Exception: return 'keine gültigen Daten'
    if not j: return 'leere Daten'
    if max_h:
        z = neueste_zeit(roh.decode('utf-8', 'ignore'))
        if not z: return 'kein Zeitstempel gefunden'
        alt = (dt.datetime.now(dt.timezone.utc) - z).total_seconds() / 3600
        if alt > max_h: return 'veraltet (letzter Wert vor %.0f Std.)' % alt
    return None


def push(titel, text, prio, tags):
    topic = os.environ.get('NTFY_TOPIC')
    if not topic: print('Kein NTFY_TOPIC'); return
    req = urllib.request.Request('https://ntfy.sh/' + topic, data=text.encode('utf-8'), headers={
        'Title': titel.encode('utf-8').decode('latin-1'), 'Priority': prio, 'Tags': tags,
        'Click': 'https://wetter-badkoenig.de/#solar'})
    urllib.request.urlopen(req, timeout=20).read(); print('Push:', titel)


def main():
    try: alt = json.load(open(MERK))
    except Exception: alt = {}
    jetzt = dt.datetime.now(TZ); heute = jetzt.date().isoformat()
    ergebnis = {}
    for name, url, max_h in QUELLEN:
        f = pruefe(name, url, max_h)
        ergebnis[name] = f or 'ok'
        print('%-28s %s' % (name, f or 'ok'))
    fehler = {k: v for k, v in ergebnis.items() if v != 'ok'}
    gemeldet = alt.get('gemeldet', {})
    neu = {k: v for k, v in fehler.items() if gemeldet.get(k) != heute}
    if neu:
        push('🛰️ Solarwetter: %d Quelle(n) mit Problem' % len(fehler),
             '\n'.join('• %s: %s' % kv for kv in fehler.items()), 'default', 'satellite,warning')
        for k in neu: gemeldet[k] = heute
    behoben = [k for k in alt.get('fehler', {}) if k not in fehler]
    if behoben:
        push('✅ Solarwetter wieder OK', 'Wieder in Ordnung: ' + ', '.join(behoben), 'low', 'satellite,white_check_mark')
    gemeldet = {k: v for k, v in gemeldet.items() if k in fehler}
    json.dump({'stand': jetzt.isoformat(timespec='minutes'), 'quellen': ergebnis, 'fehler': fehler, 'gemeldet': gemeldet},
              open(MERK, 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
