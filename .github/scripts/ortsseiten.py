#!/usr/bin/env python3
"""Ortsseiten „Wetter <Ort> – live gemessen“ (22.11.2026, Entwurf B mit Himmel-Kopf von Kingman freigegeben).
Schreibt je Ort eine statische HTML-Seite mit den aktuellen Messwerten direkt im HTML (für Google),
dazu ein kleines Skript, das die Werte im Browser alle paar Minuten aus data/odenwald-live.json auffrischt.
Aufruf: python ortsseiten.py <Zielordner> [Ort …]   (ohne Ort: alle)"""
import json, os, sys, html, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
BASIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
SITE = 'https://wetter-badkoenig.de/'
SLUG = {'Michelstadt': 'michelstadt', 'Höchst i. Odw.': 'hoechst', 'Breuberg': 'breuberg', 'Mossautal': 'mossautal', 'Oberzent': 'oberzent',
        'Reichelsheim': 'reichelsheim', 'Brombachtal': 'brombachtal', 'Lützelbach': 'luetzelbach'}
KURZ = {'Höchst i. Odw.': 'Höchst'}
VORH = {'Höchst i. Odw.': 'Höchst'}   # Name in fb/daten.json „orte“
WORT = {0: 'klar', 1: 'heiter', 2: 'wolkig', 3: 'bedeckt', 45: 'neblig', 48: 'neblig mit Reif', 51: 'Nieselregen', 53: 'Nieselregen', 55: 'Nieselregen',
        61: 'Regen', 63: 'Regen', 65: 'kräftiger Regen', 71: 'Schnee', 73: 'Schnee', 75: 'kräftiger Schnee', 80: 'Schauer', 81: 'Schauer', 82: 'kräftige Schauer',
        85: 'Schneeschauer', 86: 'Schneeschauer', 95: 'Gewitter', 96: 'Gewitter', 99: 'Gewitter'}


def k(v, n=1):
    if v is None: return '–'
    s = ('%.*f' % (n, v)).replace('.', ',')
    return s.replace('-', '−')


KOPF = ''
def himmel_klasse():
    n = dt.datetime.now(TZ); h = n.hour + n.minute / 60; m = n.month - 1
    auf = [8, 7.5, 6.7, 6.6, 5.8, 5.3, 5.5, 6.1, 6.9, 7.6, 7.5, 8.2][m]; unt = [16.9, 17.7, 18.5, 20.3, 21, 21.5, 21.4, 20.7, 19.6, 18.5, 16.7, 16.4][m]
    return 'nacht' if h < auf - 0.6 or h > unt + 0.6 else 'daemmer' if h < auf + 0.6 or h > unt - 0.6 else 'tag'


def seo_jetzt(alle):
    """Startseite: ein Satz mit den echten Werten von Bad König direkt im HTML (für Google), höchstens einmal pro Stunde neu."""
    import re
    o = next((x for x in alle if x['name'] == 'Bad König'), None)
    if not o or o.get('t') is None: return
    p = os.path.join(BASIS, 'index.html'); t = open(p, encoding='utf-8').read()
    m = re.search(r'(<!-- SEO-JETZT ANFANG -->)(.*?)(<!-- SEO-JETZT ENDE -->)', t, re.S)
    if not m: return
    std = dt.datetime.now(TZ).strftime('%d.%m.%Y %H')
    if 'data-std="%s"' % std in m.group(2): return
    wind = 'windstill' if not o.get('w') and not o.get('g') else 'Wind %s km/h, Böen %s km/h' % (k(o.get('w'), 0), k(o.get('g'), 0))
    satz = '<p class="foot" id="seoJetzt" data-std="%s">Aktuell in Bad König (eigene Station, %s Uhr): %s °C, %s %% Luftfeuchte, %s, Luftdruck %s hPa, Regen heute %s l/m².</p>' % (
        std, (o.get('zeit') or '')[11:16], k(o.get('t')), k(o.get('rh'), 0), wind, k(o.get('p'), 0), k(o.get('r')))
    t = t[:m.start()] + m.group(1) + satz + m.group(3) + t[m.end():]
    open(p, 'w', encoding='utf-8').write(t); print('Startseite: Jetzt-Satz aktualisiert')


