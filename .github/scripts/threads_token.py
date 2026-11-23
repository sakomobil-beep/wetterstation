#!/usr/bin/env python3
"""Threads-Schlüssel (Secret THREADS_TOKEN) verlängern – läuft montags im nächtlichen Archiv-Lauf (19.11.2026).
Langlebige Threads-Schlüssel gelten 60 Tage und lassen sich ab 24 Stunden Alter verlängern.
Liefert Meta dabei einen NEUEN Schlüssel, kann GitHub ihn nicht selbst speichern → Push an Kingman.
Läuft der Schlüssel in weniger als 14 Tagen ab, kommt ebenfalls ein Push."""
import os, json, urllib.request, urllib.parse, urllib.error


def push(titel, text):
    t = os.environ.get('NTFY_TOPIC')
    if not t: return
    try:
        rq = urllib.request.Request('https://ntfy.sh/' + t, data=text.encode('utf-8'), headers={'Title': titel.encode('utf-8'), 'Priority': 'high', 'Tags': 'key'})
        urllib.request.urlopen(rq, timeout=20)
    except Exception as e: print('Push:', e)


tok = os.environ.get('THREADS_TOKEN')
if not tok:
    print('Kein Threads-Schlüssel eingerichtet – nichts zu tun.'); raise SystemExit
try:
    q = urllib.parse.urlencode({'grant_type': 'th_refresh_token', 'access_token': tok})
    with urllib.request.urlopen('https://graph.threads.net/refresh_access_token?' + q, timeout=60) as r:
        j = json.loads(r.read().decode())
    tage = int(j.get('expires_in', 0)) // 86400
    print('Threads-Schlüssel verlängert, gültig noch ca.', tage, 'Tage.')
    if j.get('access_token') and j['access_token'] != tok:
        push('Threads-Schlüssel erneuert', 'Meta hat einen neuen Threads-Schlüssel ausgegeben. Bitte Claude Bescheid geben, damit das Secret THREADS_TOKEN aktualisiert wird.')
    elif tage < 14:
        push('Threads-Schlüssel läuft ab', 'Der Threads-Schlüssel gilt nur noch ca. %d Tage. Bitte Claude Bescheid geben.' % tage)
except urllib.error.HTTPError as e:
    msg = e.read().decode()[:300]; print('Threads-Verlängerung fehlgeschlagen:', e.code, msg)
    push('Threads-Schlüssel', 'Verlängerung fehlgeschlagen (%s). Threads-Posts laufen evtl. nicht mehr – bitte Claude Bescheid geben.' % e.code)
except Exception as e:
    print('Threads-Verlängerung:', e)
