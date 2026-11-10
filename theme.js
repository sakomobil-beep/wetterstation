/* Dark Mode der Privaten Wetterstation Bad König.
   - Automatisch: ab Sonnenuntergang in Bad König dunkel, ab Sonnenaufgang hell.
   - Knopf (Sonne/Mond) oben rechts: schaltet von Hand um. Die Wahl gilt bis zum
     nächsten Sonnenauf- bzw. -untergang, danach übernimmt wieder die Automatik.
   - Fremde Inhalte (Radar, Webcams, YouTube, DWD-Karten) bleiben, wie sie geliefert werden. */
(function () {
  var LAT = 49.7417, LON = 8.9817, KEY = 'wbk-theme';
  var root = document.documentElement;

  /* ---------- Sonnenauf-/untergang (NOAA-Näherung, auf ca. 1–2 Min genau) ---------- */
  function sunTimes(date) {
    var rad = Math.PI / 180;
    var start = Date.UTC(date.getFullYear(), 0, 0);
    var doy = Math.floor((Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) - start) / 864e5);
    var g = 2 * Math.PI / 365 * (doy - 1);
    var eqt = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
    var dec = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
    var ha = Math.acos(Math.cos(90.833 * rad) / (Math.cos(LAT * rad) * Math.cos(dec)) - Math.tan(LAT * rad) * Math.tan(dec)) / rad;
    var noon = 720 - 4 * LON - eqt;
    var day0 = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
    return { auf: day0 + (noon - 4 * ha) * 6e4, unter: day0 + (noon + 4 * ha) * 6e4 };
  }
  function autoState(now) {
    var t = sunTimes(new Date(now)), next;
    var hell = now >= t.auf && now < t.unter;
    if (now < t.auf) next = t.auf;
    else if (now < t.unter) next = t.unter;
    else next = sunTimes(new Date(now + 864e5)).auf;
    return { mode: hell ? 'light' : 'dark', next: next };
  }
  function readOverride() {
    try { var o = JSON.parse(localStorage.getItem(KEY) || 'null'); if (o && o.bis > Date.now()) return o.mode; localStorage.removeItem(KEY); } catch (e) {}
    return null;
  }
  function currentMode() { return readOverride() || autoState(Date.now()).mode; }

  /* ---------- Farben ---------- */
  var DARK = { bg: '#151c26', surface: '#1f2835', ink: '#dde3ea', muted: '#9aa7b6', line: '#2e3a4a' };
  var css = '' +
    'html[data-theme="dark"]{color-scheme:dark;--bg:' + DARK.bg + ';--surface:' + DARK.surface + ';--ink:' + DARK.ink + ';--muted:' + DARK.muted + ';--line:' + DARK.line + ';' +
    '--accent:#6fb1e6;--warm:#f08a5d;--live:#5cc995;--demo:#e0b060;--demo-bg:#3a2f18;--live-bg:#183a2a;' +
    '--feature:#5a2a1c;--feature-ink:#fbe6da;--feature-soft:#7a4635;--deep:#0b2233;--deep-ink:#dcebf5;--deep-soft:#7fa9c4;--mark:#4a4220;' +
    '--mut:' + DARK.muted + ';--acc:#6fb1e6}' +
    'html[data-theme="dark"],html[data-theme="dark"][data-sky]{--sky1:#1c2b42;--sky2:#18222f}' +
    'html[data-theme="dark"] .sky .cloud{filter:brightness(.38) saturate(.5)!important}' +
    'html[data-theme="dark"] .fchero::before{background:rgba(255,255,255,.04)}' +
    'html[data-theme="dark"] body{background-color:' + DARK.bg + ';color:' + DARK.ink + '}' +
    'html[data-theme="dark"] img:not(.dm-keep){filter:brightness(.82)}' +
    'html[data-theme="dark"] input,html[data-theme="dark"] select,html[data-theme="dark"] textarea{background-color:' + DARK.surface + ';color:' + DARK.ink + ';border-color:' + DARK.line + '}' +
    '.dm-knopf{position:fixed;top:max(10px,env(safe-area-inset-top));right:max(10px,env(safe-area-inset-right));z-index:9999;width:40px;height:40px;border-radius:50%;' +
    'display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:19px;line-height:1;padding:0;' +
    'background:#ffffff;color:#12252E;border:1px solid #d6dde6;box-shadow:0 2px 8px rgba(0,0,0,.12);transition:transform .15s}' +
    '.dm-knopf:hover{transform:scale(1.08)}' +
    'html[data-theme="dark"] .dm-knopf{background:' + DARK.surface + ';color:#FAC775;border-color:#3a4656;box-shadow:0 2px 8px rgba(0,0,0,.4)}' +
    '@media print{.dm-knopf{display:none}}';
  var st = document.createElement('style'); st.id = 'dm-style'; st.textContent = css;
  (document.head || root).appendChild(st);

  /* ---------- Feste (hart kodierte) helle Farben nachträglich abdunkeln ---------- */
  var changed = [];
  function parse(c) { var m = c && c.match(/rgba?\(([^)]+)\)/); if (!m) return null; var p = m[1].split(/[ ,/]+/).filter(Boolean).map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
  function lum(c) { return (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) / 255; }
  function hsl(c) {
    var r = c.r / 255, g = c.g / 255, b = c.b / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), h = 0, s = 0, l = (mx + mn) / 2;
    if (mx !== mn) { var d = mx - mn; s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn); h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; }
    return [h, s, l];
  }
  function hslStr(h, s, l) { return 'hsl(' + Math.round(h) + ',' + Math.round(s * 100) + '%,' + Math.round(l * 100) + '%)'; }
  function set(el, prop, val) {
    changed.push([el, prop, el.style.getPropertyValue(prop), el.style.getPropertyPriority(prop)]);
    el.style.setProperty(prop, val, 'important');
  }
  var SKIP = { IMG: 1, VIDEO: 1, IFRAME: 1, CANVAS: 1, PICTURE: 1, SOURCE: 1, SCRIPT: 1, STYLE: 1, BR: 1, OPTION: 1 };
  function stops(img) {
    if (!img || img === 'none' || /url\(/.test(img) || !/gradient/.test(img)) return null;
    var m = img.match(/rgba?\([^)]+\)/g); if (!m) return null;
    return m.map(parse).filter(function (c) { return c && c.a > .3; });
  }
  function darkTint(c) { var h = hsl(c); return lum(c) > .93 ? DARK.surface : hslStr(h[0], Math.min(h[1], .45), .2); }
  function effBg(el) {
    while (el && el.nodeType === 1) { var ecs = getComputedStyle(el), gs = stops(ecs.backgroundImage); if (gs && gs.length) return gs[0]; var c = parse(ecs.backgroundColor); if (c && c.a > .3) return c; el = el.parentElement; }
    return parse(DARK.bg.replace(/#(..)(..)(..)/, function (_, a, b, d) { return 'rgb(' + parseInt(a, 16) + ',' + parseInt(b, 16) + ',' + parseInt(d, 16) + ')'; }));
  }
  function fixEl(el) {
    if (SKIP[el.tagName] || el.classList.contains('dm-knopf') || el.closest('.sky,#deko,.dm-keep')) return;
    var cs = getComputedStyle(el);
    if (el instanceof SVGElement) {
      if (el.tagName === 'svg' || el.tagName === 'g' || el.tagName === 'defs') return;
      var f = parse(cs.fill), s = parse(cs.stroke);
      if (el.tagName === 'text' || el.tagName === 'tspan') {
        if (f && f.a > .3 && lum(f) < .38) { var hf = hsl(f); set(el, 'fill', hslStr(hf[0], hf[1] * .6, .8)); }
      } else if (el.tagName === 'rect' && f && f.a > .5 && lum(f) > .9) {
        set(el, 'fill', DARK.surface);
      } else if (el.tagName === 'line' || el.tagName === 'polyline') {
        if (s && lum(s) > .8) set(el, 'stroke', '#3a4656');
        else if (s && lum(s) < .25) set(el, 'stroke', '#8a97a6');
      }
      return;
    }
    var bg = parse(cs.backgroundColor);
    if (bg && bg.a > .3 && lum(bg) > .72 && cs.backgroundImage === 'none') {
      if (lum(bg) > .93) set(el, 'background-color', DARK.surface);
      else { var hb = hsl(bg); set(el, 'background-color', hslStr(hb[0], Math.min(hb[1], .45), .2)); }
    }
    var gst = stops(cs.backgroundImage);
    if (gst && gst.length && gst.every(function (c) { return lum(c) > .72; })) {
      set(el, 'background-image', 'linear-gradient(135deg,' + darkTint(gst[0]) + ',' + darkTint(gst[gst.length - 1]) + ')');
    }
    var col = parse(cs.color);
    if (col && (lum(col) < .4 || (lum(col) < .6 && hsl(col)[1] < .2)) && el.childNodes.length) {
      var eb = effBg(el);
      if (eb && lum(eb) < .32) { var hc = hsl(col); set(el, 'color', hc[1] < .15 ? (lum(col) > .3 ? DARK.muted : DARK.ink) : hslStr(hc[0], Math.min(hc[1], .75), .75)); }
    }
    var bc = parse(cs.borderTopColor);
    if (cs.borderTopStyle !== 'none' && parseFloat(cs.borderTopWidth) > 0 && bc && lum(bc) > .8) set(el, 'border-color', DARK.line);
  }
  function fixTree(node) {
    if (root.getAttribute('data-theme') !== 'dark' || !node || node.nodeType !== 1) return;
    fixEl(node);
    var all = node.getElementsByTagName('*');
    for (var i = 0; i < all.length; i++) fixEl(all[i]);
  }
  function undoAll() {
    for (var i = changed.length - 1; i >= 0; i--) { var c = changed[i]; c[0].style.removeProperty(c[1]); if (c[2]) c[0].style.setProperty(c[1], c[2], c[3]); }
    changed = [];
  }
  var queue = [], timer = null;
  var mo = new MutationObserver(function (list) {
    if (root.getAttribute('data-theme') !== 'dark') return;
    for (var i = 0; i < list.length; i++) {
      var m = list[i];
      if (m.type === 'childList') for (var j = 0; j < m.addedNodes.length; j++) queue.push(m.addedNodes[j]);
      else queue.push(m.target);
    }
    if (!timer) timer = setTimeout(function () { timer = null; var q = queue; queue = []; q.forEach(function (n) { if (n.isConnected) fixTree(n); }); }, 250);
  });

  /* ---------- Anwenden ---------- */
  var meta = document.querySelector('meta[name="theme-color"]'), metaLight = meta && meta.content;
  function apply(mode) {
    if (root.getAttribute('data-theme') === mode) return;
    root.setAttribute('data-theme', mode);
    if (meta) meta.content = mode === 'dark' ? DARK.bg : metaLight;
    if (!document.body) return;
    if (mode === 'dark') fixTree(document.body); else undoAll();
    updateButton();
  }
  var btn = null;
  function updateButton() {
    if (!btn) return;
    var dark = root.getAttribute('data-theme') === 'dark';
    btn.textContent = dark ? '☀️' : '🌙';
    btn.title = dark ? 'Hellen Modus einschalten' : 'Dunklen Modus einschalten';
    btn.setAttribute('aria-label', btn.title);
  }
  root.setAttribute('data-theme', 'light');
  var first = currentMode();
  if (first === 'dark') root.setAttribute('data-theme', 'pending');

  function init() {
    btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'dm-knopf';
    btn.addEventListener('click', function () {
      var neu = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      var a = autoState(Date.now());
      try { if (neu === a.mode) localStorage.removeItem(KEY); else localStorage.setItem(KEY, JSON.stringify({ mode: neu, bis: a.next })); } catch (e) {}
      apply(neu);
    });
    document.body.appendChild(btn);
    root.setAttribute('data-theme', 'light');
    apply(currentMode());
    updateButton();
    mo.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'hidden'] });
    setInterval(function () { apply(currentMode()); }, 60000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) apply(currentMode()); });
  }
  /* Bis die Seite geladen ist: dunkle Grundfarben schon setzen, damit nichts aufblitzt */
  if (first === 'dark') {
    var pre = document.createElement('style'); pre.id = 'dm-pre';
    pre.textContent = 'html[data-theme="pending"]{background:' + DARK.bg + '}html[data-theme="pending"] body{background:' + DARK.bg + ';color:' + DARK.ink + '}';
    (document.head || root).appendChild(pre);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
