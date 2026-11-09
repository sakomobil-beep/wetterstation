#!/usr/bin/env python3
"""Täglicher Video-Wetterbericht „Odenwald-Wetter“ mit dem Comic-Moderator (Outdoor-Guide).
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
    t = [('am Vormittag', d['rp_vm']), ('am Nachmittag', d['rp_nm']), ('am Abend', d['rp_ab'])]
    nass = [n for n, p in t if p >= 50]
    if not nass: return None
    if len(nass) == 3: return 'den ganzen Tag über'
    return ' und '.join(nass)


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


def tipps_speichern():
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
    trocken = d['rp'] < 40 and w not in ('Regen', 'Gewitter', 'Schnee')
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
    opt = ['%s gibt es %s bei Höchstwerten um %s Grad.' % (W, art(d), t),
           '%s wird es %s, bei rund %s Grad.' % (W, adj, t),
           '%s erwartet uns %s – die Temperatur schafft es auf etwa %s Grad.' % (W, art(d), t),
           '%s: %s, und das Thermometer klettert auf %s Grad.' % (Wk, art(d)[0].upper() + art(d)[1:], t)]
    if d['tmax'] <= 10: opt.append('%s wird es %s, und mehr als %s Grad sind nicht drin.' % (W, adj, t))
    if d['tmax'] >= 22: opt.append('%s wird es %s – und mit %s Grad schön warm.' % (W, adj, t))
    s = rnd.choice(opt)
    rz = regenzeit(d)
    if rz and w not in ('Regen',):
        s += ' ' + rnd.choice(['Regen ist vor allem %s wahrscheinlich.' % rz, 'Den Schirm braucht ihr vor allem %s.' % rz,
                                'Nass werden kann es %s.' % rz])
    if d.get('frost_min', d['tmin']) <= 0:   # Frost nach dem kältesten Talort
        n = zahl(d.get('frost_min', d['tmin']))
        s += ' ' + rnd.choice(['In der Nacht wird es frostig, bis %s Grad.' % n,
                                'Nachts geht es runter auf %s Grad. Also: morgens Scheiben kratzen!' % n,
                                'Und Achtung, in der Nacht gibt es Frost, bis %s Grad.' % n,
                                'Nachts friert es, mit bis zu %s Grad.' % n])
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
    f = d.get('fenster')
    if not f: return ''
    son = ' Sonne inklusive.' if f['sonnig'] and d['sonne'] >= 1 else ''
    s = rnd.choice([' Das beste Fenster für draußen: zwischen %d und %d Uhr.', ' Am besten raus geht es zwischen %d und %d Uhr.',
                    ' Mein Tipp für eure Runde: zwischen %d und %d Uhr.']) % (f['von'], f['bis'])
    if d['sonne'] >= 2: s += ' Insgesamt gibt es heute etwa %d Stunden Sonne.' % round(d['sonne'])
    return s + (son if d['sonne'] < 2 else '')


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
    nass = [TAGE[d['datum'].weekday()] for d in vorn if d['code'] in NASS or d['rp'] >= 60]
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
    hn = sum(1 for d in hinten if d['code'] in NASS or d['rp'] >= 60)
    t += ' Zum Ende der Woche zeigt die Tendenz: %s%s.' % ({'milder': 'eher milder', 'kühler': 'eher kühler', 'ähnlich': 'ähnliche Temperaturen'}[tr],
                                                          ', und eher nass' if hn == 2 else ', mit etwas Regen' if hn == 1 else ', und eher trocken')
    zeilen = ['%s  %s  %d° / %d°' % (KURZ[d['datum'].weekday()], wort(d['code']).replace('heiter bis wolkig', 'heiter'), d['tmax'], d['tmin']) for d in vorn]
    zeilen.append('Do–Fr: Tendenz %s' % {'milder': 'milder', 'kühler': 'kühler', 'ähnlich': 'gleichbleibend'}[tr])
    return t, zeilen



def skript_woche(days, warn, heute):
    """Sonntagabend-Video: Wochenausblick Montag–Freitag (Mo–Mi mit Werten, Do/Fr Tendenz)."""
    rnd = random.Random('woche' + heute.isoformat())
    woch = days[1:6]
    seg = [dict(art='intro', bg='schloss', text=rnd.choice(['Ei gude, Odenwald! Hier ist euer Max mit dem Wochenausblick.',
                                                          'Guten Abend, Odenwald! Max hier – Zeit für den Blick auf die neue Woche.',
                                                          'Sonntagabend, und euer Max ist noch mal draußen: Hier kommt der Wochenausblick!'])
                + ((' Vorweg: Vom Deutschen Wetterdienst gilt %s.' % ' und '.join(warn[:2])) if warn else ''))]
    for k, d in enumerate(woch[:3]):
        wann = TAGE[d['datum'].weekday()]
        seg.append(dict(art='tag', tag=d, titel=wann.upper(), bg='auto' if k == 0 else 'hoehen' if k == 1 else 'wald',
                        text=('Los geht es mit dem %s. ' % wann if k == 0 else '') + tagtext(d, 'Am %s' % wann)))
    wo = woche(woch, rnd)
    if wo:
        t = wo[0].split('Zum Ende der Woche', 1)
        rest = ('Und zum Ende der Woche' + t[1]) if len(t) > 1 else wo[0]
        seg.append(dict(art='woche', tage=woch, bg='wald', zeilen=wo[1], text=rest + ' Genauer wird es dann im Morgenvideo am jeweiligen Tag.'))
    try:
        tl = TERMINE.woche_liste(heute + dt.timedelta(days=1))
        if tl: seg[-1]['text'] += ' Und im Kalender diese Woche: ' + ', '.join(tl) + '.'
    except Exception as e: print('Termine nicht möglich:', e)
    seg.append(dict(art='outro', bg='schloss', text=rnd.choice(['Kommt gut in die neue Woche!', 'Ich wünsch euch einen guten Start in die Woche!',
                                                              'Habt eine gute Woche, und passt auf euch auf!'])
                    + ' Jeden Morgen gibt es euer Wettervideo, und alle Live-Werte findet ihr auf wetter-badkoenig.de.'))
    return seg


def skript_abend(days, warn, heute):
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
        seg.append(dict(art='tag', bg='studio', titel='MORGEN', tag=paar[0],
                        tafel_img=tafel_tag('MORGEN', paar[0]), text=tagtext(paar[0], 'Morgen')))
        seg.append(dict(art='tag', bg='studio', titel='ÜBERMORGEN', tag=paar[1],
                        tafel_img=tafel_tag('ÜBERMORGEN', paar[1]), text='Und übermorgen: ' + tagtext(paar[1], 'Dann')))
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


# --- Max' Persönlichkeit: 34, aus Vielbrunn, Wanderführer und Hobby-Römerforscher,
#     sein Rucksack ist immer zu schwer, Glühwein mag er lieber als Kälte ---
def max_privat(d, rnd, heute):
    """Kleine persönliche Bemerkung – nur an etwa jedem dritten Tag."""
    if rnd.random() > 0.35: return ''
    w = wort(d['code'])
    nass = w in ('Regen', 'Nieselregen', 'Schauer', 'Gewitter') or d['rp'] >= 60
    if w == 'Schnee' or d['schnee'] >= 1:
        opt = ['Ich hab meinen Schlitten schon aus dem Keller geholt – unter dem ganzen Zeug im Rucksack.',
               'Bei uns oben in Vielbrunn liegt immer zuerst Schnee – da freu ich mich jedes Jahr wie ein Kind.']
    elif nass:
        opt = ['Ich verrate euch was: Bei so einem Wetter sitz ich am liebsten mit einem Buch über die Römer auf dem Sofa.',
               'Mein Rucksack ist heute übrigens wasserdicht verpackt – na ja, fast. Irgendwas wird immer nass.',
               'Bei Regen ist mein Lieblingsplatz das warme Becken in der Therme. Vielleicht sieht man sich!']
    elif d['code'] in (45, 48, 3):
        opt = ['Bei so grauem Wetter hilft nur eins: eine Thermoskanne heißer Tee im Rucksack.',
               'Ich mag Nebel ja irgendwie. Im Wald am Limes wirkt dann alles, als wären die Römer gleich um die Ecke.',
               'Ganz ehrlich: An so einem grauen Tag darf man sich auch mal einfach eine Decke schnappen.']
    elif d['tmax'] <= 4:
        opt = ['Ganz ehrlich: Bei der Kälte ist mir ein Glühwein lieber als jede Wanderung. Aber erst die Runde, dann der Glühwein!',
               'Ich hab heute Morgen extra die dicken Socken eingepackt. Mein Rucksack wird dadurch natürlich nicht leichter.']
    else:
        opt = ['Wisst ihr, was ich als Wanderführer am meisten höre? „Max, dein Rucksack ist viel zu schwer!“ – Stimmt. Aber man weiß ja nie.',
               'Bei so einem Wetter jucken mir richtig die Wanderschuhe.',
               'Als Hobby-Römerforscher sag ich euch: Die Römer haben schon gewusst, warum sie hier oben im Odenwald ihre Grenze gebaut haben – die Aussicht ist einfach top.',
               'Ich bin ja in Vielbrunn aufgewachsen, direkt am Limes. Als Kind hab ich da im Wald immer nach Römermünzen gesucht – gefunden hab ich nur Tannenzapfen.',
               'Mein Rucksack ist heute wieder randvoll: Brotzeit, Regenjacke, Fernglas und ein Buch über die Römer. Man muss ja vorbereitet sein!']
    return ' ' + rnd.choice(opt)


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
        return 'Euer Max sagt: Heute lieber drinnen bleiben – passt auf euch auf!'
    if w == 'Schnee' or d['schnee'] >= 1:
        return 'Euer Max sagt: Warm einpacken, vorsichtig fahren – und viel Spaß im Schnee!'
    if w in ('Regen', 'Nieselregen', 'Schauer') or d['rp'] >= 60:
        return rnd.choice(['Euer Max sagt: Macht es euch heute gemütlich – der Odenwald läuft nicht weg!',
                           'Euer Max sagt: Tee kochen, Füße hoch – das nächste Wanderwetter kommt bestimmt!'])
    if d['code'] in (45, 48):
        return rnd.choice(['Euer Max sagt: Licht an im Nebel, fahrt vorsichtig – und macht es euch gemütlich!',
                           'Euer Max sagt: Warm einpacken und vorsichtig fahren – bis morgen!'])
    if d['code'] == 3:
        return rnd.choice(['Euer Max sagt: Auch ein grauer Tag kann schön werden – macht was draus!', 'Euer Max sagt: Jacke an und los – bis morgen!'])
    if d['tmax'] <= 3:
        return 'Euer Max sagt: Dick einpacken – und dann raus an die frische Luft!'
    return 'Euer Max sagt: Rucksack auf und raus – der Odenwald wartet!'


def lage_fx(d):
    """Wetterlage für Hintergrund-Effekte: schnee, gewitter, sturm, regen oder None."""
    if not d: return None
    w = wort(d['code'])
    if w == 'Schnee' or d['schnee'] >= 1: return 'schnee'
    if w == 'Gewitter': return 'gewitter'
    if d['boe'] >= 55: return 'sturm'
    if w in ('Regen', 'Nieselregen') or d['regen'] >= 5: return 'regen'
    if w == 'Schauer' or d['rp'] >= 60: return 'schauer'    # nur zeitweise Schauer: Sonne + Schauer in der Ferne
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
    if w in ('Regen', 'Nieselregen', 'Schauer') or a['rp'] >= 60: kat.append('regen')
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
    gruss = rnd.choice(['Ei gude, Odenwald! Hier ist euer Max.', 'Guten Morgen, Odenwald! Euer Max meldet sich vom Wanderweg.',
                        'Ei gude wie, Odenwald? Max hier, euer Outdoor-Guide.', 'Moin aus dem Mümlingtal – euer Max ist schon draußen!'])
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
        seg.append(dict(art='intro', bg='schloss', text=gruss + (' Für alle, die neu dabei sind: Ich bin Max, Wanderführer aus Vielbrunn.' if heute.weekday() == 0 else '') + ' Das ist euer Odenwald-Wetter für %s.' % TAGE[heute.weekday()] + hinweis))
    if not nur_special and a.get('gestern'):
        seg[-1]['text'] += ' ' + gestern_txt(a['gestern'], rnd)
    seg.append(dict(art='tag', tag=a, titel='HEUTE', bg='auto', text=tagtext(a, 'Heute') + fenster_txt(a, rnd)))
    seg.append(dict(art='tipp', tag=a, bg='wald' if a['rp'] < 40 else 'schloss', text=rnd.choice(['Mein Outdoor-Tipp für heute: ', 'Max-Tipp des Tages: ', 'Und jetzt mein Tipp: ', 'Übrigens, mein Tipp für heute: ',
                                                                               'Was könnt ihr heute machen? ', 'Und wenn ihr noch nichts vorhabt: ']) + tipp(a, rnd, heute) + max_privat(a, rnd, heute)))
    if not nur_special:
        seg.append(dict(art='tag', tag=b, titel='MORGEN', bg='hoehen',
                        text=rnd.choice(['', 'So, und jetzt der Blick nach vorn. ', 'Was bringt der nächste Tag? ', 'Schauen wir auf morgen. '])
                             + tagtext(b, rnd.choice(['Morgen, am %s,', 'Am %s']) % TAGE[b['datum'].weekday()])))
        if heute.weekday() <= 4 and len(days) >= 7:
            sa = next(d for d in days if d['datum'].weekday() == 5)
            so = next(d for d in days if d['datum'].weekday() == 6)
            if sa['datum'] > b['datum'] or so['datum'] > b['datum']:
                nass = (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99)
                gut = [n for n, d in (('Samstag', sa), ('Sonntag', so)) if d['rp'] < 40 and d['code'] not in nass]
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
    if w in ('Regen', 'Gewitter', 'Nieselregen', 'Schauer') or d['rp'] >= 60: return 'regen'
    if d['tmax'] <= 11: return 'kuehl'
    if d['tmax'] >= 20: return 'sonne' if w in ('sonnig', 'heiter bis wolkig') else 'warm'
    return 'normal'


# Oberteil je Look: (Farbe Jacke/Shirt, Farbe Weste oder None, kurze Ärmel)
OUTFIT = {'winter': ((200, 45, 50), None, False),          # dicke rote Daunenjacke
          'regen': ((250, 200, 30), None, False),          # gelbe Regenjacke (Friesennerz)
          'kuehl': ((30, 130, 120), (60, 70, 85), False),  # Softshell mit dunkler Weste
          'normal': ((30, 130, 120), (240, 140, 40), False),
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


def moderator(mund, blinzeln, zeigen, wink=0, look='normal', prop=None, studio=False):
    """zeigen: 0 = Arm hängt, 1 = zeigt zur Tafel, 2 = Daumen hoch, 3 = winkt"""
    S = 2  # doppelt zeichnen, dann verkleinern = glatte Linien
    w, h = 380 * S, 760 * S
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    L = 5 * S
    cx = w // 2
    def P(*xy): return [v * S for v in xy]
    JACKE, WESTE, KURZ = OUTFIT.get(look, OUTFIT['normal'])
    def aermel(pts):
        """Arm zeichnen: lang in Jackenfarbe oder kurz (Haut + kurzer Ärmel)."""
        d.line(pts, fill=LINIE, width=48 * S, joint='curve')
        if not KURZ:
            d.line(pts, fill=JACKE, width=36 * S, joint='curve'); return
        d.line(pts, fill=HAUT, width=36 * S, joint='curve')
        x0, y0, x1, y1 = pts[0], pts[1], pts[2], pts[3]
        xm, ym = x0 + (x1 - x0) * 0.45, y0 + (y1 - y0) * 0.45
        d.line([x0, y0, xm, ym], fill=LINIE, width=50 * S)
        d.line([x0, y0, xm, ym], fill=JACKE, width=40 * S)
    # Rucksack (schaut hinter den Schultern hervor)
    if not studio:   # im Studio sitzt Max ohne Rucksack am Tisch
        d.rounded_rectangle(P(92, 262, 288, 500), radius=40 * S, fill=(150, 45, 40), outline=LINIE, width=L)
        d.rounded_rectangle(P(150, 236, 230, 280), radius=18 * S, fill=(150, 45, 40), outline=LINIE, width=L)
    # Beine + Wanderschuhe
    d.rounded_rectangle(P(130, 520, 182, 720), radius=20 * S, fill=HOSE, outline=LINIE, width=L)
    d.rounded_rectangle(P(198, 520, 250, 720), radius=20 * S, fill=HOSE, outline=LINIE, width=L)
    d.rounded_rectangle(P(115, 700, 188, 745), radius=16 * S, fill=(120, 75, 45), outline=LINIE, width=L)
    d.rounded_rectangle(P(192, 700, 265, 745), radius=16 * S, fill=(120, 75, 45), outline=LINIE, width=L)
    # linker Arm (hängt, Hand an der Hüfte)
    aermel(P(118, 330, 92, 450, 120, 530))
    d.ellipse(P(100, 512, 142, 554), fill=HAUT, outline=LINIE, width=L)
    # Rumpf: Softshelljacke mit Weste
    d.rounded_rectangle(P(108, 290, 272, 560), radius=46 * S, fill=JACKE, outline=LINIE, width=L)
    if WESTE:
        d.polygon(P(150, 300, 190, 300, 182, 560, 150, 560), fill=WESTE, outline=LINIE)     # Weste links
        d.polygon(P(230, 300, 190, 300, 198, 560, 230, 560), fill=WESTE, outline=LINIE)     # Weste rechts
    if look == 'winter':                                                                # Steppnähte der Daunenjacke
        for y in (360, 410, 460, 510): d.line(P(116, y, 264, y), fill=(160, 30, 40), width=4 * S)
    if not KURZ: d.line(P(190, 300, 190, 560), fill=(220, 220, 225), width=4 * S)       # Reißverschluss
    d.rounded_rectangle(P(156, 400, 184, 430), radius=5 * S, fill=(205, 110, 30), outline=LINIE, width=3 * S)  # Tasche
    d.rounded_rectangle(P(196, 400, 224, 430), radius=5 * S, fill=(205, 110, 30), outline=LINIE, width=3 * S)
    if KURZ:
        d.chord(P(160, 270, 220, 320), 0, 180, fill=HAUT, outline=LINIE, width=L)     # Rundhals-Ausschnitt
    else:
        d.polygon(P(148, 278, 190, 330, 232, 278, 224, 300, 190, 345, 156, 300), fill=JACKE, outline=LINIE)  # Stehkragen
        d.polygon(P(166, 284, 190, 318, 214, 284), fill=(245, 245, 245), outline=LINIE)
    for x0, x1 in (() if studio else ((132, 146), (248, 234))):                               # Rucksackgurte
        d.line(P(x0, 296, x1, 470), fill=LINIE, width=15 * S)
        d.line(P(x0, 296, x1, 470), fill=(60, 60, 70), width=10 * S)
    if not studio: d.rounded_rectangle(P(150, 452, 230, 464), radius=4 * S, fill=(60, 60, 70), outline=LINIE, width=2 * S)  # Brustgurt
    d.rounded_rectangle(P(203, 336, 263, 360), radius=6 * S, fill=(255, 255, 255), outline=LINIE, width=3 * S)  # Namensschild
    d.text(P(233, 348), 'MAX', font=ImageFont.truetype(B, 13 * S), fill=(30, 130, 120), anchor='mm')
    d.ellipse(P(150, 334, 176, 360), fill=(250, 210, 60), outline=LINIE, width=3 * S)          # Kompass-Anstecker
    d.polygon(P(163, 338, 167, 347, 163, 356, 159, 347), fill=(200, 40, 40))
    # rechter Arm: zeigt nach oben rechts zur Tafel oder hängt
    if zeigen == 1:
        arm = P(262, 330, 320, 270 - wink, 352, 190 - wink)
        hand = P(334, 160 - wink, 376, 202 - wink)
    elif zeigen == 2:   # Daumen hoch vor der Brust
        arm = P(262, 330, 300, 430, 310, 380)
        hand = P(288, 352, 334, 398)
    elif zeigen == 3:   # Winken
        arm = P(262, 330, 318, 300, 330 + wink, 200)
        hand = P(306 + wink, 160, 356 + wink, 210)
    else:
        arm = P(262, 330, 288, 450, 260, 530)
        hand = P(240, 512, 282, 554)
    aermel(arm)
    d.ellipse(hand, fill=HAUT, outline=LINIE, width=L)
    if zeigen == 2:
        d.rounded_rectangle(P(302, 318, 322, 362), radius=9 * S, fill=HAUT, outline=LINIE, width=4 * S)
    if zeigen == 3:
        for k in range(4):
            fx = 312 + wink + k * 12
            d.rounded_rectangle(P(fx, 128 + abs(k - 1.5) * 6, fx + 11, 172), radius=5 * S, fill=HAUT, outline=LINIE, width=3 * S)
        d.ellipse(P(306 + wink, 160, 356 + wink, 210), fill=HAUT, outline=LINIE, width=L)
    if zeigen == 1:
        d.line(P(362, 172 - wink, 378, 140 - wink), fill=LINIE, width=16 * S)
        d.line(P(362, 172 - wink, 378, 140 - wink), fill=HAUT, width=9 * S)
    # Hals + Kopf
    d.rectangle(P(172, 250, 208, 295), fill=HAUT, outline=LINIE, width=L)
    d.ellipse(P(110, 60, 270, 260), fill=HAUT, outline=LINIE, width=L)
    bart = Image.new('RGBA', im.size, (0, 0, 0, 0)); bd = ImageDraw.Draw(bart)            # Dreitagebart
    bd.chord(P(124, 150, 256, 258), 15, 165, fill=HAAR + (38,))
    im.alpha_composite(bart); d = ImageDraw.Draw(im)
    d.ellipse(P(100, 140, 126, 190), fill=HAUT, outline=LINIE, width=L)                 # Ohren
    d.ellipse(P(254, 140, 280, 190), fill=HAUT, outline=LINIE, width=L)
    d.chord(P(108, 52, 272, 176), 180, 360, fill=HAAR, outline=LINIE, width=L)          # Haare
    d.pieslice(P(118, 36, 262, 150), 200, 340, fill=HAAR)
    d.polygon(P(128, 108, 150, 62, 205, 40, 258, 70, 262, 108, 230, 88, 190, 98, 160, 90), fill=HAAR)  # Tolle
    d.line(P(150, 62, 205, 40, 258, 70), fill=LINIE, width=4 * S, joint='curve')
    d.arc(P(160, 60, 240, 110), 200, 300, fill=(70, 42, 22), width=3 * S)
    d.rectangle(P(114, 108, 128, 146), fill=HAAR)
    d.rectangle(P(252, 108, 266, 146), fill=HAAR)
    # Augen + Brauen
    for ex in (158, 222):
        if blinzeln:
            d.arc(P(ex - 15, 145, ex + 15, 165), 0, 180, fill=LINIE, width=4 * S)
        else:
            d.ellipse(P(ex - 13, 138, ex + 13, 168), fill=(255, 255, 255), outline=LINIE, width=3 * S)
            d.ellipse(P(ex - 7, 146, ex + 7, 162), fill=(60, 90, 140))
            d.ellipse(P(ex - 2, 148, ex + 3, 153), fill=(255, 255, 255))
        d.line(P(ex - 16, 126, ex + 14, 122), fill=HAAR, width=6 * S)
    d.line(P(190, 165, 182, 195, 194, 198), fill=(200, 140, 110), width=4 * S)          # Nase
    d.ellipse(P(130, 185, 156, 203), fill=(250, 170, 150))                                # Wangen
    d.ellipse(P(224, 185, 250, 203), fill=(250, 170, 150))
    # Mund (0 = Lächeln zu … 3 = weit offen)
    if mund == 0:
        d.arc(P(160, 190, 220, 228), 10, 170, fill=LINIE, width=5 * S)
    else:
        o = [0, 10, 18, 26][mund]
        top, bot = 206 - o // 4, 212 + o
        mid = (top + bot) / 2
        d.chord(P(162, top, 218, bot), 0, 180, fill=(140, 40, 50), outline=LINIE, width=4 * S)
        d.rectangle(P(172, mid + 1, 208, mid + 6), fill=(255, 255, 255))
        if o >= 18: d.ellipse(P(180, bot - 10, 200, bot - 3), fill=(220, 90, 100))
    if WEIHNACHT[0] and look != 'sturm':   # Weihnachts-Max: Weihnachtsmütze + rot-grüner Schal
        d.polygon(P(108, 112, 272, 112, 250, 50, 300, 20, 214, 34, 150, 52), fill=(200, 35, 45), outline=LINIE)
        d.line(P(108, 112, 150, 52, 214, 34, 300, 20, 250, 50, 272, 112), fill=LINIE, width=L)
        d.ellipse(P(286, 4, 326, 44), fill=(245, 245, 245), outline=LINIE, width=L)
        d.rounded_rectangle(P(98, 94, 282, 130), radius=16 * S, fill=(245, 245, 245), outline=LINIE, width=L)
        d.rounded_rectangle(P(140, 250, 240, 296), radius=20 * S, fill=(200, 35, 45), outline=LINIE, width=L)
        for x in (160, 190, 220): d.line(P(x, 254, x, 292), fill=(30, 120, 60), width=8 * S)
        d.rounded_rectangle(P(150, 280, 186, 400), radius=10 * S, fill=(200, 35, 45), outline=LINIE, width=L)
        for y in (310, 340, 370): d.line(P(152, y, 184, y), fill=(30, 120, 60), width=8 * S)
        for x in (156, 168, 180): d.line(P(x, 400, x, 414), fill=(245, 245, 245), width=4 * S)
    elif look == 'winter':   # Bommelmütze + Schal
        d.chord(P(104, 30, 276, 190), 180, 360, fill=(200, 45, 50), outline=LINIE, width=L)
        d.rounded_rectangle(P(100, 96, 280, 128), radius=14 * S, fill=(240, 240, 240), outline=LINIE, width=L)
        for x in range(120, 270, 22): d.line(P(x, 40 + abs(x - 190) // 3, x, 96), fill=(170, 30, 40), width=4 * S)
        d.ellipse(P(166, 0, 214, 48), fill=(240, 240, 240), outline=LINIE, width=L)
        d.rounded_rectangle(P(140, 250, 240, 296), radius=20 * S, fill=(200, 45, 50), outline=LINIE, width=L)
        d.rounded_rectangle(P(150, 280, 186, 400), radius=10 * S, fill=(200, 45, 50), outline=LINIE, width=L)
        for y in (330, 360): d.line(P(150, y, 186, y), fill=(240, 240, 240), width=6 * S)
    elif look == 'kuehl':  # grüne Strickmütze
        d.chord(P(108, 40, 272, 200), 180, 360, fill=(40, 110, 70), outline=LINIE, width=L)
        d.rounded_rectangle(P(106, 104, 274, 130), radius=10 * S, fill=(30, 90, 55), outline=LINIE, width=L)
        for x in range(128, 262, 18): d.line(P(x, 108, x, 126), fill=(50, 130, 85), width=3 * S)
    elif look == 'regen' and prop != 'schirm':  # gelber Friesennerz-Hut
        d.ellipse(P(80, 92, 300, 140), fill=(250, 200, 30), outline=LINIE, width=L)
        d.chord(P(122, 34, 258, 170), 180, 360, fill=(250, 200, 30), outline=LINIE, width=L)
        d.line(P(124, 104, 256, 104), fill=(210, 160, 20), width=6 * S)
    elif look == 'sonne':  # Cap + Sonnenbrille
        d.chord(P(112, 40, 268, 180), 180, 360, fill=(30, 130, 120), outline=LINIE, width=L)
        d.pieslice(P(200, 88, 320, 128), 180, 360, fill=(25, 105, 95), outline=LINIE, width=L)
        d.text(P(190, 78), 'ODW', font=ImageFont.truetype(B, 18 * S), fill=(255, 255, 255), anchor='mm')
        for ex in (158, 222):
            d.rounded_rectangle(P(ex - 24, 136, ex + 24, 170), radius=12 * S, fill=(30, 40, 60), outline=LINIE, width=4 * S)
            d.line(P(ex - 14, 142, ex - 4, 142), fill=(120, 150, 200), width=3 * S)
        d.line(P(182, 148, 198, 148), fill=LINIE, width=5 * S)
    if look == 'sturm':   # Haare zerzaust vom Wind
        for k in range(6): d.line(P(120 + k * 26, 70, 150 + k * 26, 36 + (k % 2) * 10), fill=HAAR, width=9 * S)
    if prop == 'schippe': schippe(d, P, L)
    elif prop == 'schirm': schirm(d, P, L)
    return im.resize((w // S, h // S), Image.LANCZOS)


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
    if s['art'] == 'cta': return tafel_text('MACH MIT!', ['❤ Liken', '+ Folgen', '↻ Teilen', '✎ Kommentieren'], (254, 44, 85))
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


TEMPO = {'rueck': '+1%', 'wissen': '+2%', 'special': '-6%', 'tag': '+0%', 'wochenende': '+2%', 'woche': '+2%', 'tipp': '+5%', 'intro': '+4%', 'outro': '+3%'}


def sprich(text, pfad, rate='+2%'):
    text = sprechtext(text)
    try:
        import edge_tts
        async def go():
            await edge_tts.Communicate(text, VOICE, rate=rate).save(pfad)
        asyncio.run(go())
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
        echt = sprich(s['text'], p, TEMPO.get(s['art'], '+2%')) and echt
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
    if not echt:  # Testmodus: künstliche Sprechbewegung
        lv = np.array([0.8 + 0.6 * math.sin(i * 1.7) for i in range(N)])
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
        if (look, prop, st) not in MODS:
            mm_ = {}
            for m in range(4):
                for b_ in (0, 1):
                    for z, wk in ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1)):
                        im_ = moderator(m, b_, z, wk * 22, look, prop, st); gr_ = 1.2 if st else 0.92; mm_[(m, b_, z, wk)] = im_.resize((int(im_.width * gr_), int(im_.height * gr_)), Image.LANCZOS)
            MODS[(look, prop, st)] = mm_
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
        s['tafel'] = tafel_fuer(s, special)
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
        if s['tafel'] is not None and studio:
            tf = s['tafel']
            scl = W / cw
            rx0, ry0, rx1, ry1 = STUDIO_SCREEN
            rfx0, rfy0 = (rx0 - x0) * scl, (ry0 - y0) * scl
            rfw, rfh = (rx1 - rx0) * scl, (ry1 - ry0) * scl
            fit = min(rfw / tf.width, rfh / tf.height) * 0.92
            tfr = tf.resize((max(1, int(tf.width * fit)), max(1, int(tf.height * fit))), Image.LANCZOS)
            ein = min(1, lt / 0.5)
            if ein < 1: tfr = Image.blend(Image.new('RGBA', tfr.size, (0, 0, 0, 0)), tfr, ein)
            tx = int(rfx0 + (rfw - tfr.width) / 2); ty = int(rfy0 + (rfh - tfr.height) / 2)
            fr.alpha_composite(tfr, (tx, ty))
        elif s['tafel'] is not None:
            tf = s['tafel']; ein = min(1, lt / 0.45); ein = 1 - (1 - ein) ** 3
            tx = int(W - tf.width - 24 + (1 - ein) * (tf.width + 40)); ty = 215
            fr.alpha_composite(tf, (tx, ty))
        # Moderator (links unten), Mund nach Lautstärke
        v = lv[i] if i < len(lv) else 0
        m = 0 if v < 0.15 else 1 if v < 0.45 else 2 if v < 0.8 else 3
        blink = 1 if (i % 95) in (0, 1, 2) else 0
        zeigt = 1 if s['tafel'] is not None and s['art'] in ('tag', 'wochenende', 'woche', 'special') and lt < 2.2 else 0
        if s['art'] in ('intro', 'outro') and lt < 2.0: zeigt = 3
        elif s['art'] == 'cta' and (lt < 1.5 or lt > s['dauer'] - 2.5): zeigt = 3
        elif s['art'] == 'tipp' and 0.6 < lt < 2.6: zeigt = 2
        wk = 1 if zeigt == 3 and int(t * 5) % 2 else 0
        mm = mods_fuer(s['look'], s['prop'], studio)[(m, blink, zeigt, wk)]
        bob = int(4 * math.sin(t * 2.2))
        if pk == 'sturm': bob += int(5 * math.sin(t * 9))   # Max wackelt im Wind
        mx, my = -20, H - mm.height - 150 + bob
        if studio: mx, my = 10, STUDIO_TISCH - int(mm.height * 0.70) + bob // 2   # Hüfte auf Tischhöhe: Max sitzt
        fr.alpha_composite(mm, (mx, my))
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
    abends = '--abend' in sys.argv   # Abendvideo aus dem Studio (eigene Datei, nicht in der Videothek der Website)
    segs = skript_abend(days, warn, heute) if abends else skript_woche(days, warn, heute) if wochen else skript(days, warn, heute, nur_special)
    special = nur_special   # das Morgenvideo ist immer das normale Video
    name = 'abendvideo' if abends else 'special' if nur_special else 'woche' if wochen else 'wetter'
    ziel = os.path.join(FB, name + '.mp4')
    gesamt, echt = baue(segs, heute, ziel, special, titel='WOCHENAUSBLICK' if wochen else 'ODENWALD AM ABEND' if abends else None)
    text = ' '.join(s['text'] for s in segs)
    tipps_speichern()
    json.dump({'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'datum': heute.isoformat(),
               'special': special, 'warn': warn, 'dauer': round(gesamt, 1), 'stimme': echt, 'skript': text,
               **({'zeilen': next((x['zeilen'] for x in segs if x['art'] == 'woche'), [])} if wochen else {})},
              open(os.path.join(FB, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    if not abends: archiv(name, heute, special, warn, gesamt)
    print('Video fertig: %s (%.0f s)\n%s' % (ziel, gesamt, text))


def archiv(name, heute, special, warn, gesamt, tage=7):
    """Videothek: Kopie + Vorschaubild nach fb/archiv/, alles älter als 7 Tage wird gelöscht."""
    import shutil
    ad = os.path.join(FB, 'archiv'); os.makedirs(ad, exist_ok=True)
    datei = heute.isoformat() + ('-special' if name == 'special' else '-woche' if name == 'woche' else '') + '.mp4'
    shutil.copy(os.path.join(FB, name + '.mp4'), os.path.join(ad, datei))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '3', '-i', os.path.join(ad, datei), '-frames:v', '1', '-vf', 'scale=270:-2', '-q:v', '5',
                    os.path.join(ad, datei.replace('.mp4', '.jpg'))], check=False)
    lp = os.path.join(ad, 'liste.json')
    try: liste = json.load(open(lp, encoding='utf-8'))
    except Exception: liste = []
    liste = [e for e in liste if e['datei'] != datei]
    liste.append({'datum': heute.isoformat(), 'datei': datei, 'special': special, 'warn': warn, 'dauer': round(gesamt, 1)})
    grenze = (heute - dt.timedelta(days=tage - 1)).isoformat()
    for e in [e for e in liste if e['datum'] < grenze]:
        for x in (e['datei'], e['datei'].replace('.mp4', '.jpg')):
            try: os.remove(os.path.join(ad, x))
            except OSError: pass
    for f in glob.glob(os.path.join(ad, '*.mp4')) + glob.glob(os.path.join(ad, '*.jpg')):  # Reste aufräumen
        if os.path.basename(f)[:10] < grenze: os.remove(f)
    liste = sorted([e for e in liste if e['datum'] >= grenze], key=lambda e: e['datei'], reverse=True)
    json.dump(liste, open(lp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
