// Cloudflare-Worker „dwd-wecker“ (18.11.2026) – Wetterstation Bad König
// Prüft jede Minute die amtlichen DWD-Warnungen (Bright Sky) für die 12 Gemeinden des Odenwaldkreises und weckt bei
// Bedarf den GitHub-Ablauf „DWD-Warnung (schnell)“ (dwd-warnung.yml). Der Worker postet NICHTS und merkt sich nichts:
// ob gepostet wird, entscheidet allein der Ablauf bei GitHub (Gedächtnis in fb/gepostet.json, gegen Doppelposts).
//   - neue Warnung (vom DWD in den letzten 3 Minuten herausgegeben) -> sofort wecken
//   - solange eine Warnung ab Stufe 2 gilt -> zusätzlich alle 10 Minuten wecken (zweiter Versuch, falls etwas scheiterte)
// Einstellungen: Cron-Trigger „* * * * *“, geheimer Wert GH_TOKEN (GitHub-Schlüssel nur für sakomobil-beep/wetterstation,
// Recht „Actions: Read and write“).
const ORTE = [[49.741, 9.008], [49.823, 9.046], [49.773, 8.884], [49.733, 8.945], [49.657, 8.994], [49.746, 8.858],
  [49.799, 8.995], [49.786, 9.075], [49.678, 9.004], [49.660, 8.930], [49.567, 8.976], [49.713, 8.838]];
const STUFE = { moderate: 2, severe: 3, extreme: 4 };

async function pruefen(env) {
  const jetzt = Date.now();
  let aktiv = 0, neu = 0, ok = 0;
  const antworten = await Promise.all(ORTE.map(([la, lo]) =>
    fetch(`https://api.brightsky.dev/alerts?lat=${la}&lon=${lo}&tz=Europe/Berlin`, { headers: { 'User-Agent': 'wetter-badkoenig.de dwd-wecker' } })
      .then(r => r.ok ? r.json() : null).catch(() => null)));
  for (const j of antworten) {
    if (!j) continue; ok++;
    for (const a of j.alerts || []) {
      if (!STUFE[a.severity]) continue;
      if (a.expires && Date.parse(a.expires) - 30 * 60000 < jetzt) continue;   // endet in < 30 Min: wird nicht mehr gepostet
      aktiv++;
      if (a.effective && jetzt - Date.parse(a.effective) < 3 * 60000) neu++;
    }
  }
  const minute = new Date(jetzt).getUTCMinutes();
  const wecken = neu > 0 || (aktiv > 0 && minute % 10 === 0);
  if (wecken) {
    const r = await fetch('https://api.github.com/repos/sakomobil-beep/wetterstation/actions/workflows/dwd-warnung.yml/dispatches', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + env.GH_TOKEN, 'Accept': 'application/vnd.github+json', 'User-Agent': 'dwd-wecker', 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main' })
    });
    return `Orte ${ok}/12, aktiv ${aktiv}, neu ${neu} -> geweckt (GitHub ${r.status})`;
  }
  return `Orte ${ok}/12, aktiv ${aktiv}, neu ${neu} -> nichts zu tun`;
}

export default {
  async scheduled(event, env, ctx) { ctx.waitUntil(pruefen(env).then(t => console.log(t))); },
  // Aufruf im Browser zeigt nur den Stand an, ohne zu wecken (Test): https://<worker>.workers.dev/
  async fetch(req, env) {
    return new Response('DWD-Wecker Bad König – läuft. Cron jede Minute, weckt dwd-warnung.yml bei neuer Warnung.', { headers: { 'content-type': 'text/plain; charset=utf-8' } });
  }
};
