#!/usr/bin/env python3
"""Jahresrückblick-Video „Das Wetterjahr im Odenwald“ (Hochformat, ca. 3–4 Min.) aus dem eigenen Wetterarchiv (data/archiv/tage-JJJJ.json).
Wird am 30.12. erstellt und um 18 Uhr gepostet (fb_senden.py jahr). Ausgabe: fb/jahr.mp4 + fb/jahr.json.
Aufruf: python jahresrueckblick.py [JAHR]   (ohne Jahr: aktuelles Jahr; Daten bis gestern)"""
import os, sys, json, datetime as dt
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wetter_video as WV
from wetter_video import F

ROOT = WV.ROOT; FB = WV.FB
MON = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
MONL = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
# Klimamittel 1991–2020 DWD Michelstadt-Vielbrunn (453 m), Temperatur auf Stationshöhe 184,5 m umgerechnet (+0,65 K je 100 m) – wie im Klima-Tab
KL_TMAX = [2.5, 3.9, 8.3, 13.4, 17.4, 20.8, 22.9, 22.8, 18.0, 12.4, 6.6, 3.3]
KL_TMIN = [-1.9, -1.4, 1.4, 4.7, 8.5, 11.8, 13.8, 13.6, 10.0, 6.0, 2.0, -0.8]
KL_RAIN = [64.7, 58.6, 63.2, 51.7, 84.4, 60.7, 80.6, 70.5, 60.2, 67.8, 66.7, 77.2]
KORR = (453 - 184.5) * 0.0065


def k(v, n=1): return ('%.*f' % (n, v)).replace('.', ',')
def ks(v, n=1): return ('minus ' if v < 0 else '') + k(abs(v), n)   # für die Sprache
def dat(d): return '%d. %s' % (d.day, MONL[d.month - 1])


def daten(jahr):
    A = json.load(open(os.path.join(ROOT, 'data', 'archiv', 'tage-%d.json' % jahr), encoding='utf-8'))
    T = []
    for t in A['tage']:
        m = t.get('metric') or {}
        if m.get('tempHigh') is None: continue
        T.append(dict(d=dt.date.fromisoformat(t['obsTimeLocal'][:10]), hi=m['tempHigh'], lo=m['tempLow'], avg=m.get('tempAvg', (m['tempHigh'] + m['tempLow']) / 2),
                      r=m.get('precipTotal') or 0, g=m.get('windgustHigh') or 0, fremd=bool(t.get('quelle'))))
    return T


def serie(T, f):
    best, cur, ende = 0, 0, None
    for t in T:
        cur = cur + 1 if f(t) else 0
        if cur > best: best, ende = cur, t['d']
    return best, ende


def statistik(T):
    S = dict(n=len(T), mittel=sum(t['avg'] for t in T) / len(T), regen=sum(t['r'] for t in T),
             frost=sum(t['lo'] < 0 for t in T), eis=sum(t['hi'] < 0 for t in T), sommer=sum(t['hi'] >= 25 for t in T), heiss=sum(t['hi'] >= 30 for t in T),
             regentage=sum(t['r'] >= 1 for t in T))
    E = [t for t in T if not t['fremd']] or T   # Rekorde und Höhepunkte nur aus eigenen Messwerten (nicht IBADKN32)
    S['hot'] = max(E, key=lambda t: t['hi']); S['cold'] = min(E, key=lambda t: t['lo'])
    S['wet'] = max(E, key=lambda t: t['r']); S['gust'] = max(E, key=lambda t: t['g'])
    M = {}
    for t in T: M.setdefault(t['d'].month, []).append(t)
    S['mon'] = {m: dict(avg=sum(x['avg'] for x in L) / len(L), regen=sum(x['r'] for x in L), n=len(L)) for m, L in M.items()}
    voll = {m: v for m, v in S['mon'].items() if v['n'] >= 25}
    S['warm_m'] = max(voll, key=lambda m: voll[m]['avg']); S['kalt_m'] = min(voll, key=lambda m: voll[m]['avg'])
    S['nass_m'] = max(voll, key=lambda m: voll[m]['regen']); S['trocken_m'] = min(voll, key=lambda m: voll[m]['regen'])
    S['hitze'] = serie(E, lambda t: t['hi'] >= 30); S['trocken'] = serie(E, lambda t: t['r'] < 0.2); S['frostserie'] = serie(E, lambda t: t['lo'] < 0)
    herbst = [t for t in T if t['d'].month >= 8 and t['lo'] < 0]
    S['erster_frost'] = herbst[0] if herbst else None
    # Vergleich mit dem Klimamittel (nur volle Monate)
    S['kl_diff'] = sum(voll[m]['avg'] - ((KL_TMAX[m - 1] + KL_TMIN[m - 1]) / 2 + KORR) for m in voll) / len(voll)
    S['kl_regen'] = sum(voll[m]['regen'] for m in voll) / sum(KL_RAIN[m - 1] for m in voll) * 100
    S['kl_n'] = len(voll)
    return S


