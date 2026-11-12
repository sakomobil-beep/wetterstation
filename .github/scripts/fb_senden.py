#!/usr/bin/env python3
"""Postet Beiträge automatisch auf die Facebook-Seite „Private Wetterstation Bad König“
und zusätzlich auf das verknüpfte Instagram-Konto (Bild bzw. Reel; Variable IG_AUTO=aus schaltet das ab).

Gepostet wird direkt über die Facebook Graph API (Secrets FB_PAGE_TOKEN + FB_PAGE_ID).
Fehlen die Secrets, wird nichts gepostet (Beiträge bleiben zum Teilen von Hand in der Zentrale).

Aufruf:  fb_senden.py video  -> Video-Wetterbericht (fb/wetter.mp4) ab 7 Uhr, 1x pro Tag
         fb_senden.py tag      -> Tagesbeitrag (fb/post.jpg + fb/post.json), höchstens 1x pro Tag (wird nicht mehr automatisch gepostet)
         fb_senden.py mittag   -> Mittagsbeitrag ab 12 Uhr (fb/mittag.jpg): Karte des Kreises mit dem Rest des Tages
         fb_senden.py abend    -> Abendvideo aus dem Studio ab 19 Uhr (fb/abendvideo.mp4), Text aus fb/abend.json; sonntags nicht
         fb_senden.py story      -> Morgen-Story (fb/story.jpg) auf Facebook + Instagram, ab 7 Uhr (Sa/So 8 Uhr)
         fb_senden.py mittagstory -> Mittags-Story (fb/mittagstory.jpg) auf Facebook + Instagram, ab 12 Uhr
         fb_senden.py abendstory -> Abend-Story mit dem Wetter für morgen (fb/abendstory.jpg) auf Facebook + Instagram, ab 19 Uhr
         fb_senden.py woche    -> Wochenausblick-Video (fb/woche.mp4), sonntags ab 20 Uhr, 1x pro Woche
         fb_senden.py sonder   -> neue Sondermeldungen aus fb/sonder.json, je Lage 1x pro Tag; standardmäßig nur amtliche DWD-Warnungen
                          (Variable FB_SONDER_AUTO: amtlich | alle | aus)
Gemerkt wird in fb/gepostet.json, damit nichts doppelt erscheint."""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
FB = os.path.join(os.path.dirname(__file__), '..', '..', 'fb')
BASIS = 'https://wetter-badkoenig.de/fb/'
MERK = os.path.join(FB, 'gepostet.json')


