// Walk a BAW client-side human service in a real browser and report what happened.
//
// Usage:
//   node scripts/verify-service.mjs --app ZZEQ --service "Equipment Request (Modernized)" [--snapshot 1.1.0] [--out shots] [--fill]
//   node scripts/verify-service.mjs --url <a task's coach URL> [--press "Send Back"] ...
//   node scripts/verify-service.mjs --app ZZEQ --service "Equipment Request" --value "Request ID=R-1" --press Load
//
// --url opens a process task instead of an exposed service. --press (repeatable) presses the named
// buttons in order, each on the first coach that shows it, instead of the forward button.
// --value "Label=text" (repeatable) types the text into the field with that label, on the first coach
// that has such a field, before any button of that coach is pressed. It works in classic UI Toolkit
// coaches and in React ones, for text, number, radio, checkbox and switch fields (a checkbox or switch
// takes yes or no). Buttons never pressed and values never typed are listed in the report.
//
// Logs in with BAW_URL, BAW_USER and BAW_PASSWORD or BAW_APIKEY from the environment, else from the
// BAW_* keys of the repository's .env (other keys are never read; token kept in memory, never printed), opens the service's run URL,
// then on every coach takes a screenshot and presses the forward button: the primary React
// button, or the native primary / last non-Back button. It stops when no coach is left.
//
// --tabs visits every tab of a Tab Section on each coach before the forward button is pressed: it opens the
// tab, waits for its content, fills its fields (with --fill; a Yes option is chosen for Boolean radios, and a
// date field that refuses typed text is set directly) and takes a screenshot named <step>-<screen>-<tab>.png.
// --expect-blocked presses the forward button once on the first coach with nothing filled and passes only if
// the coach stays, visible error indicators appear and the first tab with an error is the one on screen. On a React coach with tabs it
// then fills the first tab only and presses forward again: the coach must stay and show the first tab that
// still has an error (reported as blocked.partial). Then the run goes on as usual. When every tab has its own button bar, the forward button is the one on the last
// tab (the others only switch tabs): the run opens that tab to press it, and goes back to it after --tabs.
// When the last tab does not open while the first is empty (form.tabsInOrder), the run fills the tabs in order and
// presses the last tab's button; --expect-blocked then presses the first tab's Next on the empty form (it must stay
// there with errors), fills the first tab and presses the finishing button (it must stop on the next tab with errors). --draft "Save as Draft" types the --value fields, presses that button on the first
// coach that shows it and passes when the coach closes; the report names the tab that was open (the resumed draft has to reopen on it). --check "Label=text" (repeatable) reads the field with
// that label on the first coach that has it and fails when it does not hold the text (a resumed draft).
// Fails (exit 1) on page errors, a screen that does not change after a press, duplicate
// screenshots, or not reaching the end within --max-steps.
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseArgs } from 'node:util';
import puppeteer from 'puppeteer-core';
import { findBrowser, isHelium } from './browsers.mjs';

const { values: args } = parseArgs({
  options: {
    app: { type: 'string' }, service: { type: 'string' }, snapshot: { type: 'string' },
    out: { type: 'string', default: 'verify-shots' }, 'max-steps': { type: 'string', default: '12' },
    fill: { type: 'boolean', default: false }, url: { type: 'string' }, press: { type: 'string', multiple: true, default: [] },
    value: { type: 'string', multiple: true, default: [] }, check: { type: 'string', multiple: true, default: [] },
    tabs: { type: 'boolean', default: false }, 'expect-blocked': { type: 'boolean', default: false }, draft: { type: 'string' },
  },
});
if (!args.url && (!args.app || !args.service)) {
  console.error('Usage: node scripts/verify-service.mjs --app <acronym> --service "<exposed service name>" [--snapshot <name>] [--out <dir>], or --url <task URL>');
  process.exit(2);
}

