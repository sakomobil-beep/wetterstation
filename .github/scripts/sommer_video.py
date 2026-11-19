#!/usr/bin/env python3
"""Themenvideo „Max erklärt: Der Jahrhundertsommer 2026“ (Querformat 1280×720, ca. 11 Minuten).
Gleiche Aufmachung wie El Niño / Polarwirbel / Vulkane, eigene Grafiken, Max im T-Shirt mit Sonnenbrille (Look 'sonne').
Inhalte: wetter-badkoenig.de/sommer2026.html + Recherche (DWD, WSA/BfG, dpa) + Messwerte der eigenen Station (Archiv Juni–August).
Ausgabe: fb/thema-sommer.mp4 + fb/thema-sommer.json (kein Autopost – Kingman postet selbst)."""
import os, sys, math
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import themen_video as T
import polarwirbel_video as PW          # gemeinsame Hilfen (wie bei den Vulkanen)
from themen_video import W, H, F, verlauf, pfeil, wolke, GELB, ROT, BLAU, DUNKEL

T.STAND = 'Stand: November 2026'
T.ZIEL = 'thema-sommer'
T.LOOK = 'sonne'   # T-Shirt, Kappe und Sonnenbrille
T.TITEL = 'Max erklärt: Der Jahrhundertsommer 2026'
T.KARTE_TITEL = ('Der Jahrhundertsommer 2026', 'Max erklärt · Hitze, Dürre und ein Rhein ohne Wasser')
T.LINK = 'wetter-badkoenig.de/sommer2026.html'
T.INTRO = ('41,8 Grad, so viele heiße Tage wie nie und ein Rhein, der bei Kaub fast verschwindet: Max blickt zurück auf den Sommer 2026 – '
           'mit den Messwerten unserer Station in Bad König, den Rekorden in Deutschland, dem Niedrigwasser für die Schifffahrt '
           'und der Frage, welche Rolle der Klimawandel spielt.')
T.TAGS = '#Sommer2026 #Hitze #Niedrigwasser #Rhein #Odenwald #MaxErklärt'
T.QUELLEN = ('Quellen: DWD · Wasserstraßen- und Schifffahrtsverwaltung · BfG · dpa / ZDFheute / hessenschau · Robert Koch-Institut · '
             'Copernicus · eigene Messwerte Station IBADKN33 · wetter-badkoenig.de/sommer2026.html')
T.STATISCH = ('odenwald', 's_glossar')

# Eigene Messwerte Station Bad König, Sommer 2026 (Archiv data/archiv/tage-2026.json, 1.6.–31.8., 92 Tage, ausgewertet 19.11.2026)
ST = dict(mittel=21.3, max=38.9, max_tag='27. Juni', min=5.9, min_tag='24. August', sommertage=70, heiss=39, sehr_heiss=14, tropen=1,
          regen=94.0, regentage=25, serie=11, trocken=15,
          monate=[('Juni', 21.0, 38.9, 31.6, 12), ('Juli', 21.6, 38.3, 12.8, 13), ('August', 21.3, 37.5, 49.5, 14)],
          welle=[('25.6.', 35.9), ('26.6.', 38.4), ('27.6.', 38.9), ('28.6.', 38.0), ('29.6.', 27.8)])

