#!/usr/bin/env python3
"""Täglicher Video-Wetterbericht „Odenwald-Wetter“ mit dem Comic-Moderator Max (Wettersprecher).
Liest fb/daten.json (von fb_post.py), schreibt fb/wetter.mp4 (+ wetter.json) bzw. fb/special.mp4 (+ special.json).
Stimme: Microsoft Neural-Stimme „Conrad“ über edge-tts. Ohne edge-tts (Test) wird eine stumme Spur erzeugt.
Eigene (KI-)Hintergrundbilder: einfach als .jpg/.png in den Ordner video/hintergruende/ legen – sie werden mitbenutzt."""
import json, termine as TERMINE, os, sys, math, random, subprocess, asyncio, glob, tempfile, datetime as dt
from zoneinfo import ZoneInfo
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FB = os.path.join(ROOT, 'fb')
W, H, FPS = 720, 1280, 25
VOICE = 'de-DE-ConradNeural'
TAGE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
R = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def F(n, bold=True): return ImageFont.truetype(B if bold else R, n)

sys.path.insert(0, os.path.dirname(__file__))
from fb_post import wort, icon  # gleiche Wetterwörter und Symbole wie das Facebook-Bild


# =====================================================================
#  1) Moderationstext
# =====================================================================
def zahl(n):
    n = int(round(n))
    return ('minus %d' % -n) if n < 0 else str(n)


def art(d):
    w = wort(d['code'])
    return {'sonnig': 'viel Sonne', 'heiter bis wolkig': 'einen Mix aus Sonne und Wolken', 'bedeckt': 'viele Wolken',
            'neblig': 'Nebel', 'Nieselregen': 'Nieselregen', 'Regen': 'Regen', 'Schnee': 'Schnee',
            'Schauer': 'einzelne Schauer', 'Gewitter': 'Gewitter'}.get(w, 'wechselhaftes Wetter')


def regenzeit(d):
    """Tageszeiten mit Schauern/Regen – aus derselben Einstufung wie alles andere (d['nied'])."""
    N = d.get('nied')
    if N: t = [('am Vormittag', N['vm'] in ('schauer', 'regen', 'gewitter')), ('am Nachmittag', N['nm'] in ('schauer', 'regen', 'gewitter')),
               ('am Abend', N['ab'] in ('schauer', 'regen', 'gewitter'))]
    else: t = [('am Vormittag', d['rp_vm'] >= 50), ('am Nachmittag', d['rp_nm'] >= 50), ('am Abend', d['rp_ab'] >= 50)]
    nass = [n for n, x in t if x]
    if not nass: return None
    if len(nass) == 3: return 'den ganzen Tag über'
    return ' und '.join(nass)


def stufe(d):
    N = d.get('nied')
    if N: return N['stufe']
    return 'trocken' if d['rp'] < 10 else 'vereinzelt' if d['rp'] < 30 else 'regen' if d['rp'] >= 60 and d.get('regen', 0) >= 1 else 'schauer'


def nass_tag(d):
    """Wird es nass (Schauer, Regen, Gewitter)? Grundlage für Kleidung, Hintergrund, Tipp, Frage, Bemerkung."""
    return stufe(d) in ('schauer', 'regen', 'gewitter')


# --- Tipp-Gedächtnis: kein Freizeittipp doppelt innerhalb von 14 Tagen (fb/tipps.json) ---
TIPP_DATEI = os.path.join(FB, 'tipps.json')
def _tipps_laden():
    try: return json.load(open(TIPP_DATEI, encoding='utf-8'))
    except Exception: return []
TIPP_LOG = _tipps_laden()
def _schluessel(t): return t[:40]


def wahl(rnd, liste, tage=14):
    """Wählt einen Tipp, der in den letzten `tage` Tagen nicht vorkam (falls möglich)."""
    grenze = (dt.date.today() - dt.timedelta(days=tage)).isoformat()
    neu = {e['k'] for e in TIPP_LOG if e['d'] >= grenze}
    frei = [t for t in liste if _schluessel(t) not in neu] or liste
    t = rnd.choice(frei)
    TIPP_LOG.append(dict(d=dt.date.today().isoformat(), k=_schluessel(t)))
    return t


# --- Satz-Gedächtnis: dieselbe Formulierung frühestens nach 10 Tagen wieder (fb/saetze.json) ---
SATZ_DATEI = os.path.join(FB, 'saetze.json')
try: SATZ_LOG = json.load(open(SATZ_DATEI, encoding='utf-8'))
except Exception: SATZ_LOG = []


def frisch(rnd, gruppe, liste, tage=10):
    """Wählt eine Formulierung aus `liste`, die in den letzten `tage` Tagen (ohne heute) nicht benutzt wurde."""
    if not liste: return ''
    heute = dt.date.today().isoformat(); grenze = (dt.date.today() - dt.timedelta(days=tage)).isoformat()
    alt = {e['k'] for e in SATZ_LOG if grenze <= e['d'] < heute and e['g'] == gruppe}
    frei = [x for x in liste if _schluessel(x) not in alt] or liste
    t = rnd.choice(frei)
    SATZ_LOG.append(dict(d=heute, g=gruppe, k=_schluessel(t)))
    return t


