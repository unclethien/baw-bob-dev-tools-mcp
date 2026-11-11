// Check the Modernizer Widgets bundle offline: renders every widget in scripts/widget-harness.html through fake
// BAW Coach Views (and as Coach Designer previews), and checks the contract, validation, visibility, the events, the Button
// and the Theme. Sections 0, 2, 2b, 11 and 12 cover every contract widget, so a new widget is checked without editing it.
//
// Usage: npm run build, then node scripts/check-widgets.mjs [--shot <png>] (also writes <png>-contract.png, every contract widget)
// Exit code 1 when a check fails.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseArgs } from 'node:util';
import puppeteer from 'puppeteer-core';
import { findBrowser } from './browsers.mjs';

const { values: args } = parseArgs({ options: { shot: { type: 'string' } } });
const harness = new URL('./widget-harness.html', import.meta.url).href;
// Every widget of the toolkit's contract (widgets/modernizer-widgets.json), so a new widget is covered without editing this script.
const contract = JSON.parse(fs.readFileSync(new URL('../widgets/modernizer-widgets.json', import.meta.url), 'utf8')).widgets;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: findBrowser(), headless: 'new',
  args: ['--allow-file-access-from-files', `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), 'mdw-check-'))}`],
});
const results = [];
const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail });

async function fresh() {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(harness);
  await page.evaluate((events, names, accessors) => { Object.assign(window.harness, { events, optionNames: names, accessors }); },
    Object.fromEntries(contract.map((w) => [w.kind, w.events || {}])), Object.fromEntries(contract.map((w) => [w.kind, w.options.map((o) => o.name)])),
    Object.fromEntries(contract.map((w) => [w.kind, w.accessor || null])));
  return { page, errors };
}
const text = (page, selector) => page.$eval(selector, (el) => el.textContent.trim()).catch(() => null);