def karte(kopf, farbe, h=330):
    w = 440; im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w, h], radius=28, fill=(255, 255, 255, 240))
    dr.rounded_rectangle([0, 0, w, 74], radius=28, fill=farbe + (255,)); dr.rectangle([0, 46, w, 74], fill=farbe + (255,))
    dr.text((w / 2, 37), kopf, font=F(32), fill=(255, 255, 255), anchor='mm')
    return im, dr


def grafik_temp(T, S, jahr):
    im, dr = karte('TEMPERATUR %d' % jahr, (215, 90, 40), 360)
    x0, x1, y0, y1 = 40, 420, 100, 320
    lo, hi = min(t['lo'] for t in T) - 1, max(t['hi'] for t in T) + 1
    Y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
    X = lambda d: x0 + (d.timetuple().tm_yday - 1) / 365 * (x1 - x0)
    if lo < 0 < hi: dr.line([x0, Y(0), x1, Y(0)], fill=(150, 180, 220), width=2)
    for i in range(12):
        x = x0 + i * (x1 - x0) / 12; dr.text((x + 3, y1 + 8), MON[i][0], font=F(18, False), fill=(110, 120, 135))
    dr.line([(X(t['d']), Y(t['hi'])) for t in T], fill=(230, 110, 60), width=2)
    dr.line([(X(t['d']), Y(t['lo'])) for t in T], fill=(70, 130, 210), width=2)
    for t, c in ((S['hot'], (200, 40, 30)), (S['cold'], (30, 80, 180))):
        v = t['hi'] if t is S['hot'] else t['lo']; dr.ellipse([X(t['d']) - 7, Y(v) - 7, X(t['d']) + 7, Y(v) + 7], fill=c, outline=(255, 255, 255), width=2)
    dr.text((x1, y0 - 6), '%s° max' % k(S['hot']['hi']), font=F(20), fill=(200, 40, 30), anchor='rb')
    return im


def grafik_regen(S, jahr):
    im, dr = karte('REGEN %d (l/m²)' % jahr, (40, 110, 200), 360)
    x0, x1, y0, y1 = 30, 425, 105, 315
    mx = max(max(v['regen'] for v in S['mon'].values()), max(KL_RAIN)) * 1.1
    bw = (x1 - x0) / 12
    for m in range(1, 13):
        x = x0 + (m - 1) * bw
        kl = y1 - KL_RAIN[m - 1] / mx * (y1 - y0)
        if m in S['mon']:
            v = S['mon'][m]['regen']; c = (30, 90, 190) if m == S['nass_m'] else (230, 150, 40) if m == S['trocken_m'] else (110, 160, 220)
            dr.rectangle([x + 4, y1 - v / mx * (y1 - y0), x + bw - 4, y1], fill=c)
        dr.line([x + 2, kl, x + bw - 2, kl], fill=(60, 60, 60), width=3)
        dr.text((x + bw / 2, y1 + 18), MON[m - 1][0], font=F(18, False), fill=(110, 120, 135), anchor='mm')
    dr.text((x0, y0 - 8), '— Klimamittel', font=F(18, False), fill=(60, 60, 60), anchor='lb')
    return im


def tafel(kopf, zeilen, farbe): return WV.tafel_text(kopf, zeilen, farbe)