const envFile = new URL('../../.env', import.meta.url);
const fileEnv = fs.existsSync(envFile) ? Object.fromEntries(fs.readFileSync(envFile, 'utf8').split('\n')
  .filter((l) => /^\s*BAW_[A-Z_]*\s*=/.test(l))
  .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim().replace(/^["']|["']$/g, '')])) : {};
const setting = (key) => process.env[key] || fileEnv[key];
// Certificates are verified unless the cluster is explicitly marked insecure; a parent's NODE_TLS_REJECT_UNAUTHORIZED must not switch verification off.
const insecure = /^(1|true|yes)$/i.test((setting('BAW_TLS_INSECURE') || '').trim());
if (insecure) process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
else delete process.env.NODE_TLS_REJECT_UNAUTHORIZED;
if (setting('BAW_CA_FILE') && !process.env.NODE_EXTRA_CA_CERTS) {
  console.error('BAW_CA_FILE is set but NODE_EXTRA_CA_CERTS is not: Node will not trust that CA when run standalone. The MCP server run_browser sets it; Chrome also needs the CA in the system trust store.');
}
const BASE = setting('BAW_URL')?.replace(/\/+$/, '');
const secret = setting('BAW_PASSWORD') ? { password: setting('BAW_PASSWORD') } : { api_key: setting('BAW_APIKEY') };
if (!BASE || !setting('BAW_USER') || !(secret.password || secret.api_key)) {
  console.error('Missing BAW settings: BAW_URL, BAW_USER, and BAW_PASSWORD or BAW_APIKEY (environment or .env)');
  process.exit(2);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A certificate failure names the settings that fix it. A redirect is never followed: the login body carries the password, and a 307 would resend it to wherever the Location header points.
const CERT_CODES = /^(UNABLE_TO_VERIFY_LEAF_SIGNATURE|UNABLE_TO_GET_ISSUER_CERT_LOCALLY|SELF_SIGNED_CERT_IN_CHAIN|DEPTH_ZERO_SELF_SIGNED_CERT|CERT_HAS_EXPIRED|CERT_NOT_YET_VALID|ERR_TLS_CERT_ALTNAME_INVALID)$/;
const baw = async (url, init) => {
  try {
    return await fetch(url, { ...init, redirect: 'error' });
  } catch (e) {
    const code = e?.cause?.code;
    if (CERT_CODES.test(code || '')) {
      throw new Error(`Certificate check failed (${code}) for ${new URL(url).host}: set BAW_CA_FILE to the cluster's CA (it is passed to Node as NODE_EXTRA_CA_CERTS; Chrome needs the CA in the system trust store), or set BAW_TLS_INSECURE=true for a test cluster`);
    }
    if (String(e?.cause?.message || e?.message).includes('redirect')) throw new Error(`${new URL(url).host} answered with a redirect, which is refused so credentials are not re-sent`);
    throw e;
  }
};
const auth = await baw(`${BASE}/icp4d-api/v1/authorize`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: setting('BAW_USER'), ...secret }),
});
const { token } = await auth.json();
if (!token) throw new Error(`Login failed (HTTP ${auth.status})`);

let item = { runURL: args.url && new URL(args.url, BASE).href };
if (!args.url) {
  const exposed = await (await baw(`${BASE}/bas/rest/bpm/wle/v1/exposed/service`, { headers: { Authorization: `Bearer ${token}` } })).json();
  item = exposed.data.exposedItemsList.find((i) => i.processAppAcronym === args.app && i.display === args.service
    && (args.snapshot ? i.snapshotName === args.snapshot : i.tip));
  if (!item) throw new Error(`No exposed service "${args.service}" in ${args.app} ${args.snapshot || '(tip)'}`);
}
const presses = [...args.press];
const labelled = (flag, list) => list.map((v) => {
  const at = v.indexOf('=');
  if (at < 1) { console.error(`--${flag} needs "Label=text", got "${v}"`); process.exit(2); }
  return { label: v.slice(0, at).trim(), text: v.slice(at + 1) };
});
const typing = labelled('value', args.value);
const checking = labelled('check', args.check);
// Tab walking and its fill refinements apply only when asked for, so other runs behave as they always did.
const deep = args.tabs || args['expect-blocked'];
const showTab = deep || !!args.draft || checking.length > 0;

// Every selector the tab, error and draft detection depends on, in one place: tune them here against the live coach.
const SELECTORS = {
  tab: '.nav-tabs a, [role=tab]',
  activeTab: '.nav-tabs li.active, [role=tab][aria-selected=true]',
  error: '.has-error, [aria-invalid=true]',
};

// Runs inside each frame: describe the coach and pick the forward button.
function inspectCoach() {
  const visible = (el) => !!el.offsetParent;
  const react = document.querySelector('.pp-app');
  const buttons = [...document.querySelectorAll(react ? '.pp-app .pp-actions button' : 'button')].filter(visible);
  if (!buttons.length) return null;
  const back = /^\W*(back|previous|prev|cancel|close)\b/i;
  const forward = react
    ? [...buttons].reverse().find((b) => b.className.includes('btn--primary')) || buttons[buttons.length - 1]
    : buttons.find((b) => b.className.includes('btn-primary')) || [...buttons].reverse().find((b) => !back.test(b.textContent.trim()));
  const title = (document.querySelector('.pp-app h1') || document.querySelector('h1,.panel-title,.BPMSectionHeader'))?.textContent.trim();
  return {
    react: !!react, title: title || document.title, button: forward?.textContent.trim(), buttons: buttons.map((b) => b.textContent.trim()),
    alert: document.querySelector('.pp--inline-notification--error')?.textContent.trim(),
    signature: document.body.innerText.length + ':' + document.body.innerText.slice(0, 2000) + '|' + fieldValues(),
  };
  // What the user has typed or ticked, so a Load that refills the same coach counts as a change.
  function fieldValues() {
    return [...document.querySelectorAll('input:not([type=hidden]), textarea, select')].filter(visible)
      .map((el) => (el.type === 'checkbox' || el.type === 'radio' ? (el.checked ? '1' : '0') : el.value)).join('\u0001');
  }
}

// Run inside each frame (selectors passed in): the visible tab names, the active one, and the visible
// error indicators (innermost only, so a wrapper and the field in it count once) with their text.
function listTabs(sel) {
  const names = [];
  for (const a of document.querySelectorAll(sel.tab)) {
    const name = a.textContent.trim();
    if (a.offsetParent && name && !names.includes(name)) names.push(name);
  }
  return names;
}
function activeTabName(sel) {
  return [...document.querySelectorAll(sel.activeTab)].find((el) => el.offsetParent)?.textContent.trim();
}
// The active tab with the size of the page text, to see when a tab's content has stopped changing.
function tabState(sel) {
  return { active: [...document.querySelectorAll(sel.activeTab)].find((el) => el.offsetParent)?.textContent.trim(), size: document.body.innerText.length };
}
function visibleErrors(sel) {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  // A flagged input has no text of its own: report the message it points to, else its label.
  const linked = (el) => ['aria-errormessage', 'aria-describedby'].flatMap((a) => (el.getAttribute(a) || '').split(/\s+/))
    .map((id) => id && clean(document.getElementById(id)?.textContent)).find(Boolean);
  return [...document.querySelectorAll(sel.error)].filter((el) => el.offsetParent && !el.querySelector(sel.error))
    .map((el) => (clean(el.textContent) || linked(el) || clean(el.labels?.[0]?.textContent) || clean(el.getAttribute('aria-label'))).slice(0, 120));
}

// Runs inside each frame: the visible field whose label reads `label` (UI Toolkit labels are not always
// tied to the input, so fall back to the nearest label around a field that has no sibling field).
function findField(label) {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').replace(/[\s*:]+$/, '').trim().toLowerCase();
  const all = [...document.querySelectorAll('input:not([type=hidden]):not([type=button]):not([type=submit]):not([type=checkbox]):not([type=radio]), textarea, select')];
  const fields = all.filter((el) => !!el.offsetParent);
  const labelsOf = (el) => {
    const found = [el.getAttribute('aria-label')];
    for (const id of (el.getAttribute('aria-labelledby') || '').split(/\s+/)) found.push(document.getElementById(id)?.textContent);
    if (el.id) found.push(...[...document.querySelectorAll('label')].filter((l) => l.htmlFor === el.id).map((l) => l.textContent));
    found.push(el.closest('label')?.textContent);
    for (let box = el.parentElement, up = 0; box && up < 5 && box.querySelectorAll('input:not([type=hidden]), textarea, select').length === 1; box = box.parentElement, up++) {
      found.push(box.querySelector('label, .control-label, legend')?.textContent);
    }
    return found.map(norm).filter(Boolean);
  };
  const want = norm(label);
  const exact = fields.find((el) => labelsOf(el).includes(want));
  // A field with exactly this label on another tab is the one meant: "Broker" must not fall back to "Broker Commission".
  if (exact || all.some((el) => !el.offsetParent && labelsOf(el).includes(want))) return exact || null;
  return fields.find((el) => labelsOf(el).some((t) => t.includes(want))) || null;
}

// Runs inside each frame: the visible radio group whose label reads `label`, as its options
// [{text, checked}], and when `pick` names an option, that option is clicked. null when there is no such group.
function radioGroup(label, pick) {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').replace(/[\s*:?]+$/, '').trim().toLowerCase();
  const want = norm(label);
  // A React radio group is a fieldset with a legend; a classic one is its CoachView.
  const groups = (inputs) => [...new Set(inputs.map((el) => el.closest('.pp-app fieldset') || el.closest('.CoachView') || el.parentElement))];
  const radios = [...document.querySelectorAll('input[type=radio]')];
  const views = groups(radios.filter((el) => el.offsetParent));
  const caption = (view) => norm(view.querySelector('.control-label, legend, label:not(:has(input))')?.textContent);
  const exact = views.find((v) => caption(v) === want);
  const elsewhere = !exact && groups(radios.filter((el) => !el.offsetParent)).some((v) => caption(v) === want);
  const view = exact || (elsewhere ? null : views.find((v) => caption(v).includes(want)));
  if (!view) return null;
  // React hides the input behind its label, so the label (found by `for`) carries the text and takes the click.
  const labelFor = (input) => (input.id ? [...document.querySelectorAll('label')].find((l) => l.htmlFor === input.id) : null);
  const options = [...view.querySelectorAll('input[type=radio]')].map((input) => ({
    input, label: labelFor(input), text: (input.closest('label')?.textContent || labelFor(input)?.textContent || input.nextElementSibling?.textContent || input.value || '').trim() }));
  const chosen = pick === undefined ? null : options.find((o) => norm(o.text) === norm(pick));
  if (pick !== undefined && !chosen) return { missing: options.map((o) => o.text) };
  if (chosen) (view.closest('.pp-app') && chosen.label || chosen.input).click();
  return options.map((o) => ({ text: o.text, checked: o.input.checked }));
}

// Runs inside each frame: the visible checkbox or switch (a Toggle widget) whose label reads `label`, as
// {on}; when `set` is true or false it is clicked until it matches. null when there is no such control.
function toggleOf(label, set) {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').replace(/[\s*:?]+$/, '').trim().toLowerCase();
  const labelFor = (el) => (el.id ? [...document.querySelectorAll('label')].filter((l) => l.htmlFor === el.id) : []);
  const labelsOf = (el) => {
    const found = [el.getAttribute('aria-label'), ...labelFor(el).map((l) => l.textContent), el.closest('label')?.textContent];
    for (const id of (el.getAttribute('aria-labelledby') || '').split(/\s+/)) found.push(document.getElementById(id)?.textContent);
    return found.map(norm).filter(Boolean);
  };
  // React hides a checkbox's input behind its label, so the label is what is visible.
  const shown = (el) => !!el.offsetParent || labelFor(el).some((l) => !!l.offsetParent) || !!el.closest('label')?.offsetParent;
  const all = [...document.querySelectorAll('input[type=checkbox], button[role=switch]')];
  const want = norm(label);
  const exact = all.filter(shown).find((el) => labelsOf(el).includes(want));
  // A control with exactly this label on another tab is the one meant.
  if (!exact && all.some((el) => !shown(el) && labelsOf(el).includes(want))) return null;
  const el = exact || all.filter(shown).find((e) => labelsOf(e).some((t) => t.includes(want)));
  if (!el) return null;
  const isSwitch = el.getAttribute('role') === 'switch';
  const isOn = () => (isSwitch ? el.getAttribute('aria-checked') === 'true' : el.checked);
  if (set !== undefined && set !== isOn()) (isSwitch ? el : labelFor(el)[0] || el.closest('label') || el).click();
  return { on: isOn() };
}

// Type text into the field labelled `label`, replacing what is there (a radio group picks the option with that
// text, e.g. Yes or No; a checkbox or switch is turned on by yes/true/on/checked/1 and off by no/false/off/unchecked/0).
// Returns false when the coach has no such field.
async function typeInto(frame, label, text) {
  const field = (await frame.evaluateHandle(findField, label)).asElement();
  if (!field) {
    const radios = await frame.evaluate(radioGroup, label, text);
    if (radios && radios.missing) throw new Error(`"${label}" has no option "${text}" (it has ${radios.missing.join(', ')})`);
    if (radios) return true;
    const word = text.trim().toLowerCase();
    const set = /^(yes|true|on|checked|1)$/.test(word) ? true : /^(no|false|off|unchecked|0)$/.test(word) ? false : undefined;
    if (set === undefined && await frame.evaluate(toggleOf, label)) throw new Error(`"${label}" is a checkbox or switch: give it yes or no, not "${text}"`);
    return set !== undefined && !!(await frame.evaluate(toggleOf, label, set));
  }
  if (await field.evaluate((el) => el.tagName === 'SELECT')) {
    const choice = await field.evaluate((el, want) => [...el.options].find((o) => o.value === want || o.textContent.trim() === want)?.value, text);
    if (choice === undefined) throw new Error(`"${label}" has no option "${text}"`);
    await field.select(choice);
    return true;
  }
  await field.evaluate((el) => { el.focus(); try { el.select(); } catch { /* types without a selection */ } });
  await field.press('Backspace');
  if (text) await field.type(text);
  await field.evaluate((el) => el.blur()); // leaving the field makes the coach take the value
  return true;
}

// Read the value of the field labelled `label` (the chosen option's text for a dropdown or a radio group, "" when no radio is chosen); undefined when there is no such field.
async function readField(frame, label) {
  const field = (await frame.evaluateHandle(findField, label)).asElement();
  if (field) return field.evaluate((el) => (el.tagName === 'SELECT' ? el.selectedOptions[0]?.textContent.trim() : el.value));
  const radios = await frame.evaluate(radioGroup, label);
  if (radios) return radios.find((o) => o.checked)?.text ?? '';
  const toggle = await frame.evaluate(toggleOf, label);
  return toggle ? (toggle.on ? 'Yes' : 'No') : undefined;
}

// Press the visible button with exactly this text.
const pressButton = (frame, label) => frame.evaluate((text) => {
  const react = document.querySelector('.pp-app');
  [...document.querySelectorAll(react ? '.pp-app .pp-actions button' : 'button')]
    .find((b) => b.offsetParent && b.textContent.trim() === text).click();
}, label);

// --fill: type into the coach's empty editable fields (the field's example placeholder, today's date for date
// pickers, 1 for number inputs, or "Test"), tick unticked checkboxes, turn on switches that are off (a Toggle
// widget), pick the first option of empty dropdowns and of radio groups with nothing chosen. Works in React
// coaches (inside .pp-app) and in classic UI Toolkit ones (the whole frame). Returns the count.
async function fill(frame, react, refine = false) {
  const at = react ? '.pp-app ' : '';
  let count = 0;
  const typable = 'input:not([readonly]):not([disabled]):not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=button]):not([type=submit])';
  for (const input of await frame.$$(`${at}${typable}, ${at}textarea:not([readonly]):not([disabled])`)) {
    // A classic UI Toolkit control is a text input inside a CoachView whose class names the control.
    // A Carbon number input is a text input inside the number widget (inputmode decimal).
    const { empty, placeholder, visible, type, control } = await input.evaluate((el) => {
      const view = el.closest('.CoachView');
      const is = (name) => !!view && (view.classList.contains(name) || (view.getAttribute('data-type') || '').endsWith(`.${name}`));
      const number = is('Integer') || is('Decimal') || !!el.closest('.cds--number') || el.inputMode === 'decimal' || el.inputMode === 'numeric';
      // A shown 0 is an answer (a resumed draft's 0 must survive); a new form's required numbers start blank.
      return { empty: !el.value, placeholder: el.placeholder, visible: !!el.offsetParent, type: el.type, control: number ? 'number' : is('Date_Picker') || is('Date_Time_Picker') ? 'date' : '' };
    });
    if (!empty || !visible) continue;
    const now = new Date();
    const today = now.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
    const iso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const text = type === 'number' || control === 'number' ? '1' : type === 'date' ? iso : placeholder === 'mm/dd/yyyy' || control === 'date' ? today : placeholder || 'Test';
    await input.evaluate((el) => { if (el.value) { el.focus(); try { el.select(); } catch { /* types without a selection */ } } }); // replaces a shown 0
    await input.type(text);
    await input.press('Tab');
    // A classic date picker can drop typed text: set the value and tell the widget it changed.
    if (refine && !react && await input.evaluate((el) => !el.value && el.tagName === 'INPUT').catch(() => false)) {
      await input.evaluate((el, value) => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, value);
        for (const name of ['input', 'change', 'blur']) el.dispatchEvent(new Event(name, { bubbles: true }));
      }, text);
    }
    if (await input.evaluate((el) => !!el.value).catch(() => true)) count++; // a field that refused the text (a classic date picker) stays empty
  }
  for (const box of await frame.$$(`${at}input[type=checkbox]:not(:checked):not([readonly]):not([disabled])`)) {
    // React hides the input behind its label; a classic checkbox is the visible input itself.
    const ticked = await box.evaluate((el, react) => {
      if (react) { el.parentElement.querySelector('label')?.click(); return true; }
      if (!el.offsetParent) return false;
      el.click();
      return true;
    }, react);
    if (ticked) count++;
  }
  for (const toggle of await frame.$$(`${at}button[role=switch][aria-checked=false]:not([disabled]):not([aria-readonly=true])`)) {
    if (!(await toggle.evaluate((el) => !!el.offsetParent))) continue;
    await toggle.click();
    count++;
  }
  for (const select of await frame.$$(`${at}select:not([disabled])`)) {
    const value = await select.evaluate((el) => (!el.value && el.offsetParent ? [...el.options].find((o) => o.value)?.value : null));
    if (value) { await select.select(value); count++; }
  }
  if (!react) {
    // Classic radio groups are not wrapped in a fieldset: group the radios by name.
    return count + await frame.evaluate((refine) => {
      const seen = new Set();
      let picked = 0;
      for (const radio of document.querySelectorAll('input[type=radio]:not([readonly]):not([disabled])')) {
        if (!radio.offsetParent || !radio.name || seen.has(radio.name)) continue;
        seen.add(radio.name);
        if ([...document.querySelectorAll(`input[type=radio][name="${CSS.escape(radio.name)}"]`)].some((r) => r.checked)) continue;
        // A Boolean radio gets its Yes option; any other group its first.
        const labelOf = (r) => (document.querySelector(`label[for="${CSS.escape(r.id)}"]`) || r.closest('label') || r.parentElement)?.textContent.trim();
        const group = [...document.querySelectorAll(`input[type=radio][name="${CSS.escape(radio.name)}"]`)];
        (refine && group.find((r) => /^yes$/i.test(labelOf(r))) || radio).click();
        picked++;
      }
      return picked;
    }, refine);
  }
  for (const group of await frame.$$('.pp-app fieldset')) {
    const picked = await group.evaluate((el, refine) => {
      const radios = [...el.querySelectorAll('input[type=radio]:not([readonly]):not([disabled])')];
      if (!radios.length || radios.some((r) => r.checked) || !el.offsetParent) return false;
      // A Boolean radio gets its Yes option; any other group its first.
      const labelOf = (r) => el.querySelector(`label[for="${CSS.escape(r.id)}"]`);
      const radio = refine && radios.find((r) => /^yes$/i.test(labelOf(r)?.textContent.trim())) || radios[0];
      labelOf(radio)?.click();
      return true;
    }, refine);
    if (picked) count++;
  }
  return count;
}

