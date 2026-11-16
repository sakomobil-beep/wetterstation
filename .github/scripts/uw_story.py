"""Story-Bild (1080x1920) zum Unwetter-Special: Warnstufe, Zeitraum, Gebiet, DWD-Hinweise (15.11.2026)."""
import datetime as dt, re, textwrap
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

TZ = ZoneInfo('Europe/Berlin')
FARBE = {2: (230, 120, 0), 3: (200, 20, 30), 4: (140, 30, 160)}

def F(s, b=False):
    try: return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % ('-Bold' if b else ''), s)
    except Exception: return ImageFont.load_default(s)

def _t(iso):
    try: return dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(TZ)
    except Exception: return None

def zeitraum(I, heute):
    v, b = _t(I.get('von') or ''), _t(I.get('bis') or '')
    def f(t): return ('%d' % t.hour if not t.minute else '%d:%02d' % (t.hour, t.minute))
    def tag(t): return '' if t.date() == heute else ('morgen ' if t.date() == heute + dt.timedelta(days=1) else t.strftime('%d.%m. '))
    if v and b and v.date() == b.date(): return '%s%s – %s Uhr' % (tag(v), f(v), f(b))   # gleicher Tag: „morgen 3 – 18 Uhr“
    if v and b: return '%s%s – %s%s Uhr' % (tag(v), f(v), tag(b), f(b))
    return ('bis %s%s Uhr' % (tag(b), f(b))) if b else ''

