#!/usr/bin/env python3
"""20.11.2026: Zusatzangaben für das Wetter-Widget (w.html) – Trend, Höchst/Tiefst heute, 24-Std.-Verlauf,
Regen-Hinweis, Frost/Glätte, Max-Satz und DWD-Warnungen aus der gemeinsamen Einstufung (fb/daten.json), Sonnenzeiten.
Wird von widget_daten.py aufgerufen; Fehler hier dürfen das Widget nie leeren."""
import json, os, re, math, datetime as dt

BASIS = os.path.join(os.path.dirname(__file__), '..', '..')
TAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
SCHNEE = set(range(71, 78)) | {85, 86}


def _lade(p):
    try: return json.load(open(os.path.join(BASIS, p), encoding='utf-8'))
    except Exception: return None


def sonne(datum, lat, lon, tz):
    """Sonnenauf-/-untergang (NOAA-Näherung, ±1 Min.)."""
    n = datum.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    de = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g)
    la = math.radians(lat)
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(de)) - math.tan(la) * math.tan(de)))
    def z(minuten):
        t = dt.datetime(datum.year, datum.month, datum.day, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=minuten)
        return t.astimezone(tz).strftime('%H:%M')
    return z(720 - 4 * (lon + ha) - eq), z(720 - 4 * (lon - ha) - eq)


def tagwort(t, heute):
    k = (t.date() - heute).days
    return 'heute' if k == 0 else 'morgen' if k == 1 else TAGE[t.weekday()]


def warnungen(D, now):
    """DWD-Warnungen für Bad König mit Stufe und Ende (wie in fb/daten.json – dieselbe Quelle wie Max)."""
    aus = []
    for h in D.get('warn') or []:
        info = (D.get('warn_info') or {}).get(h) or {}
        if 'Bad König' not in (info.get('gebiet') or h): continue
        m = re.search(r'vor (.+?)(?: für |$)', h)
        w = (m.group(1) if m else h).lower().split(); w[-1] = w[-1].capitalize()
        txt = ('Unwetterwarnung' if 'UNWETTER' in h.upper() else 'Warnung') + ' vor ' + ' '.join(w)
        bis = None
        try:
            b = dt.datetime.fromisoformat(info['bis']).astimezone(now.tzinfo)
            if b < now: continue
            if b.hour == 0 and b.minute == 0: b2 = b - dt.timedelta(minutes=1); bis = 'bis %s 24 Uhr' % tagwort(b2, now.date())
            else: bis = 'bis %s %d%s Uhr' % (tagwort(b, now.date()), b.hour, (':%02d' % b.minute) if b.minute else '')
        except Exception: pass
        aus.append(dict(text=txt, stufe=(D.get('warn_stufe') or {}).get(h) or 1, bis=bis))
    aus.sort(key=lambda x: -x['stufe'])
    return aus


def regen_hinweis(D, now):
    """Aus den Stundenwerten der gemeinsamen Einstufung; Tagesabschnitte, die die Einstufung trocken nennt, gelten als trocken."""
    try:
        T = {x['datum']: x for x in D['tage']}
        h0 = T[now.date().isoformat()]; h1 = T.get((now.date() + dt.timedelta(days=1)).isoformat())
    except Exception: return None
    def abschnitt(t, h):
        n = t.get('nied') or {}
        return n.get('vm') if h < 12 else n.get('nm') if h < 17 else n.get('ab')
    S = []
    for tag, off in ((h0, 0), (h1, 24)):
        if not tag: continue
        for x in tag.get('stunden') or []:
            hh = x['h'] + off
            if hh < now.hour or hh > now.hour + 14: continue
            trocken_abschn = abschnitt(tag, x['h']) == 'trocken'
            nass = not trocken_abschn and (x.get('rp') or 0) >= 50 and (x.get('mm') or 0) >= 0.1
            S.append((hh, nass, x.get('code') in SCHNEE))
    if not S: return None
    wort = lambda s: 'Schnee' if s else 'Regen'
    uhr = lambda hh: 'Mitternacht' if hh % 24 == 0 else '%d Uhr' % (hh % 24) + (' (morgen)' if hh >= 24 and hh % 24 >= 6 else '')
    if S[0][1]:
        for i in range(1, len(S) - 1):
            if not S[i][1] and not S[i + 1][1]:
                return dict(text='%s hält bis ca. %s an, danach meist trocken' % (wort(S[0][2]), uhr(S[i][0])), nass=True)
        return dict(text='%s hält bis in die Nacht an' % wort(S[0][2]), nass=True)
    for hh, nass, sn in S[:7]:
        if nass: return dict(text='%s ab ca. %s möglich' % (wort(sn), uhr(hh)), nass=False)
    if now.hour < 17 and all(abschnitt(h0, h) == 'trocken' for h in range(max(now.hour, 0), 24)):
        return dict(text='Bis zum Abend trocken', nass=False)
    return dict(text='Die nächsten Stunden trocken', nass=False)


