#!/usr/bin/env python3
"""Live-Werte der 6 Kartenorte im Odenwaldkreis für die Seite „Aktuell Odenwald“ (15.11.2026).
Läuft im 10-Minuten-Lauf (widget.yml) und schreibt data/odenwald-live.json:
stand, orte[name, el, lat, lon, quelle, t, rh, w, g, r (Regen heute), p, zeit], verlauf{name: [[HH:MM, t], ...]} für heute."""
import json, os, sys, math, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from fb_post import get, WU_KEY, TZ

ORTE = [('Breuberg', 160, 'wu', 'IBREUB3', 49.818, 9.040), ('Höchst i. Odw.', 170, 'wu', 'IHCHST74', 49.799, 8.994),
        ('Bad König', 185, 'wu', 'IBADKN33', 49.743, 9.006), ('Michelstadt', 250, 'wu', 'IMICHE124', 49.673, 9.014),
        ('Mossautal', 315, 'wu', 'IMOSSA13', 49.667, 8.937), ('Oberzent', 461, 'wu', 'IBEERFEL4', 49.567, 8.976)]
# 15.11.2026: Michelstadt (vorher DWD 03284, ohne Wind), Mossautal (vorher DWD 03287 = in Wahrheit Michelstadt-Vielbrunn!)
# und Oberzent (vorher DWD 00330, ohne Wind) auf private WU-Stationen umgestellt. dwd() bleibt als Reserve.
# 17.11.2026: Regen-Plausibilität. Meldet ein Ort fast keinen Regen, während die anderen deutlich Regen messen (Regenmesser
# verstopft/defekt – so bei Höchst IHCHST74 seit 16.11.2026), wird der Wert nicht gezeigt, sondern durch eine Nachbarstation ersetzt.
# 22.11.2026: Michelstadt von IMICHELS20 (Luftdruck ~16 hPa zu niedrig, nicht auf Meereshöhe abgeglichen) auf IMICHE124 umgestellt.
# Luftdruck-Korrektur je Station in hPa (Abgleich mit DWD Michelstadt-Vielbrunn und IBADKN33 am 22.11.2026, 15:40 Uhr).
# Erweitert 22.11.2026, 15:55 Uhr: alle Odenwald-Stationen auf IBADKN33 (eigene Station, Offset +5,4 hPa, stimmt mit DWD überein)
# abgeglichen – Median des Abstands 12:30–15:30 Uhr. Brombachtal (IBROMB4) liefert keinen Luftdruck.
P_KORR = {'IMICHE124': 2.4, 'IBREUB3': 0.7, 'IHCHST74': 6.4, 'IMOSSA13': 7.1, 'IBEERFEL4': 3.4,
          'IREICH180': 7.3, 'ILTZEL13': 1.0, 'IBROMB18': -5.4,
          'IMOSSA10': -7.1}   # 22.11.2026, 21:55 Uhr: IMOSSA10 (Reserve Mossautal) 30,22 inHg = 1023,4 hPa gegen IBADKN33 1016,3 hPa
