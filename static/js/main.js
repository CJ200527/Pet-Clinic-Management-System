// Pet Clinic custom JS: login curtain (ported from EAVS adminCurtain) + helpers.
function openLoginCurtain() {
  const c = document.getElementById('loginCurtain');
  if (!c) return;
  // Carry booking-bar picks into the curtain login so POST /login can prefill booking.
  // Only overwrite when the bar is fully filled (server may have pre-rendered values).
  const svc = document.getElementById('bService')?.value || '';
  const dt = document.getElementById('bDate')?.value || '';
  const tm = document.getElementById('bTime')?.value || '';
  if (svc && dt && tm) {
    document.getElementById('cService').value = svc;
    document.getElementById('cDate').value = dt;
    document.getElementById('cTime').value = tm;
    document.getElementById('cNext').value = '/client/book-appointment';
  }
  c.classList.remove('closing');
  c.classList.add('open');
  c.setAttribute('aria-hidden', 'false');
  document.body.classList.add('curtain-lock');
  setTimeout(() => document.querySelector('#loginCurtain input[name=username]')?.focus(), 600);
}
function closeLoginCurtain() {
  const c = document.getElementById('loginCurtain');
  if (!c) return;
  if (!c.classList.contains('open') && !c.classList.contains('closing')) return;
  c.classList.remove('open');
  c.classList.add('closing');
  c.setAttribute('aria-hidden', 'true');
  setTimeout(() => {
    c.classList.remove('closing');
    document.body.classList.remove('curtain-lock');
  }, 580);
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeLoginCurtain(); });
document.getElementById('loginCurtain')?.addEventListener('click', (e) => {
  if (e.target.classList?.contains('curtain-shade')) closeLoginCurtain();
});
document.addEventListener('DOMContentLoaded', () => {
  // Auto-open curtain: ?auth=open (guards, booking bar, register) or
  // ?auth=failed (bad login → curtain + error popup).
  if (window.AUTH_STATE === 'open') openLoginCurtain();
  else if (window.AUTH_STATE === 'failed') { openLoginCurtain(); openAuthPopup(); }
});
/* Auth error popup: Cancel closes everything, Confirm keeps curtain open to retry. */
function openAuthPopup() {
  const p = document.getElementById('authPopup');
  if (!p) return;
  p.classList.add('open');
  p.setAttribute('aria-hidden', 'false');
}
function authPopupCancel() {
  document.getElementById('authPopup')?.classList.remove('open');
  closeLoginCurtain();
}
function authPopupConfirm() {
  document.getElementById('authPopup')?.classList.remove('open');
  setTimeout(() => document.querySelector('#loginCurtain input[name=username]')?.focus(), 100);
}
/* Login UX: Enter in username jumps to password (never submits half a form);
   on submit, drop readonly first so the browser validates BOTH fields and
   blocks empties itself — the error popup only fires on real bad credentials. */
document.getElementById('loginCurtainForm')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && e.target.name === 'username') {
    e.preventDefault();
    document.querySelector('#loginCurtain input[name=password]')?.focus();
  }
});
document.getElementById('loginCurtainForm')?.addEventListener('submit', (e) => {
  e.target.querySelectorAll('[readonly]').forEach((el) => el.removeAttribute('readonly'));
});