def frost(D, now):
    """Frost/Glätte für die kommende Nacht (bzw. heute früh vor 10 Uhr) aus der gemeinsamen Einstufung (Tal-Werte)."""
    try: T = {x['datum']: x for x in D['tage']}
    except Exception: return None
    ziel = now.date() if now.hour < 10 else now.date() + dt.timedelta(days=1)
    t = T.get(ziel.isoformat())
    if not t: return None
    g = (t.get('lage') or {}).get('glaette', 'keine')
    tmin = t.get('tmin')
    teile = []
    if tmin is not None and tmin <= 0: teile.append('Frost bis %s °C' % str(tmin).replace('-', '−'))
    if g and g != 'keine': teile.append('Glatteis-Gefahr' if g == 'glatteis' else 'Glätte möglich')
    if not teile: return None
    vor = 'Heute früh' if ziel == now.date() else 'Nacht auf ' + ('morgen' if False else ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][ziel.weekday()])
    return vor + ': ' + ', '.join(teile)


def max_satz(D, now, warn, regen, fr):
    """Kurzer Satz von Max – nur aus der gemeinsamen Einstufung, damit er nie Max' Videos widerspricht."""
    v = now.timetuple().tm_yday + now.hour // 6
    pick = lambda L: L[v % len(L)]
    if warn and warn[0]['stufe'] >= 2:
        return pick(['Heute gilt eine amtliche Warnung – lieber vorsichtig unterwegs sein.', 'Achtung, der DWD warnt für Bad König – passt gut auf euch auf!'])
    if regen and regen['nass']:
        return pick(['Heute bleibt der Schirm griffbereit.', 'Regenjacke nicht vergessen – es bleibt nass.', 'Ein Tag für drinnen – draußen ist es nass.'])
    if fr:
        return pick(['Es wird frostig – morgens Zeit zum Scheibenkratzen einplanen.', 'Mütze und Handschuhe raus, es wird kalt!'])
    if regen and 'ab ca.' in regen['text']:
        return pick(['Noch trocken – aber den Schirm lieber schon einpacken.', 'Später wird’s nass, Erledigungen draußen am besten jetzt.'])
    try: t = {x['datum']: x for x in D['tage']}[now.date().isoformat()]; s = t.get('sonne') or 0
    except Exception: s = 0
    if now.hour < 16 and s >= 5:
        return pick(['Heute lohnt sich ein Blick nach draußen – viel Sonne!', 'Sonne satt im Odenwald, genießt den Tag!'])
    return pick(['Ein ruhiger Wettertag im Odenwald.', 'Kein Wetter-Drama heute – alles im grünen Bereich.'])


