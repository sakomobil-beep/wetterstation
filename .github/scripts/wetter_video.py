#!/usr/bin/env python3
"""Täglicher Video-Wetterbericht „Odenwald-Wetter“ mit dem Comic-Moderator (Outdoor-Guide).
Liest fb/daten.json (von fb_post.py), schreibt fb/wetter.mp4 (+ wetter.json) bzw. fb/special.mp4 (+ special.json).
Stimme: Microsoft Neural-Stimme „Conrad“ über edge-tts. Ohne edge-tts (Test) wird eine stumme Spur erzeugt.
Eigene (KI-)Hintergrundbilder: einfach als .jpg/.png in den Ordner video/hintergruende/ legen – sie werden mitbenutzt."""
import json, os, sys, math, random, subprocess, asyncio, glob, tempfile, datetime as dt
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


def abend_tipp(heute, rnd, regen=False):
    """Weihnachtsmärkte und Christmas Lights, je nach Datum und Wochentag."""
    m, tag, wt = heute.month, heute.day, heute.weekday()
    markt = (m == 11 and tag >= 27) or (m == 12 and tag <= 20)
    lights = (m == 11 and tag >= 13) or m == 12 or (m == 1 and tag <= 10)
    if (m, tag) in ((12, 24), (12, 25), (12, 31), (1, 1)): lights = False   # Ruhetage
    opt = []
    if markt and wt >= 2:
        opt.append(('Und am Abend lockt der Michelstädter Weihnachtsmarkt rund ums historische Rathaus – geöffnet mittwochs bis sonntags.',
                    'Danach ab auf den Michelstädter Weihnachtsmarkt – ein Glühwein unterm Rathausdach geht auch bei Schmuddelwetter.'))
    if markt and wt >= 4:
        opt.append(('Und heute Abend hat auch der Erbacher Weihnachtsmarkt geöffnet – den gibt es freitags bis sonntags.',
                    'Und wenn es abends trockener wird: Der Erbacher Weihnachtsmarkt hat freitags bis sonntags geöffnet.'))
    if lights:
        opt.append(('Und wenn es dunkel wird: Von 17 bis 20 Uhr leuchten die Christmas Lights im Kurpark Bad König – dieses Jahr mit „Tonis fantastischen Erinnerungen“. Zeit-Slot vorher online buchen!',
                    'Ein kleiner Lichtblick: Ab 17 Uhr verwandeln die Christmas Lights den Kurpark Bad König in eine Märchenwelt. Tickets mit Zeit-Slot gibt es online.'))
        opt.append(('Tipp für Familien: Bei den Christmas Lights im Kurpark Bad König haben Kinder bis 14 freien Eintritt – Lichterrundgang täglich ab 17 Uhr.',
                    'Abends ab 17 Uhr zu den Christmas Lights im Kurpark Bad König – Kinder bis 14 sind kostenlos dabei. Zeit-Slot online buchen!'))
        if wt >= 2:
            opt.append(('Heute Abend hat auch der Wintermarkt bei den Christmas Lights im Kurpark offen – mit Glühwein, Livebühne und Kunsthandwerk, bis 21 Uhr.',
                        'Aufwärmen im Zirkuszelt: Der Wintermarkt bei den Christmas Lights im Kurpark Bad König hat heute bis 21 Uhr geöffnet – mit Glühwein und Livebühne.'))
    if not opt: return ''
    return ' ' + rnd.choice(opt)[1 if regen else 0]


