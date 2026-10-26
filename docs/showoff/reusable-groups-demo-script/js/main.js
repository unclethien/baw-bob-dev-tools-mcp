/* Page behaviour: theme, tabs, copy buttons, demo timer, run-of-show rail, and the rehearsal scorecard. */
(() => {
  const root = document.documentElement;
  const UI = {
    system: 'System', light: 'Light', dark: 'Dark', theme: 'Theme',
    copied: 'Copied', toast: 'Copied. Paste it where it belongs.', copyFail: 'Copy failed. Select the text and copy it.',
    timerStart: 'Start the demo timer', timerPause: 'Pause the demo timer. Hold to reset.', timerReset: 'Timer reset',
    results: 'Results copied. Paste them in your notes.', cleared: 'Ticks cleared'
  };
  const store = {
    get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };
  const t = key => UI[key];

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

  /* ---------------------------------------------------------------- tabs (how it works, act cues, closing ledger) */
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

  /* ---------------------------------------------------------------- copy a prompt or command */
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

  /* ---------------------------------------------------------------- demo timer: click to start or pause, hold to reset */
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

  /* ---------------------------------------------------------------- tool order: stagger each step in */
  document.querySelectorAll('.seq').forEach(list => [...list.children].forEach((li, i) => li.style.setProperty('--i', i)));

  /* ---------------------------------------------------------------- scorecard: ticks persist, results copy as text */
  const KEY = 'reusable-groups-demo-checks';
  const boxes = [...document.querySelectorAll('[data-checks] input[type="checkbox"]')];
  const fill = document.querySelector('[data-meter-fill]');
  const read = document.querySelector('[data-meter-read]');
  const saved = new Set((store.get(KEY) || '').split(',').filter(Boolean));
  boxes.forEach(box => { box.checked = saved.has(box.value); });

  function paintChecks() {
    const done = boxes.filter(b => b.checked).length;
    fill.style.width = `${(100 * done) / boxes.length}%`;
    read.textContent = `${done} of ${boxes.length}`;
    store.set(KEY, boxes.filter(b => b.checked).map(b => b.value).join(','));
  }
  boxes.forEach(box => box.addEventListener('change', paintChecks));

  document.querySelector('[data-checks-copy]').addEventListener('click', async () => {
    const lines = [...document.querySelectorAll('[data-checks]')].flatMap(group => [
      group.querySelector('legend').textContent,
      ...[...group.querySelectorAll('label')].map(label => {
        const box = label.querySelector('input');
        return `${box.checked ? '[x]' : '[ ]'} ${box.value}. ${label.querySelector('span').textContent.trim()}`;
      })
    ]);
    say((await copyText(lines.join('\n'))) ? t('results') : t('copyFail'));
  });
  document.querySelector('[data-checks-clear]').addEventListener('click', () => {
    boxes.forEach(b => { b.checked = false; });
    paintChecks();
    say(t('cleared'));
  });

  paintTheme();
  paintTimer();
  paintChecks();
})();