def saetze_speichern():
    grenze = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    try: json.dump([e for e in SATZ_LOG if e['d'] >= grenze][-400:], open(SATZ_DATEI, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    except Exception as e: print('Satz-Gedächtnis nicht gespeichert:', e)


# Klimamittel Höchstwert 1991–2020 (DWD Michelstadt-Vielbrunn, auf 184,5 m umgerechnet) – wie im Klima-Tab
KL_TMAX = [2.5, 3.9, 8.3, 13.4, 17.4, 20.8, 22.9, 22.8, 18.0, 12.4, 6.6, 3.3]
MONATSTEIL = ['Anfang', 'Mitte', 'Ende']


def klima_tmax(datum):
    """Normaler Höchstwert für diesen Tag (zwischen den Monatsmitteln gleitend)."""
    m = datum.month - 1; f = (datum.day - 15) / 30.0
    n = (m + 1) % 12 if f >= 0 else (m - 1) % 12
    return KL_TMAX[m] + (KL_TMAX[n] - KL_TMAX[m]) * abs(f)


def einordnung(d, rnd):
    """Ordnet den Höchstwert gegenüber dem Klimamittel ein (nicht jeden Tag)."""
    dif = d['tmax'] - klima_tmax(d['datum'])
    zeit = '%s %s' % (MONATSTEIL[min(2, (d['datum'].day - 1) // 10)], MONATE[d['datum'].month - 1])
    if dif >= 4:
        return ' ' + frisch(rnd, 'klima_mild', ['Für %s ist das übrigens ungewöhnlich mild.' % zeit, 'Das sind einige Grad mehr, als um diese Zeit üblich ist.',
                                                 'Normal wären jetzt eher %s Grad – also deutlich zu warm für die Jahreszeit.' % zahl(klima_tmax(d['datum'])),
                                                 'Ganz schön mild für %s!' % zeit])
    if dif <= -4:
        return ' ' + frisch(rnd, 'klima_kalt', ['Für %s ist das ziemlich kalt.' % zeit, 'Normal wären um diese Zeit eher %s Grad.' % zahl(klima_tmax(d['datum'])),
                                                 'Das ist deutlich kälter, als es um diese Jahreszeit üblich ist.'])
    if abs(dif) <= 1.5 and rnd.random() < 0.25:
        return ' ' + frisch(rnd, 'klima_normal', ['Das ist ganz normal für die Jahreszeit.', 'Für %s also genau im Durchschnitt.' % zeit,
                                                   'Typisches Wetter für %s, würde ich sagen.' % zeit])
    return ''


def vergleich_gestern(d, rnd):
    """Bezug auf gestern (gemessen an der Station Bad König)."""
    g = d.get('gestern')
    if not g or g.get('tmax') is None: return ''
    dif = round(d['tmax'] - g['tmax'])
    if dif >= 3:
        return ' ' + frisch(rnd, 'gestern_waermer', ['Damit wird es rund %d Grad wärmer als gestern.' % dif, 'Das sind etwa %d Grad mehr als gestern.' % dif,
                                                     'Spürbar milder als gestern – gut %d Grad mehr.' % dif])
    if dif <= -3:
        return ' ' + frisch(rnd, 'gestern_kaelter', ['Das sind rund %d Grad weniger als gestern.' % -dif, 'Deutlich kühler als gestern, um etwa %d Grad.' % -dif,
                                                     'Im Vergleich zu gestern also ein ganzes Stück frischer.'])
    nass_heute = d['rp'] >= 50
    sf = stufe(d)
    if (g.get('regen') or 0) >= 2 and sf == 'trocken':
        return ' ' + frisch(rnd, 'gestern_trocken', ['Nach dem Regen von gestern bleibt es heute trocken.', 'Endlich mal wieder trocken, nachdem es gestern noch geregnet hat.',
                                                     'Gestern nass, heute trocken – so mag ich das.'])
    if (g.get('regen') or 0) >= 2 and sf == 'vereinzelt':
        return ' ' + frisch(rnd, 'gestern_meist_trocken', ['Nach dem Regen gestern wird es heute deutlich trockener.', 'Damit wird es heute weniger nass als gestern.'])
    if (g.get('regen') or 0) < 0.2 and sf in ('schauer', 'regen', 'gewitter'):
        return ' ' + frisch(rnd, 'gestern_nass', ['Anders als gestern wird es heute nass.', 'Nach dem trockenen Tag gestern kommt heute wieder Regen.']
                            if sf != 'schauer' else ['Anders als gestern sind heute Schauer möglich.', 'Nach dem trockenen Tag gestern kann es heute örtlich Schauer geben.'])
    if abs(dif) <= 1 and rnd.random() < 0.3:
        return ' ' + frisch(rnd, 'gestern_gleich', ['Temperaturmäßig also ähnlich wie gestern.', 'Kaum anders als gestern.'])
    return ''


def reaktion(d, rnd):
    """Kurze, menschliche Reaktion vorneweg – sparsam (etwa jedes dritte Mal, wenn es passt)."""
    if rnd.random() > 0.33: return ''
    w = wort(d['code'])
    if d['tmax'] <= 3 or d.get('frost_min', d['tmin']) <= -3: return frisch(rnd, 'r_kalt', ['Brrr! ', 'Puh, das wird frisch. ', 'Tja, der Winter klopft an. '])
    if w in ('Regen', 'Gewitter') or nass_tag(d): return frisch(rnd, 'r_nass', ['Puh. ', 'Tja, ', 'Na ja, '])
    if w == 'sonnig' or (d['sonne'] >= 6 and stufe(d) == 'trocken'): return frisch(rnd, 'r_sonne', ['Herrlich! ', 'Na, das kann sich sehen lassen! ', 'Also, '])
    return frisch(rnd, 'r_neutral', ['Also, ', 'So, ', ''])


def mundart(d, rnd):
    """Ab und zu ein Odenwälder Satz – sehr sparsam (etwa jedes fünfte Video)."""
    if rnd.random() > 0.2: return ''
    w = wort(d['code'])
    if w in ('Regen', 'Schauer', 'Nieselregen', 'Gewitter') or nass_tag(d):
        opt = ['Des werd e nass Sach!', 'Do bleibt mer liewer drinne.']
    elif d['tmax'] <= 5:
        opt = ['Do brauchd mer die dick Jack!', 'Des is e kalt Sach heit.']
    elif w in ('sonnig', 'heiter bis wolkig'):
        opt = ['Do kammer net meckern!', 'Des basst!']
    else:
        opt = ['Ei jo, so is es halt im Odenwald.', 'Kammer nix mache.']
    return ' ' + frisch(rnd, 'mundart', opt, tage=21)


def frage_fuer(d, heute, rnd):
    """Frage an die Zuschauer zum Schluss – passend zum Wetter, gleiche Frage frühestens nach 10 Tagen."""
    w = wort(d['code']); opt = []
    if d.get('frost_min', d['tmin']) <= 0: opt += ['Wer musste heute früh schon Scheiben kratzen? Schreibt’s in die Kommentare!',
                                                  'Wie kalt war es heute Morgen bei euch? Schreibt mir eure Temperatur und euren Ort!']
    if w in ('Regen', 'Schauer', 'Nieselregen', 'Gewitter') or nass_tag(d): opt += ['Regnet es bei euch schon? Schreibt mir euren Ort in die Kommentare!',
                                                                                     'Was macht ihr an so einem Regentag? Verratet es mir in den Kommentaren!']
    if w == 'Schnee' or d.get('schnee', 0) >= 1: opt += ['Liegt bei euch schon Schnee? Schreibt mir euren Ort – und gern ein Foto!']
    if w == 'neblig': opt += ['Wie dicht ist der Nebel bei euch? Schreibt euren Ort in die Kommentare!']
    if w in ('sonnig', 'heiter bis wolkig') or d.get('sonne', 0) >= 5: opt += ['Was habt ihr bei dem schönen Wetter heute vor? Schreibt’s mir!',
                                                                             'Scheint bei euch schon die Sonne? Schreibt mir euren Ort!']
    opt += ['Aus welchem Ort im Odenwald schaut ihr zu? Schreibt’s in die Kommentare!',
            'Wie sieht’s gerade bei euch draußen aus? Schreibt mir euren Ort!',
            'Passt meine Vorhersage bei euch? Sagt’s mir in den Kommentaren!']
    if heute.weekday() == 4: opt += ['Was habt ihr am Wochenende vor? Schreibt’s mir in die Kommentare!']
    return frisch(rnd, 'frage', opt)


def folgen_fuer(heute, rnd, warn=False):
    """Kurzer, wechselnder Aufruf zum Folgen – neue Follower anlocken."""
    opt = ['Folgst du uns eigentlich schon? Dann verpasst du kein Wetter mehr – jeden Morgen frisch aus dem Odenwald!',
           'Noch kein Follower? Ein Klick auf Folgen, und ich bin jeden Morgen pünktlich bei dir.',
           'Kennst du jemanden im Odenwald, der immer wissen will, wie das Wetter wird? Schick ihm das Video – und folg uns, falls du’s noch nicht tust!',
           'Damit du die nächste Unwetterwarnung nicht verpasst: Folg uns einfach. Kostet nichts – und ich freu mich!',
           'Das Wetter kommt hier direkt von unserer eigenen Station in Bad König. Wenn dir das gefällt: Folgen, liken, teilen!',
           'Hilf mir, den ganzen Odenwald zu erreichen: Folg uns und teil das Video mit deinen Nachbarn!',
           'Wer uns folgt, weiß morgens als Erster Bescheid – ob Frost, Regen oder Sonne. Bist du schon dabei?',
           'Ein Daumen hoch und ein Follow – damit hilfst du einem kleinen Wetterprojekt aus dem Odenwald enorm!',
           'Du schaust gerade zum ersten Mal zu? Dann herzlich willkommen – und gleich auf Folgen drücken!']
    if heute.weekday() == 0: opt.append('Neue Woche, neue Follower? Wenn du uns noch nicht folgst: Jetzt ist der perfekte Moment!')
    if heute.weekday() == 4: opt.append('Bevor’s ins Wochenende geht: Folg uns, dann weißt du auch Samstag und Sonntag, was das Wetter macht!')
    if warn: opt.append('Bei Warnungen melden wir uns sofort – folg uns, damit du nichts verpasst!')
    return frisch(rnd, 'folgen', opt)


def tipps_speichern():
    saetze_speichern()
    grenze = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    json.dump([e for e in TIPP_LOG if e['d'] >= grenze][-80:], open(TIPP_DATEI, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)


def abend_tipp(heute, rnd, regen=False):
    """Weihnachtsmärkte und Christmas Lights, je nach Datum und Wochentag."""
    m, tag, wt = heute.month, heute.day, heute.weekday()
    markt = (m == 11 and tag >= 27) or (m == 12 and tag <= 20)
    lights = (m == 11 and tag >= 13) or m == 12 or (m == 1 and tag <= 10)
    if (m, tag) in ((12, 24), (12, 25), (12, 31), (1, 1)): lights = False   # Ruhetage
    opt = []   # Weihnachtsmärkte, Feiertage und Ferien kommen jetzt aus data/termine.json (termine.py)
    if lights:
        opt.append(('Und wenn es dunkel wird: Von 17 bis 20 Uhr leuchten die Christmas Lights im Kurpark Bad König – dieses Jahr mit „Tonis fantastischen Erinnerungen“. Zeit-Slot vorher online buchen!',
                    'Ein kleiner Lichtblick: Ab 17 Uhr verwandeln die Christmas Lights den Kurpark Bad König in eine Märchenwelt. Tickets mit Zeit-Slot gibt es online.'))
        opt.append(('Tipp für Familien: Bei den Christmas Lights im Kurpark Bad König haben Kinder bis 14 freien Eintritt – Lichterrundgang täglich ab 17 Uhr.',
                    'Abends ab 17 Uhr zu den Christmas Lights im Kurpark Bad König – Kinder bis 14 sind kostenlos dabei. Zeit-Slot online buchen!'))
        if wt >= 2:
            opt.append(('Heute Abend hat auch der Wintermarkt bei den Christmas Lights im Kurpark offen – mit Glühwein, Livebühne und Kunsthandwerk, bis 21 Uhr.',
                        'Aufwärmen im Zirkuszelt: Der Wintermarkt bei den Christmas Lights im Kurpark Bad König hat heute bis 21 Uhr geöffnet – mit Glühwein und Livebühne.'))
    if not opt: return ''
    return ' ' + wahl(rnd, [o[1 if regen else 0] for o in opt], tage=3)


def tipp(d, rnd, heute):
    """Freizeittipp für den Odenwald passend zum Wetter und zur Jahreszeit."""
    m, tag = heute.month, heute.day
    w = wort(d['code'])
    trocken = not nass_tag(d) and w not in ('Regen', 'Gewitter', 'Schnee')
    if w == 'Schnee' or d['schnee'] >= 1:
        return wahl(rnd, ['Erst durch den Schnee stapfen, dann ab ins warme Thermalbad der Odenwald-Therme Bad König – besser geht Winter nicht!',
                           'Holt die Schlitten raus! Auf der Tromm und rund um den Katzenbuckel wird es weiß – aber fahrt vorsichtig, es kann glatt sein.',
                           'Winterwunderland Odenwald! Ein Schneespaziergang durchs Mümlingtal – mit festen Schuhen und warmer Mütze.'])
    if w == 'Gewitter':
        return 'Bei Gewitter gilt: raus aus dem Wald und weg von den Höhen. Lieber ab ins Trockene – zum Beispiel ins Elfenbeinmuseum nach Erbach.'
    if not trocken:
        r = wahl(rnd, ['Ideales Wetter für die Odenwald-Therme hier in Bad König – warmes Thermalwasser statt kalter Regen.',
                        'Schwitzen statt nass werden: Die Saunalandschaft der Odenwald-Therme Bad König ist bei Regen genau richtig.',
                        'Ab nach Michelstadt ins Stadtmuseum in der historischen Kellerei – und danach ein Kaffee in der Altstadt.',
                        'Ein Bummel durch die Michelstädter Altstadt geht auch mit Schirm – unter dem Fachwerk-Rathaus von 1484 bleibt man sogar trocken.',
                        'Durchatmen bei Schmuddelwetter: Die Salzgrotte in der Odenwald-Therme Bad König ist wie ein Kurzurlaub am Meer.',
                        'Ein Tag für drinnen: Schloss Erbach oder das Elfenbeinmuseum lohnen sich immer.',
                        'Wer trotzdem raus will: Regenjacke an, Gummistiefel an – der Wald im Mümlingtal riecht nach Regen am besten.',
                        'Ein Regentag für Familien: Das Odenwald- und Spielzeugmuseum in Michelstadt hat Spielsachen aus vielen Jahrzehnten.',
                        'Schmuddelwetter? Dann ab nach Erbach: Im Deutschen Elfenbeinmuseum sieht man, wie fein Odenwälder Schnitzer arbeiten.',
                        'Mit Schirm durchs Fachwerk: Ein Bummel durch Erbachs Altstadt rund ums Schloss geht auch bei Regen.'])
        r += abend_tipp(heute, rnd, regen=True)
        return r
    if d['code'] in (45, 48):   # Nebel: kein „schöner Tag für draußen“
        return wahl(rnd, ['Bei Nebel lieber gemütlich: Ab in die warme Odenwald-Therme Bad König – Sauna und Thermalwasser statt grauer Suppe.',
                           'Grau in grau draußen? Dann ein Besuch im Elfenbeinmuseum in Erbach oder im Schloss Erbach.',
                           'Nebeltage sind Museumstage: Das Stadtmuseum in der Michelstädter Kellerei lohnt sich immer.',
                           'Wer trotzdem raus will: Ein kurzer Spaziergang im Kurpark Bad König – im Nebel wirken die Seen richtig mystisch. Aber warm anziehen!',
                           'Durchatmen trotz Nebel: Die Salzgrotte in der Odenwald-Therme Bad König ist wie ein Kurzurlaub am Meer.',
                           'Ein Tag zum Aufwärmen: Heißer Kakao und ein gutes Buch – und wer mag, schaut nachmittags, ob sich der Nebel auf den Höhen lichtet.',
                           'Im Nebel wirkt die Burg Reichenberg über Reichelsheim richtig geheimnisvoll – ein kurzer Spaziergang lohnt sich.',
                           'Nebel im Tal heißt oft Sonne oben: Fahrt mal hoch Richtung Beerfelden oder auf die Tromm – manchmal liegt der Odenwald dann unter einem Nebelmeer.']) + abend_tipp(heute, rnd)
    if d['tmax'] <= 3:
        return wahl(rnd, ['Klare, kalte Luft – perfekt für einen Winterspaziergang im Kurpark Bad König. Danach einen heißen Kakao!',
                           'Klare Winterluft auf der Höhe: Ein Spaziergang am Limes bei Würzberg zum römischen Kastellbad – mit warmem Tee im Rucksack.',
                           'Klare Winterluft heißt Fernsicht: Von der Burg Breuberg schaut ihr weit übers Mümlingtal – die Burghöfe sind frei zugänglich.',
                        'Bei klarer, kalter Luft ist die Aussicht von der Burgruine Freienstein über das Gammelsbachtal besonders weit.',
                        'Ein Winterspaziergang durch den Englischen Garten Eulbach – das Rotwild im Wildgehege freut sich über Besuch.',
                        'Erst durch die Kälte, dann in die Wärme: Die Sauna der Odenwald-Therme Bad König wartet schon.',
                           'Nach dem Winterspaziergang ab ins warme Thermalbad der Odenwald-Therme Bad König – herrlich, wenn draußen die Luft klirrt.',
                           'Eine Runde um die beiden Seen im Kurpark Bad König – und danach aufwärmen im Café am See.',
                           'Wenn es früh dunkel wird: Die beleuchteten Spazierwege im Kurpark Bad König sind perfekt für eine Abendrunde.',
                           'Dick einpacken und hoch auf die Odenwälder Höhen: Bei so kalter Luft ist die Fernsicht oft großartig.',
                           'Ein Winterspaziergang in Beerfelden: Zur Mümlingquelle und hoch zum historischen Galgen – mit Blick weit über die Höhen.',
                           'Kalte, klare Luft und alte Mauern: Ein Spaziergang rund um das Kloster Höchst im Mümlingtal.']) + abend_tipp(heute, rnd)
    if d['tmax'] >= 28:
        return wahl(rnd, ['Heute lieber früh los! Morgens wandern, mittags in den Schatten – und viel trinken.',
                        'Ab an den Marbach-Stausee in Oberzent – Liegewiese, Abkühlung im Wasser und ein Spaziergang am Ufer.',
                        'Schattig und kühl: Die Obrunnschlucht bei Höchst führt am Bach entlang durch den Wald – mit Mini-Burgen und Mühlen im Maßstab 1:20.',
                           'Abkühlung gefällig? Füße rein in die Kneipp-Anlage im Kurpark Bad König – und für die Kinder gibt es den Wasserspielplatz.',
                           'Hitze im Tal – ab in den kühlen Wald oder an den Eutersee bei Erbach. Sonnencreme nicht vergessen!'])
    kurpark = ['Ein Spaziergang um die zwei Seen im Kurpark Bad König – mit Pause im Café am See.',
               'Eine Reise durchs Sonnensystem zu Fuß: Der Planetenweg im Kurpark Bad König ist genau das Richtige für heute.',
               'Ab in den Kurpark Bad König: Der Balancierparcours hält Groß und Klein auf Trab.']
    kurpark += ['Zeitreise zu den Römern: Die Villa Haselburg bei Hummetroth ist ein römisches Landgut von 130 nach Christus – frei zugänglich und mit toller Aussicht.',
                'Auf den Spuren der Römer: In der Villa Haselburg bei Hummetroth seht ihr sogar Reste einer römischen Fußbodenheizung – Eintritt frei, rund um die Uhr.']
    kurpark += ['Hoch auf die Burg Breuberg über dem Mümlingtal: Vom 25 Meter hohen Bergfried reicht der Blick bis zum Spessart – Burghöfe und Gräben sind frei zugänglich.',
                'Ritterburg zum Anfassen: Die Burg Breuberg ist eine der am besten erhaltenen Burgen Süddeutschlands – mit tiefem Burggraben und dicken Festungsmauern.']
    fuehrung = (m == 3 and tag >= 15) or 4 <= m <= 10 or (m == 11 and tag <= 15)
    if fuehrung and heute.weekday() >= 5:
        kurpark.append('Wochenendtipp: Auf der Burg Breuberg gibt es heute Burgführungen – mit Rittersaal und dem 85 Meter tiefen Brunnen samt historischem Tretrad.')
    if 4 <= m <= 10 and heute.weekday() == 6:
        kurpark.append('Sonntagstipp: Das Infozentrum der Römischen Villa Haselburg bei Hummetroth hat heute von 13 bis 17 Uhr geöffnet – mit Originalfunden und 3D-Rekonstruktionen.')
    if 4 <= m <= 10:
        kurpark += ['Wie wäre es mit einer Runde Minigolf im Kurpark Bad König? Danach ein Eis im Café am See.',
                    'Für Familien: Wasserspielplatz und Balancierparcours im Kurpark Bad König – da werden die Kids richtig ausgepowert.']
        if d['tmax'] >= 18: kurpark.append('Schuhe aus und rein in die Kneipp-Anlage im Kurpark Bad König – das macht müde Wanderbeine wieder munter.')
    schoen = ('Perfektes Wanderwetter', 'schöner Tag', 'bei Sonne', 'bei diesem Wetter', 'Bei gutem Wetter')
    def passt(liste): return liste if d['code'] <= 2 else [x for x in liste if not any(k in x for k in schoen)]
    r = wahl(rnd, passt(kurpark + ['Perfektes Wanderwetter! Auf dem Limes-Wanderweg geht ihr direkt an der alten römischen Grenze entlang – quer durch den Odenwald.',
                    'Ab nach Vielbrunn zum nachgebauten Limesturm – so sahen die römischen Wachtürme vor fast 1900 Jahren aus. Bei gutem Wetter seht ihr sogar die Segelflieger.',
                    'Römer-Wanderung bei Würzberg: Am Kastell steht ein teilweise wiederaufgebautes Römerbad, mit Infotafeln, Schutzhütte und Bänken für die Rast.',
                    'Eine Limes-Runde bei Vielbrunn: Rund um das alte Kastell Hainhaus lagen einst bis zu 150 römische Soldaten an der Grenze.',
                    'Perfektes Wanderwetter! Eine Runde über die Höhen rund um Reichelsheim, mit Blick auf die Burg Reichenberg.',
                    'Ab nach Beerfelden: Von der Mümlingquelle geht es hoch zum historischen Galgen – mit Aussicht über die Odenwaldhöhen.',
                    'Eine Runde um das Kloster Höchst und dann durchs Mümlingtal – gemütlich und für jedes Alter.',
                        'Ein Ausflug in die Obrunnschlucht bei Höchst: Am Bach entlang warten Miniaturen bekannter Burgen und Mühlen – toll für Familien.',
                        'Eine Runde um den Marbach-Stausee in Oberzent – der größte See im Odenwald, ideal zum Spazieren oder Radeln.',
                        'Hoch zur Burgruine Freienstein bei Gammelsbach – die Aussicht übers Tal ist den Aufstieg wert.',
                        'Für Fotofreunde: Das Himbächel-Viadukt bei Hetzbach – eine riesige Sandsteinbrücke mitten im Grünen, am besten wenn ein Zug drüberfährt.',
                        'Ab in den Englischen Garten Eulbach: Wildgehege, Teiche und alte Steinmonumente – ein Ausflug für die ganze Familie.',
                        'Ein Kulturspaziergang in Steinbach: Erst die Einhardsbasilika aus dem 9. Jahrhundert, dann rüber zum Schloss Fürstenau.',
                        'Bummeln, Eis essen, Fachwerk bestaunen: Die Michelstädter Altstadt mit dem Rathaus von 1484 ist bei Sonne ein Traum.',
                    'Ab aufs Rad: Der Mümlingtal-Radweg ist bei diesem Wetter genau richtig.',
                    'Wie wäre es mit dem Felsenmeer bei Reichenbach? Bei trockenem Wetter klettert es sich dort am besten.',
                    'Ein schöner Tag für einen Ausflug zur Burg Breuberg – mit toller Aussicht übers Mümlingtal.']))
    rz = regenzeit(d)
    if rz: r += ' Packt aber für %s die Regenjacke ein.' % rz.replace('am ', 'den ').replace('den ganzen Tag über', 'alle Fälle')
    r += abend_tipp(heute, rnd)
    return r


ADJ = {'sonnig': 'richtig sonnig', 'heiter bis wolkig': 'freundlich mit ein paar Wolken', 'bedeckt': 'ziemlich grau',
       'neblig': 'neblig und trüb', 'Nieselregen': 'ungemütlich mit Niesel', 'Regen': 'nass', 'Schnee': 'winterlich',
       'Schauer': 'wechselhaft mit Schauern', 'Gewitter': 'gewittrig'}


def tagtext(d, wann):
    """Tagesvorhersage in wechselnden, gesprochen klingenden Formulierungen (pro Tag fest, damit Tests gleich bleiben)."""
    rnd = random.Random('tag' + str(d['datum']) + wann)
    W, w, t = wann, wort(d['code']), zahl(d['tmax'])
    Wk = W.rstrip(',')
    adj = ADJ.get(w, 'wechselhaft')
    A = art(d)[0].upper() + art(d)[1:]
    opt = ['%s gibt es %s bei Höchstwerten um %s Grad.' % (W, art(d), t),
           '%s wird es %s, bei rund %s Grad.' % (W, adj, t),
           '%s erwartet uns %s – die Temperatur schafft es auf etwa %s Grad.' % (W, art(d), t),
           '%s: %s, und das Thermometer klettert auf %s Grad.' % (Wk, A, t),
           '%s zeigt sich das Wetter %s, die Höchstwerte liegen bei %s Grad.' % (W, adj, t),
           '%s ist %s angesagt, bei bis zu %s Grad.' % (W, art(d), t),
           '%s heißt es: %s, bei etwa %s Grad.' % (W, art(d), t),
           '%s bekommen wir %s – und um die %s Grad.' % (W, art(d), t),
           '%s wird es %s. Die Temperatur: rund %s Grad.' % (W, adj, t)]
    if Wk in ('Heute', 'Morgen'):
        opt += ['Und wie wird es %s? %s, bei rund %s Grad.' % (Wk.lower(), A, t),
                'Was bringt der Tag %s? %s, und das Thermometer zeigt bis zu %s Grad.' % (Wk.lower(), A, t)]
    if d['tmax'] <= 10: opt += ['%s wird es %s, und mehr als %s Grad sind nicht drin.' % (W, adj, t),
                                '%s bleibt es kühl: %s, höchstens %s Grad.' % (W, art(d), t),
                                '%s heißt es Jacke an – %s, und nur rund %s Grad.' % (W, art(d), t)]
    if d['tmax'] >= 22: opt += ['%s wird es %s – und mit %s Grad schön warm.' % (W, adj, t),
                                '%s wird es richtig angenehm: %s bei %s Grad.' % (W, art(d), t)]
    s = frisch(rnd, 'tag', opt)
    rz = regenzeit(d)
    sf = stufe(d)
    if rz and sf == 'schauer':
        s += ' ' + frisch(rnd, 'schauerzeit', ['Örtlich sind %s Schauer möglich.' % rz, 'Schauer gibt es am ehesten %s – nicht überall, aber hier und da.' % rz,
                                               'Ein Schirm schadet nicht, %s kann es örtlich schauern.' % rz])
    elif rz and sf in ('regen', 'gewitter') and w not in ('Regen',):
        s += ' ' + frisch(rnd, 'regenzeit', ['Regen ist vor allem %s wahrscheinlich.' % rz, 'Den Schirm braucht ihr vor allem %s.' % rz,
                                             'Nass werden kann es %s.' % rz, 'Mit Regen müsst ihr vor allem %s rechnen.' % rz,
                                             'Wenn es regnet, dann am ehesten %s.' % rz, 'Schirm einpacken – vor allem %s kann es nass werden.' % rz])
    elif sf == 'vereinzelt':
        s += ' ' + frisch(rnd, 'vereinzelt', ['Meist bleibt es trocken, nur vereinzelt ist ein kurzer Schauer möglich.',
                                              'Ganz ausschließen lässt sich ein einzelner Schauer nicht, meistens bleibt es aber trocken.'])
    if d.get('frost_min', d['tmin']) <= 0:   # Frost nach dem kältesten Talort
        n = zahl(d.get('frost_min', d['tmin']))
        s += ' ' + frisch(rnd, 'frost', ['In der Nacht wird es frostig, bis %s Grad.' % n,
                                         'Nachts geht es runter auf %s Grad. Also: morgens Scheiben kratzen!' % n,
                                         'Und Achtung, in der Nacht gibt es Frost, bis %s Grad.' % n,
                                         'Nachts friert es, mit bis zu %s Grad.' % n,
                                         'In der Nacht rutschen die Werte auf %s Grad – Eiskratzer bereitlegen!' % n,
                                         'Nachts wird es mit %s Grad richtig frostig.' % n,
                                         'Und nachts? Frost, bis %s Grad. Wer früh losmuss: Zeit zum Kratzen einplanen.' % n])
    H = d.get('hoch')   # Höhenlagen des Odenwaldkreises (Oberzent, Mossautal)
    if H:
        if H['schnee']:
            s += ' ' + rnd.choice(['Auf den Höhen, etwa rund um Beerfelden, kann es dabei schneien – da wird es glatt.',
                                    'Oben auf den Höhen, Richtung Oberzent, fällt das Ganze als Schnee. Also vorsichtig fahren!',
                                    'Und wer hoch hinaus muss: Auf den Odenwaldhöhen ist Schnee drin, bei rund %s Grad.' % zahl(H['tmax'])])
        elif d['tmax'] - H['tmax'] >= 2:
            s += ' ' + rnd.choice(['Auf den Höhen, etwa in Oberzent, sind es nur rund %s Grad.' % zahl(H['tmax']),
                                    'Oben auf den Höhen wird es mit etwa %s Grad deutlich frischer als in den Tälern.' % zahl(H['tmax']),
                                    'Richtung Beerfelden und Mossautal bleibt es kühler, um %s Grad.' % zahl(H['tmax'])])
        if H['tmin'] <= 0 < d['tmin']:
            s += ' ' + rnd.choice(['Nachts friert es auf den Höhen – da kann es glatt werden.',
                                    'Auf den Höhen gibt es nachts leichten Frost, bis %s Grad.' % zahl(H['tmin'])])
    if d.get('sicher') == 'gering':
        s += ' ' + rnd.choice(['Aber ehrlich gesagt: Da sind sich die Wettermodelle noch uneinig.',
                                'Kleiner Haken: Die Wettermodelle sind sich da noch nicht einig, also lieber nochmal reinschauen.',
                                'Noch ist das aber unsicher, die Modelle rechnen ziemlich unterschiedlich.'])
    if d['boe'] >= 60: s += ' Vorsicht, Sturmböen bis %d Kilometer pro Stunde!' % round(d['boe'])
    elif d['boe'] >= 45: s += ' ' + rnd.choice(['Dazu frischer Wind mit Böen um %d.' % round(d['boe']),
                                                 'Und der Wind frischt auf, Böen um %d Kilometer pro Stunde.' % round(d['boe'])])
    return s


def komma(v):
    v = round(v, 1)
    return ('minus ' if v < 0 else '') + ('%.1f' % abs(v)).replace('.', ',').replace(',0', '')


def tafel_gestern(g, datum):
    """Tafel zum Rückblick: gestern an der Station Bad König gemessen (Höchst, Tiefst, Regen, Böe)."""
    def k(v): return ('%.1f' % v).replace('.', ',').replace(',0', '')
    w, h = 420, 470
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w, h], radius=28, fill=(255, 255, 255, 238))
    dr.rounded_rectangle([0, 0, w, 74], radius=28, fill=(70, 80, 110, 255)); dr.rectangle([0, 46, w, 74], fill=(70, 80, 110, 255))
    dr.text((w / 2, 37), 'GESTERN GEMESSEN', font=F(32), fill=(255, 255, 255), anchor='mm')
    dr.text((w / 2, 102), '%s, %d.%d. · Station Bad König' % (TAGE[datum.weekday()], datum.day, datum.month), font=F(20, False), fill=(100, 115, 135), anchor='mm')
    rek = {n['art'] for n in (g.get('jahr') or [])}
    kacheln = [('HÖCHSTWERT', k(g['tmax']) + '°', (230, 100, 40), 'hi'), ('TIEFSTWERT', k(g['tmin']) + '°', (60, 120, 200), 'lo'),
               ('REGEN', (k(g['regen']) + ' l/m²') if g.get('regen') else 'trocken', (40, 110, 200), 'regen'),
               ('STÄRKSTE BÖE', '%d km/h' % round(g.get('boe') or 0), (90, 95, 120), 'boe')]
    for n, (t, v, c, key) in enumerate(kacheln):
        x0 = 20 + (n % 2) * 195; y0 = 130 + (n // 2) * 160
        dr.rounded_rectangle([x0, y0, x0 + 185, y0 + 145], radius=20, fill=tuple(int(255 - (255 - c_) * 0.12) for c_ in c), outline=c, width=3)
        dr.text((x0 + 92, y0 + 28), t, font=F(18), fill=c, anchor='mm')
        dr.text((x0 + 92, y0 + 85), v, font=F(46 if len(v) < 6 else 34), fill=c, anchor='mm')
        if key in rek: dr.text((x0 + 92, y0 + 126), 'JAHRESREKORD!', font=F(16), fill=(200, 40, 40), anchor='mm')
    return im


def gestern_txt(g, rnd):
    """Rückblick: gestern an der Station Bad König gemessen."""
    s = rnd.choice(['Kurzer Blick zurück: An unserer Station in Bad König haben wir gestern höchstens %s Grad gemessen, nachts ging es runter auf %s Grad.',
                    'Gestern an der Station in Bad König gemessen: %s Grad am Tag und %s Grad als Tiefstwert.',
                    'Ein Blick auf die Messwerte von gestern aus Bad König: maximal %s, minimal %s Grad.']) % (komma(g['tmax']), komma(g['tmin']))
    if g['regen'] >= 0.5: s += ' Dazu %s Liter Regen pro Quadratmeter.' % komma(g['regen'])
    elif g['regen'] == 0: s += ' Und es blieb trocken.'
    J = {'hi': ('Neuer Wärmerekord für dieses Jahr', 'Grad'), 'lo': ('Neuer Kälterekord für dieses Jahr', 'Grad'),
         'regen': ('So viel Regen an einem Tag gab es dieses Jahr noch nie', 'Liter pro Quadratmeter'), 'boe': ('Die stärkste Böe des Jahres', 'Kilometer pro Stunde')}
    for n in (g.get('jahr') or [])[:2]:
        t, e = J[n['art']]
        s += ' %s: %s %s an unserer Station! Der alte Rekord lag bei %s.' % (t, komma(n['wert']), e, komma(n['alt']))
    r = g.get('rekord')
    if r:
        if r['seit']:
            d = dt.date.fromisoformat(r['seit'])
            s += ' Und die Nacht heute war mit %s Grad die kälteste seit dem %d. %s!' % (komma(r['wert']), d.day, MONATE[d.month - 1])
        else:
            s += ' Und die Nacht heute war mit %s Grad die kälteste seit Beginn unserer Aufzeichnungen!' % komma(r['wert'])
    return s


def fenster_txt(d, rnd):
    """Kein Zeitfenster-Tipp mehr (auf Wunsch entfernt) – nur noch die Sonnenstunden."""
    if d.get('sonne', 0) >= 2: return ' Insgesamt gibt es heute etwa %d Stunden Sonne.' % round(d['sonne'])
    return ''


def himmel_txt(d, rnd):
    h = d.get('himmel')
    if not h: return ''
    if h['kp'] >= 7 and h['klar']: return 'Und jetzt aufgepasst: Heute Nacht sind sogar Polarlichter bei uns im Odenwald möglich! Schaut mal Richtung Norden. '
    if h['kp'] >= 7: return 'Spannend: Ein Sonnensturm könnte heute Nacht Polarlichter bringen – leider ist es bei uns wohl zu bewölkt. '
    if h['vollmond'] and h['klar']: return 'Heute Abend lohnt der Blick nach oben: Vollmond bei klarem Himmel. '
    if h['vollmond']: return 'Heute ist übrigens Vollmond – mal sehen, ob er sich zwischen den Wolken zeigt. '
    if h['klar']: return rnd.choice(['Heute Abend wird es klar – perfekt für einen Blick auf die Sterne. ', 'Der Himmel klart heute Abend auf, ideal zum Sterne gucken. ']) + ''
    return ''


KURZ = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
NASS = (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99)


def woche(tage, rnd):
    """Sonntagsvideo: Ausblick auf Montag bis Freitag. Mo–Mi mit Werten, Do/Fr nur als Tendenz (wie auf der Website)."""
    if len(tage) < 5: return None
    vorn, hinten = tage[:3], tage[3:5]
    lo, hi = min(d['tmax'] for d in vorn), max(d['tmax'] for d in vorn)
    t = rnd.choice(['Und weil Sonntag ist: ein Blick auf die neue Woche.', 'Zum Schluss noch der Ausblick auf die neue Woche.', 'Was bringt die neue Woche?'])
    t += ' Von Montag bis Mittwoch gibt es in den Tälern %s Grad.' % ('um ' + zahl(lo) if lo == hi else 'zwischen ' + zahl(lo) + ' und ' + zahl(hi))
    nass = [TAGE[d['datum'].weekday()] for d in vorn if d['code'] in NASS or nass_tag(d)]
    frost = [TAGE[d['datum'].weekday()] for d in vorn if d['tmin'] <= 0]
    def liste(x): return x[0] if len(x) == 1 else ', '.join(x[:-1]) + ' und ' + x[-1]
    if not nass: t += ' Dabei bleibt es meist trocken.'
    elif len(nass) == 3: t += ' Nass wird es leider an allen drei Tagen.'
    else: t += ' Regen gibt es vor allem am %s.' % liste(nass)
    if frost: t += ' Frost in der Nacht auf %s – also Kratzer bereitlegen.' % liste(frost)
    sn = [d for d in vorn if d.get('hoch') and d['hoch']['schnee']]
    if sn: t += ' Auf den Höhen kann es am %s schneien.' % liste([TAGE[d['datum'].weekday()] for d in sn])
    hx = sum(d['tmax'] for d in hinten) / 2
    tr = 'milder' if hx - hi >= 2 else 'kühler' if hx - lo <= -2 else 'ähnlich'
    hn = sum(1 for d in hinten if d['code'] in NASS or nass_tag(d))
    t += ' Zum Ende der Woche zeigt die Tendenz: %s%s.' % ({'milder': 'eher milder', 'kühler': 'eher kühler', 'ähnlich': 'ähnliche Temperaturen'}[tr],
                                                          ', und eher nass' if hn == 2 else ', mit etwas Regen' if hn == 1 else ', und eher trocken')
    zeilen = ['%s  %s  %d° / %d°' % (KURZ[d['datum'].weekday()], wort(d['code']).replace('heiter bis wolkig', 'heiter'), d['tmax'], d['tmin']) for d in vorn]
    zeilen.append('Do–Fr: Tendenz %s' % {'milder': 'milder', 'kühler': 'kühler', 'ähnlich': 'gleichbleibend'}[tr])
    return t, zeilen



def skript_woche(days, warn, heute):
    """Sonntagabend-Video aus dem Studio: Wochenausblick Montag–Freitag (Mo–Mi mit Werten, Do/Fr Tendenz)."""
    rnd = random.Random('woche' + heute.isoformat())
    woch = days[1:6]
    m0, f0 = woch[0]['datum'], woch[-1]['datum']
    seg = [dict(art='intro', bg='studio',
                tafel_img=tafel_text('DIE NEUE WOCHE', ['%d. %s – %d. %s' % (m0.day, MONATE[m0.month - 1], f0.day, MONATE[f0.month - 1]),
                                                        '• Montag bis Mittwoch', '• Tendenz bis Freitag'], (40, 130, 80)),
                text=rnd.choice(['Ei gude, Odenwald! Hier ist euer Max mit dem Wochenausblick aus dem Studio.',
                                 'Guten Abend, Odenwald! Max hier im Studio – Zeit für den Blick auf die neue Woche.',
                                 'Sonntagabend im Odenwald – hier ist Max mit dem Wochenausblick!'])
                + ((' Vorweg: Vom Deutschen Wetterdienst gilt %s.' % ' und '.join(warn[:2])) if warn else ''))]
    for k, d in enumerate(woch[:3]):
        wann = TAGE[d['datum'].weekday()]
        seg.append(dict(art='tag', tag=d, titel=wann.upper(), bg='studio',
                        text=('Los geht es mit dem %s. ' % wann if k == 0 else '') + tagtext(d, 'Am %s' % wann)))
    wo = woche(woch, rnd)
    if wo:
        t = wo[0].split('Zum Ende der Woche', 1)
        rest = ('Und zum Ende der Woche' + t[1]) if len(t) > 1 else wo[0]
        seg.append(dict(art='woche', tage=woch, bg='studio', zeilen=wo[1], text=rest + ' Genauer wird es dann im Morgenvideo am jeweiligen Tag.'))
    try:
        tl = TERMINE.woche_liste(heute + dt.timedelta(days=1))
        if tl: seg[-1]['text'] += ' Und im Kalender diese Woche: ' + ', '.join(tl) + '.'
    except Exception as e: print('Termine nicht möglich:', e)
    seg.append(dict(art='outro', bg='studio', text=rnd.choice(['Kommt gut in die neue Woche!', 'Ich wünsch euch einen guten Start in die Woche!',
                                                              'Habt eine gute Woche, und passt auf euch auf!'])
                    + ' Jeden Morgen gibt es euer Wettervideo, und alle Live-Werte findet ihr auf wetter-badkoenig.de.'))
    return seg


def karten_txt(orte, tag, rnd, nacht=False):
    """Satz zur Reliefkarte: wärmster und kühlster Ort (abends: kälteste Nacht)."""
    W = []
    for name, la, lo, seite in ORTE_KARTE:
        d = (orte.get(name) or [None] * (tag + 1))[tag] if orte.get(name) and tag < len(orte[name]) else None
        if d: W.append((name, d.get('tmin_kalt', d['tmin']) if nacht else d['tmax'], d))
    if len(W) < 3: return None
    warm, kalt = max(W, key=lambda x: x[1]), min(W, key=lambda x: x[1])
    if nacht:
        frost = [x for x in W if x[1] <= 0]
        s_ = rnd.choice(['Und so wird die Nacht bei euch im Kreis: ', 'Schauen wir auf die Nacht im Odenwaldkreis: ', 'Die kommende Nacht im Kreis: '])
        if frost:
            orte_ = ', '.join(x[0] for x in frost[:3])
            s_ += 'Frost gibt es vor allem in %s. Am kältesten wird es in %s mit %s Grad.' % (orte_, kalt[0], zahl(kalt[1]))
        else:
            s_ += 'Am kältesten wird es in %s mit %s Grad, am mildesten bleibt es in %s mit %s Grad.' % (kalt[0], zahl(kalt[1]), warm[0], zahl(warm[1]))
        return s_
    if warm[1] == kalt[1]:
        return rnd.choice(['Und das gilt ziemlich genau für den ganzen Kreis – überall um die %s Grad.',
                           'Im ganzen Odenwaldkreis sieht es ähnlich aus: überall rund %s Grad.']) % zahl(warm[1])
    return rnd.choice(['Und so verteilt sich das über den Kreis: Am mildesten wird es in %s mit %s Grad, am kühlsten oben in %s mit %s Grad.',
                       'Schauen wir in den ganzen Kreis: %s liegt mit %s Grad vorn, %s bleibt mit %s Grad am kühlsten.',
                       'Im Kreis verteilt sich das so: In %s sind %s Grad drin, in %s nur %s Grad.']) % (warm[0], zahl(warm[1]), kalt[0], zahl(kalt[1]))


def skript_abend(days, warn, heute, orte=None):
    """Abendvideo (Studio): Rückblick auf heute, Ausblick auf morgen/übermorgen (freitags aufs Wochenende)."""
    rnd = random.Random('abend' + heute.isoformat())
    a = days[0]
    wochenende = heute.weekday() == 4   # Freitag
    paar = days[1:3]
    seg = [dict(art='intro', bg='studio', tafel_img=tafel_text('GUTEN ABEND', ['%s, %d. %s' % (TAGE[heute.weekday()], heute.day, MONATE[heute.month - 1]), '• Der Tag in Zahlen', '• Das Wochenende' if wochenende else '• Morgen und übermorgen'], (40, 30, 100)), text=rnd.choice(
        ['Guten Abend, Odenwald! Euer Max meldet sich aus dem Studio.',
         'Ei gude wie, Odenwald – hier ist euer Abendwetter mit Max.',
         'Schön, dass ihr einschaltet: Max hier mit dem Odenwald-Wetter am Abend.'])
        + ((' Vorweg: Vom Deutschen Wetterdienst gilt %s.' % ' und '.join(warn[:2])) if warn else ''))]
    zahlen = [rnd.choice(['Der Tag bei uns in Zahlen: Heute haben wir in den Tälern rund %s Grad erreicht.',
                          'Schauen wir noch mal auf den Tag: Bis zu %s Grad waren es heute bei uns im Odenwald.',
                          'Kurz zu den Zahlen von heute: Rund %s Grad Höchstwert in den Tälern.']) % zahl(a['tmax'])]
    if a.get('frost_min', a['tmin']) <= 0:
        zahlen.append('Heute Nacht wird es noch mal frostig, bis %s Grad.' % zahl(a.get('frost_min', a['tmin'])))
    elif a['tmin'] <= 3:
        zahlen.append('Heute Nacht kühlt es auf etwa %s Grad ab.' % zahl(a['tmin']))
    if a.get('regen', 0) >= 1:
        zahlen.append('Dazu kamen etwa %s Liter Regen pro Quadratmeter zusammen.' % zahl(round(a['regen'])))
    seg.append(dict(art='tag', bg='studio', titel='DER TAG IN ZAHLEN',
                    tafel_img=tafel_text('DER TAG IN ZAHLEN', zahlen, (25, 85, 160)),
                    text=' '.join(zahlen)))
    if wochenende:
        seg.append(dict(art='wochenende', bg='studio', tage=paar, tafel_img=tafel_wochenende(paar),
                        text='Und jetzt der Blick aufs Wochenende: ' + tagtext(paar[0], 'Samstag') + ' ' + tagtext(paar[1], 'Sonntag')))
    else:
        seg.append(dict(art='tag', bg='studio', titel='MORGEN', tag=paar[0], grafiken=(['regen'] if paar[0]['rp'] >= 30 else []),
                        tafel_img=tafel_tag('MORGEN', paar[0]), text=tagtext(paar[0], 'Morgen') + grafik_saetze(paar[0], (['regen'] if paar[0]['rp'] >= 30 else []), rnd, 'morgen')))
        kt = karten_txt(orte or {}, 1, rnd)
        if kt:   # Reliefkarte des Kreises: die Orte erscheinen nacheinander, während Max spricht
            seg.append(dict(art='tag', bg='studio', titel='MORGEN IM KREIS',
                            tafel_seq=karten_folge(orte, 1), text=kt))
        seg.append(dict(art='tag', bg='studio', titel='ÜBERMORGEN', tag=paar[1],
                        tafel_img=tafel_tag('ÜBERMORGEN', paar[1]), text='Und übermorgen: ' + tagtext(paar[1], 'Dann')))
    nacht_frost = any((orte or {}).get(n) and len((orte or {})[n]) > 1 and ((orte or {})[n][1] or {}).get('tmin_kalt', 99) <= 0 for n, *_ in ORTE_KARTE)
    if nacht_frost:   # Nachtkarte nur, wenn irgendwo im Kreis Frost ansteht
        nt = karten_txt(orte or {}, 1, rnd, nacht=True)
        if nt: seg.append(dict(art='tag', bg='studio', titel='HEUTE NACHT', tafel_seq=karten_folge(orte, 1, nacht=True), text=nt))
    seg.append(dict(art='outro', bg='studio', text=rnd.choice(['Das war euer Odenwald-Wetter am Abend.', 'So viel für heute aus dem Studio.', 'Das war es für heute von mir.'])
                    + ' Kommt gut durch die Nacht – bis morgen früh beim Wettervideo! Alle Live-Werte gibt es auf wetter-badkoenig.de.'))
    return seg


def special_grund(days, warn):
    a = days[0]; g = []
    if warn: g.append('warn')
    if wort(a['code']) == 'Schnee' or a['schnee'] >= 1 or wort(days[1]['code']) == 'Schnee': g.append('schnee')
    if a['boe'] >= 60: g.append('sturm')
    if a['tmin'] <= -5: g.append('kaelte')
    if a['tmax'] >= 30: g.append('hitze')
    if a['regen'] >= 20: g.append('regen')
    if wort(a['code']) == 'Gewitter': g.append('gewitter')
    return g


# --- Max' Persönlichkeit: Wettersprecher aus dem Odenwald, freundlich und bodenständig,
#     mag Tee, Therme und Glühwein lieber als Kälte ---
def max_privat(d, rnd, heute):
    """Kleine persönliche Bemerkung – nur an etwa jedem dritten Tag."""
    if rnd.random() > 0.35: return ''
    w = wort(d['code'])
    nass = w in ('Regen', 'Nieselregen', 'Schauer', 'Gewitter') or nass_tag(d)
    if w == 'Schnee' or d['schnee'] >= 1:
        opt = ['Ich geb’s zu: Beim Schnee freu ich mich jedes Jahr wie ein Kind.',
               'Den Schlitten hab ich schon mal aus dem Keller geholt – man weiß ja nie.']
    elif nass:
        opt = ['Ich verrate euch was: Bei so einem Wetter sitz ich am liebsten mit einem guten Buch auf dem Sofa.',
               'Regenschirm nicht vergessen – ich spreche da aus Erfahrung.',
               'Bei Regen ist mein Lieblingsplatz das warme Becken in der Therme. Vielleicht sieht man sich!']
    elif d['code'] in (45, 48, 3):
        opt = ['Bei so grauem Wetter hilft nur eins: eine Tasse heißer Tee.',
               'Ich mag Nebel ja irgendwie. Im Wald am Limes wirkt dann alles ein bisschen geheimnisvoll.',
               'Ganz ehrlich: An so einem grauen Tag darf man sich auch mal einfach eine Decke schnappen.']
    elif d['tmax'] <= 4:
        opt = ['Ganz ehrlich: Bei der Kälte ist mir ein heißer Glühwein lieber als alles andere.',
               'Ich hab heute Morgen extra die dicken Socken rausgeholt.']
    else:
        opt = ['Bei so einem Wetter freu ich mich jetzt schon auf den Feierabend.',
               'Ich sag’s ja immer: Wetter gibt’s überall – aber so eine Aussicht wie im Odenwald nicht.',
               'So ein Tag ist doch genau richtig, um den Odenwald einfach mal zu genießen.']
    return ' ' + rnd.choice(opt)


FRAGE = ['']        # Frage des Tages an die Zuschauer (geht auch in den Facebook-Text)
WEIHNACHT = [False]   # wird in baue() für 23.11.–28.12. gesetzt


def weihnachtszeit(heute): return (heute.month == 11 and heute.day >= 23) or (heute.month == 12 and heute.day <= 28)


def advent_gruss(heute, rnd):
    """Weihnachtlicher Gruß am Ende (nur 23.11.–28.12.)."""
    if not weihnachtszeit(heute): return ''
    if heute.month == 12 and heute.day == 24: return ' Und euch allen einen frohen Heiligabend!'
    if heute.month == 12 and heute.day in (25, 26): return ' Frohe Weihnachten, Odenwald!'
    w4 = dt.date(heute.year, 12, 24) - dt.timedelta(days=(dt.date(heute.year, 12, 24).weekday() + 1) % 7)   # 4. Advent = Sonntag vor dem 25.12.
    for n in range(4):
        if heute == w4 - dt.timedelta(weeks=3 - n): return ' Und euch allen einen schönen %d. Advent!' % (n + 1)
    if heute.month == 12 and heute.day >= 27: return ''
    return rnd.choice(['', ' Eine schöne Adventszeit!', '']) if heute.month == 12 or heute.day >= 27 else ''


def abschied(d, rnd):
    w = wort(d['code'])
    if w == 'Gewitter' or d['boe'] >= 60:
        return 'Heute lieber drinnen bleiben – passt auf euch auf!'
    if w == 'Schnee' or d['schnee'] >= 1:
        return 'Warm einpacken, vorsichtig fahren – und viel Spaß im Schnee!'
    if w in ('Regen', 'Nieselregen', 'Schauer') or nass_tag(d):
        return rnd.choice(['Macht es euch heute gemütlich – der Odenwald läuft nicht weg!',
                           'Tee kochen, Füße hoch – das nächste schöne Wetter kommt bestimmt!'])
    if d['code'] in (45, 48):
        return rnd.choice(['Licht an im Nebel, fahrt vorsichtig – und macht es euch gemütlich!',
                           'Warm einpacken und vorsichtig fahren – bis morgen!'])
    if d['code'] == 3:
        return rnd.choice(['Auch ein grauer Tag kann schön werden – macht was draus!', 'Jacke an und los – bis morgen!'])
    if d['tmax'] <= 3:
        return 'Dick einpacken – und dann raus an die frische Luft!'
    return rnd.choice(['Genießt den Tag – bis morgen!', 'Macht was draus – bis morgen!'])


def lage_fx(d):
    """Wetterlage für Hintergrund-Effekte: schnee, gewitter, sturm, regen oder None."""
    if not d: return None
    w = wort(d['code'])
    if w == 'Schnee' or d['schnee'] >= 1: return 'schnee'
    if w == 'Gewitter': return 'gewitter'
    if d['boe'] >= 55: return 'sturm'
    if w in ('Regen', 'Nieselregen') or d['regen'] >= 5: return 'regen'
    if w == 'Schauer' or nass_tag(d): return 'schauer'    # nur zeitweise Schauer: Sonne + Schauer in der Ferne
    return None


def special_fx(sp, warn, a):
    """Wetterlage fürs ganze Special-Video – aus DWD-Warnung oder Special-Grund."""
    t = ' '.join(warn).upper()
    for wort_, fx in (('GEWITTER', 'gewitter'), ('SCHNEE', 'schnee'), ('GLATTEIS', 'frost'), ('GLÄTTE', 'frost'),
                      ('FROST', 'frost'), ('NEBEL', 'nebel'), ('ORKAN', 'sturm'), ('STURM', 'sturm'), ('WIND', 'sturm'),
                      ('STARKREGEN', 'regen'), ('DAUERREGEN', 'regen'), ('TAUWETTER', 'regen'), ('HITZE', None)):
        if wort_ in t: return fx
    if warn: return None   # andere Warnung: keine Wetter-Effekte raten
    for g in sp:
        if g in ('schnee', 'gewitter', 'sturm', 'regen'): return g
        if g == 'kaelte': return 'frost'
        if g == 'hitze': return None
    return lage_fx(a)


WISSEN = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'wetterwissen.json')


def wetterwissen(a, heute, rnd):
    """„Wetter-Wissen in 20 Sekunden“: Mo, Mi, Fr, Sa ein Fun-Fact passend zu Wetter und Jahreszeit (Wiederholung frühestens nach ~30 Tagen)."""
    if heute.weekday() not in (0, 2, 4, 5): return None
    try: L = json.load(open(WISSEN, encoding='utf-8'))
    except Exception: return None
    w = wort(a['code']); m = heute.month
    kat = []
    if a['code'] in (45, 48): kat.append('nebel')
    if w == 'Schnee' or a.get('schnee', 0) >= 1: kat.append('schnee')
    if w == 'Gewitter': kat.append('gewitter')
    if a.get('boe', 0) >= 50: kat.append('sturm')
    if a['tmin'] <= 0: kat.append('frost')
    if w in ('Regen', 'Nieselregen', 'Schauer') or nass_tag(a): kat.append('regen')
    if w in ('sonnig', 'heiter bis wolkig'): kat.append('sonne')
    kat.append({12: 'winter', 1: 'winter', 2: 'winter', 3: 'fruehling', 4: 'fruehling', 5: 'fruehling', 6: 'sommer', 7: 'sommer', 8: 'sommer'}.get(m, 'herbst'))
    kat += ['wolken', 'allgemein']
    for k in kat:
        kand = [x for x in L if x['k'] == k]
        if not kand: continue
        frei = [x for x in kand if _schluessel(x['s']) not in {e['k'] for e in TIPP_LOG if e['d'] >= (dt.date.today() - dt.timedelta(days=30)).isoformat()}]
        if frei:
            x = rnd.choice(frei); TIPP_LOG.append(dict(d=dt.date.today().isoformat(), k=_schluessel(x['s'])))
            return x
    return None


def skript(days, warn, heute, nur_special=False):
    rnd = random.Random(heute.isoformat())
    a, b = days[0], days[1]
    seg = []
    gruss = rnd.choice(['Ei gude, Odenwald! Hier ist euer Max.', 'Guten Morgen, Odenwald! Hier ist Max mit eurem Wetter.',
                        'Ei gude wie, Odenwald? Max hier, mit dem Wetter für heute.', 'Guten Morgen aus dem Mümlingtal – hier ist euer Max.'])
    sp = special_grund(days, warn)
    if nur_special:   # eigenes Special-Video (mittags/nachmittags bei neuer Warnung)
        if warn:
            t = 'Achtung, Wetter-Special! Der Deutsche Wetterdienst warnt: %s.' % '. '.join(warn[:2])
        elif 'schnee' in sp: t = 'Wetter-Special: Es wird winterlich im Odenwald – Schnee ist im Anmarsch!'
        elif 'sturm' in sp: t = 'Wetter-Special: Sturm über dem Odenwald – Böen bis %d Kilometer pro Stunde.' % round(a['boe'])
        elif 'kaelte' in sp: t = 'Wetter-Special: Strenger Frost! Heute Nacht bis %s Grad.' % zahl(a['tmin'])
        elif 'hitze' in sp: t = 'Wetter-Special: Hitze im Odenwald – bis %s Grad!' % zahl(a['tmax'])
        elif 'gewitter' in sp: t = 'Wetter-Special: Heute drohen Gewitter im Odenwald.'
        else: t = 'Wetter-Special: Heute fällt viel Regen, über %d Liter pro Quadratmeter.' % round(a['regen'])
        karte = ('DWD warnt: ' + '. '.join(warn[:2])) if warn else t.replace('Wetter-Special: ', '')
        seg.append(dict(art='special', karte=karte, bg='sturm' if sp and sp[0] in ('warn', 'sturm', 'gewitter', 'regen') else 'winter' if 'schnee' in sp else 'hoehen',
                        text=(gruss + ' ' if not nur_special else '') + t))
    else:
        hinweis = (' Kurz vorweg: Vom Deutschen Wetterdienst gilt %s. Passt auf euch auf!' % ' und '.join(('eine ' + w[0].lower() + w[1:]) if w.lower().startswith('amtliche') else w for w in warn[:2])) if warn else ''
        seg.append(dict(art='intro', bg='schloss', text=gruss + (' Für alle, die neu dabei sind: Ich bin Max, euer Wettersprecher für den Odenwald.' if heute.weekday() == 0 else '') + ' Das ist euer Odenwald-Wetter für %s.' % TAGE[heute.weekday()] + hinweis))
    if not nur_special and a.get('gestern'):
        seg.append(dict(art='rueckblick', bg='schloss', tafel_img=tafel_gestern(a['gestern'], heute - dt.timedelta(days=1)),
                        text=gestern_txt(a['gestern'], rnd)))
    seg.append(dict(art='tag', tag=a, titel='HEUTE', bg='auto', grafiken=(['regen'] if a['rp'] >= 30 else []) + (['wind'] if a.get('boe', 0) >= 45 else []),
                    text=reaktion(a, rnd) + frisch(rnd, 'ueberg_heute', ['', '', 'Kommen wir zum Wetter. ', 'So, jetzt zum Wetter. ', 'Und nun zum Tag. '])
                         + tagtext(a, 'Heute') + vergleich_gestern(a, rnd) + einordnung(a, rnd) + mundart(a, rnd) + fenster_txt(a, rnd) + grafik_saetze(a, (['regen'] if a['rp'] >= 30 else []) + (['wind'] if a.get('boe', 0) >= 45 else []), rnd)))
    seg.append(dict(art='tipp', tag=a, bg='wald' if not nass_tag(a) else 'schloss', text=frisch(rnd, 'ueberg_tipp', ['Mein Tipp für heute: ', 'Max-Tipp des Tages: ', 'Und jetzt mein Tipp: ', 'Übrigens, mein Tipp für heute: ',
                                                                               'Was könnt ihr heute machen? ', 'Und wenn ihr noch nichts vorhabt: ', 'Bevor ich’s vergesse – mein Tipp: ',
                                                                               'Noch was für eure Freizeit: ', 'Ihr sucht noch was für heute? ', 'Kleiner Tipp am Rande: ']) + tipp(a, rnd, heute) + max_privat(a, rnd, heute)))
    if not nur_special:
        seg.append(dict(art='tag', tag=b, titel='MORGEN', bg='hoehen', grafiken=[],
                        text=frisch(rnd, 'ueberg_morgen', ['', 'So, und jetzt der Blick nach vorn. ', 'Was bringt der nächste Tag? ', 'Schauen wir auf morgen. ',
                                                           'Und wie geht’s morgen weiter? ', 'Kurzer Blick nach vorn. ', 'Und dann? ', 'Werfen wir noch einen Blick auf morgen. '])
                             + tagtext(b, rnd.choice(['Morgen, am %s,', 'Am %s']) % TAGE[b['datum'].weekday()]) ))
        if 3 <= heute.weekday() <= 4 and len(days) >= 7:   # Wochenendwetter erst ab Donnerstag (vorher zu ungenau)
            sa = next(d for d in days if d['datum'].weekday() == 5)
            so = next(d for d in days if d['datum'].weekday() == 6)
            if sa['datum'] > b['datum'] or so['datum'] > b['datum']:
                nass = (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99)
                gut = [n for n, d in (('Samstag', sa), ('Sonntag', so)) if not nass_tag(d) and d['code'] not in nass]
                grau = any(d['code'] in (45, 48) or d['code'] == 3 for d in (sa, so))
                t = '%s Im Odenwald Samstag %s bei %s Grad, Sonntag %s bei %s Grad.' % (rnd.choice(['Ein Blick aufs Wochenende:', 'Und das Wochenende?', 'Kurz noch zum Wochenende:']), wort(sa['code']), zahl(sa['tmax']), wort(so['code']), zahl(so['tmax']))
                t += (' Trockener bleibt es am %s.' % gut[0]) if len(gut) == 1 else ((' Beide Tage bleiben wohl trocken – zieht euch aber warm an.' if grau else ' Beide Tage sehen gut aus für draußen!') if gut else ' Plant lieber etwas für drinnen ein.')
                seg.append(dict(art='wochenende', tage=[sa, so], bg='wald', text=t))
    if not nur_special:
        try:
            th = TERMINE.max_hinweis(heute, rnd)
            if th: seg[-1 if seg[-1]['art'] != 'wochenende' else -1]['text'] += ' ' + th
        except Exception as e: print('Termine nicht möglich:', e)
    if not nur_special:
        try:
            ww = wetterwissen(a, heute, rnd)
            if ww: seg.append(dict(art='wissen', bg='wald', titel_w=ww['t'], text=rnd.choice(['Und jetzt: Wetter-Wissen in 20 Sekunden! ', 'Zum Schluss noch Wetter-Wissen in 20 Sekunden: ', 'Wetter-Wissen in 20 Sekunden: ']) + ww['s']))
        except Exception as e: print('Wetter-Wissen nicht möglich:', e)
    hm = himmel_txt(a, rnd) if not nur_special else ''
    if not nur_special:   # Frage an die Zuschauer (Interaktion auf Facebook/Instagram)
        FRAGE[0] = frage_fuer(a, heute, rnd)
        seg.append(dict(art='frage', bg='schloss', frage=FRAGE[0], text=FRAGE[0]))
        seg.append(dict(art='cta', bg='schloss', text=folgen_fuer(heute, rnd, bool(warn))))   # Aufruf zum Folgen
    seg.append(dict(art='outro', bg='schloss', text=hm + rnd.choice(['Alle Live-Werte findet ihr auf wetter-badkoenig.de.', 'Mehr gibt es live auf wetter-badkoenig.de.',
                                                       'Die aktuellen Werte von meiner Station gibt es jederzeit auf wetter-badkoenig.de.', 'Schaut gern mal rein auf wetter-badkoenig.de.'])
                       + ' ' + abschied(a, rnd) + advent_gruss(heute, rnd)))
    # Wetter-Effekte: Tages-Tafeln zeigen das Wetter ihres Tages, im Special das ganze Video
    gfx = special_fx(sp, warn, a) if nur_special else None
    for x in seg:
        if gfx: x['fx'] = gfx
        elif x['art'] == 'tag': x['fx'] = lage_fx(x['tag'])
    return seg


def verlauf(w, h, oben, unten):
    a = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(oben)[None, None, :] * (1 - a) + np.array(unten)[None, None, :] * a
    return Image.fromarray(np.repeat(arr, w, axis=1).astype('uint8'))


def huegel(dr, w, y, amp, col, seed, step=6):
    r = random.Random(seed); ph = [r.uniform(0, 6) for _ in range(3)]
    pts = [(0, 99999)]
    for x in range(0, w + step, step):
        pts.append((x, y + amp * (0.5 * math.sin(x / 170 + ph[0]) + 0.3 * math.sin(x / 70 + ph[1]) + 0.2 * math.sin(x / 33 + ph[2]))))
    pts.append((w, 99999))
    dr.polygon(pts, fill=col)
    return pts


def tanne(dr, x, y, h, col):
    for k in range(3):
        t = y - h * (0.25 + k * 0.25)
        dr.polygon([(x, t - h * 0.35), (x - h * (0.32 - k * 0.07), t + h * 0.12), (x + h * (0.32 - k * 0.07), t + h * 0.12)], fill=col, outline=(30, 50, 35))
    dr.rectangle([x - h * 0.04, y - h * 0.25, x + h * 0.04, y], fill=(90, 60, 40))


def bg_landschaft(art_, seed):
    BW, BH = 1000, 1500
    frost = art_ == 'frost'
    if frost: art_ = 'winter'   # Raureif-Landschaft wie Winter, aber ohne Schneeflocken
    if art_ == 'sturm': im = verlauf(BW, BH, (70, 80, 100), (150, 160, 175))
    elif art_ == 'regen': im = verlauf(BW, BH, (105, 115, 130), (175, 185, 195))
    elif art_ == 'gewitter': im = verlauf(BW, BH, (35, 35, 55), (95, 90, 110))
    elif art_ == 'winter': im = verlauf(BW, BH, (150, 185, 225), (235, 242, 250))
    else: im = verlauf(BW, BH, (70, 150, 225), (250, 215, 165))
    dr = ImageDraw.Draw(im)
    r = random.Random(seed)
    if art_ in ('regen', 'gewitter', 'sturm'):   # dicke Wolkenbänke
        wc = {'regen': (135, 140, 150), 'gewitter': (55, 55, 75), 'sturm': (95, 100, 115)}[art_]
        for _ in range(28):
            x, y, rr = r.uniform(-100, BW + 100), r.uniform(-60, 420), r.uniform(90, 190)
            dr.ellipse([x - rr * 1.6, y - rr * 0.6, x + rr * 1.6, y + rr * 0.6], fill=tuple(max(0, v + r.randint(-12, 12)) for v in wc))
    if art_ not in ('sturm', 'regen', 'gewitter'):
        dr.ellipse([680, 230, 860, 410], fill=(255, 225, 120))
    farben = {'wald': [(120, 160, 140), (80, 130, 90), (50, 105, 70), (35, 80, 55)],
              'hoehen': [(150, 170, 200), (115, 150, 170), (85, 125, 120), (60, 100, 80)],
              'sturm': [(100, 110, 125), (80, 95, 100), (60, 80, 75), (45, 65, 55)],
              'regen': [(125, 135, 145), (95, 115, 110), (70, 100, 85), (55, 85, 65)],
              'gewitter': [(70, 70, 90), (55, 65, 70), (45, 60, 55), (35, 50, 45)],
              'winter': [(205, 215, 230), (225, 232, 242), (240, 244, 250), (250, 252, 255)]}[art_]
    for k, c in enumerate(farben):
        y = 700 + k * 170
        huegel(dr, BW, y, 60 + k * 25, c, seed * 10 + k)
        if k >= 1 and art_ != 'hoehen' or k >= 2:
            for _ in range(10 + k * 6):
                x = r.uniform(0, BW)
                tanne(dr, x, y + 80 + r.uniform(-10, 30), 40 + k * 35, tuple(max(0, v - 25) for v in c) if art_ != 'winter' else (70, 110, 90))
        if k == 2 and art_ == 'wald':  # die Mümling
            dr.polygon([(0, y + 150), (BW, y + 110), (BW, y + 160), (0, y + 215)], fill=(120, 180, 215))
        if k == 1 and art_ == 'hoehen':  # Aussichtsturm auf der Höhe
            x0 = 760
            dr.rectangle([x0, y - 150, x0 + 26, y + 10], fill=(110, 95, 85), outline=(40, 30, 25), width=3)
            dr.polygon([(x0 - 12, y - 150), (x0 + 13, y - 190), (x0 + 38, y - 150)], fill=(160, 70, 50), outline=(40, 30, 25))
    if art_ == 'winter' and not frost:
        for _ in range(250):
            x, y = r.uniform(0, BW), r.uniform(0, BH); s = r.uniform(2, 5)
            dr.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255))
    return im.filter(ImageFilter.SMOOTH)


def laubbaum(dr, x, y, h, krone, r):
    dr.rectangle([x - h * 0.05, y - h * 0.45, x + h * 0.05, y], fill=(85, 60, 40))
    for _ in range(6):
        dx, dy, rr = r.uniform(-0.28, 0.28) * h, r.uniform(-0.75, -0.45) * h, r.uniform(0.18, 0.28) * h
        c = tuple(max(0, min(255, v + r.randint(-18, 18))) for v in krone)
        dr.ellipse([x + dx - rr, y + dy - rr, x + dx + rr, y + dy + rr], fill=c)


def haus(dr, x, y, w, dach=(170, 70, 50), wand=(240, 230, 210), licht=False):
    h = w * 0.7
    dr.rectangle([x, y - h, x + w, y], fill=wand, outline=(60, 45, 35), width=2)
    dr.polygon([(x - w * 0.1, y - h), (x + w / 2, y - h - w * 0.55), (x + w * 1.1, y - h)], fill=dach, outline=(60, 40, 30))
    for fx in (0.2, 0.6):
        dr.rectangle([x + w * fx, y - h * 0.7, x + w * (fx + 0.18), y - h * 0.4], fill=(255, 205, 110) if licht else (110, 130, 150))


def bg_land(art_, seed):
    """Gemalte Mümlingtal-Ansicht aus der Fantasie: bewaldete Höhenzüge, Wiesen mit Streuobst, die Mümling im Talgrund,
    ein Städtchen mit roten Dächern und spitzem Kirchturm, vorn ein Feld. Je nach Jahreszeit/Stimmung andere Farben."""
    BW, BH = 1000, 1500
    r = random.Random(seed * 7 + len(art_))
    P = {  # himmel oben/unten, ferne Höhe, nahe Höhe, Waldtupfer, Wiese, Feld vorn, Obstbaum, Dach, Wand, Wasser
        'fruehling': ((120, 170, 225), (225, 235, 240), (120, 150, 165), (60, 105, 70), (95, 150, 80), (150, 195, 95), (140, 190, 70), (245, 235, 240), (200, 90, 55), (240, 232, 215), (150, 190, 215)),
        'sommer':    ((90, 145, 215), (235, 235, 220), (105, 130, 145), (45, 85, 55), (70, 125, 60), (135, 175, 75), (195, 185, 90), (85, 140, 60), (205, 95, 55), (240, 232, 215), (140, 180, 205)),
        'herbst':    ((130, 160, 200), (240, 220, 185), (135, 140, 150), (90, 95, 60), (185, 120, 50), (140, 160, 80), (150, 125, 70), (210, 140, 50), (190, 85, 50), (235, 225, 205), (150, 175, 195)),
        'abend':     ((70, 75, 135), (250, 170, 110), (105, 90, 125), (55, 55, 75), (85, 75, 80), (95, 95, 70), (110, 95, 60), (70, 75, 55), (150, 80, 60), (230, 190, 150), (230, 160, 120)),
        'nebel':     ((190, 195, 202), (226, 229, 233), (170, 176, 184), (120, 135, 130), (115, 130, 120), (150, 165, 140), (140, 150, 120), (120, 135, 115), (170, 110, 90), (225, 222, 215), (190, 200, 205)),
        'dorfwinter':((150, 175, 210), (232, 238, 246), (175, 190, 210), (80, 100, 95), (110, 115, 110), (236, 240, 247), (240, 243, 249), (130, 120, 110), (175, 120, 110), (238, 232, 222), (170, 190, 205)),
    }[art_]
    h_o, h_u, ferne, nahe, wald, wiese, feld, obst, dach, wand, wasser = P
    im = verlauf(BW, BH, h_o, h_u); dr = ImageDraw.Draw(im)
    def var(c, d=14): return tuple(max(0, min(255, v + r.randint(-d, d))) for v in c)
    # Sonne / Wolken (weich)
    ov = Image.new('RGBA', (BW, BH)); od = ImageDraw.Draw(ov)
    if art_ == 'abend': od.ellipse([620, 470, 760, 610], fill=(255, 200, 120, 255))
    for _ in range(0 if art_ == 'nebel' else 6):   # Haufenwolken aus vielen Bällchen, flacher Boden
        cx_, cy_, w_ = r.uniform(-50, BW), r.uniform(90, 420), r.uniform(160, 320)
        for _ in range(14):
            bx = cx_ + r.uniform(-w_ / 2, w_ / 2); br = r.uniform(25, 55) * (1 - abs(bx - cx_) / w_)
            od.ellipse([bx - br, cy_ - br * 1.3, bx + br, cy_ + br * 0.3], fill=(255, 250, 245, 200) if art_ != 'abend' else (255, 175, 140, 190))
    im = Image.alpha_composite(im.convert('RGBA'), ov.filter(ImageFilter.GaussianBlur(6))).convert('RGB'); dr = ImageDraw.Draw(im)
    def kamm(y, amp, f, ph):
        return [(x, y + amp * (0.6 * math.sin(x / f + ph) + 0.4 * math.sin(x / (f * 0.37) + ph * 2))) for x in range(0, BW + 10, 10)]
    # zwei bewaldete Höhenzüge (hinten bläulich, vorn dunkelgrün) mit Baumtupfern
    for k, (y, amp, col) in enumerate(((610, 45, ferne), (690, 55, nahe))):
        pts = kamm(y, amp, 260 + k * 60, r.uniform(0, 6))
        dr.polygon([(0, BH)] + pts + [(BW, BH)], fill=col)
        for _ in range(1400 if k else 700):
            x = r.uniform(0, BW); i = min(len(pts) - 1, int(x / 10)); yt = pts[i][1]
            yy = r.uniform(yt + 4, yt + 190); rr = r.uniform(4, 9) * (1 + k * 0.4)
            c = var(col if not k else wald, 18)
            if art_ == 'herbst' and k and r.random() < 0.35: c = var((90, 105, 60), 15)   # Tannen zwischen buntem Laub
            if art_ == 'dorfwinter': c = var((215, 222, 232), 10) if r.random() < 0.55 else var((85, 100, 95), 12)
            dr.ellipse([x - rr, yy - rr * 0.8, x + rr, yy + rr * 0.8], fill=c)
    # Talgrund: Wiesen und Felder
    tal = kamm(860, 18, 300, r.uniform(0, 6))
    dr.polygon([(0, BH)] + tal + [(BW, BH)], fill=wiese)
    for _ in range(14):
        x, y = r.uniform(-60, BW), r.uniform(850, 1000); w_ = r.uniform(120, 260)
        dr.polygon([(x, y), (x + w_, y - 10), (x + w_ + 40, y + 45), (x + 25, y + 55)], fill=var(wiese, 22 if art_ != 'dorfwinter' else 4))
    # die Mümling: schlängelt sich durch den Talgrund, mit Ufergehölz
    fl = [(x, 985 + 22 * math.sin(x / 120 + 1.3) + 10 * math.sin(x / 47)) for x in range(-20, BW + 30, 15)]
    dr.line(fl, fill=wasser, width=14, joint='curve')
    dr.line([(x, y - 3) for x, y in fl], fill=tuple(min(255, v + 35) for v in wasser), width=3)
    for x, y in fl[::2]:
        if r.random() < 0.55:
            rr = r.uniform(8, 15); dr.ellipse([x - rr, y - 18 - rr, x + rr, y - 18 + rr * 0.8], fill=var(wald, 15) if art_ != 'dorfwinter' else var((120, 110, 100), 10))
    # Städtchen mit roten Dächern und Kirchturm
    cx = r.uniform(330, 620); haeuser = []
    for _ in range(140):
        x = r.gauss(cx, 150); y = r.gauss(930, 26)
        if 0 < x < BW: haeuser.append((y, x))
    haeuser.sort()
    for y, x in haeuser:
        w_ = r.uniform(14, 24); h_ = w_ * 0.55
        dr.rectangle([x, y - h_, x + w_, y], fill=var(wand, 10))
        dr.polygon([(x - 2, y - h_), (x + w_ / 2, y - h_ - w_ * 0.45), (x + w_ + 2, y - h_)], fill=var(dach if art_ != 'dorfwinter' else (240, 243, 248), 18))
        if art_ in ('abend', 'dorfwinter') and r.random() < 0.6: dr.rectangle([x + w_ * 0.3, y - h_ * 0.7, x + w_ * 0.5, y - h_ * 0.35], fill=(255, 205, 110))
        if r.random() < 0.18:
            rr = r.uniform(6, 11); dr.ellipse([x - rr, y - rr * 1.6, x + rr, y], fill=var(wald, 15) if art_ != 'dorfwinter' else var((120, 110, 100), 10))
    ky = 935
    dr.rectangle([cx, ky - 95, cx + 22, ky], fill=var(wand, 6), outline=(80, 65, 55))
    dr.polygon([(cx - 2, ky - 95), (cx + 11, ky - 190), (cx + 24, ky - 95)], fill=(55, 60, 75))
    dr.rectangle([cx - 50, ky - 38, cx, ky], fill=var(wand, 6)); dr.polygon([(cx - 54, ky - 38), (cx - 25, ky - 62), (cx + 4, ky - 38)], fill=var(dach, 8))
    # Streuobstwiese am Hang vorn
    hang = kamm(1090, 30, 340, r.uniform(0, 6))
    dr.polygon([(0, BH)] + hang + [(BW, BH)], fill=feld)
    for _ in range(9):
        x = r.choice((r.uniform(10, 330), r.uniform(650, 990))); i = min(len(hang) - 1, int(x / 10)); y = hang[i][1] + r.uniform(10, 60)
        hh = r.uniform(70, 120)
        dr.line([(x, y), (x, y - hh * 0.5)], fill=(90, 65, 45), width=6)
        for _ in range(9 if art_ != 'dorfwinter' else 0):
            rr = r.uniform(14, 26); dx, dy = r.uniform(-30, 30), r.uniform(-hh, -hh * 0.45)
            dr.ellipse([x + dx - rr, y + dy - rr, x + dx + rr, y + dy + rr], fill=var(obst, 20))
        if art_ == 'dorfwinter':
            for a_ in (-1, 1): dr.line([(x, y - hh * 0.45), (x + a_ * 30, y - hh * 0.9)], fill=(95, 80, 70), width=4)
    for _ in range(2600):   # Pinselstriche im Feld
        x, y = r.uniform(0, BW), r.uniform(1110, BH); l = r.uniform(8, 22)
        dr.line([(x, y), (x + r.uniform(-3, 3), y - l)], fill=var(feld, 22), width=2)
    if art_ == 'nebel':
        ov = Image.new('RGBA', (BW, BH)); od = ImageDraw.Draw(ov)
        for _ in range(16):
            x, y, w_ = r.uniform(-250, BW), r.uniform(700, 1060), r.uniform(350, 750)
            od.ellipse([x, y, x + w_, y + r.uniform(50, 120)], fill=(238, 240, 244, 185))
        im = Image.alpha_composite(im.convert('RGBA'), ov.filter(ImageFilter.GaussianBlur(40))).convert('RGB'); dr = ImageDraw.Draw(im)
    if art_ == 'dorfwinter':
        for _ in range(200):
            x, y = r.uniform(0, BW), r.uniform(0, BH); s_ = r.uniform(1.5, 4)
            dr.ellipse([x - s_, y - s_, x + s_, y + s_], fill=(255, 255, 255))
    # leicht gemalter Look: weichzeichnen + feines Korn
    im = im.filter(ImageFilter.GaussianBlur(1.1))
    arr = np.asarray(im).astype('int16') + np.random.RandomState(seed % 1000).randint(-7, 8, (BH, BW, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype('uint8'))


LAND_SAISON = {'fruehling': (3, 4, 5), 'sommer': (6, 7, 8), 'herbst': (9, 10, 11), 'dorfwinter': (12, 1, 2), 'abend': tuple(range(1, 13))}

# Studio fürs Abendvideo: Holzvertäfelung, Fenster mit Blick auf Schloss/Wald, Bildschirm für die Vorhersagekarte.
# Bildraum 1000x1500, Bildschirmfläche fix (siehe STUDIO_SCREEN) – wird beim Rendern auf Bildschirmkoordinaten umgerechnet.
STUDIO_SCREEN = (530, 190, 890, 700)
STUDIO_TISCH = 905   # Oberkante des Tisches im fertigen Bild (720x1280)


def bg_studio(seed):
    BW, BH = 1000, 1500
    r = random.Random(seed * 13 + 7)
    im = Image.new('RGB', (BW, BH), (107, 78, 52))
    dr = ImageDraw.Draw(im)
    for x in range(0, BW, 92):   # Holzvertäfelung
        dr.line([(x, 0), (x, 1500)], fill=(93, 66, 43), width=4)
    for y in range(0, 1100, 70):
        dr.line([(0, y), (BW, y)], fill=(118, 87, 58), width=1)
    # Fenster mit Blick auf Schloss Bad König und Wald
    fx0, fy0, fx1, fy1 = 90, 140, 430, 720
    dr.rectangle([fx0 - 18, fy0 - 18, fx1 + 18, fy1 + 18], fill=(78, 56, 36), outline=(50, 36, 22), width=6)
    sky = Image.new('RGB', (fx1 - fx0, fy1 - fy0), (160, 195, 220))
    sd = ImageDraw.Draw(sky)
    for yy in range(sky.height):
        t = yy / sky.height
        sd.line([(0, yy), (sky.width, yy)], fill=(int(140 + 40 * t), int(170 + 50 * t), int(205 + 30 * t)))
    for k, (hy, amp, col) in enumerate(((0.52, 22, (90, 110, 80)), (0.62, 28, (62, 86, 55)))):
        pts = [(x, int(sky.height * hy) + int(amp * math.sin(x / 55 + k))) for x in range(0, sky.width + 10, 10)]
        sd.polygon([(0, sky.height)] + pts + [(sky.width, sky.height)], fill=col)
    cx = sky.width * 0.46
    sd.rectangle([cx - 36, sky.height * 0.42, cx + 36, sky.height * 0.66], fill=(150, 140, 120))
    sd.polygon([(cx - 40, sky.height * 0.42), (cx, sky.height * 0.3), (cx + 40, sky.height * 0.42)], fill=(95, 70, 60))
    sd.rectangle([cx - 10, sky.height * 0.34, cx + 10, sky.height * 0.42], fill=(50, 38, 32))
    im.paste(sky, (fx0, fy0))
    dr.line([(fx0 + (fx1 - fx0) // 2, fy0), (fx0 + (fx1 - fx0) // 2, fy1)], fill=(78, 56, 36), width=10)
    dr.line([(fx0, fy0 + (fy1 - fy0) // 2), (fx1, fy0 + (fy1 - fy0) // 2)], fill=(78, 56, 36), width=10)
    # Bildschirm an der Wand (Inhalt kommt beim Rendern dazu)
    for _ in range(90):   # leichtes Korn, damit die Wand nicht zu glatt wirkt
        x, y = r.uniform(0, BW), r.uniform(760, 1100)
        dr.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(130, 98, 66))
    sx0, sy0, sx1, sy1 = STUDIO_SCREEN
    dr.rounded_rectangle([sx0 - 14, sy0 - 14, sx1 + 14, sy1 + 14], radius=10, fill=(30, 28, 26))
    dr.rectangle([sx0, sy0, sx1, sy1], fill=(24, 36, 48))
    return im.filter(ImageFilter.SMOOTH)


def studio_desk_overlay():
    """Holztisch im Vordergrund (Bildkoordinaten) – verdeckt Max' Beine, sodass er am Tisch zu sitzen scheint."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    top = STUDIO_TISCH
    dr.rectangle([0, top, W, top + 46], fill=(150, 108, 68, 255))                    # Tischplatte
    dr.rectangle([0, top + 46, W, top + 58], fill=(110, 78, 48, 255))                # Kante
    dr.rectangle([0, top + 58, W, H], fill=(74, 52, 34, 255))                        # Front
    for y in range(top + 90, H, 34):
        dr.line([(0, y), (W, y)], fill=(62, 44, 28, 255), width=2)
    dr.rounded_rectangle([430, top - 34, 500, top + 20], radius=8, fill=(240, 240, 235, 255), outline=(25, 30, 40, 255), width=4)   # Kaffeetasse
    dr.arc([488, top - 22, 522, top + 10], 270, 90, fill=(25, 30, 40, 255), width=5)
    dr.rounded_rectangle([560, top + 4, 690, top + 24], radius=4, fill=(235, 235, 240, 255), outline=(25, 30, 40, 255), width=3)    # Notizen
    dr.text((W / 2, top + 150), 'ODENWALD-WETTER', font=F(34), fill=(215, 180, 130, 255), anchor='mm')
    return im


# Eigene Bilder: Dateiname = Ort, optional _saison (_sommer, _herbst, _winter, _fruehling, _advent)
EIGEN_NAME = {}
ORT_WORTE = {'kurpark': ('Kurpark',), 'therme': ('Therme', 'Sauna', 'Salzgrotte', 'Thermalbad'), 'limesturm': ('Limesturm', 'Vielbrunn'),
             'wuerzberg': ('Würzberg', 'Römerbad', 'Kastellbad'), 'haselburg': ('Haselburg',), 'eulbach': ('Eulbach',),
             'erbach': ('Schloss Erbach', 'Erbach'), 'felsenmeer': ('Felsenmeer',), 'michelstadt': ('Michelstadt', 'Michelstädter'),
             'stausee': ('Stausee', 'Marbach'), 'viadukt': ('Viadukt',), 'christmas-lights': ('Christmas Lights', 'Wintermarkt'),
             'burg-breuberg': ('Breuberg',), 'burg-freienstein': ('Freienstein',),
             'schnee': ('Schlitten', 'Schnee', 'Winterwunderland'), 'nebel': ('Nebel', 'Grau in grau')}


def saison_ok(name, heute):
    m, t = heute.month, heute.day
    if name.endswith('_advent'): return (m == 11 and t >= 15) or m == 12 or (m == 1 and t <= 6)
    if name.endswith('_winter'): return m in (11, 12, 1, 2)
    if name.endswith('_herbst'): return m in (9, 10, 11)
    if name.endswith('_fruehling'): return m in (3, 4, 5)
    if name.endswith('_sommer'): return m in (5, 6, 7, 8, 9)
    return True


def bild_zum_text(text, kandidaten, n_=0):
    """Passendes Bild zum Text. Spezifischere Orte (Christmas Lights) vor allgemeinen (Kurpark); bei mehreren Bildern wird gewechselt."""
    for ort, worte in sorted(ORT_WORTE.items(), key=lambda x: x[0] != 'christmas-lights'):
        if any(w in text for w in worte):
            tr = [k for k in kandidaten if EIGEN_NAME.get(k, '').startswith(ort)]
            if tr: return tr[n_ % len(tr)]
    return None


def lichterkette(im, seed):
    """Advents-Look: Lichterketten quer übers Bild und leuchtende Punkte (auf Raureif- bzw. Schneelandschaft)."""
    im = im.copy(); dr = ImageDraw.Draw(im); r = random.Random(seed); W_, H_ = im.size
    farben = [(255, 210, 90), (255, 90, 80), (120, 220, 130), (110, 170, 255), (255, 240, 200)]
    for k, y0 in enumerate((70, 190)):
        pts = [(x, y0 + 45 * math.sin(math.pi * x / W_) + 10 * k) for x in range(0, W_ + 20, 20)]
        dr.line(pts, fill=(60, 70, 60), width=3)
        for i, (x, y) in enumerate(pts[1::2]):
            c = farben[(i + k) % len(farben)]
            dr.ellipse([x - 9, y + 4, x + 9, y + 24], fill=c, outline=(80, 80, 60))
    for _ in range(30):
        x, y = r.uniform(0, W_), r.uniform(H_ * 0.62, H_ * 0.85); c = r.choice(farben)
        dr.ellipse([x - 4, y - 4, x + 4, y + 4], fill=c)
    return im


def hintergruende(seed):
    bgs = {}
    sch = Image.open(os.path.join(ROOT, 'vorschau.jpg')).convert('RGB')
    s = 1500 / sch.height
    bgs['schloss'] = sch.resize((int(sch.width * s), 1500), Image.LANCZOS)
    for k in ('wald', 'hoehen', 'sturm', 'winter', 'frost', 'regen', 'gewitter'):
        bgs[k] = bg_landschaft(k, seed)
    for k in ('fruehling', 'sommer', 'herbst', 'abend', 'nebel', 'dorfwinter'):
        bgs['land_' + k] = bg_land(k, seed)
    bgs['studio'] = bg_studio(seed)
    if WEIHNACHT[0]:
        bgs['advent'] = lichterkette(bg_landschaft('frost', seed), seed)
        bgs['advent_schnee'] = lichterkette(bg_landschaft('winter', seed), seed + 1)
    eigene = sorted(glob.glob(os.path.join(ROOT, 'video', 'hintergruende', '*.[jp][pn]g')))
    for i, p in enumerate(eigene):  # eigene KI-Bilder ersetzen reihum die gezeichneten Landschaften
        try:
            im = Image.open(p).convert('RGB'); s = max(1000 / im.width, 1500 / im.height)
            bgs['eigen%d' % i] = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
            EIGEN_NAME['eigen%d' % i] = os.path.splitext(os.path.basename(p))[0].lower()
        except Exception as e:
            print('Bild übersprungen:', p, e)
    return bgs


# --- der Moderator ---
HAUT, HAAR, JACKE, JACKE2, HOSE, LINIE = (247, 205, 170), (95, 60, 35), (30, 130, 120), (240, 140, 40), (55, 65, 80), (25, 30, 40)


def look_fuer(d):
    """Kleidung nach Wetterlage: winter, regen, kuehl, normal, warm, sonne."""
    w = wort(d['code'])
    if w == 'Schnee' or d['schnee'] >= 1 or d['tmax'] <= 4: return 'winter'
    if w in ('Regen', 'Gewitter', 'Nieselregen', 'Schauer') or nass_tag(d): return 'regen'
    if d['tmax'] <= 11: return 'kuehl'
    if d['tmax'] >= 20: return 'sonne' if w in ('sonnig', 'heiter bis wolkig') else 'warm'
    return 'normal'


# Oberteil je Look: (Farbe Jacke/Shirt, Farbe Weste oder None, kurze Ärmel)
OUTFIT = {'winter': ((200, 45, 50), None, False),          # dicke rote Daunenjacke
          'regen': ((250, 200, 30), None, False),          # gelbe Regenjacke (Friesennerz)
          'kuehl': ((30, 130, 120), (60, 70, 85), False),  # Softshell mit dunkler Weste
          'normal': ((30, 130, 120), (60, 70, 85), False),     # Wettersprecher: Jacke mit dunkler Weste
          'sturm': ((30, 130, 120), (60, 70, 85), False),   # Softshell, Mütze ist weggeflogen
          'warm': ((70, 140, 200), None, True),            # blaues Funktions-Shirt
          'sonne': ((240, 140, 40), None, True)}           # oranges T-Shirt


def schippe(d, P, L):
    """Schneeschippe in der linken Hand (Stiel bis zum Boden, Schaufelblatt neben den Schuhen)."""
    d.line(P(118, 520, 100, 718), fill=LINIE, width=16 * 2)
    d.line(P(118, 520, 100, 718), fill=(150, 100, 55), width=10 * 2)
    d.rounded_rectangle(P(100, 500, 140, 516), radius=6 * 2, fill=(40, 40, 45), outline=LINIE, width=L)   # Griff
    d.polygon(P(52, 712, 148, 712, 140, 758, 60, 758), fill=(30, 110, 200), outline=LINIE)                # Blatt
    d.line(P(58, 738, 142, 738), fill=(250, 250, 255), width=8 * 2)                                       # Schnee drauf


def schirm(d, P, L):
    """Roter Regenschirm über dem Kopf, Griff in der linken Hand."""
    d.line(P(118, 530, 112, 90), fill=LINIE, width=10 * 2)
    d.chord(P(-8, 4, 262, 176), 180, 360, fill=(200, 40, 50), outline=LINIE, width=L)
    for x in (32, 77, 127, 172, 217): d.line(P(127, 6, x, 88), fill=(150, 25, 35), width=3 * 2)


# ---------------------------------------------------------------------
#  Max in Ebenen: Beine, Oberkörper (beide Arme), Kopf (Mundformen, Mimik, Augen),
#  Schal mit schwingendem Ende, Mützenzipfel/Bommel und Requisiten.
#  MaxFigur setzt die Ebenen Bild für Bild zusammen, MaxAnimation steuert die Bewegung.
# ---------------------------------------------------------------------
SCHULTER_R, SCHULTER_L = (262, 330), (118, 330)
POSEN = {   # rechter Arm: Ellbogen (x, y), Hand (x, y) in Grundkoordinaten
    'haengt': (288, 450, 261, 533),
    'zeigt': (320, 270, 355, 181),
    'daumen': (300, 430, 311, 375),
    'winkt': (318, 300, 331, 185),
    'offen': (300, 452, 338, 410),
    'finger': (306, 432, 318, 352),   # Zeigefinger hoch: „Aufgepasst!“
}
POSEN_L = {'haengt': (92, 450, 121, 533), 'offen': (80, 452, 42, 410)}
POSE_NR = {0: 'haengt', 1: 'zeigt', 2: 'daumen', 3: 'winkt', 4: 'offen', 5: 'finger'}
KOPF_DREH = (190, 262)   # Drehpunkt am Hals (Kopf-Koordinaten)
KOPF_H = 312             # Kopf-Ebene reicht von y=0 bis hier
KOPF_Y = 18              # Kopf sitzt so viel tiefer auf dem Hals (kürzerer Hals)
HUEFTE = (190, 540)      # Drehpunkt des Oberkörpers
SCHAL_DREH = (168, 288)  # Schalende hängt hier
VISEME = ('ruhe', 'A', 'E', 'I', 'O', 'U', 'MBP', 'FV', 'L', 'etc')


def _hand_typ(pose, tabelle=POSEN):
    best, dist = 'haengt', 1e9
    for k, v in tabelle.items():
        dd = sum((a - b) ** 2 for a, b in zip(pose, v)) ** 0.5
        if k == 'winkt': dd = min(dd, sum((a - b) ** 2 for a, b in zip(pose, (v[0], v[1], v[2] + 22, v[3]))) ** 0.5)
        if dd < dist: best, dist = k, dd
    return best if dist < 18 else 'haengt'


def _aermel(d, P, pts, look):
    JACKE_, WESTE, KURZ = OUTFIT.get(look, OUTFIT['normal'])
    S = 2
    d.line(pts, fill=LINIE, width=48 * S, joint='curve')
    if not KURZ:
        d.line(pts, fill=JACKE_, width=36 * S, joint='curve'); return
    d.line(pts, fill=HAUT, width=36 * S, joint='curve')
    x0, y0, x1, y1 = pts[0], pts[1], pts[2], pts[3]
    xm, ym = x0 + (x1 - x0) * 0.45, y0 + (y1 - y0) * 0.45
    d.line([x0, y0, xm, ym], fill=LINIE, width=50 * S)
    d.line([x0, y0, xm, ym], fill=JACKE_, width=40 * S)


def _hand(d, P, hx, hy, typ, spiegel=False):
    S, L = 2, 10
    sx = -1 if spiegel else 1
    if typ == 'winkt':
        for k in range(4):
            fx = hx - 19 + k * 12
            d.rounded_rectangle(P(fx, hy - 57 + abs(k - 1.5) * 6, fx + 11, hy - 13), radius=5 * S, fill=HAUT, outline=LINIE, width=3 * S)
    elif typ == 'offen':
        for k in range(4):
            fx = hx - 14 + k * 10 if not spiegel else hx + 5 - k * 10
            d.rounded_rectangle(P(fx, hy - 44 + abs(k - 1.5) * 5, fx + 9, hy - 10), radius=4 * S, fill=HAUT, outline=LINIE, width=3 * S)
    d.ellipse(P(hx - 21, hy - 21, hx + 21, hy + 21), fill=HAUT, outline=LINIE, width=L)
    if typ == 'daumen':
        d.rounded_rectangle(P(hx - 9, hy - 57, hx + 11, hy - 13), radius=9 * S, fill=HAUT, outline=LINIE, width=4 * S)
    elif typ == 'zeigt':
        d.line(P(hx + 7, hy - 9, hx + 23, hy - 41), fill=LINIE, width=16 * S)
        d.line(P(hx + 7, hy - 9, hx + 23, hy - 41), fill=HAUT, width=9 * S)
    elif typ == 'finger':
        d.line(P(hx + 3, hy - 14, hx + 6, hy - 52), fill=LINIE, width=16 * S)
        d.line(P(hx + 3, hy - 14, hx + 6, hy - 52), fill=HAUT, width=9 * S)


def max_beine():
    """Beide Beine einzeln (für die Laufbewegung): Liste [(bild, drehpunkt)]."""
    S = 2; L = 5 * S
    def P(*xy): return [v * S for v in xy]
    aus = []
    for (x0, x1, s0, s1, hx) in ((130, 182, 120, 188, 156), (198, 250, 192, 260, 224)):
        im = Image.new('RGBA', (380 * S, 760 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle(P(x0, 520, x1, 725), radius=20 * S, fill=HOSE, outline=LINIE, width=L)
        d.rounded_rectangle(P(s0, 712, s1, 744), radius=13 * S, fill=(50, 38, 32), outline=LINIE, width=L)
        aus.append((im.resize((380, 760), Image.LANCZOS), (hx, 528)))
    return aus


def max_oberkoerper(pose_r, pose_l, look='normal', studio=False, prop=None):
    """Oberkörper mit beiden Armen in beliebiger Stellung und Hals (ohne Kopf, ohne Beine)."""
    S = 2
    w, h = 380 * S, 760 * S
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    L = 5 * S
    def P(*xy): return [v * S for v in xy]
    JACKE_, WESTE, KURZ = OUTFIT.get(look, OUTFIT['normal'])
    # linker Arm (hinter dem Rumpf)
    ex, ey, hx, hy = pose_l
    _aermel(d, P, P(SCHULTER_L[0], SCHULTER_L[1], ex, ey, hx, hy), look)
    _hand(d, P, hx, hy, _hand_typ(pose_l, POSEN_L), spiegel=True)
    d.rounded_rectangle(P(108, 290, 272, 560), radius=46 * S, fill=JACKE_, outline=LINIE, width=L)
    if WESTE:
        d.polygon(P(150, 300, 190, 300, 182, 560, 150, 560), fill=WESTE, outline=LINIE)
        d.polygon(P(230, 300, 190, 300, 198, 560, 230, 560), fill=WESTE, outline=LINIE)
    if look == 'winter':
        for y in (360, 410, 460, 510): d.line(P(116, y, 264, y), fill=(160, 30, 40), width=4 * S)
    if not KURZ: d.line(P(190, 300, 190, 560), fill=(220, 220, 225), width=4 * S)
    dunkel = tuple(int(v * 0.72) for v in (WESTE or JACKE_))
    d.line(P(150, 470, 178, 470), fill=dunkel, width=5 * S)
    d.line(P(202, 470, 230, 470), fill=dunkel, width=5 * S)
    if KURZ:
        d.chord(P(160, 270, 220, 320), 0, 180, fill=HAUT, outline=LINIE, width=L)
    else:
        d.polygon(P(148, 278, 190, 330, 232, 278, 224, 300, 190, 345, 156, 300), fill=JACKE_, outline=LINIE)
        d.polygon(P(166, 284, 190, 318, 214, 284), fill=(245, 245, 245), outline=LINIE)
    d.rounded_rectangle(P(203, 336, 263, 360), radius=6 * S, fill=(255, 255, 255), outline=LINIE, width=3 * S)
    d.text(P(233, 348), 'MAX', font=ImageFont.truetype(B, 13 * S), fill=(30, 130, 120), anchor='mm')
    d.rounded_rectangle(P(158, 338, 170, 352), radius=2 * S, fill=(70, 70, 78), outline=LINIE, width=2 * S)
    d.ellipse(P(156, 324, 172, 340), fill=(35, 35, 40), outline=LINIE, width=2 * S)
    d.line(P(164, 352, 160, 380), fill=(35, 35, 40), width=2 * S)
    # rechter Arm (vor dem Rumpf)
    ex, ey, hx, hy = pose_r
    _aermel(d, P, P(SCHULTER_R[0], SCHULTER_R[1], ex, ey, hx, hy), look)
    _hand(d, P, hx, hy, _hand_typ(pose_r))
    d.rectangle(P(172, 250, 208, 295), fill=HAUT, outline=LINIE, width=L)   # Hals
    return im.resize((w // S, h // S), Image.LANCZOS)


def max_koerper(pose, look='normal', studio=False):
    """Ganzer Körper ohne Kopf (Beine + Oberkörper, linker Arm hängt) – für Einzelbilder."""
    im = Image.new('RGBA', (380, 760), (0, 0, 0, 0))
    for b, _ in max_beine(): im.alpha_composite(b)
    im.alpha_composite(max_oberkoerper(pose, POSEN_L['haengt'], look, studio))
    return im


def _mund(d, P, vis, auf, ausdruck):
    """Mundform zeichnen. vis: Mundbild (Visem), auf 1..3 = wie weit offen."""
    S = 2
    ROT, ZUNGE, ZAHN = (140, 40, 50), (220, 90, 100), (255, 255, 255)
    if vis == 'ruhe':
        if ausdruck == 'freude':
            d.chord(P(164, 196, 216, 228), 10, 170, fill=ROT, outline=LINIE, width=4 * S)
            d.rectangle(P(172, 212, 208, 216), fill=ZAHN)
        elif ausdruck == 'besorgt':
            d.arc(P(166, 210, 214, 236), 200, 340, fill=LINIE, width=5 * S)
        elif ausdruck == 'staunen':
            d.ellipse(P(183, 204, 199, 222), fill=ROT, outline=LINIE, width=4 * S)
        elif ausdruck == 'nachdenklich':
            d.line(P(172, 214, 210, 210), fill=LINIE, width=5 * S)
        else:
            d.arc(P(160, 190, 220, 228), 10, 170, fill=LINIE, width=5 * S)
        return
    f = (0.65, 0.85, 1.0)[max(1, min(3, auf)) - 1]
    if vis == 'MBP':
        d.line(P(168, 211, 212, 211), fill=LINIE, width=6 * S)
        d.arc(P(164, 196, 216, 222), 25, 155, fill=(150, 70, 70), width=3 * S)
    elif vis == 'A':
        o = 26 * f; top, bot = 204, 212 + o
        d.chord(P(162, top, 218, bot), 0, 180, fill=ROT, outline=LINIE, width=4 * S)
        d.rectangle(P(172, (top + bot) / 2 + 1, 208, (top + bot) / 2 + 6), fill=ZAHN)
        d.ellipse(P(180, bot - 10, 200, bot - 3), fill=ZUNGE)
    elif vis == 'E':
        o = 21 * f
        d.chord(P(158, 202, 222, 212 + o), 0, 180, fill=ROT, outline=LINIE, width=4 * S)
        d.rectangle(P(168, 208, 212, 213), fill=ZAHN)
    elif vis == 'I':
        o = 13 * f
        d.chord(P(156, 203, 224, 212 + o), 0, 180, fill=ROT, outline=LINIE, width=4 * S)
        d.rectangle(P(166, 208, 214, 212), fill=ZAHN)
    elif vis == 'O':
        o = 30 * f
        d.ellipse(P(176, 202, 204, 204 + o), fill=ROT, outline=LINIE, width=4 * S)
        d.ellipse(P(183, 198 + o, 197, 202 + o), fill=ZUNGE)
    elif vis == 'U':
        d.ellipse(P(181, 203, 199, 223), fill=ROT, outline=LINIE, width=5 * S)
        d.arc(P(176, 199, 204, 227), 0, 360, fill=(170, 80, 80), width=2 * S)
    elif vis == 'FV':
        d.chord(P(166, 204, 214, 222), 0, 180, fill=ROT, outline=LINIE, width=4 * S)
        d.rectangle(P(170, 206, 210, 212), fill=ZAHN)
        d.line(P(168, 214, 212, 214), fill=(170, 80, 80), width=4 * S)
    elif vis == 'L':
        o = 18 * f
        d.chord(P(162, 204, 218, 212 + o), 0, 180, fill=ROT, outline=LINIE, width=4 * S)
        d.rectangle(P(172, 208, 208, 212), fill=ZAHN)
        d.ellipse(P(182, 210, 198, 218), fill=ZUNGE)
    else:   # etc: leicht geöffnet mit Zähnen
        o = 10 * f
        d.chord(P(162, 205, 218, 212 + o), 0, 180, fill=ROT, outline=LINIE, width=4 * S)
        d.rectangle(P(172, 209, 208, 213), fill=ZAHN)


def max_kopf(vis, auf, auge, blick, braue, ausdruck='neutral', look='normal', prop=None, ohne_zipfel=False):
    """Kopf-Ebene (y 0..KOPF_H). vis = Mundbild, auf 1..3, auge 0 offen/1 halb/2 zu, blick -1..1,
    braue -1 ernst/0/1/2 hoch, ausdruck neutral/freude/staunen/nachdenklich/besorgt."""
    S = 2
    w, h = 380 * S, KOPF_H * S
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    L = 5 * S
    def P(*xy): return [v * S for v in xy]
    d.ellipse(P(110, 60, 270, 260), fill=HAUT, outline=LINIE, width=L)
    bart = Image.new('RGBA', im.size, (0, 0, 0, 0)); bd = ImageDraw.Draw(bart)
    bd.chord(P(124, 150, 256, 258), 15, 165, fill=HAAR + (38,))
    im.alpha_composite(bart); d = ImageDraw.Draw(im)
    d.ellipse(P(100, 140, 126, 190), fill=HAUT, outline=LINIE, width=L)
    d.ellipse(P(254, 140, 280, 190), fill=HAUT, outline=LINIE, width=L)
    d.chord(P(108, 52, 272, 176), 180, 360, fill=HAAR, outline=LINIE, width=L)
    d.pieslice(P(118, 36, 262, 150), 200, 340, fill=HAAR)
    d.polygon(P(128, 108, 150, 62, 205, 40, 258, 70, 262, 108, 230, 88, 190, 98, 160, 90), fill=HAAR)
    d.line(P(150, 62, 205, 40, 258, 70), fill=LINIE, width=4 * S, joint='curve')
    d.arc(P(160, 60, 240, 110), 200, 300, fill=(70, 42, 22), width=3 * S)
    d.rectangle(P(114, 108, 128, 146), fill=HAAR)
    d.rectangle(P(252, 108, 266, 146), fill=HAAR)
    bx = blick * 5
    by = -3 if ausdruck == 'nachdenklich' else 0
    gross = 2 if ausdruck == 'staunen' else 0
    for n_, ex in enumerate((158, 222)):
        if auge >= 2:
            if ausdruck == 'freude': d.arc(P(ex - 15, 148, ex + 15, 168), 180, 360, fill=LINIE, width=4 * S)   # Lachaugen
            else: d.arc(P(ex - 15, 145, ex + 15, 165), 0, 180, fill=LINIE, width=4 * S)
        else:
            d.ellipse(P(ex - 13 - gross, 138 - gross, ex + 13 + gross, 168 + gross), fill=(255, 255, 255), outline=LINIE, width=3 * S)
            d.ellipse(P(ex - 7 + bx, 146 + by, ex + 7 + bx, 162 + by), fill=(60, 90, 140))
            d.ellipse(P(ex - 2 + bx, 148 + by, ex + 3 + bx, 153 + by), fill=(255, 255, 255))
            if auge == 1:
                d.chord(P(ex - 13, 138, ex + 13, 168), 180, 360, fill=HAUT)
                d.line(P(ex - 13, 153, ex + 13, 153), fill=LINIE, width=4 * S)
            if ausdruck == 'freude':   # Wangen schieben das Unterlid hoch
                d.chord(P(ex - 15, 158, ex + 15, 182), 180, 360, fill=HAUT)
                d.arc(P(ex - 14, 158, ex + 14, 180), 200, 340, fill=LINIE, width=3 * S)
        hoch = {0: 0, 1: 4, 2: 8, -1: 0}.get(braue, 0)
        if ausdruck in ('freude',): hoch += 2
        if ausdruck == 'staunen': hoch = max(hoch, 9)
        l_y, r_y = 126 - hoch, 122 - hoch
        innen = 0
        if braue == -1: innen = 6           # ernst: innere Enden tiefer
        if ausdruck == 'besorgt': innen = -7  # besorgt: innere Enden hoch
        if n_ == 0: r_y += innen
        else: l_y += innen
        if ausdruck == 'nachdenklich' and n_ == 1: l_y -= 7; r_y -= 9   # eine Braue hoch
        d.line(P(ex - 16, l_y, ex + 14, r_y), fill=HAAR, width=6 * S)
    d.line(P(190, 165, 182, 195, 194, 198), fill=(200, 140, 110), width=4 * S)
    wange = 1.0 if ausdruck != 'freude' else 1.25
    for cx_ in (143, 237):
        rx, ry = 13 * wange, 9 * wange
        d.ellipse(P(cx_ - rx, 194 - ry, cx_ + rx, 194 + ry), fill=(250, 170, 150))
    _mund(d, P, vis, auf, ausdruck)
    if WEIHNACHT[0] and look != 'sturm':
        d.polygon(P(108, 112, 272, 112, 250, 50, 232, 40, 214, 34, 150, 52), fill=(200, 35, 45), outline=LINIE)
        d.line(P(108, 112, 150, 52, 214, 34), fill=LINIE, width=L); d.line(P(250, 50, 272, 112), fill=LINIE, width=L)
        if not ohne_zipfel:
            d.polygon(P(250, 50, 300, 20, 214, 34), fill=(200, 35, 45), outline=LINIE)
            d.ellipse(P(286, 4, 326, 44), fill=(245, 245, 245), outline=LINIE, width=L)
        d.rounded_rectangle(P(98, 94, 282, 130), radius=16 * S, fill=(245, 245, 245), outline=LINIE, width=L)
    elif look == 'winter':
        d.chord(P(104, 30, 276, 190), 180, 360, fill=(200, 45, 50), outline=LINIE, width=L)
        d.rounded_rectangle(P(100, 96, 280, 128), radius=14 * S, fill=(240, 240, 240), outline=LINIE, width=L)
        for x in range(120, 270, 22): d.line(P(x, 40 + abs(x - 190) // 3, x, 96), fill=(170, 30, 40), width=4 * S)
        if not ohne_zipfel: d.ellipse(P(166, 0, 214, 48), fill=(240, 240, 240), outline=LINIE, width=L)
    elif look == 'kuehl':
        d.chord(P(108, 40, 272, 200), 180, 360, fill=(40, 110, 70), outline=LINIE, width=L)
        d.rounded_rectangle(P(106, 104, 274, 130), radius=10 * S, fill=(30, 90, 55), outline=LINIE, width=L)
        for x in range(128, 262, 18): d.line(P(x, 108, x, 126), fill=(50, 130, 85), width=3 * S)
    elif look == 'regen' and prop != 'schirm':
        d.ellipse(P(80, 92, 300, 140), fill=(250, 200, 30), outline=LINIE, width=L)
        d.chord(P(122, 34, 258, 170), 180, 360, fill=(250, 200, 30), outline=LINIE, width=L)
        d.line(P(124, 104, 256, 104), fill=(210, 160, 20), width=6 * S)
    elif look == 'sonne':
        d.chord(P(112, 40, 268, 180), 180, 360, fill=(30, 130, 120), outline=LINIE, width=L)
        d.pieslice(P(200, 88, 320, 128), 180, 360, fill=(25, 105, 95), outline=LINIE, width=L)
        d.text(P(190, 78), 'ODW', font=ImageFont.truetype(B, 18 * S), fill=(255, 255, 255), anchor='mm')
        for ex in (158, 222):
            d.rounded_rectangle(P(ex - 24, 136, ex + 24, 170), radius=12 * S, fill=(30, 40, 60), outline=LINIE, width=4 * S)
            d.line(P(ex - 14, 142, ex - 4, 142), fill=(120, 150, 200), width=3 * S)
        d.line(P(182, 148, 198, 148), fill=LINIE, width=5 * S)
    if look == 'sturm':
        for k in range(6): d.line(P(120 + k * 26, 70, 150 + k * 26, 36 + (k % 2) * 10), fill=HAAR, width=9 * S)
    return im.resize((w // S, h // S), Image.LANCZOS)


def max_schal(look, teil='knoten'):
    """Schal: 'knoten' (um den Hals) oder 'ende' (hängendes Ende, schwingt nach)."""
    S = 2
    im = Image.new('RGBA', (380 * S, 760 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); L = 5 * S
    def P(*xy): return [v * S for v in xy]
    weih = WEIHNACHT[0] and look != 'sturm'
    if not weih and look != 'winter': return None
    rot = (200, 35, 45) if weih else (200, 45, 50)
    if teil == 'knoten':
        d.rounded_rectangle(P(140, 250, 240, 296), radius=20 * S, fill=rot, outline=LINIE, width=L)
        if weih:
            for x in (160, 190, 220): d.line(P(x, 254, x, 292), fill=(30, 120, 60), width=8 * S)
    else:
        d.rounded_rectangle(P(150, 280, 186, 400), radius=10 * S, fill=rot, outline=LINIE, width=L)
        if weih:
            for y in (310, 340, 370): d.line(P(152, y, 184, y), fill=(30, 120, 60), width=8 * S)
            for x in (156, 168, 180): d.line(P(x, 400, x, 414), fill=(245, 245, 245), width=4 * S)
        else:
            for y in (330, 360): d.line(P(150, y, 186, y), fill=(240, 240, 240), width=6 * S)
    return im.resize((380, 760), Image.LANCZOS)


def max_prop(prop):
    S = 2
    if prop not in ('schippe', 'schirm'): return None
    im = Image.new('RGBA', (380 * S, 760 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); L = 5 * S
    def P(*xy): return [v * S for v in xy]
    (schippe if prop == 'schippe' else schirm)(d, P, L)
    return im.resize((380, 760), Image.LANCZOS)


class Feder:
    """Gedämpfte Feder: folgt einem Ziel weich, schießt leicht über (Zeichentrick-Bewegung)."""
    def __init__(self, wert, k=0.14, daempf=0.72):
        self.x = list(wert) if isinstance(wert, (list, tuple)) else [wert]
        self.v = [0.0] * len(self.x); self.k, self.dm = k, daempf
    def zu(self, ziel):
        z = list(ziel) if isinstance(ziel, (list, tuple)) else [ziel]
        for j in range(len(self.x)):
            self.v[j] = (self.v[j] + (z[j] - self.x[j]) * self.k) * self.dm
            self.x[j] += self.v[j]
        return tuple(self.x) if len(self.x) > 1 else self.x[0]


def _dreh(px, py, cx, cy, grad):
    """Punkt um (cx, cy) drehen – wie PIL rotate (positiv = gegen den Uhrzeigersinn)."""
    a = math.radians(grad); dx, dy = px - cx, py - cy
    return cx + dx * math.cos(a) + dy * math.sin(a), cy - dx * math.sin(a) + dy * math.cos(a)


class MaxFigur:
    """Setzt Max Bild für Bild aus den Ebenen zusammen (mit Zwischenspeicher)."""
    def __init__(self, look='normal', prop=None, studio=False, gr=1.0):
        self.look, self.prop, self.studio, self.gr = look, prop, studio, gr
        self.K, self.KO, self.SR, self.PR = {}, {}, {}, {}
        self.w, self.h = int(380 * gr), int(760 * gr)
        def sk(im): return None if im is None else im.resize((self.w, self.h), Image.LANCZOS)
        self.beine = [(sk(b), (p[0] * gr, p[1] * gr)) for b, p in max_beine()]
        self.beine_fest = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        for b, _ in self.beine: self.beine_fest.alpha_composite(b)
        self.knoten, self.ende, self.req = sk(max_schal(look, 'knoten')), sk(max_schal(look, 'ende')), sk(max_prop(prop))
        self.zipfel = 'weih' if WEIHNACHT[0] and look != 'sturm' else 'bommel' if look == 'winter' else None
        self.zf = None   # Feder für Bommel/Mützenzipfel

    def oberkoerper(self, pr, pl):
        q = (tuple(int(round(v / 3.0)) * 3 for v in pr), tuple(int(round(v / 3.0)) * 3 for v in pl))
        if q not in self.K:
            self.K[q] = max_oberkoerper(q[0], q[1], self.look, self.studio, self.prop).resize((self.w, self.h), Image.LANCZOS)
        return self.K[q]

    def kopf(self, vis, auf, auge, blick, braue, ausdruck):
        k = (vis, auf if vis not in ('ruhe', 'MBP', 'U', 'FV') else 0, auge, round(blick * 2) / 2, braue, ausdruck)
        if k not in self.KO:
            im = max_kopf(vis, max(1, k[1]), auge, k[3], braue, ausdruck, self.look, self.prop, ohne_zipfel=self.zipfel is not None)
            self.KO[k] = im.resize((self.w, int(KOPF_H * self.gr)), Image.LANCZOS)
        return self.KO[k]

    def bild(self, pose=POSEN['haengt'], pose_l=POSEN_L['haengt'], vis='ruhe', auf=2, auge=0, blick=0, braue=0, ausdruck='neutral',
             winkel=0.0, nick=0.0, atem=0.0, koerper=0.0, schal=0.0, schirm=0.0, lauf=None, mund=None):
        """winkel: Kopfneigung (Grad), nick: Kopf runter (Grundpixel), atem 0..1, koerper: Neigung des Oberkörpers (Grad),
        schal: Auslenkung des Schalendes (Grad), schirm: Schirm wackelt (Grad), lauf: Phase der Laufbewegung oder None."""
        if mund is not None:   # alte Aufrufe: mund 0..3 / 'o' / 'm'
            vis, auf = {0: ('ruhe', 1), 1: ('etc', 1), 2: ('E', 2), 3: ('A', 3), 'o': ('O', 2), 'm': ('MBP', 1)}.get(mund, ('ruhe', 1))
        g = self.gr
        out = Image.new('RGBA', (self.w, self.h), (0, 0, 0, 0))
        if lauf is None:
            out.alpha_composite(self.beine_fest)
        else:
            for j, (b, (px, py)) in enumerate(self.beine):
                a = 16 * math.sin(lauf + j * math.pi)
                out.alpha_composite(b.rotate(a, resample=Image.BICUBIC, center=(px, py)))
        ob = self.oberkoerper(pose, pose_l).copy()
        ko = self.kopf(vis, auf, auge, blick, braue, ausdruck)
        px, py = KOPF_DREH[0] * g, KOPF_DREH[1] * g
        wq = round(winkel * 4) / 4
        if wq: ko = ko.rotate(wq, resample=Image.BICUBIC, center=(px, py))
        ky = (nick + KOPF_Y) * g
        ob.alpha_composite(ko, (0, int(round(ky))))
        if self.knoten is not None:
            ob.alpha_composite(self.knoten)
            sq = round(schal * 2) / 2
            if sq not in self.SR: self.SR[sq] = self.ende.rotate(sq, resample=Image.BICUBIC, center=(SCHAL_DREH[0] * g, SCHAL_DREH[1] * g)) if sq else self.ende
            ob.alpha_composite(self.SR[sq])
        if self.zipfel:   # Bommel bzw. Mützenzipfel schwingen nach
            d = ImageDraw.Draw(ob); lw = max(2, int(5 * g))
            def kp(x, y):
                xx, yy = _dreh(x * g, y * g, px, py, wq); return xx, yy + ky
            if self.zipfel == 'bommel':
                ax, ay = kp(190, 24)
                if self.zf is None or abs(self.zf.x[0] - ax) > 60 * g: self.zf = Feder((ax, ay), 0.22, 0.78)
                bx, by = self.zf.zu((ax, ay)); r = 24 * g
                d.ellipse([bx - r, by - r, bx + r, by + r], fill=(240, 240, 240), outline=LINIE, width=lw)
            else:
                ax, ay = kp(306, 24)
                if self.zf is None or abs(self.zf.x[0] - ax) > 60 * g: self.zf = Feder((ax, ay), 0.16, 0.80)
                bx, by = self.zf.zu((ax, ay))
                p1, p2 = kp(250, 50), kp(214, 34)
                d.polygon([p1, (bx - 6 * g, by - 4 * g), p2], fill=(200, 35, 45), outline=LINIE)
                d.line([p2, (bx - 6 * g, by - 4 * g), p1], fill=LINIE, width=lw)
                r = 20 * g
                d.ellipse([bx - r, by - r, bx + r, by + r], fill=(245, 245, 245), outline=LINIE, width=lw)
        if self.req is not None:
            sq = round(schirm * 2) / 2 if self.prop == 'schirm' else 0
            if sq not in self.PR: self.PR[sq] = self.req.rotate(sq, resample=Image.BICUBIC, center=(118 * g, 530 * g)) if sq else self.req
            ob.alpha_composite(self.PR[sq])
        kq = round(koerper * 4) / 4
        if kq: ob = ob.rotate(kq, resample=Image.BICUBIC, center=(HUEFTE[0] * g, HUEFTE[1] * g))
        out.alpha_composite(ob, (0, -int(round(atem * 3 * g))))
        return out


def moderator(mund, blinzeln, zeigen, wink=0, look='normal', prop=None, studio=False):
    """Einzelbild von Max (für Themenvideos): zeigen 0 hängt, 1 zeigt, 2 Daumen, 3 winkt, 4 offene Hand, 5 Zeigefinger."""
    pose = list(POSEN[POSE_NR.get(zeigen, 'haengt')])
    if zeigen == 3: pose[2] += wink
    return MaxFigur(look, prop, studio, 1.0).bild(tuple(pose), mund=mund, auge=2 if blinzeln else 0)


# --- Lippensynchronität: deutsche Schreibung -> Mundbilder (Viseme) ---
_LAUT_REGELN = [('tsch', ['U']), ('sch', ['U']), ('chs', ['etc']), ('ch', ['etc']), ('ck', ['etc']), ('ph', ['FV']), ('pf', ['FV']),
                ('qu', ['etc', 'FV']), ('ei', ['A', 'I']), ('ai', ['A', 'I']), ('ay', ['A', 'I']), ('au', ['A', 'U']), ('eu', ['O', 'I']),
                ('äu', ['O', 'I']), ('ie', ['I']), ('aa', ['A']), ('ah', ['A']), ('ee', ['E']), ('eh', ['E']), ('oo', ['O']), ('oh', ['O']),
                ('uh', ['U']), ('äh', ['E']), ('öh', ['O']), ('üh', ['U']), ('th', ['etc'])]
_LAUT_EINZEL = {'a': 'A', 'ä': 'E', 'e': 'E', 'i': 'I', 'y': 'I', 'o': 'O', 'ö': 'O', 'u': 'U', 'ü': 'U',
                'b': 'MBP', 'm': 'MBP', 'p': 'MBP', 'f': 'FV', 'v': 'FV', 'w': 'FV', 'l': 'L'}


def laute(wort):
    """Wort -> Folge von Mundbildern (grobe deutsche Ausspracheregeln)."""
    w = ''.join(c for c in wort.lower() if c.isalnum())
    if not w: return []
    if w.isdigit(): return ['etc', 'A', 'etc', 'E'][:max(2, min(4, len(w) + 1))]
    out, i = [], 0
    while i < len(w):
        if w.endswith('er') and i == len(w) - 2 and len(w) > 3: out.append('A'); break   # vokalisches r: „Wetter“
        for mu, v in _LAUT_REGELN:
            if w.startswith(mu, i): out += v; i += len(mu); break
        else:
            c = w[i]; i += 1
            if c == 'h': continue
            out.append(_LAUT_EINZEL.get(c, 'etc'))
    z = []
    for v in out:
        if not z or z[-1] != v: z.append(v)
    return z


def _gewicht(v): return 2.0 if v in ('A', 'E', 'I', 'O', 'U') else 1.3 if v == 'MBP' else 1.0


class MaxAnimation:
    """Bewegungsablauf: Lippensynchronität, Mimik, Blinzeln, Blick, Brauen, Kopf, Oberkörper, beide Arme mit Federbewegung,
    Gesten, Atmung, nachschwingender Schal, wackelnder Schirm und Hereinlaufen am Anfang."""
    def __init__(self, lv, rund=None, seed=1, segmente=None):
        self.lv = lv; n = len(lv)
        self.r = random.Random(seed)
        self.blink = np.zeros(n, dtype=int); i = int(self.r.uniform(1, 3) * FPS)
        while i < n:
            folge = [1, 2, 1]
            if self.r.random() < 0.18: folge += [0, 0, 1, 2, 1]
            for k, v in enumerate(folge):
                if i + k < n: self.blink[i + k] = v
            i += len(folge) + int(self.r.uniform(2.0, 6.0) * FPS)
        sm = np.convolve(lv, np.ones(3) / 3, mode='same')
        self.betont = np.zeros(n, dtype=bool); sperre = 0
        for i in range(4, n):
            if sm[i] > 0.9 and sm[i] - sm[i - 4] > 0.45 and i > sperre:
                self.betont[i] = True; sperre = i + int(0.7 * FPS)
        self.spricht = lv >= 0.15
        self.vis = self._viseme(segmente or [], rund)
        self.arm_r = Feder(POSEN['haengt'], 0.14, 0.72); self.arm_l = Feder(POSEN_L['haengt'], 0.14, 0.72)
        self.blick = 0.0; self.braue = 0.0; self.nick = 0.0; self.nv = 0.0
        self.koerper = Feder(0.0, 0.08, 0.82); self.schal = Feder(0.0, 0.10, 0.86); self.schal_v = 0.0
        self.atem = 0.0; self.geste_bis = -1; self.geste_art = 'r'; self.naechste_geste = int(self.r.uniform(3, 6) * FPS)
        self.blick_bis = -1; self.blick_ziel = 0.0; self.ruhe = 0; self.letzte_koerper = 0.0
        self.ph = [self.r.uniform(0, 6.3) for _ in range(5)]

    def _viseme(self, segmente, rund):
        n = len(self.lv); vis = ['ruhe'] * n
        for s in segmente:
            t0 = s.get('t0'); woerter = s.get('woerter')
            if t0 is None: continue
            if woerter:
                for a, b, w in woerter:
                    seq = laute(w)
                    if not seq: continue
                    f0, f1 = int((t0 + a) * FPS), max(int((t0 + a) * FPS) + 1, int((t0 + b) * FPS))
                    ges = sum(_gewicht(v) for v in seq); pos = f0
                    for v in seq:
                        l = (f1 - f0) * _gewicht(v) / ges
                        for f in range(int(round(pos)), int(round(pos + l))):
                            if 0 <= f < n: vis[f] = v
                        pos += l
            else:   # ohne Wortzeiten: Laute gleichmäßig auf die gesprochenen Bilder des Abschnitts verteilen
                fr = [f for f in range(int(t0 * FPS), min(n, int((t0 + s.get('dauer', 0) - 0.6) * FPS))) if self.lv[f] >= 0.15]
                seq = [v for w in sprechtext(s.get('text', '')).split() for v in laute(w)]
                if not fr or not seq: continue
                gw = [_gewicht(v) for v in seq]; ges = sum(gw); acc = 0
                for v, g_ in zip(seq, gw):
                    a_, acc = acc, acc + g_
                    for f in fr[int(len(fr) * a_ / ges):int(len(fr) * acc / ges)]: vis[f] = v
        if not segmente and rund is not None:   # ganz ohne Text: alte Methode über den Klang
            for f in range(n):
                if self.lv[f] >= 0.15: vis[f] = 'O' if f < len(rund) and rund[f] else 'A' if self.lv[f] >= 0.8 else 'E' if self.lv[f] >= 0.45 else 'etc'
        return vis

    def mund(self, i):
        lv = self.lv; v = lv[i] if i < len(lv) else 0
        vis = self.vis[i] if i < len(self.vis) else 'ruhe'
        if v < 0.12:
            vor = any(lv[j] >= 0.3 for j in range(max(0, i - 3), i))
            nach = any(lv[j] >= 0.3 for j in range(i + 1, min(len(lv), i + 4)))
            return ('MBP' if vor and nach else 'ruhe'), 1
        if vis == 'ruhe': vis = 'etc'
        return vis, 1 if v < 0.5 else 2 if v < 0.9 else 3

    @staticmethod
    def ausdruck_fuer(s, lt, special=False):
        txt = s.get('text', '')
        if s.get('art') == 'special' or (special and s.get('art') in ('tag', 'intro')): return 'besorgt'
        if any(w in txt for w in ('Rekord', 'noch nie', 'Wahnsinn', 'unglaublich')) and lt < 2.5: return 'staunen'
        if s.get('art') in ('tipp', 'intro', 'outro', 'cta', 'frage'): return 'freude'
        if lt < 1.6 and txt.split('.')[0].rstrip().endswith('?'): return 'nachdenklich'
        tg = s.get('tag') or {}
        if tg:
            w = wort(tg.get('code', 3))
            if w in ('Gewitter',) or tg.get('boe', 0) >= 60: return 'besorgt'
            if tg.get('code') in (0, 1) or (tg.get('tmax', 0) >= 20 and tg.get('rp', 100) < 30): return 'freude'
        return 'neutral'

    def schritt(self, i, t, s, lt, zeigt_alt, ernst=False, studio=False, prop=None, erster=False, special=False):
        n = len(self.lv); v = self.lv[i] if i < n else 0
        spricht = bool(self.spricht[i]) if i < n else False
        # --- Arme: Grundgeste aus dem Ablauf, beim Reden Erklär-Gesten (rechts, links oder beide)
        ziel = zeigt_alt
        if ernst and ziel == 0 and 0.8 < lt < 2.3 and s.get('art') in ('special', 'intro'): ziel = 5   # Zeigefinger: aufgepasst
        if ziel == 0 and spricht and i >= self.naechste_geste and 1.0 < lt < s['dauer'] - 1.5:
            self.geste_bis = i + int(self.r.uniform(1.0, 1.8) * FPS)
            self.naechste_geste = i + int(self.r.uniform(3.5, 6.5) * FPS)
            self.geste_art = self.r.choice(('r', 'r', 'l', 'beide')) if prop is None else 'r'
        links = 'haengt'
        if ziel == 0 and i < self.geste_bis:
            if self.geste_art in ('r', 'beide'): ziel = 4
            if self.geste_art in ('l', 'beide'): links = 'offen'
        zp = list(POSEN[POSE_NR[ziel]])
        if ziel == 3: zp[2] += 11 + 11 * math.sin(t * 2 * math.pi * 2.4)
        if ziel == 4: zp[3] += 6 * math.sin(t * 5.5); zp[2] += 3 * math.sin(t * 3.1)
        zl = list(POSEN_L[links])
        if links == 'offen': zl[3] += 6 * math.sin(t * 5.1 + 1); zl[2] -= 3 * math.sin(t * 2.9)
        self.arm_r.k = 0.30 if ziel == 3 else 0.14
        pose = self.arm_r.zu(zp); pose_l = self.arm_l.zu(zl)
        # --- Blick
        if zeigt_alt == 1: self.blick_ziel, self.blick_bis = 1.0, i + int(0.4 * FPS)
        elif i > self.blick_bis:
            self.blick_ziel = 0.0
            if self.r.random() < 0.004: self.blick_ziel, self.blick_bis = self.r.choice((-0.5, 0.5)), i + int(0.6 * FPS)
        self.blick += (self.blick_ziel - self.blick) * 0.35
        # --- Mimik und Brauen
        ausdruck = self.ausdruck_fuer(s, lt, special)
        if i < n and self.betont[i]: self.braue = 2.0
        txt = s.get('text', '').rstrip()
        if txt.endswith('?') and lt > s['dauer'] - 1.6: self.braue = max(self.braue, 1.5)
        self.braue *= 0.88
        braue = 2 if self.braue > 1.3 else 1 if self.braue > 0.5 else (-1 if ernst and ausdruck != 'besorgt' else 0)
        # --- Kopf
        if i < n and self.betont[i]: self.nv += 2.6
        self.nv += -self.nick * 0.35; self.nv *= 0.70; self.nick += self.nv
        sp = min(1.0, v)
        winkel = (1.2 * math.sin(t * 0.6 + self.ph[0]) + 1.6 * sp * math.sin(t * 2.1 + self.ph[1])
                  + 0.8 * math.sin(t * 1.3 + self.ph[2]) - 2.5 * self.blick * (zeigt_alt == 1))
        if lt < 0.6: winkel += 1.5 * math.sin(lt / 0.6 * math.pi)
        if ausdruck == 'nachdenklich': winkel += 3
        # --- Oberkörper: Gewicht verlagern, zur Geste hin neigen
        kz = 0.9 * math.sin(t * 0.45 + self.ph[3]) + 0.5 * math.sin(t * 1.1 + self.ph[4]) * sp
        if ziel in (1, 3, 4, 5): kz -= 1.2
        if links == 'offen': kz += 1.0
        if i < n and self.betont[i]: self.koerper.v[0] += 0.6
        koerper = self.koerper.zu(kz)
        # --- Atmung (in Pausen deutlicher), Schulterzucken bei Betonung
        self.ruhe = self.ruhe + 1 if not spricht else 0
        tief = 1.0 if self.ruhe > FPS * 0.35 else 0.35
        self.atem += (tief * (0.5 + 0.5 * math.sin(t * 2 * math.pi / 3.6)) - self.atem) * 0.15
        # --- Schalende schwingt der Körperbewegung hinterher
        dk = koerper - self.letzte_koerper; self.letzte_koerper = koerper
        self.schal.v[0] -= dk * 2.5
        schal = self.schal.zu(-koerper * 0.6)
        # --- Schirm wackelt im Wind
        schirm = 2.0 * math.sin(t * 1.7) + 1.0 * math.sin(t * 4.3) if prop == 'schirm' else 0.0
        # --- Hereinlaufen am Anfang (nur draußen, erstes Intro)
        lauf, xoff = None, 0
        if erster and not studio and lt < 1.1:
            q = min(1.0, lt / 1.1); e = 1 - (1 - q) ** 3
            xoff = -380 * (1 - e)
            if q < 0.95: lauf = lt * 2 * math.pi * 2.2
        auge = int(self.blink[i]) if i < n else 0
        vis, auf = self.mund(i)
        return dict(pose=pose, pose_l=pose_l, vis=vis, auf=auf, auge=auge, blick=self.blick, braue=braue, ausdruck=ausdruck,
                    winkel=winkel, nick=self.nick, atem=self.atem, koerper=koerper, schal=schal, schirm=schirm, lauf=lauf), xoff


def rundheit(wav, n_frames):
    """Je Bild: True, wenn der Klang dunkel/rund ist (O/U) – Anteil tiefer Frequenzen hoch (Rückfall ohne Text)."""
    raw = subprocess.check_output(['ffmpeg', '-loglevel', 'error', '-i', wav, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'])
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    per = 16000 // FPS
    fr = np.fft.rfftfreq(per, 1 / 16000)
    tief, hoch = (fr >= 150) & (fr < 700), (fr >= 700) & (fr < 3500)
    q = []
    for i in range(n_frames):
        c = a[i * per:(i + 1) * per]
        if len(c) < per: q.append(0.0); continue
        sp = np.abs(np.fft.rfft(c * np.hanning(per)))
        q.append(float(sp[tief].sum() / (sp[hoch].sum() + 1e-6)))
    q = np.array(q)
    stimme = q[q > 0]
    if len(stimme) < 10: return np.zeros(n_frames, dtype=bool)
    return q > np.percentile(stimme, 80)


def baum(sway):
    """Großer Laubbaum im Vordergrund – Krone neigt sich im Sturm (sway in Grad)."""
    im = Image.new('RGBA', (360, 620), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(165, 620), (195, 620), (190, 300), (172, 300)], fill=(85, 60, 40), outline=LINIE)
    for (x, y, r_, c) in ((180, 170, 120, (55, 110, 60)), (110, 220, 85, (45, 95, 50)), (250, 215, 90, (60, 120, 65)),
                          (180, 90, 85, (70, 130, 70)), (130, 130, 70, (50, 105, 55)), (235, 135, 70, (65, 125, 65))):
        d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=c, outline=(30, 60, 35), width=3)
    return im.rotate(sway, resample=Image.BICUBIC, center=(180, 610))


def kappe():
    im = Image.new('RGBA', (130, 80), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.chord([10, 5, 100, 95], 180, 360, fill=(30, 130, 120), outline=LINIE, width=4)
    d.pieslice([60, 30, 128, 60], 180, 360, fill=(25, 105, 95), outline=LINIE, width=4)
    return im


# --- Tafeln ---
def schatten_text(d, xy, t, f, fill=(255, 255, 255), anchor='la'):
    d.text((xy[0] + 2, xy[1] + 3), t, font=f, fill=(0, 0, 0, 150), anchor=anchor)
    d.text(xy, t, font=f, fill=fill, anchor=anchor)


# --- Reliefkarte des Odenwaldkreises (Bildschirm im Studio) ---
ORTE_KARTE = [('Breuberg', 49.818, 9.040, 'r'), ('Höchst', 49.799, 8.994, 'l'), ('Bad König', 49.743, 9.006, 'r'),
              ('Mossautal', 49.667, 8.937, 'l'), ('Michelstadt', 49.678, 9.004, 'r'), ('Oberzent', 49.567, 8.976, 'r')]
RELIEF = os.path.join(ROOT, 'data', 'odenwald-relief.png')
GRENZE = os.path.join(ROOT, 'data', 'odenwald-grenze.json')


def relief_ausschnitt(breite, hoehe, blau=False):
    """Reliefkarte auf die echte Kreisgrenze zugeschnitten (kein Rechteck) – gibt Bild und Grenzlinie zurück."""
    G = json.load(open(os.path.join(ROOT, 'data', 'odenwald-relief.json'), encoding='utf-8'))
    (lo0, lo1), (la0, la1) = G['lo'], G['la']
    pts = json.load(open(GRENZE, encoding='utf-8'))['punkte']
    xy = [((lo - lo0) / (lo1 - lo0) * breite, (la1 - la) / (la1 - la0) * hoehe) for lo, la in pts]
    rel = Image.open(RELIEF).convert('RGB').resize((breite, hoehe), Image.LANCZOS)
    if blau:
        rel = Image.alpha_composite(rel.convert('RGBA'), Image.new('RGBA', rel.size, (40, 60, 120, 90))).convert('RGB')
    maske = Image.new('L', (breite, hoehe), 0)
    ImageDraw.Draw(maske).polygon(xy, fill=255)
    aus = rel.convert('RGBA'); aus.putalpha(maske)
    return aus, xy


def kreiskarte(orte, tag, nacht=False, bis=None):
    """Karte des Odenwaldkreises mit den Werten je Ort. nacht=True: Tiefstwerte, Frost blau hervorgehoben.
    bis = wie viele Orte schon eingeblendet sind (für das Nacheinander-Erscheinen)."""
    KW, KH = 332, 537
    kopf = 74
    w, h = 452, kopf + KH + 36
    KX = (w - KW) // 2
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    farbe = (35, 70, 140) if nacht else (25, 85, 160)
    dr.rounded_rectangle([0, 0, w, h], radius=28, fill=(255, 255, 255, 238))
    dr.rounded_rectangle([0, 0, w, kopf], radius=28, fill=farbe + (255,)); dr.rectangle([0, 46, w, kopf], fill=farbe + (255,))
    dr.text((w / 2, 37), 'HEUTE NACHT' if nacht else 'MORGEN IM KREIS', font=F(34), fill=(255, 255, 255), anchor='mm')
    try:
        rel, rand = relief_ausschnitt(KW, KH, blau=nacht)
        im.alpha_composite(rel, (KX, kopf + 6))
        dr.line([(KX + x, kopf + 6 + y) for x, y in rand] + [(KX + rand[0][0], kopf + 6 + rand[0][1])],
                fill=(70, 85, 105, 255), width=3, joint='curve')
    except Exception as e:
        print('Reliefkarte nicht gezeichnet:', e)
    G = json.load(open(os.path.join(ROOT, 'data', 'odenwald-relief.json'), encoding='utf-8'))
    (lo0, lo1), (la0, la1) = G['lo'], G['la']
    f, fk = F(27), F(20, False)
    for n, (name, la, lo, seite) in enumerate(ORTE_KARTE):
        if bis is not None and n >= bis: continue
        d = (orte.get(name) or [None])[tag] if orte.get(name) and tag < len(orte[name]) else None
        if not d: continue
        x = KX + (lo - lo0) / (lo1 - lo0) * KW
        y = kopf + 6 + (la1 - la) / (la1 - la0) * KH
        wert = d.get('tmin_kalt', d['tmin']) if nacht else d['tmax']
        frost = nacht and wert <= 0
        bg = (40, 90, 190) if frost else (25, 45, 85) if nacht else (210, 85, 35)
        txt = '%d°' % wert
        bw_ = max(dr.textlength(name, font=fk), dr.textlength(txt, font=f)) + 24
        bx = x + 14 if seite == 'r' else x - 14 - bw_
        bx = max(3, min(bx, w - bw_ - 3))
        by = max(kopf + 4, min(y - 28, h - 92))
        dr.rounded_rectangle([bx, by, bx + bw_, by + 58], radius=13, fill=bg + (245,))
        dr.text((bx + bw_ / 2, by + 16), name, font=fk, fill=(235, 240, 250), anchor='mm')
        dr.text((bx + bw_ / 2, by + 40), txt, font=f, fill=(255, 255, 255), anchor='mm')
        dr.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 255, 255), outline=(30, 40, 60), width=3)
        if frost: dr.text((bx + bw_ - 7, by + 5), '*', font=F(28), fill=(190, 225, 255), anchor='mm')
    dr.text((w / 2, h - 19), '* Frost  ·  Tiefstwerte' if nacht else 'Höchstwerte im Odenwaldkreis', font=F(20, False), fill=(105, 120, 142), anchor='mm')
    return im


def karten_folge(orte, tag, nacht=False):
    """Bildfolge: die Orte erscheinen nacheinander."""
    return [kreiskarte(orte, tag, nacht, bis=k) for k in range(1, len(ORTE_KARTE) + 1)]


def tafel_tag(titel, d):
    w, h = 400, (565 if d.get('hoch') else 520)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w, h], radius=28, fill=(255, 255, 255, 238))
    dr.rounded_rectangle([0, 0, w, 74], radius=28, fill=(25, 85, 160, 255)); dr.rectangle([0, 46, w, 74], fill=(25, 85, 160, 255))
    dr.text((w / 2, 37), titel, font=F(38), fill=(255, 255, 255), anchor='mm')
    dr.text((w / 2, 104), '%s, %d. %s' % (TAGE[d['datum'].weekday()], d['datum'].day, MONATE[d['datum'].month - 1]), font=F(24, False), fill=(100, 115, 135), anchor='mm')
    dr.rounded_rectangle([90, 130, w - 90, 290], radius=26, fill=(120, 175, 225))
    icon(dr, w / 2, 200, 130, d['code'])
    dr.text((w / 2 - 20, 345), '%d°' % d['tmax'], font=F(88), fill=(230, 100, 40), anchor='rm')
    dr.text((w / 2 + 20, 352), '%d°' % d['tmin'], font=F(58), fill=(60, 120, 200), anchor='lm')
    dr.text((w / 2, 425), wort(d['code']).capitalize(), font=F(32), fill=(35, 50, 70), anchor='mm')
    dr.text((w / 2, 470), ('Regen %d %%  ·  Böen %d km/h' % (d['rp'], round(d['boe']))), font=F(22, False), fill=(90, 105, 125), anchor='mm')
    if d.get('hoch'):
        H = d['hoch']
        dr.text((w / 2, 515), 'Höhen: %d° / %d°%s' % (H['tmax'], H['tmin'], '  ·  Schnee' if H['schnee'] else ''), font=F(26), fill=(57, 73, 171), anchor='mm')
    return im


def tafel_wochenende(tage):
    w, h = 420, 470
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w, h], radius=28, fill=(255, 255, 255, 238))
    dr.rounded_rectangle([0, 0, w, 74], radius=28, fill=(40, 130, 80, 255)); dr.rectangle([0, 46, w, 74], fill=(40, 130, 80, 255))
    dr.text((w / 2, 37), 'WOCHENENDE', font=F(36), fill=(255, 255, 255), anchor='mm')
    for k, d in enumerate(tage):
        x = w / 4 + k * w / 2
        dr.text((x, 110), TAGE[d['datum'].weekday()][:2].upper(), font=F(34), fill=(40, 130, 80), anchor='mm')
        dr.rounded_rectangle([x - 80, 140, x + 80, 270], radius=22, fill=(120, 175, 225))
        icon(dr, x, 200, 100, d['code'])
        dr.text((x, 320), '%d°' % d['tmax'], font=F(64), fill=(230, 100, 40), anchor='mm')
        dr.text((x, 380), '%d°' % d['tmin'], font=F(40), fill=(60, 120, 200), anchor='mm')
        dr.text((x, 425), 'Regen %d %%' % d['rp'], font=F(22, False), fill=(90, 105, 125), anchor='mm')
    dr.line([w / 2, 100, w / 2, 440], fill=(220, 228, 235), width=3)
    return im


def tafel_text(kopf, zeilen, farbe):
    w = 440
    f = F(30); dr0 = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines = []
    for z in zeilen:
        cur = ''
        for wd in z.split():
            if dr0.textlength((cur + ' ' + wd).strip(), font=f) > w - 50: lines.append(cur); cur = wd
            else: cur = (cur + ' ' + wd).strip()
        lines.append(cur)
    h = 100 + len(lines) * 42 + 20
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w, h], radius=28, fill=(255, 255, 255, 238))
    dr.rounded_rectangle([0, 0, w, 74], radius=28, fill=farbe + (255,)); dr.rectangle([0, 46, w, 74], fill=farbe + (255,))
    dr.text((w / 2, 37), kopf, font=F(34), fill=(255, 255, 255), anchor='mm')
    for k, l in enumerate(lines):
        dr.text((25, 100 + k * 42), l, font=f, fill=(35, 50, 70))
    return im


# ---------------------------------------------------------------------
#  Wettergrafiken für die Tafel: bauen sich von links nach rechts auf
#  (Bild.info['leer'] = Tafel ohne Inhalt, Bild.info['bereich'] = aufzudeckender Bereich)
# ---------------------------------------------------------------------
GW, GH = 440, 540


def _grafik_rahmen(kopf, farbe, unter):
    im = Image.new('RGBA', (GW, GH), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, GW, GH], radius=28, fill=(255, 255, 255, 238))
    dr.rounded_rectangle([0, 0, GW, 74], radius=28, fill=farbe + (255,)); dr.rectangle([0, 46, GW, 74], fill=farbe + (255,))
    dr.text((GW / 2, 37), kopf, font=F(30), fill=(255, 255, 255), anchor='mm')
    dr.text((GW / 2, 100), unter, font=F(21, False), fill=(100, 115, 135), anchor='mm')
    return im, dr


def _fertig(leer, voll, x0, x1, y0=118, y1=GH - 8):
    voll.info['leer'] = leer; voll.info['bereich'] = (x0, y0, x1, y1)
    return voll


def tafel_zeigen(tf, seit, dauer=1.4):
    """Grafik-Tafel schrittweise aufdecken (seit = Sekunden seit Erscheinen)."""
    if 'leer' not in tf.info or seit >= dauer: return tf
    x0, y0, x1, y1 = tf.info['bereich']
    q = max(0.0, seit / dauer); q = 1 - (1 - q) ** 2
    xr = int(x0 + (x1 - x0) * q)
    out = tf.info['leer'].copy()
    if xr > x0: out.paste(tf.crop((x0, y0, xr, y1)), (x0, y0))
    return out


def _datum_txt(d): return '%s, %d. %s' % (TAGE[d['datum'].weekday()], d['datum'].day, MONATE[d['datum'].month - 1])


def tafel_temperatur(d, titel='HEUTE', von=6, bis=23):
    st = [x for x in d.get('stunden') or [] if von <= x['h'] <= bis]
    if len(st) < 6: return None
    im, dr = _grafik_rahmen('TEMPERATUR ' + titel, (230, 100, 40), _datum_txt(d) + ' · Bad König')
    x0, x1, y0, y1 = 48, GW - 28, 150, 385
    ts = [x['t'] for x in st]; lo, hi = math.floor(min(ts)) - 1, math.ceil(max(ts)) + 1
    if hi - lo < 6: m_ = (hi + lo) / 2; lo, hi = math.floor(m_ - 3), math.ceil(m_ + 3)
    def X(h): return x0 + (x1 - x0) * (h - von) / (bis - von)
    def Y(t): return y1 - (y1 - y0) * (t - lo) / (hi - lo)
    schritt = 2 if hi - lo <= 10 else 4
    for v in range(int(lo), int(hi) + 1):   # Hilfslinien
        if v % schritt: continue
        dr.line([x0, Y(v), x1, Y(v)], fill=(225, 230, 238), width=1)
        dr.text((x0 - 8, Y(v)), '%d°' % v, font=F(16, False), fill=(130, 140, 155), anchor='rm')
    if lo < 0 < hi: dr.line([x0, Y(0), x1, Y(0)], fill=(120, 170, 230), width=2)   # Frostlinie
    for x in st:
        if x['h'] % 3 == 0: dr.text((X(x['h']), 505), '%d' % x['h'], font=F(18, False), fill=(110, 120, 135), anchor='mm')
    leer = im.copy()
    pts = [(X(x['h']), Y(x['t'])) for x in st]
    fl = Image.new('RGBA', im.size, (0, 0, 0, 0)); fd = ImageDraw.Draw(fl)
    fd.polygon(pts + [(pts[-1][0], y1), (pts[0][0], y1)], fill=(245, 150, 70, 70))
    im.alpha_composite(fl); dr = ImageDraw.Draw(im)
    for a, b in zip(pts, pts[1:]):
        t_ = (a[1] + b[1]) / 2; kalt = Y(0) if lo < 0 < hi else None
        dr.line([a, b], fill=(60, 120, 200) if kalt and t_ > kalt else (230, 100, 40), width=6)
    kmax = max(range(len(st)), key=lambda k: st[k]['t']); kmin = min(range(len(st)), key=lambda k: st[k]['t'])
    for k, x in enumerate(st):
        px, py = pts[k]
        if x['h'] % 3 == 0 or k in (kmax, kmin):
            hv = k == kmax
            dr.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(255, 255, 255), outline=(230, 100, 40) if hv or k != kmin else (60, 120, 200), width=4)
        if k in (kmax, kmin):
            dr.text((px, py - 26 if k == kmax else py + 26), '%d°' % round(x['t']), font=F(24),
                    fill=(230, 100, 40) if k == kmax else (60, 120, 200), anchor='mm', stroke_width=3, stroke_fill=(255, 255, 255))
    for x in st:   # Wettersymbole alle 3 Stunden
        if x['h'] % 3 == 0: icon(dr, X(x['h']), 440, 44, x['code'])
    return _fertig(leer, im, x0 - 10, x1 + 12)


def tafel_regen(d, titel='HEUTE', von=6, bis=23):
    st = [x for x in d.get('stunden') or [] if von <= x['h'] <= bis]
    if len(st) < 6: return None
    summe = sum(x['mm'] for x in st)
    im, dr = _grafik_rahmen('REGEN ' + titel, (40, 110, 200), _datum_txt(d) + ' · je Stunde')
    x0, x1, y0, y1 = 48, GW - 24, 150, 420
    for v in (0, 25, 50, 75, 100):
        y = y1 - (y1 - y0) * v / 100
        dr.line([x0, y, x1, y], fill=(225, 230, 238), width=1)
        dr.text((x0 - 8, y), '%d%%' % v, font=F(15, False), fill=(130, 140, 155), anchor='rm')
    bw = (x1 - x0) / len(st)
    for k, x in enumerate(st):
        if x['h'] % 3 == 0: dr.text((x0 + bw * (k + 0.5), 445), '%d' % x['h'], font=F(18, False), fill=(110, 120, 135), anchor='mm')
    leer = im.copy()
    for k, x in enumerate(st):
        p = x['rp']; xa = x0 + bw * k + 2; xb = xa + bw - 4
        y = y1 - (y1 - y0) * p / 100
        c = (150, 190, 235) if p < 30 else (70, 140, 220) if p < 60 else (30, 85, 175)
        if p > 0: dr.rounded_rectangle([xa, y, xb, y1], radius=4, fill=c)
        if x['mm'] >= 0.3 and x['h'] % 3 == 0: dr.text(((xa + xb) / 2, y - 12), ('%.1f' % x['mm']).replace('.', ','), font=F(13), fill=(30, 85, 175), anchor='mm')
    fazit = 'Bleibt trocken' if max(x['rp'] for x in st) < 20 and summe < 0.2 else 'Zusammen ca. %s l/m²' % ('%.1f' % summe).replace('.', ',') if summe >= 0.2 else 'Kaum Regen erwartet'
    dr.text((GW / 2, 490), fazit, font=F(26), fill=(30, 85, 175), anchor='mm')
    return _fertig(leer, im, x0 - 4, x1 + 4)


def tafel_wind(d, titel='HEUTE', von=6, bis=23):
    st = [x for x in d.get('stunden') or [] if von <= x['h'] <= bis]
    if len(st) < 6: return None
    im, dr = _grafik_rahmen('WINDBÖEN ' + titel, (90, 95, 120), _datum_txt(d) + ' · km/h')
    x0, x1, y0, y1 = 48, GW - 24, 150, 420
    top = max(80, (max(x['boe'] for x in st) // 20 + 1) * 20)
    for v in range(0, top + 1, 20):
        y = y1 - (y1 - y0) * v / top
        dr.line([x0, y, x1, y], fill=(225, 230, 238), width=1)
        dr.text((x0 - 8, y), str(v), font=F(15, False), fill=(130, 140, 155), anchor='rm')
    y60 = y1 - (y1 - y0) * 60 / top
    dr.line([x0, y60, x1, y60], fill=(220, 60, 60), width=2); dr.text((x1, y60 - 12), 'Sturmböen', font=F(15), fill=(200, 40, 40), anchor='rm')
    bw = (x1 - x0) / len(st)
    for k, x in enumerate(st):
        if x['h'] % 3 == 0: dr.text((x0 + bw * (k + 0.5), 445), '%d' % x['h'], font=F(18, False), fill=(110, 120, 135), anchor='mm')
    leer = im.copy()
    for k, x in enumerate(st):
        b = x['boe']; xa = x0 + bw * k + 2; xb = xa + bw - 4; y = y1 - (y1 - y0) * b / top
        c = (120, 190, 140) if b < 40 else (240, 180, 50) if b < 60 else (220, 60, 60)
        dr.rounded_rectangle([xa, y, xb, y1], radius=4, fill=c)
    km = max(st, key=lambda x: x['boe'])
    dr.text((GW / 2, 490), 'Stärkste Böen: %d km/h (%d Uhr)' % (km['boe'], km['h']), font=F(22), fill=(70, 75, 95), anchor='mm')
    return _fertig(leer, im, x0 - 4, x1 + 4)


def grafik_saetze(d, grafiken, rnd, wann='heute'):
    """Max erklärt die Grafiken – so bleibt jede Tafel lange genug stehen."""
    st = [x for x in d.get('stunden') or [] if 6 <= x['h'] <= 23]
    if len(st) < 6: return ''
    out = []
    if 'temp' in grafiken:
        hi = max(st, key=lambda x: x['t']); lo = min(st, key=lambda x: x['t'])
        out.append(rnd.choice(['Schaut mal auf die Temperaturkurve: ', 'Hier seht ihr den Verlauf über den Tag: ', 'Die Kurve zeigt es: '])
                   + 'Am wärmsten wird es %s gegen %d Uhr mit etwa %s Grad, am kühlsten ist es um %d Uhr mit %s Grad.'
                   % (wann, hi['h'], zahl(hi['t']), lo['h'], zahl(lo['t'])))
    if 'regen' in grafiken:
        nass = [x for x in st if x['rp'] >= 30]
        if not nass and max(x['rp'] for x in st) < 10:
            out.append('Bei den Regenbalken sieht es gut aus: Es bleibt trocken.')
        elif nass:
            out.append('Bei den Regenbalken seht ihr: Am ehesten gibt es Niederschlag zwischen %d und %d Uhr, da liegt das Risiko bei bis zu %d Prozent.'
                       % (nass[0]['h'], nass[-1]['h'] + 1, max(x['rp'] for x in nass)))
        else:
            out.append('Das Regenrisiko bleibt über den Tag gering, höchstens %d Prozent.' % max(x['rp'] for x in st))
    if 'wind' in grafiken:
        km = max(st, key=lambda x: x['boe'])
        out.append('Und beim Wind: Die stärksten Böen kommen gegen %d Uhr mit bis zu %d Kilometern pro Stunde.' % (km['h'], km['boe']))
    return ' ' + ' '.join(out)


def grafiken_fuer(s):
    """Tafel-Folge für einen Abschnitt mit s['grafiken'] (erst die normale Tafel, dann die Grafiken)."""
    aus = []
    d = s.get('tag')
    for g in s.get('grafiken') or []:
        try:
            im = (tafel_temperatur(d, s.get('titel', '')) if g == 'temp' else tafel_regen(d, s.get('titel', '')) if g == 'regen'
                  else tafel_wind(d, s.get('titel', '')) if g == 'wind' else None)
        except Exception as e:
            print('Grafik %s nicht möglich: %s' % (g, e)); im = None
        if im is not None: aus.append(im); s.setdefault('grafik_namen', []).append(g)
    return aus


GRAFIK_ANFANG = {'temp': ('Schaut mal auf die Temperaturkurve', 'Hier seht ihr den Verlauf über den Tag', 'Die Kurve zeigt es'),
                 'regen': ('Bei den Regenbalken', 'Das Regenrisiko bleibt'),
                 'wind': ('Und beim Wind:',)}


def grafik_zeiten(s):
    """Startzeit (Sek. im Abschnitt) je Grafik = Moment, in dem Max den passenden Satz beginnt.
    None, wenn ein Satz nicht gefunden wird (dann gleichmäßige Verteilung wie bisher)."""
    txt = s['text']; w = s.get('woerter') or []; n_txt = max(1, len(txt.split()))
    zeiten = []
    for g in s.get('grafik_namen') or []:
        pos = min([txt.find(a) for a in GRAFIK_ANFANG.get(g, ()) if txt.find(a) >= 0] or [-1])
        if pos < 0: return None
        nw = len(txt[:pos].split())
        if w: t_ = w[min(nw, len(w) - 1)][0] if nw < len(w) else w[-1][0]
        else: t_ = (s['dauer'] - 0.6) * nw / n_txt
        zeiten.append(max(1.5, t_ - 0.3))   # kurz bevor er den Satz beginnt
    if any(b <= a for a, b in zip(zeiten, zeiten[1:])): return None
    return zeiten


def kurz(t, n=95):
    return t if len(t) <= n else t[:n].rsplit(' ', 1)[0] + ' …'


def tafel_fuer(s, special):
    if s.get('tafel_img') is not None: return s['tafel_img']
    if s['art'] == 'tag': return tafel_tag(s['titel'], s['tag'])
    if s['art'] == 'wochenende': return tafel_wochenende(s['tage'])
    if s['art'] == 'woche': return tafel_text('DIE NEUE WOCHE', s['zeilen'], (40, 130, 80))
    if s['art'] == 'tipp':
        t_ = s['text'].split(': ', 1)[-1]
        return tafel_text('MAX\' FREIZEIT-TIPP', [kurz(t_.split('. ')[0].rstrip('.!') + ('' if t_.split('. ')[0][-1:] in '.!' else '.'), 110)], (230, 130, 30))
    if s['art'] == 'special': return tafel_text('⚠ WETTER-SPECIAL'.replace('⚠ ', ''), [kurz(s.get('karte', s['text']), 120)], (200, 40, 40))
    if s['art'] == 'wissen': return tafel_text('WETTER-WISSEN', [kurz(s.get('titel_w', ''), 80)], (215, 160, 20))
    if s['art'] == 'frage': return tafel_text('💬 SCHREIBT UNS!'.replace('💬 ', ''), [kurz(s['frage'], 120)], (254, 44, 85))
    if s['art'] == 'cta': return tafel_text('FOLGST DU UNS?', ['+ Folgen', '❤ Liken', '↻ Teilen', 'auf Facebook & Instagram'], (24, 119, 242))
    if s['art'] == 'outro': return tafel_text('LIVE IM NETZ', ['wetter-badkoenig.de', 'Station Bad König · 184,5 m', 'Wetter für den ganzen Odenwald'], (25, 85, 160))
    return None


def kopfband(heute, special, titel=None):
    im = Image.new('RGBA', (W, 170), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    farbe = (200, 40, 40, 235) if special else (40, 30, 100, 235) if titel else (20, 60, 120, 230)
    dr.rectangle([0, 30, W, 120], fill=farbe)
    dr.rectangle([0, 120, W, 128], fill=(245, 175, 40, 255))
    schatten_text(dr, (28, 75), titel or ('WETTER-SPECIAL' if special else 'ODENWALD-WETTER'), F(40), anchor='lm')
    jetzt = dt.datetime.now(ZoneInfo('Europe/Berlin'))
    dr.text((W - 30, 60), '%d.%d.%d' % (heute.day, heute.month, heute.year), font=F(24, False), fill=(230, 238, 250), anchor='rm')
    dr.text((W - 30, 93), jetzt.strftime('%H:%M') + ' Uhr', font=F(22, False), fill=(200, 215, 240), anchor='rm')
    dr.text((30, 150), 'Private Wetterstation Bad König', font=F(22), fill=(255, 255, 255), anchor='lm', stroke_width=3, stroke_fill=(20, 40, 70))
    return im


def untertitel_bild(t):
    f = F(30); dr0 = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines, cur = [], ''
    for wd in t.split():
        if dr0.textlength((cur + ' ' + wd).strip(), font=f) > W - 80: lines.append(cur); cur = wd
        else: cur = (cur + ' ' + wd).strip()
    lines.append(cur)
    h = 26 + 40 * len(lines)
    im = Image.new('RGBA', (W - 40, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, W - 40, h], radius=18, fill=(10, 20, 35, 200))
    for k, l in enumerate(lines):
        dr.text(((W - 40) / 2, 13 + 20 + 40 * k), l, font=f, fill=(255, 255, 255), anchor='mm')
    return im


# =====================================================================
#  3) Stimme
# =====================================================================
def sprechtext(t):
    """Text für die Stimme natürlicher machen (Untertitel bleiben unverändert)."""
    for a, b in (('wetter-badkoenig.de', 'wetter bad könig punkt d e'), ('°C', ' Grad'), ('km/h', 'Kilometer pro Stunde'),
                 ('l/m²', 'Liter pro Quadratmeter'), ('z. B.', 'zum Beispiel'), ('ca.', 'circa'), (' – ', ', '), ('!', '! '), ('Ei gude', 'Ei gude,')):
        t = t.replace(a, b)
    t = t.replace('Ei gude,,', 'Ei gude,').replace('Ei gude, wie', 'Ei gude wie')
    return ' '.join(t.split())


TEMPO = {'rueck': '+1%', 'rueckblick': '+1%', 'wissen': '+2%', 'special': '-6%', 'tag': '+0%', 'wochenende': '+2%', 'woche': '+2%', 'tipp': '+5%', 'intro': '+4%', 'outro': '+3%'}


def sprich(text, pfad, rate='+2%', woerter=None):
    """Sprachausgabe; woerter (Liste) bekommt die Wortzeiten (start, ende, wort) für die Lippensynchronität."""
    text = sprechtext(text)
    try:
        import edge_tts
        async def go():
            try: c = edge_tts.Communicate(text, VOICE, rate=rate, boundary='WordBoundary')
            except TypeError: c = edge_tts.Communicate(text, VOICE, rate=rate)
            n = 0
            with open(pfad, 'wb') as f:
                async for ch in c.stream():
                    if ch['type'] == 'audio': f.write(ch['data']); n += 1
                    elif ch['type'] == 'WordBoundary' and woerter is not None:
                        woerter.append((ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7, ch['text']))
            if not n: raise RuntimeError('keine Audiodaten')
        try:
            asyncio.run(go())
        except Exception as e:   # Rückfall: Stimme ohne Wortzeiten wie früher (Mundbilder dann aus dem Text verteilt)
            print('Wortzeiten nicht verfügbar (%s) – Stimme ohne Wortzeiten.' % e)
            if woerter is not None: woerter.clear()
            asyncio.run(edge_tts.Communicate(text, VOICE, rate=rate).save(pfad))
        return True
    except Exception as e:
        print('Sprachausgabe nicht verfügbar (%s) – stumme Testspur.' % e)
        dauer = max(2.5, len(text) / 15)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '%.2f' % dauer, pfad], check=True)
        return False


def dauer(p):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).decode().strip())


def pegel(wav, n_frames):
    raw = subprocess.check_output(['ffmpeg', '-loglevel', 'error', '-i', wav, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'])
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    per = 16000 // FPS
    out = []
    for i in range(n_frames):
        c = a[i * per:(i + 1) * per]
        out.append(float(np.sqrt(np.mean(c * c))) if len(c) else 0.0)
    out = np.array(out)
    if out.max() > 0: out = out / np.percentile(out[out > 0], 90)
    return out


# =====================================================================
#  4) Video zusammensetzen
# =====================================================================
def baue(segmente, heute, ziel, special, titel=None):
    tmp = tempfile.mkdtemp()
    seed = int(heute.strftime('%Y%m%d'))
    WEIHNACHT[0] = weihnachtszeit(heute)
    bgs = hintergruende(seed)
    eigene = [k for k in bgs if k.startswith('eigen') and saison_ok(EIGEN_NAME.get(k, ''), heute)]
    land = [k for k in bgs if k.startswith('land_') and heute.month in LAND_SAISON.get(k[5:], ())]   # gezeichnete Odenwald-Szenen der Jahreszeit
    WETTERBILD = ('schnee', 'nebel', 'regen', 'schauer', 'gewitter', 'sturm', 'frost')   # Wetterbilder nur bei passender Lage
    pool = [e for e in eigene if not EIGEN_NAME.get(e, '').startswith(WETTERBILD)] + land
    echt = True
    # Audio je Abschnitt
    for i, s in enumerate(segmente):
        p = os.path.join(tmp, 's%02d.mp3' % i)
        s['woerter'] = []
        echt = sprich(s['text'], p, TEMPO.get(s['art'], '+2%'), s['woerter']) and echt
        s['dauer'] = dauer(p) + 0.6
        s['audio'] = p
    liste = os.path.join(tmp, 'liste.txt')
    with open(liste, 'w') as f:
        for s in segmente:
            pad = s['audio'].replace('.mp3', '_p.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', s['audio'], '-af', 'apad=pad_dur=0.6', '-ar', '24000', '-ac', '1', pad], check=True)
            f.write("file '%s'\n" % pad)
    ton = os.path.join(tmp, 'ton.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', liste, '-c', 'copy', ton], check=True)
    gesamt = sum(s['dauer'] for s in segmente) + 0.8
    N = int(gesamt * FPS)
    lv = pegel(ton, N)
    try: rund = rundheit(ton, N)
    except Exception as e: print('Mundform-Analyse übersprungen:', e); rund = np.zeros(N, dtype=bool)
    if not echt:  # Testmodus: künstliche Sprechbewegung
        lv = np.array([max(0, 0.8 + 0.7 * math.sin(i * 1.7) * math.sin(i * 0.23)) for i in range(N)]); rund = np.array([(i // 7) % 5 == 0 for i in range(N)])
    # Hintergrundmusik (Pixabay, Sonican – lizenzfrei): leise darunter, bei Sprache zusätzlich abgesenkt
    musik = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'video', 'musik', 'hintergrund.mp3')
    if os.path.exists(musik):
        mix = os.path.join(tmp, 'ton_mix.wav')
        fo = max(gesamt - 2.0, 0)
        fk = ('[0:a]aformat=sample_rates=44100:channel_layouts=stereo,apad,atrim=0:%.2f,asplit[v][sc];'
              '[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.03,afade=t=in:d=1.5,afade=t=out:st=%.2f:d=2,atrim=0:%.2f[m];'
              '[m][sc]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=500[md];'
              '[v][md]amix=inputs=2:duration=first:normalize=0' % (gesamt, fo, gesamt))
        try:
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', ton, '-stream_loop', '-1', '-i', musik,
                            '-filter_complex', fk, mix], check=True)
            ton = mix
        except Exception as e:
            print('Musik übersprungen:', e)

    # vorbereiten
    MODS = {}
    lk0 = next((look_fuer(s['tag']) for s in segmente if s.get('tag')), 'kuehl' if heute.month in (11, 12, 1, 2, 3) else 'normal')   # ohne Tageswerte (z. B. Jahresrückblick): nach Jahreszeit
    def mods_fuer(look, prop, st=False):
        if (look, prop, st) not in MODS: MODS[(look, prop, st)] = MaxFigur(look, prop, st, 1.2 if st else 0.92)
        return MODS[(look, prop, st)]
    FX_LOOK = {'frost': ('winter', None), 'nebel': ('kuehl', None), 'schnee': ('winter', 'schippe'), 'regen': ('regen', 'schirm'), 'schauer': ('regen', None), 'gewitter': ('regen', None), 'sturm': ('sturm', None)}
    BAEUME = [baum(a_) for a_ in range(-14, 15, 2)]
    KAPPE = kappe()
    STUDIO_DESK = studio_desk_overlay()
    kopf = kopfband(heute, special, titel)
    zeit = 0.0
    for k, s in enumerate(segmente):
        s['t0'] = zeit; zeit += s['dauer']
        bg = s['bg']
        fx = s.get('fx')
        if bg == 'auto': bg = 'hoehen'
        if bg != 'studio' and not fx and s['art'] in ('tipp', 'intro', 'outro'):   # passendes eigenes Bild zum genannten Ort / Advent
            treffer = bild_zum_text(s['text'], eigene, seed + k)
            if not treffer and s['art'] == 'intro': treffer = next((e for e in eigene if EIGEN_NAME[e].endswith('_advent')), None)
            if treffer: bg = treffer
        if bg == 'studio': fx = None   # im Studio keine Wetter-Effekte
        if fx and bg != 'schloss' or fx and s['art'] in ('tag', 'special'):
            bg = {'schnee': 'winter', 'frost': 'frost', 'nebel': 'land_nebel', 'regen': 'regen', 'schauer': 'hoehen', 'gewitter': 'gewitter', 'sturm': 'sturm'}[fx]
            passend = [e for e in eigene if EIGEN_NAME[e].startswith(fx)]   # eigenes Stimmungsbild (z. B. schnee-…, nebel-…) bevorzugen
            if passend: bg = passend[(seed + k) % len(passend)]
        elif bg != 'studio' and s['art'] == 'tag' and s.get('tag') and s['tag']['code'] in (45, 48) and any(EIGEN_NAME[e].startswith('nebel') for e in eigene):
            nb = [e for e in eigene if EIGEN_NAME[e].startswith('nebel')]; bg = nb[(seed + k) % len(nb)]   # Nebeltag
        elif WEIHNACHT[0] and bg in ('wald', 'hoehen'):   # Adventszeit: eigene Advents-Bilder oder Lichterketten-Landschaft
            adv = [e for e in eigene if EIGEN_NAME.get(e, '').endswith('_advent')]
            bg = adv[(k + seed) % len(adv)] if adv and k % 2 else ('advent_schnee' if lk0 == 'winter' else 'advent')
        elif pool and bg in ('wald', 'hoehen'): bg = pool[(k + seed) % len(pool)]
        s['look'], s['prop'] = FX_LOOK.get(fx, (lk0, None))
        if s['look'] == 'regen' and s['prop'] is None and fx == 'regen': s['prop'] = 'schirm'
        s['bgimg'] = bgs[bg]
        s['bg_key'] = bg
        if bg == 'studio': s['look'], s['prop'] = 'normal', None   # drinnen: Softshell, keine Mütze, kein Schirm
        s['tafel'] = s['tafel_seq'][-1] if s.get('tafel_seq') else tafel_fuer(s, special)
        if s.get('grafiken') and s['tafel'] is not None:   # Wettergrafiken: Tafeln wechseln, während Max spricht
            gr_ = grafiken_fuer(s)
            if gr_: s['tafel_seq'] = [s['tafel']] + gr_; s['tafel_wechsel'] = True; s['grafik_t'] = grafik_zeiten(s)
        # Untertitel: Sätze, Zeit nach Zeichenanzahl verteilt
        saetze, cur = [], ''
        for teil in s['text'].replace('! ', '!|').replace('. ', '.|').replace('? ', '?|').split('|'):
            if len(cur) + len(teil) < 70: cur = (cur + ' ' + teil).strip()
            else:
                if cur: saetze.append(cur)
                cur = teil
        if cur: saetze.append(cur)
        ges = sum(len(x) for x in saetze); t = s['t0']; s['ut'] = []
        for x in saetze:
            d_ = (s['dauer'] - 0.35) * len(x) / ges
            s['ut'].append((t, t + d_, untertitel_bild(x))); t += d_
        s['partikel'] = fx

    rnd = random.Random(1)
    tropfen = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(14, 26)) for _ in range(110)]
    flocken = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(2, 5), rnd.uniform(0, 6)) for _ in range(140)]
    blaetter = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(6, 11), rnd.uniform(0, 6), rnd.choice([(200, 120, 30), (170, 70, 30), (220, 170, 40)])) for _ in range(40)]
    blitze = [rnd.uniform(0, 1) for _ in range(50)]

    ANIM = MaxAnimation(lv, rund, seed, segmente)
    erstes_intro = next((x for x in segmente if x['art'] == 'intro'), None)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-i', ton, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '27', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '96k', '-af', 'apad', '-shortest', '-movflags', '+faststart', ziel], stdin=subprocess.PIPE)
    for i in range(N):
        t = i / FPS
        s = next((x for x in segmente if x['t0'] <= t < x['t0'] + x['dauer']), segmente[-1])
        lt = t - s['t0']; p = min(1, lt / max(1, s['dauer']))
        # Hintergrund mit langsamer Kamerafahrt
        studio = s.get('bg_key') == 'studio'
        bgi = s['bgimg']; bw, bh = bgi.size
        sc = 1.0 if studio else 1.0 + 0.06 * p
        cw, ch = int(W * bh / H / sc * (H / bh) * (bh / H)), 0
        cw = int(min(bw, bh * W / H) / sc); ch = int(cw * H / W)
        x0 = (bw - cw) // 2 if studio else int((bw - cw) * (0.15 + 0.7 * p)) if bw > cw + 10 else (bw - cw) // 2
        y0 = int((bh - ch) * 0.4) if not studio else 0
        fr = bgi.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR).convert('RGBA')
        # Übergang: kurzes Einblenden aus Weiß
        if lt < 0.3 and i > 0:
            fr = Image.blend(Image.new('RGBA', (W, H), (255, 255, 255, 255)), fr, lt / 0.3)
        pk = s['partikel']
        if pk == 'sturm':    # Baum im Wind, rechts hinten
            sw = 12 * math.sin(t * 3.1) + 5 * math.sin(t * 7.3)
            bm = BAEUME[max(0, min(len(BAEUME) - 1, int(round((sw + 14) / 2))))]
            fr.alpha_composite(bm, (W - bm.width + 40, H - bm.height - 120))
        if pk == 'gewitter':  # Blitz: alle paar Sekunden kurzes Aufleuchten mit Blitzstrahl
            z = int(t / 2.7); ph = t - z * 2.7
            if blitze[z % len(blitze)] < 0.7 and ph < 0.22:
                rb = random.Random(z); bx = rb.uniform(W * 0.35, W * 0.9)
                fr = Image.blend(fr, Image.new('RGBA', (W, H), (255, 255, 240, 255)), 0.55 if ph < 0.08 else 0.2)
                pts = [(bx, 0)]
                for _ in range(7): pts.append((pts[-1][0] + rb.uniform(-45, 45), pts[-1][1] + rb.uniform(60, 110)))
                bd = ImageDraw.Draw(fr); bd.line(pts, fill=(255, 255, 200, 255), width=7); bd.line(pts, fill=(255, 255, 255, 255), width=3)
        dr = ImageDraw.Draw(fr)
        if pk in ('regen', 'gewitter', 'sturm'):
            schraeg = 260 if pk == 'sturm' else 120
            for (x, y, l) in tropfen:
                yy = (y + t * 900) % H; xx = (x - t * schraeg) % W
                dr.line([xx, yy, xx - 5 - schraeg / 40, yy + l], fill=(200, 215, 235, 200), width=2)
            for j_ in range(14):   # Spritzer am Boden
                sx = (j_ * 53 + int(t * 7) * 131) % W; sp_ = (t * 6 + j_ * 0.37) % 1
                dr.ellipse([sx - 6 * sp_ - 2, H - 175 - 3 * sp_, sx + 6 * sp_ + 2, H - 171 + 3 * sp_], outline=(220, 230, 245, int(200 * (1 - sp_))), width=2)
        if pk == 'sturm':    # herumwirbelnde Blätter
            for (x, y, r_, ph, c) in blaetter:
                xx = (x + t * 420) % W; yy = (y + 60 * math.sin(t * 2 + ph) + t * 40) % H
                dr.ellipse([xx - r_, yy - r_ / 2, xx + r_, yy + r_ / 2], fill=c + (230,))
        elif pk == 'frost':   # glitzernde Eiskristalle, kein Niederschlag
            for j_, (x, y, r_, ph) in enumerate(flocken[:60]):
                a_ = int(255 * max(0, math.sin(t * 3 + ph * 2)))
                if a_ > 60:
                    dr.line([x - r_ * 2, y, x + r_ * 2, y], fill=(255, 255, 255, a_), width=2)
                    dr.line([x, y - r_ * 2, x, y + r_ * 2], fill=(255, 255, 255, a_), width=2)
        elif pk == 'nebel':   # ziehende Nebelschleier
            for j_ in range(5):
                yy = 500 + j_ * 230; xx = ((t * 25 + j_ * 300) % (W + 600)) - 300
                dr.ellipse([xx - 500, yy - 90, xx + 500, yy + 90], fill=(235, 238, 242, 70))
            dr.rectangle([0, 0, W, H], fill=(230, 233, 238, 60))
        elif pk == 'schnee':
            for (x, y, r_, ph) in flocken:
                yy = (y + t * 60 * r_) % H; xx = (x + 20 * math.sin(t + ph)) % W
                dr.ellipse([xx - r_, yy - r_, xx + r_, yy + r_], fill=(255, 255, 255, 230))
        # Tafel: im Studio auf dem Bildschirm an der Wand, sonst rechts oben, schiebt sich herein
        tafel_seit = lt; tf_alt = None
        if s.get('tafel_wechsel'):   # Wettergrafiken: Tafeln wechseln gleichmäßig über den Abschnitt
            sq_ = s['tafel_seq']
            if s.get('grafik_t'):   # synchron: jede Grafik erscheint, wenn Max über sie spricht, und bleibt bis zur nächsten
                st_ = [0.0] + s['grafik_t']
                k_ = max(i_ for i_, a_ in enumerate(st_) if lt >= a_); tafel_seit = lt - st_[k_]
            else:
                schritt_ = max(4.0, (s['dauer'] - 0.6) / len(sq_))
                erst_ = max(2.5, (s['dauer'] - 0.6) - schritt_ * (len(sq_) - 1))   # Tageskarte bekommt den Rest
                if lt < erst_: k_, tafel_seit = 0, lt
                else: k_ = min(len(sq_) - 1, 1 + int((lt - erst_) / schritt_)); tafel_seit = lt - erst_ - (k_ - 1) * schritt_
            if k_ and tafel_seit < 0.3: tf_alt = sq_[k_ - 1]
            tf_wechsel = tafel_zeigen(sq_[k_], tafel_seit - 0.3 if k_ else tafel_seit)
        if s['tafel'] is not None and studio:
            tf = s['tafel']
            sq = s.get('tafel_seq')
            if s.get('tafel_wechsel'):
                tf = tf_wechsel if tf_alt is None else tf_alt
            elif sq:   # die Orte erscheinen nacheinander
                schritt = max(0.55, (s['dauer'] - 1.4) / len(sq))
                tf = sq[min(len(sq) - 1, int(lt / schritt))]
            scl = W / cw
            rx0, ry0, rx1, ry1 = STUDIO_SCREEN
            rfx0, rfy0 = (rx0 - x0) * scl, (ry0 - y0) * scl
            rfw, rfh = (rx1 - rx0) * scl, (ry1 - ry0) * scl
            fit = min(rfw / tf.width, rfh / tf.height) * 0.92
            tfr = tf.resize((max(1, int(tf.width * fit)), max(1, int(tf.height * fit))), Image.LANCZOS)
            ein = min(1, lt / 0.5)
            if s.get('tafel_wechsel'): ein = 1 - min(1, tafel_seit / 0.3) if tf_alt is not None else min(1, (tafel_seit - (0.3 if lt > 1 else 0)) / 0.3) if lt > 1 else min(1, lt / 0.5)
            ein = max(0.0, ein)
            if ein < 1: tfr = Image.blend(Image.new('RGBA', tfr.size, (0, 0, 0, 0)), tfr, ein)
            tx = int(rfx0 + (rfw - tfr.width) / 2); ty = int(rfy0 + (rfh - tfr.height) / 2)
            fr.alpha_composite(tfr, (tx, ty))
        elif s['tafel'] is not None:
            tf = s['tafel']; ein = min(1, lt / 0.45); ein = 1 - (1 - ein) ** 3
            if s.get('tafel_wechsel'):
                if tf_alt is not None:   # alte Tafel schiebt sich hinaus …
                    tf = tf_alt; ein = 1 - (tafel_seit / 0.3) ** 2
                else:                    # … die neue schiebt sich herein und baut sich auf
                    tf = tf_wechsel; e_ = tafel_seit - (0.3 if lt > 1 else 0); ein = min(1, max(0, e_) / 0.45); ein = 1 - (1 - ein) ** 3
            tx = int(W - tf.width - 24 + (1 - ein) * (tf.width + 40)); ty = 215
            fr.alpha_composite(tf, (tx, ty))
        # Moderator (links unten), Mund nach Lautstärke
        zeigt = 1 if s['tafel'] is not None and s['art'] in ('tag', 'wochenende', 'woche', 'special', 'rueckblick', 'frage') and (lt < 2.2 or s.get('tafel_wechsel') and 0.3 < tafel_seit < 1.9) else 0
        if s['art'] in ('intro', 'outro') and lt < 2.0: zeigt = 3
        elif s['art'] == 'cta' and (lt < 1.5 or lt > s['dauer'] - 2.5): zeigt = 3
        elif s['art'] == 'tipp' and 0.6 < lt < 2.6: zeigt = 2
        zst, xoff = ANIM.schritt(i, t, s, lt, zeigt, ernst=bool(special) and s['art'] in ('special', 'tag', 'intro'), studio=studio,
                                 prop=s['prop'], erster=s is erstes_intro and i < 3 * FPS + int(s['t0'] * FPS), special=bool(special))
        mm = mods_fuer(s['look'], s['prop'], studio).bild(**zst)
        bob = int(4 * math.sin(t * 2.2))
        if pk == 'sturm': bob += int(5 * math.sin(t * 9))   # Max wackelt im Wind
        mx, my = -20, H - mm.height - 150 + bob
        if studio: mx, my = 10, STUDIO_TISCH - int(mm.height * 0.70) + bob // 2   # Hüfte auf Tischhöhe: Max sitzt
        fr.alpha_composite(mm, (mx + int(xoff), my))
        if studio:
            fr.alpha_composite(STUDIO_DESK, (0, 0))
        if pk == 'sturm' and lt < 2.4:   # die Kappe fliegt ihm vom Kopf davon
            q = lt / 2.4
            kp = KAPPE.rotate(-q * 540, expand=True)
            fr.alpha_composite(kp, (int(mx + 120 + q * 700), int(my + 20 - 260 * q + 300 * q * q)))
        fr.alpha_composite(kopf, (0, 0))
        # Untertitel
        for (a, b_, img) in s['ut']:
            if a <= t < b_:
                fr.alpha_composite(img, (20, H - img.height - 40)); break
        ff.stdin.write(fr.convert('RGB').tobytes())
    ff.stdin.close(); ff.wait()
    return gesamt, echt


NASS_WORTE = ('Schirm', 'nass werden', 'wird es heute nass', 'wieder Regen', 'Regen ist vor allem', 'Mit Regen müsst', 'Wenn es regnet',
              'regnet es', 'Regnet es', 'kann es nass', 'Regenjacke', 'Schauer gibt es', 'schauern', 'Schauer möglich')
TROCKEN_WORTE = ('heute trocken', 'wieder trocken', 'Es bleibt trocken', 'bleibt es trocken', 'Dabei bleibt es meist trocken')


def pruefen(segs):
    """Selbstkontrolle vor dem Rendern: Passt jeder Satz über Regen zur Regen-Einstufung des Tages?
    Widersprüchliche Sätze werden entfernt (Grafik-Sätze bleiben, damit die Tafeln stimmen), dazu eine Push-Nachricht."""
    import re
    fehler = []
    for sg in segs:
        d = sg.get('tag')
        if not d or sg.get('art') == 'rueckblick': continue
        sf = stufe(d); schutz = tuple(a for v in GRAFIK_ANFANG.values() for a in v)
        saetze = re.split(r'(?<=[.!?])\s+', sg['text']); neu = []
        for x in saetze:
            falsch = (sf in ('trocken', 'vereinzelt') and any(w_ in x for w_ in NASS_WORTE) and not ('vereinzelt' in x or 'einzelner Schauer' in x or 'kurzer Schauer' in x)) \
                     or (sf == 'trocken' and 'Schauer' in x) \
                     or (sf in ('schauer', 'regen', 'gewitter') and any(w_ in x for w_ in TROCKEN_WORTE))
            if falsch and not x.startswith(schutz): fehler.append('%s (%s): „%s“' % (d['datum'], sf, x))
            else: neu.append(x)
        sg['text'] = ' '.join(neu)
    if fehler:
        print('Selbstkontrolle – entfernt:\n  ' + '\n  '.join(fehler))
        topic = os.environ.get('NTFY_TOPIC')
        if topic:
            try:
                import urllib.request
                urllib.request.urlopen(urllib.request.Request('https://ntfy.sh/' + topic, data=('Max-Video: %d widersprüchliche(r) Regen-Satz/Sätze entfernt – Video kommt trotzdem.\n' % len(fehler)
                                                                                            + '\n'.join(fehler))[:3000].encode('utf-8'),
                                                              headers={'Title': 'Max: Selbstkontrolle', 'Tags': 'umbrella'}), timeout=15)
            except Exception as e: print('Push nicht möglich:', e)
    return fehler


def main():
    daten = json.load(open(os.path.join(FB, 'daten.json'), encoding='utf-8'))
    days = [dict(d, datum=dt.date.fromisoformat(d['datum'])) for d in daten['tage']]
    # Videos = Odenwald-Wetter: Talwerte aus der Modellmischung für Breuberg, Höchst, Bad König, Michelstadt (wie die Odenwald-Vorhersage der Website)
    for d in days:
        T = d.get('tal')
        if T: d.update(tmax=T['tmax'], tmin=T['tmin'], code=T['code']); d.setdefault('frost_min', T.get('tmin_kalt', T['tmin']))
    warn = [' '.join(w_.capitalize() if w_.isupper() and len(w_) > 2 else w_ for w_ in x.split()) for x in (daten.get('warn') or [])]
    heute = days[0]['datum']
    nur_special = '--special' in sys.argv
    if nur_special:
        # Mittags/Nachmittags: nur wenn eine NEUE Warnung dazukommt
        alt = []
        for n in ('wetter.json', 'special.json'):
            try:
                j = json.load(open(os.path.join(FB, n), encoding='utf-8'))
                if j.get('datum') == heute.isoformat(): alt += j.get('warn', [])
            except Exception: pass
        neu = [w for w in warn if w not in alt]
        if not neu:
            print('Keine neue Warnung – kein Special.'); return
    wochen = '--woche' in sys.argv
    abends = '--abend' in sys.argv   # Abendvideo aus dem Studio (eigene Datei, kommt als „abends“ auch in die Videothek)
    segs = skript_abend(days, warn, heute, daten.get('orte') or {}) if abends else skript_woche(days, warn, heute) if wochen else skript(days, warn, heute, nur_special)
    pruefen(segs)
    special = nur_special   # das Morgenvideo ist immer das normale Video
    name = 'abendvideo' if abends else 'special' if nur_special else 'woche' if wochen else 'wetter'
    ziel = os.path.join(FB, name + '.mp4')
    gesamt, echt = baue(segs, heute, ziel, special, titel='WOCHENAUSBLICK' if wochen else 'ODENWALD AM ABEND' if abends else None)
    if abends: feed_fassung(ziel)
    text = ' '.join(s['text'] for s in segs)
    tipps_speichern()
    json.dump({'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'datum': heute.isoformat(),
               'special': special, 'warn': warn, 'dauer': round(gesamt, 1), 'stimme': echt, 'skript': text, 'frage': FRAGE[0],
               **({'zeilen': next((x['zeilen'] for x in segs if x['art'] == 'woche'), [])} if wochen else {})},
              open(os.path.join(FB, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    archiv(name, heute, special, warn, gesamt)
    print('Video fertig: %s (%.0f s)\n%s' % (ziel, gesamt, text))


def feed_fassung(quelle):
    """Zweite Fassung im Format 4:5 (1080x1350) für den Instagram-Feed: das Hochkant-Video mittig,
    links und rechts Holzfarbe wie der Studiotisch. Hochkant (9:16) nimmt Instagram nur als Reel an."""
    ziel = quelle.replace('.mp4', '-feed.mp4')
    try:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', quelle,
                        '-vf', 'scale=760:1350,pad=1080:1350:160:0:color=0x4A3422', '-c:v', 'libx264', '-preset', 'veryfast',
                        '-crf', '27', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', ziel], check=True)
        print('Feed-Fassung (4:5): %s' % ziel)
    except Exception as e:
        print('Feed-Fassung nicht möglich:', e)


ARCHIV_REIHE = {'morgen': '06:30', 'special': '12:00', 'abend': '19:00', 'woche': '20:00'}   # Ersatz-Uhrzeit für ältere Einträge


def archiv_art(e):
    n = e['datei']
    return e.get('art') or ('special' if '-special' in n else 'woche' if '-woche' in n else 'abend' if '-abend' in n else 'morgen')


def archiv_sortierung(e):
    """Neuestes zuerst: nach Datum, dann nach Erstellzeit (oder Tagesablauf morgens → Special → abends → Wochenausblick)."""
    return (e['datum'], e.get('erstellt', '')[11:16] or ARCHIV_REIHE.get(archiv_art(e), '06:30'))


def archiv(name, heute, special, warn, gesamt, tage=7):
    """Videothek: Kopie + Vorschaubild nach fb/archiv/, alles älter als 7 Tage wird gelöscht."""
    import shutil
    ad = os.path.join(FB, 'archiv'); os.makedirs(ad, exist_ok=True)
    art_ = {'special': 'special', 'woche': 'woche', 'abendvideo': 'abend'}.get(name, 'morgen')
    datei = heute.isoformat() + ('' if art_ == 'morgen' else '-' + art_) + '.mp4'
    shutil.copy(os.path.join(FB, name + '.mp4'), os.path.join(ad, datei))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '3', '-i', os.path.join(ad, datei), '-frames:v', '1', '-vf', 'scale=270:-2', '-q:v', '5',
                    os.path.join(ad, datei.replace('.mp4', '.jpg'))], check=False)
    lp = os.path.join(ad, 'liste.json')
    try: liste = json.load(open(lp, encoding='utf-8'))
    except Exception: liste = []
    liste = [e for e in liste if e['datei'] != datei]
    liste.append({'datum': heute.isoformat(), 'datei': datei, 'art': art_, 'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'),
                  'special': special, 'warn': warn, 'dauer': round(gesamt, 1)})
    grenze = (heute - dt.timedelta(days=tage - 1)).isoformat()
    for e in [e for e in liste if e['datum'] < grenze]:
        for x in (e['datei'], e['datei'].replace('.mp4', '.jpg')):
            try: os.remove(os.path.join(ad, x))
            except OSError: pass
    for f in glob.glob(os.path.join(ad, '*.mp4')) + glob.glob(os.path.join(ad, '*.jpg')):  # Reste aufräumen
        if os.path.basename(f)[:10] < grenze: os.remove(f)
    liste = sorted([e for e in liste if e['datum'] >= grenze], key=archiv_sortierung, reverse=True)
    json.dump(liste, open(lp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