# 22.11.2026, 16:10 Uhr: Stationen ohne Luftdruck bekommen ihn von einer Nachbarstation (übrige Werte bleiben von der Hauptstation).
P_ERSATZ = {'IBROMB4': 'IBROMB18'}   # Brombachtal: IBROMB4 (WH2600, kein Drucksensor) → Luftdruck von IBROMB18 (1,2 km)
# 22.11.2026, 21:50 Uhr (Kingman, Variante 2): sendet die Hauptstation über 60 Min. nichts, springt eine Reserve-Station ein;
# kommt die Hauptstation zurück, wird sie wieder genommen. Luftdruck der Reserve über P_KORR auf IBADKN33 abgeglichen.
AUSFALL_ERSATZ = {'IMOSSA13': 'IMOSSA10'}   # Mossautal: IMOSSA13 offline seit 22.11. 19:42 → IMOSSA10 „Bauhof Mossautal“ (2,5 km)
REGEN_ERSATZ = {'Höchst i. Odw.': ['IHCHSTIO2', 'IDTSANDB5']}   # private WU-Stationen in der Nähe, in dieser Reihenfolge; danach DWD (nächste Station)
REGEN_MIN_MEDIAN = 5.0    # erst prüfen, wenn die anderen Orte im Mittel (Median) mindestens so viel Regen haben
REGEN_ANTEIL = 0.25       # unplausibel: weniger als ein Viertel des Medians der anderen Orte
def reserve_text(n, sid, ist_extra):
    """23.11.2026: welche Reserve einspringen kann (Anzeige in der Zentrale)."""
    t = []
    if sid == 'IBADKN33': t.append('Weather Underground')
    if sid in AUSFALL_ERSATZ: t.append('%s (springt nach 60 Min. ein)' % AUSFALL_ERSATZ[sid])
    if n in REGEN_ERSATZ: t.append('Regen: ' + ', '.join(REGEN_ERSATZ[n]))
    if ist_extra: t.append('andere Station im Ort (automatische Wahl)')
    if sid != 'IBADKN33': t.append('Netatmo-Gegenprobe Regen/Böen')
    return ' · '.join(t)


ALARM = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'stationen-alarm.json')


def stationen_alarm(orte, jetzt):
    """23.11.2026 (Kingman): Push, sobald eine Station über 90 Min. nichts sendet oder eine Reserve einspringt – je Ausfall einmal, mit Entwarnung."""
    try: A = json.load(open(ALARM, encoding='utf-8'))
    except Exception: A = {}
    neu, push = {}, []
    for o in orte:
        n = o['name']; kn = n.replace(' i. Odw.', '')
        alter = (jetzt - dt.datetime.fromisoformat(o['zeit'])).total_seconds() / 60 if o.get('zeit') else 9999
        rot = alter > 90 or bool(o.get('station_ersatz'))
        if rot:
            neu[n] = A.get(n) or jetzt.isoformat(timespec='minutes')
            if n not in A:
                push.append('📡 %s (%s) sendet seit %s nichts%s' % (kn, o.get('station') or '?', ('%d Min.' % alter) if alter < 600 else 'über 10 Std.',
                            ' – Reserve %s ist eingesprungen' % o['station_ersatz'] if o.get('station_ersatz') else ''))
        elif n in A:
            push.append('✅ %s (%s) sendet wieder' % (kn, o.get('station') or '?'))
    if neu != A: json.dump(neu, open(ALARM, 'w', encoding='utf-8'), ensure_ascii=False)
    t = os.environ.get('NTFY_TOPIC')
    if push and t:
        try: urllib.request.urlopen(urllib.request.Request('https://ntfy.sh/' + t, data='\n'.join(push).encode('utf-8'),
                 headers={'Title': 'Odenwald-Stationen', 'Tags': 'satellite_antenna', 'Click': 'https://sakomobil-beep.github.io/zentrale/'}), timeout=20).read()
        except Exception as e: print('Push:', e)
    print('Stations-Alarm:', push or 'alles ok')


DATEI = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'odenwald-live.json')
r1 = lambda v: None if v is None else round(float(v), 1)


import time, urllib.request
START = time.time()


def get_wu(url):
    """Schneller Abruf für Weather Underground: 2 Versuche à 12 s statt 5 à 45 s, damit der 10-Minuten-Lauf nie abbricht (18.11.2026)."""
    for v in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de'}), timeout=12) as r: return json.loads(r.read().decode())
        except Exception as e:
            if v or getattr(e, 'code', None) in (401, 403, 429): raise
            time.sleep(2)


