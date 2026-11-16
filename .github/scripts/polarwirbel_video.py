#!/usr/bin/env python3
"""Themenvideo „Max erklärt: Der Polarwirbel“ (Querformat 1280×720, ca. 10 Minuten).
Gleiche Aufmachung wie das El-Niño-Video (themen_video.py), eigene Grafiken, Inhalte von wetter-badkoenig.de/polarwirbel.html.
Ausgabe: fb/thema-polarwirbel.mp4 + fb/thema-polarwirbel.json (kein Autopost – Kingman postet selbst)."""
import os, sys, math
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import themen_video as T
from themen_video import W, H, F, verlauf, pfeil, wolke, GELB, ROT, BLAU, DUNKEL

T.STAND = 'Stand: Mitte November 2026'
T.ZIEL = 'thema-polarwirbel'
T.TITEL = 'Max erklärt: Der Polarwirbel – was passiert, wenn er zusammenbricht?'
T.KARTE_TITEL = ('Der Polarwirbel', 'Max erklärt · Was passiert, wenn er zusammenbricht?')
T.LINK = 'wetter-badkoenig.de/polarwirbel.html'
T.INTRO = ('Der Polarwirbel ist so schwach wie nie zu dieser Jahreszeit. Was ist dieser Wirbel hoch über der Arktis, was passiert, wenn er '
           'zusammenbricht, wie war das 2018 und 2021 – und was heißt das für den Winter im Odenwald?')
T.TAGS = '#Polarwirbel #Winter #Wetter #Odenwald #MaxErklärt'
T.QUELLEN = 'Quellen: DWD · Met Office · AWI · MeteoSchweiz · ECMWF · NOAA · wetter-badkoenig.de/polarwirbel.html'
T.STATISCH = ('odenwald', 'schichten', 'glossar')

