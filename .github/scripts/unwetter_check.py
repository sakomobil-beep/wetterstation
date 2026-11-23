#!/usr/bin/env python3
"""Unwetter-Check (Viertelstunden-Lauf, rund um die Uhr, seit 15.11.2026):
- DWD-Stufe 3/4 (Unwetter/extrem), neu: neu=1 -> Ablauf baut sofort das Special mit Max + Story, beides wird gepostet.
- DWD-Stufe 2 (markantes Wetter), neu: Story-Bild fb/warn2-story.jpg + warn2.json, wird als Story gepostet.
- Stufe 1: nichts.
Gemeldet wird nur eine neue Warnart oder eine echte Hochstufung – gemerkt je Art.

Seit 18.11.2026 (Ablauf dwd-warnung.yml, angestoßen vom Cloudflare-Worker):
- Das Gedächtnis steht in fb/gepostet.json unter „uw_merk“ (wird mit dem Merkzettel gesichert, gegen Doppelposts).
- Eine Warnung gilt erst als erledigt, wenn sie wirklich gepostet ist (fb_senden.py trägt sie dann ein). Bis dahin
  wird es bei jedem Lauf erneut versucht – solange die Warnung gilt, bis 30 Minuten vor ihrem Ende.
- Ist ein schon gebautes Bild (warn2.json / uw3.json) noch nicht fertig gepostet und betrifft dieselben Warnungen,
  wird es nicht neu gebaut – so wird nur die fehlende Plattform nachgeholt, nie doppelt gepostet.
- Stufe 3/4: zuerst das Story-Bild (fb/special-story.jpg + uw3.json, sofort gepostet), das Video mit Max danach."""
import json, os, sys, datetime as dt
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
import kreis

TZ = ZoneInfo('Europe/Berlin')
FB = os.path.join(os.path.dirname(__file__), '..', '..', 'fb')
MERK = os.path.join(FB, 'uw_gemeldet.json')   # bis 18.11.2026 – wird nur noch als Startwert gelesen
GEP = os.path.join(FB, 'gepostet.json')
VORLAUF = dt.timedelta(minutes=30)   # Warnungen, die in weniger als 30 Minuten enden, werden nicht mehr gepostet


def merk_laden():
    try: G = json.load(open(GEP, encoding='utf-8'))
    except Exception: G = {}
    if isinstance(G.get('uw_merk'), dict): return G['uw_merk']
    try: return json.load(open(MERK, encoding='utf-8'))
    except Exception: return {}


def offen_behalten(datei, warn, jetzt):
    """True, wenn fb/<datei> dieselben Warnungen enthält, jünger als 3 h ist und noch nicht fertig gepostet wurde."""
    try:
        j = json.load(open(os.path.join(FB, datei), encoding='utf-8'))
        G = json.load(open(GEP, encoding='utf-8'))
    except Exception: return False
    fertig = G.get('warn2_erstellt' if datei == 'warn2.json' else 'uw3_erstellt') == j.get('erstellt')
    try: alt = (jetzt - dt.datetime.fromisoformat(j['erstellt'])).total_seconds()
    except Exception: return False
    return not fertig and alt < 3 * 3600 and sorted(j.get('warn') or []) == sorted(warn)


def ausgabe(neu, story2=False):
    p = os.environ.get('GITHUB_OUTPUT')
    if p: open(p, 'a').write('neu=%s\nstory2=%s\n' % ('1' if neu else '0', '1' if story2 else '0'))


ARTEN = [('wind', ('WIND', 'STURM', 'ORKAN', 'BÖEN', 'BOEEN')), ('gewitter', ('GEWITTER',)), ('schnee', ('SCHNEE',)),
         ('glaette', ('GLÄTTE', 'GLATTEIS', 'FROST', 'REIF')), ('regen', ('REGEN', 'TAUWETTER')), ('hitze', ('HITZE', 'UV')), ('nebel', ('NEBEL',))]


def art(t):
    """Warnart (Familie), damit z. B. Windböen → Sturmböen → Orkanböen als dieselbe Art zählen."""
    T = (t or '').upper()
    return next((n for n, ws in ARTEN if any(x in T for x in ws)), T[:40])


