#!/usr/bin/env python3
"""Einheitliche Wiedergabe der DWD-Warnungen für den Odenwaldkreis (17.11.2026, Kingmans Regel) – für Max' Videos
und die Zeilen „🚨 DWD: …“ in den Beitragstexten:
 1. Gleiche Warnart nur einmal (Kreis + einzelner Ort = einmal, ohne Ort).
 2. „Amtliche Warnung“ nur einmal im Satz – mehrere Arten werden zusammengezogen.
 3. Die stärkere Warnung schluckt die schwächere derselben Sorte (Sturmböen statt Windböen), wenn sie deren Gebiet abdeckt.
 4. Ein Ort wird nur genannt, wenn die Warnung wirklich nur dort gilt; bei mehreren Orten „für Teile des Odenwaldkreises“.
Eingaben wie in fb/daten.json: warn (Liste der DWD-Überschriften), warn_stufe {Überschrift: 1–4}, warn_info {Überschrift: {gebiet, …}}."""
import re

GANZ = 'ganzer Odenwaldkreis'
KLEIN = {'mit', 'und', 'oder', 'in', 'im', 'auf', 'vor', 'bei', 'oberhalb', 'unterhalb', 'verbreitet', 'örtlich', 'gebietsweise',
         'schweren', 'schwerem', 'schwerer', 'starkem', 'starken', 'starker', 'leichtem', 'leichten', 'leichter', 'ergiebigem', 'ergiebigen',
         'heftigem', 'heftigen', 'extrem', 'extremem', 'extremen', 'orkanartigen', 'strengem', 'strengen', 'mäßigem', 'mäßigen', 'markantem',
         'markanten', 'geringer', 'geringem', 'gefrierendem', 'überfrierender', 'anhaltendem', 'ergiebiger', 'starke', 'schwere'}
SORTEN = [('gewitter', ('GEWITTER',)), ('wind', ('BÖEN', 'STURM', 'ORKAN')), ('dauerregen', ('DAUERREGEN',)), ('starkregen', ('STARKREGEN',)),
          ('schneeverwehung', ('VERWEHUNG',)), ('schnee', ('SCHNEE',)), ('glaette', ('GLÄTTE', 'GLATTEIS')), ('frost', ('FROST',)),
          ('nebel', ('NEBEL',)), ('tauwetter', ('TAUWETTER',)), ('hitze', ('HITZE',))]


def _name(ereignis):
    w = [x for x in ereignis.split() if x]
    return ' '.join((x.lower() if x.lower() in KLEIN else x.capitalize() if x.isupper() else x) for x in w)


def _sorte(ereignis):
    e = ereignis.upper()
    for s, keys in SORTEN:
        if any(k in e for k in keys): return s
    return e


def gruppen(warn, stufe=None, info=None):
    """Fasst die Warnungen zusammen. Ergebnis: Liste von dict(name, stufe, orte) – orte=None heißt ganzer Kreis –,
    stärkste zuerst. Überschriften, die sich nicht zerlegen lassen, bleiben unverändert (name=None, roh=…)."""
    stufe, info = stufe or {}, info or {}
    G, rest = {}, []
    for w in warn or []:
        m = re.match(r'^.*?\bvor\s+(.+?)(?:\s+für\s+(.+))?$', w.strip())
        if not m: rest.append(dict(name=None, roh=w, stufe=stufe.get(w, 1), orte=None, sorte=w)); continue
        ev = m.group(1).strip()
        geb = ((info.get(w) or {}).get('gebiet') or m.group(2) or GANZ).strip()
        orte = None if geb == GANZ else [o.strip() for o in geb.split(',') if o.strip()]
        g = G.setdefault(ev.upper(), dict(name=_name(ev), stufe=0, orte=[], sorte=_sorte(ev)))
        g['stufe'] = max(g['stufe'], stufe.get(w, 3 if 'UNWETTER' in w.upper() else 1))
        if orte is None or g['orte'] is None: g['orte'] = None                      # Regel 1: gilt irgendwo kreisweit -> ganzer Kreis
        else: g['orte'] = g['orte'] + [o for o in orte if o not in g['orte']]
    L = list(G.values())

    def deckt(stark, schwach):                                                      # Regel 3: stärker, gleiche Sorte, Gebiet abgedeckt
        if stark is schwach or stark['sorte'] != schwach['sorte'] or stark['stufe'] <= schwach['stufe']: return False
        return stark['orte'] is None or (schwach['orte'] is not None and set(schwach['orte']) <= set(stark['orte']))
    L = [g for g in L if not any(deckt(h, g) for h in L)]
    return sorted(L, key=lambda g: -g['stufe']) + rest


def _mit_ort(g):
    if g['orte'] is None: return g['name']
    return g['name'] + (' für ' + g['orte'][0] if len(g['orte']) == 1 else ' für Teile des Odenwaldkreises')   # Regel 4


def _reihe(teile):
    return teile[0] if len(teile) == 1 else ', '.join(teile[:-1]) + ' und ' + teile[-1]


def satz(warn, stufe=None, info=None, hoechstens=3):
    """Für Max: „eine amtliche Warnung vor Sturmböen“ bzw. „amtliche Warnungen vor Sturmböen und Dauerregen“ (Regel 2).
    Unwetterwarnungen (ab Stufe 3) stehen vorn und heißen auch so."""
    G = gruppen(warn, stufe, info)
    klar = [g for g in G if g['name']][:hoechstens]
    teile = []
    for unwetter in (True, False):
        k = [g for g in klar if (g['stufe'] >= 3) == unwetter]
        if not k: continue
        wort = 'Unwetterwarnung' if unwetter else 'Warnung'
        teile.append(('eine amtliche %s vor ' % wort if len(k) == 1 else 'amtliche %sen vor ' % wort) + _reihe([_mit_ort(g) for g in k]))
    for g in [g for g in G if not g['name']][:max(0, hoechstens - len(klar))]:
        r = g['roh']; teile.append(('eine ' + r[0].lower() + r[1:]) if r.lower().startswith('amtliche') else r)
    return ' sowie '.join(teile)


def mehrzahl(text):
    """True, wenn satz() mehrere Warnungen nennt („gelten“ statt „gilt“)."""
    return not text.startswith('eine ') or ' sowie ' in text


def zeilen(warn, stufe=None, info=None, hoechstens=3):
    """Für Beitragstexte: je Warnart eine Zeile, z. B. „Amtliche Warnung vor Sturmböen“ oder „… vor Windböen für Breuberg“."""
    out = []
    for g in gruppen(warn, stufe, info)[:hoechstens]:
        out.append(g['roh'] if not g['name'] else 'Amtliche %s vor %s' % ('Unwetterwarnung' if g['stufe'] >= 3 else 'Warnung', _mit_ort(g)))
    return out
