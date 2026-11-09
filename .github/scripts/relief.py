#!/usr/bin/env python3
"""Einmalig: Reliefkarte (Höhen + Schummerung) des Odenwaldkreises aus Open-Meteo-Höhendaten -> data/odenwald-relief.png
Ausschnitt etwas größer als der Kreis; die Kreisgrenze liegt in data/odenwald-grenze.json."""
import json, os, time, urllib.request
import numpy as np
from PIL import Image

LO0, LO1, LA0, LA1 = 8.78, 9.18, 49.468, 49.872   # etwas weiter als der Kreis, damit die Grenze ganz hineinpasst
NX, NY = 64, 81          # Gitterpunkte (ca. 450 m Abstand)
pts = [(LA1 - (LA1 - LA0) * j / (NY - 1), LO0 + (LO1 - LO0) * i / (NX - 1)) for j in range(NY) for i in range(NX)]
el = []
for k in range(0, len(pts), 100):
    ch = pts[k:k + 100]
    url = 'https://api.open-meteo.com/v1/elevation?latitude=%s&longitude=%s' % (','.join('%.5f' % p[0] for p in ch), ','.join('%.5f' % p[1] for p in ch))
    for v in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de relief'}), timeout=40) as r:
                el += json.loads(r.read().decode())['elevation']; break
        except Exception as e:
            print('erneut', e); time.sleep(3)
    print('Paket', k // 100 + 1, 'von', (len(pts) + 99) // 100, flush=True)
Z = np.array(el, dtype=float).reshape(NY, NX)
print('Höhe min/max', Z.min(), Z.max())
# auf Bildgröße hochrechnen (glatt)
W, H = 600, 970
Zi = np.array(Image.fromarray(Z.astype(np.float32), 'F').resize((W, H), Image.BICUBIC))
# Schummerung (Licht von Nordwest)
dy, dx = np.gradient(Zi, 30.0)
az, alt = np.radians(315), np.radians(45)
slope = np.pi / 2 - np.arctan(np.hypot(dx, dy) * 2.2)
aspect = np.arctan2(-dx, dy)
hs = np.clip(np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect), 0, 1)
# Höhenfarben: Tal grün -> Höhen hellbraun
st = [(100, (120, 170, 110)), (200, (150, 190, 120)), (300, (200, 205, 140)), (400, (205, 180, 125)), (500, (180, 150, 110)), (620, (160, 135, 115))]
e = np.array([s[0] for s in st]); c = np.array([s[1] for s in st], dtype=float)
rgb = np.stack([np.interp(Zi, e, c[:, k]) for k in range(3)], -1)
rgb = rgb * (0.55 + 0.6 * hs[..., None])
# Höhenlinien alle 100 m
lin = (np.abs(((Zi + 50) % 100) - 50) < 1.6)
rgb[lin] = rgb[lin] * 0.72
img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), 'RGB')
os.makedirs('data', exist_ok=True)
img.save('data/odenwald-relief.png', optimize=True)
json.dump({'lo': [LO0, LO1], 'la': [LA0, LA1], 'min': float(Z.min()), 'max': float(Z.max())}, open('data/odenwald-relief.json', 'w'))
print('fertig')
