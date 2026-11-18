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
  // Forms marked data-confirm-password also collect the admin's own password.
  const shell = document.getElementById('decisionModal');
  const title = document.getElementById('decisionTitle');
  const msg = document.getElementById('decisionMsg');
  const go = document.getElementById('decisionGo');
  const pwWrap = document.getElementById('decisionPwWrap');
  const pwInput = document.getElementById('decisionPassword');
  const pwHint = document.getElementById('decisionPwHint');
  let pendingForm = null;
  let needsPassword = false;

  function resetDecisionPassword(required) {
    needsPassword = required;
    if (pwWrap) pwWrap.hidden = !required;
    if (pwHint) pwHint.hidden = !required;
    if (pwInput) {
      pwInput.value = '';
      pwInput.required = required;
      pwInput.type = 'password';
      pwInput.classList.remove('has-content');
    }
  }

  if (shell) {
    shell.querySelectorAll('[data-decision-close]').forEach((b) => {
      b.addEventListener('click', () => {
        pendingForm = null;
        closeVetModal('decisionModal');
      });
    });
    go?.addEventListener('click', () => {
      if (!pendingForm) { closeVetModal('decisionModal'); return; }
      if (needsPassword && pwInput && !pwInput.value.trim()) {
        pwInput.classList.add('is-invalid');
        pwInput.focus();
        return; // keep the shell open until a password is typed
      }
      const form = pendingForm;
      pendingForm = null;
      if (needsPassword && pwInput) {
        let hidden = form.querySelector('input[data-decision-password]');
        if (!hidden) {
          hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = 'admin_password';
          hidden.dataset.decisionPassword = '1';
          form.appendChild(hidden);
        }
        hidden.value = pwInput.value;
      }
      closeVetModal('decisionModal');
      form.submit();
    });
    pwInput?.addEventListener('input', () => pwInput.classList.remove('is-invalid'));
    pwInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); go?.click(); }
    });
  }
  document.querySelectorAll('form.needs-confirm').forEach((form) => {
    form.addEventListener('submit', (e) => {
      if (!shell) return; // no shell on page: fall back to native submit
      e.preventDefault();
      pendingForm = form;
      if (title) title.textContent = form.dataset.confirmTitle || 'Please confirm';
      if (msg) msg.textContent = form.dataset.confirmMsg || 'Proceed with this action?';
      resetDecisionPassword(form.dataset.confirmPassword === 'required');
      openVetModal('decisionModal');
    });
  });

  // Prevent double submits from modal Save buttons; restore on bfcache return.
  document.querySelectorAll('.vet-overlay .btn-modal-save').forEach((b) => {
    b.dataset.label = b.textContent;
    b.form?.addEventListener('submit', () => {
      b.disabled = true;
      b.textContent = 'Saving…';
    });
  });
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('.vet-overlay .btn-modal-save').forEach((b) => {
      if (b.disabled) { b.disabled = false; b.textContent = b.dataset.label || 'Save'; }
    });
  });
});

function openVetModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  const body = m.querySelector('.vet-modal-body');
  if (body) body.scrollTop = 0;
  m.classList.add('open');
  m.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-lock');
  const fields = m.querySelectorAll('input:not([type=hidden]), select, textarea');
  const first = Array.from(fields).find((el) => el.offsetParent !== null);
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
function togglePwVisibility(btn) {
  const input = btn.closest('.fx21-field')?.querySelector('input');
  if (!input) return;
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.title = show ? 'Hide password' : 'Show password';
  btn.setAttribute('aria-label', btn.title);
}
