/* vet-modals.js — CPSC-pattern popup engine: open/close, fx21 labels, decision flow. */
document.addEventListener('DOMContentLoaded', () => {
  // fx21 floating labels: keep floated while a field has content.
  document.addEventListener('input', (e) => {
    const f = e.target.closest ? e.target.closest('.effect-21') : null;
    if (!f) return;
    f.classList.toggle('has-content', (f.value || '').trim() !== '');
  });
  document.querySelectorAll('.fx21-field .effect-21').forEach((f) => {
    if ((f.value || '').trim() !== '') f.classList.add('has-content');
  });

  // Decision shell: forms with .needs-confirm show it instead of native confirm().
  const shell = document.getElementById('decisionModal');
  const title = document.getElementById('decisionTitle');
  const msg = document.getElementById('decisionMsg');
  const go = document.getElementById('decisionGo');
  let pendingForm = null;
  if (shell) {
    shell.querySelectorAll('[data-decision-close]').forEach((b) => {
      b.addEventListener('click', () => closeVetModal('decisionModal'));
    });
    go?.addEventListener('click', () => {
      closeVetModal('decisionModal');
      if (pendingForm) { const f = pendingForm; pendingForm = null; f.submit(); }
    });
  }
  document.querySelectorAll('form.needs-confirm').forEach((form) => {
    form.addEventListener('submit', (e) => {
      if (!shell) return; // no shell on page: fall back to native submit
      e.preventDefault();
      pendingForm = form;
      if (title) title.textContent = form.dataset.confirmTitle || 'Please confirm';
      if (msg) msg.textContent = form.dataset.confirmMsg || 'Proceed with this action?';
      openVetModal('decisionModal');
    });
  });
});

function openVetModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.add('open');
  m.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-lock');
  const first = m.querySelector('input:not([type=hidden]), select, textarea');
  if (first) setTimeout(() => first.focus(), 120);
}
function closeVetModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.remove('open');
  m.setAttribute('aria-hidden', 'true');
  if (!document.querySelector('.vet-overlay.open')) {
    document.body.classList.remove('modal-lock');
  }
}
