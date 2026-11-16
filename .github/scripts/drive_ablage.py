#!/usr/bin/env python3
"""Legt jedes live gegangene Max-Video automatisch in Google Drive ab (seit 15.11.2026).

Ordner (legt das Programm selbst an – es sieht wegen des Bereichs drive.file nur seine eigenen Ordner):
  Wetterstation – Videos / <Art> / <JJJJ-MM-TT HH-MM> / <Art JJJJ-MM-TT HH-MM>.mp4 + Beitragstext.txt
Arten: Morgenvideo, Abendvideo, Wochenausblick, Wetterwissen, Monatsrückblick, Jahresrückblick, Unwetter-Specials

Secrets: GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN (fehlen sie, passiert nichts).
Fehler beim Ablegen stoppen nie das Posten – es gibt nur eine Push-Nachricht.

Von Hand:  drive_ablage.py <datei.mp4 in fb/> [JJJJ-MM-TTTHH:MM]   (z. B. zum Nachtragen)
"""
import json, os, sys, urllib.request, urllib.parse, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
FB = os.path.join(os.path.dirname(__file__), '..', '..', 'fb')
WURZEL = 'Wetterstation – Videos'
ARTEN = {'wetter.mp4': 'Morgenvideo', 'abendvideo.mp4': 'Abendvideo', 'woche.mp4': 'Wochenausblick',
         'wissen.mp4': 'Wetterwissen', 'monat.mp4': 'Monatsrückblick', 'jahr.mp4': 'Jahresrückblick',
         'special.mp4': 'Unwetter-Specials'}
BILDER = {'story.jpg': 'Morgen-Story', 'mittagstory.jpg': 'Mittags-Story', 'abendstory.jpg': 'Abend-Story',
          'mittag.jpg': 'Mittagskarte', 'post.jpg': 'Tagesbild', 'special-story.jpg': 'Unwetter-Storys',
          'warn2-story.jpg': 'Warn-Storys (Stufe 2)', 'warn2-post.jpg': 'Warn-Beiträge (Stufe 2)'}   # 15.11.2026
WURZEL_BILD = 'Wetterstation – Bilder'
API = 'https://www.googleapis.com/drive/v3/files'
ORDNER = 'application/vnd.google-apps.folder'


def zugang():
    cid, sec, ref = (os.environ.get(k) for k in ('GDRIVE_CLIENT_ID', 'GDRIVE_CLIENT_SECRET', 'GDRIVE_REFRESH_TOKEN'))
    if not (cid and sec and ref): return None
    q = urllib.parse.urlencode({'client_id': cid.strip(), 'client_secret': sec.strip(), 'refresh_token': ref.strip(),
                                'grant_type': 'refresh_token'}).encode()
    with urllib.request.urlopen('https://oauth2.googleapis.com/token', data=q, timeout=30) as r:
        return json.loads(r.read().decode())['access_token']


def anfrage(tok, url, daten=None, methode=None, kopf=None, roh=False):
    h = {'Authorization': 'Bearer ' + tok}
    if kopf: h.update(kopf)
    if daten is not None and not isinstance(daten, (bytes, bytearray)):
        daten = json.dumps(daten).encode(); h.setdefault('Content-Type', 'application/json; charset=UTF-8')
    req = urllib.request.Request(url, data=daten, headers=h, method=methode)
    with urllib.request.urlopen(req, timeout=300) as r:
        return r if roh else json.loads(r.read().decode() or '{}')


def ordner(tok, name, eltern=None):
    """Ordner suchen (nur eigene) oder anlegen."""
    q = "mimeType='%s' and trashed=false and name='%s'" % (ORDNER, name.replace("'", "\\'"))
    if eltern: q += " and '%s' in parents" % eltern
    r = anfrage(tok, API + '?' + urllib.parse.urlencode({'q': q, 'fields': 'files(id)', 'spaces': 'drive'}))
    if r.get('files'): return r['files'][0]['id']
    meta = {'name': name, 'mimeType': ORDNER}
    if eltern: meta['parents'] = [eltern]
    return anfrage(tok, API + '?fields=id', meta)['id']


def hochladen(tok, pfad, name, eltern, mime):
    """Fortsetzbarer Upload (auch für große Videos)."""
    groesse = os.path.getsize(pfad)
    r = anfrage(tok, 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id',
                {'name': name, 'parents': [eltern]}, kopf={'X-Upload-Content-Type': mime, 'X-Upload-Content-Length': str(groesse)}, roh=True)
    ziel = r.headers['Location']
    with open(pfad, 'rb') as f:
        req = urllib.request.Request(ziel, data=f.read(), method='PUT', headers={'Content-Type': mime, 'Content-Length': str(groesse)})
    with urllib.request.urlopen(req, timeout=600) as r2:
        return json.loads(r2.read().decode())['id']


def push(titel, text):
    t = os.environ.get('NTFY_TOPIC')
    if not t: return
    try:
        urllib.request.urlopen(urllib.request.Request('https://ntfy.sh/' + t, data=text.encode('utf-8'),
                               headers={'Title': titel.encode('utf-8').decode('latin-1'), 'Tags': 'floppy_disk'}), timeout=20).read()
    except Exception as e: print('Push fehlgeschlagen:', e)


def ablegen(datei, text='', zeit=None):
    """Video fb/<datei> mit Beitragstext in Drive ablegen. Gibt True/False zurück, wirft nie."""
    bild = datei in BILDER
    art = BILDER.get(datei) if bild else ARTEN.get(datei)
    wurzel = WURZEL_BILD if bild else WURZEL
    pfad = os.path.join(FB, datei)
    if not art or not os.path.exists(pfad): return False
    try:
        tok = zugang()
        if not tok: print('Google Drive nicht eingerichtet (GDRIVE_* fehlen) – keine Ablage.'); return False
        zeit = zeit or dt.datetime.now(TZ)
        stempel = zeit.strftime('%Y-%m-%d %H-%M')
        w = ordner(tok, wurzel); a = ordner(tok, art, w); u = ordner(tok, stempel, a)
        if bild: hochladen(tok, pfad, '%s %s.jpg' % (art, stempel), u, 'image/jpeg')
        else: hochladen(tok, pfad, '%s %s.mp4' % (art, stempel), u, 'video/mp4')
        tf = '/tmp/beitragstext.txt'
        open(tf, 'w', encoding='utf-8').write('%s · live gegangen am %s Uhr\n\n%s\n' % (art, zeit.strftime('%d.%m.%Y %H:%M'), text or ''))
        hochladen(tok, tf, 'Beitragstext.txt', u, 'text/plain')
        print('Google Drive: %s / %s / %s abgelegt.' % (wurzel, art, stempel))
        return True
    except Exception as e:
        print('Google Drive: Ablage fehlgeschlagen:', e)
        push('Drive-Ablage fehlgeschlagen', '%s konnte nicht in Google Drive abgelegt werden (%s). Gepostet wurde trotzdem.' % (art, str(e)[:150]))
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    z = dt.datetime.fromisoformat(sys.argv[2]).replace(tzinfo=TZ) if len(sys.argv) > 2 else None
    txt = ''
    try:
        if sys.argv[1] == 'wetter.mp4': txt = json.load(open(os.path.join(FB, 'post.json'), encoding='utf-8')).get('text', '')
    except Exception: pass
    sys.exit(0 if ablegen(sys.argv[1], txt, z) else 1)
