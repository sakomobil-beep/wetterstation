#!/usr/bin/env python3
"""Themenvideo „Max erklärt: Vulkane und das Wetter“ (Querformat 1280×720, ca. 10 Minuten).
Gleiche Aufmachung wie El Niño / Polarwirbel, eigene Grafiken, Inhalte von wetter-badkoenig.de/vulkane.html.
Ausgabe: fb/thema-vulkan.mp4 + fb/thema-vulkan.json (kein Autopost – Kingman postet selbst)."""
import os, sys, math
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import themen_video as T
import polarwirbel_video as PW          # kleine Infokarten + gemeinsame Szenen (schichten usw.)
from themen_video import W, H, F, verlauf, pfeil, wolke, GELB, ROT, BLAU, DUNKEL

T.STAND = 'Stand: November 2026'
T.ZIEL = 'thema-vulkan'
T.TITEL = 'Max erklärt: Wenn ein Vulkan der Welt den Sommer nimmt'
T.KARTE_TITEL = ('Vulkane und das Wetter', 'Max erklärt · Wenn ein Vulkan der Welt den Sommer nimmt')
T.LINK = 'wetter-badkoenig.de/vulkane.html'
T.INTRO = ('Wie kann ein einziger Vulkan das Wetter auf der ganzen Erde verändern? Warum war 1816 das „Jahr ohne Sommer“, was hat das '
           'mit dem Fahrrad zu tun, warum war Tonga 2022 ein Sonderfall – und was würden wir im Odenwald davon merken?')
T.TAGS = '#Vulkane #Klima #Wetter #Odenwald #MaxErklärt'
T.QUELLEN = 'Quellen: SRF Meteo · wetter.de · wetter.tv · Spektrum · Der Standard / Uni Graz · wetter-badkoenig.de/vulkane.html'
T.STATISCH = ('odenwald', 'v_tabelle', 'v_glossar')