def skript(T, S, jahr, bis):
    eigen = next((t['d'] for t in T if not t['fremd']), T[0]['d'])
    seg = []
    seg.append(dict(art='rueck', bg='schloss', fx='frost', tafel_img=tafel('WETTERJAHR %d' % jahr, ['Odenwald · Station Bad König', 'Rückblick bis %s' % dat(bis)], (25, 85, 160)),
                    text='Ei gude, Odenwald! Euer Max hier – und heute gibt es was Besonderes: den großen Rückblick auf das Wetterjahr %d! Was war los an unserer Station in Bad König? Schauen wir es uns an.' % jahr))
    seg.append(dict(art='rueck', bg='hoehen', tafel_img=tafel('DAS JAHR IN ZAHLEN', [
        'Ø Temperatur: %s °C' % k(S['mittel']), 'Regen: %s l/m²' % k(S['regen'], 0), 'Frosttage: %d · Eistage: %d' % (S['frost'], S['eis']),
        'Sommertage: %d · heiße Tage: %d' % (S['sommer'], S['heiss'])], (40, 130, 80)),
        text='Erst mal die nackten Zahlen. Im Schnitt hatten wir %s Grad. Insgesamt sind %s Liter Regen pro Quadratmeter gefallen, an %d Tagen hat es richtig geregnet. Es gab %d Frosttage, aber auch %d Sommertage über 25 Grad – und %d heiße Tage mit mehr als 30 Grad.'
             % (ks(S['mittel']), k(S['regen'], 0), S['regentage'], S['frost'], S['sommer'], S['heiss'])))
    seg.append(dict(art='rueck', bg='wald', tafel_img=grafik_temp(T, S, jahr),
                    text='So sah die Temperatur über das Jahr aus. Der kälteste Monat war der %s, der wärmste der %s. Die roten Linien sind die Höchstwerte, die blauen die Tiefstwerte – und die beiden Punkte markieren den heißesten und den kältesten Tag.'
                         % (MONL[S['kalt_m'] - 1], MONL[S['warm_m'] - 1])))
    seg.append(dict(art='rueck', bg='hoehen', tafel_img=grafik_regen(S, jahr),
                    text='Und der Regen, Monat für Monat. Am nassesten war der %s mit %s Litern pro Quadratmeter, am trockensten der %s mit nur %s Litern. Die schwarzen Striche zeigen, wie viel normalerweise fällt.'
                         % (MONL[S['nass_m'] - 1], k(S['mon'][S['nass_m']]['regen'], 0), MONL[S['trocken_m'] - 1], k(S['mon'][S['trocken_m']]['regen'], 0))))
    rek = [('🏆 HEISSESTER TAG', '%s °C' % k(S['hot']['hi']), S['hot']['d'], (210, 60, 40)), ('🏆 KÄLTESTER TAG', '%s °C' % k(S['cold']['lo']), S['cold']['d'], (40, 90, 190)),
           ('🏆 NASSESTER TAG', '%s l/m²' % k(S['wet']['r']), S['wet']['d'], (40, 130, 170)), ('🏆 STÄRKSTE BÖE', '%s km/h' % k(S['gust']['g'], 0), S['gust']['d'], (100, 110, 70))]
    seg.append(dict(art='rueck', bg='schloss', tafel_img=tafel('DIE REKORDE %d' % jahr, ['%s: %s (%s)' % (r[0].replace('🏆 ', '').capitalize(), r[1], r[2].strftime('%d.%m.')) for r in rek], (200, 150, 20)),
                    text='Jetzt die Rekorde! Der heißeste Tag war der %s mit %s Grad. Am kältesten war es am %s mit %s Grad. Der nasseste Tag war der %s mit %s Litern pro Quadratmeter. Und die stärkste Böe haben wir am %s gemessen: %s Kilometer pro Stunde.'
                         % (dat(S['hot']['d']), ks(S['hot']['hi']), dat(S['cold']['d']), ks(S['cold']['lo']), dat(S['wet']['d']), k(S['wet']['r']), dat(S['gust']['d']), k(S['gust']['g'], 0))))
    hl, txt = [], []
    if S['hitze'][0] >= 3:
        hl.append('Hitzewelle: %d Tage über 30 °C' % S['hitze'][0]); txt.append('Die längste Hitzewelle dauerte %d Tage am Stück über 30 Grad, bis zum %s.' % (S['hitze'][0], dat(S['hitze'][1])))
    if S['trocken'][0] >= 7:
        hl.append('Trockenphase: %d Tage ohne Regen' % S['trocken'][0]); txt.append('%d Tage am Stück fiel praktisch kein Regen – das endete am %s.' % (S['trocken'][0], dat(S['trocken'][1])))
    if S['frostserie'][0] >= 3:
        hl.append('Frostserie: %d Nächte unter 0 °C' % S['frostserie'][0]); txt.append('Die längste Frostserie: %d Nächte in Folge unter null Grad.' % S['frostserie'][0])
    if S['erster_frost']:
        hl.append('Erster Herbstfrost: %s' % S['erster_frost']['d'].strftime('%d.%m.')); txt.append('Der erste Frost im Herbst kam am %s.' % dat(S['erster_frost']['d']))
    if hl:
        seg.append(dict(art='rueck', bg='wald', tafel_img=tafel('HÖHEPUNKTE', hl[:4], (150, 70, 160)), text='Ein paar Höhepunkte aus dem Jahr. ' + ' '.join(txt[:4])))
    d = S['kl_diff']
    vgl = ('%s Grad wärmer als im langjährigen Mittel' % k(d)) if d >= 0.3 else ('%s Grad kühler als im langjährigen Mittel' % k(-d)) if d <= -0.3 else 'ziemlich genau im langjährigen Mittel'
    rg = S['kl_regen']
    rgt = 'etwas nasser als üblich' if rg >= 110 else 'trockener als üblich' if rg <= 90 else 'beim Regen ziemlich normal'
    seg.append(dict(art='rueck', bg='hoehen', tafel_img=tafel('IM VERGLEICH', ['Temperatur: %s%s °C' % ('+' if d >= 0 else '−', k(abs(d))), 'Regen: %d %% vom Mittel' % round(rg), 'Mittel 1991–2020 (DWD)'], (90, 100, 120)),
                    text='Und wie war das Jahr im Vergleich? Verglichen mit dem Klimamittel des Deutschen Wetterdienstes war %d bei uns %s – und %s.' % (jahr, vgl, rgt)))
    seg.append(dict(art='rueck', bg='schloss', tafel_img=tafel('UNSER JAHR', ['Station online seit %s' % eigen.strftime('%d.%m.%Y'), 'wetter-badkoenig.de', 'Max-Videos · Facebook · Instagram'], (25, 85, 160)),
                    text='Und noch was in eigener Sache: Unsere Station in Bad König misst seit dem %s. Seitdem gibt es die Website, und seit diesem Herbst auch mich – euren Max – jeden Morgen auf Facebook und Instagram. Danke an alle, die zuschauen!' % dat(eigen)))
    seg.append(dict(art='outro', bg='schloss', fx='frost',
                    text='Kommt gut rüber ins neue Jahr – und bleibt gesund! Wir sehen uns %d. Euer Max!' % (jahr + 1)))
    return seg


