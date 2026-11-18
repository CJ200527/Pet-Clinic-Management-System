/* clinic.js — header chrome: live clock, filter/bell panels, live toggles, skeleton. */
document.addEventListener('DOMContentLoaded', () => {
  // Live clock under every header label.
  const clocks = new Set(document.querySelectorAll('.live-clock'));
  const tick = () => {
    const text = new Date().toLocaleDateString('en-US',
      { year: 'numeric', month: 'long', day: 'numeric' })
      + ' | ' + new Date().toLocaleTimeString('en-US',
      { hour: 'numeric', minute: '2-digit', second: '2-digit' });
    clocks.forEach((c) => { c.textContent = text; });
  };
  tick();
  setInterval(tick, 1000);

  // Filter + bell panel toggles: every .filter-wrap/.notif-wrap pair on the
  // page (action bars, chart cards, header bell). One panel open at a time.
  const panelHost = (p) => p.closest('.card, .chart-card');
  const pairs = [];
  document.querySelectorAll('.filter-wrap, .notif-wrap').forEach((wrap) => {
    const btn = wrap.querySelector(':scope > button');
    const panel = wrap.querySelector('.filter-panel, .notif-panel');
    if (btn && panel) pairs.push([btn, panel]);
  });
  pairs.forEach(([btn, panel]) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const wasOpen = panel.classList.contains('open');
      pairs.forEach(([, p]) => {
        p.classList.remove('open');
        panelHost(p)?.classList.remove('pop-front');
      });
      if (!wasOpen) {
        panel.classList.add('open');
        panelHost(panel)?.classList.add('pop-front');
      }
    });
  });
  const closeAllPanels = () => {
    document.querySelectorAll('.filter-panel.open, .notif-panel.open')
      .forEach((p) => {
        p.classList.remove('open');
        panelHost(p)?.classList.remove('pop-front');
      });
  };
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.filter-wrap') && !e.target.closest('.notif-wrap')) closeAllPanels();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllPanels();
  });

  // Live refresh toggles: queue board + dashboard (independent states).
  [['liveToggle', 'queueLive'], ['dashLiveToggle', 'dashLive']].forEach(([id, KEY]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    let live = sessionStorage.getItem(KEY) !== 'off';
    const paint = () => {
      btn.classList.toggle('live-off', !live);
      btn.title = live ? 'Pause live refresh' : 'Resume live refresh';
    };
    paint();
    btn.addEventListener('click', () => {
      live = !live;
      sessionStorage.setItem(KEY, live ? 'on' : 'off');
      paint();
    });
    setInterval(() => { if (live) window.location.reload(); }, 30000);
  });

  // Cascade unveil is CSS-only (main.content.cascade) so it starts at first
  // paint — no JS class-adding, which used to flash the content first.

  // Toasts: server-rendered flashes slide in, auto-dismiss, or close on click.
  const dismissToast = (t) => {
    t.classList.add('leaving');
    setTimeout(() => t.remove(), 300);
  };
  document.querySelectorAll('.toast').forEach((t) => {
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => dismissToast(t), 5000);
    t.querySelector('.toast-x')?.addEventListener('click', () => dismissToast(t));
  });

  // Skeleton overlay: only plays on fresh login (?welcome=1), ~1.2s then fade.
  const skeleton = document.getElementById('skeleton-overlay');
  if (skeleton && skeleton.classList.contains('show')) {
    setTimeout(() => {
      skeleton.style.transition = 'opacity 0.4s ease';
      skeleton.style.opacity = '0';
      setTimeout(() => { skeleton.style.display = 'none'; }, 400);
    }, 1200);
  }
});
