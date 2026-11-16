"""Gemeinden des Odenwaldkreises und amtliche DWD-Warnungen für den ganzen Kreis (über Bright Sky).
Wird von fb_post.py (Beiträge/Max) und sonder.py (Sondermeldungen) genutzt; die Website fragt dieselben Orte ab."""
import json, urllib.request

GEMEINDEN = [   # (Name, Breite, Länge) – Ortsmitte bzw. Hauptort
    ('Bad König', 49.741, 9.008), ('Breuberg', 49.823, 9.046), ('Brensbach', 49.773, 8.884),
    ('Brombachtal', 49.733, 8.945), ('Erbach', 49.657, 8.994), ('Fränkisch-Crumbach', 49.746, 8.858),
    ('Höchst', 49.799, 8.995), ('Lützelbach', 49.786, 9.075), ('Michelstadt', 49.678, 9.004),
    ('Mossautal', 49.660, 8.930), ('Oberzent', 49.567, 8.976), ('Reichelsheim', 49.713, 8.838)]


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de'}), timeout=30) as r:
        return json.loads(r.read().decode())


def warnungen(get=None):
    """Alle aktuellen DWD-Warnungen im Kreis, doppelte zusammengefasst. Jede Warnung bekommt 'orte' (Gemeinden)
    und 'gebiet' (Text: „ganzer Kreis“ oder die Gemeinden). Wirft nur, wenn keine einzige Abfrage klappt."""
    get = get or _get
    alle, ok = {}, 0
    for name, la, lo in GEMEINDEN:
        try:
            j = get('https://api.brightsky.dev/alerts?lat=%s&lon=%s&tz=Europe/Berlin' % (la, lo)); ok += 1
        except Exception as e:
            print('Warnungen %s nicht abrufbar: %s' % (name, e)); continue
        for a in j.get('alerts') or []:
            k = (a.get('event_de'), a.get('headline_de'), a.get('severity'), a.get('onset'), a.get('expires'))
            if k not in alle: alle[k] = dict(a, orte=[])
            if name not in alle[k]['orte']: alle[k]['orte'].append(name)
    if not ok: raise RuntimeError('keine Warnabfrage erfolgreich')
    for a in alle.values():
        a['gebiet'] = 'ganzer Odenwaldkreis' if len(a['orte']) >= len(GEMEINDEN) - 1 else ', '.join(a['orte'])
    return list(alle.values())