def wu(sid):
    if sid == 'IBADKN33':   # 18.11.2026: eigene Station nicht doppelt abrufen – der Live-Werte-Lauf hat sie gerade in data/live.json geholt
        try:
            o = json.load(open(os.path.join(os.path.dirname(DATEI), 'live.json'), encoding='utf-8'))['cur']['observations'][0]
            if time.time() - o['epoch'] < 20 * 60: return wu_werte(o)
        except Exception as e: print('live.json nicht nutzbar, rufe WU ab:', e)
    o = (get_wu('https://api.weather.com/v2/pws/observations/current?stationId=%s&format=json&units=m&numericPrecision=decimal&apiKey=%s' % (sid, WU_KEY)).get('observations') or [None])[0]
    v = wu_werte(o) if o else None
    if v and v.get('p') is not None and sid in P_KORR: v['p'] = r1(v['p'] + P_KORR[sid])
    if v and v.get('p') is None and sid in P_ERSATZ:
        try: v['p'] = (wu(P_ERSATZ[sid]) or {}).get('p')
        except Exception: pass
    return v


def wu_werte(o):
    m = o.get('metric') or {}
    return dict(t=r1(m.get('temp')), rh=o.get('humidity'), w=r1(m.get('windSpeed')), g=r1(m.get('windGust')), r=r1(m.get('precipTotal')),
                rr=r1(m.get('precipRate')), sol=o.get('solarRadiation'), p=r1(m.get('pressure')),
                wd=o.get('winddir'), td=r1(m.get('dewpt')), uv=o.get('uv'), gf=gefuehlt(m), zeit=dt.datetime.fromtimestamp(o['epoch'], TZ).isoformat(timespec='minutes'))


def gefuehlt(m):
    """Gefühlte Temperatur: Windchill bei Kälte und Wind, Hitzeindex bei Wärme, sonst die Lufttemperatur (18.11.2026)."""
    t = m.get('temp')
    if t is None: return None
    if t <= 10 and (m.get('windSpeed') or 0) > 4.8 and m.get('windChill') is not None: return r1(m['windChill'])
    if t >= 27 and m.get('heatIndex') is not None: return r1(m['heatIndex'])
    return r1(t)


# 18.11.2026: fünf weitere Orte für „Aktuell Odenwald“ (erst in der Live-Vorschau). Die Station wird automatisch gesucht:
# nächste private WU-Station mit aktuellen Werten, nicht schon von einem anderen Ort benutzt; die Wahl hält 24 Stunden.
# 19.11.2026: Erbach raus (zu nah an Michelstadt)
EXTRA = [('Reichelsheim', 215, 49.713, 8.838),   # 22.11.2026: Fränkisch-Crumbach ganz entfernt (seit 19.11. nicht mehr angezeigt)
         ('Brombachtal', 250, 49.735, 8.946), ('Lützelbach', 230, 49.784, 9.077)]
EXTRA_AN = True   # 18.11.2026 23:50: wieder an; seit 22.11.2026 alle Orte alle 20 Minuten
# 19.11.2026: unplausible Stationen nie wieder wählen (IBROMB9: Regenmesser 0 mm bei Dauerregen, Luftdruck ~10 hPa zu tief)
SPERRE = {'IBROMB9', 'IBROMB18'}   # IBROMB18: 8 mm Regen, wo alle anderen 1–2 mm haben
STATIONSWAHL = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'odenwald-stationen.json')