T.KAPITEL = [
    dict(titel='Vulkane und das Wetter', szene='v_ausbruch', teile=[
        ('Hallo und herzlich willkommen zu einer neuen Folge von „Max erklärt“. Heute geht es um eine der gewaltigsten Kräfte der Natur: Vulkane.', None),
        ('Die meisten Ausbrüche wirken nur in ihrer Umgebung. Aber ein sehr großer Ausbruch kann für ein bis drei Jahre das Wetter auf der ganzen Erde verändern.', ('Große Ausbrüche', 'wirken 1 bis 3 Jahre weltweit')),
        ('1816 zum Beispiel gab es in Europa ein „Jahr ohne Sommer“, mit Schnee im Juli, Missernten und Hunger. Schuld war ein Vulkan auf der anderen Seite der Erde.', ('1816', 'das „Jahr ohne Sommer“')),
        ('In diesem Video klären wir, wie ein Vulkan das Wetter verändert, wann ein Ausbruch weltweit zählt, welche Ausbrüche Geschichte geschrieben haben, warum Tonga 2022 ein Sonderfall war und was wir hier im Odenwald davon merken würden.', None),
    ]),
    dict(titel='1. Wie ein Vulkan das Wetter verändert', szene='v_schleier', teile=[
        ('Ein Vulkan wirft vor allem drei Dinge aus: Asche, Wasserdampf und Gase, darunter viel Schwefeldioxid.', ('Ausstoß', 'Asche, Wasserdampf, Schwefeldioxid')),
        ('Die Asche sieht spektakulär aus, ist aber schwer. Sie fällt nach Stunden bis Tagen wieder herunter und verdunkelt nur die Gegend rund um den Vulkan.', ('Asche', 'fällt in Stunden bis Tagen aus')),
        ('Viel wichtiger ist der Schwefel. Gelangt das Schwefeldioxid hoch genug, in die Stratosphäre ab etwa fünfzehn Kilometern, dann reagiert es mit Wasserdampf zu winzigen Tröpfchen aus Schwefelsäure.', ('Schwefel', 'ab ca. 15 km Höhe entscheidend')),
        ('Diese Tröpfchen nennt man Sulfat-Aerosole. Sie verteilen sich rund um den Globus wie ein feiner Schleier und werfen einen Teil des Sonnenlichts zurück ins All.', ('Sulfat-Aerosole', 'Schleier wirft Sonnenlicht zurück')),
        ('Die Folge: Am Boden wird es kühler. Oben in der Stratosphäre wird es dagegen wärmer, weil die Tröpfchen dort Wärme aufnehmen.', ('Wirkung', 'unten kühler, oben wärmer')),
        ('Was dagegen unterhalb der Stratosphäre bleibt, regnet in Tagen bis Wochen wieder aus und hat für das Weltklima kaum Bedeutung.', None),
    ]),
    dict(titel='1. Wie ein Vulkan das Wetter verändert', szene='v_kurve', teile=[
        ('So sieht der typische Verlauf nach einem großen Ausbruch aus.', None),
        ('Die Abkühlung baut sich langsam auf, weil sich der Schleier erst um die Erde verteilen muss. Ihren Tiefpunkt erreicht sie nach etwa einem Jahr.', ('Tiefpunkt', 'nach etwa einem Jahr')),
        ('Danach sinken die Tröpfchen langsam ab und werden ausgewaschen. Nach zwei bis drei Jahren ist der Schleier verschwunden, und die Temperatur ist wieder auf dem alten Stand.', ('Ende', 'nach 2 bis 3 Jahren')),
    ]),
    dict(titel='2. Wann ein Ausbruch weltweit zählt', szene='v_bedingungen', teile=[
        ('Nicht jeder spektakuläre Ausbruch ist auch fürs Klima wichtig. Es müssen mehrere Dinge zusammenkommen.', None),
        ('Erstens: Er muss explosiv genug sein. Die Eruptionssäule muss die Grenze zur Stratosphäre durchbrechen. Ruhig fließende Lava, wie bei vielen Ausbrüchen auf Island, schafft das meist nicht.', ('1. Explosiv genug', 'bis in die Stratosphäre')),
        ('Zweitens: viel Schwefel. Gemessen wird in Millionen Tonnen Schwefeldioxid. Beim Pinatubo 1991 waren es rund siebzehn, beim Tambora 1815 nach Schätzungen sechzig bis achtzig. Viel Asche allein reicht nicht.', ('2. Viel Schwefel', 'Pinatubo ~17 · Tambora 60–80 Mio. t')),
        ('Drittens: nah am Äquator. Von den Tropen aus verteilen die Höhenwinde den Schleier über beide Erdhalbkugeln. Ein Ausbruch weit im Norden wirkt eher nur auf der Nordhalbkugel.', ('3. Nah am Äquator', 'Schleier verteilt sich weltweit')),
        ('Und viertens: Die Wirkung ist immer nur vorübergehend. Nach ein bis drei Jahren ist sie vorbei. Den langfristigen Klimawandel kann ein Vulkan deshalb nicht aufhalten.', ('4. Nur vorübergehend', '1 bis 3 Jahre')),
        ('Übrigens: Die Stärke eines Ausbruchs misst man mit dem Vulkanexplosivitätsindex, kurz VEI, von null bis acht. Jede Stufe steht für etwa zehnmal mehr ausgeworfenes Material. Pinatubo hatte Stufe sechs, Tambora Stufe sieben.', ('VEI', 'Pinatubo 6 · Tambora 7')),
    ]),
    dict(titel='2. Wann ein Ausbruch weltweit zählt', szene='v_europa', teile=[
        ('Wichtig ist auch: Kühler heißt nicht überall kühler. Im weltweiten Mittel sinkt die Temperatur, regional kann es ganz anders aussehen.', ('Regional', 'nicht überall kühler')),
        ('Nach großen tropischen Ausbrüchen wurden in Nord- und Mitteleuropa oft sogar mildere Winter beobachtet. Der Grund: Die Westwinde verstärken sich und bringen milde Atlantikluft.', ('Winter danach', 'in Europa oft milder')),
        ('Der Zusammenhang läuft über die Stratosphäre: Der Schwefelschleier wärmt sie auf, und dadurch ist der Polarwirbel im Winter danach oft stärker. Zum Polarwirbel gibt es übrigens ein eigenes Video.', ('Polarwirbel', 'im Winter danach oft stärker')),
        ('Der Sommer danach ist dagegen häufig kühl und nass. Und auch die Monsunregen in Afrika und Asien können schwächer ausfallen.', ('Sommer danach', 'oft kühl und nass')),
    ]),
    dict(titel='3. Ausbrüche, die Geschichte schrieben', szene='v_zeitleiste', teile=[
        ('Schauen wir uns die bekanntesten Ausbrüche an.', None),
        ('1783 und 84: der Laki auf Island. Acht Monate lang trat Lava aus einer langen Spalte, dabei wurden rund hundertzwanzig Millionen Tonnen Schwefeldioxid frei.', ('1783/84 Laki, Island', 'ca. 120 Mio. t Schwefeldioxid')),
        ('Über Europa lag monatelang ein „trockener Nebel“. Aus Mannheim wurde im Juli 1783 ein seltsamer Nebel bei roter Sonne gemeldet. Auf Island kam es zu einer Hungersnot.', ('Trockener Nebel', 'Mannheim, Juli 1783')),
        ('Im Januar 1784 folgte klirrende Kälte am Rhein, danach Tauwetter mit Rekordhochwasser an Rhein und Main, also ganz in unserer Nähe.', ('Januar 1784', 'Kälte, dann Rekordhochwasser am Main')),
        ('1815: der Tambora in Indonesien, der stärkste Ausbruch der letzten fünfhundert Jahre. Darauf kommen wir gleich noch genauer.', ('1815 Tambora', 'stärkster Ausbruch seit 500 Jahren')),
        ('1883: Krakatau, ebenfalls Indonesien. Weltweit gab es danach leuchtend rote Sonnenuntergänge und eine messbare Abkühlung.', ('1883 Krakatau', 'rote Sonnenuntergänge weltweit')),
        ('1991: der Pinatubo auf den Philippinen, mit rund siebzehn Millionen Tonnen Schwefeldioxid. Das ist die bisher letzte deutlich messbare Abkühlung: etwa ein halbes Grad weltweit, für ein bis zwei Jahre.', ('1991 Pinatubo', 'ca. −0,5 °C weltweit')),
        ('Und 2010: der Eyjafjallajökull auf Island. Er legte wochenlang den Luftverkehr in Europa lahm, hatte aber kaum Wirkung aufs Klima, weil der Schwefel nicht hoch genug kam.', ('2010 Eyjafjallajökull', 'Flugchaos, aber kaum Klimawirkung')),
    ]),
    dict(titel='4. 1816 – das Jahr ohne Sommer', szene='v_1816', teile=[
        ('Zurück zum Tambora. Im April 1815 explodierte er in Indonesien und schleuderte riesige Mengen Schwefel in die Stratosphäre.', None),
        ('Im Jahr darauf, 1816, kam der Sommer in Europa und Nordamerika einfach nicht. Es gab Dauerregen, Nachtfrost und Schnee bis in mittlere Lagen.', ('1816', 'Dauerregen, Nachtfrost, Sommerschnee')),
        ('Die Ernten verfaulten auf den Feldern. Es kam zu Missernten, Teuerung und Hunger. Auch Baden rund um Karlsruhe, also gar nicht weit von uns, war stark betroffen.', ('Folgen', 'Missernten und Hunger, auch in Baden')),
        ('Und jetzt wird es spannend: Weil Hafer so teuer wurde, dass sich viele kein Pferd mehr leisten konnten, suchte der Mannheimer Karl Drais nach einem Ersatz. 1817 erfand er das Laufrad, den Vorläufer des Fahrrads.', ('1817', 'Karl Drais erfindet das Laufrad')),
        ('Auch Mary Shelleys „Frankenstein“ entstand in diesem verregneten Sommer am Genfer See. Und die glutroten Sonnenuntergänge inspirierten Maler wie William Turner und Caspar David Friedrich.', ('Kultur', 'Frankenstein, Turner, C. D. Friedrich')),
    ]),
    dict(titel='5. Sonderfall Tonga 2022', szene='v_tonga', teile=[
        ('Ein ganz besonderer Fall war der Ausbruch des Unterseevulkans Hunga Tonga im Südpazifik am 15. Januar 2022, der stärkste Ausbruch des 21. Jahrhunderts.', ('15. Januar 2022', 'Hunga Tonga, Südpazifik')),
        ('Die Wolke stieg bis etwa siebenundfünfzig Kilometer hoch. Die Druckwelle lief mehrmals um die ganze Erde und war auch an Wetterstationen in Deutschland als Sprung im Luftdruck zu sehen.', ('Druckwelle', 'auch in Deutschland gemessen')),
        ('Trotzdem gelangten nur rund 0,4 Millionen Tonnen Schwefeldioxid in die Stratosphäre, viel zu wenig für eine Abkühlung wie beim Pinatubo.', ('Schwefel', 'nur ca. 0,4 Mio. t')),
        ('Dafür schleuderte der Vulkan etwa hundertsechsundvierzig Millionen Tonnen Wasserdampf nach oben, weil er unter Wasser lag. Wasserdampf ist ein Treibhausgas, deshalb wurde zuerst eine Erwärmung befürchtet.', ('Wasserdampf', 'ca. 146 Mio. t')),
        ('Neuere Auswertungen zeigen aber: Die Stratosphäre kühlte bis Mitte 2023 um bis zu vier Grad ab, und unterm Strich trug der Ausbruch sogar leicht zur Abkühlung bei. Am Boden war die Wirkung insgesamt gering.', ('Ergebnis', 'Stratosphäre bis −4 °C, am Boden gering')),
    ]),
    dict(titel='6. Was heißt das für den Odenwald?', szene='v_odenwald', teile=[
        ('Und was würden wir hier im Odenwald davon merken? Auch hier habe ich drei Möglichkeiten mitgebracht.', None),
        ('Meistens: kaum etwas. Ausbrüche auf Island, am Ätna oder in Indonesien gibt es jedes Jahr. Fast alle sind zu klein oder zu niedrig. Manchmal sind höchstens die Sonnenuntergänge etwas farbiger.', ('Meistens', 'kaum etwas zu spüren')),
        ('Möglich: ein kühler, nasser Sommer nach einem großen Ausbruch in den Tropen, ähnlich wie 1816, aber meist deutlich schwächer. Der Winter danach kann sogar milder sein.', ('Möglich', 'kühler, nasser Sommer')),
        ('Selten: Schwefelnebel aus Island. Ein langer Spaltenausbruch wie der Laki könnte Schwefeldunst bis nach Mitteleuropa tragen, mit trüber Sonne und schlechter Luft. Das kommt nur alle paar hundert Jahre vor.', ('Selten', 'Schwefeldunst aus Island')),
        ('Und unsere Wetterstation in Bad König würde das sogar messen: Ein Schwefelschleier senkt die Sonneneinstrahlung, das sähe man an klaren Tagen bei Solarstrahlung und UV.', ('Station', 'weniger Sonnenstrahlung messbar')),
        ('Eine Druckwelle wie bei Tonga wäre als kurzer Sprung im Luftdruck zu sehen. Und eine Abkühlung um ein halbes Grad fällt im Alltag kaum auf, zeigt sich aber im Vergleich der Monatsmittel.', ('Station', 'Druckwelle und Monatsmittel')),
    ]),
    dict(titel='7. Kommt wieder ein Jahr ohne Sommer?', szene='v_haeufigkeit', teile=[
        ('Bleibt die große Frage: Könnte heute wieder ein „Jahr ohne Sommer“ kommen? Die ehrliche Antwort: Ja, ausgeschlossen ist das nicht.', None),
        ('Ausbrüche in der Größe des Tambora kommen statistisch etwa ein- bis zweimal pro Jahrtausend vor, solche wie der Pinatubo einige Male pro Jahrhundert.', ('Häufigkeit', 'Tambora 1–2× pro Jahrtausend')),
        ('Vorhersagen lassen sie sich nur kurzfristig, wenn ein Vulkan unruhig wird. Heute wären die Folgen für die Ernährung aber besser abzufedern als 1816, weil Lebensmittel weltweit gehandelt werden.', ('Heute', 'Welthandel federt ab')),
        ('Und den menschengemachten Klimawandel würde auch ein großer Ausbruch nur für ein bis drei Jahre bremsen. Danach geht die Erwärmung im gleichen Tempo weiter.', ('Klimawandel', 'nur kurz gebremst')),
    ]),
    dict(titel='8. Kleines Vulkan-Lexikon', szene='v_glossar', teile=[
        ('Zum Schluss die wichtigsten Begriffe. Stratosphäre: die Luftschicht über dem Wetter. Tropopause: die Grenze dorthin, bei uns in zehn bis zwölf, in den Tropen in etwa siebzehn Kilometern Höhe.', None),
        ('Schwefeldioxid und Sulfat-Aerosole: das Gas und die Tröpfchen, die den kühlenden Schleier bilden. VEI: die Stärkeskala der Ausbrüche.', None),
        ('Spaltenausbruch: Lava tritt ruhig aus einer langen Erdspalte aus, wie oft auf Island. Und die Eruptionssäule ist die Wolke aus Asche und Gas über dem Vulkan.', None),
    ]),
    dict(titel='Fazit', szene='odenwald', teile=[
        ('Fassen wir zusammen. Für das Weltwetter ist nicht die Asche entscheidend, sondern der Schwefel, und der muss hoch hinaus, in die Stratosphäre.', None),
        ('Dann kann ein einziger Ausbruch die Erde für ein bis drei Jahre abkühlen, wie beim Pinatubo um ein halbes Grad, oder wie 1816 einen ganzen Sommer ausfallen lassen.', None),
        ('Bei uns im Odenwald merken wir von den meisten Ausbrüchen nichts. Aber unsere Station würde es zeigen, wenn wieder ein großer Schleier um die Erde zieht.', None),
        ('Mehr dazu findet ihr auf wetter badkoenig punkt de unter Vulkane.', None),
        ('Wenn euch das Video gefallen hat, lasst gern ein Like da und folgt uns, damit ihr nichts verpasst. Und schreibt in die Kommentare: Hättet ihr gedacht, dass ein Vulkan das Fahrrad erfunden hat? Danke fürs Zuschauen, und bis zum nächsten Mal bei „Max erklärt“!', None),
    ]),
]


