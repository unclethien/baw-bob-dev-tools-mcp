/* Page behaviour: theme, language, cue tabs, copy buttons, rehearsal timer, run-of-show rail. */
(() => {
  const root = document.documentElement;
  const VI = window.I18N_VI || {};
  const UI = window.I18N_UI || { en: {}, vi: {} };
  const store = {
    get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };
  let lang = root.lang === 'vi' ? 'vi' : 'en';
  const t = key => UI[lang][key] || UI.en[key];

  /* ---------------------------------------------------------------- toast */
  const toast = document.querySelector('[data-toast]');
  let toastTimer;
  function say(msg) {
    toast.textContent = msg;
    toast.setAttribute('data-show', '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.removeAttribute('data-show'), 2200);
  }

  /* ---------------------------------------------------------------- theme: system, light, dark */
  const MODES = ['system', 'light', 'dark'];
  const themeBtn = document.querySelector('[data-theme-toggle]');
  const themeLabel = themeBtn.querySelector('[data-theme-label]');
  let mode = MODES.includes(root.dataset.theme) ? root.dataset.theme : 'system';

  function paintTheme() {
    if (mode === 'system') delete root.dataset.theme; else root.dataset.theme = mode;
    themeBtn.dataset.mode = mode;
    themeLabel.textContent = t(mode);
    themeBtn.setAttribute('aria-label', `${t('theme')}: ${t(mode)}`);
  }
  themeBtn.addEventListener('click', () => {
    mode = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    store.set('demo-theme', mode);
    paintTheme();
  });

  /* ---------------------------------------------------------------- language */
  const nodes = [...document.querySelectorAll('[data-i18n]')];
  const isSvg = n => n instanceof SVGElement;
  const EN = new Map(nodes.map(n => [n, isSvg(n) ? n.textContent : n.innerHTML]));
  const langBtns = [...document.querySelectorAll('[data-lang]')];

  function applyLang(next) {
    lang = next;
    root.lang = next;
    const missing = [];
    for (const n of nodes) {
      const key = n.dataset.i18n;
      let html = EN.get(n);
      if (next === 'vi') {
        if (key in VI) html = VI[key]; else missing.push(key);
      }
      if (isSvg(n)) n.textContent = html; else n.innerHTML = html;
    }
    if (missing.length) console.warn('Missing Vietnamese copy:', [...new Set(missing)]);
    langBtns.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.lang === next)));
    paintTheme();
    paintTimer();
  }
  langBtns.forEach(b => b.addEventListener('click', () => {
    store.set('demo-lang', b.dataset.lang);
    applyLang(b.dataset.lang);
  }));

  /* ---------------------------------------------------------------- tabs (act 1 cues, guardrails ledger) */
  document.querySelectorAll('[data-cues]').forEach(group => {
    const tabs = [...group.querySelectorAll('[role="tab"]')];
    function select(tab, focus) {
      tabs.forEach(x => {
        const on = x === tab;
        x.setAttribute('aria-selected', String(on));
        x.tabIndex = on ? 0 : -1;
        document.getElementById(x.getAttribute('aria-controls')).hidden = !on;
      });
      if (focus) tab.focus();
    }
    tabs.forEach((tab, i) => {
      tab.type = 'button';
      tab.addEventListener('click', () => select(tab, false));
      tab.addEventListener('keydown', e => {
        const moves = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 };
        if (!(e.key in moves)) return;
        e.preventDefault();
        select(tabs[(moves[e.key] + tabs.length) % tabs.length], true);
      });
    });
  });

  /* ---------------------------------------------------------------- copy prompt */
  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      const area = Object.assign(document.createElement('textarea'), { value: text });
      area.setAttribute('readonly', '');
      area.style.cssText = 'position:fixed;opacity:0';
      document.body.append(area);
      area.select();
      const ok = document.execCommand('copy');
      area.remove();
      return ok;
    }
  }
  document.querySelectorAll('[data-copy]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const code = btn.closest('figure').querySelector('code');
      if (!(await copyText(code.textContent.trim()))) { say(t('copyFail')); return; }
      const label = btn.innerHTML;
      btn.setAttribute('data-done', '');
      btn.textContent = t('copied');
      say(t('toast'));
      setTimeout(() => { btn.removeAttribute('data-done'); btn.innerHTML = label; }, 1600);
    });
  });

  /* ---------------------------------------------------------------- rehearsal timer: click to start or pause, hold to reset */
  const timerBtn = document.querySelector('[data-timer]');
  const readout = timerBtn.querySelector('.timer-read');
  let elapsed = 0, startedAt = 0, tick = 0, holdTimer = 0, held = false;

  const running = () => tick !== 0;
  const now = () => elapsed + (running() ? Date.now() - startedAt : 0);
  function paintTimer() {
    const s = Math.floor(now() / 1000);
    readout.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    timerBtn.setAttribute('aria-pressed', String(running()));
    timerBtn.title = running() ? t('timerPause') : t('timerStart');
  }
  function toggleTimer() {
    if (running()) { elapsed = now(); clearInterval(tick); tick = 0; }
    else { startedAt = Date.now(); tick = setInterval(paintTimer, 250); }
    paintTimer();
  }
  function resetTimer() {
    clearInterval(tick); tick = 0; elapsed = 0;
    paintTimer();
    say(t('timerReset'));
  }
  timerBtn.addEventListener('pointerdown', () => {
    held = false;
    holdTimer = setTimeout(() => { held = true; resetTimer(); }, 700);
  });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(ev => timerBtn.addEventListener(ev, () => clearTimeout(holdTimer)));
  timerBtn.addEventListener('click', () => { if (!held) toggleTimer(); held = false; });

  /* presenter keys: T toggles the timer, R resets it (ignored while typing or with modifiers) */
  document.addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey || e.target.closest('input, textarea, [contenteditable]')) return;
    if (e.key === 't' || e.key === 'T') toggleTimer();
    if (e.key === 'r' || e.key === 'R') resetTimer();
  });

  /* ---------------------------------------------------------------- run-of-show rail follows the section in view */
  const railLinks = new Map([...document.querySelectorAll('.rail a')].map(a => [a.hash.slice(1), a]));
  const spy = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      railLinks.forEach((a, id) => a.setAttribute('aria-current', String(id === entry.target.id)));
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  document.querySelectorAll('main > section[id]').forEach(s => spy.observe(s));

  applyLang(lang);
})();
