#!/usr/bin/env python3
"""Wöchentlicher Gesundheitsbericht (22.11.2026, Wunsch von Kingman).
Läuft sonntags abends, schaut auf die letzten 7 Tage (Mo–So) und schreibt data/gesundheit.json
(die Zentrale zeigt das unter Technik › Wochenbericht). Gibt es Hinweise, kommt eine Push-Nachricht.

Quellen:
- Posts: Verlauf von fb/gepostet.json in Git (jede Fassung der Woche) -> was an welchem Tag gepostet wurde
- Fehlgeschlagene GitHub-Abläufe: GitHub-Schnittstelle (GITHUB_TOKEN)
- Datenlücken: data/odenwald-archiv/<Monat>.json (Messzeitpunkte je Ort, eigene Station = Bad König)
- Luftqualität: data/luft.json (nur Stand)
Ändert nichts an den anderen Abläufen, liest nur.
"""
import datetime as dt, json, os, subprocess, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
jetzt = dt.datetime.now(TZ)
ende = jetzt.date()                       # Sonntag
start = ende - dt.timedelta(days=6)       # Montag
TAGE = [start + dt.timedelta(days=i) for i in range(7)]

# ---------- Posts aus dem Git-Verlauf von fb/gepostet.json ----------
gesehen = {}   # schluessel -> set(datum)
zeiten = {}    # (schluessel, datum) -> Uhrzeit
warnungen = set()
erst = {}       # schluessel -> erster Tag, an dem es ihn gab (neue Posts wie Threads ab 19.11. zählen erst ab da)
log = subprocess.run(['git', 'log', '--since=%s' % (start - dt.timedelta(days=8)).isoformat(), '--format=%H', '--', 'fb/gepostet.json'],
                     capture_output=True, text=True).stdout.split()
fassungen = []
for h in log:
    try: fassungen.append(json.loads(subprocess.run(['git', 'show', h + ':fb/gepostet.json'], capture_output=True, text=True).stdout))
    except Exception: pass
try: fassungen.append(json.load(open('fb/gepostet.json')))
except Exception: pass
for d in fassungen:
    for k, v in d.items():
        if k.endswith('_zeit') and isinstance(v, str) and len(v) >= 16:
            sk = k[:-5]
            try: tag = dt.date.fromisoformat(v[:10])
            except ValueError: continue
            erst.setdefault(sk, tag); erst[sk] = min(erst[sk], tag)
            if start <= tag <= ende:
                gesehen.setdefault(sk, set()).add(tag)
                zeiten[(sk, tag)] = v[11:16]
    t = d.get('warn2_titel'); z = d.get('warn2_zeit', '')
    if t and z[:10] and start.isoformat() <= z[:10] <= ende.isoformat(): warnungen.add((z[:16], t))

# Soll: (Name, Schlüssel FB/IG, Schlüssel Threads, an welchen Wochentagen; 0 = Montag)
ALLE = range(7)
SOLL = [
    ('Morgenvideo', 'video', 'th_wetter', ALLE),
    ('Morgen-Story / Morgenbild', 'story', 'th_story', ALLE),
    ('Mittagskarte', 'mittag', 'th_mittag', ALLE),
    ('Mittags-Story', 'mittagstory', None, ALLE),
    ('Wetterwissen', 'wissen', 'th_wissen', range(5)),
    ('Abendvideo', 'abend', 'th_abendvideo', range(6)),
    ('Abend-Story / Abendbild', 'abendstory', 'th_abendstory', ALLE),
    ('Wochenausblick', 'woche', 'th_woche', [6]),
]
posts, hinweise = [], []
soll_n = ist_n = 0
for name, fb, th, wt in SOLL:
    tage = [t for t in TAGE if t.weekday() in wt]
    z = {'name': name, 'soll': len(tage)}
    for spalte, sk in (('fb', fb), ('th', th)):
        if not sk: z[spalte] = None; continue
        da = gesehen.get(sk, set())
        tg = [t for t in tage if sk in erst and t >= erst[sk]] if erst.get(sk, start) > start else tage
        fehlt = [t for t in tg if t not in da]
        z[spalte] = len(tg) - len(fehlt); z[spalte + '_soll'] = len(tg)
        soll_n += len(tg); ist_n += len(tg) - len(fehlt)
        for t in fehlt:
            if t == ende and jetzt.hour < 21 and sk in ('abendstory', 'th_abendstory', 'woche', 'th_woche'): continue
            hinweise.append({'tag': t.isoformat(), 'text': '%s %s nicht gepostet' % (name, 'auf Threads' if spalte == 'th' else 'auf Facebook/Instagram')})
    posts.append(z)