def post_json(url, daten):
    req = urllib.request.Request(url, data=json.dumps(daten).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read().decode()[:300]


def push(titel, text, prio='default', tags='white_check_mark'):
    """Handy-Push über ntfy (Secret NTFY_TOPIC) – Fehler stoppen das Posten nie."""
    topic = os.environ.get('NTFY_TOPIC')
    if not topic: return
    try:
        req = urllib.request.Request('https://ntfy.sh/' + topic, data=text.encode('utf-8'), headers={
            'Title': titel.encode('utf-8').decode('latin-1'), 'Priority': prio, 'Tags': tags,
            'Click': 'https://www.facebook.com/profile.php?id=' + (os.environ.get('FB_PAGE_ID') or '')
            if os.environ.get('FB_PAGE_ID') else 'https://www.facebook.com/'})
        urllib.request.urlopen(req, timeout=20).read(); print('Push gesendet:', titel)
    except Exception as e: print('Push fehlgeschlagen:', e)


GRAPH = 'https://graph.facebook.com/v21.0/'


def _ig_id(tok, page):
    """Instagram-Business-Konto, das mit der Facebook-Seite verknüpft ist (wird selbst abgefragt)."""
    with urllib.request.urlopen(GRAPH + '%s?fields=instagram_business_account&access_token=%s' % (page, tok), timeout=30) as r:
        return (json.loads(r.read().decode()).get('instagram_business_account') or {}).get('id')


IG_TAGS = '#odenwald #odenwaldwetter #badkönig #wetter #odenwaldkreis #michelstadt #erbach #höchst #breuberg #wetterbericht #hessen #wettervorhersage'


def ig_text(text):
    """Instagram-Text: Hashtag-Zeilen vom Facebook-Text weg, dafür fester Instagram-Hashtag-Block."""
    z = [l for l in text.rstrip().split('\n') if not (l.strip().startswith('#') and all(w.startswith('#') for w in l.split()))]
    return ('\n'.join(z).rstrip() + '\n\n' + IG_TAGS)[:2200]


def instagram(datei, text, video=False, story=False):
    """Postet dasselbe zusätzlich auf Instagram (Bild oder Reel). Fehler stoppen Facebook nie.
    Variable IG_AUTO=aus schaltet Instagram ab."""
    if (os.environ.get('IG_AUTO') or '').lower() == 'aus': return False
    tok, page = os.environ.get('FB_PAGE_TOKEN'), os.environ.get('FB_PAGE_ID')
    if not (tok and page): return False
    try:
        ig = _ig_id(tok, page)
        if not ig: print('Instagram: kein Konto mit der Seite verknüpft – übersprungen.'); return False
        url = BASIS + datei + '?v=' + str(int(time.time()))
        d = {'caption': ig_text(text), 'access_token': tok}
        if story: d = {'media_type': 'STORIES', 'image_url': url, 'access_token': tok}
        elif video: d.update(media_type='REELS', video_url=url, share_to_feed='true')
        else: d['image_url'] = url
        with urllib.request.urlopen(GRAPH + ig + '/media', data=urllib.parse.urlencode(d).encode(), timeout=120) as r:
            cid = json.loads(r.read().decode())['id']
        for _ in range(60):   # Instagram verarbeitet Medien erst (Videos dauern)
            with urllib.request.urlopen(GRAPH + cid + '?fields=status_code&access_token=' + tok, timeout=30) as r:
                st = json.loads(r.read().decode()).get('status_code')
            if st == 'FINISHED': break
            if st == 'ERROR': print('Instagram: Verarbeitung fehlgeschlagen.'); return False
            time.sleep(10)
        q = urllib.parse.urlencode({'creation_id': cid, 'access_token': tok}).encode()
        with urllib.request.urlopen(GRAPH + ig + '/media_publish', data=q, timeout=60) as r:
            print('Instagram direkt:', r.status, r.read().decode()[:200])
        return True
    except urllib.error.HTTPError as e:
        print('Instagram-Fehler:', e.code, e.read().decode()[:300])
    except Exception as e:
        print('Instagram-Fehler:', e)
    return False


def video_senden(datei, text):
    url = BASIS + datei + '?v=' + str(int(time.time()))
    tok, page = os.environ.get('FB_PAGE_TOKEN'), os.environ.get('FB_PAGE_ID')
    if tok and page:
        q = urllib.parse.urlencode({'file_url': url, 'description': text, 'access_token': tok}).encode()
        with urllib.request.urlopen('https://graph-video.facebook.com/v21.0/%s/videos' % page, data=q, timeout=300) as r:
            print('Facebook-Video direkt:', r.status, r.read().decode()[:200])
        instagram(datei, text, video=True); return True
    print('Kein Facebook-Zugang eingerichtet (FB_PAGE_TOKEN/FB_PAGE_ID).')
    return False


def senden(bild, text, art):
    """bild = Dateiname in fb/, text = Beitragstext. Gibt True zurück, wenn gepostet."""
    url = BASIS + bild + '?v=' + str(int(time.time()))
    tok, page = os.environ.get('FB_PAGE_TOKEN'), os.environ.get('FB_PAGE_ID')
    if tok and page:
        q = urllib.parse.urlencode({'url': url, 'caption': text, 'access_token': tok}).encode()
        with urllib.request.urlopen('https://graph.facebook.com/v21.0/%s/photos' % page, data=q, timeout=60) as r:
            print('Facebook direkt:', r.status, r.read().decode()[:200])
        instagram(bild, text); return True
    print('Kein Facebook-Zugang eingerichtet (FB_PAGE_TOKEN/FB_PAGE_ID) – nichts gepostet.')
    return False


def fb_story(datei):
    """Foto-Story auf der Facebook-Seite: Bild unveröffentlicht hochladen, dann als Story veröffentlichen."""
    tok, page = os.environ.get('FB_PAGE_TOKEN'), os.environ.get('FB_PAGE_ID')
    if not (tok and page): return False
    try:
        url = BASIS + datei + '?v=' + str(int(time.time()))
        q = urllib.parse.urlencode({'url': url, 'published': 'false', 'access_token': tok}).encode()
        with urllib.request.urlopen(GRAPH + '%s/photos' % page, data=q, timeout=60) as r:
            pid = json.loads(r.read().decode())['id']
        q = urllib.parse.urlencode({'photo_id': pid, 'access_token': tok}).encode()
        with urllib.request.urlopen(GRAPH + '%s/photo_stories' % page, data=q, timeout=60) as r:
            print('Facebook-Story direkt:', r.status, r.read().decode()[:200])
        return True
    except urllib.error.HTTPError as e:
        print('Facebook-Story-Fehler:', e.code, e.read().decode()[:300])
    except Exception as e:
        print('Facebook-Story-Fehler:', e)
    return False


def story_beide(M, key, datei, heute, jetzt, titel, text, tags):
    """Postet eine Story auf Instagram (Schlüssel key) und Facebook (Schlüssel fb_key), jede höchstens 1x pro Tag."""
    wo = []
    if M.get(key) != heute and not frisch_gepostet(key, heute):
        if instagram(datei, '', story=True):
            M[key] = heute; M[key + '_zeit'] = jetzt.isoformat(timespec='minutes'); wo.append('Instagram')
    fk = 'fb_' + key
    if M.get(fk) != heute and not frisch_gepostet(fk, heute):
        if fb_story(datei):
            M[fk] = heute; M[fk + '_zeit'] = jetzt.isoformat(timespec='minutes'); wo.append('Facebook')
    if wo: push(titel, text + ' Jetzt online auf ' + ' und '.join(wo) + '.', tags=tags)


def seiten_token():
    """Ist FB_PAGE_TOKEN ein Benutzer-Token, holen wir daraus den Seiten-Token (sonst 403 beim Posten)."""
    tok, page = os.environ.get('FB_PAGE_TOKEN', '').strip(), os.environ.get('FB_PAGE_ID', '').strip()
    if not tok or not page: return
    try:
        with urllib.request.urlopen(GRAPH + '%s?fields=access_token&access_token=%s' % (page, tok), timeout=30) as r:
            pt = json.load(r).get('access_token')
        if pt and pt != tok:
            os.environ['FB_PAGE_TOKEN'] = pt
            print('Seiten-Token aus Benutzer-Token geholt.')
    except Exception as e:
        print('Seiten-Token nicht ermittelt (nutze Token wie hinterlegt):', e)


def frisch_gepostet(schluessel, heute):
    """Prüft direkt vor dem Posten den aktuellen Stand von fb/gepostet.json bei GitHub.
    Verhindert Doppelposts, wenn zwei Läufe (Zeitplan + cron-job.org-Weckruf) fast gleichzeitig starten:
    ein wartender Lauf arbeitet sonst mit dem alten Stand vom Startzeitpunkt."""
    import subprocess
    try:
        subprocess.run(['git', 'fetch', '-q', 'origin'], timeout=60, check=True)
        ref = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'origin/HEAD'], capture_output=True, text=True).stdout.strip() or 'origin/main'
        aktuell = json.loads(subprocess.run(['git', 'show', ref + ':fb/gepostet.json'], capture_output=True, text=True, timeout=30).stdout or '{}')
        if aktuell.get(schluessel) == heute:
            print('Schon von einem anderen Lauf gepostet (%s) – übersprungen.' % schluessel); return True
    except Exception as e:
        print('Frischer Stand nicht prüfbar:', e)
    return False