T.KAPITEL = [
    dict(titel='Der Polarwirbel', szene='pol_stark', teile=[
        ('Hallo und herzlich willkommen zu einer neuen Folge von „Max erklärt“. Heute geht es um ein Wort, das jeden Winter durch die Nachrichten geistert: den Polarwirbel.', None),
        ('Und in diesem Herbst ist er tatsächlich eine Schlagzeile wert. Seit Anfang November ist der Polarwirbel so schwach wie noch nie zu dieser Jahreszeit seit Beginn der Messungen.', ('November 2026', 'Polarwirbel rekordschwach')),
        ('Oft liest man dann Überschriften wie „Polarwirbel bricht zusammen – Eiswinter droht“. Aber stimmt das so? Genau das schauen wir uns heute in Ruhe an.', None),
        ('Wir klären, was der Polarwirbel überhaupt ist, was bei einem Zusammenbruch passiert, wie das 2018 und 2021 war, wie die Lage gerade aussieht und was das für uns hier im Odenwald bedeuten kann.', None),
    ]),
    dict(titel='1. Was ist der Polarwirbel?', szene='pol_stark', teile=[
        ('Stellt euch die Erde von oben vor, mit dem Nordpol in der Mitte. Im Winter liegt die Arktis wochenlang im Dunkeln. Dort oben kühlt die Luft immer weiter aus.', ('Polarnacht', 'Arktis kühlt stark aus')),
        ('Zwischen der eiskalten Luft über dem Pol und der wärmeren Luft weiter südlich entsteht ein großer Temperaturunterschied. Und der treibt einen gewaltigen Westwindring an, der um den Pol kreist.', ('Antrieb', 'Temperaturunterschied Pol – Süden')),
        ('Dieser Ring aus Wind ist der Polarwirbel. Er sitzt nicht da, wo unser Wetter stattfindet, sondern viel höher: in der Stratosphäre, ungefähr zwischen sechzehn und achtundvierzig Kilometern Höhe.', ('Höhe', 'ca. 16 bis 48 km (Stratosphäre)')),
        ('Gemessen wird er meist in rund dreißig Kilometern Höhe, auf der Druckfläche von zehn Hektopascal. Dort hat es im Kern des Wirbels oft minus siebzig Grad und kälter.', ('Messhöhe', '10 hPa, ca. 30 km · um −70 °C')),
        ('Ein starker Polarwirbel ist wie ein Deckel auf der Kälte: Er hält die arktische Luft im Norden fest. Für uns heißt das meist: Westwetter, mild und oft nass.', ('Starker Wirbel', 'Kälte bleibt im Norden')),
    ]),
    dict(titel='2. Wo genau sitzt er?', szene='schichten', teile=[
        ('Damit man das richtig einordnet, schauen wir uns kurz den Aufbau der Atmosphäre an.', None),
        ('Ganz unten ist die Troposphäre. Sie reicht bei uns bis etwa zehn bis zwölf Kilometer hoch. Hier spielt sich das Wetter ab: Wolken, Regen, Schnee, Hochs und Tiefs.', ('Troposphäre', 'bis ca. 10–12 km · unser Wetter')),
        ('Darüber liegt die Stratosphäre. Dort gibt es kaum Wolken, und hier dreht sich der Polarwirbel.', ('Stratosphäre', 'ca. 12–50 km · Polarwirbel')),
        ('Nicht verwechseln darf man ihn mit dem Jetstream. Der Jetstream weht viel tiefer, in etwa zehn Kilometern Höhe, und steuert unsere Tiefdruckgebiete. Beide hängen aber zusammen, wie wir gleich sehen.', ('Jetstream', 'ca. 10 km · steuert die Tiefs')),
    ]),
    dict(titel='3. Stark, verschoben oder geteilt', szene='pol_zustaende', teile=[
        ('Der Polarwirbel hat verschiedene Zustände. Im Normalfall ist er rund, kräftig und liegt schön über dem Pol.', ('Zustand 1', 'stark und rund über dem Pol')),
        ('Er kann aber auch vom Pol weggeschoben werden, zum Beispiel Richtung Sibirien oder Kanada. Fachleute sprechen dann von einer Verschiebung, auf Englisch Displacement.', ('Zustand 2', 'verschoben (Displacement)')),
        ('Und im extremen Fall wird er in zwei oder sogar mehr Teile zerrissen. Das nennt man einen Split. Dann kann kalte Luft an mehreren Stellen nach Süden vorankommen.', ('Zustand 3', 'geteilt (Split)')),
        ('Was den Wirbel stört, kommt übrigens von unten: große Wellen in der Atmosphäre, angestoßen von Gebirgen wie den Rocky Mountains oder dem Himalaya und von großen Hochdruckgebieten. Diese Wellen laufen nach oben und rütteln am Wirbel.', ('Ursache', 'Wellen von unten rütteln am Wirbel')),
    ]),
    dict(titel='4. Wenn er zusammenbricht', szene='erwaermung', teile=[
        ('Jetzt zum spannendsten Teil: Was passiert, wenn der Polarwirbel zusammenbricht? Fachleute nennen das ein plötzliches Stratosphärenerwärmungs-Ereignis, kurz Major Warming.', ('Fachbegriff', 'Major Warming (SSW)')),
        ('Schritt eins: Sehr kräftige Wellen aus der Troposphäre laufen nach oben und brechen in der Stratosphäre, ähnlich wie Wellen am Strand.', ('Schritt 1', 'Wellen brechen in der Stratosphäre')),
        ('Schritt zwei: Dabei sinkt Luft über dem Pol ab und erwärmt sich. In wenigen Tagen kann es dort oben um bis zu fünfzig Grad wärmer werden. Mitten im Winter, in der Polarnacht.', ('Schritt 2', 'bis zu +50 °C in wenigen Tagen')),
        ('Schritt drei: Der Temperaturunterschied, der den Wirbel antreibt, bricht zusammen. Der Westwind wird schwächer und dreht schließlich auf Ost. Genau das ist das offizielle Kennzeichen: Ostwind bei sechzig Grad Nord in zehn Hektopascal.', ('Schritt 3', 'Wind dreht auf Ost (60° N, 10 hPa)')),
        ('Schritt vier: Die Störung arbeitet sich langsam nach unten durch. Das dauert meist zehn bis fünfzehn Tage, manchmal bis zu sechs Wochen.', ('Schritt 4', 'Abwärts in 10–15 Tagen, bis 6 Wochen')),
        ('Schritt fünf: Unten angekommen, wird der Jetstream welliger. Er schlägt große Bögen, Hochdruckgebiete setzen sich im Norden fest, und kalte Luft kann weit nach Süden ausbrechen. Das kann bis zu zwei Monate anhalten.', ('Schritt 5', 'welliger Jetstream, Kaltluftausbrüche')),
        ('Entdeckt hat das übrigens ein Deutscher: Richard Scherhag beobachtete 1952 über Berlin diese plötzliche Erwärmung. Lange hieß das deshalb „Berliner Phänomen“.', ('1952', 'Richard Scherhag: „Berliner Phänomen“')),
        ('Und so selten ist das gar nicht. Ein Major Warming gibt es ungefähr in jedem zweiten Winter, am häufigsten im Januar und Februar.', ('Häufigkeit', 'etwa jeder zweite Winter')),
    ]),
    dict(titel='5. Die Folgen – und keine Garantie', szene='jet', teile=[
        ('Was heißt das für das Wetter am Boden? Hier ist der wichtigste Punkt dieses Videos: Ein Zusammenbruch des Polarwirbels heißt nicht automatisch Eiswinter bei uns.', ('Wichtig', 'Zusammenbruch ≠ automatisch Eiswinter')),
        ('In etwa zwei von drei Fällen schlägt die Störung bis nach unten durch. Dann kippt oft die Nordatlantische Oszillation, kurz NAO, ins Negative. Der milde Westwind schwächelt, und Kälte hat leichteres Spiel.', ('Etwa 2 von 3 Fällen', 'Wirkung am Boden, NAO negativ')),
        ('Aber wohin die Kälte fließt, ist offen. Sie kann nach Nordamerika gehen, nach Sibirien, nach Skandinavien oder eben zu uns nach Mitteleuropa.', ('Wohin?', 'Nordamerika, Sibirien, Europa …')),
        ('Eine Studie von 2020 hat gezeigt: Entscheidend ist, wo sich danach das Hoch festsetzt. Lag es über Europa und Skandinavien, gab es in sieben von sieben Fällen Kälte in Europa. Lag es über Grönland, nur in einem von fünf Fällen.', ('Studie 2020', 'Hoch über Europa: 7 von 7 · über Grönland: 1 von 5')),
        ('Der Deutsche Wetterdienst sagt es deshalb ganz klar: Ein Major Warming erhöht die Chance auf einen Kälteeinbruch, ist aber keine Garantie.', ('DWD', 'höhere Chance, keine Garantie')),
    ]),
    dict(titel='6. Frühere Fälle', szene='zeitleiste_pw', teile=[
        ('Schauen wir uns ein paar bekannte Fälle an.', None),
        ('1952 wurde das Phänomen über Berlin entdeckt. Seitdem wird es mit Wetterballons und später mit Satelliten genau beobachtet.', ('1952', 'Entdeckung über Berlin')),
        ('Februar 2018: Nach einem Split des Polarwirbels kam das sogenannte „Beast from the East“. Eisiger Ostwind brachte Großbritannien und weiten Teilen Europas Schnee und strengen Frost, auch bei uns war es Ende Februar bitterkalt.', ('Februar 2018', '„Beast from the East“')),
        ('Februar 2021: Auch hier ging ein Major Warming voraus. In Nord- und Mitteldeutschland gab es heftigen Schneefall und strengen Frost, teils mit Schneeverwehungen. Weiter südlich war es weniger extrem.', ('Februar 2021', 'Schnee im Norden und in der Mitte')),
        ('Und es gibt viele Fälle, in denen nach einem Zusammenbruch bei uns gar nichts Besonderes passierte, weil die Kälte woanders hinfloss. Die liest man nur seltener in den Schlagzeilen.', ('Nicht vergessen', 'oft ohne Folgen bei uns')),
    ]),
    dict(titel='7. Die Lage im November 2026', szene='balken_wind', teile=[
        ('Und jetzt zur aktuellen Lage. Normalerweise baut sich der Polarwirbel im Herbst kräftig auf. Mitte November weht der Wind dort oben im Mittel mit etwa fünfundzwanzig bis achtundzwanzig Metern pro Sekunde.', ('Normal Mitte November', 'ca. 25–28 m/s Westwind')),
        ('In diesem Jahr ist er seit Anfang November rekordschwach. Zeitweise lag der Wind nur noch bei 0,3 Metern pro Sekunde. Dort oben war es rund fünfundzwanzig Grad wärmer als normal.', ('2026', 'zeitweise nur 0,3 m/s · ca. +25 °C')),
        ('Um den 11. November herum drehte der Wind sogar kurz auf Ost. So früh im Winter gab es das seit Beginn der Auswertungen 1959 noch nie. Die bisherigen Rekorde lagen jeweils am 28. November, 1968 und 2025.', ('Rekord', 'Ostwind so früh wie nie seit 1959')),
        ('Aber: Das war ein schwaches Ereignis, etwa minus zwei Meter pro Sekunde. Bei den großen Zusammenbrüchen im Hochwinter sind es minus fünfzehn bis minus dreißig.', ('Einordnung', 'schwach: ca. −2 m/s statt −15 bis −30')),
        ('Die Modelle erwarten, dass sich der Wirbel bis Ende November wieder weitgehend erholt. Eine stärkere Störung Ende November oder im Dezember halten Fachleute aber für möglich.', ('Ausblick', 'Erholung, später neue Störung möglich')),
    ]),
    dict(titel='7. Die Lage im November 2026', szene='pol_wackel', teile=[
        ('Was sagen die Fachleute? Das britische Met Office hat Anfang November erklärt, dass der schwache Wirbel die Chance auf kalte Phasen im Winter erhöht, aber eben nur die Chance.', ('Met Office, 4. November', 'mehr Chance auf Kälte')),
        ('Auch der Polarwirbel-Forscher Judah Cohen und das Alfred-Wegener-Institut betonen, wie ungewöhnlich die Lage ist, und wie unsicher, was daraus wird.', ('AWI und Judah Cohen', 'ungewöhnlich, aber unsicher')),
        ('Gleichzeitig läuft im Pazifik der Rekord-El-Niño, über den wir schon ein eigenes Video gemacht haben. Ein starker El Niño kann den Polarwirbel zusätzlich stören.', ('El Niño', 'kann den Wirbel zusätzlich stören')),
        ('Dazu kommt die QBO, ein Windwechsel hoch über dem Äquator, der alle gut zwei Jahre die Richtung wechselt. Auch sie beeinflusst, wie stabil der Wirbel ist.', ('QBO', 'Windwechsel über dem Äquator')),
        ('Und die Jahreszeitenprognosen? Das europäische Wettermodell ECMWF rechnet für den Dezember eher mit einem wärmeren Monat als normal, MeteoSchweiz erwartet insgesamt eher einen milden Winter. Ihr seht: Die Signale widersprechen sich.', ('Prognosen', 'ECMWF und MeteoSchweiz: eher mild')),
    ]),
    dict(titel='8. Was heißt das für den Odenwald?', szene='szenarien', teile=[
        ('Und was bedeutet das alles für uns hier im Odenwald? Ich habe euch drei Möglichkeiten mitgebracht.', None),
        ('Möglichkeit eins, und die ist am wahrscheinlichsten: Die Kälte geht woanders hin, nach Nordamerika oder Asien. Bei uns bleibt es wechselhaft, mal mild, mal kühl, wie in vielen Wintern.', ('Möglichkeit 1', 'Kälte geht woanders hin (am wahrscheinlichsten)')),
        ('Möglichkeit zwei: ein kurzer Wintergruß. Ein paar Tage mit Frost, vielleicht etwas Schnee in den Höhenlagen, dann wird es wieder milder.', ('Möglichkeit 2', 'kurzer Wintergruß')),
        ('Möglichkeit drei: ein echter Kälteeinbruch wie 2018, mit Ostwind und Dauerfrost über viele Tage. Das ist möglich, aber eher die Ausnahme.', ('Möglichkeit 3', 'echter Kälteeinbruch wie 2018')),
        ('Bei einer Ostlage gilt bei uns: Der Ostwind ist trocken und eisig. Es kann also bitterkalt werden, ohne dass viel Schnee fällt. Gefühlt ist es dann durch den Wind noch deutlich kälter.', ('Ostwind', 'trocken und eisig, gefühlt noch kälter')),
        ('Und dann ist da noch unsere Landschaft. In klaren, windstillen Nächten sammelt sich die kalte Luft im Mümlingtal. Hier in Bad König auf rund 185 Metern kann es dann kälter sein als oben in Vielbrunn auf 453 Metern.', ('Kaltluftsee', 'Mümlingtal oft kälter als die Höhen')),
        ('Schnee dagegen hat in den Höhenlagen, etwa in Vielbrunn oder am Katzenbuckel mit 626 Metern, die besseren Karten.', ('Schnee', 'eher in den Höhenlagen')),
    ]),
    dict(titel='9. Und der Klimawandel?', szene='klima', teile=[
        ('Bleibt eine Frage, die oft gestellt wird: Macht der Klimawandel den Polarwirbel schwächer?', None),
        ('Fest steht: Die Arktis erwärmt sich deutlich schneller als der Rest der Erde. Damit wird der Temperaturunterschied zwischen Pol und Süden kleiner.', ('Arktis', 'erwärmt sich besonders schnell')),
        ('Ob das den Polarwirbel aber häufiger stört, ist in der Forschung umstritten. Eine Studie von 2023 fand zum Beispiel keinen klaren Trend. Andere Forschende, etwa am MIT, sehen Hinweise auf mehr Störungen.', ('Forschung', 'noch kein klares Ergebnis')),
        ('Und eines zeigen die Messungen eindeutig: Bei uns gibt es heute rund dreimal so viele Wärmerekorde wie Kälterekorde. Kalte Winter gibt es weiterhin, sie werden aber seltener.', ('Rekorde', 'ca. 3× mehr Wärme- als Kälterekorde')),
    ]),
    dict(titel='10. Kleines Polarwirbel-Lexikon', szene='glossar', teile=[
        ('Zum Schluss noch die wichtigsten Begriffe zum Mitnehmen. Major Warming: der große Zusammenbruch, mit Ostwind in dreißig Kilometern Höhe. Minor Warming: eine kleinere Störung ohne Winddrehung.', None),
        ('Final Warming: das ganz normale Ende des Polarwirbels im Frühjahr. Split und Displacement: geteilter oder verschobener Wirbel.', None),
        ('NAO: die Nordatlantische Oszillation, also das Kräftemessen zwischen Azorenhoch und Islandtief. Und QBO: der Windwechsel über dem Äquator.', None),
    ]),
    dict(titel='Fazit', szene='odenwald', teile=[
        ('Fassen wir zusammen. Der Polarwirbel ist ein riesiger Windring hoch über der Arktis. Ist er stark, bleibt die Kälte im Norden.', None),
        ('Bricht er zusammen, steigt die Chance auf Kälteeinbrüche bei uns, aber erst nach ein bis zwei Wochen, und nur in etwa zwei von drei Fällen. Wohin die Kälte geht, entscheidet sich erst später.', None),
        ('In diesem Herbst ist der Wirbel so schwach wie nie zu dieser Zeit. Ob daraus ein strenger Winter wird, weiß heute noch niemand. Die meisten Prognosen sehen eher einen milden Winter, mit der Chance auf kalte Phasen.', None),
        ('Ich behalte das für euch im Blick. Alle Zahlen und Grafiken findet ihr auf wetter badkoenig punkt de unter Polarwirbel.', None),
        ('Wenn euch das Video gefallen hat, lasst gern ein Like da und folgt uns, damit ihr nichts verpasst. Und schreibt in die Kommentare: Glaubt ihr an einen richtigen Winter? Danke fürs Zuschauen, und bis zum nächsten Mal bei „Max erklärt“!', None),
    ]),
]