T.KAPITEL = [
    dict(titel='Der Jahrhundertsommer 2026', szene='s_sonne', teile=[
        ('Hallo und herzlich willkommen zu einer neuen Folge von „Max erklärt“. Ihr seht schon: Heute habe ich mal T-Shirt und Sonnenbrille an. Denn heute geht es um den Sommer 2026.', None),
        ('Ein Sommer, den wohl keiner von uns so schnell vergisst: Hitze wie nie, kaum Regen, Sonne ohne Ende. Und am Ende ein Rhein, der so wenig Wasser hatte wie noch nie seit Beginn der Messungen.', ('Sommer 2026', 'Hitze, Dürre, Niedrigwasser')),
        ('In diesem Video schauen wir uns an, wie der Sommer abgelaufen ist, welche Rekorde gefallen sind, was unsere eigene Station hier in Bad König gemessen hat, was das Niedrigwasser für die Schifffahrt bedeutet hat und welche Rolle der Klimawandel spielt.', None),
    ]),
    dict(titel='1. Die Bilanz in Zahlen', szene='s_bilanz', teile=[
        ('Fangen wir mit der Bilanz des Deutschen Wetterdienstes an. Im Mittel lag die Temperatur in Deutschland bei 19,6 Grad. Das sind 3,3 Grad mehr als im Vergleichszeitraum 1961 bis 1990.', ('Deutschland', '19,6 °C im Mittel · +3,3 Grad')),
        ('Damit war es der zweitwärmste Sommer seit Beginn der Messungen 1881. Nur der berühmte Jahrhundertsommer 2003 war mit 19,7 Grad noch ein Zehntelgrad wärmer.', ('Platz 2 seit 1881', 'nur 2003 minimal wärmer')),
        ('Beim Regen sah es mager aus: Rund 171 Liter pro Quadratmeter, nur gut 72 Prozent der üblichen Menge. In Hessen waren es sogar nur 57 Prozent.', ('Regen', '72 % · Hessen nur 57 %')),
        ('Und die Sonne schien rund 779 Stunden lang. Damit gehört der Sommer zu den fünf sonnigsten seit 1951.', ('Sonne', 'rund 779 Stunden')),
        ('Der DWD hat das in einem Satz zusammengefasst: historische Hitze, verbreitete Trockenheit und außergewöhnlich viel Sonnenschein.', None),
    ]),
    dict(titel='2. So lief der Sommer', szene='s_chronik', teile=[
        ('Schauen wir auf den Ablauf. Der Juni wurde der zweitwärmste seit Messbeginn. Vom 18. bis 28. Juni lag Deutschland elf Tage lang unter einer Hitzeglocke, wie man sie sonst nur vom Mittelmeer kennt.', ('Juni', 'Hitzewelle 18.–28. Juni')),
        ('Am 26. Juni knackte Saarbrücken-Burbach mit 41,3 Grad den alten deutschen Rekord. Und schon einen Tag später kam Möckern-Drewitz in Sachsen-Anhalt auf 41,8 Grad. Das ist der neue deutsche Allzeitrekord.', ('27. Juni', '41,8 °C Möckern-Drewitz')),
        ('Der alte Rekord von 41,2 Grad aus dem Juli 2019 wurde damit um sechs Zehntel übertroffen. Mehr als die Hälfte der Stationen mit langer Messreihe hatte einen neuen Allzeitrekord.', ('Alter Rekord', '41,2 °C, Juli 2019')),
        ('Der Juli war der drittwärmste, in Hessen mit historischer Trockenheit. Und ab dem 8. August rollte die nächste Hitzewelle mit über 35 Grad heran.', ('Juli und August', 'Trockenheit und neue Hitze')),
        ('Erst in der zweiten Augusthälfte brachten Gewitter regional wieder kräftigen Regen.', None),
    ]),
    dict(titel='3. Die Rekorde', szene='s_rekorde', teile=[
        ('Ein paar Rekorde muss man sich wirklich auf der Zunge zergehen lassen.', None),
        ('Im sächsischen Kubschütz fiel die Temperatur Ende Juni eine ganze Nacht lang nicht unter 29,4 Grad. Das ist die wärmste je in Deutschland gemessene Nacht.', ('Wärmste Nacht', '29,4 °C Kubschütz')),
        ('Im Deutschlandmittel gab es rund 22 heiße Tage mit mindestens 30 Grad. Früher waren es im Schnitt vier. Dazu etwa fünf sehr heiße Tage mit 35 Grad und mehr.', ('Heiße Tage', '22 statt früher 4')),
        ('Das wärmste Bundesland war das Saarland mit 21,3 Grad im Mittel. Und sogar auf Helgoland gab es zum ersten Mal einen heißen Tag.', ('Saarland', '21,3 °C · Helgoland erstmals heiß')),
        ('Der DWD nennt die Häufigkeit der Hitze in diesem Sommer „beispiellos“.', None),
    ]),
    dict(titel='4. Schlimmer als 2003?', szene='s_vergleich', teile=[
        ('Bleibt die Frage: War 2026 nun schlimmer als 2003? Die Antwort ist: Es kommt darauf an, wie man misst.', None),
        ('Beim Mittelwert über den ganzen Sommer liegt 2003 mit 19,7 Grad knapp vorn. 2026 kommt auf 19,6 Grad.', ('Mittelwert', '2003: 19,7 · 2026: 19,6 °C')),
        ('Bei den Extremen hat 2026 aber alles übertroffen: noch nie so viele heiße und sehr heiße Tage, der höchste je gemessene Wert und die wärmste Nacht.', ('Extreme', 'alles Rekord 2026')),
        ('Der Schwerpunkt lag im Westen und Südwesten. In Baden-Württemberg und voraussichtlich auch in Hessen war es sogar der wärmste Sommer seit 1881. Hessen kam auf rund 19,9 Grad.', ('Hessen', 'rund 19,9 °C – wohl Rekord')),
    ]),
    dict(titel='5. Was unsere Station gemessen hat', szene='s_station', teile=[
        ('Jetzt wird es persönlich. Unsere Wetterstation in Bad König misst seit dem 20. Januar 2026 und hat den ganzen Sommer lückenlos mitgeschrieben. Hier sind unsere eigenen Zahlen von Juni bis August.', ('Station Bad König', '92 von 92 Tagen gemessen')),
        ('Das Mittel lag bei 21,3 Grad. Der heißeste Tag war der 27. Juni, derselbe Tag wie der Deutschlandrekord, mit 38,9 Grad hier im Mümlingtal.', ('Höchstwert', '38,9 °C am 27. Juni')),
        ('An 39 Tagen erreichten wir 30 Grad oder mehr, an 14 Tagen sogar 35 Grad. Und an 70 Tagen war es mindestens ein Sommertag mit 25 Grad.', ('Bad König', '39 heiße · 14 sehr heiße Tage')),
        ('Die Hitzewelle Ende Juni sah bei uns so aus: 35,9 Grad am 25., dann 38,4, 38,9 und 38,0 Grad. Elf Tage am Stück lagen wir bei 30 Grad und mehr.', ('Ende Juni', '11 Tage am Stück ab 30 °C')),
        ('Und jetzt das Spannende: Tropennächte, in denen es nicht unter 20 Grad abkühlt, hatten wir nur eine einzige. In klaren Nächten fließt bei uns kühle Luft von den Odenwaldhöhen ins Tal. In den Städten am Rhein war das ganz anders.', ('Tropennächte', 'nur 1 – dank Kaltluft im Tal')),
    ]),
    dict(titel='5. Was unsere Station gemessen hat', szene='s_regen', teile=[
        ('Beim Regen hat unsere Station nur 94 Liter pro Quadratmeter gemessen, verteilt auf 25 Tage mit mindestens einem Liter.', ('Regen', '94 l/m² in 3 Monaten')),
        ('Der Juli war mit nicht einmal 13 Litern extrem trocken. Mitte Juli gab es bei uns 15 Tage am Stück praktisch ohne Regen.', ('Juli', 'nur 12,8 l/m²')),
        ('Erst der August brachte mit knapp 50 Litern etwas Entlastung. Den meisten Regen an einem Tag gab es ganz am Ende, am 31. August mit 9,6 Litern.', ('August', '49,5 l/m²')),
        ('Wenn bei solcher Hitze Gewitter kommen, prasselt oft viel Regen auf einmal herunter. Auf dem ausgetrockneten Boden versickert der schlecht und läuft einfach ab.', None),
    ]),
    dict(titel='6. Ein Fluss ohne Wasser: die Schifffahrt', szene='s_rhein', teile=[
        ('Und damit kommen wir zu einem Thema, das diesen Sommer ganz besonders geprägt hat: das Niedrigwasser und die Schifffahrt.', None),
        ('Der Rhein ist die wichtigste Wasserstraße Europas. Und die engste Stelle liegt ganz in unserer Nähe, bei Kaub am Mittelrhein, zwischen Mainz und Koblenz. Der Pegel dort ist für die ganze Binnenschifffahrt der wichtigste Messwert.', ('Pegel Kaub', 'Nadelöhr am Mittelrhein')),
        ('Wichtig zu wissen: Der Pegel ist nicht die Wassertiefe. Er ist ein Referenzwert. Auch bei null Zentimetern ist die Fahrrinne bei Kaub noch gut einen Meter tief.', ('Pegel ≠ Tiefe', 'Fahrrinne noch gut 1 m tiefer')),
        ('Normalerweise beginnt die Niedrigwasserzeit erst im Herbst. 2026 waren die Flüsse aber schon mitten im Sommer an historischen Marken. Ende Juli lag Kaub bei nur noch 27 Zentimetern.', ('Ende Juli', 'Kaub nur noch 27 cm')),
    ]),
    dict(titel='6. Ein Fluss ohne Wasser: die Schifffahrt', szene='s_pegel', teile=[
        ('Hier seht ihr den Verlauf. Der bisherige Tiefstwert stammte vom Oktober 2018: 25 Zentimeter.', ('Rekord bisher', '25 cm, Oktober 2018')),
        ('Ende der ersten Augustwoche wurde dieser Wert unterschritten. Und am 14. August zeigte der Pegel Kaub zum ersten Mal überhaupt einen einstelligen Wert, etwa acht Zentimeter. Die digitale Anzeige am Pegelhaus zeigte gar nichts mehr an.', ('14. August', 'erstmals einstellig')),
        ('Mit dem Regen in der zweiten Augusthälfte stieg der Rhein kurz wieder an. Aber im September ging es erneut abwärts, und Ende September fiel der Pegel zeitweise sogar unter den Nullpunkt.', ('Ende September', 'unter null')),
        ('Auch Elbe und Donau waren betroffen. An der Elbe in Sachsen musste der Güterverkehr schon Ende April weitgehend eingestellt werden. Auf der Donau standen rund drei Viertel der Messstellen bei extremem Niedrigwasser.', ('Elbe und Donau', 'Güterverkehr eingestellt')),
        ('Laut dem EU-Klimadienst Copernicus führten Europas Flüsse im Sommer 2026 so wenig Wasser wie noch nie seit Beginn dieser Aufzeichnungen 1992.', ('Europa', 'niedrigster Abfluss seit 1992')),
    ]),
    dict(titel='6. Ein Fluss ohne Wasser: die Schifffahrt', szene='s_schiff', teile=[
        ('Was heißt das für die Schiffe? Ein festes Fahrverbot gibt es bei Niedrigwasser nicht. Jeder Kapitän entscheidet selbst, ob und wie viel er noch lädt.', ('Kein Fahrverbot', 'Kapitän entscheidet')),
        ('Aber je tiefer der Pegel, desto weniger Ladung passt aufs Schiff. Zum Teil konnten die Schiffe nur noch ein Viertel ihrer normalen Fracht laden. Für dieselbe Menge braucht man dann viel mehr Fahrten, und die Frachtpreise steigen stark.', ('Ladung', 'teils nur noch ein Viertel')),
        ('Fähren am Mittelrhein wurden zeitweise eingestellt, zum Beispiel an der Loreley. Und Flusskreuzfahrten auf Donau und Rhein wurden abgesagt oder umgebucht.', ('Fähren und Kreuzfahrten', 'eingestellt oder abgesagt')),
        ('Die Industrie hat das deutlich gespürt: Chemie- und Stahlwerke am Rhein, Baustoffe, Heizöl und Kohle. Die Fracht wich auf Bahn und Lkw aus, und dort wurde es eng.', ('Wirtschaft', 'Chemie, Stahl, Baustoffe, Energie')),
        ('Auch Hessen hat reagiert und das Lkw-Fahrverbot an Sonn- und Feiertagen gelockert. Denn auch die Häfen am Main hängen am Rhein und damit am Nadelöhr Kaub.', ('Hessen', 'Lkw-Sonntagsfahrverbot gelockert')),
    ]),
    dict(titel='7. Was die Hitze angerichtet hat', szene='s_folgen', teile=[
        ('Aber nicht nur die Schifffahrt hat gelitten. Am schwersten wiegt die Gesundheit: Nach einer Schätzung des Robert Koch-Instituts starben bis Mitte August rund 15.800 Menschen in Deutschland an den Folgen der Hitze.', ('Gesundheit', 'rund 15.800 Hitzetote')),
        ('In der Landwirtschaft gab es braune Felder, Risse im Boden, kleine Kartoffeln und eine schwache Maisernte. Vielerorts wurde das Futter für das Vieh knapp.', ('Landwirtschaft', 'schwache Ernte, Futter knapp')),
        ('Dazu kamen großflächige Waldbrände, versiegende Bäche und sinkendes Grundwasser. Und regional heftige Unwetter, sogar mit Tornados.', ('Natur', 'Waldbrände, Bäche, Grundwasser')),
        ('Für Fische war die Kombination aus wenig Wasser und warmem Wasser besonders gefährlich, weil warmes Wasser weniger Sauerstoff aufnehmen kann.', None),
    ]),
    dict(titel='8. Welche Rolle spielt der Klimawandel?', szene='s_klima', teile=[
        ('Und jetzt die große Frage: Was hat der Klimawandel damit zu tun?', None),
        ('Eine Studie des Deutschen Wetterdienstes zur Hitzewelle Ende Juni kam zu einem klaren Ergebnis: Ohne den Klimawandel wäre eine Hitzewelle in diesem Ausmaß statistisch unmöglich gewesen.', ('DWD-Studie', 'ohne Klimawandel „unmöglich“')),
        ('Auch die Forschungsgruppe World Weather Attribution kam zu dem Schluss: Eine so starke Hitzewelle so früh im Jahr hätte es vor 50 Jahren nicht gegeben.', ('Attributionsforschung', 'vor 50 Jahren nicht möglich')),
        ('Fachleute sprechen deshalb von einer Zäsur: Deutschland erreicht inzwischen Werte, die man bisher nur aus Frankreich oder Spanien kannte. Und Hitzesommer wie dieser werden in Zukunft häufiger.', ('Zäsur', 'Werte wie in Spanien')),
    ]),
    dict(titel='9. Kleines Sommer-Lexikon', szene='s_glossar', teile=[
        ('Zum Schluss die wichtigsten Begriffe. Sommertag: mindestens 25 Grad. Heißer Tag: mindestens 30 Grad. Sehr heißer Tag: ab 35 Grad. Und eine Tropennacht: Die Temperatur fällt nicht unter 20 Grad.', None),
        ('Pegel: ein Referenzwert für den Wasserstand, nicht die Wassertiefe. Fahrrinne: der vertiefte Weg für die Schiffe im Fluss. Und Abladetiefe: wie tief ein beladenes Schiff im Wasser liegen darf.', None),
        ('Und Attribution heißt: Forscher berechnen, wie viel wahrscheinlicher ein Wetterereignis durch den Klimawandel geworden ist.', None),
    ]),
    dict(titel='Fazit', szene='odenwald', teile=[
        ('Fassen wir zusammen. Der Sommer 2026 war der zweitwärmste in Deutschland, aber der extremste: neuer Allzeitrekord mit 41,8 Grad, die wärmste Nacht und so viele heiße Tage wie nie.', None),
        ('Bei uns in Bad König waren es 38,9 Grad und 39 heiße Tage, aber dank der kühlen Talluft nur eine Tropennacht.', None),
        ('Und der Rhein hat gezeigt, wie verletzlich wir sind, wenn das Wasser fehlt: Am Pegel Kaub ging es bis unter null, und die Schifffahrt kam an ihre Grenzen.', None),
        ('Alle Zahlen, die Chronik und unsere Messwerte findet ihr auf wetter badkoenig punkt de unter Sommer 2026.', None),
        ('Wenn euch das Video gefallen hat, lasst gern ein Like da und folgt uns, damit ihr nichts verpasst. Und schreibt in die Kommentare: Wie habt ihr den Sommer 2026 erlebt? Danke fürs Zuschauen, und bis zum nächsten Mal bei „Max erklärt“!', None),
    ]),
]