def ergaenzen(d, now, lat, lon, alt):
    """Ergänzt d (Inhalt von widget.json) um die neuen Felder."""
    # 24-Std.-Verlauf (Temperatur, Luftdruck) – laufend fortgeschrieben
    V = list((alt or {}).get('verlauf') or [])
    if not V:
        L = _lade('data/live.json')
        for x in ((L or {}).get('hist') or {}).get('observations') or []:
            m = x.get('metric') or {}
            if x.get('epoch') and m.get('tempAvg') is not None: V.append([x['epoch'], m['tempAvg'], m.get('pressureMax')])
    L = d.get('live') or {}
    try:
        ep = int(dt.datetime.fromisoformat(d['stand']).timestamp())
        if L.get('temp') is not None and (not V or V[-1][0] < ep): V.append([ep, L['temp'], L.get('druck')])
    except Exception: pass
    grenze = now.timestamp() - 24 * 3600
    V = [x for x in V if x[0] >= grenze]
    d['verlauf'] = [[x[0], round(x[1], 1), None if x[2] is None else round(x[2], 1)] for x in V]
    # Trend gegenüber vor ~1 Stunde
    if V:
        ziel = V[-1][0] - 3600
        alt1 = min(V, key=lambda x: abs(x[0] - ziel))
        if abs(alt1[0] - ziel) <= 25 * 60:
            dtv = V[-1][1] - alt1[1]
            d['trend_t'] = 'hoch' if dtv >= 0.3 else 'runter' if dtv <= -0.3 else 'gleich'
            if V[-1][2] is not None and alt1[2] is not None:
                dp = V[-1][2] - alt1[2]
                d['trend_p'] = 'hoch' if dp >= 0.5 else 'runter' if dp <= -0.5 else 'gleich'
    # Höchst/Tiefst heute (eigene Station) mit Uhrzeit
    try:
        H = [x for x in (_lade('data/live.json') or {})['hist']['observations'] if str(x.get('obsTimeLocal', ''))[:10] == now.date().isoformat()]
        hi = max(H, key=lambda x: x['metric']['tempHigh']); lo = min(H, key=lambda x: x['metric']['tempLow'])
        d['hoch'] = [hi['metric']['tempHigh'], str(hi['obsTimeLocal'])[11:16]]
        d['tief'] = [lo['metric']['tempLow'], str(lo['obsTimeLocal'])[11:16]]
    except Exception as e: print('Höchst/Tiefst nicht ermittelt:', e)
    # Sonne
    try: d['sonne'] = list(sonne(now.date(), lat, lon, now.tzinfo))
    except Exception as e: print('Sonnenzeiten nicht berechnet:', e)
    # Gemeinsame Einstufung
    D = _lade('fb/daten.json')
    if D:
        try:
            if (now - dt.datetime.fromisoformat(D['erstellt'])).total_seconds() > 6 * 3600: D = None; print('fb/daten.json zu alt – Einstufung übersprungen')
        except Exception: pass
    if D:
        w = warnungen(D, now)
        d['warn'] = w   # ersetzt Bright-Sky-Liste (gleiche Quelle wie Max)
        r = regen_hinweis(D, now); f = frost(D, now)
        if r: d['regen_hinweis'] = r['text']
        if f: d['frost'] = f
        d['max'] = max_satz(D, now, w, r, f)
        T = {x['datum']: x for x in D.get('tage') or []}
        for t in d.get('tage') or []:   # Symbol, Werte und Regenrisiko wie in Max' Vorhersage
            x = T.get(t['datum'])
            if x: t.update(code=x.get('code', t['code']), max=x.get('tmax', t['max']), min=x.get('tmin', t['min']), rp=x.get('rp', t['rp']))
    else:   # Reserve: Bright-Sky-Warnungen ins gleiche Format bringen
        S = {'minor': 1, 'moderate': 2, 'severe': 3, 'extreme': 4}
        d['warn'] = [dict(text='Warnung vor ' + ' '.join([w.lower() for w in str(x['text']).split()[:-1]] + [str(x['text']).split()[-1].capitalize()]) if x.get('text') else 'Amtliche Warnung',
                          stufe=S.get(x.get('stufe'), x.get('stufe') if isinstance(x.get('stufe'), int) else 1), bis=x.get('bis')) for x in d.get('warn') or []]
    return d
