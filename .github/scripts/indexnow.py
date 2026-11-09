"""Meldet geänderte Seiten per IndexNow an Bing & Co. und aktualisiert lastmod in sitemap.xml (für Google)."""
import sys, re, json, datetime as dt, urllib.request
KEY = '7563e24b17ace6c0005b4ab183bd635d'
HOST = 'wetter-badkoenig.de'
SKIP = {'facebook.html'}
dateien = [d for d in sys.argv[1:] if d.endswith('.html') and '/' not in d and d not in SKIP]
alle = '--alle' in sys.argv
sm = open('sitemap.xml', encoding='utf-8').read()
locs = re.findall(r'<loc>(.*?)</loc>', sm)
heute = dt.date.today().isoformat()
def url(d): return 'https://%s/' % HOST + ('' if d == 'index.html' else d)
if alle: urls = locs
else:
    urls = [url(d) for d in dateien if url(d) in locs]
    for u in urls:
        sm = re.sub(r'(<loc>%s</loc><lastmod>)[^<]*' % re.escape(u), r'\g<1>' + heute, sm)
    open('sitemap.xml', 'w', encoding='utf-8').write(sm)
if not urls: print('Keine geänderten Seiten.'); sys.exit()
body = json.dumps({'host': HOST, 'key': KEY, 'keyLocation': 'https://%s/%s.txt' % (HOST, KEY), 'urlList': urls}).encode()
req = urllib.request.Request('https://api.indexnow.org/indexnow', data=body, headers={'Content-Type': 'application/json; charset=utf-8'})
try:
    with urllib.request.urlopen(req, timeout=30) as r: print('IndexNow:', r.status, len(urls), 'Seite(n) gemeldet')
except urllib.error.HTTPError as e: print('IndexNow Fehler', e.code, e.read()[:300])