# ---------------------------------------------------------------- Hilfen
HIMMEL_HEISS = ((255, 190, 90), (255, 235, 180))
NACHT = ((15, 25, 45), (30, 45, 80))
HELLT = (200, 215, 235)


def sonne(d, x, y, r, t, col=(255, 210, 60)):
    for k in range(12):
        a = k * math.pi / 6 + t * 0.4
        d.line([x + math.cos(a) * (r + 10), y + math.sin(a) * (r + 10), x + math.cos(a) * (r + 34 + 6 * math.sin(t * 3 + k)), y + math.sin(a) * (r + 34 + 6 * math.sin(t * 3 + k))], fill=col, width=7)
    d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(240, 160, 40), width=4)


def thermometer(d, x, y, h, wert, vmax=42, col=ROT):
    d.rounded_rectangle([x - 16, y, x + 16, y + h], radius=16, fill=(245, 245, 245), outline=(60, 60, 70), width=3)
    d.ellipse([x - 30, y + h - 12, x + 30, y + h + 48], fill=col, outline=(60, 60, 70), width=3)
    f = max(0, min(1, wert / vmax))
    d.rounded_rectangle([x - 8, y + h - f * (h - 12), x + 8, y + h + 10], radius=8, fill=col)


def kachel(d, x, y, w, h, gross, klein, col, on=True):
    d.rounded_rectangle([x, y, x + w, y + h], radius=18, fill=(25, 40, 70), outline=col if on else (70, 80, 100), width=4)
    if on:
        d.text((x + w / 2, y + h * 0.40), gross, font=F(46), fill=col, anchor='mm')
        d.text((x + w / 2, y + h * 0.78), klein, font=F(19, False), fill=HELLT, anchor='mm')


