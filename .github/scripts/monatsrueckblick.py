#!/usr/bin/env python3
"""Monatsrückblick-Video mit Max aus dem Studio (Hochformat, ca. 1,5–2 Min.) aus dem eigenen Wetterarchiv (data/archiv/tage-JJJJ.json).
Wird am 1. des neuen Monats gebaut und ab 15 Uhr gepostet (fb_senden.py monat). Ausgabe: fb/monat.mp4 + fb/monat.json.
Aufruf: python monatsrueckblick.py [JJJJ-MM]   (ohne Angabe: der Vormonat)
Ablauf: Begrüßung · Monat in Zahlen · Temperaturkurve · Regen je Tag · Vergleich (Klimamittel + Vorjahresmonat) ·
besondere Momente · Ausblick (Klimamittel des neuen Monats) · Schluss mit Zuschauerfrage."""
import os, sys, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wetter_video as WV
import jahresrueckblick as JR
from jahresrueckblick import k, ks, dat, karte, MON, MONL, KL_TMAX, KL_TMIN, KL_RAIN, KORR
from wetter_video import F

ROOT = WV.ROOT; FB = WV.FB
VORJAHR_STATION = 'IBADKN32'   # Vergleichsstation für den Vorjahresmonat, bis eigene Daten vorliegen (Messbeginn 20.01.2026)


def monat_daten(jahr, monat):
    try: T = JR.daten(jahr)
    except Exception: return [], []
    vor = [t for t in T if t['d'] < dt.date(jahr, monat, 1)]
    return [t for t in T if t['d'].month == monat], vor


