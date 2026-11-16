#!/usr/bin/env python3
"""Notfall-Sicherung des Merkzettels fb/gepostet.json (16.11.2026).
Scheitert git push mehrfach, ging bisher der Merker verloren und der nächste Lauf postete dasselbe noch einmal
(Dauerregen-Warnung kam doppelt). Hier wird die Datei einzeln über die GitHub-Schnittstelle gespeichert:
Stand bei GitHub holen, unsere Einträge darüberlegen, mit Prüfsumme speichern – mehrere Versuche."""
import base64, json, os, sys, time, urllib.request, urllib.error

PFAD = 'fb/gepostet.json'
repo, tok = os.environ.get('GITHUB_REPOSITORY'), os.environ.get('GH_TOKEN')
if not (repo and tok): print('Kein Zugang für Notfall-Sicherung.'); sys.exit(1)
URL = 'https://api.github.com/repos/%s/contents/%s' % (repo, PFAD)
H = {'Authorization': 'Bearer ' + tok, 'Accept': 'application/vnd.github+json'}
lokal = json.load(open(PFAD, encoding='utf-8'))
for i in range(6):
    try:
        with urllib.request.urlopen(urllib.request.Request(URL + '?ref=main', headers=H), timeout=30) as r:
            j = json.load(r)
        fern = json.loads(base64.b64decode(j['content']).decode('utf-8'))
        fern.update(lokal)
        daten = json.dumps({'message': 'Facebook: Merkzettel gesichert (Notfall)', 'sha': j['sha'], 'branch': 'main',
                            'content': base64.b64encode(json.dumps(fern, ensure_ascii=False, indent=1).encode('utf-8')).decode()}).encode()
        with urllib.request.urlopen(urllib.request.Request(URL, data=daten, headers=H, method='PUT'), timeout=30) as r:
            print('Merkzettel per Schnittstelle gesichert:', r.status); sys.exit(0)
    except urllib.error.HTTPError as e: print('Versuch', i + 1, 'fehlgeschlagen:', e.code)
    except Exception as e: print('Versuch', i + 1, 'fehlgeschlagen:', e)
    time.sleep(5 * (i + 1))
sys.exit(1)