def balken(d, x, y, w, h, v, vmax, col, lab, txt):
    f = max(0, min(1, v / vmax))
    d.rectangle([x, y + h - f * h, x + w, y + h], fill=col)
    d.text((x + w / 2, y + h + 18), lab, font=F(19, False), fill=HELLT, anchor='mm')
    d.text((x + w / 2, y + h - f * h - 18), txt, font=F(22), fill=(255, 255, 255), anchor='mm')


def schiff(d, x, y, s=1.0, tief=0.0):
    """Binnenschiff: tief = 0 (voll beladen, liegt tief) … 1 (fast leer, liegt hoch)."""
    yy = y - tief * 12 * s
    d.polygon([(x, yy), (x + 300 * s, yy), (x + 280 * s, yy + 34 * s), (x + 14 * s, yy + 34 * s)], fill=(40, 60, 90), outline=(20, 25, 35))
    d.rectangle([x + 230 * s, yy - 46 * s, x + 285 * s, yy], fill=(235, 235, 240), outline=(20, 25, 35))
    d.rectangle([x + 240 * s, yy - 38 * s, x + 275 * s, yy - 26 * s], fill=(120, 170, 220))
    nc = int(4 * (1 - tief) + 0.5)
    for k in range(nc):
        d.rectangle([x + 20 * s + k * 50 * s, yy - 32 * s, x + 66 * s + k * 50 * s, yy - 2 * s], fill=[(200, 80, 50), (60, 130, 90), (230, 170, 40), (70, 110, 180)][k], outline=(20, 25, 35))