def _kopf():
    try:
        import re
        t = open(os.path.join(BASIS, 'index.html'), encoding='utf-8').read()
        svg = re.search(r'<svg class="brandlogo".*?</svg>', t, re.S).group(0)
    except Exception: svg = '<b>Private Wetterstation Bad König</b>'
    nav = ''.join('<a href="%s%s"%s>%s</a>' % (SITE, h, ' class="on"' if n == 'Aktuell Odenwald' else '', n) for h, n in
                  (('', 'Aktuell Bad König'), ('#odenwald', 'Aktuell Odenwald'), ('#vorhersage', 'Vorhersage'), ('#historie', 'Historie'), ('#statistik', 'Statistik'), ('#video', 'Videos')))
    return '<div class="logo"><a href="%s" aria-label="Startseite">%s</a></div><nav class="nav">%s</nav>' % (SITE, svg, nav)


def max_satz(name, vh, nied):
    """Kurzer Satz aus Ortsvorhersage + gemeinsamer Einstufung (gleiche Grundlage wie Max)."""
    if not vh: return ''
    h, m = vh[0], vh[1] if len(vh) > 1 else None
    t = []
    jetzt = dt.datetime.now(TZ)
    if m and jetzt.hour >= 17:
        if m['tmin_kalt'] <= 0: t.append('In %s wird es heute Nacht frostig, bis %s Grad.' % (name, k(m['tmin_kalt'], 0)))
        else: t.append('Heute Nacht sinken die Werte in %s auf etwa %s Grad.' % (name, k(m['tmin'], 0)))
        t.append('Morgen %s bei %s Grad.' % (WORT.get(m['code'], 'wechselhaft'), k(m['tmax'], 0)))
    else:
        t.append('Heute in %s %s, bis %s Grad.' % (name, WORT.get(h['code'], 'wechselhaft'), k(h['tmax'], 0)))
        if nied and nied.get('stufe') in ('schauer', 'regen', 'gewitter'): t.append('Regenschirm einpacken.')
    return ' '.join(t)


