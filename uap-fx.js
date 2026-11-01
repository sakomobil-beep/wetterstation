/* UAP Observatory: gemeinsame Animationen für alle Themenseiten */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var css = [
    '.gdd{display:block!important;opacity:0;visibility:hidden;transform:translateX(-50%) translateY(-6px);transition:opacity .18s ease,transform .18s ease,visibility 0s linear .18s}',
    '.gg.open .gdd{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0);transition:opacity .18s ease,transform .18s ease}',
    '@media (max-width:560px){.gdd{transform:translateY(-6px)}.gg.open .gdd{transform:none}}',
    '.gg .caret{display:inline-block;transition:transform .2s}.gg.open .caret{transform:rotate(180deg)}',
    '.gdd a{transition:background .15s,padding-left .15s}.gdd a:hover{padding-left:14px}',
    '.fx-in{opacity:0;transform:translateY(28px);transition:opacity .7s ease,transform .7s cubic-bezier(.2,.7,.2,1)}',
    '.fx-in.fx-on{opacity:1;transform:none}',
    '.stat{transition:transform .25s,border-color .25s}.stat:hover{transform:translateY(-3px);border-color:var(--cyan)}',
    '.hs .ring{transform-box:fill-box;transform-origin:center;animation:fxPulse 2.4s ease-out infinite}',
    '@keyframes fxPulse{0%{transform:scale(1);opacity:.9}70%{transform:scale(1.9);opacity:0}100%{opacity:0}}',
    '.timeline li{transition:background .2s}.timeline li:hover{background:rgba(79,227,240,.05)}',
    '#fxTop{position:fixed;right:16px;bottom:16px;width:42px;height:42px;border-radius:50%;border:1px solid var(--line);background:#121A42;color:var(--cyan);font-size:18px;cursor:pointer;opacity:0;pointer-events:none;transition:opacity .3s;z-index:70}',
    '#fxTop.show{opacity:1;pointer-events:auto}',
    '.hero h1{background:linear-gradient(90deg,#E8ECFF,#4FE3F0,#A77BFF,#E8ECFF);background-size:300% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;animation:fxShine 8s linear infinite}@keyframes fxShine{to{background-position:300% 0}}',
    '.card{transition:box-shadow .3s,border-color .3s}.card:hover{box-shadow:0 0 0 1px rgba(79,227,240,.25),0 10px 40px rgba(79,227,240,.06)}',
    '#fxBar{position:fixed;left:0;top:0;height:3px;width:0;background:linear-gradient(90deg,var(--violet),var(--cyan));z-index:80}'
  ];
  if (reduce) css = css.filter(function (r) { return r.indexOf('fx-in') < 0 && r.indexOf('fxPulse') < 0 && r.indexOf('fxShine') < 0; });
  var st = document.createElement('style'); st.textContent = css.join('\n'); document.head.appendChild(st);

  // Lesefortschritt und "nach oben"
  var bar = document.createElement('div'); bar.id = 'fxBar'; document.body.appendChild(bar);
  var top = document.createElement('button'); top.id = 'fxTop'; top.type = 'button'; top.setAttribute('aria-label', 'Nach oben'); top.textContent = '↑';
  top.onclick = function () { window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' }); };
  document.body.appendChild(top);
  function onScroll() {
    var h = document.documentElement, max = h.scrollHeight - h.clientHeight;
    bar.style.width = (max > 0 ? h.scrollTop / max * 100 : 0) + '%';
    top.classList.toggle('show', h.scrollTop > 900);
  }
  window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

  if (reduce || !('IntersectionObserver' in window)) return;

  // Abschnitte fliegen beim Scrollen ein
  var cards = document.querySelectorAll('section.card, .tile, .stat');
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('fx-on'); io.unobserve(e.target); } });
  }, { threshold: .08, rootMargin: '0px 0px -40px 0px' });
  cards.forEach(function (c, i) {
    var r = c.getBoundingClientRect();
    if (r.top < window.innerHeight) return; // bereits sichtbar: nicht verstecken
    c.classList.add('fx-in');
    if (c.classList.contains('tile') || c.classList.contains('stat')) c.style.transitionDelay = ((i % 4) * 70) + 'ms';
    io.observe(c);
  });

  // Zahlen hochzählen (nur reine Zahlen wie "62", "> 200", "1.370 m")
  document.querySelectorAll('.stat .v').forEach(function (el) {
    var t = el.textContent.trim(), m = t.match(/^([^\d]*)(\d{1,3}(?:\.\d{3})*|\d+)([^\d.,:\/]*)$/);
    if (!m || /\d{1,2}\.\d{1,2}\.\d{2,4}/.test(t)) return;
    var n = parseInt(m[2].replace(/\./g, ''), 10); if (!n || n < 3) return;
    if (/^\d{4}$/.test(m[2]) && n > 1500 && n < 2100) return; // Jahreszahlen nicht zählen
    var pre = m[1], post = m[3];
    var o = new IntersectionObserver(function (es) {
      if (!es[0].isIntersecting) return; o.disconnect();
      var t0 = performance.now();
      (function f(now) { var p = Math.min((now - t0) / 1200, 1), v = Math.round(n * (1 - Math.pow(1 - p, 3)));
        el.textContent = pre + v.toLocaleString('de-DE') + post; if (p < 1) requestAnimationFrame(f); })(t0);
    });
    o.observe(el);
  });
})();