# ---------------------------------------------------------------- eigene Grafiken
def vulkan(d, cx, boden, b, h, t, glut=1.0, saeule=1.0, hoch=200):
    d.polygon([(cx - b, boden), (cx - b * 0.18, boden - h), (cx + b * 0.18, boden - h), (cx + b, boden)], fill=(95, 75, 65))
    d.polygon([(cx - b * 0.18, boden - h), (cx - b * 0.08, boden - h + 25), (cx + b * 0.1, boden - h + 18), (cx + b * 0.18, boden - h)], fill=(220, 90, 40))
    if saeule:
        for k in range(10):
            y = boden - h - k * hoch / 10 * saeule
            r = 18 + k * 7 + 4 * math.sin(t * 2 + k)
            g = int(110 - k * 4)
            d.ellipse([cx - r + 6 * math.sin(t + k), y - r, cx + r + 6 * math.sin(t + k), y + r], fill=(g, g - 5, g - 10))
        for k in range(int(6 * glut)):
            a = t * 3 + k
            d.ellipse([cx - 4 + 30 * math.sin(a), boden - h - 20 - (t * 60 + k * 23) % 80, cx + 4 + 30 * math.sin(a), boden - h - 12 - (t * 60 + k * 23) % 80], fill=(255, 150, 50))