def tipp(d, rnd, heute):
    """Freizeittipp für den Odenwald passend zum Wetter und zur Jahreszeit."""
    m, tag = heute.month, heute.day
    w = wort(d['code'])
    trocken = d['rp'] < 40 and w not in ('Regen', 'Gewitter', 'Schnee')
    if w == 'Schnee' or d['schnee'] >= 1:
        return rnd.choice(['Erst durch den Schnee stapfen, dann ab ins warme Thermalbad der Odenwald-Therme Bad König – besser geht Winter nicht!',
                           'Holt die Schlitten raus! Auf der Tromm und rund um den Katzenbuckel wird es weiß – aber fahrt vorsichtig, es kann glatt sein.',
                           'Winterwunderland Odenwald! Ein Schneespaziergang durchs Mümlingtal – mit festen Schuhen und warmer Mütze.'])
    if w == 'Gewitter':
        return 'Bei Gewitter gilt: raus aus dem Wald und weg von den Höhen. Lieber ab ins Trockene – zum Beispiel ins Elfenbeinmuseum nach Erbach.'
    if not trocken:
        r = rnd.choice(['Ideales Wetter für die Odenwald-Therme hier in Bad König – warmes Thermalwasser statt kalter Regen.',
                        'Schwitzen statt nass werden: Die Saunalandschaft der Odenwald-Therme Bad König ist bei Regen genau richtig.',
                        'Ab nach Michelstadt ins Stadtmuseum in der historischen Kellerei – und danach ein Kaffee in der Altstadt.',
                        'Ein Bummel durch die Michelstädter Altstadt geht auch mit Schirm – unter dem Fachwerk-Rathaus von 1484 bleibt man sogar trocken.',
                        'Durchatmen bei Schmuddelwetter: Die Salzgrotte in der Odenwald-Therme Bad König ist wie ein Kurzurlaub am Meer.',
                        'Ein Tag für drinnen: Schloss Erbach oder das Elfenbeinmuseum lohnen sich immer.',
                        'Wer trotzdem raus will: Regenjacke an, Gummistiefel an – der Wald im Mümlingtal riecht nach Regen am besten.'])
        r += abend_tipp(heute, rnd, regen=True)
        return r
    if d['tmax'] <= 3:
        return abend_tipp(heute, rnd).strip() and (rnd.choice(['Klare, kalte Luft – perfekt für einen Winterspaziergang im Kurpark Bad König.', 'Dick einpacken und hoch auf die Odenwälder Höhen – die Fernsicht ist bei Kälte oft großartig.']) + abend_tipp(heute, rnd)) or rnd.choice(['Klare, kalte Luft – perfekt für einen Winterspaziergang im Kurpark Bad König. Danach einen heißen Kakao!',
                           'Klare Winterluft auf der Höhe: Ein Spaziergang am Limes bei Würzberg zum römischen Kastellbad – mit warmem Tee im Rucksack.',
                           'Klare Winterluft heißt Fernsicht: Von der Burg Breuberg schaut ihr weit übers Mümlingtal – die Burghöfe sind frei zugänglich.',
                        'Bei klarer, kalter Luft ist die Aussicht von der Burgruine Freienstein über das Gammelsbachtal besonders weit.',
                        'Ein Winterspaziergang durch den Englischen Garten Eulbach – das Rotwild im Wildgehege freut sich über Besuch.',
                        'Erst durch die Kälte, dann in die Wärme: Die Sauna der Odenwald-Therme Bad König wartet schon.',
                           'Nach dem Winterspaziergang ab ins warme Thermalbad der Odenwald-Therme Bad König – herrlich, wenn draußen die Luft klirrt.',
                           'Eine Runde um die beiden Seen im Kurpark Bad König – und danach aufwärmen im Café am See.',
                           'Wenn es früh dunkel wird: Die beleuchteten Spazierwege im Kurpark Bad König sind perfekt für eine Abendrunde.',
                           'Dick einpacken und hoch auf die Odenwälder Höhen: Bei so kalter Luft ist die Fernsicht oft großartig.'])
    if d['tmax'] >= 28:
        return rnd.choice(['Heute lieber früh los! Morgens wandern, mittags in den Schatten – und viel trinken.',
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
    r = rnd.choice(kurpark + ['Perfektes Wanderwetter! Auf dem Limes-Wanderweg geht ihr direkt an der alten römischen Grenze entlang – quer durch den Odenwald.',
                    'Ab nach Vielbrunn zum nachgebauten Limesturm – so sahen die römischen Wachtürme vor fast 1900 Jahren aus. Bei gutem Wetter seht ihr sogar die Segelflieger.',
                    'Römer-Wanderung bei Würzberg: Am Kastell steht ein teilweise wiederaufgebautes Römerbad, mit Infotafeln, Schutzhütte und Bänken für die Rast.',
                    'Eine Limes-Runde bei Vielbrunn: Rund um das alte Kastell Hainhaus lagen einst bis zu 150 römische Soldaten an der Grenze.',
                    'Perfektes Wanderwetter! Eine Runde über die Höhen rund um Bad König.',
                        'Ein Ausflug in die Obrunnschlucht bei Höchst: Am Bach entlang warten Miniaturen bekannter Burgen und Mühlen – toll für Familien.',
                        'Eine Runde um den Marbach-Stausee in Oberzent – der größte See im Odenwald, ideal zum Spazieren oder Radeln.',
                        'Hoch zur Burgruine Freienstein bei Gammelsbach – die Aussicht übers Tal ist den Aufstieg wert.',
                        'Für Fotofreunde: Das Himbächel-Viadukt bei Hetzbach – eine riesige Sandsteinbrücke mitten im Grünen, am besten wenn ein Zug drüberfährt.',
                        'Ab in den Englischen Garten Eulbach: Wildgehege, Teiche und alte Steinmonumente – ein Ausflug für die ganze Familie.',
                        'Ein Kulturspaziergang in Steinbach: Erst die Einhardsbasilika aus dem 9. Jahrhundert, dann rüber zum Schloss Fürstenau.',
                        'Bummeln, Eis essen, Fachwerk bestaunen: Die Michelstädter Altstadt mit dem Rathaus von 1484 ist bei Sonne ein Traum.',
                    'Ab aufs Rad: Der Mümlingtal-Radweg ist bei diesem Wetter genau richtig.',
                    'Wie wäre es mit dem Felsenmeer bei Reichenbach? Bei trockenem Wetter klettert es sich dort am besten.',
                    'Ein schöner Tag für einen Ausflug zur Burg Breuberg – mit toller Aussicht übers Mümlingtal.'])
    rz = regenzeit(d)
    if rz: r += ' Packt aber für %s die Regenjacke ein.' % rz.replace('am ', 'den ').replace('den ganzen Tag über', 'alle Fälle')
    r += abend_tipp(heute, rnd)
    return r


def tagtext(d, wann):
    s = '%s gibt es %s bei Höchstwerten um %s Grad.' % (wann, art(d), zahl(d['tmax']))
    rz = regenzeit(d)
    if rz and wort(d['code']) not in ('Regen',): s += ' Regen ist vor allem %s wahrscheinlich.' % rz
    if d['tmin'] <= 0: s += ' In der Nacht wird es frostig, bis %s Grad.' % zahl(d['tmin'])
    if d['boe'] >= 60: s += ' Vorsicht, Sturmböen bis %d Kilometer pro Stunde!' % round(d['boe'])
    elif d['boe'] >= 45: s += ' Dazu frischer Wind mit Böen um %d.' % round(d['boe'])
    return s


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


def abschied(d, rnd):
    w = wort(d['code'])
    if w == 'Gewitter' or d['boe'] >= 60:
        return 'Euer Max sagt: Heute lieber drinnen bleiben – passt auf euch auf!'
    if w == 'Schnee' or d['schnee'] >= 1:
        return 'Euer Max sagt: Warm einpacken, vorsichtig fahren – und viel Spaß im Schnee!'
    if w in ('Regen', 'Nieselregen', 'Schauer') or d['rp'] >= 60:
        return rnd.choice(['Euer Max sagt: Macht es euch heute gemütlich – der Odenwald läuft nicht weg!',
                           'Euer Max sagt: Tee kochen, Füße hoch – das nächste Wanderwetter kommt bestimmt!'])
    if d['tmax'] <= 3:
        return 'Euer Max sagt: Dick einpacken – und dann raus an die frische Luft!'
    return 'Euer Max sagt: Rucksack auf und raus – der Odenwald wartet!'


def skript(days, warn, heute, nur_special=False):
    rnd = random.Random(heute.isoformat())
    a, b = days[0], days[1]
    seg = []
    gruss = rnd.choice(['Ei gude, Odenwald! Hier ist euer Max.', 'Guten Morgen, Bad König! Euer Max meldet sich vom Wanderweg.',
                        'Ei gude wie, Odenwald? Max hier, euer Outdoor-Guide.', 'Moin aus dem Mümlingtal – euer Max ist schon draußen!'])
    sp = special_grund(days, warn)
    if nur_special or sp:
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
        seg.append(dict(art='intro', bg='schloss', text=gruss + (' Für alle, die neu dabei sind: Ich bin Max, Wanderführer aus Vielbrunn.' if heute.weekday() == 0 else '') + ' Das ist euer Odenwald-Wetter für %s.' % TAGE[heute.weekday()]))
    seg.append(dict(art='tag', tag=a, titel='HEUTE', bg='auto', text=tagtext(a, 'Heute')))
    seg.append(dict(art='tipp', tag=a, bg='wald' if a['rp'] < 40 else 'schloss', text=rnd.choice(['Mein Outdoor-Tipp für heute: ', 'Max-Tipp des Tages: ', 'Und jetzt mein Tipp: ']) + tipp(a, rnd, heute) + max_privat(a, rnd, heute)))
    if not nur_special:
        seg.append(dict(art='tag', tag=b, titel='MORGEN', bg='hoehen',
                        text=tagtext(b, 'Und morgen, am %s,' % TAGE[b['datum'].weekday()]).replace('Und morgen, am %s, gibt' % TAGE[b['datum'].weekday()], 'Morgen, am %s, gibt' % TAGE[b['datum'].weekday()])))
        if heute.weekday() <= 4 and len(days) >= 7:
            sa = next(d for d in days if d['datum'].weekday() == 5)
            so = next(d for d in days if d['datum'].weekday() == 6)
            if sa['datum'] > b['datum'] or so['datum'] > b['datum']:
                gut = [n for n, d in (('Samstag', sa), ('Sonntag', so)) if d['rp'] < 40]
                t = 'Ein Blick aufs Wochenende: Samstag %s bei %s Grad, Sonntag %s bei %s Grad.' % (wort(sa['code']), zahl(sa['tmax']), wort(so['code']), zahl(so['tmax']))
                t += (' Euer Ausflugstag ist der %s!' % gut[0]) if len(gut) == 1 else (' Beide Tage sehen gut aus für draußen!' if gut else ' Plant lieber etwas für drinnen ein.')
                seg.append(dict(art='wochenende', tage=[sa, so], bg='wald', text=t))
    seg.append(dict(art='outro', bg='schloss', text=rnd.choice(['Alle Live-Werte findet ihr auf wetter-badkoenig.de.', 'Mehr gibt es live auf wetter-badkoenig.de.'])
                       + ' ' + abschied(a, rnd)))
    return seg


def skript_abend(days, warn, heute):
    """Abendvideo (TikTok): Ausblick auf morgen, freitags aufs Wochenende."""
    rnd = random.Random('abend' + heute.isoformat())
    b = days[1]; morgen = b['datum']
    wt = TAGE[morgen.weekday()]
    seg = []
    w = wort(b['code'])
    if warn: hook = 'Achtung, Odenwald! Für morgen gibt es eine Wetterwarnung – bleibt dran!'
    elif w == 'Schnee' or b['schnee'] >= 1: hook = 'Schnee im Odenwald? Morgen könnte es so weit sein – bleibt dran!'
    elif w == 'Gewitter': hook = 'Morgen kracht es im Odenwald! Wann die Gewitter kommen – jetzt!'
    elif b['boe'] >= 55: hook = 'Haltet eure Mützen fest – morgen wird es stürmisch im Odenwald!'
    elif b['tmin'] <= 0: hook = 'Eiskratzer bereit? Morgen früh wird es frostig im Odenwald!'
    elif b['rp'] >= 60: hook = 'Schirm oder nicht? Ich sag euch, wann es morgen im Odenwald regnet!'
    elif b['tmax'] >= 25: hook = 'Sonnencreme raus – morgen wird es richtig warm im Odenwald!'
    elif b['rp'] < 20 and w in ('sonnig', 'heiter bis wolkig'): hook = 'Morgen wird ein Ausflugstag im Odenwald – und ich hab den perfekten Tipp!'
    else: hook = rnd.choice(['Was macht das Wetter morgen im Odenwald? In 30 Sekunden wisst ihr es!', 'Wetter für morgen in 30 Sekunden – los geht es!'])
    seg.append(dict(art='intro', bg='schloss', text=hook + ' Hier ist euer Max mit dem Wetter für %s.' % wt))
    if warn:
        seg.append(dict(art='special', karte='DWD warnt: ' + '. '.join(warn[:2]), bg='sturm',
                        text='Aber zuerst: Der Deutsche Wetterdienst warnt: %s.' % '. '.join(warn[:2])))
    t = tagtext(b, 'Morgen')
    if days[0]['tmin'] <= 0 or b['tmin'] <= 0:
        t += ' Denkt morgen früh ans Scheibenkratzen!'
    seg.append(dict(art='tag', tag=b, titel='MORGEN', bg='auto', text=t))
    seg.append(dict(art='tipp', tag=b, bg='wald' if b['rp'] < 40 else 'schloss',
                    text=rnd.choice(['Mein Tipp für morgen: ', 'Max-Tipp für morgen: ']) + tipp(b, rnd, morgen) + max_privat(b, rnd, morgen)))
    if heute.weekday() == 4 and len(days) >= 3:   # Freitag: Wochenende
        sa, so = days[1], days[2]
        gut = [n for n, d in (('Samstag', sa), ('Sonntag', so)) if d['rp'] < 40]
        t = 'Und am Sonntag: %s bei %s Grad.' % (wort(so['code']), zahl(so['tmax']))
        t += (' Euer Ausflugstag ist der %s!' % gut[0]) if len(gut) == 1 else (' Das ganze Wochenende passt für draußen!' if gut else ' Plant fürs Wochenende lieber etwas für drinnen ein.')
        seg.append(dict(art='wochenende', tage=[sa, so], bg='hoehen', text=t))
    elif len(days) >= 3:
        c = days[2]
        seg.append(dict(art='tag', tag=c, titel='ÜBERMORGEN', bg='hoehen',
                        text='Übermorgen, am %s, gibt es %s bei %s Grad.' % (TAGE[c['datum'].weekday()], art(c), zahl(c['tmax']))))
    if w == 'Gewitter' or b['boe'] >= 60: ab = 'Passt morgen gut auf euch auf. Gute Nacht!'
    elif w == 'Schnee' or b['schnee'] >= 1: ab = 'Schlitten bereitstellen – und gute Nacht!'
    elif b['rp'] >= 60: ab = 'Schirm schon mal an die Tür stellen. Gute Nacht!'
    else: ab = rnd.choice(['Rucksack packen und gut schlafen!', 'Schlaft gut – morgen geht es raus!'])
    nass = b['rp'] >= 60 or w in ('Regen', 'Schauer', 'Gewitter', 'Schnee')
    frage = rnd.choice(['Was macht ihr morgen bei dem Wetter? Schreibt es mir in die Kommentare!',
                        'Sofa oder Therme? Verratet es mir in den Kommentaren!'] if nass else
                       ['Wo geht ihr morgen hin? Schreibt mir euren Lieblingsplatz im Odenwald in die Kommentare!',
                        'Wanderschuhe oder Sofa? Schreibt es mir in die Kommentare!',
                        'Welchen Ausflugstipp habt ihr für morgen? Ab damit in die Kommentare!'])
    seg.append(dict(art='cta', bg='schloss',
                    text=frage + ' Und wenn euch mein Wetter gefällt: Folgen, liken und mit allen aus dem Odenwald teilen! Euer Max sagt: ' + ab))
    return seg


def tiktok_text(days, warn, heute):
    b = days[1]; c = days[2] if len(days) > 2 else None
    m = b['datum']
    zeilen = ['🌙 Wetter für morgen im Odenwald – %s, %d.%d.' % (TAGE[m.weekday()], m.day, m.month)]
    if warn: zeilen.append('⚠️ DWD-Warnung: ' + '. '.join(warn[:2]))
    zeilen.append('%s %s, %s bis %s °C, Regenrisiko %d %%' % ({'sonnig': '☀️', 'heiter bis wolkig': '⛅', 'bedeckt': '☁️', 'neblig': '🌫️', 'Nieselregen': '🌦️', 'Regen': '🌧️', 'Schnee': '❄️', 'Schauer': '🌦️', 'Gewitter': '⛈️'}.get(wort(b['code']), '🌤️'), wort(b['code']), zahl(b['tmin']), zahl(b['tmax']), b['rp']))
    if heute.weekday() == 4 and c:
        zeilen.append('Sonntag: %s, bis %s °C' % (wort(c['code']), zahl(c['tmax'])))
    zeilen.append('Live-Daten: wetter-badkoenig.de (Link im Profil)')
    tags = ['#badkönig', '#odenwald', '#wetter', '#wetterbericht', '#michelstadt', '#erbach', '#odenwaldkreis', '#hessen']
    w = wort(b['code'])
    extra = {'Schnee': '#schnee', 'Gewitter': '#gewitter', 'Regen': '#regen', 'neblig': '#nebel', 'sonnig': '#sonne'}.get(w)
    if extra: tags.append(extra)
    if heute.weekday() == 4: tags.append('#wochenende')
    return '\n'.join(zeilen) + '\n\n' + ' '.join(tags)


# =====================================================================
#  2) Bilder: Hintergründe, Moderator, Tafeln
# =====================================================================
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
    if art_ == 'sturm': im = verlauf(BW, BH, (70, 80, 100), (150, 160, 175))
    elif art_ == 'winter': im = verlauf(BW, BH, (150, 185, 225), (235, 242, 250))
    else: im = verlauf(BW, BH, (70, 150, 225), (250, 215, 165))
    dr = ImageDraw.Draw(im)
    r = random.Random(seed)
    if art_ not in ('sturm',):
        dr.ellipse([680, 230, 860, 410], fill=(255, 225, 120))
    farben = {'wald': [(120, 160, 140), (80, 130, 90), (50, 105, 70), (35, 80, 55)],
              'hoehen': [(150, 170, 200), (115, 150, 170), (85, 125, 120), (60, 100, 80)],
              'sturm': [(100, 110, 125), (80, 95, 100), (60, 80, 75), (45, 65, 55)],
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
    if art_ == 'winter':
        for _ in range(250):
            x, y = r.uniform(0, BW), r.uniform(0, BH); s = r.uniform(2, 5)
            dr.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255))
    return im.filter(ImageFilter.SMOOTH)


def hintergruende(seed):
    bgs = {}
    sch = Image.open(os.path.join(ROOT, 'vorschau.jpg')).convert('RGB')
    s = 1500 / sch.height
    bgs['schloss'] = sch.resize((int(sch.width * s), 1500), Image.LANCZOS)
    for k in ('wald', 'hoehen', 'sturm', 'winter'):
        bgs[k] = bg_landschaft(k, seed)
    eigene = sorted(glob.glob(os.path.join(ROOT, 'video', 'hintergruende', '*.[jp][pn]g')))
    for i, p in enumerate(eigene):  # eigene KI-Bilder ersetzen reihum die gezeichneten Landschaften
        try:
            im = Image.open(p).convert('RGB'); s = max(1000 / im.width, 1500 / im.height)
            bgs['eigen%d' % i] = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
        except Exception as e:
            print('Bild übersprungen:', p, e)
    return bgs


# --- der Moderator ---
HAUT, HAAR, JACKE, JACKE2, HOSE, LINIE = (247, 205, 170), (95, 60, 35), (30, 130, 120), (240, 140, 40), (55, 65, 80), (25, 30, 40)


def look_fuer(d):
    w = wort(d['code'])
    if w == 'Schnee' or d['schnee'] >= 1 or d['tmax'] <= 4: return 'winter'
    if w in ('Regen', 'Gewitter', 'Nieselregen') or d['rp'] >= 60: return 'regen'
    if w in ('sonnig', 'heiter bis wolkig') and d['tmax'] >= 20: return 'sonne'
    return 'normal'


def moderator(mund, blinzeln, zeigen, wink=0, look='normal'):
    """zeigen: 0 = Arm hängt, 1 = zeigt zur Tafel, 2 = Daumen hoch, 3 = winkt"""
    S = 2  # doppelt zeichnen, dann verkleinern = glatte Linien
    w, h = 380 * S, 760 * S
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    L = 5 * S
    cx = w // 2
    def P(*xy): return [v * S for v in xy]
    # Rucksack (schaut hinter den Schultern hervor)
    d.rounded_rectangle(P(92, 262, 288, 500), radius=40 * S, fill=(150, 45, 40), outline=LINIE, width=L)
    d.rounded_rectangle(P(150, 236, 230, 280), radius=18 * S, fill=(150, 45, 40), outline=LINIE, width=L)
    # Beine + Wanderschuhe
    d.rounded_rectangle(P(130, 520, 182, 720), radius=20 * S, fill=HOSE, outline=LINIE, width=L)
    d.rounded_rectangle(P(198, 520, 250, 720), radius=20 * S, fill=HOSE, outline=LINIE, width=L)
    d.rounded_rectangle(P(115, 700, 188, 745), radius=16 * S, fill=(120, 75, 45), outline=LINIE, width=L)
    d.rounded_rectangle(P(192, 700, 265, 745), radius=16 * S, fill=(120, 75, 45), outline=LINIE, width=L)
    # linker Arm (hängt, Hand an der Hüfte)
    d.line(P(118, 330, 92, 450, 120, 530), fill=LINIE, width=48 * S, joint='curve')
    d.line(P(118, 330, 92, 450, 120, 530), fill=JACKE, width=36 * S, joint='curve')
    d.ellipse(P(100, 512, 142, 554), fill=HAUT, outline=LINIE, width=L)
    # Rumpf: Softshelljacke mit Weste
    d.rounded_rectangle(P(108, 290, 272, 560), radius=46 * S, fill=JACKE, outline=LINIE, width=L)
    d.polygon(P(150, 300, 190, 300, 182, 560, 150, 560), fill=JACKE2, outline=LINIE)     # Weste links
    d.polygon(P(230, 300, 190, 300, 198, 560, 230, 560), fill=JACKE2, outline=LINIE)     # Weste rechts
    d.line(P(190, 300, 190, 560), fill=(220, 220, 225), width=4 * S)                    # Reißverschluss
    d.rounded_rectangle(P(156, 400, 184, 430), radius=5 * S, fill=(205, 110, 30), outline=LINIE, width=3 * S)  # Tasche
    d.rounded_rectangle(P(196, 400, 224, 430), radius=5 * S, fill=(205, 110, 30), outline=LINIE, width=3 * S)
    d.polygon(P(148, 278, 190, 330, 232, 278, 224, 300, 190, 345, 156, 300), fill=JACKE, outline=LINIE)  # Softshell-Stehkragen
    d.polygon(P(166, 284, 190, 318, 214, 284), fill=(245, 245, 245), outline=LINIE)
    for x0, x1 in ((132, 146), (248, 234)):                                                   # Rucksackgurte
        d.line(P(x0, 296, x1, 470), fill=LINIE, width=15 * S)
        d.line(P(x0, 296, x1, 470), fill=(60, 60, 70), width=10 * S)
    d.rounded_rectangle(P(150, 452, 230, 464), radius=4 * S, fill=(60, 60, 70), outline=LINIE, width=2 * S)  # Brustgurt
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
    d.line(arm, fill=LINIE, width=48 * S, joint='curve')
    d.line(arm, fill=JACKE, width=36 * S, joint='curve')
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
    if look == 'winter':   # Bommelmütze + Schal
        d.chord(P(104, 30, 276, 190), 180, 360, fill=(200, 45, 50), outline=LINIE, width=L)
        d.rounded_rectangle(P(100, 96, 280, 128), radius=14 * S, fill=(240, 240, 240), outline=LINIE, width=L)
        for x in range(120, 270, 22): d.line(P(x, 40 + abs(x - 190) // 3, x, 96), fill=(170, 30, 40), width=4 * S)
        d.ellipse(P(166, 0, 214, 48), fill=(240, 240, 240), outline=LINIE, width=L)
        d.rounded_rectangle(P(140, 250, 240, 296), radius=20 * S, fill=(200, 45, 50), outline=LINIE, width=L)
        d.rounded_rectangle(P(150, 280, 186, 400), radius=10 * S, fill=(200, 45, 50), outline=LINIE, width=L)
        for y in (330, 360): d.line(P(150, y, 186, y), fill=(240, 240, 240), width=6 * S)
    elif look == 'regen':  # gelber Friesennerz-Hut
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
    return im.resize((w // S, h // S), Image.LANCZOS)


# --- Tafeln ---
def schatten_text(d, xy, t, f, fill=(255, 255, 255), anchor='la'):
    d.text((xy[0] + 2, xy[1] + 3), t, font=f, fill=(0, 0, 0, 150), anchor=anchor)
    d.text(xy, t, font=f, fill=fill, anchor=anchor)


def tafel_tag(titel, d):
    w, h = 400, 520
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
    if s['art'] == 'tag': return tafel_tag(s['titel'], s['tag'])
    if s['art'] == 'wochenende': return tafel_wochenende(s['tage'])
    if s['art'] == 'tipp':
        t_ = s['text'].split(': ', 1)[-1]
        return tafel_text('MAX\' FREIZEIT-TIPP', [kurz(t_.split('. ')[0].rstrip('.!') + ('' if t_.split('. ')[0][-1:] in '.!' else '.'), 110)], (230, 130, 30))
    if s['art'] == 'special': return tafel_text('⚠ WETTER-SPECIAL'.replace('⚠ ', ''), [kurz(s.get('karte', s['text']), 120)], (200, 40, 40))
    if s['art'] == 'cta': return tafel_text('MACH MIT!', ['❤ Liken', '+ Folgen', '↻ Teilen', '✎ Kommentieren'], (254, 44, 85))
    if s['art'] == 'outro': return tafel_text('LIVE IM NETZ', ['wetter-badkoenig.de', 'Station Bad König · 184,5 m'], (25, 85, 160))
    return None


def kopfband(heute, special, titel=None):
    im = Image.new('RGBA', (W, 170), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    farbe = (200, 40, 40, 235) if special else (40, 30, 100, 235) if titel else (20, 60, 120, 230)
    dr.rectangle([0, 30, W, 120], fill=farbe)
    dr.rectangle([0, 120, W, 128], fill=(245, 175, 40, 255))
    schatten_text(dr, (28, 75), titel or ('WETTER-SPECIAL' if special else 'ODENWALD-WETTER'), F(40), anchor='lm')
    dr.text((W - 30, 75), '%d.%d.%d' % (heute.day, heute.month, heute.year), font=F(24, False), fill=(230, 238, 250), anchor='rm')
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
def sprich(text, pfad):
    try:
        import edge_tts
        async def go():
            await edge_tts.Communicate(text, VOICE, rate='+6%').save(pfad)
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
    bgs = hintergruende(seed)
    eigene = [k for k in bgs if k.startswith('eigen')]
    echt = True
    # Audio je Abschnitt
    for i, s in enumerate(segmente):
        p = os.path.join(tmp, 's%02d.mp3' % i)
        echt = sprich(s['text'], p) and echt
        s['dauer'] = dauer(p) + 0.35
        s['audio'] = p
    liste = os.path.join(tmp, 'liste.txt')
    with open(liste, 'w') as f:
        for s in segmente:
            pad = s['audio'].replace('.mp3', '_p.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', s['audio'], '-af', 'apad=pad_dur=0.35', '-ar', '24000', '-ac', '1', pad], check=True)
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
              '[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.065,afade=t=in:d=1.5,afade=t=out:st=%.2f:d=2,atrim=0:%.2f[m];'
              '[m][sc]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=500[md];'
              '[v][md]amix=inputs=2:duration=first:normalize=0' % (gesamt, fo, gesamt))
        try:
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', ton, '-stream_loop', '-1', '-i', musik,
                            '-filter_complex', fk, mix], check=True)
            ton = mix
        except Exception as e:
            print('Musik übersprungen:', e)

    # vorbereiten
    mods = {}
    lk = next((look_fuer(s['tag']) for s in segmente if s.get('tag')), 'normal')
    for m in range(4):
        for b_ in (0, 1):
            for z, wk in ((0, 0), (1, 0), (2, 0), (3, 0), (3, 1)):
                im_ = moderator(m, b_, z, wk * 22, lk); mods[(m, b_, z, wk)] = im_.resize((int(im_.width * 0.92), int(im_.height * 0.92)), Image.LANCZOS)
    kopf = kopfband(heute, special, titel)
    zeit = 0.0
    for k, s in enumerate(segmente):
        s['t0'] = zeit; zeit += s['dauer']
        bg = s['bg']
        if bg == 'auto':
            w = wort(s['tag']['code'])
            bg = 'winter' if w == 'Schnee' else 'sturm' if w in ('Regen', 'Gewitter') or s['tag']['boe'] >= 55 else 'hoehen'
        if eigene and bg in ('wald', 'hoehen') : bg = eigene[k % len(eigene)]
        s['bgimg'] = bgs[bg]
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
        s['partikel'] = 'regen' if bg == 'sturm' else 'schnee' if bg == 'winter' else None

    rnd = random.Random(1)
    tropfen = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(14, 26)) for _ in range(110)]
    flocken = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(2, 5), rnd.uniform(0, 6)) for _ in range(140)]

    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-i', ton, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '27', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '96k', '-af', 'apad', '-shortest', '-movflags', '+faststart', ziel], stdin=subprocess.PIPE)
    for i in range(N):
        t = i / FPS
        s = next((x for x in segmente if x['t0'] <= t < x['t0'] + x['dauer']), segmente[-1])
        lt = t - s['t0']; p = min(1, lt / max(1, s['dauer']))
        # Hintergrund mit langsamer Kamerafahrt
        bgi = s['bgimg']; bw, bh = bgi.size
        sc = 1.0 + 0.06 * p
        cw, ch = int(W * bh / H / sc * (H / bh) * (bh / H)), 0
        cw = int(min(bw, bh * W / H) / sc); ch = int(cw * H / W)
        x0 = int((bw - cw) * (0.15 + 0.7 * p)) if bw > cw + 10 else (bw - cw) // 2
        y0 = int((bh - ch) * 0.4)
        fr = bgi.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR).convert('RGBA')
        # Übergang: kurzes Einblenden aus Weiß
        if lt < 0.3 and i > 0:
            fr = Image.blend(Image.new('RGBA', (W, H), (255, 255, 255, 255)), fr, lt / 0.3)
        dr = ImageDraw.Draw(fr)
        if s['partikel'] == 'regen':
            for (x, y, l) in tropfen:
                yy = (y + t * 900) % H; xx = (x - t * 120) % W
                dr.line([xx, yy, xx - 5, yy + l], fill=(200, 215, 235, 200), width=2)
        elif s['partikel'] == 'schnee':
            for (x, y, r_, ph) in flocken:
                yy = (y + t * 60 * r_) % H; xx = (x + 20 * math.sin(t + ph)) % W
                dr.ellipse([xx - r_, yy - r_, xx + r_, yy + r_], fill=(255, 255, 255, 230))
        # Tafel (rechts oben, schiebt sich herein)
        if s['tafel'] is not None:
            tf = s['tafel']; ein = min(1, lt / 0.45); ein = 1 - (1 - ein) ** 3
            tx = int(W - tf.width - 24 + (1 - ein) * (tf.width + 40)); ty = 215
            fr.alpha_composite(tf, (tx, ty))
        # Moderator (links unten), Mund nach Lautstärke
        v = lv[i] if i < len(lv) else 0
        m = 0 if v < 0.15 else 1 if v < 0.45 else 2 if v < 0.8 else 3
        blink = 1 if (i % 95) in (0, 1, 2) else 0
        zeigt = 1 if s['tafel'] is not None and s['art'] in ('tag', 'wochenende', 'special') and lt < 2.2 else 0
        if s['art'] in ('intro', 'outro') and lt < 2.0: zeigt = 3
        elif s['art'] == 'cta' and (lt < 1.5 or lt > s['dauer'] - 2.5): zeigt = 3
        elif s['art'] == 'tipp' and 0.6 < lt < 2.6: zeigt = 2
        wk = 1 if zeigt == 3 and int(t * 5) % 2 else 0
        mod = mods[(m, blink, zeigt, wk)]
        bob = int(4 * math.sin(t * 2.2))
        mm = mod
        fr.alpha_composite(mm, (-20, H - mm.height - 150 + bob))
        fr.alpha_composite(kopf, (0, 0))
        # Untertitel
        for (a, b_, img) in s['ut']:
            if a <= t < b_:
                fr.alpha_composite(img, (20, H - img.height - 40)); break
        ff.stdin.write(fr.convert('RGB').tobytes())
    ff.stdin.close(); ff.wait()
    return gesamt, echt