try {
  // 0. Every contract entry is complete, so Coach Designer shows it as the UI Toolkit shows its controls and the
  //    widget host can run its events (the rules a new widget's entry follows, in the modernizer-widget skill).
  {
    const full = JSON.parse(fs.readFileSync(new URL('../widgets/modernizer-widgets.json', import.meta.url), 'utf8'));
    const catalog = full.events || {};
    // The UI Toolkit's controls, read from BAW (server/ui_toolkit_reference.py): a widget with a uiToolkit counterpart
    // has its settings and events, or says in leftOut why one cannot work.
    const reference = JSON.parse(fs.readFileSync(new URL('../widgets/ui-toolkit-reference.json', import.meta.url), 'utf8'));
    const ownTypes = full.types || {};
    const aliases = full.uiToolkitNames || {};
    const TYPES = ['String', 'Integer', 'Decimal', 'Boolean', 'Date', 'NameValuePair', ...Object.keys(ownTypes)];
    const GROUPS = ['Behavior', 'Items', 'Appearance'];
    const CATEGORIES = ['Input', 'Informational', 'Layout', 'Operational', 'Chart'];
    // Names the view or the coach spec already uses for something else.
    const RESERVED = ['label', 'helpText', 'help', 'visibility', 'path', 'type', 'readonly', 'required', 'binding'];
    const problems = [];
    for (const [name, choices] of Object.entries(ownTypes)) {
      if (!reference.types[name]) problems.push(`type ${name}: the UI Toolkit has no dropdown type of that name (ui-toolkit-reference.json types)`);
      else if (JSON.stringify(choices) !== JSON.stringify(reference.types[name])) problems.push(`type ${name}: copy its choices from ui-toolkit-reference.json, so a value carried over from a UI Toolkit coach means the same`);
    }
    const seen = { kind: new Set(), view: new Set() };
    for (const w of contract) {
      const at = w.kind || JSON.stringify(w).slice(0, 40);
      const bad = (what) => problems.push(`${at}: ${what}`);
      if (!/^[a-z][a-z0-9]*$/.test(w.kind || '')) bad('kind must be lower-case letters and digits');
      for (const key of ['kind', 'view']) { if (seen[key].has(w[key])) bad(`${key} is not unique`); seen[key].add(w[key]); }
      if (w.binding !== null && !['String', 'Integer', 'Decimal', 'Boolean', 'Date'].includes(w.binding)) bad(`binding ${w.binding} is not String, Integer, Decimal, Boolean, Date or null`);
      if (typeof w.label !== 'boolean' || typeof w.boundary !== 'boolean') bad('label and boundary must be true or false');
      if (!w.preview || !('value' in w.preview)) bad('preview needs a value (null when it binds nothing)');
      if (!Array.isArray(w.tags) || !w.tags.some((t) => CATEGORIES.includes(t))) bad(`tags need one of ${CATEGORIES.join(', ')}`);
      const control = w.uiToolkit === undefined ? null : reference.controls[w.uiToolkit];
      if (w.uiToolkit !== undefined && !control) bad(`uiToolkit ${w.uiToolkit} is not a UI Toolkit control (python3 server/ui_toolkit_reference.py show <control> lists them)`);
      if (w.leftOut && w.uiToolkit === undefined) bad('leftOut lists a counterpart\'s settings, so it needs uiToolkit');
      const groups = new Set([...GROUPS, ...(control ? control.settings.map((st) => st.group).filter(Boolean) : [])]);
      for (const o of w.options || []) {
        if (!o.name || !o.label) bad('an option needs a name and a label');
        if (!TYPES.includes(o.type || 'String')) bad(`option ${o.name}: type ${o.type} is not one of ${TYPES.join(', ')} (copy a UI Toolkit dropdown type into the top-level types)`);
        if (!groups.has(o.group)) bad(`option ${o.name}: group must be ${[...groups].join(', ')}`);
        if (o.name && o.name.startsWith('eventON_')) bad(`option ${o.name}: an event goes in events, not options`);
        if (RESERVED.includes(o.name) || (o.name || '').startsWith('@')) bad(`option ${o.name}: the name is taken (${RESERVED.join(', ')}); name it after what it holds, e.g. barLabel`);
      }
      const events = w.events || {};
      if (!('eventON_LOAD' in events)) bad('events need eventON_LOAD');
      for (const [name, argNames] of Object.entries(events)) {
        if (!(name in catalog)) bad(`event ${name} is not in the top-level events (${Object.keys(catalog).join(', ')})`);
        if (!Array.isArray(argNames) || argNames.some((a) => typeof a !== 'string')) bad(`event ${name}: its arguments must be a list of names`);
      }
      if (w.binding !== null && (events.eventON_CHANGE || []).length !== 2) bad('a widget with a binding needs eventON_CHANGE with two arguments (new and old value)');
      if (w.boundary && !('eventON_CLICK' in events && 'eventON_BOUNDARYEVT' in events)) bad('a boundary widget needs eventON_CLICK and eventON_BOUNDARYEVT');
      if (w.binding !== null && !w.accessor) bad('a widget with a binding needs an accessor [getter, setter]');
      if (w.accessor && !(Array.isArray(w.accessor) && w.accessor.length === 2 && w.accessor.every((m) => /^[a-z][A-Za-z]*$/.test(m)))) bad('accessor must be [getter, setter] method names');
      if (w.accessor && w.binding === null && !w.label) bad('an accessor of a widget with no binding reads the label, so label must be true');
      if (!fs.existsSync(new URL(`../widgets/icons/${w.kind}.svg`, import.meta.url))) bad(`no icon widgets/icons/${w.kind}.svg`);
      if (control) {
        const left = w.leftOut || {};
        const reason = (name) => typeof left[name] === 'string' && left[name].trim() !== '';
        const mine = Object.fromEntries((w.options || []).map((o) => [o.name, o]));
        for (const st of control.settings) {
          const o = mine[aliases[st.name] || st.name];
          if (!o) {
            if (!reason(st.name)) bad(`the UI Toolkit ${w.uiToolkit} has "${st.label}" (${st.name}, ${st.group || 'no section'}): add it as an option, or list it in leftOut with the reason it cannot work`);
            continue;
          }
          if ((o.group || null) !== (st.group || null)) bad(`option ${o.name}: the UI Toolkit ${w.uiToolkit} shows it under ${st.group || 'no section'}, so use that group`);
          if (reference.types[st.type] && o.type !== st.type) bad(`option ${o.name}: give it the UI Toolkit's type ${st.type} (copied into the top-level types), so authors get the same dropdown`);
          if (st.name in left) bad(`leftOut ${st.name}: the widget has it, so take it out of leftOut`);
        }
        for (const e of control.events) {
          if (e.name in events) { if (e.name in left) bad(`leftOut ${e.name}: the widget has it, so take it out of leftOut`); }
          else if (!reason(e.name)) bad(`the UI Toolkit ${w.uiToolkit} has the event "${e.label}" (${e.name}): add it to events (and the top-level events), or list it in leftOut with the reason it cannot work`);
        }
        for (const name of Object.keys(left)) {
          if (!control.settings.some((st) => st.name === name) && !control.events.some((e) => e.name === name)) bad(`leftOut ${name} is not a setting or event of the UI Toolkit ${w.uiToolkit}`);
        }
      }
    }
    const parity = (pr) => /UI Toolkit|leftOut|type /.test(pr);
    check('every contract entry is complete (groups, events, accessor, icon)', !problems.some((pr) => !parity(pr)), problems.filter((pr) => !parity(pr)));
    check('every widget has its UI Toolkit counterpart\'s settings and events, or says why not (leftOut)', !problems.some(parity), problems.filter(parity));
  }

  // 1. Every widget renders at runtime, through the widget host.
  {
    const { page, errors } = await fresh();
    await page.evaluate((pairs) => {
      // NameValuePair items as BAW hands them over: objects read with get().
      const nvp = { items: pairs.map(([name, value]) => ({ get: (key) => (key === 'name' ? name : value) })) };
      const v = (spec) => harness.view(spec);
      v({ kind: 'theme', id: 'Theme1', options: { theme: JSON.stringify({ primary: '#7a1fa2', banner: { product: 'ACME Insurance' } }) } });
      v({ kind: 'header', id: 'Header1', options: { title: 'Requester', subtitle: 'ZZ App', intro: 'Tell us who you are.', steps: { items: ['One', 'Two'] }, step: 1 } });
      v({ kind: 'errors', id: 'Errors1' });
      v({ kind: 'text', id: 'Text1', label: 'Name', value: 'Ada', options: { example: 'Ada Lovelace' } });
      v({ kind: 'textarea', id: 'Area1', label: 'Notes', value: 'Hello' });
      v({ kind: 'number', id: 'Num1', label: 'Count', value: 3 });
      v({ kind: 'date', id: 'Date1', label: 'Due', value: new Date(2026, 0, 15) });
      v({ kind: 'checkbox', id: 'Check1', label: 'Agree', value: true });
      v({ kind: 'select', id: 'Sel1', label: 'Plan', value: 'b', options: { options: nvp } });
      v({ kind: 'radio', id: 'Rad1', label: 'Size', value: 'a', options: { options: nvp } });
      v({ kind: 'button', id: 'Button1', label: 'Next >', options: { kind: 'primary' } });
    }, [['Alpha', 'a'], ['Beta', 'b']]);
    await sleep(300);
    check('text renders with its value', await page.$eval('[data-kind=text] input', (i) => i.value) === 'Ada');
    check('textarea renders', await page.$eval('[data-kind=textarea] textarea', (i) => i.value) === 'Hello');
    check('number renders', await page.$eval('[data-kind=number] input', (i) => i.value) === '3');
    check('date renders', (await page.$eval('[data-kind=date] input', (i) => i.value)).includes('01/15/2026'));
    check('checkbox renders checked', await page.$eval('[data-kind=checkbox] input', (i) => i.checked));
    const selectOptions = await page.$$eval('[data-kind=select] option', (o) => o.map((x) => x.textContent));
    check('select lists NameValuePair options', JSON.stringify(selectOptions) === JSON.stringify(['Choose an option', 'Alpha', 'Beta']), selectOptions);
    check('select shows its value', await page.$eval('[data-kind=select] select', (s) => s.value) === 'b');
    const radios = await page.$$eval('[data-kind=radio] .pp--radio-button__label', (l) => l.map((x) => x.textContent.trim()));
    check('radio lists its options', JSON.stringify(radios) === JSON.stringify(['Alpha', 'Beta']), radios);
    check('header shows title and steps', await text(page, '[data-kind=header] h1') === 'Requester'
      && (await page.$$('[data-kind=header] .pp--progress-step')).length === 2);
    check('header shows the intro text', await text(page, '[data-kind=header] .pp-lead') === 'Tell us who you are.');
    check('header takes the product name from the Theme widget', await text(page, '[data-kind=header] .pp-brand-mark') === 'ACME Insurance');
    check('the theme colour reaches every widget', await page.$eval('[data-kind=text] .pp-widget', (el) => el.style.getPropertyValue('--pp-theme-primary')) === '#7a1fa2');
    check('theme draws nothing on the page', await page.$eval('[data-kind=theme]', (el) => el.textContent.trim()) === '');
    check('error summary is empty before validation', await page.$eval('[data-kind=errors]', (el) => el.textContent.trim()) === '');
    check('button label is cleaned up', await text(page, '[data-kind=button] button') === 'Next');
    check('widgets have no page padding', await page.$eval('[data-kind=text] .pp-widget', (el) => getComputedStyle(el).paddingTop) === '0px');
    check('no page errors (runtime)', errors.length === 0, errors);
    if (args.shot) await page.screenshot({ path: args.shot, fullPage: true });
    await page.close();
  }

  // 2. Coach Designer previews: every widget draws, and follows label and option changes.
  {
    const { page, errors } = await fresh();
    const kinds = contract.map((w) => w.kind);
    await page.evaluate((list) => {
      window.previews = {};
      list.forEach(({ kind, value }) => { window.previews[kind] = { state: { label: kind + ' label', options: {}, value } }; });
      list.forEach(({ kind }) => { window.previews[kind].handle = harness.preview(kind, window.previews[kind].state).handle; });
    }, contract.map((w) => ({ kind: w.kind, value: w.preview.value })));
    await sleep(300);
    const empty = [];
    for (const kind of kinds) if (!(await page.$eval(`[data-preview=${kind}]`, (el) => el.textContent.trim() || el.querySelector('input,select,textarea,button')))) empty.push(kind);
    check('every widget draws a preview', empty.length === 0, empty);
    check('theme preview shows a marker', await text(page, '[data-preview=theme]') === 'Theme');
    check('error summary preview shows a sample', (await text(page, '[data-preview=errors]') || '').includes('needs attention'));
    await page.evaluate(() => {
      const p = window.previews.text;
      p.state.label = 'Spike test';
      p.state.options.example = 'Hello';
      p.state.value = '';
      p.handle.update();
      const h = window.previews.header;
      h.state.options.title = 'New title';
      h.handle.update();
    });
    await sleep(100);
    check('preview follows a label change', await text(page, '[data-preview=text] label') === 'Spike test');
    check('preview shows the Example as placeholder', await page.$eval('[data-preview=text] input', (i) => i.placeholder) === 'Hello');
    check('preview follows an option change', await text(page, '[data-preview=header] h1') === 'New title');
    await page.click('[data-preview=button] button');
    await page.click('[data-preview=text] input');
    check('a preview button never fires', (await page.evaluate(() => harness.triggered.length)) === 0);
    check('no page errors (preview)', errors.length === 0, errors);
    await page.close();
  }

  // 2b. Every widget of the contract renders at runtime with its sample value, and a field widget shows its label.
  {
    const { page, errors } = await fresh();
    await page.evaluate((list) => {
      list.forEach(({ kind, value }) => harness.view({ kind, id: `Any_${kind}`, label: `${kind} label`, value }));
    }, contract.map((w) => ({ kind: w.kind, value: w.preview.value })));
    await sleep(300);
    const missing = [];
    for (const w of contract) {
      const cell = `[data-kind=${w.kind}]`;
      const drawn = await page.$eval(`${cell} .pp-widget`, () => true).catch(() => false);
      const labelled = w.binding === null || ((await text(page, cell)) || '').includes(`${w.kind} label`);
      if (!drawn || !labelled) missing.push(w.kind);
    }
    check('every contract widget renders at runtime', missing.length === 0, missing);
    // A Carbon component whose styles the bundle lacks still renders, unstyled: every Carbon block a widget uses
    // (pp--toggle for pp--toggle__switch) must appear in some CSS rule. A new widget adds its own <kind>.scss.
    const unstyled = await page.evaluate(() => {
      const selectors = [];
      const collect = (rule) => { if (rule.selectorText) selectors.push(rule.selectorText); for (const r of rule.cssRules || []) collect(r); };
      for (const sheet of document.styleSheets) { try { for (const r of sheet.cssRules) collect(r); } catch { /* cross-origin */ } }
      const styled = new Set(selectors.join(' ').match(/\.pp--[\w-]+/g));
      const out = {};
      for (const cell of document.querySelectorAll('[data-kind]')) {
        const blocks = {}; // block -> does any of its classes (modifiers aside) have a rule
        cell.querySelectorAll('[class]').forEach((el) => el.classList.forEach((c) => {
          const [block, ...rest] = c.startsWith('pp--') ? c.slice(4).split('--') : [];
          if (block === undefined || rest.length) return;
          const name = `pp--${block.split('__')[0]}`;
          blocks[name] = blocks[name] || styled.has(`.${c}`);
        }));
        // Carbon also writes classes it gives no rule of their own (pp--modal-tall on a pp--modal): a block is styled
        // when a styled block of the same widget starts its name.
        const bare = Object.keys(blocks).filter((b) => !blocks[b] && !Object.keys(blocks).some((o) => blocks[o] && b.startsWith(`${o}-`)));
        if (bare.length) out[cell.dataset.kind] = bare;
      }
      return out;
    });
    const fix = Object.fromEntries(Object.entries(unstyled).map(([kind, bare]) => [kind, bare.map((b) => `${b}: add @use '@carbon/react/scss/components/<name>'; to src/widgets/${kind}.scss`)]));
    check('every Carbon component a widget uses is styled', Object.keys(unstyled).length === 0, fix);
    // The toolkit's Carbon classes start with pp-- (ClassPrefix "pp"); a cds-- class has no styles here.
    const foreign = await page.evaluate(() => {
      const out = {};
      for (const cell of document.querySelectorAll('[data-kind]')) {
        const found = [...new Set([...cell.querySelectorAll('[class]')].flatMap((el) => [...el.classList]).filter((c) => c.startsWith('cds--') || c.startsWith('bx--')))];
        if (found.length) out[cell.dataset.kind] = found.map((c) => `${c}: write pp--${c.replace(/^(cds|bx)--/, '')}`);
      }
      return out;
    });
    check('every Carbon class a widget writes has the toolkit prefix pp--', Object.keys(foreign).length === 0, foreign);
    check('no page errors (contract widgets)', errors.length === 0, errors);
    // The contract widgets with their sample values, for a look at widgets the first screenshot does not show.
    if (args.shot) await page.screenshot({ path: args.shot.replace(/(\.png)?$/, '-contract.png'), fullPage: true });
    await page.close();
  }

  // 3. Validation: required, pattern, min; screen order; the Button blocks and then fires; busy state resets.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      harness.view({ kind: 'errors', id: 'Errors1' });
      harness.view({ kind: 'text', id: 'Name', label: 'Name', visibility: 'REQUIRED' });
      harness.view({ kind: 'text', id: 'Zip', label: 'Zip', value: 'abc', options: { pattern: '^[0-9]+$' } });
      harness.view({ kind: 'number', id: 'Qty', label: 'Quantity', value: 2, options: { min: 5 } });
      harness.view({ kind: 'checkbox', id: 'Terms', label: 'Accept terms', visibility: 'REQUIRED', value: false, options: { message: 'Please accept the terms' } });
      harness.view({ kind: 'button', id: 'Next', label: 'Next' });
    });
    await sleep(200);
    await page.click('[data-kind=button] button');
    await sleep(100);
    const summary = await text(page, '[data-kind=errors]');
    check('invalid fields block the Button', (await page.evaluate(() => harness.triggered.length)) === 0);
    check('error summary counts the errors', (summary || '').includes('4 fields need attention'), summary);
    check('error summary lists them in screen order', (summary || '').includes('Name is required · Zip is not valid · Quantity must be at least 5'), summary);
    check('each field shows its own error', (await text(page, '[data-kind=text] .pp--form-requirement')) === 'Name is required');
    check('a custom message is used', (await page.$$eval('[data-kind=checkbox] *', (els) => els.map((e) => e.textContent).join(' '))).includes('Please accept the terms'));
    await page.type('[data-kind=text] input', 'Ada');
    await page.$eval('input#pp-Zip', (i) => i.select());
    await page.type('input#pp-Zip', '12345');
    await page.$eval('input#pp-Qty', (i) => i.select());
    await page.type('input#pp-Qty', '7');
    await page.click('[data-kind=checkbox] label');
    await page.click('[data-kind=button] button');
    await sleep(5);
    const fired = await page.evaluate(() => harness.triggered);
    check('a valid page fires the boundary event once', fired.length === 1 && fired[0].id === 'Next', fired);
    check('the button asks BAW to call back', fired[0]?.callBackForAll === true);
    check('the button is busy while BAW handles the event', await page.$eval('[data-kind=button] button', (b) => b.disabled));
    await sleep(100);
    check('the button takes presses again when the coach stays', !(await page.$eval('[data-kind=button] button', (b) => b.disabled)));
    check('the error summary clears', ((await text(page, '[data-kind=errors]')) || '') === '');
    check('no page errors (validation)', errors.length === 0, errors);
    await page.close();
  }

  // 3b. Show validation marker: on an error, a checkbox with the option shows a warning icon whose tooltip gives the
  // error; one without it shows only the error text. The marker goes once the error is fixed.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      harness.view({ kind: 'checkbox', id: 'Marked', label: 'Marked', visibility: 'REQUIRED', value: false, options: { showValidationMarker: true } });
      harness.view({ kind: 'checkbox', id: 'Plain', label: 'Plain', visibility: 'REQUIRED', value: false, options: { showValidationMarker: 'false' } });
      harness.view({ kind: 'button', id: 'Next', label: 'Next' });
    });
    await sleep(200);
    const marker = (id) => page.evaluate((i) => {
      const cell = document.getElementById(`pp-${i}`).closest('[data-kind=checkbox]');
      const m = cell.querySelector('.pp-validation-marker');
      return m && { label: m.getAttribute('aria-label'), tooltip: cell.querySelector('.pp--popover-content')?.textContent, icon: !!m.querySelector('svg') };
    }, id);
    check('no marker before validation', !(await marker('Marked')));
    await page.click('[data-kind=button] button');
    await sleep(100);
    const shown = await marker('Marked');
    check('showValidationMarker shows a warning icon on an error', shown?.icon === true, shown);
    check('the marker\'s tooltip gives the error', shown?.label === 'Marked is required' && shown?.tooltip === 'Marked is required', shown);
    check('without showValidationMarker there is no marker', !(await marker('Plain')));
    check('the error text still shows with the marker', (await page.$$eval('[data-kind=checkbox] .pp--form-requirement', (els) => els.map((e) => e.textContent))).includes('Marked is required'));
    await page.click('label[for=pp-Marked]');
    await page.click('label[for=pp-Plain]');
    await page.click('[data-kind=button] button');
    await sleep(100);
    check('the marker goes once the error is fixed', !(await marker('Marked')));
    check('no page errors (validation marker)', errors.length === 0, errors);
    await page.close();
  }

  // 3c. The UI Toolkit's common settings: Width, Label placement and Label width (any widget that declares them, by
  // the widget host), Size (a Carbon size), the Radio validation marker and the Toggle's On and Off labels.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      const items = [{ name: 'Alpha', value: 'A' }, { name: 'Beta', value: 'B' }];
      harness.view({ kind: 'text', id: 'Wide', label: 'Wide', options: { width: '320' } });
      harness.view({ kind: 'select', id: 'Left', label: 'Left', options: { labelPlacement: 'L', labelWidth: '160px', options: items } });
      harness.view({ kind: 'text', id: 'Top', label: 'Top', options: { labelPlacement: 'T', labelWidth: '160px' } });
      harness.view({ kind: 'text', id: 'Small', label: 'Small', options: { sizeStyle: 'S' } });
      harness.view({ kind: 'number', id: 'Large', label: 'Large', options: { sizeStyle: 'L' } });
      harness.view({ kind: 'textarea', id: 'Notes', label: 'Notes', options: { sizeStyle: 'L' } });
      harness.view({ kind: 'button', id: 'Tiny', label: 'Tiny', options: { sizeStyle: 'X', width: '300px' } });
      harness.view({ kind: 'toggle', id: 'Switch', label: 'Switch', value: true, options: { onLabel: 'Enabled', offLabel: 'Disabled', sizeStyle: 'L' } });
      harness.view({ kind: 'radio', id: 'Tier', label: 'Tier', visibility: 'REQUIRED', options: { options: items, showValidationMarker: true, labelPlacement: 'L' } });
      harness.view({ kind: 'button', id: 'Next', label: 'Next' });
    });
    await sleep(200);
    const box = (selector) => page.$eval(selector, (el) => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, width: r.width, height: r.height }; });
    const root = (id) => `#pp-${id}`;
    const host = (id) => page.$eval(root(id), (el) => el.closest('.pp-widget').className);
    check('Width sets the widget\'s width (a bare number is pixels)', Math.round((await page.$eval(root('Wide'), (el) => el.closest('.pp-widget').getBoundingClientRect().width))) === 320);
    const label = await page.$eval(root('Left'), (el) => { const r = el.closest('.pp-widget').querySelector('.pp--label').getBoundingClientRect(); return { right: r.right, width: r.width }; });
    const input = await box(root('Left'));
    check('Label placement Left puts the label beside the input', (await host('Left')).includes('pp-label-left') && label.right <= input.left, { label, input });
    check('Label width sets the label column', Math.round(label.width) === 160, label);
    check('Label placement Top keeps the label above', !(await host('Top')).includes('pp-label-left'));
    check('Size Small and Large reach the Carbon input', await page.$eval(root('Small'), (el) => el.className.includes('pp--text-input--sm'))
      && await page.$eval('[data-kind=number] .pp--number', (el) => el.className.includes('pp--number--lg')));
    check('Size on a Text Area is styled on the widget', (await host('Notes')).includes('pp-size-L'));
    const tiny = await page.$eval('[data-kind=button] .pp--btn', (el) => ({ small: el.className.includes('pp--btn--sm'), width: Math.round(el.getBoundingClientRect().width) }));
    check('a Button takes the UI Toolkit\'s Size and Width', tiny.small && tiny.width === 300, tiny);
    check('the Toggle shows its On label and takes Size', (await text(page, '[data-kind=toggle] .pp--toggle__text')) === 'Enabled' && (await host('Switch')).includes('pp-size-L'));
    await page.$$eval('[data-kind=button] button', (els) => els[els.length - 1].click());
    await sleep(100);
    check('a Radio group with Show validation marker shows it on an error',
      await page.$eval('[data-kind=radio]', (el) => !!el.querySelector('.pp-validation-marker') && el.querySelector('.pp-validation-marker').getAttribute('aria-label') === 'Tier is required'));
    check('no page errors (common settings)', errors.length === 0, errors);
    await page.close();
  }

  // 4. Visibility, secondary buttons, unique ids, revealing a field in another tab.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      harness.view({ kind: 'text', id: 'Ro', label: 'Read only', visibility: 'READONLY', value: 'Ada' });
      harness.view({ kind: 'text', id: 'Hid', label: 'Hidden', visibility: 'HIDDEN', value: 'x' });
      harness.view({ kind: 'text', id: 'None', label: 'None', visibility: 'NONE', value: 'x' });
      harness.view({ kind: 'text', id: 'Inh', label: 'Inherited', visibility: 'DEFAULT', inherited: 'READONLY', value: 'Bob' });
      harness.view({ kind: 'text', id: 'Same1', label: 'Same label' });
      harness.view({ kind: 'text', id: 'Same2', label: 'Same label' });
      // ARIA tabs: the required field sits in the second, unselected tab.
      const root = document.getElementById('root');
      root.insertAdjacentHTML('beforeend', '<div role="tablist"><button role="tab" id="t1" aria-controls="p1" aria-selected="true">One</button>'
        + '<button role="tab" id="t2" aria-controls="p2" aria-selected="false">Two</button></div><div role="tabpanel" id="p1"></div><div role="tabpanel" id="p2" hidden></div>');
      document.querySelectorAll('[role=tab]').forEach((tab) => tab.addEventListener('click', () => {
        document.querySelectorAll('[role=tab]').forEach((t) => t.setAttribute('aria-selected', String(t === tab)));
        document.querySelectorAll('[role=tabpanel]').forEach((p) => { p.hidden = p.id !== tab.getAttribute('aria-controls'); });
      }));
      harness.view({ kind: 'text', id: 'InTab', label: 'In tab two', visibility: 'REQUIRED', parent: document.getElementById('p2') });
      // BAW's Tab Section markup: a tab strip of links, and panes in the same order without aria-controls.
      root.insertAdjacentHTML('beforeend', '<div class="Tab_Section"><div><ul class="nav nav-tabs nav-tabs-strip"><li class="active"><a id="b1">One</a></li>'
        + '<li><a id="b2">Two</a></li></ul><div class="tab-content"><div class="ContentBox"><div class="tab-pane" role="tabpanel" id="bp1"></div>'
        + '<div class="tab-pane tab-hidden" role="tabpanel" id="bp2"></div></div></div></div></div>');
      document.querySelectorAll('.nav-tabs-strip a').forEach((a) => a.addEventListener('click', () => {
        document.querySelectorAll('.nav-tabs-strip li').forEach((li) => li.classList.toggle('active', li === a.parentElement));
      }));
      harness.view({ kind: 'text', id: 'InBawTab', label: 'In BAW tab two', visibility: 'REQUIRED', parent: document.getElementById('bp2') });
      harness.view({ kind: 'button', id: 'Back', label: 'Back', options: { kind: 'secondary' } });
      harness.view({ kind: 'button', id: 'Next', label: 'Next' });
    });
    await sleep(200);
    check('READONLY draws the value as text', (await text(page, '.cell:nth-child(1) dd')) === 'Ada');
    check('HIDDEN draws nothing', await page.$eval('.cell:nth-child(2)', (el) => el.textContent.trim() === ''));
    check('NONE draws nothing', await page.$eval('.cell:nth-child(3)', (el) => el.textContent.trim() === ''));
    check('DEFAULT takes the inherited visibility', (await text(page, '.cell:nth-child(4) dd')) === 'Bob');
    const ids = await page.$$eval('input[id^=pp-Same]', (els) => els.map((e) => e.id));
    check('inputs with the same label get different ids', ids.length === 2 && ids[0] !== ids[1], ids);
    await page.click('[data-kind=button]:nth-last-of-type(2) button');
    await sleep(20);
    check('a secondary button fires without validating', (await page.evaluate(() => harness.triggered.map((t) => t.id))).includes('Back'));
    await page.click('[data-kind=button]:last-of-type button');
    await sleep(50);
    check('the tab that holds the first error is selected', await page.$eval('#t2', (t) => t.getAttribute('aria-selected')) === 'true');
    check("a BAW Tab Section's tab that holds an error is marked", await page.$eval('#b2', (a) => a.parentElement.classList.contains('pp-tab-error')));
    await page.type('#p2 input', 'filled');
    await page.click('[data-kind=button]:last-of-type button');
    await sleep(50);
    check("a BAW Tab Section's tab that holds the first error is selected", await page.$eval('#b2', (a) => a.parentElement.classList.contains('active')));
    check('a tab without errors is not marked', await page.$$eval('.pp-tab-error', (els) => els.length) === 1);
    check('the required field in the other tab blocks the Button', !(await page.evaluate(() => harness.triggered.map((t) => t.id))).includes('Next'));
    check('no page errors (visibility)', errors.length === 0, errors);
    await page.close();
  }

  // 5. Typing: a decimal number and a typed date reach the binding when the input loses focus.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      window.cost = harness.view({ kind: 'number', id: 'Cost', label: 'Cost', value: 0 });
      window.due = harness.view({ kind: 'date', id: 'Due', label: 'Due', value: null });
    });
    await sleep(200);
    await page.click('#pp-Cost', { clickCount: 3 });
    await page.keyboard.press('Backspace');
    await page.type('#pp-Cost', '1234.5');
    await page.keyboard.press('Tab');
    await page.type('#pp-Due', '03/20/2027');
    await page.keyboard.press('Tab');
    await sleep(100);
    check('a typed decimal number is kept', (await page.evaluate(() => cost.value())) === 1234.5, await page.evaluate(() => cost.value()));
    check('numbers show without thousands separators', (await page.$eval('#pp-Cost', (i) => i.value)) === '1234.5', await page.$eval('#pp-Cost', (i) => i.value));
    check('a typed date is kept when the field loses focus', await page.evaluate(() => due.value() instanceof Date && due.value().getFullYear() === 2027 && due.value().getMonth() === 2 && due.value().getDate() === 20));
    await page.click('#pp-Due', { clickCount: 3 });
    await page.keyboard.press('Backspace');
    await page.type('#pp-Due', '02/31/2027');
    await page.keyboard.press('Tab');
    await sleep(100);
    check('an impossible date leaves the value unchanged', await page.evaluate(() => due.value().getDate() === 20));
    check('no page errors (typing)', errors.length === 0, errors);
    await page.close();
  }

  // 6. Review fixes: editing a date in the middle, repeated views, a bad pattern, a hidden container, min while typing,
  //    and an option change at runtime.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      window.due = harness.view({ kind: 'date', id: 'Due', label: 'Due', value: new Date(2026, 0, 15) });
      window.row1 = harness.view({ kind: 'radio', id: 'Size', path: 'Table1[0]/Size', label: 'Size', visibility: 'REQUIRED', options: { options: { items: ['a', 'b'].map((v) => ({ name: v.toUpperCase(), value: v })) } } });
      window.row2 = harness.view({ kind: 'radio', id: 'Size', path: 'Table1[1]/Size', label: 'Size', visibility: 'REQUIRED', options: { options: { items: ['a', 'b'].map((v) => ({ name: v.toUpperCase(), value: v })) } } });
      harness.view({ kind: 'text', id: 'Bad', label: 'Bad pattern', value: 'x', options: { pattern: '[' } });
      harness.view({ kind: 'text', id: 'InHidden', label: 'In a hidden panel', visibility: 'REQUIRED', inherited: 'HIDDEN' });
      window.qty = harness.view({ kind: 'number', id: 'Qty', label: 'Quantity', value: null, options: { min: 5 } });
      window.head = harness.view({ kind: 'header', id: 'Head', options: { title: 'First' } });
      harness.view({ kind: 'button', id: 'Go', label: 'Go' });
    });
    await sleep(200);
    await page.$eval('#pp-Due', (i) => { i.focus(); i.setSelectionRange(3, 5); });
    await page.keyboard.type('28');
    await sleep(50);
    const due = await page.evaluate(() => [due.value().getFullYear(), due.value().getMonth(), due.value().getDate()]);
    check('editing the day in the middle of a date stores that date', JSON.stringify(due) === JSON.stringify([2026, 0, 28]), due);
    const names = await page.$$eval('input[type=radio]', (r) => [...new Set(r.map((x) => x.name))]);
    check('two instances of one view get separate radio groups', names.length === 2, names);
    await page.type('#pp-Qty', '2');
    check('min is not flagged while typing', await page.$eval('#pp-Qty', (i) => !i.closest('[data-invalid]') && i.getAttribute('aria-invalid') !== 'true'));
    await page.keyboard.press('Tab');
    await page.click('[data-kind=button] button');
    await sleep(100);
    const summary = await text(page, '[data-kind=errors]') || await page.evaluate(() => ModernizerWidgets.page.errors.map((e) => e.message).join(' · '));
    check('both instances are validated', (summary.match(/Size is required/g) || []).length === 2, summary);
    check('a bad pattern does not break the Button', summary.includes('Quantity must be at least 5') && !summary.includes('Bad pattern'), summary);
    check('a field in a hidden container draws nothing and is not validated', !summary.includes('hidden panel')
      && (await page.$eval('[data-kind=text]:nth-of-type(5)', (el) => el.textContent.trim())) === '');
    await page.evaluate(() => head.setOption('title', 'Second'));
    await sleep(50);
    check('a widget re-renders when an option changes', (await text(page, '[data-kind=header] h1')) === 'Second');
    check('no page errors (review fixes)', errors.length === 0, errors);
    await page.close();
  }

  // 7. The generated Coach Designer preview script (server/widget_toolkit.py preview), run as Designer runs it.
  {
    const { page, errors } = await fresh();
    for (const kind of ['text', 'select', 'header']) {
      const script = execFileSync('python3', ['../server/widget_toolkit.py', 'preview', 'modernizer', kind], { encoding: 'utf8' });
      await page.evaluate((src, k) => {
        const holder = (v) => ({ get: () => v });
        const mixObject = new Function(`${src}; return mixObject;`)();
        const view = Object.assign({ context: {
          getManagedAssetUrl: (name) => `../bundle/${name}`, assetType_WEB: 'W',
          options: k === 'text' ? { example: holder('Hello') } : {},
        } }, mixObject);
        const div = document.createElement('div');
        div.setAttribute('data-generated', k);
        document.getElementById('root').appendChild(div);
        view.createPreview(div, `${k} label`, () => div.setAttribute('data-ready', '1'));
        window[`gen_${k}`] = view;
      }, script, kind);
    }
    await sleep(200);
    check('generated previews call back', (await page.$$('[data-generated][data-ready]')).length === 3);
    check('generated preview starts from the options set in Designer', await page.$eval('[data-generated=text] input', (i) => i.placeholder) === 'Hello');
    await page.evaluate(() => {
      gen_text.propertyChanged('@label', 'Renamed');
      gen_text.propertyChanged('@helpText', 'Some help');
      gen_header.propertyChanged('title', 'Designer title');
      gen_select.propertyChanged('options', { items: [{ get: (k) => (k === 'name' ? 'One' : '1') }] });
    });
    await sleep(100);
    check('generated preview follows the label', (await text(page, '[data-generated=text] label')) === 'Renamed');
    check('generated preview shows help text', ((await text(page, '[data-generated=text]')) || '').includes('Some help'));
    check('generated preview follows options', (await text(page, '[data-generated=header] h1')) === 'Designer title'
      && JSON.stringify(await page.$$eval('[data-generated=select] option', (o) => o.map((x) => x.textContent))) === JSON.stringify(['Choose an option', 'One']));
    check('no page errors (generated previews)', errors.length === 0, errors);
    await page.close();
  }
  // 8. Events without BPM UI on the page: the handlers are compiled by the widgets, with me, view and the arguments
  //    the UI Toolkit names; the me API; a handler that returns false cancels; a failing handler breaks nothing.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      window.log = [];
      window.name1 = harness.view({ kind: 'text', id: 'Name', label: 'Name', value: '', options: {
        eventON_LOAD: 'log.push(["load", me.getText(), view === me, !!me.context.element.querySelector("input")]);',
        eventON_CHANGE: 'log.push(["change", newText, oldText]);',
        eventON_FOCUS: 'log.push(["focus"]);',
        eventON_BLUR: 'log.push(["blur"]);',
        eventON_INPUT: 'if (potential.length > 5) { log.push(["input refused", current, potential, type]); return false; }',
      } });
      window.agree = harness.view({ kind: 'checkbox', id: 'Agree', label: 'Agree', value: false, options: {
        eventON_CHANGE: 'log.push(["checked", me.isChecked(), newValue, oldValue]);' } });
      window.broken = harness.view({ kind: 'text', id: 'Broken', label: 'Broken', value: '', options: { eventON_CHANGE: 'throw new Error("boom")' } });
      window.bad = harness.view({ kind: 'text', id: 'Bad', label: 'Bad', value: '', options: { eventON_CHANGE: 'this is not javascript' } });
      window.fill = harness.view({ kind: 'button', id: 'Fill', label: 'Fill', options: { kind: 'secondary',
        eventON_CLICK: 'name1.view.setText("Set"); log.push(["click"]); return false;' } });
      window.go = harness.view({ kind: 'button', id: 'Go', label: 'Go', options: { kind: 'secondary',
        eventON_CLICK: 'log.push(["go"]);', eventON_BOUNDARYEVT: 'log.push(["boundary", status]);' } });
    });
    await sleep(200);
    const log = () => page.evaluate(() => window.log.splice(0));
    const loaded = await log();
    check('eventON_LOAD runs once the widget is drawn, with me as the view', JSON.stringify(loaded) === JSON.stringify([['load', '', true, true]]), loaded);
    await page.click('#pp-Name');
    await page.type('#pp-Name', 'Adam');
    const typed = await log();
    check('eventON_FOCUS runs when the field takes the focus', JSON.stringify(typed[0]) === '["focus"]', typed);
    check('eventON_CHANGE gets newText and oldText', JSON.stringify(typed.at(-1)) === '["change","Adam","Ada"]', typed);
    await page.type('#pp-Name', 'sXY');
    const refused = await log();
    check('eventON_INPUT returning false refuses the keystroke', (await page.evaluate(() => name1.value())) === 'Adams'
      && JSON.stringify(refused.at(-1)) === '["input refused","Adams","AdamsY","insertText"]', [await page.evaluate(() => name1.value()), refused]);
    await page.keyboard.press('Tab');
    check('eventON_BLUR runs when the focus leaves the field', JSON.stringify(await log()) === '[["blur"]]');
    await page.click('[data-kind=checkbox] label');
    const checked = await log();
    check('a Checkbox handler reads me.isChecked() and the new value', JSON.stringify(checked) === '[["checked",true,true,false]]', checked);
    await page.click('[data-kind=button]:nth-of-type(5) button');
    await sleep(50);
    const filled = await log();
    check("a handler's me.setText() sets the other widget, which fires its eventON_CHANGE", (await page.evaluate(() => name1.value())) === 'Set'
      && JSON.stringify(filled) === '[["change","Set","Adams"],["click"]]', filled);
    check('eventON_CLICK returning false cancels the boundary event', (await page.evaluate(() => harness.triggered.length)) === 0);
    await page.click('[data-kind=button]:nth-of-type(6) button');
    await sleep(80);
    const went = await log();
    check('eventON_BOUNDARYEVT runs after BAW handled the boundary event, with its status', JSON.stringify(went) === '[["go"],["boundary","ok"]]'
      && (await page.evaluate(() => harness.triggered.map((t) => t.id))).join() === 'Go', went);
    await page.type('#pp-Broken', 'x');
    await page.type('#pp-Bad', 'y');
    check('a failing or broken handler leaves its widget working', (await page.evaluate(() => [broken.value(), bad.value()].join())) === 'x,y');
    check('a failing or broken handler is logged', errors.some((e) => e.includes('eventON_CHANGE handler of Broken failed'))
      && errors.some((e) => e.includes('eventON_CHANGE handler of Bad does not compile')), errors);
    await page.evaluate(() => { name1.view.setLabel('Full name'); agree.view.setEnabled(false); });
    await sleep(50);
    check('me.setLabel() relabels the widget', (await text(page, '[data-kind=text] label')) === 'Full name');
    check('me.setEnabled(false) makes the widget read-only', (await text(page, '[data-kind=checkbox] dd')) === 'Yes');
    await page.evaluate(() => name1.view.setPlaceholder('Your full name'));
    await sleep(50);
    check('me.setPlaceholder() works on an option the layout did not set', await page.$eval('#pp-Name', (i) => i.placeholder) === 'Your full name');
    await page.evaluate(() => name1.view.setVisible(false));
    await sleep(50);
    check('me.setVisible(false) hides the widget', (await page.$eval('[data-kind=text]', (el) => el.textContent.trim())) === ''
      && !(await page.evaluate(() => name1.view.isVisible())));
    const unexpected = errors.filter((e) => !e.includes('handler of Broken') && !e.includes('handler of Bad') && !e.includes('boom') && !e.includes('Unexpected identifier'));
    check('no other page errors (events)', unexpected.length === 0, unexpected);
    await page.close();
  }

  // 9. Events with BPM UI on the page: the view is registered with bpmext, which runs the handlers (${Control}
  //    references, page.ui), with the argument names the UI Toolkit uses; its result still cancels a click.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      window.calls = [];
      const registered = new Map();
      window.bpmext = { ui: {
        loadView(view) {
          calls.push(['loadView', view.context.viewid]);
          const code = view.context.options.eventON_LOAD && view.context.options.eventON_LOAD.get('value');
          if (code) new Function('me', code)(view);
        },
        registerEventHandlingFunction(view, name, ...args) { calls.push(['register', view.context.viewid, name, ...args]); registered.set(`${view.context.viewid}/${name}`, args); },
        executeEventHandlingFunction(view, name, ...values) {
          calls.push(['execute', view.context.viewid, name, ...values]);
          const code = view.context.options[name].get('value').replace(/\$\{(\w+)\}/g, 'page.ui.get("$1")');
          return new Function('me', 'page', ...registered.get(`${view.context.viewid}/${name}`), code)(view, { ui: { get: (id) => ({ id }) } }, ...values);
        },
        unloadView(view) { calls.push(['unloadView', view.context.viewid]); },
      } };
      window.seen = [];
      window.city = harness.view({ kind: 'text', id: 'City', label: 'City', value: 'Oslo', options: {
        eventON_LOAD: 'seen.push("load " + me.getText());', eventON_CHANGE: 'seen.push(${Other}.id + " " + newText + " " + oldText);' } });
      window.stop = harness.view({ kind: 'button', id: 'Stop', label: 'Stop', options: { kind: 'secondary', eventON_CLICK: 'return false;' } });
      window.thrower = harness.view({ kind: 'text', id: 'Thrower', label: 'Thrower', value: '', options: { eventON_CHANGE: 'throw new Error("bpm boom")' } });
    });
    await sleep(150);
    await page.click('#pp-City', { clickCount: 3 });
    await page.keyboard.type('Rome');
    await page.click('[data-kind=button] button');
    await sleep(50);
    await page.type('#pp-Thrower', 'z');
    check('a handler that throws under BPM UI leaves its widget working', (await page.evaluate(() => thrower.value())) === 'z');
    check('a handler that throws under BPM UI is logged', errors.some((e) => e.includes('eventON_CHANGE handler of Thrower failed')), errors);
    errors.splice(0, errors.length, ...errors.filter((e) => !e.includes('Thrower') && !e.includes('bpm boom')));
    await page.evaluate(() => city.handle.unmount());
    const calls = await page.evaluate(() => window.calls);
    const seen = await page.evaluate(() => window.seen);
    const registers = calls.filter((c) => c[0] === 'register' && c[1] === 'City').map((c) => c.slice(2).join(' '));
    check('the view is loaded into BPM UI, which runs eventON_LOAD', calls[0]?.join() === 'loadView,City' && seen[0] === 'load Oslo', [calls[0], seen]);
    check('each other event is registered with the UI Toolkit argument names', JSON.stringify(registers)
      === JSON.stringify(['eventON_CHANGE newText oldText', 'eventON_FOCUS', 'eventON_BLUR', 'eventON_INPUT current potential selection type']), registers);
    check('BPM UI runs eventON_CHANGE, with ${Control} references', seen.at(-1) === 'Other Rome Rom', seen);
    check('only events that have code are run', !calls.some((c) => c[0] === 'execute' && c[2] !== 'eventON_CHANGE' && c[2] !== 'eventON_CLICK'), calls.filter((c) => c[0] === 'execute').map((c) => c[2]));
    check('a BPM UI click handler returning false cancels the boundary event', (await page.evaluate(() => harness.triggered.length)) === 0);
    check('unmounting unloads the view from BPM UI', calls.at(-1)?.join() === 'unloadView,City', calls.at(-1));
    check('no page errors (BPM UI events)', errors.length === 0, errors);
    await page.close();
  }

  // 10. The options the widgets take from the UI Toolkit: tab index, select all, height, decimal places, date range,
  //     select placeholder, and the Carbon button kinds.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      harness.view({ kind: 'text', id: 'Code', label: 'Code', value: 'ABC123', options: { tabIndex: 3, selectAll: true } });
      harness.view({ kind: 'textarea', id: 'Notes', label: 'Notes', value: '', options: { height: '150px' } });
      window.price = harness.view({ kind: 'number', id: 'Price', label: 'Price', value: null, options: { decimalPlaces: 2 } });
      window.start = harness.view({ kind: 'date', id: 'Start', label: 'Start', value: new Date(2026, 0, 1), options: { startDate: new Date(2026, 0, 10), endDate: new Date(2026, 11, 31) } });
      harness.view({ kind: 'select', id: 'Plan', label: 'Plan', value: '', options: { example: 'Pick a plan', options: { items: [{ name: 'A', value: 'a' }] } } });
      harness.view({ kind: 'checkbox', id: 'Ok', label: 'Ok', value: false, options: { tabIndex: 4 } });
      harness.view({ kind: 'button', id: 'Save', label: 'Save', options: { kind: 'ghost', validate: true, tabIndex: 5 } });
    });
    await sleep(200);
    check('tabIndex reaches the input', await page.$eval('#pp-Code', (i) => i.tabIndex) === 3);
    check('tabIndex reaches a checkbox and a button', await page.$eval('[data-kind=checkbox] input', (i) => i.tabIndex) === 4
      && await page.$eval('[data-kind=button] button', (b) => b.tabIndex) === 5);
    await page.focus('#pp-Code');
    check('selectAll selects the text on focus', JSON.stringify(await page.$eval('#pp-Code', (i) => [i.selectionStart, i.selectionEnd])) === '[0,6]');
    check('height sizes the text area', await page.$eval('#pp-Notes', (t) => t.style.height) === '150px');
    await page.type('#pp-Price', '3.14159');
    await page.keyboard.press('Tab');
    await sleep(50);
    check('decimalPlaces keeps the number to that many decimals', (await page.evaluate(() => price.value())) === 3.14, await page.evaluate(() => price.value()));
    check('decimalPlaces shows that many decimals', (await page.$eval('#pp-Price', (i) => i.value)) === '3.14', await page.$eval('#pp-Price', (i) => i.value));
    check('the select shows its placeholder', (await page.$$eval('[data-kind=select] option', (o) => o[0].textContent)) === 'Pick a plan');
    check('a ghost button draws as a Carbon ghost button', await page.$eval('[data-kind=button] button', (b) => b.className.includes('pp--btn--ghost')));
    await page.click('[data-kind=button] button');
    await sleep(50);
    const errs = await page.evaluate(() => ModernizerWidgets.page.errors.map((e) => e.message));
    check('a date before startDate is flagged', errs.some((m) => m.startsWith('Start must be on or after')), errs);
    check('the flagged date blocks the validating button', (await page.evaluate(() => harness.triggered.length)) === 0);
    check('no page errors (options)', errors.length === 0, errors);
    await page.close();
  }

  // 11. The generated toolkit: every option sits in a Configuration group, every contract event is an EVENT option
  //     (Coach Designer's Events tab), and the preview script runs no event code.
  {
    const out = path.join(os.tmpdir(), `mdw-check-${process.pid}.twx`);
    execFileSync('python3', ['../server/widget_toolkit.py', 'build', 'modernizer', '0.0.0', out]);
    const views = JSON.parse(execFileSync('python3', ['-I', '-c', `
import json, re, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
views = {}
for n in z.namelist():
    t = z.read(n).decode('utf-8', 'replace')
    m = re.search(r'<coachView id="[^"]+" name="([^"]+)"', t)
    if m:
        views[m.group(1)] = {
            "options": re.findall(r'<configOption name="([^"]+)">.*?<propertyType>(\\w+)</propertyType>.*?<groupName(?: isNull="true" />|>([^<]*)</groupName>)', t),
            "load": re.search(r'<loadJsFunction>(.*?)</loadJsFunction>', t, re.S).group(1)}
print(json.dumps(views))`, out], { encoding: 'utf8' }));
    fs.rmSync(out, { force: true });
    const problems = [];
    for (const w of contract) {
      const v = views[w.view];
      if (!v) { problems.push(`${w.view}: not built`); continue; }
      const byName = Object.fromEntries(v.options.map(([name, type, group]) => [name, { type, group }]));
      for (const o of w.options) if (byName[o.name]?.type !== 'OBJECT' || byName[o.name]?.group !== o.group) problems.push(`${w.view}.${o.name}: ${JSON.stringify(byName[o.name])}`);
      for (const e of Object.keys(w.events || {})) if (byName[e]?.type !== 'EVENT' || byName[e]?.group !== 'Events') problems.push(`${w.view}.${e}: ${JSON.stringify(byName[e])}`);
      if (!v.load.includes('eventON_LOAD')) problems.push(`${w.view}: load does not pass the events`);
    }
    check('every option is in its Configuration group and every event is an EVENT option', problems.length === 0, problems);
    const preview = execFileSync('python3', ['../server/widget_toolkit.py', 'preview', 'modernizer', 'text'], { encoding: 'utf8' });
    check('the Coach Designer preview runs no event code', !preview.includes('eventON_'));
  }
  // 12. What every contract widget does, so a new widget is covered without editing this script: its eventON_LOAD
  //     runs with me, its accessor reads and writes its value (its label when it binds nothing) and fires
  //     eventON_CHANGE, a field fires focus, blur and input, and a boundary widget fires eventON_CLICK, its boundary
  //     event and eventON_BOUNDARYEVT.
  {
    const SAMPLE = { String: 'b', Integer: 7, Decimal: 7.5, Boolean: true };
    const record = (event) => `window.seen = window.seen || {}; (window.seen[me.context.viewid] = window.seen[me.context.viewid] || {})[${JSON.stringify(event)}] = Array.prototype.slice.call(arguments, 2).concat([true]);`;
    const nvp = { items: [{ name: 'A', value: 'a' }, { name: 'B', value: 'b' }] };
    const setUp = async (page, list) => page.evaluate((items) => items.forEach((w) => {
      window.views = window.views || {};
      window.views[w.kind] = harness.view({ kind: w.kind, id: `W_${w.kind}`, label: `${w.kind} label`, value: null, options: w.options });
    }), list);
    const spec = (w) => {
      const options = Object.fromEntries(Object.keys(w.events || {}).map((e) => [e, record(e)]));
      if (w.options.some((o) => o.name === 'options' && o.list)) options.options = nvp;
      if (w.options.some((o) => o.name === 'validate')) options.validate = false;
      return { kind: w.kind, options };
    };
    const seen = (page) => page.evaluate(() => window.seen || {});

    const { page, errors } = await fresh();
    const plain = contract.filter((w) => !w.boundary);
    await setUp(page, plain.map(spec));
    await sleep(200);
    const problems = [];
    let got = await seen(page);
    for (const w of plain) if (!got[`W_${w.kind}`]?.eventON_LOAD) problems.push(`${w.kind}: eventON_LOAD did not run (the component threw, or registerWidget names another kind)`);
    // The accessor, then the DOM events of each field.
    const values = await page.evaluate((list, sample) => Object.fromEntries(list.filter((w) => w.accessor).map((w) => {
      const view = window.views[w.kind].view;
      const [get, set] = w.accessor;
      if (typeof view[get] !== 'function' || typeof view[set] !== 'function') return [w.kind, { missing: true }];
      const value = w.binding === null ? 'Renamed' : w.binding === 'Date' ? new Date(2026, 1, 2) : sample[w.binding];
      view[set](value);
      const back = view[get]();
      return [w.kind, { same: back === value || (back instanceof Date && back.getTime() === value.getTime()) }];
    })), plain, SAMPLE);
    for (const [kind, v] of Object.entries(values)) {
      if (v.missing) problems.push(`${kind}: me has no accessor methods (accessor must be [getter, setter] in the contract)`);
      else if (!v.same) problems.push(`${kind}: the accessor setter did not change what the getter reads (a field must write its value with binding.set)`);
    }
    await sleep(100);
    got = await seen(page);
    for (const w of plain.filter((x) => x.binding !== null && x.events?.eventON_CHANGE)) {
      if (!got[`W_${w.kind}`]?.eventON_CHANGE) problems.push(`${w.kind}: setting its value did not fire eventON_CHANGE (the field must bind its value with fieldWidget and binding.set)`);
    }
    for (const w of plain.filter((x) => x.events?.eventON_FOCUS || x.events?.eventON_BLUR || x.events?.eventON_INPUT)) {
      const input = `[data-kind=${w.kind}] input:not([type=hidden]), [data-kind=${w.kind}] select, [data-kind=${w.kind}] textarea, [data-kind=${w.kind}] button`;
      if (!(await page.$(input))) { problems.push(`${w.kind}: declares eventON_FOCUS, eventON_BLUR or eventON_INPUT but draws no input, select, textarea or button; drop those events`); continue; }
      if (w.events.eventON_INPUT) await page.type(input, 'x'); else await page.focus(input);
      await page.evaluate(() => document.activeElement && document.activeElement.blur());
      await sleep(50);
      const s = (await seen(page))[`W_${w.kind}`] || {};
      const hint = { eventON_INPUT: 'declare eventON_INPUT only on a widget whose first input is a text input or textarea, where the user types', eventON_FOCUS: 'its first input could not take the focus', eventON_BLUR: 'its first input could not take the focus' };
      for (const e of ['eventON_FOCUS', 'eventON_BLUR', 'eventON_INPUT']) if (w.events[e] && !s[e]) problems.push(`${w.kind}: ${e} did not fire (${hint[e]})`);
    }
    check('every widget runs eventON_LOAD, its accessor and its field events', problems.length === 0, problems);
    check('no page errors (every widget\'s events)', errors.length === 0, errors);
    await page.close();

    // Each boundary widget on a page of its own, pressed by its first button or link. A widget that asks first (a
    // confirm dialog) is then confirmed with the primary button it shows.
    const pressed = [];
    for (const w of contract.filter((x) => x.boundary)) {
      const { page: p, errors: errs } = await fresh();
      await setUp(p, [spec(w)]);
      const target = `[data-kind=${w.kind}] button, [data-kind=${w.kind}] a, [data-kind=${w.kind}] [role=button]`;
      if (!(await p.$(target))) { pressed.push(`${w.kind}: draws no button or link to press`); await p.close(); continue; }
      await p.click(target);
      await sleep(150);
      if (!(await p.evaluate(() => harness.triggered.length))) {
        const confirm = await p.evaluateHandle((kind) => {
          const visible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
          const scopes = [document.querySelector(`[data-kind=${kind}]`), ...document.querySelectorAll('[role=dialog]')];
          const all = scopes.flatMap((sc) => (sc ? [...sc.querySelectorAll('.pp--btn--primary, .pp--btn--danger')] : []));
          return all.filter(visible).filter((b) => b !== document.querySelector(`[data-kind=${kind}] button, [data-kind=${kind}] a`)).pop() || null;
        }, w.kind);
        if (confirm.asElement()) { await confirm.asElement().click(); await sleep(150); }
      }
      const s = (await seen(p))[`W_${w.kind}`] || {};
      const fired = await p.evaluate(() => harness.triggered.map((t) => t.id));
      if (!s.eventON_LOAD) pressed.push(`${w.kind}: eventON_LOAD did not run (the component threw, or registerWidget names another kind)`);
      if (!s.eventON_CLICK) pressed.push(`${w.kind}: eventON_CLICK did not run (call fire('eventON_CLICK') when the first button or link is pressed)`);
      if (!fired.includes(`W_${w.kind}`)) pressed.push(`${w.kind}: pressing it fired no boundary event (call trigger(done) on the press, or on the primary button of the confirm step it shows)`);
      if (!s.eventON_BOUNDARYEVT || s.eventON_BOUNDARYEVT[0] !== 'ok') pressed.push(`${w.kind}: eventON_BOUNDARYEVT did not get the status (fire the boundary event with trigger(done))`);
      if (errs.length) pressed.push(`${w.kind}: ${errs.join('; ')}`);
      await p.close();
    }
    check('every boundary widget fires eventON_CLICK, its boundary event and eventON_BOUNDARYEVT', pressed.length === 0, pressed);
  }

  // 13. Typed values: Yes/No and whole-number options read and write booleans and numbers, not text.
  {
    const { page, errors } = await fresh();
    await page.evaluate(() => {
      const nvp = (pairs) => ({ items: pairs.map(([name, value]) => ({ get: (key) => (key === 'name' ? name : value) })) });
      const yesNo = nvp([['Yes', 'true'], ['No', 'false']]);
      const ages = nvp([19, 20, 21, 22, 23, 24, 25, 26].map((n) => [`${n} years`, String(n)]));
      window.cover = {};
      for (const [name, value] of [['Null', null], ['True', true], ['False', false]]) {
        window.cover[name] = harness.view({ kind: 'radio', id: `Cover${name}`, label: 'Prior coverage', value, options: { options: yesNo } });
      }
      window.ageNull = harness.view({ kind: 'select', id: 'AgeNull', label: 'Age', value: null, options: { options: ages } });
      window.age19 = harness.view({ kind: 'select', id: 'Age19', label: 'Age', value: 19, options: { options: ages } });
      window.age26 = harness.view({ kind: 'select', id: 'Age26', label: 'Age', value: 26, options: { options: ages } });
      window.zero = harness.view({ kind: 'select', id: 'Zero', label: 'Count', value: 0, options: { options: nvp([['None', '0'], ['One', '1']]) } });
      window.words = harness.view({ kind: 'select', id: 'Words', label: 'Word', value: null, options: { options: nvp([['A', 'a'], ['B', 'b']]) } });
      window.cost = harness.view({ kind: 'number', id: 'Cost', label: 'Cost', value: 0, options: { decimalPlaces: 2 } });
      window.price = harness.view({ kind: 'number', id: 'Price', label: 'Price', value: 12.5, options: { decimalPlaces: 2 } });
      harness.view({ kind: 'text', id: 'Mark', label: 'Mark', value: '' });
    });
    await sleep(300);
    const checked = (id) => page.$$eval(`input[type=radio][name=pp-${id}]`, (r) => r.filter((x) => x.checked).map((x) => x.value));
    check('a null Yes/No shows nothing selected', (await checked('CoverNull')).length === 0, await checked('CoverNull'));
    check('a true Yes/No shows Yes selected', JSON.stringify(await checked('CoverTrue')) === '["true"]', await checked('CoverTrue'));
    check('a false Yes/No shows No selected', JSON.stringify(await checked('CoverFalse')) === '["false"]', await checked('CoverFalse'));
    await page.click('input[name=pp-CoverNull][value=true] + label');
    await sleep(50);
    check('picking Yes stores the boolean true', await page.evaluate(() => cover.Null.value() === true), await page.evaluate(() => cover.Null.value()));
    await page.click('input[name=pp-CoverNull][value=false] + label');
    await sleep(50);
    check('picking No stores the boolean false', await page.evaluate(() => cover.Null.value() === false), await page.evaluate(() => cover.Null.value()));
    const selected = (id) => page.$eval(`#${id}`, (s) => s.value);
    check('a null dropdown shows the blank item', (await selected('pp-AgeNull')) === '', await selected('pp-AgeNull'));
    check('a 19 dropdown shows 19', (await selected('pp-Age19')) === '19', await selected('pp-Age19'));
    check('a 26 dropdown shows 26', (await selected('pp-Age26')) === '26', await selected('pp-Age26'));
    check('a 0 dropdown shows its 0 option', (await selected('pp-Zero')) === '0', await selected('pp-Zero'));
    await page.select('#pp-AgeNull', '19');
    await sleep(50);
    check('picking 19 stores the number 19', await page.evaluate(() => ageNull.value() === 19), await page.evaluate(() => ageNull.value()));
    await page.select('#pp-AgeNull', '26');
    await sleep(50);
    check('picking 26 stores the number 26', await page.evaluate(() => ageNull.value() === 26));
    await page.select('#pp-AgeNull', '');
    await sleep(50);
    check('picking the blank item stores null', await page.evaluate(() => ageNull.value() === null), await page.evaluate(() => ageNull.value()));
    await page.select('#pp-Zero', '1');
    await page.select('#pp-Zero', '0');
    await sleep(50);
    check('picking 0 stores the number 0', await page.evaluate(() => zero.value() === 0), await page.evaluate(() => zero.value()));
    await page.select('#pp-Words', 'b');
    await sleep(50);
    check('text options still store text', await page.evaluate(() => words.value() === 'b'), await page.evaluate(() => words.value()));
    check('a 0 number shows 0.00', (await page.$eval('#pp-Cost', (i) => i.value)) === '0.00', await page.$eval('#pp-Cost', (i) => i.value));
    check('12.5 with 2 decimals shows 12.50', (await page.$eval('#pp-Price', (i) => i.value)) === '12.50', await page.$eval('#pp-Price', (i) => i.value));
    await page.click('#pp-Price', { clickCount: 3 });
    await page.type('#pp-Price', '12.5');
    await page.keyboard.press('Tab');
    await sleep(100);
    check('a typed 12.5 is stored as the number 12.5', await page.evaluate(() => price.value() === 12.5), await page.evaluate(() => price.value()));
    await page.click('#pp-Price', { clickCount: 3 });
    await page.keyboard.press('Backspace');
    await page.keyboard.press('Tab');
    await sleep(100);
    check('a cleared number stores null', await page.evaluate(() => price.value() === null), await page.evaluate(() => price.value()));
    await page.click('#pp-Cost', { clickCount: 3 });
    await page.type('#pp-Cost', '0');
    await page.keyboard.press('Tab');
    await sleep(100);
    check('a typed 0 is stored as the number 0', await page.evaluate(() => cost.value() === 0), await page.evaluate(() => cost.value()));
    check('no page errors (typed values)', errors.length === 0, errors);
    await page.close();
  }
} catch (e) {
  check('harness ran', false, String(e).slice(0, 500));
} finally {
  await browser.close();
}

for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}${r.ok || r.detail === undefined ? '' : `  ${JSON.stringify(r.detail)}`}`);
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