def extra_stationen(jetzt, belegt):
    try: W = json.load(open(STATIONSWAHL, encoding='utf-8'))
    except Exception: W = {}
    neu = False
    for n, el, la, lo in EXTRA:
        w = W.get(n)
        if time.time() - START > 90: break   # Zeit reicht nicht mehr – nächster Lauf sucht weiter
        if w and w['id'] in SPERRE: W.pop(n, None); w = None
        if w and (jetzt - dt.datetime.fromisoformat(w['gewaehlt'])).total_seconds() < 7 * 86400: belegt.add(w['id']); continue
        try:
            L = get_wu('https://api.weather.com/v3/location/near?geocode=%s,%s&product=pws&format=json&apiKey=%s' % (la, lo, WU_KEY)).get('location') or {}
            ids, km = L.get('stationId') or [], L.get('distanceKm') or []
        except Exception as e: print('Stationssuche %s:' % n, e); continue
        for sid, k in zip(ids, km):
            if sid in belegt or sid in SPERRE or k > 4: continue
            try: v = wu(sid)
            except Exception: v = None
            if v and v.get('t') is not None and (jetzt - dt.datetime.fromisoformat(v['zeit'])).total_seconds() < 3600:
                W[n] = dict(id=sid, km=k, gewaehlt=jetzt.isoformat(timespec='minutes')); belegt.add(sid); neu = True; print('Station für %s: %s (%s km)' % (n, sid, k)); break
            if time.time() - START > 90: break
        if n not in W and w: W[n] = w   # alte Wahl behalten, falls die Suche nichts bringt
    if neu: json.dump(W, open(STATIONSWAHL, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return W


def archiv_lesen(jetzt):
    A = {}
    for m in {jetzt.strftime('%Y-%m'), (jetzt - dt.timedelta(days=31)).strftime('%Y-%m'), (jetzt - dt.timedelta(days=1)).strftime('%Y-%m')}:
        try:
            for st, werte in json.load(open(os.path.join(os.path.dirname(DATEI), 'odenwald-archiv', m + '.json'), encoding='utf-8')).items(): A.setdefault(st, {}).update(werte)
        except Exception: pass
    return A


def vergleich(o, A, jetzt):
    """Wert von gestern um diese Zeit und Regensummen 24 h / 7 Tage / Monat aus dem Archiv (18.11.2026)."""
    W = A.get(o['name']) or {}
    if not W: return
    ziel = jetzt - dt.timedelta(days=1)
    best = None
    for z, v in W.items():
        try: d = abs((dt.datetime.fromisoformat(z).replace(tzinfo=TZ) - ziel).total_seconds())
        except Exception: continue
        if d <= 20 * 60 and (best is None or d < best[0]): best = (d, v)
    if best: o['t_gestern'] = best[1][0]; r_gestern_jetzt = best[1][4]
    else: r_gestern_jetzt = None
    tag = {}
    for z in sorted(W):
        if W[z][4] is not None: tag[z[:10]] = W[z][4]   # letzter Wert des Tages = Tagessumme
    heute = jetzt.date().isoformat(); tag[heute] = o.get('r') if o.get('r') is not None else tag.get(heute)
    gestern = ziel.date().isoformat()
    if o.get('r') is not None and gestern in tag and r_gestern_jetzt is not None: o['r24'] = round(o['r'] + max(0, tag[gestern] - r_gestern_jetzt), 1)
    tage7 = [(jetzt - dt.timedelta(days=i)).date().isoformat() for i in range(7)]
    v7 = [tag[t] for t in tage7 if tag.get(t) is not None]
    if v7: o['r7'] = round(sum(v7), 1); o['r7_tage'] = len(v7)
    vm = [v for t, v in tag.items() if t[:7] == heute[:7] and v is not None]
    if vm: o['rmon'] = round(sum(vm), 1); o['rmon_tage'] = len(vm); o['r_seit'] = min(t for t in tag if tag[t] is not None)


def dwd(sid, heute):
    w = get('https://api.brightsky.dev/current_weather?dwd_station_id=%s&tz=Europe/Berlin' % sid).get('weather') or {}
    if w.get('temperature') is None: return None
    r = None
    try:   # Regen heute: Stundenwerte seit Mitternacht
        h = get('https://api.brightsky.dev/weather?dwd_station_id=%s&date=%s&tz=Europe/Berlin' % (sid, heute)).get('weather') or []
        bis = dt.datetime.now(TZ).isoformat()
        r = round(sum((x.get('precipitation') or 0) for x in h if x.get('timestamp', '')[:10] == heute and x['timestamp'] <= bis), 1)
    except Exception as e: print('Regen heute %s:' % sid, e)
    return dict(t=r1(w.get('temperature')), rh=w.get('relative_humidity'), w=r1(w.get('wind_speed_10')), g=r1(w.get('wind_gust_speed_10')),
                r=r, p=r1(w.get('pressure_msl')), zeit=dt.datetime.fromisoformat(w['timestamp']).astimezone(TZ).isoformat(timespec='minutes'))


def regen_unplausibel(r, andere):
    """True, wenn der Regenwert r neben den Werten der anderen Orte nicht stimmen kann (Messer gestört)."""
    andere = sorted(v for v in andere if v is not None)
    if r is None or len(andere) < 3: return False
    n = len(andere); med = andere[n // 2] if n % 2 else (andere[n // 2 - 1] + andere[n // 2]) / 2
    return med >= REGEN_MIN_MEDIAN and r < REGEN_ANTEIL * med


def regen_dwd(la, lo, heute):
    """Regen heute an der nächstgelegenen DWD-Station (Bright Sky, Stundenwerte seit Mitternacht) oder None."""
    h = get('https://api.brightsky.dev/weather?lat=%s&lon=%s&date=%s&tz=Europe/Berlin' % (la, lo, heute)).get('weather') or []
    bis = dt.datetime.now(TZ).isoformat()
    w = [x.get('precipitation') for x in h if x.get('timestamp', '')[:10] == heute and x['timestamp'] <= bis and x.get('precipitation') is not None]
    return round(sum(w), 1) if w else None


NETATMO_URL = 'https://wetter-badkoenig.sakomobil.workers.dev/netatmo'   # 22.11.2026: Worker holt öffentliche Netatmo-Stationen im Kreis (15 Min. Speicher)
_NETATMO = None


def netatmo_regen(la, lo, km=3.0):   # 22.11.2026, 19:05 Uhr: Umkreis 3 statt 2 km (Kingman)
    """Regen heute an Netatmo-Regenmessern im Umkreis 3 km (Median, ab 2 Messern) -> (mm, Anzahl) oder (None, n)."""
    global _NETATMO
    import math
    if _NETATMO is None:
        try:   # eigener Abruf mit 40 s Wartezeit: der Worker fragt bei leerem Speicher 4 Kacheln bei Netatmo ab (22.11.2026)
            with urllib.request.urlopen(urllib.request.Request(NETATMO_URL, headers={'User-Agent': 'wetter-badkoenig.de'}), timeout=40) as r: _NETATMO = json.loads(r.read().decode()).get('body') or []
        except Exception as e: print('Netatmo nicht abrufbar:', e); _NETATMO = []
    jetzt = time.time(); W = []
    for s in _NETATMO:
        lo2, la2 = s['place']['location']
        if math.hypot((la2 - la) * 111, (lo2 - lo) * 72) > km: continue
        for m in s.get('measures', {}).values():
            if 'rain_24h' in m and m.get('rain_timeutc') and jetzt - m['rain_timeutc'] < 3600 and m['rain_24h'] is not None: W.append(m['rain_24h'])
    W.sort()
    if len(W) < 2: return None, len(W)
    n = len(W); return round(W[n // 2] if n % 2 else (W[n // 2 - 1] + W[n // 2]) / 2, 1), n


def netatmo_wind(la, lo, km=5.0):
    """Böen der Netatmo-Windmesser im Umkreis (22.11.2026) -> (Median km/h, Anzahl, Maximum) – nur Werte der letzten Stunde."""
    global _NETATMO
    import math
    if _NETATMO is None: netatmo_regen(la, lo)   # lädt die Netatmo-Daten
    jetzt = time.time(); W = []
    for s in _NETATMO or []:
        lo2, la2 = s['place']['location']
        if math.hypot((la2 - la) * 111, (lo2 - lo) * 72) > km: continue
        for m in s.get('measures', {}).values():
            if 'gust_strength' in m and m.get('wind_timeutc') and jetzt - m['wind_timeutc'] < 3600 and m['gust_strength'] is not None: W.append(m['gust_strength'])
    W.sort()
    if not W: return None, 0, None
    n = len(W); return (W[n // 2] if n % 2 else (W[n // 2 - 1] + W[n // 2]) / 2), n, W[-1]


def boeen_pruefen(orte):
    """Böen-Gegenprobe (22.11.2026): viele WU-Stationen stehen windgeschützt (z. B. IBREUB3). Messen mindestens 2 Netatmo-Windmesser
    im Umkreis 5 km im Mittel (Median) mindestens 30 km/h und 15 km/h mehr als die Station, gilt der Netatmo-Wert (o['g_roh'] = Stationswert)."""
    for o in orte:
        try: gm, n, gx = netatmo_wind(o['lat'], o['lon'])
        except Exception as e: print('Netatmo-Wind nicht möglich:', e); continue
        o['g_netatmo'], o['n_wind'], o['g_netatmo_max'] = (round(gm) if gm is not None else None), n, gx
        if n >= 2 and gm is not None and gm >= 30 and (o.get('g') is None or gm >= (o.get('g') or 0) + 15):
            o['g_roh'] = o.get('g'); o['g'] = round(gm); o['g_ersatz'] = 'Netatmo (%d Windmesser im Umkreis 5 km)' % n
            print('Böen-Gegenprobe: %s meldet %s km/h, Netatmo %s km/h (%d Messer) -> Netatmo' % (o['name'], o['g_roh'], o['g'], n))
    return orte


def regen_pruefen(orte, heute):
    """Unplausible Regenwerte erkennen und ersetzen: o['r_roh'] = gemeldeter Wert, o['r_stoerung'] = True,
    o['r'] = Ersatzwert (o['r_ersatz'] = Quelle) oder None, wenn kein plausibler Ersatz zu bekommen ist."""
    for o in orte:
        andere = [x.get('r') for x in orte if x is not o and not x.get('r_stoerung')]
        if not regen_unplausibel(o.get('r'), andere): continue
        o['r_roh'] = o['r']; o['r_stoerung'] = True; o['r'] = None
        for sid in REGEN_ERSATZ.get(o['name'], []):
            try: v = (wu(sid) or {}).get('r')
            except Exception as e: print('Regen-Ersatz %s nicht abrufbar:' % sid, e); v = None
            if v is not None and not regen_unplausibel(v, andere): o['r'] = v; o['r_ersatz'] = 'Nachbarstation ' + sid; break
        if o['r'] is None:   # 22.11.2026: Netatmo-Regenmesser im Ort (Median) vor DWD
            try: v, n = netatmo_regen(o['lat'], o['lon'])
            except Exception as e: print('Netatmo-Regen nicht möglich:', e); v, n = None, 0
            if v is not None and not regen_unplausibel(v, andere): o['r'] = v; o['r_ersatz'] = 'Netatmo (%d Messer im Ort)' % n
        if o['r'] is None:
            try: v = regen_dwd(o['lat'], o['lon'], heute)
            except Exception as e: print('Regen-Ersatz DWD nicht abrufbar:', e); v = None
            if v is not None and not regen_unplausibel(v, andere): o['r'] = v; o['r_ersatz'] = 'DWD (nächste Station)'
        print('Regen unplausibel: %s meldet %s mm, andere %s -> %s' % (o['name'], o['r_roh'], andere, ('%s mm von %s' % (o['r'], o['r_ersatz'])) if o['r'] is not None else 'kein Ersatz'))
    return orte


def sonnenhoehe(lat, lon, t):
    """Sonnenhöhe in Grad (Näherung, reicht für Tag/Nacht und Klarhimmel-Strahlung)."""
    import math
    u = t.astimezone(dt.timezone.utc); n = u.timetuple().tm_yday; h = u.hour + u.minute / 60
    g = 2 * math.pi / 365 * (n - 1 + (h - 12) / 24)
    dek = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    ha = math.radians((h * 60 + eq + 4 * lon) / 4 - 180)
    la = math.radians(lat)
    return math.degrees(math.asin(math.sin(la) * math.sin(dek) + math.cos(la) * math.cos(dek) * math.cos(ha)))


def wetter_symbol(o, jetzt):
    """Wetterlage je Station aus den Messwerten (16.11.2026): regen, schauer, nass, schnee, nebel, sonne, wolkig, bedeckt, nacht."""
    t, rr, rh, dr = o.get('t'), o.get('rr') or 0, o.get('rh'), o.get('dr30') or 0
    if t is None: return None
    if (rr > 0 or dr > 0) and t <= 1: return 'schnee'
    if rr >= 2.5: return 'regen'
    if rr > 0: return 'schauer'
    if dr > 0: return 'nass'
    if rh is not None and rh >= 97: return 'nebel'
    el = sonnenhoehe(o['lat'], o['lon'], jetzt)
    if el < 0: return 'nacht'
    sol = o.get('sol')
    if sol is None or el < 5: return 'tag'
    klar = 1000 * math.sin(math.radians(el)) * 0.75
    q = sol / klar if klar > 0 else 0
    return 'sonne' if q >= 0.6 else 'wolkig' if q >= 0.3 else 'bedeckt'


def archiv(orte, jetzt):
    """Messwert-Datenbank: jeder 10-Minuten-Wert jeder Station dauerhaft in data/odenwald-archiv/JJJJ-MM.json
    (Format: {station: {zeit: [t, rh, w, g, r]}}), damit nichts verloren geht."""
    d = os.path.join(os.path.dirname(DATEI), 'odenwald-archiv'); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, jetzt.strftime('%Y-%m') + '.json')
    try: A = json.load(open(f, encoding='utf-8'))
    except Exception: A = {}
    for o in orte:
        z = o.get('zeit')
        if not z or z[:7] != jetzt.strftime('%Y-%m') or o.get('t') is None: continue
        A.setdefault(o['name'], {})[z[:16]] = [o.get('t'), o.get('rh'), o.get('w'), o.get('g'), o.get('r')]
    json.dump(A, open(f, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


def main():
    jetzt = dt.datetime.now(TZ); heute = jetzt.date().isoformat()
    try: alt = json.load(open(DATEI, encoding='utf-8'))
    except Exception: alt = {}
    verlauf = alt.get('verlauf') if alt.get('datum') == heute else {}
    verlauf = verlauf or {}
    orte = []
    belegt = set(x[3] for x in ORTE)
    # 18.11.2026 23 Uhr: WU-Schlüssel gedrosselt („API key is throttled“) – Zusatzorte pausiert, bis geklärt ist, wie viele Abrufe gehen
    try: wahl = extra_stationen(jetzt, belegt) if EXTRA_AN else {}
    except Exception as e: print('Zusatzorte nicht möglich:', e); wahl = {}
    liste = [x + (False,) for x in ORTE] + [(n, el, 'wu', wahl[n]['id'], la, lo, True) for n, el, la, lo in EXTRA if n in wahl]
    alt_alle = alt.get('orte', []) + alt.get('extra', [])
    # 22.11.2026, 17:35 Uhr (Kingman): alle Orte im gleichen Takt alle 20 Minuten (:00, :20, :40) statt 10 bzw. 30 Minuten –
    # spart WU-Abfragen (ca. 650 statt 910 am Tag). Eigene Station kostet nichts und wird bei jedem Lauf aktualisiert.
    abruf_jetzt = (jetzt.minute // 10) % 2 == 0 or alt.get('datum') != heute
    for n, el, art, sid, la, lo, ist_extra in liste:
        alt_e = next((o for o in alt.get('orte', []) + alt.get('extra', []) if o['name'] == n), None)
        if sid != 'IBADKN33' and not abruf_jetzt and alt_e and (alt_e.get('station') == sid or not ist_extra) and alt_e.get('zeit') \
           and (jetzt - dt.datetime.fromisoformat(alt_e['zeit'])).total_seconds() < 25 * 60:
            alt_e.setdefault('station', sid); alt_e['reserve'] = reserve_text(n, sid, ist_extra)
            orte.append(alt_e); continue   # alter Wert bleibt bis zum nächsten Abruf
        try: v = wu(sid) if art == 'wu' else dwd(sid, heute)
        except Exception as e: print('Station %s nicht abrufbar:' % n, e); v = None
        if sid in AUSFALL_ERSATZ and (not v or not v.get('zeit') or (jetzt - dt.datetime.fromisoformat(v['zeit'])).total_seconds() > 60 * 60):
            try: ve = wu(AUSFALL_ERSATZ[sid])
            except Exception as e: print('Reserve %s nicht abrufbar:' % AUSFALL_ERSATZ[sid], e); ve = None
            if ve and ve.get('zeit') and (jetzt - dt.datetime.fromisoformat(ve['zeit'])).total_seconds() <= 60 * 60:
                ve['station_ersatz'] = AUSFALL_ERSATZ[sid]; v = ve
                print('%s: %s sendet nicht, Reserve %s eingesprungen' % (n, sid, AUSFALL_ERSATZ[sid]))
        alt_o = next((o for o in alt_alle if o['name'] == n), None) if alt.get('datum') == heute else None
        if not v and alt_o: v = {k: alt_o.get(k) for k in ('t', 'rh', 'w', 'g', 'r', 'rr', 'sol', 'p', 'wd', 'td', 'uv', 'gf', 'zeit')}
        # Regenzuwachs der letzten 30 Minuten (für „nass / gerade aufgehört“)
        phist = [x for x in (alt_o or {}).get('phist', []) if (jetzt - dt.datetime.fromisoformat(x[0])).total_seconds() <= 190 * 60]
        if v and v.get('p') is not None and v.get('zeit') and (not phist or phist[-1][0] != v['zeit']): phist.append([v['zeit'], v['p']])
        rhist = [x for x in (alt_o or {}).get('rhist', []) if (jetzt - dt.datetime.fromisoformat(x[0])).total_seconds() <= 35 * 60]
        if v and v.get('r') is not None and v.get('zeit'): rhist.append([v['zeit'], v['r']])
        dr30 = round(max(0, rhist[-1][1] - rhist[0][1]), 1) if len(rhist) >= 2 else 0
        o = dict(name=n, el=el, lat=la, lon=lo, quelle='eigene Station' if sid == 'IBADKN33' else 'privat (WU)' if art == 'wu' else 'DWD', **(v or {}))
        o['rhist'] = rhist; o['dr30'] = dr30; o['phist'] = phist
        if len(phist) >= 2 and (dt.datetime.fromisoformat(phist[-1][0]) - dt.datetime.fromisoformat(phist[0][0])).total_seconds() >= 150 * 60: o['p3h'] = round(phist[-1][1] - phist[0][1], 1)
        o['wx'] = wetter_symbol(o, jetzt)
        if ist_extra: o['extra'] = True
        o['station'] = sid; o['reserve'] = reserve_text(n, sid, ist_extra)   # 23.11.2026: für „📡 Stationen“ in der Zentrale
        orte.append(o)
        if v and v.get('t') is not None and (v.get('zeit') or '')[:10] == heute:
            L = verlauf.setdefault(n, []); hm = v['zeit'][11:16]
            if not L or L[-1][0] != hm: L.append([hm, v['t']])
    for o in orte:   # 22.11.2026: Netatmo-Gegenprobe Regen je Ort (nur gespeichert, Ersatz siehe regen_pruefen)
        try: o['r_netatmo'], o['n_netatmo'] = netatmo_regen(o['lat'], o['lon'])
        except Exception: pass
    try: boeen_pruefen(orte)
    except Exception as e: print('Böen-Prüfung nicht möglich:', e)
    try: regen_pruefen(orte, heute)   # vor dem Archiv: dort landet der geprüfte Wert (17.11.2026)
    except Exception as e: print('Regen-Prüfung nicht möglich:', e)
    archiv(orte, jetzt)
    try:
        A = archiv_lesen(jetzt)
        for o in orte: vergleich(o, A, jetzt)
    except Exception as e: print('Vergleich nicht möglich:', e)
    # die Zusatzorte stehen getrennt unter „extra“, damit die jetzige Seite unverändert bleibt (Vorschau zuerst)
    json.dump(dict(stand=jetzt.isoformat(timespec='minutes'), datum=heute, orte=[o for o in orte if not o.get('extra')],
                   extra=[o for o in orte if o.get('extra')], verlauf=verlauf),
              open(DATEI, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('Odenwald live:', [(o['name'], o.get('t')) for o in orte])
    try: stationen_alarm(orte, jetzt)
    except Exception as e: print('Stations-Alarm nicht möglich:', e)


if __name__ == '__main__':
    main()