def main():
    jetzt = dt.datetime.now(TZ)
    nur_bild = '--bild' in sys.argv   # nur Bild + Text zur aktuellen Stufe-2-Warnung bauen, nichts merken, nichts posten
    try: alle = kreis.warnungen()
    except Exception as e: print('Warnungen nicht abrufbar:', e); return ausgabe(False)
    M = merk_laden()
    # Gedächtnis je Warnart (seit 15.11.2026): {art: {"stufe": n, "bis": Ende der Warnung}} – gepostet wird nur bei
    # einer neuen Warnart oder einer echten Hochstufung; geänderte Uhrzeiten/Orte oder Herabstufungen lösen nichts aus.
    M = {k: v for k, v in M.items() if isinstance(v, dict) and v.get('bis', '') >= jetzt.isoformat()}
    neu3, neu2, info2, info3, merk2, merk3, st3 = [], [], {}, {}, {}, {}, 3
    for a in sorted(alle, key=lambda a: -{'moderate': 2, 'severe': 3, 'extreme': 4}.get(a.get('severity'), 1)):
        st = {'moderate': 2, 'severe': 3, 'extreme': 4}.get(a.get('severity'), 1)
        if st < 2: continue
        w = a.get('headline_de') or a.get('event_de')
        if a.get('gebiet') and a['gebiet'] != 'ganzer Odenwaldkreis': w += ' für ' + a['gebiet']
        k = art(a.get('event_de') or w)
        bis = a.get('expires') or (jetzt + dt.timedelta(hours=24)).isoformat()
        try:
            bis_dt = dt.datetime.fromisoformat(bis.replace('Z', '+00:00')).astimezone(TZ); bis = bis_dt.isoformat()
            if bis_dt - VORLAUF < jetzt and not nur_bild: print('Endet bald – nicht mehr posten:', w); continue
        except Exception: pass
        alt = M.get(k)
        if alt and alt.get('stufe', 0) >= st and not nur_bild:
            if bis > alt.get('bis', ''): alt['bis'] = bis   # gleiche Warnart, gleiche/niedrigere Stufe: nur verlängern
            continue
        inf = dict(von=a.get('onset'), bis=a.get('expires'), text=a.get('description_de') or '', rat=a.get('instruction_de') or '', gebiet=a.get('gebiet') or '')
        if st >= 3:
            if w not in neu3: neu3.append(w); info3[w] = inf
            merk3[k] = {'stufe': st, 'bis': bis}; st3 = max(st3, st)
        elif w not in neu2:
            neu2.append(w); info2[w] = inf; merk2[k] = {'stufe': st, 'bis': bis}
    story2 = False
    if neu2 and not nur_bild and offen_behalten('warn2.json', neu2, jetzt):
        print('Stufe-2-Bild ist schon gebaut, aber noch nicht fertig gepostet – wird nachgeholt.'); story2 = True; neu2 = []
    if neu2:
        try:
            import uw_story
            vor = 'warn2-hand' if nur_bild else 'warn2'   # --bild: eigene Dateien, damit nichts automatisch gepostet wird
            uw_story.bauen(neu2, info2, 2, jetzt.date(), os.path.join(FB, vor + '-story.jpg'))
            uw_story.feed(os.path.join(FB, vor + '-story.jpg'), os.path.join(FB, vor + '-post.jpg'), 2)   # Beitragsbild (15.11.2026)
            json.dump({'erstellt': jetzt.isoformat(timespec='minutes'), 'warn': neu2, 'merk': merk2, 'text': uw_story.text(neu2, info2, 2, jetzt.date())},
                      open(os.path.join(FB, vor + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
            story2 = True
        except Exception as e: print('Stufe-2-Story nicht gebaut:', e)
    if nur_bild: print('Nur Bild gebaut:', neu2); return
    if neu3 and offen_behalten('uw3.json', neu3, jetzt):
        print('Unwetter-Story ist schon gebaut, aber noch nicht fertig gepostet – wird nachgeholt.'); neu3 = []
    elif neu3:   # Stufe 3/4: Story-Bild sofort, damit die Warnung vor dem Video draußen ist (18.11.2026)
        try:
            import uw_story
            uw_story.bauen(neu3, info3, st3, jetzt.date(), os.path.join(FB, 'special-story.jpg'))
            json.dump({'erstellt': jetzt.isoformat(timespec='minutes'), 'warn': neu3, 'stufe': st3, 'merk': merk3},
                      open(os.path.join(FB, 'uw3.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        except Exception as e: print('Unwetter-Story nicht gebaut:', e)
    print('Neu Stufe 3/4:', neu3, '| neu Stufe 2:', neu2)
    ausgabe(bool(neu3), story2)


if __name__ == '__main__':
    main()