def main():
    seiten_token()
    modus = sys.argv[1] if len(sys.argv) > 1 else 'tag'
    if modus == 'pushtest':
        push('Wetterstation verbunden', 'Ab jetzt bekommst du eine Nachricht, sobald etwas automatisch auf Facebook gepostet wurde 👍'); return
    heute = dt.datetime.now(TZ).date().isoformat()
    try: M = json.load(open(MERK, encoding='utf-8'))
    except Exception: M = {}
    if modus == 'tag':
        j = json.load(open(os.path.join(FB, 'post.json'), encoding='utf-8'))
        if not j.get('erstellt', '').startswith(heute): print('Tagesbeitrag ist nicht von heute – übersprungen.'); return
        if M.get('tag') == heute: print('Tagesbeitrag heute schon gepostet.'); return
        # warten, bis GitHub Pages das neue Bild ausliefert (sonst holt Facebook das alte)
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        if frisch_gepostet('tag', heute): return
        if senden('post.jpg', j['text'], 'tag'): M['tag'] = heute
    elif modus == 'abend':   # Abendvideo aus dem Studio, Mo–Sa ab 19 Uhr; der ausführliche Abendtext ist die Beschreibung
        jetzt = dt.datetime.now(TZ)
        if jetzt.weekday() == 6: print('Sonntags kommt der Wochenausblick – kein Abendvideo.'); return
        if jetzt.hour < 19: print('Abendvideo erst ab 19 Uhr.'); return
        j = json.load(open(os.path.join(FB, 'abend.json'), encoding='utf-8'))
        if not j.get('erstellt', '').startswith(heute): print('Abendtext ist nicht von heute – übersprungen.'); return
        try: v = json.load(open(os.path.join(FB, 'abendvideo.json'), encoding='utf-8'))
        except Exception: print('Kein Abendvideo vorhanden.'); return
        if v.get('datum') != heute: print('Abendvideo ist nicht von heute.'); return
        if M.get('abend') == heute: print('Abendvideo heute schon gepostet.'); return
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        if frisch_gepostet('abend', heute): return
        if video_senden('abendvideo.mp4', j['text'].rstrip() + ' #Wettervideo'):
            M['abend'] = heute; M['abend_zeit'] = jetzt.isoformat(timespec='minutes')
            push('Abendvideo gepostet', 'Max aus dem Studio ist jetzt auf Facebook und Instagram online.', tags='crescent_moon,movie_camera')
    elif modus == 'video':
        jetzt = dt.datetime.now(TZ)
        ab = 8 if jetzt.weekday() >= 5 else 7   # Wochenende erst ab 8 Uhr
        if jetzt.hour < ab: print('Vor %d Uhr – Video kommt später.' % ab); return
        j = json.load(open(os.path.join(FB, 'wetter.json'), encoding='utf-8'))
        if j.get('datum') != heute: print('Video ist nicht von heute.'); return
        if M.get('video') == heute: print('Video heute schon gepostet.'); return
        try: zeilen = json.load(open(os.path.join(FB, 'post.json'), encoding='utf-8'))['text'].split('\n')[1:]
        except Exception: zeilen = ['', 'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de', '#BadKönig #Odenwald #Wetter']
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))   # warten, bis GitHub Pages das frisch erstellte Video ausliefert
        if frisch_gepostet('video', heute): return
        d = dt.date.fromisoformat(heute)
        tage = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        kopf = ('⚠️ Wetter-Special' if j.get('special') else '🎬 Euer Odenwald-Wetter') + ' für %s, %d.%d. – mit Max, eurem Wettersprecher!' % (tage[d.weekday()], d.day, d.month)
        if j.get('frage'): kopf += '\n\n💬 ' + j['frage']   # Frage an die Zuschauer – bringt Kommentare
        if video_senden('wetter.mp4', '\n'.join([kopf] + zeilen).strip() + ' #Wettervideo'):
            M['video'] = heute; M['video_zeit'] = jetzt.isoformat(timespec='minutes'); push('Wettervideo gepostet', kopf + '\nMax ist jetzt auf Facebook online.', tags='movie_camera,white_check_mark')
    elif modus == 'story':   # Facebook + Instagram: Story mit dem Wetter von heute, zusammen mit dem Morgenvideo
        jetzt = dt.datetime.now(TZ); ab = 8 if jetzt.weekday() >= 5 else 7
        if jetzt.hour < ab: print('Vor %d Uhr – Story kommt später.' % ab); return
        if jetzt.hour >= 11: print('Story nur morgens (bis 11 Uhr).'); return
        try: j = json.load(open(os.path.join(FB, 'story.json'), encoding='utf-8'))
        except Exception: print('Keine Story vorhanden.'); return
        if j.get('datum') != heute: print('Story ist nicht von heute.'); return
        if M.get('story') == heute and M.get('fb_story') == heute: print('Story heute schon gepostet.'); return
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        story_beide(M, 'story', 'story.jpg', heute, jetzt, 'Morgen-Story gepostet', 'Die Morgen-Story mit dem Wetter von heute.', 'camera,white_check_mark')
    elif modus == 'mittag':   # Mittagsbeitrag: Karte des Kreises mit dem Rest des Tages
        jetzt = dt.datetime.now(TZ)
        if jetzt.hour < 12: print('Mittagsbeitrag erst ab 12 Uhr.'); return
        if jetzt.hour >= 16: print('Zu spät für den Mittagsbeitrag.'); return
        try: j = json.load(open(os.path.join(FB, 'mittag.json'), encoding='utf-8'))
        except Exception: print('Kein Mittagsbeitrag vorhanden.'); return
        if j.get('datum') != heute: print('Mittagsbeitrag ist nicht von heute.'); return
        if M.get('mittag') == heute: print('Mittagsbeitrag heute schon gepostet.'); return
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        if frisch_gepostet('mittag', heute): return
        if senden('mittag.jpg', j['text'], 'mittag'):
            M['mittag'] = heute; M['mittag_zeit'] = jetzt.isoformat(timespec='minutes')
            push('Mittagsbeitrag gepostet', 'Die Karte mit dem Rest des Tages ist jetzt auf Facebook und Instagram online.', tags='map,white_check_mark')
    elif modus == 'abendstory':   # Facebook + Instagram: Story mit dem Wetter von morgen, zusammen mit dem Abendvideo
        jetzt = dt.datetime.now(TZ)
        if jetzt.hour < 19: print('Vor 19 Uhr – Abend-Story kommt später.'); return
        try: j = json.load(open(os.path.join(FB, 'abendstory.json'), encoding='utf-8'))
        except Exception: print('Keine Abend-Story vorhanden.'); return
        if j.get('datum') != heute: print('Abend-Story ist nicht von heute.'); return
        if M.get('abendstory') == heute and M.get('fb_abendstory') == heute: print('Abend-Story heute schon gepostet.'); return
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        story_beide(M, 'abendstory', 'abendstory.jpg', heute, jetzt, 'Abend-Story gepostet', 'Die Story mit dem Wetter für morgen.', 'camera,crescent_moon')
    elif modus == 'mittagstory':   # Facebook + Instagram: Mittagskarte als Story, ab 12 Uhr
        jetzt = dt.datetime.now(TZ)
        if jetzt.hour < 12: print('Mittags-Story erst ab 12 Uhr.'); return
        if jetzt.hour >= 16: print('Zu spät für die Mittags-Story.'); return
        try: j = json.load(open(os.path.join(FB, 'mittagstory.json'), encoding='utf-8'))
        except Exception: print('Keine Mittags-Story vorhanden.'); return
        if j.get('datum') != heute: print('Mittags-Story ist nicht von heute.'); return
        if M.get('mittagstory') == heute and M.get('fb_mittagstory') == heute: print('Mittags-Story heute schon gepostet.'); return
        story_beide(M, 'mittagstory', 'mittagstory.jpg', heute, jetzt, 'Mittags-Story gepostet', 'Die Mittagskarte als Story.', 'camera,map')
    elif modus == 'jahr':   # Jahresrückblick: am 30.12. ab 18 Uhr, einmal
        jetzt = dt.datetime.now(TZ)
        if not (jetzt.month == 12 and jetzt.day >= 30 and jetzt.hour >= 18): print('Jahresrückblick nur am 30.12. ab 18 Uhr.'); return
        try: j = json.load(open(os.path.join(FB, 'jahr.json'), encoding='utf-8'))
        except Exception: print('Kein Jahresrückblick vorhanden.'); return
        if j.get('jahr') != jetzt.year or not j.get('datum', '').startswith(str(jetzt.year) + '-12-3'): print('Jahresrückblick ist nicht aktuell.'); return
        if M.get('jahr') == heute: print('Jahresrückblick schon gepostet.'); return
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        if frisch_gepostet('jahr', heute): return
        if video_senden('jahr.mp4', j['text']):
            M['jahr'] = heute; M['jahr_zeit'] = jetzt.isoformat(timespec='minutes'); push('Jahresrückblick gepostet', 'Max mit dem Wetterjahr %d ist jetzt auf Facebook und Instagram online.' % j['jahr'], tags='fireworks,white_check_mark')
    elif modus == 'woche':
        jetzt = dt.datetime.now(TZ)
        if jetzt.weekday() != 6 or jetzt.hour < 20: print('Wochenausblick nur sonntags ab 20 Uhr.'); return
        j = json.load(open(os.path.join(FB, 'woche.json'), encoding='utf-8'))
        if j.get('datum') != heute: print('Wochenausblick ist nicht von heute.'); return
        if M.get('woche') == heute: print('Wochenausblick heute schon gepostet.'); return
        time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        if frisch_gepostet('woche', heute): return
        txt = '\n'.join(['📅 Euer Wochenausblick für den Odenwald – mit Max, eurem Wettersprecher!', ''] +
                        ['• ' + z for z in j.get('zeilen', [])] +
                        ['', '📍 Vorhersage für den Odenwaldkreis aus vier Wettermodellen – Messwerte von unserer Station in Bad König.',
                         'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de', '#Odenwald #Odenwaldkreis #BadKönig #Wetter #Wochenausblick #Wettervideo'])
        if video_senden('woche.mp4', txt):
            M['woche'] = heute; M['woche_zeit'] = dt.datetime.now(TZ).isoformat(timespec='minutes'); push('Wochenausblick gepostet', 'Max mit dem Wochenausblick ist jetzt auf Facebook online.', tags='calendar,white_check_mark')
    elif modus == 'sonder':
        modus_s = os.environ.get('FB_SONDER_AUTO') or 'amtlich'   # amtlich (Standard) | alle | aus
        if modus_s == 'aus': print('Sondermeldungen werden von Hand geteilt.'); return
        try: j = json.load(open(os.path.join(FB, 'sonder.json'), encoding='utf-8'))
        except Exception: return
        neu = [m for m in j.get('meldungen', []) if M.get('sonder-' + m['typ']) != heute and (m.get('amtlich') or modus_s == 'alle')]
        if neu: time.sleep(int(os.environ.get('FB_WARTEN', '90')))
        neu = [m for m in neu if not frisch_gepostet('sonder-' + m['typ'], heute)]
        for m in neu:
            if senden(m['bild'], m['text'], 'sonder'):
                M['sonder-' + m['typ']] = heute; M['sonder_zeit'] = dt.datetime.now(TZ).isoformat(timespec='minutes')
                push('Sondermeldung gepostet', m['text'].split('\n')[0][:200] + '\nAutomatisch auf Facebook veröffentlicht.',
                     prio='high' if m.get('amtlich') else 'default', tags='warning,white_check_mark')
    json.dump(M, open(MERK, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
