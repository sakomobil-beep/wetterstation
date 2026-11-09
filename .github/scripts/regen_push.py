#!/usr/bin/env python3
"""Regen-Push: prüft den DWD-Radar-Nowcast (RADOLAN über Bright Sky, 2 h in 5-Minuten-Schritten)
für Bad König und schickt eine ntfy-Push-Nachricht, wenn Regen im Anmarsch ist.

- Push, wenn es gerade trocken ist und das Radar innerhalb der nächsten 60 Minuten Regen zeigt.
- Pro Regenereignis nur ein Push; neuer Push erst, wenn es mindestens 60 Minuten trocken war.
- Merkt sich den Stand in fb/regen_push.json. Secret: NTFY_TOPIC."""
import gzip, json, os, urllib.request, urllib.error, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
LAT, LON = 49.750, 9.017
VORLAUF_MIN = 60          # so weit voraus wird gewarnt
SCHWELLE = 0.02           # mm pro 5 Minuten (≈ 0,24 mm/h) – darunter zählt es als trocken
PAUSE_MIN = 60            # so lange muss es trocken gewesen sein, bevor wieder gewarnt wird
MERK = os.path.join(os.path.dirname(__file__), '..', '..', 'fb', 'regen_push.json')


def laden():
    j = None
    for extra in ('&distance=0', '&distance=1000', ''):
        url = 'https://api.brightsky.dev/radar?lat=%s&lon=%s&format=plain%s' % (LAT, LON, extra)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de', 'Accept-Encoding': 'gzip'})
            with urllib.request.urlopen(req, timeout=30) as r:
                roh = r.read()
                if r.headers.get('Content-Encoding') == 'gzip': roh = gzip.decompress(roh)
                j = json.loads(roh); break
        except urllib.error.HTTPError as e:
            print('Radar-Abfrage', extra or '(ohne distance)', '->', e.code, e.read().decode()[:200])
    if j is None: return []
    out = []
    for e in j.get('radar') or []:
        v = e.get('precipitation_5')
        while isinstance(v, list): v = v[0] if v else 0
        out.append((dt.datetime.fromisoformat(e['timestamp']).astimezone(TZ), (v or 0) / 100))
    return sorted(out)


def staerke(mm5):
    h = mm5 * 12
    return 'leichter' if h < 0.5 else 'mäßiger' if h < 4 else 'starker'


def push(titel, text, prio):
    topic = os.environ.get('NTFY_TOPIC')
    if not topic: print('Kein NTFY_TOPIC – kein Push.'); return
    req = urllib.request.Request('https://ntfy.sh/' + topic, data=text.encode('utf-8'), headers={
        'Title': titel.encode('utf-8').decode('latin-1'), 'Priority': prio, 'Tags': 'umbrella',
        'Click': 'https://wetter-badkoenig.de/'})
    urllib.request.urlopen(req, timeout=20).read(); print('Push gesendet:', titel)


def main():
    jetzt = dt.datetime.now(TZ)
    try: merk = json.load(open(MERK))
    except Exception: merk = {}
    werte = [w for w in laden() if w[0] >= jetzt - dt.timedelta(minutes=5)]
    if not werte: print('Keine Radardaten.'); return
    nass = lambda w: w[1] >= SCHWELLE
    jetzt_nass = nass(werte[0])
    if jetzt_nass or any(nass(w) for w in werte if w[0] <= jetzt + dt.timedelta(minutes=10)):
        merk['zuletzt_nass'] = jetzt.isoformat()

    bald = [w for w in werte if w[0] <= jetzt + dt.timedelta(minutes=VORLAUF_MIN)]
    erster = next((w for w in bald if nass(w)), None)
    letzter_push = merk.get('gepusht')

    # Darf wieder gewarnt werden? Erst, wenn es nach dem letzten Push lange genug trocken war.
    darf = True
    if letzter_push:
        zn = dt.datetime.fromisoformat(merk.get('zuletzt_nass', letzter_push))
        darf = jetzt - zn >= dt.timedelta(minutes=PAUSE_MIN) and not jetzt_nass

    if erster and not jetzt_nass and darf:
        regen = [w for w in werte if w[0] >= erster[0]]
        ende = next((w for w in regen if not nass(w)), None)
        mx = max(w[1] for w in regen[:12])
        minuten = max(5, round((erster[0] - jetzt).total_seconds() / 300) * 5)
        text = ('Laut Regenradar beginnt in Bad König in etwa %d Minuten (gegen %s Uhr) %s Regen.'
                % (minuten, erster[0].strftime('%H:%M'), staerke(mx)))
        if ende: text += ' Voraussichtlich vorbei gegen %s Uhr.' % ende[0].strftime('%H:%M')
        else: text += ' Er hält laut Radar mindestens bis %s Uhr an.' % werte[-1][0].strftime('%H:%M')
        nacht = jetzt.hour >= 22 or jetzt.hour < 6
        push('🌧️ Regen im Anmarsch', text, 'low' if nacht else ('high' if mx * 12 >= 4 else 'default'))
        merk['gepusht'] = jetzt.isoformat()
        merk['zuletzt_nass'] = erster[0].isoformat()
    else:
        print('Kein Regen-Push (jetzt nass: %s, Regen in %d min: %s, darf: %s).'
              % (jetzt_nass, VORLAUF_MIN, bool(erster), darf))
    json.dump(merk, open(MERK, 'w'), indent=1)


if __name__ == '__main__':
    try: main()
    except Exception as e: print('Regen-Push nicht möglich:', e)