def main():
    abend = '--abend' in sys.argv
    quelle = 'daten-abend.json' if abend and os.path.exists(os.path.join(FB, 'daten-abend.json')) else 'daten.json'
    daten = json.load(open(os.path.join(FB, quelle), encoding='utf-8'))
    days = [dict(d, datum=dt.date.fromisoformat(d['datum'])) for d in daten['tage']]
    warn = [' '.join(w_.capitalize() if w_.isupper() and len(w_) > 2 else w_ for w_ in x.split()) for x in (daten.get('warn') or [])]
    heute = days[0]['datum']
    if abend: return main_abend(days, warn, heute)
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
    segs = skript(days, warn, heute, nur_special)
    special = nur_special or bool(special_grund(days, warn))
    name = 'special' if nur_special else 'wetter'
    ziel = os.path.join(FB, name + '.mp4')
    gesamt, echt = baue(segs, heute, ziel, special)
    text = ' '.join(s['text'] for s in segs)
    json.dump({'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'datum': heute.isoformat(),
               'special': special, 'warn': warn, 'dauer': round(gesamt, 1), 'stimme': echt, 'skript': text},
              open(os.path.join(FB, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    archiv(name, heute, special, warn, gesamt)
    print('Video fertig: %s (%.0f s)\n%s' % (ziel, gesamt, text))


def main_abend(days, warn, heute):
    """TikTok: Abendvideo mit Ausblick auf morgen -> fb/tiktok/abend.mp4 + abend.json, Archiv der letzten 7 Tage."""
    import shutil
    td = os.path.join(FB, 'tiktok'); os.makedirs(td, exist_ok=True)
    segs = skript_abend(days, warn, heute)
    ziel = os.path.join(td, 'abend.mp4')
    titel = 'WOCHENENDWETTER' if heute.weekday() == 4 else 'WETTER MORGEN'
    gesamt, echt = baue(segs, days[1]['datum'], ziel, False, titel)
    text = ' '.join(s['text'] for s in segs)
    beschr = tiktok_text(days, warn, heute)
    json.dump({'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'datum': heute.isoformat(),
               'fuer': days[1]['datum'].isoformat(), 'warn': warn, 'dauer': round(gesamt, 1), 'stimme': echt,
               'skript': text, 'beschreibung': beschr},
              open(os.path.join(td, 'abend.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    # Archiv (7 Tage)
    ad = os.path.join(td, 'archiv'); os.makedirs(ad, exist_ok=True)
    datei = heute.isoformat() + '.mp4'
    shutil.copy(ziel, os.path.join(ad, datei))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '3', '-i', os.path.join(ad, datei), '-frames:v', '1', '-vf', 'scale=270:-2', '-q:v', '5',
                    os.path.join(ad, datei.replace('.mp4', '.jpg'))], check=False)
    lp = os.path.join(ad, 'liste.json')
    try: liste = json.load(open(lp, encoding='utf-8'))
    except Exception: liste = []
    liste = [e for e in liste if e['datei'] != datei]
    liste.append({'datum': heute.isoformat(), 'fuer': days[1]['datum'].isoformat(), 'datei': datei, 'dauer': round(gesamt, 1), 'beschreibung': beschr})
    grenze = (heute - dt.timedelta(days=6)).isoformat()
    for f in glob.glob(os.path.join(ad, '*.mp4')) + glob.glob(os.path.join(ad, '*.jpg')):
        if os.path.basename(f)[:10] < grenze: os.remove(f)
    liste = sorted([e for e in liste if e['datum'] >= grenze], key=lambda e: e['datei'], reverse=True)
    json.dump(liste, open(lp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('TikTok-Video fertig: %s (%.0f s)\n%s\n---\n%s' % (ziel, gesamt, text, beschr))


def archiv(name, heute, special, warn, gesamt, tage=7):
    """Videothek: Kopie + Vorschaubild nach fb/archiv/, alles älter als 7 Tage wird gelöscht."""
    import shutil
    ad = os.path.join(FB, 'archiv'); os.makedirs(ad, exist_ok=True)
    datei = heute.isoformat() + ('-special' if name == 'special' else '') + '.mp4'
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
