// Check the Modernizer Widgets bundle offline: renders every widget in scripts/widget-harness.html through fake
// BAW Coach Views (and as Coach Designer previews), and checks validation, visibility, the Button and the Theme.
//
// Usage: npm run build, then node scripts/check-widgets.mjs [--shot <png>] (also writes <png>-contract.png, every contract widget)
// Exit code 1 when a check fails.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseArgs } from 'node:util';
import puppeteer from 'puppeteer-core';

const { values: args } = parseArgs({ options: { shot: { type: 'string' } } });
const BROWSERS = [process.env.BROWSER_PATH, '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Helium.app/Contents/MacOS/Helium',
  '/usr/bin/chromium', '/usr/bin/google-chrome'];
const harness = new URL('./widget-harness.html', import.meta.url).href;
// Every widget of the toolkit's contract (widgets/modernizer-widgets.json), so a new widget is covered without editing this script.
const contract = JSON.parse(fs.readFileSync(new URL('../widgets/modernizer-widgets.json', import.meta.url), 'utf8')).widgets;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: BROWSERS.find((p) => p && fs.existsSync(p)), headless: 'new',
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
  return { page, errors };
}
const text = (page, selector) => page.$eval(selector, (el) => el.textContent.trim()).catch(() => null);

try {
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
        const bare = Object.keys(blocks).filter((b) => !blocks[b]);
        if (bare.length) out[cell.dataset.kind] = bare;
      }
      return out;
    });
    check('every Carbon component a widget uses is styled', Object.keys(unstyled).length === 0, unstyled);
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
} catch (e) {
  check('harness ran', false, String(e).slice(0, 500));
} finally {
  await browser.close();
}

for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}${r.ok || r.detail === undefined ? '' : `  ${JSON.stringify(r.detail)}`}`);
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
