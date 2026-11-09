#!/usr/bin/env python3
"""DWD-Warn-Push: holt die amtlichen DWD-Warnungen für Bad König (Bright Sky /alerts) und schickt
für jede NEUE Warnung eine ntfy-Push-Nachricht (Secret NTFY_TOPIC). Eine Warnung = ein Push.
Wird eine Warnung verlängert/verschärft (neue Warnungs-ID), kommt erneut ein Push.
Stufe -> Priorität: gering = leise, markant = normal, Unwetter = hoch, extrem = dringend.
Merkt sich die gemeldeten Warnungen in fb/dwd_push.json."""
import gzip, json, os, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Berlin')
LAT, LON = 49.750, 9.017
MERK = os.path.join(os.path.dirname(__file__), '..', '..', 'fb', 'dwd_push.json')
STUFE = {'minor': ('Wetterwarnung', 'low', 'yellow_circle'),
         'moderate': ('Markante Wetterwarnung', 'default', 'orange_circle'),
         'severe': ('UNWETTERWARNUNG', 'high', 'red_circle'),
         'extreme': ('EXTREMES UNWETTER', 'urgent', 'rotating_light')}


def holen():
    url = 'https://api.brightsky.dev/alerts?lat=%s&lon=%s&tz=Europe/Berlin' % (LAT, LON)
    req = urllib.request.Request(url, headers={'User-Agent': 'wetter-badkoenig.de', 'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=30) as r:
        roh = r.read()
        if r.headers.get('Content-Encoding') == 'gzip': roh = gzip.decompress(roh)
    return json.loads(roh).get('alerts') or []


def uhr(s):
    t = dt.datetime.fromisoformat(s).astimezone(TZ)
    heute = dt.datetime.now(TZ).date()
    tag = 'heute' if t.date() == heute else 'morgen' if t.date() == heute + dt.timedelta(days=1) else t.strftime('%d.%m.')
    return '%s %s Uhr' % (tag, t.strftime('%H:%M'))


def push(titel, text, prio, tags):
    topic = os.environ.get('NTFY_TOPIC')
    if not topic: print('Kein NTFY_TOPIC – kein Push.'); return False
    req = urllib.request.Request('https://ntfy.sh/' + topic, data=text.encode('utf-8'), headers={
        'Title': titel.encode('utf-8').decode('latin-1'), 'Priority': prio, 'Tags': tags,
        'Click': 'https://wetter-badkoenig.de/'})
    urllib.request.urlopen(req, timeout=20).read(); print('Push gesendet:', titel); return True


def main():
    try: merk = json.load(open(MERK))
    except Exception: merk = {}
    alerts = holen()
    jetzt = dt.datetime.now(TZ)
    # abgelaufene Einträge vergessen
    merk = {k: v for k, v in merk.items() if dt.datetime.fromisoformat(v) > jetzt - dt.timedelta(days=2)}
    neu = 0
    for a in alerts:
        aid = str(a.get('alert_id') or a.get('id'))
        if aid in merk: continue
        if a.get('expires') and dt.datetime.fromisoformat(a['expires']) < jetzt: continue
        stufe, prio, tag = STUFE.get(a.get('severity'), ('Wetterwarnung', 'default', 'warning'))
        ev = (a.get('event_de') or 'Warnung').title() if (a.get('event_de') or '').isupper() else (a.get('event_de') or 'Warnung')
        teile = []
        if a.get('onset') and a.get('expires'): teile.append('Gültig %s bis %s.' % (uhr(a['onset']), uhr(a['expires'])))
        if a.get('description_de'): teile.append(a['description_de'].strip()[:400])
        if a.get('instruction_de'): teile.append('Tipp: ' + a['instruction_de'].strip().split('\n')[0][:200])
        teile.append('Amtliche Warnung des DWD für Bad König.')
        if push('⚠️ %s: %s' % (stufe, ev), '\n'.join(teile), prio, tag + ',warning'):
            merk[aid] = (a.get('expires') or jetzt.isoformat()); neu += 1
    print('%d aktive DWD-Warnung(en), %d neu gemeldet.' % (len(alerts), neu))
    json.dump(merk, open(MERK, 'w'), indent=1)


if __name__ == '__main__':
    try: main()
    except Exception as e: print('DWD-Push nicht möglich:', e)