# ---------------------------------------------------------------- Szenen
def szene_s(name, t, p):
    if name == 's_sonne':
        im = verlauf(W, H, (255, 170, 70), (255, 230, 170)); d = ImageDraw.Draw(im)
        sonne(d, 780, 170, 80, t)
        d.polygon([(0, 560), (180, 470), (330, 520), (520, 440), (700, 500), (880, 450), (1040, 520), (1040, H), (0, H)], fill=(170, 150, 70))
        d.polygon([(0, 620), (260, 560), (520, 610), (800, 570), (1040, 610), (1040, H), (0, H)], fill=(190, 165, 80))
        for k in range(6):   # Hitzeflimmern
            y = 470 + k * 16
            pts = [(x, y + 4 * math.sin(x / 30 + t * 4 + k)) for x in range(0, 1041, 20)]
            d.line(pts, fill=(255, 225, 160), width=2)
        d.text((60, 90), 'Sommer 2026', font=F(64), fill=(110, 40, 10))
        d.text((62, 170), 'Juni · Juli · August', font=F(28, False), fill=(130, 60, 20))
        thermometer(d, 950, 260, 220, min(41.8, 15 + t * 3))
        return im
    if name == 's_bilanz':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        d.text((520, 88), 'Deutschland · Sommer 2026 (DWD)', font=F(30), fill=(255, 255, 255), anchor='mm')
        k = [('19,6 °C', 'Mittel · +3,3 Grad', ROT), ('Platz 2', 'seit 1881 · nur 2003 wärmer', GELB), ('72 %', 'des üblichen Regens', (120, 190, 255)), ('779 h', 'Sonnenschein', (255, 210, 60))]
        sicht = 1 + int(max(0, t - 3) / 9)
        for i, (a, b, c) in enumerate(k):
            kachel(d, 40 + (i % 2) * 490, 120 + (i // 2) * 190, 460, 170, a, b, c, i < sicht)
        return im
    if name == 's_chronik':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        x0, x1, y = 60, 1000, 360
        d.line([x0, y, x1, y], fill=HELLT, width=4)
        for i, m in enumerate(('Juni', 'Juli', 'August')):
            xa = x0 + i * (x1 - x0) / 3
            d.line([xa, y - 12, xa, y + 12], fill=HELLT, width=3)
            d.text((xa + (x1 - x0) / 6, y + 40), m, font=F(26), fill=(255, 255, 255), anchor='mm')
        def tx(mon, tag): return x0 + (mon + (tag - 1) / 31) * (x1 - x0) / 3
        ev = [(0, 18, 28, 'Hitzewelle 18.–28.6.', 0), (0, 27, 27, '41,8 °C Rekord', 1), (1, 1, 31, 'historisch trocken', 2), (2, 8, 16, 'neue Hitzewelle', 3), (2, 18, 31, 'Gewitter, Regen', 4)]
        sicht = int(max(0, t - 2) / 8) + 1
        for mon, a, b, txt, i in ev:
            if i >= sicht: continue
            xa, xb = tx(mon, a), tx(mon, b)
            col = ROT if i in (0, 1, 3) else (120, 190, 255) if i == 4 else GELB
            if a == b:
                d.ellipse([xa - 12, y - 12, xa + 12, y + 12], fill=col)
                d.line([xa, y - 12, xa, y - 130], fill=col, width=3); d.text((xa, y - 150), txt, font=F(24), fill=col, anchor='mm')
            else:
                yy = y - 60 if i % 2 == 0 else y + 90
                d.rounded_rectangle([xa, yy - 14, xb, yy + 14], radius=10, fill=col)
                d.text(((xa + xb) / 2, yy + (36 if i % 2 else -34)), txt, font=F(21), fill=col, anchor='mm')
        return im
    if name == 's_rekorde':
        im = verlauf(W, H, (60, 15, 15), (140, 40, 25)); d = ImageDraw.Draw(im)
        k = [('41,8 °C', 'Allzeitrekord · Möckern-Drewitz', (255, 210, 120)), ('29,4 °C', 'wärmste Nacht · Kubschütz', (255, 170, 120)),
             ('22', 'heiße Tage (früher 4)', (255, 220, 160)), ('21,3 °C', 'Saarland, wärmstes Land', (255, 190, 140))]
        sicht = 1 + int(max(0, t - 2) / 8)
        for i, (a, b, c) in enumerate(k):
            kachel(d, 40 + (i % 2) * 490, 90 + (i // 2) * 200, 460, 175, a, b, c, i < sicht)
        return im
    if name == 's_vergleich':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        d.text((260, 85), 'Mittel Deutschland', font=F(26), fill=(255, 255, 255), anchor='mm')
        f = min(1, t / 6)
        balken(d, 120, 150, 110, 300, 19.7 * f, 20.5, (200, 120, 60), '2003', '19,7 °C')
        balken(d, 290, 150, 110, 300, 19.6 * f, 20.5, ROT, '2026', '19,6 °C')
        if t > 12:
            d.text((750, 85), '2026 bei den Extremen vorn', font=F(26), fill=GELB, anchor='mm')
            for i, s_ in enumerate(('höchster Wert: 41,8 °C', 'wärmste Nacht: 29,4 °C', 'meiste heiße Tage: 22', 'Hessen: wohl Rekordsommer')):
                if t > 12 + i * 4:
                    d.rounded_rectangle([520, 130 + i * 100, 990, 210 + i * 100], radius=14, fill=(25, 40, 70), outline=GELB, width=3)
                    d.text((545, 170 + i * 100), '✓  ' + s_, font=F(25), fill=(255, 255, 255), anchor='lm')
        return im
    if name == 's_station':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        d.text((520, 82), 'Station Bad König (IBADKN33) · Juni bis August 2026', font=F(26), fill=(255, 255, 255), anchor='mm')
        if t < 30:
            k = [('21,3 °C', 'Mittel', GELB), ('38,9 °C', 'am 27. Juni', ROT), ('39', 'Tage ab 30 °C', (255, 150, 90)), ('14', 'Tage ab 35 °C', ROT), ('70', 'Sommertage ab 25 °C', (255, 200, 120)), ('1', 'Tropennacht', (120, 190, 255))]
            sicht = 1 + int(max(0, t - 3) / 4)
            for i, (a, b, c) in enumerate(k):
                kachel(d, 40 + (i % 3) * 325, 115 + (i // 3) * 190, 305, 170, a, b, c, i < sicht)
        else:   # Hitzewelle Ende Juni als Säulen
            d.text((520, 118), 'Hitzewelle Ende Juni in Bad König', font=F(24), fill=GELB, anchor='mm')
            f = min(1, (t - 30) / 4)
            for i, (tag, v) in enumerate(ST['welle']):
                balken(d, 110 + i * 175, 165, 120, 290, v * f, 40, ROT if v >= 35 else (255, 150, 90), tag, ('%.1f °C' % v).replace('.', ','))
            y30 = 165 + 290 - 30 / 40 * 290
            d.line([90, y30, 1000, y30], fill=GELB, width=2); d.text((1000, y30 - 14), '30 °C', font=F(18, False), fill=GELB, anchor='rm')
        return im
    if name == 's_regen':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        d.text((520, 82), 'Regen in Bad König (l/m²)', font=F(28), fill=(255, 255, 255), anchor='mm')
        f = min(1, t / 6)
        for i, (m, mi, mx, r, h30) in enumerate(ST['monate']):
            balken(d, 140 + i * 260, 140, 150, 300, r * f, 60, (120, 190, 255), m, ('%.1f' % r).replace('.', ','))
        d.text((640, 520), 'Summe Juni–August: 94 l/m² · 25 Regentage ab 1 l/m²', font=F(22, False), fill=HELLT, anchor='mm')
        if 8 < t < 22:   # Risse im Boden über dem Juli
            for k in range(7):
                x = 430 + k * 14; d.line([x, 440, x + 8 * math.sin(k), 455, x - 6, 468], fill=(160, 110, 60), width=2)
        return im
    if name in ('s_rhein', 's_schiff'):
        im = verlauf(W, H, (120, 180, 230), (200, 228, 248)); d = ImageDraw.Draw(im)
        sonne(d, 900, 90, 45, t)
        # Hänge des Mittelrheintals
        d.polygon([(0, 140), (200, 220), (320, 360), (330, 520), (0, 520)], fill=(90, 120, 60))
        d.polygon([(W, 160), (860, 230), (740, 360), (720, 520), (W, 520)], fill=(80, 110, 55))
        # Burg Pfalzgrafenstein (schematisch)
        d.rectangle([600, 360, 680, 410], fill=(235, 230, 220), outline=(80, 80, 80)); d.polygon([(600, 360), (640, 330), (680, 360)], fill=(60, 60, 70))
        # Wasser sinkt
        fall = min(1, t / 20) if name == 's_rhein' else 1
        wl = 430 + 60 * fall
        d.rectangle([0, wl, W, H], fill=(50, 110, 160))           # Wasser
        sand = int(fall * 300)                                          # trockenfallende Ufer
        if sand:
            d.polygon([(0, wl), (sand, wl), (sand + 60, 560), (0, 560)], fill=(185, 165, 120))
            d.polygon([(W, wl), (W - sand, wl), (W - 60 - sand, 560), (W, 560)], fill=(185, 165, 120))
        d.rectangle([380, 560, 650, 610], fill=(40, 95, 140))   # Fahrrinne
        d.text((515, 630), 'Fahrrinne', font=F(18, False), fill=(60, 60, 60), anchor='mm')
        # Schiff mit wenig Ladung
        sx = 160 + (t * 22) % 420
        schiff(d, sx, wl + 30, 0.9, tief=min(0.75, fall * 0.75) if name == 's_schiff' else fall * 0.5)
        # Pegellatte
        d.rectangle([60, 260, 110, 600], fill=(255, 255, 255), outline=(40, 40, 40), width=2)
        for k in range(8):
            yy = 600 - k * 42; d.line([60, yy, 85, yy], fill=(40, 40, 40), width=2); d.text((116, yy), '%d' % (k * 40), font=F(15, False), fill=(30, 30, 30), anchor='lm')
        cm = int(120 - fall * 93) if name == 's_rhein' else 8   # Ende Juli 27 cm, Mitte August ca. 8 cm
        d.text((85, 238), 'Kaub: %d cm' % cm, font=F(22), fill=(150, 20, 20), anchor='mm')
        return im
    if name == 's_pegel':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        d.text((520, 82), 'Pegel Kaub 2026 (schematisch, Zentimeter)', font=F(26), fill=(255, 255, 255), anchor='mm')
        x0, x1, y0, y1 = 100, 990, 120, 460
        def Y(v): return y1 - (v + 20) / 220 * (y1 - y0)
        for v in (0, 50, 100, 150, 200):
            d.line([x0, Y(v), x1, Y(v)], fill=(70, 85, 110), width=1); d.text((x0 - 10, Y(v)), str(v), font=F(16, False), fill=HELLT, anchor='rm')
        mon = ['Juni', 'Juli', 'Aug.', 'Sept.', 'Okt.']
        for i, m in enumerate(mon): d.text((x0 + (i + 0.5) * (x1 - x0) / 5, y1 + 22), m, font=F(18, False), fill=HELLT, anchor='mm')
        # grober Verlauf nach Meldungen (Ende Juli 27, 1. Augustwoche <25, 14.8. ~8, Mitte Aug. Anstieg, Ende Sept. <0)
        pkt = [(0, 190), (0.6, 120), (1.0, 70), (1.7, 40), (1.95, 27), (2.2, 22), (2.45, 8), (2.6, 30), (2.85, 55), (3.2, 30), (3.7, 15), (3.95, -3), (4.3, 10), (5, 25)]
        n = min(len(pkt), 2 + int(t / 2.5))
        pts = [(x0 + m * (x1 - x0) / 5, Y(v)) for m, v in pkt[:n]]
        if len(pts) > 1: d.line(pts, fill=(120, 190, 255), width=6)
        yr = Y(25); d.line([x0, yr, x1, yr], fill=GELB, width=2)
        d.text((x1, yr - 14), 'bisheriger Rekord 25 cm (2018)', font=F(17, False), fill=GELB, anchor='rm')
        d.line([x0, Y(0), x1, Y(0)], fill=ROT, width=2); d.text((x1, Y(0) + 14), 'Nullpunkt', font=F(17, False), fill=ROT, anchor='rm')
        if n > 7: d.text((x0 + 2.45 * (x1 - x0) / 5, Y(8) + 34), '14.8.: ca. 8 cm', font=F(18), fill=(255, 255, 255), anchor='mm')
        if n > 12: d.text((x0 + 3.95 * (x1 - x0) / 5, Y(-3) + 30), 'unter null', font=F(18), fill=ROT, anchor='mm')
        return im
    if name == 's_folgen':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        k = [('Gesundheit', 'ca. 15.800 Hitzetote (RKI)', ROT), ('Landwirtschaft', 'braune Felder, Futter knapp', (220, 170, 60)),
             ('Natur', 'Waldbrände, Bäche trocken', (230, 120, 50)), ('Fische', 'warmes Wasser, wenig Sauerstoff', (120, 190, 255))]
        sicht = 1 + int(max(0, t - 1) / 10)
        for i, (a, b, c) in enumerate(k):
            x = 40 + (i % 2) * 490; y = 90 + (i // 2) * 200; on = i < sicht
            d.rounded_rectangle([x, y, x + 460, y + 180], radius=18, fill=(25, 40, 70), outline=c if on else (70, 80, 100), width=4)
            if on:
                d.text((x + 230, y + 65), a, font=F(38), fill=c, anchor='mm')
                d.text((x + 230, y + 125), b, font=F(22, False), fill=HELLT, anchor='mm')
        return im
    if name == 's_klima':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        d.text((520, 82), 'Hitzetage ab 30 °C im Deutschlandmittel', font=F(26), fill=(255, 255, 255), anchor='mm')
        f = min(1, t / 8)
        balken(d, 220, 140, 170, 290, 4 * f, 24, (255, 170, 90), 'früher im Schnitt', '4')
        balken(d, 620, 140, 170, 290, 22 * f, 24, ROT, 'Sommer 2026', '22')
        if t > 14:
            d.rounded_rectangle([330, 500, 1010, 560], radius=14, fill=(25, 40, 70), outline=GELB, width=3)
            d.text((670, 530), 'Ohne Klimawandel statistisch unmöglich (DWD)', font=F(22), fill=GELB, anchor='mm')
        return im
    if name == 's_glossar':
        im = verlauf(W, H, *NACHT); d = ImageDraw.Draw(im)
        eintr = [('Sommertag', 'mindestens 25 °C'), ('Heißer Tag', 'mindestens 30 °C'), ('Sehr heißer Tag', 'ab 35 °C'), ('Tropennacht', 'nicht unter 20 °C'),
                 ('Pegel', 'Referenzwert, nicht die Wassertiefe'), ('Fahrrinne', 'vertiefter Weg der Schiffe im Fluss'), ('Attribution', 'Anteil des Klimawandels berechnen')]
        for i, (a, b) in enumerate(eintr):
            y = 90 + i * 66
            d.rounded_rectangle([60, y, 1000, y + 54], radius=12, fill=(25, 40, 70))
            d.text((85, y + 27), a, font=F(24), fill=GELB, anchor='lm')
            d.text((360, y + 27), b, font=F(22, False), fill=(255, 255, 255), anchor='lm')
        return im
    return _vor(name, t, p)


_vor = T.szene_bild
T.szene_bild = szene_s

if __name__ == '__main__':
    T.main()