const executablePath = findBrowser();
// Cookies are bound to the port and scheme they were set for, so the token cookie reaches the BAW port only. Puppeteer merges this flag into the single --enable-features list it passes to Chrome, next to its own features.
const browser = await puppeteer.launch({
  executablePath, headless: 'new', acceptInsecureCerts: insecure,
  args: ['--no-first-run', '--enable-features=EnablePortBoundCookies,EnableSchemeBoundCookies', ...(insecure ? ['--ignore-certificate-errors'] : []), `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), 'baw-verify-'))}`],
});
const bawOrigin = new URL(BASE).origin;
const report = { app: args.app, service: args.service || args.url, snapshot: item.snapshotName, steps: [], errors: [], notes: [], ok: false };
// A run URL on another origin gets no token, so the page is expected to ask for a login: say why instead of failing quietly.
try {
  const runOrigin = new URL(item.runURL).origin;
  if (runOrigin !== bawOrigin) report.notes.push(`run URL is on ${runOrigin}, not BAW_URL's origin: no credentials are sent to it`);
  fs.mkdirSync(args.out, { recursive: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000 });
  // The token goes only to the BAW origin: a host-only cookie the page cannot read, bound to the BAW port and the https scheme (sourcePort/sourceScheme, with the port-bound cookie features enabled at launch), and an
  // Authorization header added per request, so a cross-origin image, script or redirect target never sees it (an Authorization header of the page's own is dropped).
  await page.setCookie({ name: 'ibm-private-cloud-session', value: token, url: BASE, httpOnly: true, secure: true, sameSite: 'Lax', sourcePort: Number(new URL(BASE).port) || 443, sourceScheme: 'Secure' });
  await page.setRequestInterception(true);
  page.on('request', (req) => {
    if (req.isInterceptResolutionHandled()) return;
    let origin = null;
    try { origin = new URL(req.url()).origin; } catch { /* not a URL: send without credentials */ }
    const headers = { ...req.headers() };
    delete headers.authorization;
    if (origin === bawOrigin) headers.authorization = `Bearer ${token}`;
    // A request the page already abandoned (navigation, close) rejects here: that must not take the run down.
    req.continue({ headers }).catch((e) => report.notes.push(`request not continued: ${String(e).slice(0, 120)}`));
  });
  let posts = 0;
  page.on('request', (req) => { if (req.method() === 'POST') posts++; });
  page.on('pageerror', (e) => report.errors.push(String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error') report.errors.push(`console: ${m.text().slice(0, 300)}`); });
  page.on('response', (r) => { // a server error says why in its body (for example a service call from the coach that BAW rejects)
    if (r.status() >= 500) r.text().then((body) => report.errors.push(`HTTP ${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}: ${body.replace(/\s+/g, ' ').slice(0, 300)}`)).catch(() => {});
  });
  try {
    await page.goto(item.runURL, { waitUntil: 'networkidle2', timeout: 90000 });
  } catch (e) {
    if (String(e).includes('net::ERR_ABORTED') && isHelium(executablePath)) {
      throw new Error(`Helium aborted loading the page (${String(e).slice(0, 160)}); Helium cannot open a BAW task link. Install Chrome or Brave, or Chrome for Testing with \`npx @puppeteer/browsers install chrome@stable --path ~/.cache/puppeteer\`, or set BROWSER_PATH to another Chromium browser`);
    }
    throw e;
  }

  const coach = async (timeout = 30000) => {
    for (const end = Date.now() + timeout; Date.now() < end; await sleep(500)) {
      for (const frame of page.frames()) {
        const info = await frame.evaluate(inspectCoach).catch(() => null);
        if (info) return { frame, info };
      }
    }
    return null;
  };
  // The coach scrolls inside a frame as tall as the window, so grow the window to the whole coach first.
  const shoot = async (frame, file) => {
    const top = (await (await frame.frameElement())?.boundingBox())?.y || 0;
    const height = await frame.evaluate(() => document.documentElement.scrollHeight).catch(() => 0);
    await page.setViewport({ width: 1400, height: Math.min(Math.max(1000, Math.ceil(top + height)), 8000) });
    await sleep(300);
    const shot = await page.screenshot({ path: file, fullPage: true });
    await page.setViewport({ width: 1400, height: 1000 });
    return shot;
  };
  const slug = (text) => text.replace(/[^a-z0-9]+/gi, '-').toLowerCase().slice(0, 40);
  // Open a tab and wait until it is the active one and its content has stopped changing.
  const openTab = async (frame, name) => {
    await frame.evaluate((sel, want) => {
      [...document.querySelectorAll(sel.tab)].find((a) => a.offsetParent && a.textContent.trim() === want)?.click();
    }, SELECTORS, name);
    let size = -1;
    for (const end = Date.now() + 8000; Date.now() < end; await sleep(200)) {
      const now = await frame.evaluate(tabState, SELECTORS).catch(() => null);
      if (now && now.active === name && now.size === size) return true;
      size = now ? now.size : -1;
    }
    return false;
  };
  // Which button moves the task on when every tab has its own button bar. The buttons that switch tabs differ
  // from the one that finishes, so a coach whose first and last tabs pick different forward buttons has
  // per-tab bars and the forward button is the last tab's pick; a shared bar gives the same pick on both and
  // needs no tab. Leaves the tab that was open when called open again.
  const forwardRoute = async (frame) => {
    const names = await frame.evaluate(listTabs, SELECTORS).catch(() => []);
    if (names.length < 2) return {};
    const home = await frame.evaluate(activeTabName, SELECTORS).catch(() => undefined);
    const pick = async (name) => {
      await openTab(frame, name);
      return (await frame.evaluate(inspectCoach).catch(() => null))?.button;
    };
    const first = await pick(names[0]);
    // Tabs in order (form.tabsInOrder): the empty first tab keeps the user, so the last tab does not open and its
    // button is read once the earlier tabs are filled.
    if (!(await openTab(frame, names[names.length - 1])) && (await frame.evaluate(activeTabName, SELECTORS).catch(() => undefined)) === names[0]) {
      return { tab: names[names.length - 1], inOrder: true };
    }
    const last = (await frame.evaluate(inspectCoach).catch(() => null))?.button;
    if (home && home !== names[names.length - 1]) await openTab(frame, home);
    return first && last && first !== last ? { button: last, tab: names[names.length - 1] } : {};
  };
  // Open the tab that holds the forward button, unless it is open already.
  const showForwardTab = async (frame, tab) => {
    if (tab && (await frame.evaluate(activeTabName, SELECTORS).catch(() => undefined)) !== tab) await openTab(frame, tab);
  };
  // Visit every tab: open it, fill its fields (with --fill), screenshot it; then go back to the tab with the
  // forward button (the first tab when the buttons are shared).
  const walkTabs = async (frame, react, stem, home) => {
    const names = await frame.evaluate(listTabs, SELECTORS).catch(() => []);
    if (names.length < 2) return undefined;
    const visits = [];
    for (const name of names) {
      const opened = await openTab(frame, name);
      const visit = { tab: name, opened };
      if (args.fill) visit.filled = await fill(frame, react, true);
      visit.screenshot = path.join(args.out, `${stem}-${slug(name)}.png`);
      await shoot(frame, visit.screenshot);
      visits.push(visit);
    }
    await openTab(frame, home || names[0]);
    return visits;
  };
  // Press the forward button with nothing filled: the coach must stay, show error indicators and have the first tab with an error open.
  // On a React screen it then fills the first tab only and presses forward again: that must block too, with the first
  // tab that still has an error open (reported as `partial`).
  const checkBlocked = async (frame, label, title, stem, tab, react, inOrder) => {
    const result = { button: label, stayed: false, errors: [] };
    const names = await frame.evaluate(listTabs, SELECTORS).catch(() => []);
    const postsBefore = posts;
    // With tabs in order the last tab cannot be opened yet: the first tab's own button (Next) is pressed instead.
    if (inOrder) result.tabsInOrder = { lastTabOpened: false, pressed: label };
    else await showForwardTab(frame, tab);
    await pressButton(frame, label);
    for (const end = Date.now() + 10000; Date.now() < end && !result.errors.length; await sleep(300)) {
      result.errors = await frame.evaluate(visibleErrors, SELECTORS).catch(() => []);
    }
    const after = await coach(3000);
    // With a bar per tab the check opens the first tab with an error, which shows Next, not the pressed button.
    result.stayed = !!after && (tab || after.info.buttons.includes(label)) && after.info.title === title;
    result.requestsSent = posts - postsBefore;
    if (!after) return { ...result, failure: `"${label}" moved on with nothing filled: the required check did not block` };
    result.screenshot = path.join(args.out, `${stem}-blocked.png`);
    await shoot(after.frame, result.screenshot);
    result.tab = await after.frame.evaluate(activeTabName, SELECTORS).catch(() => undefined);
    if (names.length > 1) {
      const errorTabs = [];
      for (const name of names) { // the first tab, in tab order, that holds an error indicator
        await openTab(after.frame, name);
        if ((await after.frame.evaluate(visibleErrors, SELECTORS).catch(() => [])).length) {
          errorTabs.push(name);
          if (!result.firstErrorTab) result.firstErrorTab = name;
          if (!react) break;
        }
      }
      if (react) result.errorTabs = errorTabs;
      if (result.tab) await openTab(after.frame, result.tab);
    }
    if (!result.stayed) result.failure = `"${label}" moved on with nothing filled: the required check did not block`;
    else if (!result.errors.length) result.failure = `the coach stayed after "${label}" but shows no error indicator (${SELECTORS.error})`;
    else if (result.firstErrorTab && result.tab !== result.firstErrorTab) result.failure = `tab "${result.tab}" is open but the first tab with an error is "${result.firstErrorTab}"`;
    result.ok = !result.failure;
    if (result.ok && (react || inOrder) && names.length > 1) {
      if (react && !result.errorTabs.some((name) => name !== names[0])) {
        result.partial = { skipped: 'only the first tab has errors, so filling it would let the coach move on' };
      } else {
        result.partial = await checkPartial(after.frame, label, title, stem, tab, names, inOrder, react);
        result.ok = result.partial.ok;
        result.failure = result.partial.failure;
      }
    }
    return result;
  };
  // Fill the first tab only, press forward and expect to be blocked on the first tab that is still incomplete.
  const checkPartial = async (frame, label, title, stem, tab, names, inOrder, react) => {
    const partial = { filledTab: names[0], button: label, stayed: false, errors: [] };
    await openTab(frame, names[0]);
    partial.filled = await fill(frame, react, true);
    const postsBefore = posts;
    await showForwardTab(frame, tab);
    if (inOrder) { // the finishing button is the one on the last tab, which opens now that the first tab is filled
      partial.lastTabOpened = (await frame.evaluate(activeTabName, SELECTORS).catch(() => undefined)) === tab;
      if (!partial.lastTabOpened) {
        partial.screenshot = path.join(args.out, `${stem}-blocked-partial.png`);
        await shoot(frame, partial.screenshot);
        return { ...partial, ok: false, failure: `with the first tab ("${names[0]}") filled, the last tab ("${tab}") still does not open` };
      }
      label = partial.button = (await frame.evaluate(inspectCoach).catch(() => null))?.button || label;
    }
    await pressButton(frame, label);
    for (const end = Date.now() + 10000; Date.now() < end && !partial.errors.length; await sleep(300)) {
      partial.errors = await frame.evaluate(visibleErrors, SELECTORS).catch(() => []);
    }
    const after = await coach(3000);
    partial.stayed = !!after && (tab || after.info.buttons.includes(label)) && after.info.title === title;
    partial.requestsSent = posts - postsBefore;
    if (!after) return { ...partial, ok: false, failure: `"${label}" moved on with only the first tab ("${names[0]}") filled: the other tabs' required checks did not block` };
    partial.screenshot = path.join(args.out, `${stem}-blocked-partial.png`);
    await shoot(after.frame, partial.screenshot);
    partial.tab = await after.frame.evaluate(activeTabName, SELECTORS).catch(() => undefined);
    for (const name of names) { // the first tab, in tab order, that still holds an error indicator
      await openTab(after.frame, name);
      if ((await after.frame.evaluate(visibleErrors, SELECTORS).catch(() => [])).length) { partial.firstErrorTab = name; break; }
    }
    if (partial.tab) await openTab(after.frame, partial.tab);
    if (!partial.stayed) partial.failure = `"${label}" moved on with only the first tab ("${names[0]}") filled: the other tabs' required checks did not block`;
    else if (!partial.errors.length) partial.failure = `the coach stayed after "${label}" with only the first tab filled but shows no error indicator (${SELECTORS.error})`;
    else if (partial.firstErrorTab && partial.tab !== partial.firstErrorTab) partial.failure = `with the first tab filled, tab "${partial.tab}" is open but the first tab with an error is "${partial.firstErrorTab}"`;
    else if (partial.tab === names[0]) partial.failure = `with the first tab filled, the first tab ("${names[0]}") is still the one with errors: the filled values were not accepted`;
    partial.ok = !partial.failure;
    return partial;
  };
  const hashes = new Set();
  let blockedChecked = false, draftDone = false;
  let current = await coach();
  if (!current) {
    await page.screenshot({ path: path.join(args.out, '00-no-coach.png'), fullPage: true });
    throw new Error('no coach rendered (see 00-no-coach.png)');
  }
  for (let step = 1; current && step <= Number(args['max-steps']); step++) {
    await sleep(1500); // let React and BAW finish rendering
    // A frame that closed with no coach left means the service ended after the last press.
    current = (await coach()) || (current.frame.detached ? null : current);
    if (!current) break;
    const typed = [];
    const typePending = async () => {
      for (const field of typing.filter((t) => !t.done)) {
        if (await typeInto(current.frame, field.label, field.text)) { field.done = true; typed.push(field.label); }
      }
    };
    // The blocked check presses forward on the empty screen, so values wait until it has run.
    const blockFirst = args['expect-blocked'] && !blockedChecked;
    if (!blockFirst) await typePending();
    // A draft run types the fields of every tab and stays on the last tab it typed on, so the tab the draft is
    // saved from (and the one the task reopens on) is not the first.
    if (args.draft && typing.some((t) => !t.done)) {
      for (const name of await current.frame.evaluate(listTabs, SELECTORS).catch(() => [])) {
        if (!typing.some((t) => !t.done)) break;
        await openTab(current.frame, name);
        await typePending();
      }
    }
    if (typed.length) await sleep(500);
    const stem = `${String(step).padStart(2, '0')}-${slug(current.info.title)}`;
    const file = path.join(args.out, `${stem}.png`);
    const shot = await shoot(current.frame, file);
    const hash = crypto.createHash('md5').update(shot).digest('hex');
    const { signature, buttons, ...info } = current.info;
    const tab = showTab ? await current.frame.evaluate(activeTabName, SELECTORS).catch(() => undefined) : undefined;
    // The pick above is the one on the open tab; with a bar per tab that can be a Next that only switches tabs.
    const route = await forwardRoute(current.frame);
    if (route.button) info.button = route.button;
    const forward = info.button;
    const explicit = presses.length && (buttons.includes(presses[0]) || presses[0] === route.button);
    if (explicit) info.button = presses.shift();
    const forwardTab = route.inOrder || info.button === route.button ? route.tab : undefined;
    if (route.inOrder) info.tabsInOrder = true;
    report.steps.push({ step, ...info, tab, typed: typed.length ? typed : undefined, screenshot: file, duplicate: hashes.has(hash) || undefined });
    hashes.add(hash);
    // A number control shows its value formatted, so 12.5 reads back as "12.50" and 1234.56 as "1,234.56".
    const number = (s) => (/^-?[\d,]*\.?\d+$/.test(s) ? Number(s.replaceAll(',', '')) : NaN);
    const same = (actual, expected) => actual === expected || number(actual) === number(expected);
    const readChecks = async () => {
      for (const check of checking.filter((c) => !c.done)) {
        let actual;
        for (const end = Date.now() + 5000; Date.now() < end; await sleep(500)) {
          actual = await readField(current.frame, check.label).catch(() => undefined);
          if (actual === undefined || same(actual, check.text)) break;
        }
        if (actual === undefined) continue;
        check.done = true;
        const ok = same(actual, check.text);
        (report.checked ||= []).push({ label: check.label, expected: check.text, actual, ok });
        if (!ok) report.failure ||= `"${check.label}" holds "${actual}", expected "${check.text}"`;
      }
    };
    await readChecks();
    // Fields on the other tabs are read by opening those tabs; the tab the task opened on is already in the report.
    if (checking.some((c) => !c.done)) {
      for (const name of await current.frame.evaluate(listTabs, SELECTORS).catch(() => [])) {
        if (!checking.some((c) => !c.done) || name === tab) continue;
        await openTab(current.frame, name);
        await readChecks();
      }
    }
    if (report.failure) break;
    if (args.draft && !draftDone && buttons.includes(args.draft)) {
      draftDone = true;
      await pressButton(current.frame, args.draft);
      let left = current;
      for (const end = Date.now() + 30000; left && Date.now() < end; await sleep(1000)) left = await coach(3000);
      report.draft = { button: args.draft, tab, closed: !left };
      if (left) report.failure = `"${args.draft}" did not close the coach${left.info.alert ? `: ${left.info.alert}` : ''}`;
      current = null;
      break;
    }
    if (!forward) { report.failure = 'no forward button'; break; }
    if (args['expect-blocked'] && !blockedChecked) {
      blockedChecked = true;
      const blocked = await checkBlocked(current.frame, forward, info.title, stem, forwardTab, info.react, route.inOrder);
      report.steps.at(-1).blocked = blocked;
      if (!blocked.ok) { report.failure = blocked.failure; break; }
    }
    if (blockFirst) {
      await typePending();
      if (typed.length) report.steps.at(-1).typed = typed;
    }
    // A bar per tab means the finishing button sits on the last tab and checks every tab, so a filled run
    // fills them all, not only the tab it presses on.
    if (args.tabs || args['expect-blocked'] || (args.fill && forwardTab)) {
      const visits = await walkTabs(current.frame, info.react, stem, forwardTab);
      if (visits) report.steps.at(-1).tabs = visits;
    }
    await showForwardTab(current.frame, forwardTab);
    if (route.inOrder && !explicit) { // the finishing button is on the last tab, open now that the earlier tabs are filled
      const here = await current.frame.evaluate(inspectCoach).catch(() => null);
      if (here?.button) info.button = report.steps.at(-1).button = here.button;
    }
    if (args.fill) report.steps.at(-1).filled = await fill(current.frame, info.react, deep);
    // Compare against the screen as it is now (typed and filled), not as it was when first inspected.
    const now = await current.frame.evaluate(inspectCoach).catch(() => null);
    const before = now ? now.signature : signature;
    await pressButton(current.frame, info.button);
    let next = null;
    for (const end = Date.now() + 30000; Date.now() < end; await sleep(1000)) {
      next = await coach(3000);
      if (!next || next.info.signature !== before) break;
    }
    if (next && next.info.signature === before) {
      report.failure = `stuck on "${info.title}" after pressing "${info.button}"${next.info.alert ? `: ${next.info.alert}` : ''}`;
      break;
    }
    // The same coach, now showing error indicators: a required check cancelled the press.
    const errorsLeft = next && next.info.title === info.title ? await next.frame.evaluate(visibleErrors, SELECTORS).catch(() => []) : [];
    if (errorsLeft.length) {
      report.failure = `blocked on "${info.title}" after pressing "${info.button}": ${errorsLeft.length} field(s) still show an error`;
      break;
    }
    current = next;
  }
  const unpressed = presses, untyped = typing.filter((t) => !t.done).map((t) => t.label);
  if (unpressed.length) report.unpressed = unpressed;
  if (untyped.length) report.untyped = untyped;
  const unchecked = checking.filter((c) => !c.done).map((c) => c.label);
  if (unchecked.length) report.failure ||= `fields never found to check: ${unchecked.join(', ')}`;
  if (args.draft && !draftDone) report.failure ||= `no coach showed a "${args.draft}" button`;
  if (!report.failure && current) report.failure = `still on a coach after ${args['max-steps']} steps`;
  if (!report.failure && report.steps.some((s) => s.duplicate)) report.failure = 'duplicate screenshots';
  report.ok = !report.failure && report.errors.length === 0;
} catch (e) {
  report.failure = String(e).slice(0, 300);
  if (/ERR_CERT_|ERR_SSL_/.test(report.failure)) report.failure += ' - Chrome does not trust the BAW certificate: add its CA to the system trust store, or set BAW_TLS_INSECURE=true for a test cluster (BAW_CA_FILE only reaches Node)';
} finally {
  await browser.close();
  console.log(JSON.stringify(report, null, 1));
  process.exit(report.ok ? 0 : 1);
}
