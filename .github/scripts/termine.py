"""Regionale Termine für Max: Feiertage Hessen (berechnet), Schulferien Hessen und Veranstaltungen aus data/termine.json."""
import json, os, datetime as dt

DATEI = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'termine.json')
TAGE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']


def ostern(j):
    a, b, c = j % 19, j // 100, j % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31
    return dt.date(j, mo, (h + l - 7 * m + 114) % 31 + 1)


def feiertage(j):
    o = ostern(j); t = dt.timedelta
    return {dt.date(j, 1, 1): 'Neujahr', o - t(2): 'Karfreitag', o + t(1): 'Ostermontag', dt.date(j, 5, 1): 'Tag der Arbeit',
            o + t(39): 'Christi Himmelfahrt', o + t(50): 'Pfingstmontag', o + t(60): 'Fronleichnam',
            dt.date(j, 10, 3): 'Tag der Deutschen Einheit', dt.date(j, 12, 25): 'der erste Weihnachtsfeiertag', dt.date(j, 12, 26): 'der zweite Weihnachtsfeiertag'}


def laden():
    try: return json.load(open(DATEI, encoding='utf-8'))
    except Exception: return {'ferien': [], 'termine': []}


def offen(t, tag):
    """Hat der Termin an diesem Tag geöffnet? Gibt die Uhrzeit (oder '') zurück, sonst None."""
    k = tag.isoformat()
    if t.get('daten'): return t['daten'].get(k)
    if t.get('von', '9') <= k <= t.get('bis', '0') and (not t.get('wochentage') or tag.weekday() in t['wochentage']): return t.get('zeit') or ''
    return None


def datum_txt(d): return '%s, %d. %s' % (TAGE[d.weekday()], d.day, MONATE[d.month - 1])


def max_hinweis(heute, rnd):
    """Höchstens EIN Hinweis fürs Morgenvideo: Feiertag > Ferien > Veranstaltung."""
    F = feiertage(heute.year); F.update(feiertage(heute.year + 1))
    morgen = heute + dt.timedelta(days=1)
    if heute in F: return rnd.choice(['Heute ist %s – genießt den freien Tag!', 'Und nicht vergessen: Heute ist %s, also raus in den Odenwald!']) % F[heute]
    if morgen in F: return rnd.choice(['Morgen ist übrigens %s – ein freier Tag.', 'Vormerken: Morgen ist %s.']) % F[morgen]
    D = laden()
    for f in D.get('ferien', []):
        v, b = dt.date.fromisoformat(f['von']), dt.date.fromisoformat(f['bis'])
        vor = (v - heute).days
        if vor in (0, 1) or (heute.weekday() == 4 and 1 <= vor <= 3):
            wann = 'heute' if vor == 0 else 'morgen' if vor == 1 else 'ab Montag'
            return rnd.choice(['Für alle Schulkinder: %s beginnen die %s in Hessen!', 'Endlich: %s starten in Hessen die %s.']) % (wann, f['name'])
        if b == heute:
            return 'Für alle Schulkinder: Heute ist der letzte Ferientag – danach geht in Hessen die Schule wieder los.'
    beste, heute_offen = None, []
    for t in D.get('termine', []):
        z = offen(t, heute)
        if z is not None: heute_offen.append((t, z)); continue
        for n in (1, 2, 3):   # erster Öffnungstag in 1–3 Tagen ankündigen
            tag = heute + dt.timedelta(days=n)
            if offen(t, tag) is not None and not any(offen(t, heute - dt.timedelta(days=m)) is not None for m in range(0, 8)):
                cand = (n, 'Schon mal vormerken: %s öffnet der %s, %s%s.' % ('morgen' if n == 1 else 'am ' + datum_txt(tag), t['name'], t['ort'],
                                                                                 (' – ' + t['info']) if t.get('info') else ''))
                if not beste or cand[0] < beste[0]: beste = cand
                break
    if beste and beste[0] == 1: return beste[1]   # Eröffnung morgen hat Vorrang
    if heute_offen:
        eigene = [x for x in heute_offen if x[0].get('daten')]   # Termine mit festen Tagen (z. B. Nikolausmarkt) zuerst
        t, z = (eigene or [rnd.choice(heute_offen)])[0]
        return rnd.choice(['Heute hat der %s geöffnet, %s%s.', 'Tipp für heute: der %s, %s%s.']) % (t['name'], t['ort'], (' – ' + z) if z else '')
    return beste[1] if beste else ''


def woche_liste(montag):
    """Für den Wochenausblick (Montag bis Sonntag): Feiertage, Ferien und Veranstaltungen der Woche."""
    out, D = [], laden(); F = feiertage(montag.year); F.update(feiertage(montag.year + 1))
    tage = [montag + dt.timedelta(days=i) for i in range(7)]
    for d in tage:
        if d in F: out.append('%s ist %s' % (TAGE[d.weekday()], F[d]))
    for f in D.get('ferien', []):
        v = dt.date.fromisoformat(f['von'])
        if v in tage: out.append('am %s beginnen die %s' % (TAGE[v.weekday()], f['name']))
    for t in D.get('termine', []):
        auf = [d for d in tage if offen(t, d) is not None]
        if auf: out.append('%s hat %s geöffnet' % (t['name'], ('am ' + TAGE[auf[0].weekday()]) if len(auf) == 1 else 'von %s bis %s' % (TAGE[auf[0].weekday()], TAGE[auf[-1].weekday()])))
    return out[:3]
