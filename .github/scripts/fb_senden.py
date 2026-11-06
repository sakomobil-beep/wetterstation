#!/usr/bin/env python3
"""Postet Beiträge automatisch auf die Facebook-Seite „Private Wetterstation Bad König“.

Zwei Wege – welcher aktiv ist, entscheiden allein die GitHub-Secrets:
  B) FB_PAGE_TOKEN (+ FB_PAGE_ID) gesetzt  -> direkt über die Facebook Graph API (Entwicklerkonto)
  A) sonst MAKE_WEBHOOK gesetzt            -> über ein Make.com-Szenario (Webhook -> Facebook Pages: Foto hochladen)
  sonst                                    -> nichts tun (Beiträge bleiben zum Teilen von Hand auf facebook.html)

Aufruf:  fb_senden.py video  -> Video-Wetterbericht (fb/wetter.mp4) ab 7 Uhr, 1x pro Tag (Secret MAKE_VIDEO_WEBHOOK)
         fb_senden.py tag      -> Tagesbeitrag (fb/post.jpg + fb/post.json), höchstens 1x pro Tag (wird nicht mehr automatisch gepostet)
         fb_senden.py abend    -> Abendbeitrag ab 18 Uhr (fb/abend.jpg + fb/abend.json): morgen/übermorgen, freitags Wochenende
         fb_senden.py sonder   -> neue Sondermeldungen aus fb/sonder.json, je Lage 1x pro Tag; standardmäßig nur amtliche DWD-Warnungen
                          (Variable FB_SONDER_AUTO: amtlich | alle | aus)
Gemerkt wird in fb/gepostet.json, damit nichts doppelt erscheint."""
import json, os, sys, time, urllib.request, urllib.parse, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
FB = os.path.join(os.path.dirname(__file__), '..', '..', 'fb')
BASIS = 'https://wetter-badkoenig.de/fb/'
MERK = os.path.join(FB, 'gepostet.json')


def post_json(url, daten):
    req = urllib.request.Request(url, data=json.dumps(daten).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read().decode()[:300]


def video_senden(datei, text):
    url = BASIS + datei + '?v=' + str(int(time.time()))
    tok, page, hook = os.environ.get('FB_PAGE_TOKEN'), os.environ.get('FB_PAGE_ID'), os.environ.get('MAKE_VIDEO_WEBHOOK')
    if tok and page:
        q = urllib.parse.urlencode({'file_url': url, 'description': text, 'access_token': tok}).encode()
        with urllib.request.urlopen('https://graph-video.facebook.com/v21.0/%s/videos' % page, data=q, timeout=300) as r:
            print('Facebook-Video direkt:', r.status, r.read().decode()[:200]); return True
    if hook:
        st, body = post_json(hook, {'art': 'video', 'video_url': url, 'text': text})
        print('Make-Video:', st, body); return 200 <= st < 300
    print('Kein Video-Weg eingerichtet (MAKE_VIDEO_WEBHOOK oder FB_PAGE_TOKEN).')
    return False


def senden(bild, text, art):
    """bild = Dateiname in fb/, text = Beitragstext. Gibt True zurück, wenn gepostet."""
    url = BASIS + bild + '?v=' + str(int(time.time()))
    tok, page, hook = os.environ.get('FB_PAGE_TOKEN'), os.environ.get('FB_PAGE_ID'), os.environ.get('MAKE_WEBHOOK')
    if tok and page:
        q = urllib.parse.urlencode({'url': url, 'caption': text, 'access_token': tok}).encode()
        with urllib.request.urlopen('https://graph.facebook.com/v21.0/%s/photos' % page, data=q, timeout=60) as r:
            print('Facebook direkt:', r.status, r.read().decode()[:200]); return True
    if hook:
        st, body = post_json(hook, {'art': art, 'bild_url': url, 'text': text})
        print('Make:', st, body); return 200 <= st < 300
    print('Kein Facebook-Weg eingerichtet (FB_PAGE_TOKEN oder MAKE_WEBHOOK) – nichts gepostet.')
    return False


def main():
    modus = sys.argv[1] if len(sys.argv) > 1 else 'tag'
    heute = dt.datetime.now(TZ).date().isoformat()
    try: M = json.load(open(MERK, encoding='utf-8'))
    except Exception: M = {}
    if modus == 'tag':
        j = json.load(open(os.path.join(FB, 'post.json'), encoding='utf-8'))
        if not j.get('erstellt', '').startswith(heute): print('Tagesbeitrag ist nicht von heute – übersprungen.'); return
        if M.get('tag') == heute: print('Tagesbeitrag heute schon gepostet.'); return
        # warten, bis GitHub Pages das neue Bild ausliefert (sonst holt Facebook das alte)
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        if senden('post.jpg', j['text'], 'tag'): M['tag'] = heute
    elif modus == 'abend':
        j = json.load(open(os.path.join(FB, 'abend.json'), encoding='utf-8'))
        if not j.get('erstellt', '').startswith(heute): print('Abendbeitrag ist nicht von heute – übersprungen.'); return
        if M.get('abend') == heute: print('Abendbeitrag heute schon gepostet.'); return
        if dt.datetime.now(TZ).hour < 18 or int(j['erstellt'][11:13]) < 18:   # nur der echte Abendbeitrag ab 18 Uhr (nicht Test-Erstellungen tagsüber)
            print('Abendbeitrag erst ab 18 Uhr.'); return
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        if senden('abend.jpg', j['text'], 'tag'): M['abend'] = heute
    elif modus == 'video':
        jetzt = dt.datetime.now(TZ)
        ab = 8 if jetzt.weekday() >= 5 else 7   # Wochenende erst ab 8 Uhr
        if jetzt.hour < ab: print('Vor %d Uhr – Video kommt später.' % ab); return
        j = json.load(open(os.path.join(FB, 'wetter.json'), encoding='utf-8'))
        if j.get('datum') != heute: print('Video ist nicht von heute.'); return
        if M.get('video') == heute: print('Video heute schon gepostet.'); return
        try: zeilen = json.load(open(os.path.join(FB, 'post.json'), encoding='utf-8'))['text'].split('\n')[1:]
        except Exception: zeilen = ['', 'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de', '#BadKönig #Odenwald #Wetter']
        d = dt.date.fromisoformat(heute)
        tage = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        kopf = ('⚠️ Wetter-Special' if j.get('special') else '🎬 Euer Odenwald-Wetter') + ' für %s, %d.%d. – mit dem Odenwälder Outdoor-Guide!' % (tage[d.weekday()], d.day, d.month)
        if video_senden('wetter.mp4', '\n'.join([kopf] + zeilen).strip() + ' #Wettervideo'): M['video'] = heute
    elif modus == 'sonder':
        modus_s = os.environ.get('FB_SONDER_AUTO') or 'amtlich'   # amtlich (Standard) | alle | aus
        if modus_s == 'aus': print('Sondermeldungen werden von Hand geteilt.'); return
        try: j = json.load(open(os.path.join(FB, 'sonder.json'), encoding='utf-8'))
        except Exception: return
        neu = [m for m in j.get('meldungen', []) if M.get('sonder-' + m['typ']) != heute and (m.get('amtlich') or modus_s == 'alle')]
        if neu: time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        for m in neu:
            if senden(m['bild'], m['text'], 'sonder'): M['sonder-' + m['typ']] = heute
    json.dump(M, open(MERK, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
