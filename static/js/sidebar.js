// sidebar.js — mobile drawer toggle for the left nav shell.
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('navToggle')?.addEventListener('click', () => {
    document.querySelector('.shell')?.classList.toggle('nav-open');
  });
  document.querySelector('.shell')?.addEventListener('click', (e) => {
    if (e.target.closest('.sidebar') || e.target.closest('#navToggle')) return;
    document.querySelector('.shell')?.classList.remove('nav-open');
  });
});
