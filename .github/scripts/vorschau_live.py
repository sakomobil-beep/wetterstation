#!/usr/bin/env python3
"""Live-Vorschau (18.11.2026): baut vorschau/live/index.html aus der echten index.html – mit allen Live-Daten und
Funktionen, aber im Look von Variante C („Jetzige Seite verfeinert“, Kingmans Wahl) und mit Max-Karte.
Die echte Seite bleibt unverändert. Neu bauen: python .github/scripts/vorschau_live.py"""
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CSS = r'''
<style id="vorschauC">
html,html[data-theme],html[data-theme="dark"],html[data-theme="light"]{--bg:#0f172a!important;--surface:#1e293b!important;--ink:#e2e8f0!important;--muted:#94a3b8!important;--line:#2c3a52!important;--accent:#f97316!important;--card:#1e293b!important;--sky1:#0f172a!important;--sky2:#0f172a!important;color-scheme:dark}
body{background:#0f172a!important;color:#e2e8f0}
.sky,.deko{display:none!important}
.vbar{background:#f97316;color:#fff;text-align:center;font:600 13px/1.4 var(--font-body);padding:6px}.vbar a{color:#fff;text-decoration:underline}
.top{display:block!important;background:#0f172a;border-bottom:1px solid #2c3a52;padding:16px 0 0!important;margin-bottom:18px}
.top .label{font-size:12.5px!important;color:#94a3b8!important;letter-spacing:0!important;text-transform:none!important;font-weight:500!important}
.top h1{font-size:20px!important;font-weight:700!important;color:#e2e8f0!important}
.vbrand{display:flex;align-items:center;gap:12px}
.vlogo{width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,#f97316,#fb923c);color:#fff;font:800 17px/38px var(--font-body);text-align:center;flex:none}
.tabnav{margin-top:12px!important}
.tabnav .navrow{display:flex!important;flex-wrap:nowrap!important;gap:2px!important;align-items:center;border:0!important;background:none!important;padding:0!important}
.tabnav .navrow a{background:none!important;border:0!important;border-bottom:2px solid transparent!important;border-radius:0!important;padding:11px 14px!important;color:#94a3b8!important;font-weight:600!important;font-size:14.5px!important;box-shadow:none!important}
.tabnav .navrow a[aria-current="page"],.tabnav .navrow a.on{color:#e2e8f0!important;border-bottom-color:#f97316!important}
.tabnav .navrow.topics{display:none!important}
.vmehr{margin-left:auto;position:relative}
.vmehr summary{list-style:none;cursor:pointer;padding:11px 14px;color:#94a3b8;font-weight:600;font-size:14.5px}.vmehr summary::-webkit-details-marker{display:none}
.vmehr[open] summary{color:#e2e8f0}
.vmehr .vm{position:absolute;right:0;top:100%;z-index:50;background:#1e293b;border:1px solid #2c3a52;border-radius:12px;padding:8px;min-width:220px;box-shadow:0 12px 30px #0008;display:grid}
.vmehr .vm a{padding:8px 12px!important;border:0!important;border-radius:8px!important;color:#e2e8f0!important;font-size:14px!important}.vmehr .vm a:hover{background:#24324a!important}
figure.photo{border-radius:14px!important;overflow:hidden!important;margin-bottom:18px!important}
.tile,.hero,.wcard,.chart,.fcard,.vj,.factscard,.dob,.ow-card,.ow-chip,.fcw,section.tile,article.tile{background:#1e293b!important;border:1px solid #2c3a52!important;border-radius:14px!important;box-shadow:none!important;color:#e2e8f0}
#heroCard{background:linear-gradient(135deg,#312e81,#1e293b 70%)!important}
.label,.w-kicker{color:#94a3b8!important}
h2.sec{color:#e2e8f0!important}
.refresh,.tab,.tabs button,.fcsw button{border-radius:9px!important}
.vmax{background:#1e293b;border:1px solid #2c3a52;border-radius:14px;padding:16px 18px;margin-bottom:14px}
.vmax .mx{display:flex;gap:12px;align-items:center}
.vmax .av{width:54px;height:54px;border-radius:50%;background:#24324a url(vorschau/max-kopf.png) center 30%/86% no-repeat;border:2px solid #f97316;flex:none}
.vmax b{font-size:15px}.vmax p{margin:0;font-size:12.5px;color:#94a3b8}
.vmax .q{margin-top:12px;font-size:15px;line-height:1.55}
</style>'''
JS = r'''
<script id="vorschauJS">
(function(){
  var h=document.documentElement;
  function dunkel(){ if(h.getAttribute('data-theme')!=='dark') h.setAttribute('data-theme','dark'); }
  dunkel(); new MutationObserver(dunkel).observe(h,{attributes:true,attributeFilter:['data-theme']});
  var vb=document.createElement('div'); vb.className='vbar';
  vb.innerHTML='LIVE-VORSCHAU Variante C · echte Daten, neuer Look · nicht die öffentliche Seite · <a href="/vorschau/">alle Entwürfe</a> · <a href="/">echte Seite</a>';
  document.body.insertBefore(vb, document.body.firstChild);
  var top=document.querySelector('.top'); if(top){ var d=top.firstElementChild; if(d){ var b=document.createElement('div'); b.className='vbrand'; b.innerHTML='<div class="vlogo">BK</div>'; top.insertBefore(b,d); b.appendChild(d); } }
  var r1=document.querySelector('.tabnav .navrow'), r2=document.querySelector('.tabnav .navrow.topics');
  if(r1){ var det=document.createElement('details'); det.className='vmehr'; det.innerHTML='<summary>Mehr ▾</summary><div class="vm"></div>'; var vm=det.querySelector('.vm');
    ['nav-woche','nav-station','nav-webcams'].forEach(function(i){var a=document.getElementById(i); if(a) vm.appendChild(a);});
    if(r2) [].slice.call(r2.querySelectorAll('a')).forEach(function(a){vm.appendChild(a);});
    r1.appendChild(det); vm.addEventListener('click',function(){det.open=false;}); }
  function maxKarte(){
    if(document.querySelector('.mxk')) return true;   // echte Seite hat die Max-Karte schon (seit 18.11.2026)
    var ob=document.querySelector('.dob'); if(!ob||document.querySelector('.vmax')) return !!document.querySelector('.vmax');
    var k=document.createElement('section'); k.className='vmax';
    k.innerHTML='<div class="mx"><div class="av"></div><div><b>Max sagt</b><p>Euer Wettersprecher für den Odenwald</p></div></div><div class="q" id="vmaxQ">…</div>';
    ob.parentNode.insertBefore(k, ob); return true;
  }
  function maxText(){
    if(document.querySelector('.mxk')) return true;
    var q=document.getElementById('vmaxQ'), t=document.getElementById('fcText'); if(!q||!t) return false;
    var s=(t.textContent||'').replace(/\s+/g,' ').trim(); if(s.length<20) return false;
    var m=s.match(/^[^.!?]*[.!?]/); var x=(m?m[0]:s.slice(0,160)).trim().replace(/^(Heute|In der Nacht|Heute Nacht|Morgen|Am Abend|Heute Abend)\s*:\s*/,function(_,w){return w==='In der Nacht'||w==='Heute Nacht'?'Heute Nacht: ':''}); q.textContent='„'+x.charAt(0).toUpperCase()+x.slice(1)+'“'; return true;
  }
  var n=0, iv=setInterval(function(){ n++; if((maxKarte()&&maxText())||n>60) clearInterval(iv); }, 500);
})();
</script>'''

def bauen():
    s = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    s = s.replace('<head>', '<head>\n<base href="/">\n<meta name="robots" content="noindex,nofollow">', 1)
    s = s.replace('</head>', CSS + '\n</head>', 1)
    i = s.rfind('</body>'); s = s[:i] + JS + '\n' + s[i:]
    os.makedirs(os.path.join(ROOT, 'vorschau', 'live'), exist_ok=True)
    open(os.path.join(ROOT, 'vorschau', 'live', 'index.html'), 'w', encoding='utf-8').write(s)
    print('vorschau/live/index.html gebaut (%d KB)' % (len(s) // 1024))

if __name__ == '__main__':
    bauen()
