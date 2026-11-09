"""Termin für Max hinzufügen/löschen (aufgerufen vom Formular in der Zentrale über den Workflow 'Termine für Max')."""
import json, os, re, sys, datetime as dt
D = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'termine.json')
T = json.load(open(D, encoding='utf-8'))
e = os.environ
if e.get('AKTION') == 'loeschen':
    T['termine'] = [t for t in T['termine'] if t.get('id') != e.get('TID')]
else:
    von, bis = e['VON'], e.get('BIS') or e['VON']
    dt.date.fromisoformat(von); dt.date.fromisoformat(bis)
    name, ort = e['NAME'].strip()[:80], (e.get('ORT') or '').strip()[:100]
    tid = re.sub(r'[^a-z0-9]+', '-', (name + '-' + von).lower()).strip('-')
    t = {'id': tid, 'name': name, 'ort': ort or 'im Odenwald', 'von': von, 'bis': bis, 'zeit': (e.get('ZEIT') or '').strip()[:40],
         'info': (e.get('INFO') or '').strip()[:80], 'quelle': 'Zentrale'}
    wt = (e.get('WOCHENTAGE') or '').strip()
    if wt: t['wochentage'] = [int(x) for x in wt.split(',') if x.strip().isdigit()]
    T['termine'] = [x for x in T['termine'] if x.get('id') != tid] + [t]
heute = dt.date.today().isoformat()
T['termine'] = sorted([t for t in T['termine'] if (t.get('bis') or max(t.get('daten', {'0': 0}))) >= heute], key=lambda t: t.get('von') or min(t.get('daten', {'9': 0})))
json.dump(T, open(D, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('Termine:', len(T['termine']))