def vorjahr(jahr, monat):
    """Vorjahresmonat: eigenes Archiv, falls vorhanden, sonst IBADKN32 über Weather Underground."""
    T, _ = monat_daten(jahr - 1, monat)
    eigen = [t for t in T if not t['fremd']]
    if len(eigen) >= 25: return dict(quelle='Station Bad König', T=eigen)
    try:
        import archiv
        ende = (dt.date(jahr - 1, monat, 28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
        j = archiv.get('/v2/pws/history/daily', station=VORJAHR_STATION, startDate='%d%02d01' % (jahr - 1, monat), endDate=ende.strftime('%Y%m%d'))
        L = []
        for o in (j.get('observations') or j.get('summaries') or []):
            m = o.get('metric') or {}
            if m.get('tempHigh') is None: continue
            L.append(dict(d=dt.date.fromisoformat(str(o['obsTimeLocal'])[:10]), hi=m['tempHigh'], lo=m['tempLow'],
                          avg=m.get('tempAvg', (m['tempHigh'] + m['tempLow']) / 2), r=m.get('precipTotal') or 0, g=m.get('windgustHigh') or 0, fremd=True))
        if len(L) >= 25: return dict(quelle='Nachbarstation in Bad König', T=L)
    except Exception as e:
        print('Vorjahresmonat nicht abrufbar:', e)
    return None


def statistik(T, vor):
    E = [t for t in T if not t['fremd']] or T
    S = dict(n=len(T), mittel=sum(t['avg'] for t in T) / len(T), regen=sum(t['r'] for t in T), regentage=sum(t['r'] >= 1 for t in T),
             frost=sum(t['lo'] < 0 for t in T), eis=sum(t['hi'] < 0 for t in T), sommer=sum(t['hi'] >= 25 for t in T),
             hot=max(E, key=lambda t: t['hi']), cold=min(E, key=lambda t: t['lo']), wet=max(E, key=lambda t: t['r']), gust=max(E, key=lambda t: t['g']))
    S['frostserie'] = JR.serie(E, lambda t: t['lo'] < 0); S['trocken'] = JR.serie(E, lambda t: t['r'] < 0.2)
    m = T[0]['d'].month
    S['kl_diff'] = S['mittel'] - ((KL_TMAX[m - 1] + KL_TMIN[m - 1]) / 2 + KORR)
    tage_m = ((T[0]['d'].replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)).day
    S['kl_regen'] = S['regen'] / (KL_RAIN[m - 1] * len(T) / tage_m) * 100   # bei fehlenden Tagen anteilig
    # besondere Momente: Jahresrekorde (nur eigene Messwerte), erster Herbstfrost
    ev = [t for t in vor if not t['fremd']]
    S['rek'] = []
    if ev:
        if S['hot']['hi'] > max(t['hi'] for t in ev): S['rek'].append(('wärmster Tag des Jahres bisher', S['hot']['d'], '%s °C' % k(S['hot']['hi'])))
        if S['cold']['lo'] < min(t['lo'] for t in ev): S['rek'].append(('kältester Tag des Jahres bisher', S['cold']['d'], '%s °C' % k(S['cold']['lo'])))
        if S['wet']['r'] > max(t['r'] for t in ev) and S['wet']['r'] >= 5: S['rek'].append(('nassester Tag des Jahres bisher', S['wet']['d'], '%s l/m²' % k(S['wet']['r'])))
        if S['gust']['g'] > max(t['g'] for t in ev) and S['gust']['g'] >= 40: S['rek'].append(('stärkste Böe des Jahres bisher', S['gust']['d'], '%s km/h' % k(S['gust']['g'], 0)))
    herbst_vor = any(t['lo'] < 0 for t in vor if t['d'].month >= 8)
    S['erster_frost'] = None if herbst_vor or m < 8 else next((t for t in E if t['lo'] < 0), None)
    return S


def grafik_temp(T, S, titel):
    im, dr = karte(titel, (215, 90, 40), 360)
    x0, x1, y0, y1 = 46, 420, 100, 315
    lo, hi = min(t['lo'] for t in T) - 1, max(t['hi'] for t in T) + 1
    Y = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
    n = len(T); X = lambda i: x0 + i / max(1, n - 1) * (x1 - x0)
    if lo < 0 < hi: dr.line([x0, Y(0), x1, Y(0)], fill=(150, 180, 220), width=2); dr.text((x0 - 6, Y(0)), '0°', font=F(16, False), fill=(110, 130, 160), anchor='rm')
    for i, t in enumerate(T):
        if t['d'].day in (1, 10, 20) or i == n - 1: dr.text((X(i), y1 + 16), str(t['d'].day), font=F(17, False), fill=(110, 120, 135), anchor='mm')
    dr.line([(X(i), Y(t['hi'])) for i, t in enumerate(T)], fill=(230, 110, 60), width=3)
    dr.line([(X(i), Y(t['lo'])) for i, t in enumerate(T)], fill=(70, 130, 210), width=3)
    for t, c, v in ((S['hot'], (200, 40, 30), S['hot']['hi']), (S['cold'], (30, 80, 180), S['cold']['lo'])):
        i = T.index(t); dr.ellipse([X(i) - 7, Y(v) - 7, X(i) + 7, Y(v) + 7], fill=c, outline=(255, 255, 255), width=2)
    dr.text((x1, y0 - 8), 'Höchst · Tiefst', font=F(17, False), fill=(110, 120, 135), anchor='rb')
    return im


def grafik_regen(T, S, titel):
    im, dr = karte(titel, (40, 110, 200), 360)
    x0, x1, y0, y1 = 30, 425, 105, 312
    mx = max(5, max(t['r'] for t in T)) * 1.1; bw = (x1 - x0) / len(T)
    for i, t in enumerate(T):
        if t['r'] <= 0: continue
        c = (30, 90, 190) if t is S['wet'] else (110, 160, 220)
        dr.rectangle([x0 + i * bw + 1, y1 - t['r'] / mx * (y1 - y0), x0 + (i + 1) * bw - 1, y1], fill=c)
        if t['d'].day in (1, 10, 20): pass
    for i, t in enumerate(T):
        if t['d'].day in (1, 10, 20) or i == len(T) - 1: dr.text((x0 + (i + 0.5) * bw, y1 + 16), str(t['d'].day), font=F(17, False), fill=(110, 120, 135), anchor='mm')
    dr.text((x0, y0 - 8), 'Summe %s l/m²' % k(S['regen'], 0), font=F(19), fill=(40, 90, 160), anchor='lb')
    return im


def tafel(kopf, zeilen, farbe): return WV.tafel_text(kopf, zeilen, farbe)


def skript(T, S, jahr, monat, V):
    M = MONL[monat - 1]; nm = monat % 12 + 1; NM = MONL[nm - 1]
    seg = []
    seg.append(dict(art='intro', bg='studio', tafel_img=tafel('RÜCKBLICK %s' % M.upper(), ['%s %d' % (M, jahr), 'Odenwald · Station Bad König', '• Zahlen · Kurven · Vergleich'], (25, 85, 160)),
                    text='Hallo Odenwald! Euer Max meldet sich aus dem Studio – heute mit dem Rückblick auf den %s. Wie war der Monat an unserer Station in Bad König? Schauen wir es uns an.' % M))
    z = ['Ø Temperatur: %s °C' % k(S['mittel']), 'Wärmster Tag: %s °C (%s)' % (k(S['hot']['hi']), S['hot']['d'].strftime('%d.%m.')),
         'Kältester Tag: %s °C (%s)' % (k(S['cold']['lo']), S['cold']['d'].strftime('%d.%m.')), 'Regen: %s l/m² an %d Tagen' % (k(S['regen'], 0), S['regentage'])]
    if S['frost']: z.append('Frosttage: %d' % S['frost'])  # Tafel
    if S['sommer']: z.append('Sommertage: %d' % S['sommer'])
    z.append('Stärkste Böe: %s km/h' % k(S['gust']['g'], 0))
    t = ('Erst mal die Zahlen. Im Schnitt hatten wir %s Grad. Am wärmsten war es am %s mit %s Grad, am kältesten am %s mit %s Grad. '
         'Insgesamt sind %s Liter Regen pro Quadratmeter gefallen, an %d Tagen hat es richtig geregnet.') % (
        ks(S['mittel']), dat(S['hot']['d']), ks(S['hot']['hi']), dat(S['cold']['d']), ks(S['cold']['lo']), k(S['regen'], 0), S['regentage'])
    if S['frost']: t += ' %d Nächte hatten Frost.' % S['frost'] if S['frost'] > 1 else ' In einer Nacht gab es Frost.'
    t += ' Und die stärkste Böe haben wir mit %s Kilometern pro Stunde gemessen.' % k(S['gust']['g'], 0)
    seg.append(dict(art='rueck', bg='studio', tafel_img=tafel('DER %s IN ZAHLEN' % M.upper(), z, (40, 130, 80)), text=t))
    seg.append(dict(art='rueck', bg='studio', tafel_img=grafik_temp(T, S, 'TEMPERATUR %s' % M.upper()),
                    text='So lief die Temperatur durch den Monat: oben die Höchstwerte, unten die Tiefstwerte. Die beiden Punkte zeigen den wärmsten und den kältesten Moment.'
                         + (' Unter der hellblauen Linie wurde es frostig.' if S['cold']['lo'] < 0 < S['hot']['hi'] else '')))
    seg.append(dict(art='rueck', bg='studio', tafel_img=grafik_regen(T, S, 'REGEN JE TAG (l/m²)'),
                    text=('Und der Regen, Tag für Tag. Der nasseste Tag war der %s mit %s Litern pro Quadratmeter.' % (dat(S['wet']['d']), k(S['wet']['r'])))
                    if S['wet']['r'] >= 1 else 'Und der Regen, Tag für Tag – da war nicht viel los, der Monat blieb fast trocken.'))
    d = S['kl_diff']; rg = S['kl_regen']
    vgl = ('%s Grad wärmer als im langjährigen Mittel' % k(d)) if d >= 0.3 else ('%s Grad kühler als im langjährigen Mittel' % k(-d)) if d <= -0.3 else 'ziemlich genau so warm wie im langjährigen Mittel'
    rgt = 'nasser als üblich' if rg >= 115 else 'trockener als üblich' if rg <= 85 else 'beim Regen ziemlich normal'
    zz = ['Temperatur: %s%s °C zum Mittel' % ('+' if d >= 0 else '−', k(abs(d))), 'Regen: %d %% vom Mittel' % round(rg)]
    txt = 'Und wie war der %s im Vergleich? Gemessen am Klimamittel des Deutschen Wetterdienstes war er bei uns %s – und %s.' % (M, vgl, rgt)
    if V:
        VT = V['T']; vm = sum(t['avg'] for t in VT) / len(VT); vr = sum(t['r'] for t in VT); dv = S['mittel'] - vm
        zz.append('%s %d: Ø %s °C · %s l/m²' % (M, jahr - 1, k(vm), k(vr, 0)))
        txt += ' Und verglichen mit dem %s %d war es diesmal %s' % (M, jahr - 1, ('%s Grad wärmer' % k(dv)) if dv >= 0.3 else ('%s Grad kälter' % k(-dv)) if dv <= -0.3 else 'fast genauso warm')
        txt += ', bei %s Regen.' % ('mehr' if S['regen'] > vr * 1.15 else 'weniger' if S['regen'] < vr * 0.85 else 'ähnlich viel')
        if V['quelle'] != 'Station Bad König': zz.append('Vorjahr: Nachbarstation')
    zz.append('Mittel 1991–2020 (DWD)')
    seg.append(dict(art='rueck', bg='studio', tafel_img=tafel('IM VERGLEICH', zz, (90, 100, 120)), text=txt))
    hl, ht = [], []
    for name, tag, wert in S['rek'][:2]:
        hl.append('Rekord: %s – %s (%s)' % (name, wert, tag.strftime('%d.%m.'))); ht.append('Neuer Jahresrekord am %s: %s, mit %s.' % (dat(tag), name, wert.replace('°C', 'Grad').replace('l/m²', 'Litern pro Quadratmeter').replace('km/h', 'Kilometern pro Stunde')))
    if S['erster_frost'] and len(hl) < 2:
        hl.append('Erster Frost des Herbstes: %s' % S['erster_frost']['d'].strftime('%d.%m.')); ht.append('Der erste Frost des Herbstes kam am %s.' % dat(S['erster_frost']['d']))
    if S['frostserie'][0] >= 3 and len(hl) < 2:
        hl.append('Frostserie: %d Nächte in Folge' % S['frostserie'][0]); ht.append('%d Nächte am Stück fiel die Temperatur unter null Grad.' % S['frostserie'][0])
    if S['trocken'][0] >= 7 and len(hl) < 2:
        hl.append('Trockenphase: %d Tage ohne Regen' % S['trocken'][0]); ht.append('%d Tage am Stück fiel praktisch kein Regen.' % S['trocken'][0])
    if hl: seg.append(dict(art='rueck', bg='studio', tafel_img=tafel('BESONDERE MOMENTE', hl, (150, 70, 160)), text='Ein paar besondere Momente. ' + ' '.join(ht)))
    kx, kn, kr = KL_TMAX[nm - 1] + KORR, KL_TMIN[nm - 1] + KORR, KL_RAIN[nm - 1]
    at = 'Und was bringt der %s normalerweise? Im langjährigen Mittel sind es bei uns tagsüber rund %s Grad und nachts etwa %s Grad, dazu um die %s Liter Regen.' % (NM, ks(kx, 0), ks(kn, 0), k(kr, 0))
    if nm == 12: at += ' Und ob es weiße Weihnachten gibt? Das kann heute noch niemand seriös sagen – ich halte euch auf dem Laufenden.'
    seg.append(dict(art='rueck', bg='studio', tafel_img=tafel('AUSBLICK %s' % NM.upper(), ['So ist es normalerweise:', 'tagsüber ~%s °C · nachts ~%s °C' % (k(kx, 0), k(kn, 0)), 'Regen ~%s l/m²' % k(kr, 0)], (25, 85, 160)), text=at))
    seg.append(dict(art='outro', bg='studio', text='Wie fandet ihr den %s? Schreibt es mir in die Kommentare! Das war mein Monatsrückblick – alle Live-Werte findet ihr auf wetter-badkoenig.de. Bis bald, euer Max!' % M))
    return seg


def main():
    heute = dt.date.today()
    if len(sys.argv) > 1 and '-' in sys.argv[1]: jahr, monat = map(int, sys.argv[1].split('-'))
    else: v = heute.replace(day=1) - dt.timedelta(days=1); jahr, monat = v.year, v.month
    T, vor = monat_daten(jahr, monat)
    if len(T) < 20: print('Zu wenige Tage im Archiv für %02d/%d (%d).' % (monat, jahr, len(T))); return
    S = statistik(T, vor); V = vorjahr(jahr, monat)
    segs = skript(T, S, jahr, monat, V)
    ziel = os.path.join(FB, 'monat.mp4')
    gesamt, echt = WV.baue(segs, heute, ziel, False, titel='RÜCKBLICK %s' % MONL[monat - 1].upper())
    M = MONL[monat - 1]
    text = ('📅 Der %s %d im Odenwald – der Monatsrückblick mit Max!\n\n' % (M, jahr) +
            '🌡️ Ø %s °C · ☔ %s l/m² Regen an %d Tagen\n' % (k(S['mittel']), k(S['regen'], 0), S['regentage']) +
            '🔺 Wärmster Tag: %s °C (%s) · 🔻 Kältester: %s °C (%s)\n' % (k(S['hot']['hi']), S['hot']['d'].strftime('%d.%m.'), k(S['cold']['lo']), S['cold']['d'].strftime('%d.%m.')) +
            (('❄️ %d Frosttag%s · ' % (S['frost'], '' if S['frost'] == 1 else 'e')) if S['frost'] else '') + '💨 stärkste Böe %s km/h\n\n' % k(S['gust']['g'], 0) +
            'Wie fandet ihr den %s? Schreibt es in die Kommentare! 👇\n📍 Messwerte unserer Station in Bad König\n' % M +
            'Live-Werte & Vorhersage 👉 https://wetter-badkoenig.de\n#Odenwald #Odenwaldkreis #BadKönig #Wetter #Monatsrückblick #Wettervideo')
    json.dump({'erstellt': dt.datetime.now().astimezone().isoformat(timespec='minutes'), 'datum': heute.isoformat(), 'monat': '%d-%02d' % (jahr, monat),
               'dauer': round(gesamt, 1), 'stimme': echt, 'text': text, 'skript': ' '.join(s['text'] for s in segs)},
              open(os.path.join(FB, 'monat.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    WV.archiv('monat', heute, False, [], gesamt)
    print('Monatsrückblick fertig: %.0f s\n%s' % (gesamt, text))


if __name__ == '__main__':
    main()