# ---------- Fehlgeschlagene GitHub-Abläufe ----------
abl_fehler = []
try:
    repo = os.environ['GITHUB_REPOSITORY']
    req = urllib.request.Request('https://api.github.com/repos/%s/actions/runs?status=failure&per_page=100&created=>=%s' % (repo, start.isoformat()),
                                 headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'], 'Accept': 'application/vnd.github+json'})
    runs = json.load(urllib.request.urlopen(req, timeout=30)).get('workflow_runs', [])
    zahl = {}
    for r in runs: zahl[r['name']] = zahl.get(r['name'], 0) + 1
    abl_fehler = [{'name': k, 'anzahl': v} for k, v in sorted(zahl.items(), key=lambda x: -x[1])]
except Exception as e:
    print('GitHub-Abläufe nicht abrufbar:', e)
for a in abl_fehler:
    if a['anzahl'] >= 3: hinweise.append({'tag': '', 'text': 'Ablauf „%s“ %d× fehlgeschlagen' % (a['name'], a['anzahl'])})

# ---------- Datenlücken der Odenwald-Orte (Lücke = über 60 Min. ohne neuen Messwert) ----------
orte = {}
for mon in sorted({t.strftime('%Y-%m') for t in TAGE}):
    try: d = json.load(open('data/odenwald-archiv/%s.json' % mon))
    except Exception: continue
    for ort, werte in d.items():
        orte.setdefault(ort, []).extend(werte.keys())
luecken, abdeckung = [], {}
anf = dt.datetime.combine(start, dt.time(0), TZ); end = min(jetzt, dt.datetime.combine(ende, dt.time(23, 59), TZ))
try: _l = json.load(open('data/odenwald-live.json')); AKTIV = {o['name'] for o in _l['orte'] + _l.get('extra', [])}
except Exception: AKTIV = set(orte)
for ort, ts in orte.items():
    if ort not in AKTIV: continue   # z. B. Erbach, seit 19.11. nicht mehr dabei
    alle = sorted(dt.datetime.fromisoformat(t).replace(tzinfo=TZ) for t in ts)
    zs = sorted({x for x in alle if anf <= x <= end})
    beginn = max(anf, alle[0]) if alle else anf   # neue Orte (z. B. 19.11.) erst ab ihrem ersten Messwert
    punkte = [beginn] + zs + [end]
    fehl_min = 0; groesste = None
    for a, b in zip(punkte, punkte[1:]):
        m = (b - a).total_seconds() / 60
        if m > 60:
            fehl_min += m
            if not groesste or m > groesste[2]: groesste = (a, b, m)
    gesamt = (end - beginn).total_seconds() / 60
    abdeckung[ort] = round(100 * (1 - fehl_min / gesamt), 1) if gesamt else None
    if groesste and groesste[2] >= 120:
        a, b, m = groesste
        luecken.append({'ort': ort, 'von': a.strftime('%d.%m. %H:%M'), 'bis': b.strftime('%d.%m. %H:%M'), 'stunden': round(m / 60, 1)})
# gleiche Lücke bei mehreren Orten = Lücke im Ablauf -> ein Hinweis
grp = {}
for l in luecken: grp.setdefault((l['von'], l['bis'], l['stunden']), []).append(l['ort'])
for (von, bis, h), os_ in grp.items():
    wer = ('%d Odenwald-Orte' % len(os_)) if len(os_) >= 4 else ', '.join(os_)
    bis_k = bis[7:] if bis[:6] == von[:6] else bis
    hinweise.append({'tag': '%s-%s-%s' % (start.year, von[3:5], von[0:2]), 'text': '%s %s Std. ohne Daten (%s–%s)' % (wer, str(h).replace('.', ','), von, bis_k)})
station = abdeckung.get('Bad König')

# ---------- Luftqualität (nur ob aktuell) ----------
luft_ok = None
try:
    st = json.load(open('data/luft.json')).get('stand', '')
    luft_ok = (jetzt - dt.datetime.fromisoformat(st)).total_seconds() < 3 * 3600
except Exception: pass
if luft_ok is False: hinweise.append({'tag': '', 'text': 'Luftqualität seit über 3 Std. nicht aktualisiert'})

# ---------- Speichern (älteste Wochen hinten, max. 12) ----------
bericht = {
    'woche': '%s–%s' % (start.strftime('%d.%m.'), ende.strftime('%d.%m.%Y')), 'start': start.isoformat(), 'ende': ende.isoformat(),
    'erstellt': jetzt.strftime('%Y-%m-%dT%H:%M'), 'posts_ist': ist_n, 'posts_soll': soll_n,
    'station_online': station, 'warnungen': len(warnungen), 'posts': posts, 'ablauf_fehler': abl_fehler,
    'abdeckung': abdeckung, 'luecken': luecken, 'luft_ok': luft_ok,
    'hinweise': sorted(hinweise, key=lambda h: h['tag']),
}
P = 'data/gesundheit.json'
try: alt = json.load(open(P))
except Exception: alt = {'wochen': []}
w = [x for x in alt.get('wochen', []) if x.get('start') != start.isoformat()]
alt = {'stand': bericht['erstellt'], 'wochen': ([bericht] + w)[:12]}
json.dump(alt, open(P, 'w'), ensure_ascii=False, indent=1)
print(json.dumps(bericht, ensure_ascii=False, indent=1)[:3000])

# ---------- Push nur bei Hinweisen ----------
topic = os.environ.get('NTFY_TOPIC')
if hinweise and topic and os.environ.get('KEIN_PUSH') != '1':
    txt = 'Woche %s: %d von %d Posts, %d Hinweis%s\n' % (bericht['woche'], ist_n, soll_n, len(hinweise), 'e' if len(hinweise) != 1 else '')
    txt += '\n'.join('• ' + h['text'] for h in bericht['hinweise'][:6])
    try:
        urllib.request.urlopen(urllib.request.Request('https://ntfy.sh/' + topic, data=txt.encode('utf-8'), headers={
            'Title': 'Wochenbericht Wetterstation', 'Tags': 'stethoscope',
            'Click': 'https://sakomobil-beep.github.io/zentrale/'}), timeout=20).read()
        print('Push gesendet')
    except Exception as e: print('Push fehlgeschlagen:', e)
