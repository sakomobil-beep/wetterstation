#!/usr/bin/env python3
"""Threads-Schlüssel (Secret THREADS_TOKEN) verlängern – läuft montags im nächtlichen Archiv-Lauf (19.11.2026).
Langlebige Threads-Schlüssel gelten 60 Tage und lassen sich ab 24 Stunden Alter verlängern.
Liefert Meta dabei einen NEUEN Schlüssel, speichert der Lauf ihn seit 23.11.2026 selbst als Secret THREADS_TOKEN
(über den Zugangsschlüssel GH_SECRETS_PAT, der nur Secrets im Repo wetterstation ändern darf). Fehlt der oder klappt es nicht → Push an Kingman.
Der Schlüssel wird nie ausgegeben oder ins Protokoll geschrieben.
Läuft der Schlüssel in weniger als 14 Tagen ab, kommt ebenfalls ein Push."""
import os, json, urllib.request, urllib.parse, urllib.error


def push(titel, text):
    t = os.environ.get('NTFY_TOPIC')
    if not t: return
    try:
        rq = urllib.request.Request('https://ntfy.sh/' + t, data=text.encode('utf-8'), headers={'Title': titel.encode('utf-8'), 'Priority': 'high', 'Tags': 'key'})
        urllib.request.urlopen(rq, timeout=20)
    except Exception as e: print('Push:', e)


def secret_speichern(name, wert):
    """Secret im Repo per GitHub-API setzen (verschlüsselt mit dem öffentlichen Repo-Schlüssel, libsodium sealed box)."""
    pat = os.environ.get('GH_SECRETS_PAT'); repo = os.environ.get('GITHUB_REPOSITORY')
    if not pat or not repo: return False
    from base64 import b64encode, b64decode
    from nacl import encoding, public
    h = {'Authorization': 'Bearer ' + pat, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/%s/actions/secrets/public-key' % repo, headers=h), timeout=30) as r:
        k = json.loads(r.read().decode())
    box = public.SealedBox(public.PublicKey(k['key'].encode(), encoding.Base64Encoder()))
    daten = json.dumps({'encrypted_value': b64encode(box.encrypt(wert.encode())).decode(), 'key_id': k['key_id']}).encode()
    rq = urllib.request.Request('https://api.github.com/repos/%s/actions/secrets/%s' % (repo, name), data=daten, method='PUT', headers=dict(h, **{'Content-Type': 'application/json'}))
    with urllib.request.urlopen(rq, timeout=30) as r: return r.status in (201, 204)


if os.environ.get('PAT_TEST'):
    # Probe ohne Änderung: darf GH_SECRETS_PAT den öffentlichen Secret-Schlüssel lesen?
    try:
        rq = urllib.request.Request('https://api.github.com/repos/%s/actions/secrets/public-key' % os.environ['GITHUB_REPOSITORY'],
                                    headers={'Authorization': 'Bearer ' + os.environ.get('GH_SECRETS_PAT', ''), 'Accept': 'application/vnd.github+json'})
        urllib.request.urlopen(rq, timeout=30).read(); print('GH_SECRETS_PAT funktioniert.')
        push('Threads-Schlüssel', 'Test erfolgreich: Neue Threads-Schlüssel werden ab jetzt automatisch gespeichert.')
    except Exception as e:
        print('GH_SECRETS_PAT funktioniert nicht:', getattr(e, 'code', type(e).__name__)); raise SystemExit(1)
    raise SystemExit

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
        ok = False
        try: ok = secret_speichern('THREADS_TOKEN', j['access_token'])
        except Exception as e: print('Secret speichern fehlgeschlagen:', type(e).__name__)
        if ok:
            print('Neuer Threads-Schlüssel als Secret gespeichert.')
            push('Threads-Schlüssel erneuert', 'Meta hat einen neuen Threads-Schlüssel ausgegeben – automatisch gespeichert, gültig ca. %d Tage. Nichts zu tun.' % tage)
        else:
            push('Threads-Schlüssel erneuert', 'Meta hat einen neuen Threads-Schlüssel ausgegeben, er konnte aber nicht automatisch gespeichert werden. Bitte Claude Bescheid geben.')
    elif tage < 14:
        push('Threads-Schlüssel läuft ab', 'Der Threads-Schlüssel gilt nur noch ca. %d Tage. Bitte Claude Bescheid geben.' % tage)
except urllib.error.HTTPError as e:
    msg = e.read().decode()[:300]; print('Threads-Verlängerung fehlgeschlagen:', e.code, msg)
    push('Threads-Schlüssel', 'Verlängerung fehlgeschlagen (%s). Threads-Posts laufen evtl. nicht mehr – bitte Claude Bescheid geben.' % e.code)
except Exception as e:
    print('Threads-Verlängerung:', e)
