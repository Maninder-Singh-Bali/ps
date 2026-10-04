/* Synchronous, before styles/body: no server request or scene mutation. */
(function () {
  'use strict';
  const key = 'pixeloid.appearance', choices = ['dark', 'light', 'system'];
  const root = document.documentElement;
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = 'dark';
  try { const saved = localStorage.getItem(key); if (choices.includes(saved)) preference = saved; } catch (_) { /* Private/blocked storage: usable session preference. */ }
  function apply() {
    const theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    document.querySelectorAll('[data-appearance-toggle]').forEach(button => {
      button.setAttribute('aria-checked', String(theme === 'dark'));
      button.title = theme === 'dark' ? 'Switch to Light mode' : 'Switch to Dark mode';
      button.querySelector('[data-theme-label]').textContent = theme === 'dark' ? 'Dark' : 'Light';
    });
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === 'dark' ? '#202225' : '#f5f6f8';
  }
  function choose(value) {
    if (!choices.includes(value)) return;
    preference = value;
    try { localStorage.setItem(key, value); } catch (_) { /* Keep the session choice when storage is blocked. */ }
    apply();
  }
  apply();
  media.addEventListener('change', () => { if (preference === 'system') apply(); });
  window.addEventListener('storage', e => {
    if (e.key === key || e.key === null) { preference = choices.includes(e.newValue) ? e.newValue : 'dark'; apply(); }
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-appearance-toggle]').forEach(button => button.addEventListener('click', () => choose(root.dataset.theme === 'dark' ? 'light' : 'dark')));
    apply();
  });
})();
