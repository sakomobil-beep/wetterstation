/* UAP Observatory: kleine Szenen-Engine für nachgestellte Abläufe.
   UAPScene({svg, cap, btn, steps:[{t, cap, show:[ids], hide:[ids], anim:{id:[keyframes, dauer, wiederholungen]}, sound}]}) */
(function () {
  var ctx;
  function snd(kind) {
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      var o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime;
      o.connect(g); g.connect(ctx.destination);
      if (kind === 'hum') { o.type = 'sawtooth'; o.frequency.value = 58; g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(.04, t + .8); g.gain.exponentialRampToValueAtTime(.0001, t + 3.5); o.start(t); o.stop(t + 3.6); }
      else if (kind === 'beep') { o.type = 'square'; o.frequency.value = 880; g.gain.setValueAtTime(.03, t); g.gain.exponentialRampToValueAtTime(.0001, t + .25); o.start(t); o.stop(t + .3); }
      else if (kind === 'alarm') { o.type = 'square'; o.frequency.setValueAtTime(600, t); o.frequency.setValueAtTime(900, t + .25); o.frequency.setValueAtTime(600, t + .5); o.frequency.setValueAtTime(900, t + .75); g.gain.setValueAtTime(.03, t); g.gain.exponentialRampToValueAtTime(.0001, t + 1); o.start(t); o.stop(t + 1.05); }
      else if (kind === 'boom') { var b = ctx.createBuffer(1, ctx.sampleRate * 1.2, ctx.sampleRate), d = b.getChannelData(0); for (var i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 3); var s = ctx.createBufferSource(), gg = ctx.createGain(); gg.gain.value = .35; s.buffer = b; s.connect(gg); gg.connect(ctx.destination); s.start(); }
      else if (kind === 'shot') { var b2 = ctx.createBuffer(1, ctx.sampleRate * .25, ctx.sampleRate), d2 = b2.getChannelData(0); for (var j = 0; j < d2.length; j++) d2[j] = (Math.random() * 2 - 1) * Math.pow(1 - j / d2.length, 6); var s2 = ctx.createBufferSource(), g2 = ctx.createGain(); g2.gain.value = .3; s2.buffer = b2; s2.connect(g2); g2.connect(ctx.destination); s2.start(); }
    } catch (e) {}
  }
  window.UAPScene = function (o) {
    var svg = document.getElementById(o.svg), cap = document.getElementById(o.cap), btn = document.getElementById(o.btn), mute = document.getElementById(o.mute), timers = [], anims = [];
    if (!svg || !btn) return;
    function q(id) { return svg.querySelector('#' + id); }
    function reset() {
      timers.forEach(clearTimeout); timers = []; anims.forEach(function (a) { try { a.cancel(); } catch (e) {} }); anims = [];
      (o.hidden || []).forEach(function (id) { var e = q(id); if (e) e.style.opacity = 0; });
      (o.visible || []).forEach(function (id) { var e = q(id); if (e) e.style.opacity = 1; });
    }
    reset(); cap.textContent = o.intro || 'Bereit. Drück auf Abspielen.';
    btn.addEventListener('click', function () {
      reset(); btn.disabled = true;
      var end = 0;
      o.steps.forEach(function (s) {
        end = Math.max(end, s.t + 1500);
        timers.push(setTimeout(function () {
          if (s.cap) { cap.textContent = s.cap; cap.animate([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], { duration: 400 }); }
          (s.show || []).forEach(function (id) { var e = q(id); if (e) { e.style.opacity = 1; anims.push(e.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500 })); } });
          (s.hide || []).forEach(function (id) { var e = q(id); if (e) { anims.push(e.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 500, fill: 'forwards' })); setTimeout(function () { e.style.opacity = 0; }, 500); } });
          if (s.anim) Object.keys(s.anim).forEach(function (id) { var e = q(id), a = s.anim[id]; if (e) anims.push(e.animate(a[0], { duration: a[1] || 1000, iterations: a[2] || 1, fill: a[2] === Infinity ? 'none' : 'forwards', easing: a[3] || 'ease-in-out' })); });
          if (s.sound && (!mute || mute.checked)) snd(s.sound);
          if (s.shake) { anims.push(svg.animate([{ transform: 'translate(0,0)' }, { transform: 'translate(-4px,2px)' }, { transform: 'translate(4px,-2px)' }, { transform: 'translate(0,0)' }], { duration: 120, iterations: 6 })); }
        }, s.t));
      });
      timers.push(setTimeout(function () { btn.disabled = false; btn.textContent = '▶ Noch einmal abspielen'; }, end + 500));
    });
  };
})();