def seite(o, alle, vh, nied, stand, stil='himmel'):
    n = o['name']; kn = KURZ.get(n, n); slug = SLUG[n]
    zeit = (o.get('zeit') or '')[11:16]
    wind = 'windstill' if not o.get('w') and not o.get('g') else '%s km/h, Böen %s' % (k(o.get('w'), 0), k(o.get('g'), 0))
    desc = 'Aktuell in %s: %s °C, %s %% Luftfeuchte, %s (%s Uhr). Echte Messwerte aus %s im Odenwald, Vorhersage für heute und morgen, Regen der letzten Tage.' % (
        kn, k(o.get('t')), k(o.get('rh'), 0), wind, zeit, kn)
    vt = ''
    if vh:
        def tag(i, was):
            d = vh[i]; return '<div class="box"><small>%s</small><b>%s, %s °C</b><span>Nacht bis %s °C</span></div>' % (was, WORT.get(d['code'], 'wechselhaft'), k(d['tmax'], 0), k(d['tmin_kalt'], 0))
        vt = '<div class="zwei">' + tag(0, 'Heute') + (tag(1, 'Morgen') if len(vh) > 1 else '') + '</div>'
    ms = max_satz(kn, vh, nied)
    andere = ' · '.join('<a href="%s.html">%s</a>' % (SLUG[x['name']], KURZ.get(x['name'], x['name'])) for x in alle if x['name'] in SLUG and x['name'] != n)
    ld = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': 'Wetter %s live' % kn, 'description': desc, 'url': SITE + slug + '.html',
          'about': {'@type': 'Place', 'name': kn, 'geo': {'@type': 'GeoCoordinates', 'latitude': o['lat'], 'longitude': o['lon'], 'elevation': o['el']}},
          'isPartOf': {'@type': 'WebSite', 'name': 'Private Wetterstation Bad König', 'url': SITE}}
    e = html.escape
    return f'''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wetter {e(kn)} live – gemessen, nicht geschätzt | Private Wetterstation Bad König</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}{slug}.html">
<meta property="og:title" content="Wetter {e(kn)} live – gemessen im Odenwald">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}{slug}.html">
<meta property="og:image" content="{SITE}vorschau.jpg">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>
:root{{--bg:#EAF0F3;--surface:#fff;--ink:#12252E;--muted:#56707C;--line:#D6E0E5;--accent:#1A6BA6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}}
.kopf{{background:linear-gradient(180deg,#2f6fb0 0%,#7fb3e0 70%,#cfe3f3 100%);color:#fff;padding:18px 16px 70px}}
.kopf .in{{max-width:900px;margin:0 auto}}.kopf a{{color:#fff;text-decoration:none;opacity:.9}}.brot{{font-size:13px}}
h1{{margin:10px 0 2px;font-size:clamp(1.7rem,4.5vw,2.4rem);line-height:1.15}}.unter{{opacity:.9;font-size:14px}}
.wrap{{max-width:900px;margin:-50px auto 0;padding:0 16px 40px;display:grid;gap:14px}}
.card{{background:var(--surface);border-radius:16px;padding:18px 20px}}
.werte{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}
.werte div{{background:#f3f7fa;border-radius:12px;padding:10px 12px}}.werte small,.box small{{display:block;color:var(--muted);font-size:12px}}
.werte b{{font-size:22px;font-weight:600}}.werte .gross b{{font-size:32px}}.werte span{{display:block;font-size:12px;color:var(--muted)}}
.max{{border-left:4px solid var(--accent);padding:6px 12px;display:flex;gap:12px;align-items:center}}.max img{{width:48px;height:48px;border-radius:50%}}
.zwei{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.box{{border:1px solid var(--line);border-radius:12px;padding:10px 12px}}.box b{{display:block}}.box span{{font-size:13px;color:var(--muted)}}
.regen{{display:flex;gap:18px;flex-wrap:wrap;font-size:14px;color:var(--muted)}}
a{{color:var(--accent)}}.links{{font-size:14px;color:var(--muted)}}.fuss{{font-size:13px;color:var(--muted);text-align:center}}
html .himmel{{padding-top:14px}}.himmel.nacht{{background:linear-gradient(180deg,#0b1a33 0%,#1d3f6e 55%,#3d6fa3 100%)}}.himmel.tag{{background:linear-gradient(180deg,#2f6fb0 0%,#5f9fd6 60%,#a9cdec 100%)}}.himmel.daemmer{{background:linear-gradient(180deg,#27315f 0%,#8a5c86 55%,#f0a46c 100%)}}
.logo{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}.logo svg{{height:84px;width:auto}}.bl-sub{{fill:#f59e0b}}.bl-main{{fill:#fff}}
.nav{{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0 8px;padding:6px;border-radius:12px;background:rgba(255,255,255,.12)}}.nav a{{font-size:14px;padding:4px 10px;border-radius:8px;opacity:1}}.nav a.on{{background:#f59e0b;color:#1b1b1b}}
@media(max-width:640px){{.werte{{grid-template-columns:1fr 1fr}}.zwei{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header id="kopf" class="kopf{(' himmel ' + himmel_klasse()) if stil == 'himmel' else ''}"><div class="in">
{KOPF if stil == 'himmel' else ''}
<div class="brot"><a href="{SITE}">Private Wetterstation Bad König</a> › <a href="{SITE}#odenwald">Odenwald</a> › {e(kn)}</div>
<h1>Wetter {e(kn)} – live gemessen</h1>
<div class="unter">Messwerte einer privaten Wetterstation in {e(kn)} ({o['el']} m), alle 20 Minuten neu · Stand <span id="zeit">{zeit}</span> Uhr</div>
</div></header>
<main class="wrap">
<section class="card"><div class="werte">
<div class="gross"><small>Jetzt</small><b id="t">{k(o.get('t'))} °C</b><span>{('gestern ' + k(o.get('t_gestern')) + ' °C um diese Zeit') if o.get('t_gestern') is not None else ''}</span></div>
<div><small>Luftfeuchte</small><b id="rh">{k(o.get('rh'), 0)} %</b></div>
<div><small>Wind</small><b id="w">{wind}</b></div>
<div><small>Luftdruck</small><b id="p">{k(o.get('p'), 0)} hPa</b></div>
</div></section>
{('<section class="card max"><img src="' + SITE + 'max-kopf.png" alt=""><div><b>Max sagt:</b> ' + e(ms) + '</div></section>') if ms else ''}
{('<section class="card">' + vt + '</section>') if vt else ''}
<section class="card regen"><span>Regen heute: <b>{k(o.get('r'))} l/m²</b></span><span>7 Tage: <b>{k(o.get('r7'), 0)} l/m²</b></span><span>Dieser Monat: <b>{k(o.get('rmon'), 0)} l/m²</b></span></section>
<section class="card links">Weitere Orte: {andere} · <a href="{SITE}">Wetter Bad König</a><br>Mehr: <a href="{SITE}#odenwald">Karte Odenwaldkreis</a> · <a href="{SITE}#video">Max-Videos</a> · <a href="https://www.dwd.de/DE/wetter/warnungen_gemeinden/warnWetter_node.html" rel="noopener">DWD-Warnungen</a></section>
<p class="fuss">Messwerte: {e(o.get('quelle') or 'private Station')} in {e(kn)} · Vorhersage: an den Odenwald angepasste Modellmischung · <a href="{SITE}impressum.html">Impressum &amp; Datenschutz</a></p>
</main>
<script>
(function(){{var N={json.dumps(n, ensure_ascii=False)};function f(v,n){{return v==null?'–':v.toFixed(n).replace('.',',').replace('-','−')}}
function lade(){{fetch('{SITE}data/odenwald-live.json?x='+Date.now()).then(function(r){{return r.json()}}).then(function(d){{var o=(d.orte||[]).concat(d.extra||[]).filter(function(x){{return x.name==N}})[0];if(!o)return;
document.getElementById('t').textContent=f(o.t,1)+' °C';document.getElementById('rh').textContent=f(o.rh,0)+' %';document.getElementById('p').textContent=f(o.p,0)+' hPa';
document.getElementById('w').textContent=(!o.w&&!o.g)?'windstill':f(o.w,0)+' km/h, Böen '+f(o.g,0);document.getElementById('zeit').textContent=(o.zeit||'').slice(11,16)}}).catch(function(){{}})}}
setInterval(lade,5*60000);
var k=document.getElementById('kopf');if(k&&k.classList.contains('himmel')){{var h=new Date().getHours()+new Date().getMinutes()/60,m=new Date().getMonth(),auf=[8,7.5,6.7,6.6,5.8,5.3,5.5,6.1,6.9,7.6,7.5,8.2][m],unt=[16.9,17.7,18.5,20.3,21,21.5,21.4,20.7,19.6,18.5,16.7,16.4][m];
k.classList.remove('tag','nacht','daemmer');k.classList.add(h<auf-0.6||h>unt+0.6?'nacht':(h<auf+0.6||h>unt-0.6)?'daemmer':'tag')}}}})();
</script>
</body>
</html>
'''


