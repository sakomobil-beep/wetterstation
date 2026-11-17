#!/usr/bin/env python3
"""Wetterwissen mit Max auf der Website (seit 17.11.2026): jede Folge wird 7 Tage in fb/wissen-archiv/ aufbewahrt
(Video + Vorschaubild + liste.json mit Folge und Titel). Die Website zeigt die Folgen im Video-Tab und nennt die
neueste auf der Startseite – die Folge von heute erst ab 15 Uhr (Zeit des Autoposts, prüft die Seite selbst).
Aufruf am Ende von wissen_video.py; von Hand:  python wissen_archiv.py"""
import os, sys, json, glob, shutil, subprocess, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FB = os.path.join(ROOT, 'fb')
AD = os.path.join(FB, 'wissen-archiv')
TAGE = 7


def ablegen():
    j = json.load(open(os.path.join(FB, 'wissen.json'), encoding='utf-8'))
    quelle = os.path.join(FB, 'wissen.mp4')
    if not os.path.exists(quelle) or not j.get('datum'): print('Kein Wetterwissen-Video zum Ablegen.'); return False
    os.makedirs(AD, exist_ok=True)
    datei = j['datum'] + '.mp4'
    shutil.copy(quelle, os.path.join(AD, datei))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '3', '-i', os.path.join(AD, datei), '-frames:v', '1', '-vf', 'scale=270:-2', '-q:v', '5',
                    os.path.join(AD, datei.replace('.mp4', '.jpg'))], check=False)
    lp = os.path.join(AD, 'liste.json')
    try: liste = json.load(open(lp, encoding='utf-8'))
    except Exception: liste = []
    liste = [e for e in liste if e.get('datei') != datei]
    liste.append({'datum': j['datum'], 'datei': datei, 'folge': j.get('folge'), 'titel': j.get('titel', ''), 'dauer': j.get('dauer'), 'erstellt': j.get('erstellt', '')})
    grenze = (dt.date.fromisoformat(j['datum']) - dt.timedelta(days=TAGE - 1)).isoformat()
    for f in glob.glob(os.path.join(AD, '*.mp4')) + glob.glob(os.path.join(AD, '*.jpg')):
        if os.path.basename(f)[:10] < grenze: os.remove(f)
    liste = sorted([e for e in liste if e['datum'] >= grenze], key=lambda e: e['datum'], reverse=True)
    json.dump(liste, open(lp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('Wetterwissen abgelegt: %s (%d Folgen im Archiv)' % (datei, len(liste)))
    return True


if __name__ == '__main__':
    ablegen()