def bauen(warn, info, stufe, heute, pfad):
    W, H = 1080, 1920
    c = FARBE.get(min(max(stufe, 2), 4))
    im = Image.new('RGB', (W, H), (18, 22, 34)); d = ImageDraw.Draw(im)
    for y in range(H):   # dunkler Verlauf
        k = y / H; d.line([(0, y), (W, y)], fill=(int(18 + 25 * k), int(22 + 10 * k), int(34 + 20 * k)))
    d.rectangle([0, 0, W, 300], fill=c)
    d.text((W // 2, 110), '⚠ ' if False else 'UNWETTERWARNUNG' if stufe >= 3 else 'WETTERWARNUNG', font=F(84, True), fill='white', anchor='mm')
    d.text((W // 2, 215), 'Stufe %d von 4 · %s' % (stufe, 'EXTREM' if stufe >= 4 else 'UNWETTER' if stufe == 3 else 'MARKANT'), font=F(46, True), fill='white', anchor='mm')
    y = 380
    w0 = warn[0] if warn else ''
    I = info.get(w0) or next(iter(info.values()), {}) if info else {}
    titel = re.sub(r'^Amtliche (UNWETTERWARNUNG|Unwetterwarnung|WARNUNG|Warnung) vor ', '', w0.split(' für ')[0], flags=re.I).upper()
    titel = re.sub(r'(EXTREM|SCHWER|HEFTIG|STARK)EM\b', r'\1ES', titel).replace('ORKANARTIGEN', 'ORKANARTIGE')
    for z in textwrap.wrap(titel, 15)[:3]:
        d.text((W // 2, y), z, font=F(84, True), fill=(220, 120, 240) if stufe >= 4 else (255, 90, 80) if stufe == 3 else (255, 160, 40), anchor='mm'); y += 105
    y += 30
    zr = zeitraum(I, heute)
    if zr:
        d.rounded_rectangle([90, y, W - 90, y + 150], 30, fill=(255, 255, 255))
        d.text((W // 2, y + 45), 'GÜLTIG', font=F(34, True), fill=(90, 90, 90), anchor='mm')
        gr = 60
        while gr > 30 and d.textlength(zr, font=F(gr, True)) > W - 240: gr -= 2   # passt immer in den Kasten
        d.text((W // 2, y + 105), zr, font=F(gr, True), fill=(20, 20, 20), anchor='mm'); y += 200
    geb = I.get('gebiet') or 'ganzer Odenwaldkreis'
    gz = textwrap.wrap(geb, 34) if geb != 'ganzer Odenwaldkreis' else [geb]
    gf = 44 if len(gz) == 1 else 36
    for z in gz[:4]:
        d.text((W // 2, y + 20), z, font=F(gf, True), fill='white', anchor='mm'); y += gf + 14
    y += 40
    txt = re.sub(r'\s+', ' ', I.get('text') or '').strip()
    for z in textwrap.wrap(txt, 36)[:5]:
        d.text((W // 2, y), z, font=F(38), fill=(225, 225, 230), anchor='mm'); y += 52
    rr = re.sub(r'\s+', ' ', I.get('rat') or '').strip()
    teile = re.split(r'\s*Handlungsempfehlungen:\s*', rr, maxsplit=1)   # DWD: „Gefahr durch: a; b. Handlungsempfehlungen: x; y“
    rat = []
    if len(teile) == 2:
        gef = teile[0].strip(' .')
        if gef: rat.append(gef.replace('; ', ', '))
        for x in teile[1].split(';'):
            x = re.sub(r'^\s*z\.\s?B\.\s*', '', x).strip(' .')
            if len(x) > 3: rat.append(x)
    else:
        MARK = '\u0001'
        rr = rr.replace('z.B.', 'z' + MARK + 'B' + MARK).replace('z. B.', 'z' + MARK + ' B' + MARK)
        rat = [x.strip(' .;').replace(MARK, '.') for x in re.split(r'(?<=[.!])\s+|;\s*', rr) if len(x.strip(' .;')) > 3]
    rat = [x[0].upper() + x[1:] for x in rat][:5]
    if rat:
        y += 40; d.text((W // 2, y), 'HINWEISE DES DWD', font=F(40, True), fill=(255, 200, 60), anchor='mm'); y += 70
        for s in rat:
            zl = textwrap.wrap(s, 36)
            if y + len(zl) * 48 > H - 200: break   # nur ganze Hinweise, nichts abgeschnitten
            for i, z in enumerate(zl):
                d.text((110, y), ('• ' if i == 0 else '  ') + z, font=F(36), fill='white'); y += 48
            y += 12
    d.rectangle([0, H - 170, W, H], fill=(10, 12, 20))
    d.text((W // 2, H - 110), 'Max erklärt alles im Video' if stufe >= 3 else 'Live-Werte & Radar online', font=F(40, True), fill=(255, 200, 60), anchor='mm')
    d.text((W // 2, H - 55), 'wetter-badkoenig.de · Quelle: DWD', font=F(34), fill=(200, 200, 210), anchor='mm')
    im.save(pfad, quality=90)


def feed(story_pfad, pfad, stufe):
    """Beitragsbild 4:5 (1080x1350) aus dem Story-Bild – für Facebook/Instagram-Feed (15.11.2026)."""
    st = Image.open(story_pfad).convert('RGB').resize((760, 1350), Image.LANCZOS)
    im = Image.new('RGB', (1080, 1350), st.getpixel((5, 700)))
    d = ImageDraw.Draw(im)
    for y in range(1350):   # Hintergrund wie im Story-Bild
        im.paste(st.getpixel((3, y)), (0, y, 160, y + 1)); im.paste(st.getpixel((756, y)), (920, y, 1080, y + 1))
    im.paste(st, (160, 0)); im.save(pfad, quality=90)


def text(warn, info, stufe, heute):
    """Kurzer Beitragstext zur Warnung."""
    w0 = warn[0]; I = info.get(w0) or {}
    titel = re.sub(r'^Amtliche (UNWETTERWARNUNG|Unwetterwarnung|WARNUNG|Warnung) vor ', '', w0.split(' für ')[0], flags=re.I)
    titel = ' '.join(x.capitalize() if x.isupper() and len(x) > 2 else x for x in titel.split())
    zr = zeitraum(I, heute)
    geb = I.get('gebiet') or 'ganzer Odenwaldkreis'
    z = ['⚠️ DWD-Warnung für den Odenwald: %s (Stufe %d von 4)' % (titel, stufe), '']
    if zr: z.append('🕒 Gültig: ' + zr)
    z.append('📍 ' + geb)
    if I.get('text'): z += ['', re.sub(r'\s+', ' ', I['text']).strip()]
    z += ['', 'Kommt gut durch! Live-Werte, Radar & alle Warnungen 👉 https://wetter-badkoenig.de',
          '#Odenwald #Odenwaldkreis #BadKönig #Wetter #Wetterwarnung #DWD']
    return '\n'.join(z)
