// Website-Karte „Jetzt im Odenwald“ als PNG (transparent) mit eigenen Werten – für die Mittagskarte (19.11.2026).
// Aufruf: node karte_shot.mjs URL WERTE_JSON AUSGABE.png    WERTE = {"Ort": {"t": 11, "wx": "schauer"}, ...}
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os'; import { join } from 'node:path';
const [url, werte, out, gross] = process.argv.slice(2);   // gross: Faktor für die Ortsfelder (z. B. 1.5 für Stories)
const bin = process.env.CHROME_BIN || 'google-chrome', port = 9300 + Math.floor(Math.random() * 500);
const ch = spawn(bin, ['--headless=new', '--no-sandbox', '--disable-gpu', '--remote-debugging-port=' + port, '--user-data-dir=' + mkdtempSync(join(tmpdir(), 'ks-')),
  '--window-size=1400,2400', '--force-device-scale-factor=2', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const ende = (c, t) => { if (t) console.error(t); try { ch.kill(); } catch (e) {} process.exit(c); };
setTimeout(() => ende(1, 'Zeitüberschreitung'), 90000);
let tabs; for (let i = 0; i < 100; i++) { try { tabs = await (await fetch('http://127.0.0.1:' + port + '/json')).json(); if (tabs.length) break; } catch (e) {} await sleep(200); }
const ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pend = {}; ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend[m.id]) { pend[m.id](m.result); delete pend[m.id]; } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async x => (await send('Runtime.evaluate', { expression: x, returnByValue: true })).result?.value;
await send('Page.enable'); await send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }, { name: 'prefers-color-scheme', value: 'light' }] });
await send('Page.navigate', { url: url.includes('#') ? url : url + '#odenwald' });
for (let i = 0; i < 60; i++) { if (await ev("typeof OW!=='undefined'&&!!OW.d&&typeof owKarte==='function'")) break; if (i % 10 === 9) await ev("try{owLaden(true)}catch(e){}"); await sleep(500); }
await sleep(1500);
const r = await ev(`(function(){try{var W=${werte};
 OW.k='t'; OW.sel=null; window.owNacht=function(){return false};
 var F=function(L){return (L||[]).filter(function(o){return W[o.name]}).map(function(o){var w=W[o.name];o.t=w.t;o.wx=w.wx;o.zeit=new Date().toISOString();return o})};
 OW.d.orte=F(OW.d.orte); OW.d.extra=F(OW.d.extra);
 if(parseFloat('${gross || 1}')>1){OW_POS['Höchst i. Odw.']=[-72,-34];OW_POS['Brombachtal']=[-34,8];OW_POS['Bad König']=[12,-14];OW_POS['Michelstadt']=[10,-2];}   // Stories: größere Felder ohne Überlappung
 owKarte();
 document.querySelectorAll('#owMap .owk-v').forEach(function(t){t.textContent=t.textContent.replace(/,0°$/,'°')});
 var G=parseFloat('${gross || 1}'); if(G>1) document.querySelectorAll('#owMap g[data-ow]').forEach(function(g){var c=g.querySelector('circle');var x=+c.getAttribute('cx'),y=+c.getAttribute('cy');var dy=0;g.setAttribute('transform','translate('+x+' '+(y+dy)+') scale('+G+') translate('+(-x)+' '+(-y)+')')}); document.querySelector('#owMap svg').setAttribute('viewBox','-125 0 560 505');
 var leg=document.querySelector('#owMap .ow-wxleg'); if(leg) leg.remove();
 document.querySelectorAll('#owMap p').forEach(function(p){p.remove()});
 Array.from(document.body.querySelectorAll('*')).forEach(function(e){var sv=document.querySelector('#owMap svg');if(!sv.contains(e)&&!e.contains(sv))e.style.visibility='hidden'});
 document.documentElement.style.background='transparent'; document.body.style.background='transparent'; document.body.style.backgroundImage='none';
 var p=document.getElementById('owMap'); while(p){p.style.background='transparent';p.style.boxShadow='none';p.style.border='0';p=p.parentElement;}
 var s=document.querySelector('#owMap svg'); s.style.maxHeight='none'; s.style.height='auto'; s.style.width='760px'; s.setAttribute('height','905'); s.scrollIntoView(); var b=s.getBoundingClientRect();
 return JSON.stringify({x:b.x,y:b.y,w:b.width,h:b.height,n:OW.d.orte.length+OW.d.extra.length});}catch(e){return 'FEHLER '+e}})()`);
if (!r || r.startsWith('FEHLER')) ende(1, 'Karte nicht gezeichnet: ' + r);
const b = JSON.parse(r); await sleep(600);
const shot = await send('Page.captureScreenshot', { format: 'png', clip: { x: b.x, y: b.y, width: b.w, height: b.h, scale: 1 } });
writeFileSync(out, Buffer.from(shot.data, 'base64')); console.log('Website-Karte: %d Orte', b.n); ws.close(); ende(0);
