/* landing-services.js — clickable landing service cards with a comparison dock.
   Each card opens a floating detail panel; several can stay open together,
   each can be minimized to its header, and every panel closes cleanly. */
(function () {
  'use strict';

  function slugify(value) {
    return String(value || '').toLowerCase()
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }

  function money(value) {
    var n = parseFloat(value);
    if (!isFinite(n)) return '';
    return '₱' + n.toLocaleString('en-PH',
      { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var dock = document.getElementById('svcDock');
    if (!dock) return;
    var cards = new Map();
    var panels = new Map();
    var order = [];

    function el(tag, className, text) {
      var node = document.createElement(tag);
      if (className) node.className = className;
      if (text) node.textContent = text;
      return node;
    }

    function makeRow(label, value, highlight) {
      var row = el('div', 'svc-pop-row');
      row.appendChild(el('span', null, label));
      var strong = el('strong', highlight ? 'svc-pop-fee' : null, value);
      row.appendChild(strong);
      return row;
    }

    function buildPanel(card) {
      var key = slugify(card.dataset.svcName);
      var label = card.dataset.svcLabel || card.dataset.svcName || 'Service';
      var icon = (card.dataset.svcIcon || '').replace(/[^a-z0-9-]/gi, '') || 'i-paw';
      var panel = document.createElement('section');
      panel.className = 'svc-pop';
      panel.id = 'svcPop-' + key;
      panel.setAttribute('role', 'group');
      panel.setAttribute('aria-label', label + ' details');

      var head = el('header', 'svc-pop-head');
      var ic = el('span', 'svc-pop-ic');
      ic.setAttribute('aria-hidden', 'true');
      ic.innerHTML = '<svg class="ic"><use href="#' + icon + '"></use></svg>';
      var title = el('span', 'svc-pop-title');
      title.appendChild(el('strong', null, label));
      var sub = el('small', null,
        label === card.dataset.svcName ? 'Fixed service' : card.dataset.svcName);
      title.appendChild(sub);

      var minBtn = document.createElement('button');
      minBtn.type = 'button';
      minBtn.className = 'svc-pop-btn';
      minBtn.dataset.act = 'min';
      minBtn.title = 'Minimize';
      minBtn.setAttribute('aria-label', 'Minimize details');
      minBtn.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-minus"></use></svg>';

      var closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'svc-pop-btn svc-pop-close';
      closeBtn.dataset.act = 'close';
      closeBtn.title = 'Close';
      closeBtn.setAttribute('aria-label', 'Close details');
      closeBtn.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-x"></use></svg>';

      head.appendChild(ic);
      head.appendChild(title);
      head.appendChild(minBtn);
      head.appendChild(closeBtn);

      var body = el('div', 'svc-pop-body');
      var fee = money(card.dataset.svcFee);
      var duration = (card.dataset.svcDuration || '').trim();
      var inclusions = (card.dataset.svcInclusions || '').trim();

      body.appendChild(makeRow('Fee', fee || 'Ask the clinic', !!fee));
      if (duration) body.appendChild(makeRow('Duration', duration));
      body.appendChild(el('p', 'svc-pop-inc-label', 'What is included'));
      var inc = el('p', 'svc-pop-inc',
        inclusions || 'Ask the clinic for the current inclusions.');
      if (!inclusions) inc.classList.add('is-muted');
      body.appendChild(inc);
      if (!fee && !duration && !inclusions) {
        body.appendChild(el('p', 'svc-pop-note',
          'This service is not listed for booking right now.'));
      }

      panel.appendChild(head);
      panel.appendChild(body);
      return panel;
    }

    function syncCard(key) {
      var card = cards.get(key);
      if (!card) return;
      var panel = panels.get(key);
      card.classList.toggle('is-open', !!panel);
      card.setAttribute('aria-expanded',
        panel && !panel.classList.contains('is-min') ? 'true' : 'false');
    }

    function setMinimized(panel, minimized) {
      panel.classList.toggle('is-min', minimized);
      var btn = panel.querySelector('[data-act="min"]');
      if (btn) {
        btn.title = minimized ? 'Expand' : 'Minimize';
        btn.setAttribute('aria-label', minimized ? 'Expand details' : 'Minimize details');
        btn.setAttribute('aria-expanded', minimized ? 'false' : 'true');
        var use = btn.querySelector('use');
        if (use) use.setAttribute('href', minimized ? '#i-plus' : '#i-minus');
      }
      syncCard(panel.id.replace('svcPop-', ''));
    }

    function closePanel(panel) {
      if (!panel || panel.classList.contains('is-closing')) return;
      panel.classList.add('is-closing');
      panel.setAttribute('aria-hidden', 'true');
      window.setTimeout(function () {
        var key = panel.id.replace('svcPop-', '');
        panels.delete(key);
        order = order.filter(function (k) { return k !== key; });
        if (panel.parentNode) panel.parentNode.removeChild(panel);
        syncCard(key);
      }, 170);
    }

    function openFor(card) {
      var key = slugify(card.dataset.svcName);
      var panel = panels.get(key);
      if (panel && panel.classList.contains('is-closing')) {
        panels.delete(key);
        order = order.filter(function (k) { return k !== key; });
        if (panel.parentNode) panel.parentNode.removeChild(panel);
        panel = null;
      }
      if (!panel) {
        panel = buildPanel(card);
        panels.set(key, panel);
        order.push(key);
        dock.appendChild(panel);
      } else if (panel.classList.contains('is-min')) {
        setMinimized(panel, false);
      }
      syncCard(key);
      panel.classList.remove('svc-pop-flash');
      void panel.offsetWidth;
      panel.classList.add('svc-pop-flash');
      panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    document.querySelectorAll('.amenity[data-svc-name]').forEach(function (card) {
      cards.set(slugify(card.dataset.svcName), card);
      card.addEventListener('click', function () { openFor(card); });
    });

    dock.addEventListener('click', function (e) {
      var btn = e.target.closest('.svc-pop-btn');
      var panel = e.target.closest('.svc-pop');
      if (!panel) return;
      if (btn && btn.dataset.act === 'close') { closePanel(panel); return; }
      if (btn && btn.dataset.act === 'min') {
        setMinimized(panel, !panel.classList.contains('is-min'));
        return;
      }
      if (e.target.closest('.svc-pop-head') && panel.classList.contains('is-min')) {
        setMinimized(panel, false);
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || !order.length) return;
      var panel = panels.get(order[order.length - 1]);
      if (panel) { e.preventDefault(); closePanel(panel); }
    });
  });
})();