def main():
    jahr = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else dt.date.today().year
    T = [t for t in daten(jahr)]
    bis = T[-1]['d']
    S = statistik(T)
    segs = skript(T, S, jahr, bis)
    heute = dt.date.today()
    ziel = os.path.join(FB, 'jahr.mp4')
    gesamt, echt = WV.baue(segs, heute, ziel, False, titel='JAHRESRÜCKBLICK %d' % jahr)
    text = ('🎬 Das Wetterjahr %d im Odenwald – der große Jahresrückblick mit Max!\n\n' % jahr +
            '🌡️ Ø %s °C · ☔ %s l/m² Regen\n🏆 Heißester Tag: %s °C (%s) · Kältester Tag: %s °C (%s)\n' % (k(S['mittel']), k(S['regen'], 0), k(S['hot']['hi']), S['hot']['d'].strftime('%d.%m.'), k(S['cold']['lo']), S['cold']['d'].strftime('%d.%m.')) +
            '❄️ %d Frosttage · ☀️ %d Sommertage · 🔥 %d heiße Tage\n\n' % (S['frost'], S['sommer'], S['heiss']) +
            'Danke fürs Zuschauen – kommt gut ins neue Jahr! 🎆\n📍 Messwerte unserer Station in Bad König\nLive-Werte & Vorhersage 👉 https://wetter-badkoenig.de\n#Odenwald #BadKönig #Wetter #Jahresrückblick #Wetterjahr%d' % jahr)
    json.dump({'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'datum': heute.isoformat(), 'jahr': jahr, 'bis': bis.isoformat(),
               'dauer': round(gesamt, 1), 'stimme': echt, 'text': text, 'skript': ' '.join(s['text'] for s in segs)},
              open(os.path.join(FB, 'jahr.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('Jahresrückblick fertig: %.0f s\n%s' % (gesamt, text))


if __name__ == '__main__':
    main()