def main():
    ziel = sys.argv[1] if len(sys.argv) > 1 else BASIS
    nur = sys.argv[2:]
    L = json.load(open(os.path.join(BASIS, 'data', 'odenwald-live.json'), encoding='utf-8'))
    alle = L['orte'] + L.get('extra', [])
    try:
        D = json.load(open(os.path.join(BASIS, 'fb', 'daten.json'), encoding='utf-8'))
        vor = D.get('orte') or {}; nied = (D.get('tage') or [{}])[0].get('nied')
    except Exception: vor, nied = {}, None
    global KOPF
    KOPF = _kopf()
    stil = os.environ.get('STIL', 'himmel')
    os.makedirs(ziel, exist_ok=True)
    for o in alle:
        if o['name'] not in SLUG or (nur and SLUG[o['name']] not in nur): continue
        p = os.path.join(ziel, SLUG[o['name']] + os.environ.get('ENDUNG', '') + '.html')
        neu = seite(o, alle, vor.get(VORH.get(o['name'], o['name'])), nied, L.get('stand'), stil)
        try: alt = open(p, encoding='utf-8').read()
        except Exception: alt = ''
        if alt != neu: open(p, 'w', encoding='utf-8').write(neu); print('geschrieben:', p)
    if ziel == BASIS and not nur: seo_jetzt(alle)


if __name__ == '__main__': main()