# ---------------------------------------------------------------- eigene Grafiken
def polkarte(d, cx, cy, r):
    """Nordhalbkugel von oben (schematisch): Meer, Landmassen, Breitenkreise."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(26, 74, 128))
    land = (92, 140, 92)
    for a0, a1, r0, r1 in ((200, 290, 0.45, 1.0), (300, 360, 0.5, 1.0), (0, 40, 0.55, 1.0), (40, 180, 0.42, 1.0), (300, 335, 0.12, 0.42)):
        pts = [(cx + r * r1 * math.cos(math.radians(a)), cy + r * r1 * math.sin(math.radians(a))) for a in range(a0, a1 + 1, 4)]
        pts += [(cx + r * r0 * (1 + 0.1 * math.sin(a / 9)) * math.cos(math.radians(a)), cy + r * r0 * (1 + 0.1 * math.sin(a / 9)) * math.sin(math.radians(a))) for a in range(a1, a0 - 1, -4)]
        d.polygon(pts, fill=land)
    for f in (0.33, 0.66):
        d.ellipse([cx - r * f, cy - r * f, cx + r * f, cy + r * f], outline=(120, 160, 200), width=1)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(200, 220, 240), width=2)


def wirbel(d, cx, cy, rx, ry, t, staerke=1.0, col=(120, 200, 255)):
    """Rotierender Windring als Pfeilsegmente."""
    n = 14
    for i in range(n):
        a = (i / n) * 2 * math.pi + t * 0.9 * staerke
        a2 = a + 0.28
        x1, y1 = cx + rx * math.cos(a), cy + ry * math.sin(a)
        x2, y2 = cx + rx * math.cos(a2), cy + ry * math.sin(a2)
        pfeil(d, x1, y1, x2, y2, col, w=max(2, int(6 * staerke)), kopf=int(10 + 8 * staerke))
    # kalter Kern
    for k in range(6, 0, -1):
        f = k / 6
        d.ellipse([cx - rx * 0.7 * f, cy - ry * 0.7 * f, cx + rx * 0.7 * f, cy + ry * 0.7 * f], fill=(int(60 + 60 * f), int(90 + 70 * f), int(200 + 30 * f)))


def beschriftung(d, x, y, text, col=(230, 240, 250), gr=22):
    d.text((x, y), text, font=F(gr), fill=col, anchor='mm')


def szene_pw(name, t, p):
    if name in ('pol_stark', 'pol_wackel'):
        im = verlauf(W, H, (8, 14, 32), (22, 34, 66)); d = ImageDraw.Draw(im)
        cx, cy, r = 600, 390, 290
        polkarte(d, cx, cy, r)
        if name == 'pol_stark':
            wirbel(d, cx, cy, 180, 170, t)
            d.text((cx, 690), 'Blick von oben auf den Nordpol (schematisch): Westwindring um die Arktis', font=F(19, False), fill=(200, 215, 235), anchor='mm')
        else:
            dx = 70 * math.sin(t * 0.7); dy = 40 * math.sin(t * 0.5)
            wirbel(d, cx + dx, cy + dy, 150 + 20 * math.sin(t), 110, t, 0.45, col=(170, 210, 240))
            d.text((cx, 690), 'Geschwächter Wirbel: langsam, verformt, aus der Mitte geschoben (schematisch)', font=F(19, False), fill=(200, 215, 235), anchor='mm')
        d.text((cx, cy - 6), 'N', font=F(26), fill=(255, 255, 255), anchor='mm')
        return im
    if name == 'pol_zustaende':
        im = verlauf(W, H, (8, 14, 32), (22, 34, 66)); d = ImageDraw.Draw(im)
        aktiv = min(2, int(t / 9))
        for i, (tit, cx) in enumerate((('stark', 230), ('verschoben', 560), ('geteilt (Split)', 890))):
            r = 130; cy = 245
            polkarte(d, cx, cy, r)
            if i == 0: wirbel(d, cx, cy, 85, 80, t, 0.8)
            if i == 1: wirbel(d, cx + 45, cy - 35, 70, 55, t, 0.6)
            if i == 2:
                wirbel(d, cx - 60, cy + 30, 45, 40, t, 0.5); wirbel(d, cx + 60, cy - 35, 45, 40, -t, 0.5)
            c = GELB if i <= aktiv else (140, 150, 170)
            d.rounded_rectangle([cx - 120, cy + r + 18, cx + 120, cy + r + 62], radius=12, fill=(15, 25, 45), outline=c, width=3)
            d.text((cx, cy + r + 40), tit, font=F(24), fill=c, anchor='mm')
        return im
    if name == 'schichten':
        im = verlauf(W, H, (6, 10, 30), (130, 180, 230)); d = ImageDraw.Draw(im)
        boden = 640
        def hy(km): return boden - km * 10.5
        d.rectangle([0, hy(50), 1010, hy(12)], fill=(30, 40, 90))
        d.rectangle([0, hy(12), 1010, boden], fill=(110, 165, 220))
        d.rectangle([0, boden, W, H], fill=(70, 110, 60))
        for x in range(0, 1010, 160): d.polygon([(x, boden), (x + 80, boden - 40), (x + 160, boden)], fill=(60, 95, 55))
        for km in (0, 10, 20, 30, 40, 50):
            d.line([0, hy(km), 25, hy(km)], fill=(255, 255, 255), width=2); d.text((32, hy(km)), '%d km' % km, font=F(18, False), fill=(240, 245, 255), anchor='lm')
        wolke(d, 300, hy(3), 1.0); wolke(d, 620, hy(5), 0.8)
        d.text((800, hy(6)), 'Troposphäre: Wetter', font=F(26), fill=DUNKEL, anchor='mm')
        y = hy(10)
        d.line([[(x, y + 6 * math.sin(x / 70)) for x in range(100, 1000, 10)]][0], fill=(255, 230, 120), width=5)
        d.text((560, y - 22), 'Jetstream (ca. 10 km)', font=F(20), fill=(255, 230, 120), anchor='mm')
        y2 = hy(30)
        for i in range(6):
            x = 140 + i * 145; pfeil(d, x, y2, x + 100, y2, (120, 200, 255), w=6)
        d.text((560, y2 - 34), 'Polarwirbel (ca. 30 km, −70 °C)', font=F(24), fill=(150, 215, 255), anchor='mm')
        d.text((800, hy(44)), 'Stratosphäre', font=F(26), fill=(220, 230, 255), anchor='mm')
        return im
    if name == 'erwaermung':
        im = verlauf(W, H, (8, 14, 32), (22, 34, 66)); d = ImageDraw.Draw(im)
        cx, cy, r = 470, 380, 270
        polkarte(d, cx, cy, r)
        p_ = min(1, t / 60)   # Kapitel dauert gut eine Minute
        st = max(0.15, 1 - p_ * 1.1)
        if p_ < 0.6:
            wirbel(d, cx + 60 * p_, cy, 160 * (1 - p_ * 0.4), 150 * (1 - p_ * 0.5), t, st)
        else:
            wirbel(d, cx - 90, cy + 50, 70, 60, t, 0.35, col=(170, 210, 240)); wirbel(d, cx + 100, cy - 60, 70, 60, -t, 0.35, col=(170, 210, 240))
        # warme Blase
        for k in range(8, 0, -1):
            f = k / 8; rr = 30 + 160 * p_ * f
            im2 = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d2 = ImageDraw.Draw(im2)
            d2.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(240, 120, 60, int(28 * p_)))
            im.paste(im2, (0, 0), im2); d = ImageDraw.Draw(im)
        # Thermometer
        tx = 960; d.rounded_rectangle([tx, 150, tx + 40, 560], radius=20, fill=(230, 235, 245))
        temp = -70 + 50 * min(1, p_ * 1.6)
        hoehe = 400 * (temp + 80) / 100
        d.rounded_rectangle([tx + 8, 552 - hoehe, tx + 32, 552], radius=12, fill=ROT)
        d.ellipse([tx - 12, 540, tx + 52, 604], fill=ROT)
        d.text((tx + 70, 552 - hoehe), '%d °C' % round(temp), font=F(30), fill=(255, 255, 255), anchor='lm')
        d.text((tx + 20, 120), 'in 30 km Höhe', font=F(20, False), fill=(200, 215, 235), anchor='mm')
        return im
    if name == 'jet':
        im = verlauf(W, H, (110, 160, 210), (180, 210, 235)); d = ImageDraw.Draw(im)
        box = (0, 60, 1040, 700)
        T.weltkarte(d, box)
        amp = 20 + 90 * min(1, t / 15)
        pts = [(x, 250 + amp * math.sin(x / 130 + t * 0.4)) for x in range(0, 1041, 8)]
        for x, y in pts[::14]:
            if math.sin(x / 130 + t * 0.4) > 0.5:
                d.ellipse([x - 40, y - 10, x + 40, y + 60], fill=(70, 130, 230))
        d.line(pts, fill=(255, 220, 90), width=7)
        d.text((520, 685), 'Jetstream (gelb) schlägt große Bögen – Kaltluft (blau) bricht nach Süden aus', font=F(19, False), fill=DUNKEL, anchor='mm')
        return im
    if name == 'zeitleiste_pw':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        y = 330; d.line([60, y, 1000, y], fill=(200, 215, 235), width=4)
        ev = [(1952, 'Entdeckung', 'Berlin'), (1968, 'früher Rekord', '28.11.'), (2018, 'Beast from', 'the East'), (2021, 'Schnee', 'Nord/Mitte'), (2025, 'Rekord', '28.11.'), (2026, 'Ostwind', '~11.11.')]
        sicht = 1 + int(t / 6)
        for i, (j, a, b) in enumerate(ev):
            x = 110 + i * 168
            on = i < sicht
            c = GELB if on else (90, 100, 120)
            d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=c)
            oben = i % 2 == 0
            yy = y - 90 if oben else y + 90
            d.line([x, y, x, yy + (30 if oben else -30)], fill=c, width=2)
            if on:
                d.text((x, yy - 14), str(j), font=F(28), fill=(255, 255, 255), anchor='mm')
                d.text((x, yy + 16), a + ' ' + b, font=F(17, False), fill=(210, 220, 235), anchor='mm')
        return im
    if name == 'balken_wind':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        base = 470; skala = 9
        d.line([80, base, 1000, base], fill=(220, 225, 235), width=2)
        werte = [('normal Mitte Nov.', 26.5, BLAU), ('2026 zeitweise', 0.3, GELB), ('Ostwind ~11.11.', -2, (120, 200, 255)), ('großer Zusammenbruch', -22, ROT)]
        sicht = 1 + int(t / 10)
        for i, (lab, v, c) in enumerate(werte):
            if i >= sicht: continue
            x = 150 + i * 220; h_ = v * skala * min(1, (t - i * 10) / 1.5 if i else min(1, t / 1.5))
            d.rectangle([x, min(base, base - h_), x + 120, max(base, base - h_)], fill=c)
            d.text((x + 60, base - h_ - 22 if v >= 0 else base - h_ + 24), ('%+.1f m/s' % v).replace('.', ','), font=F(24), fill=(255, 255, 255), anchor='mm')
            d.text((x + 60, base + 30 if v >= 0 else base - 26), lab, font=F(17, False), fill=(210, 220, 235), anchor='mm')
        d.text((540, 95), 'Zonaler Wind bei 60° N in 10 hPa (ca. 30 km)', font=F(22), fill=(255, 255, 255), anchor='mm')
        d.text((540, 125), 'positiv = Westwind (Wirbel intakt) · negativ = Ostwind (Wirbel zusammengebrochen)', font=F(17, False), fill=(200, 215, 235), anchor='mm')
        return im
    if name == 'szenarien':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        tit = [('1  Kälte woanders', (90, 170, 110), 'wechselhaft, mal mild'), ('2  Wintergruß', (120, 170, 230), 'ein paar Frosttage'), ('3  Kälteeinbruch', (90, 120, 230), 'Ostwind, Dauerfrost')]
        aktiv = min(2, int(max(0, t - 5) / 12))
        for i, (a, c, b) in enumerate(tit):
            x = 40 + i * 330; on = i <= aktiv
            d.rounded_rectangle([x, 120, x + 300, 420], radius=20, fill=(25, 40, 70), outline=c if on else (70, 80, 100), width=4)
            d.text((x + 150, 160), a, font=F(26), fill=(255, 255, 255) if on else (130, 140, 160), anchor='mm')
            d.text((x + 150, 390), b, font=F(19, False), fill=(210, 220, 235) if on else (110, 120, 140), anchor='mm')
            # Mini-Thermometer
            lv_ = (0.6, 0.35, 0.1)[i]
            d.rounded_rectangle([x + 135, 200, x + 165, 350], radius=14, fill=(230, 235, 245))
            d.rounded_rectangle([x + 141, 350 - 140 * lv_, x + 159, 350], radius=8, fill=c)
        # Gelände Mümlingtal
        gy = 600
        pts = [(0, H), (0, 500), (180, 480), (330, 560), (470, gy), (640, gy), (780, 540), (930, 470), (1040, 450), (1040, H)]
        d.polygon(pts, fill=(70, 110, 60))
        d.polygon([(400, 585), (470, gy - 4), (640, gy - 4), (720, 575), (640, 588), (470, 588)], fill=(120, 170, 230))
        d.text((555, gy + 30), 'Kaltluftsee Mümlingtal · Bad König ~185 m', font=F(17), fill=(255, 255, 255), anchor='mm')
        d.text((180, 465), 'Vielbrunn 453 m', font=F(17), fill=(255, 255, 255), anchor='mm')
        d.text((930, 455), 'Höhenlagen', font=F(17), fill=(255, 255, 255), anchor='mm')
        return im
    if name == 'klima':
        im = verlauf(W, H, (15, 25, 45), (60, 30, 30)); d = ImageDraw.Draw(im)
        cx, cy, r = 330, 380, 230
        polkarte(d, cx, cy, r)
        rr = 60 + 30 * math.sin(t)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=ROT, width=6)
        d.text((cx, cy + r + 30), 'Arktis erwärmt sich schneller', font=F(22), fill=(255, 255, 255), anchor='mm')
        base = 560
        for i, (lab, v, c) in enumerate((('Wärmerekorde', 3, ROT), ('Kälterekorde', 1, BLAU))):
            x = 720 + i * 170; h_ = v * 110 * min(1, max(0, t - 20) / 2)
            d.rectangle([x, base - h_, x + 110, base], fill=c)
            d.text((x + 55, base + 26), lab, font=F(19, False), fill=(230, 235, 245), anchor='mm')
            if h_: d.text((x + 55, base - h_ - 22), '%d×' % v, font=F(28), fill=(255, 255, 255), anchor='mm')
        return im
    if name == 'glossar':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        eintr = [('Major Warming', 'Zusammenbruch, Ostwind in ca. 30 km'), ('Minor Warming', 'kleinere Störung, keine Winddrehung'),
                 ('Final Warming', 'normales Ende des Wirbels im Frühjahr'), ('Split', 'Wirbel in zwei Teile zerrissen'),
                 ('Displacement', 'Wirbel vom Pol weggeschoben'), ('NAO', 'Azorenhoch gegen Islandtief'), ('QBO', 'Windwechsel über dem Äquator')]
        for i, (a, b) in enumerate(eintr):
            y = 100 + i * 66
            d.rounded_rectangle([60, y, 1000, y + 54], radius=12, fill=(25, 40, 70))
            d.text((85, y + 27), a, font=F(24), fill=GELB, anchor='lm')
            d.text((370, y + 27), b, font=F(22, False), fill=(230, 235, 245), anchor='lm')
        return im
    return _alt(name, t, p)


def karte_klein(kopf, text):
    """Kleinere Infokarte (verdeckt weniger von den Grafiken)."""
    f1, f2 = F(15), F(19); bw = 380
    dr0 = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    z, cur = [], ''
    for w_ in text.split():
        if dr0.textlength((cur + ' ' + w_).strip(), font=f2) > bw - 50: z.append(cur); cur = w_
        else: cur = (cur + ' ' + w_).strip()
    z.append(cur); h = 42 + len(z) * 25 + 10
    im = Image.new('RGBA', (bw, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw, h], radius=14, fill=(255, 255, 255, 238)); d.rounded_rectangle([0, 0, 6, h], radius=3, fill=ROT + (255,))
    d.text((18, 12), kopf.upper(), font=f1, fill=ROT)
    for i, s_ in enumerate(z): d.text((18, 36 + i * 25), s_, font=f2, fill=DUNKEL)
    return im


_alt = T.szene_bild
T.szene_bild = szene_pw
T.karte_bild = karte_klein

if __name__ == '__main__':
    T.main()
