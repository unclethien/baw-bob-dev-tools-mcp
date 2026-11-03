// Slide deck behaviour: theme toggle, slide counter and keyboard paging, and playing each slide's
// animation when it comes into view. Without this script every slide still shows its final state.
(() => {
  const root = document.documentElement;
  const slides = [...document.querySelectorAll('[data-slide]')];
  const counter = document.querySelector('[data-counter]');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');

  // Theme: system (default), light, dark.
  const themeBtn = document.querySelector('[data-theme-toggle]');
  const themeLabel = document.querySelector('[data-theme-label]');
  const order = ['system', 'light', 'dark'];
  const names = { system: 'System', light: 'Light', dark: 'Dark' };
  const current = () => root.dataset.theme || 'system';
  const showTheme = (t) => {
    themeLabel.textContent = names[t];
    themeBtn.setAttribute('aria-label', `Theme: ${names[t].toLowerCase()}`);
  };
  themeBtn.addEventListener('click', () => {
    const next = order[(order.indexOf(current()) + 1) % order.length];
    if (next === 'system') delete root.dataset.theme; else root.dataset.theme = next;
    try { next === 'system' ? localStorage.removeItem('sprint-theme') : localStorage.setItem('sprint-theme', next); } catch (e) {}
    showTheme(next);
  });
  showTheme(current());

  // Which slide is on screen.
  let index = 0;
  const go = (i) => {
    index = Math.max(0, Math.min(slides.length - 1, i)); // set now, so quick key presses add up
    const target = slides[index];
    target.scrollIntoView({ behavior: reduced.matches ? 'auto' : 'smooth', block: 'start' });
  };
  const play = (slide) => {
    // Automated browsers and hidden tabs may pause CSS animations part-way, which would leave the
    // dropped items invisible; they get the final state instead.
    if (reduced.matches || navigator.webdriver || document.hidden) return;
    slide.classList.remove('play');
    void slide.offsetWidth; // restart the CSS animations
    slide.classList.add('play');
  };

  const seen = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      index = slides.indexOf(e.target);
      counter.textContent = `${index + 1} / ${slides.length}`;
      showNotes();
      if (!e.target.dataset.played) { e.target.dataset.played = '1'; play(e.target); }
    }
  }, { rootMargin: '-45% 0px -45% 0px' });
  slides.forEach((s) => seen.observe(s));

  // Presenter notes: the current slide's talk track in a panel at the bottom.
  const notesBtn = document.querySelector('[data-notes-toggle]');
  const panel = document.getElementById('notes-panel');
  const showNotes = () => {
    if (panel.hidden) return;
    const slide = slides[index];
    const tpl = slide.querySelector('template[data-notes]');
    panel.querySelector('[data-notes-title]').textContent = `Slide ${index + 1}. ${slide.querySelector('h1, h2').textContent}`;
    panel.querySelector('[data-notes-time]').textContent = tpl?.dataset.time || '';
    panel.querySelector('[data-notes-body]').replaceChildren(tpl ? tpl.content.cloneNode(true) : '');
  };
  const toggleNotes = () => {
    panel.hidden = !panel.hidden;
    notesBtn.setAttribute('aria-pressed', String(!panel.hidden));
    document.body.classList.toggle('notes-on', !panel.hidden);
    showNotes();
  };
  notesBtn.addEventListener('click', toggleNotes);

  document.querySelectorAll('[data-step]').forEach((b) => b.addEventListener('click', () => go(index + Number(b.dataset.step))));
  document.querySelector('[data-replay]')?.addEventListener('click', (e) => play(e.currentTarget.closest('[data-slide]')));

  // Presenter keys: arrows, Page Up/Down, Space, Home, End.
  addEventListener('keydown', (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey || /input|textarea|select/i.test(e.target.tagName)) return;
    const next = ['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(e.key);
    const prev = ['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key);
    if (next || prev) { e.preventDefault(); go(index + (next ? 1 : -1)); }
    else if (e.key === 'n' || e.key === 'N') toggleNotes();
    else if (e.key === 'Home') { e.preventDefault(); go(0); }
    else if (e.key === 'End') { e.preventDefault(); go(slides.length - 1); }
  });
})();