def szene_v(name, t, p):
    if name == 'v_ausbruch':
        im = verlauf(W, H, (40, 30, 40), (150, 90, 70)); d = ImageDraw.Draw(im)
        d.rectangle([0, 600, W, H], fill=(60, 50, 45))
        vulkan(d, 500, 600, 330, 260, t, saeule=min(1, 0.3 + t / 10), hoch=300)
        return im
    if name == 'v_schleier':
        im = verlauf(W, H, (6, 10, 30), (130, 180, 230)); d = ImageDraw.Draw(im)
        boden = 640
        def hy(km): return boden - km * 10.5
        d.rectangle([0, hy(50), 1010, hy(15)], fill=(30, 40, 90)); d.rectangle([0, hy(15), 1010, boden], fill=(110, 165, 220))
        d.line([0, hy(15), 1010, hy(15)], fill=(255, 255, 255), width=1)
        d.text((20, hy(15) - 14), 'Grenze zur Stratosphäre (ca. 15 km)', font=F(17, False), fill=(240, 245, 255))
        d.rectangle([0, boden, W, H], fill=(70, 110, 60))
        for km in (0, 10, 20, 30, 40): d.text((960, hy(km)), '%d km' % km, font=F(16, False), fill=(240, 245, 255), anchor='lm')
        vulkan(d, 230, boden, 170, 90, t, saeule=1, hoch=min(330, 60 + t * 25))
        sp = min(1, max(0, (t - 8) / 20))
        for i in range(int(90 * sp)):
            x = (230 + (i * 37) % 760) ; y = hy(22) + (i * 13) % 50 + 4 * math.sin(t + i)
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(250, 230, 150))
        if sp > 0.3:
            d.text((600, hy(30)), 'Schwefelschleier (Sulfat-Aerosole)', font=F(22), fill=(250, 230, 150), anchor='mm')
            for k in range(4):
                x = 420 + k * 140; yy = hy(48) + (t * 80 + k * 30) % 70
                pfeil(d, x, yy, x + 20, yy + 30, GELB, w=4)
                if yy > hy(44): pfeil(d, x + 40, hy(25), x + 70, hy(42), (255, 220, 120), w=3)
        sonne_x, sonne_y = 900, hy(46)
        d.ellipse([sonne_x - 26, sonne_y - 26, sonne_x + 26, sonne_y + 26], fill=GELB)
        d.text((520, boden - 30), 'Asche fällt nach Stunden bis Tagen aus', font=F(18, False), fill=DUNKEL, anchor='mm')
        return im
    if name == 'v_kurve':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        x0, x1, y0 = 110, 960, 260
        d.line([x0, y0, x1, y0], fill=(200, 215, 235), width=2)
        d.text((x0 - 10, y0), '±0', font=F(18), fill=(220, 230, 240), anchor='rm')
        d.text((x0 - 10, y0 + 250), '−0,5 °C', font=F(18), fill=(220, 230, 240), anchor='rm')
        for j in range(5):
            x = x0 + j * (x1 - x0) / 4; d.text((x, y0 - 22), 'Jahr %d' % j, font=F(17, False), fill=(200, 215, 235), anchor='mm')
        n = int(min(1, t / 14) * 200)
        pts = []
        for i in range(n):
            j = i / 200 * 4
            v = 0 if j < 0.15 else -0.5 * math.sin(min(1, (j - 0.15) / 2.6) * math.pi) ** 1.2
            pts.append((x0 + i / 200 * (x1 - x0), y0 - v * 500))
        if len(pts) > 1: d.line(pts, fill=(120, 190, 255), width=6)
        d.text((x0 + 22, y0 + 18), '▲ Ausbruch', font=F(17), fill=ROT)
        d.text((535, 620), 'Typischer Verlauf der weltweiten Temperatur nach einem großen Ausbruch (schematisch)', font=F(18, False), fill=(200, 215, 235), anchor='mm')
        return im
    if name == 'v_bedingungen':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        tit = [('1', 'explosiv genug'), ('2', 'viel Schwefel'), ('3', 'nah am Äquator'), ('4', 'nur vorübergehend')]
        aktiv = int(max(0, t - 4) / 11)
        for i, (n_, a) in enumerate(tit):
            x = 40 + (i % 2) * 490; y = 90 + (i // 2) * 170; on = i <= aktiv
            d.rounded_rectangle([x, y, x + 460, y + 145], radius=18, fill=(25, 40, 70), outline=GELB if on else (70, 80, 100), width=4)
            d.ellipse([x + 20, y + 40, x + 85, y + 105], fill=GELB if on else (70, 80, 100))
            d.text((x + 52, y + 72), n_, font=F(34), fill=DUNKEL, anchor='mm')
            d.text((x + 110, y + 72), a, font=F(30), fill=(255, 255, 255) if on else (130, 140, 160), anchor='lm')
        return im
    if name == 'v_europa':
        im = verlauf(W, H, (110, 160, 210), (180, 210, 235)); d = ImageDraw.Draw(im)
        T.weltkarte(d, (0, 60, 1040, 700))
        for k in range(5):
            x = (t * 80 + k * 210) % 1040; y = 230 + 15 * math.sin(x / 60)
            pfeil(d, x, y, x + 70, y, (255, 255, 255), w=6)
        d.text((520, 685), 'Nach großen tropischen Ausbrüchen: kräftigere Westwinde – Winter in Europa oft milder', font=F(19, False), fill=DUNKEL, anchor='mm')
        return im
    if name == 'v_zeitleiste':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        y = 330; d.line([60, y, 1000, y], fill=(200, 215, 235), width=4)
        ev = [('1783', 'Laki'), ('1815', 'Tambora'), ('1883', 'Krakatau'), ('1991', 'Pinatubo'), ('2010', 'Eyjafjallajökull'), ('2022', 'Hunga Tonga')]
        sicht = 1 + int(max(0, t - 4) / 11)
        for i, (j, a) in enumerate(ev):
            x = 110 + i * 168; on = i < sicht
            c = (240, 120, 60) if on else (90, 100, 120)
            d.polygon([(x - 18, y + 12), (x, y - 16), (x + 18, y + 12)], fill=c)
            oben = i % 2 == 0; yy = y - 90 if oben else y + 90
            d.line([x, y, x, yy + (30 if oben else -30)], fill=c, width=2)
            if on:
                d.text((x, yy - 14), j, font=F(28), fill=(255, 255, 255), anchor='mm')
                d.text((x, yy + 16), a, font=F(17, False), fill=(210, 220, 235), anchor='mm')
        return im
    if name == 'v_1816':
        im = verlauf(W, H, (90, 100, 115), (150, 160, 170)); d = ImageDraw.Draw(im);
        d.rectangle([0, 520, W, H], fill=(95, 110, 80))
        for k in range(5): wolke(d, 80 + k * 200, 120 + 20 * (k % 2), 1.2, (110, 115, 125))
        for i in range(140):
            x = (i * 53) % 1010; y = (i * 97 + t * 260) % 420 + 150
            if i % 3: d.line([x, y, x - 4, y + 18], fill=(200, 210, 225), width=2)
            else: d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 255, 255))
        # Laufrad
        lx = (t * 50) % 1300 - 200
        if lx < 1000:
            for dx in (0, 150):
                d.ellipse([lx + dx - 45, 470, lx + dx + 45, 560], outline=(60, 40, 30), width=6)
            d.line([lx, 515, lx + 150, 500], fill=(90, 60, 40), width=8); d.line([lx + 140, 500, lx + 150, 440], fill=(60, 40, 30), width=5)
        d.rounded_rectangle([340, 70, 700, 120], radius=12, fill=(15, 25, 45))
        d.text((520, 95), 'Juli 1816: Schnee statt Sommer', font=F(24), fill=(255, 255, 255), anchor='mm')
        return im
    if name == 'v_tonga':
        im = verlauf(W, H, (6, 10, 30), (40, 90, 150)); d = ImageDraw.Draw(im)
        d.rectangle([0, 560, W, H], fill=(25, 80, 140))
        hoch = min(480, t * 40)
        for k in range(12):
            y = 560 - k * hoch / 12; r = 25 + k * 10
            d.ellipse([500 - r, y - r * 0.5, 500 + r, y + r * 0.5], fill=(230, 235, 245) if k % 2 else (200, 210, 225))
        for k in range(3):
            r = ((t * 120) + k * 260) % 900
            d.ellipse([500 - r, 560 - r * 0.25, 500 + r, 560 + r * 0.25], outline=(255, 220, 120), width=3)
        d.text((800, 120), 'bis ca. 57 km hoch', font=F(24), fill=(255, 255, 255), anchor='mm')
        # Balken Schwefel vs. Wasserdampf
        if t > 12:
            for i, (lab, v, c) in enumerate((('Schwefeldioxid', 0.4, GELB), ('Wasserdampf', 146, (120, 200, 255)))):
                y = 600 + i * 45; w_ = 4 + v * 5.5
                d.rectangle([60, y, 60 + w_, y + 30], fill=c)
                d.text((70 + w_, y + 15), '%s: %s Mio. t' % (lab, str(v).replace('.', ',')), font=F(19), fill=(255, 255, 255), anchor='lm')
        return im
    if name == 'v_odenwald':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        tit = [('meistens', 'kaum etwas', (90, 170, 110)), ('möglich', 'kühler, nasser Sommer', (120, 170, 230)), ('selten', 'Schwefeldunst', (200, 160, 70))]
        aktiv = min(2, int(max(0, t - 5) / 12))
        for i, (a, b, c) in enumerate(tit):
            x = 40 + i * 330; on = i <= aktiv
            d.rounded_rectangle([x, 110, x + 300, 300], radius=20, fill=(25, 40, 70), outline=c if on else (70, 80, 100), width=4)
            d.text((x + 150, 170), a.upper(), font=F(28), fill=c if on else (110, 120, 140), anchor='mm')
            d.text((x + 150, 240), b, font=F(21, False), fill=(230, 235, 245) if on else (110, 120, 140), anchor='mm')
        if t > 45:
            d.rounded_rectangle([40, 340, 960, 520], radius=20, fill=(25, 40, 70), outline=GELB, width=3)
            d.text((500, 375), 'Was unsere Station in Bad König zeigen würde', font=F(24), fill=GELB, anchor='mm')
            for i, s in enumerate(('☀  weniger Sonnenstrahlung und UV', '⏲  Druckwelle als Sprung im Luftdruck', '🌡  kühlere Monatsmittel')):
                d.text((90, 420 + i * 34), s.split('  ')[1], font=F(21, False), fill=(230, 235, 245), anchor='lm')
                d.ellipse([60, 412 + i * 34, 76, 428 + i * 34], fill=GELB)
        return im
    if name == 'v_haeufigkeit':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        d.text((520, 110), 'Wie oft? (statistisch)', font=F(30), fill=(255, 255, 255), anchor='mm')
        for i, (lab, n_, c) in enumerate((('wie Pinatubo', 'einige Male pro Jahrhundert', (120, 190, 255)), ('wie Tambora', '1–2× pro Jahrtausend', ROT))):
            y = 220 + i * 170
            d.text((80, y), lab, font=F(28), fill=c, anchor='lm')
            d.text((80, y + 44), n_, font=F(22, False), fill=(220, 230, 240), anchor='lm')
            k = 5 if i == 0 else 1
            for j in range(k):
                x = 520 + j * 85
                d.polygon([(x - 30, y + 40), (x, y - 15), (x + 30, y + 40)], fill=c)
        return im
    if name == 'v_glossar':
        im = verlauf(W, H, (15, 25, 45), (30, 45, 80)); d = ImageDraw.Draw(im)
        eintr = [('Stratosphäre', 'Luftschicht über dem Wetter, ca. 10–50 km'), ('Tropopause', 'Grenze: bei uns 10–12 km, Tropen ~17 km'),
                 ('Schwefeldioxid', 'Gas aus dem Vulkan, wird zum Schleier'), ('Sulfat-Aerosole', 'Tröpfchen, werfen Sonnenlicht zurück'),
                 ('VEI', 'Stärkeskala 0–8, je Stufe 10× mehr'), ('Spaltenausbruch', 'Lava tritt ruhig aus einer Erdspalte'), ('Eruptionssäule', 'Wolke aus Asche und Gas')]
        for i, (a, b) in enumerate(eintr):
            y = 90 + i * 66
            d.rounded_rectangle([60, y, 1000, y + 54], radius=12, fill=(25, 40, 70))
            d.text((85, y + 27), a, font=F(24), fill=GELB, anchor='lm')
            d.text((370, y + 27), b, font=F(22, False), fill=(230, 235, 245), anchor='lm')
        return im
    return _vor(name, t, p)


_vor = T.szene_bild
T.szene_bild = szene_v

if __name__ == '__main__':
    T.main()
