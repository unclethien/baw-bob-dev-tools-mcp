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
// coaches and in React ones. Buttons never pressed and values never typed are listed in the report.
//
// Logs in with BAW_URL, BAW_USER and BAW_PASSWORD or BAW_APIKEY from the environment, else from the
// BAW_* keys of the repository's .env (other keys are never read; token kept in memory, never printed), opens the service's run URL,
// then on every coach takes a screenshot and presses the forward button: the primary React
// button, or the native primary / last non-Back button. It stops when no coach is left.
// Fails (exit 1) on page errors, a screen that does not change after a press, duplicate
// screenshots, or not reaching the end within --max-steps.
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseArgs } from 'node:util';
import puppeteer from 'puppeteer-core';

const { values: args } = parseArgs({
  options: {
    app: { type: 'string' }, service: { type: 'string' }, snapshot: { type: 'string' },
    out: { type: 'string', default: 'verify-shots' }, 'max-steps': { type: 'string', default: '12' },
    fill: { type: 'boolean', default: false }, url: { type: 'string' }, press: { type: 'string', multiple: true, default: [] },
    value: { type: 'string', multiple: true, default: [] },
  },
});
if (!args.url && (!args.app || !args.service)) {
  console.error('Usage: node scripts/verify-service.mjs --app <acronym> --service "<exposed service name>" [--snapshot <name>] [--out <dir>], or --url <task URL>');
  process.exit(2);
}

process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0'; // Test clusters often use self-signed certificates
const envFile = new URL('../../.env', import.meta.url);
const fileEnv = fs.existsSync(envFile) ? Object.fromEntries(fs.readFileSync(envFile, 'utf8').split('\n')
  .filter((l) => /^\s*BAW_[A-Z_]*\s*=/.test(l))
  .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim().replace(/^["']|["']$/g, '')])) : {};
const setting = (key) => process.env[key] || fileEnv[key];
const BASE = setting('BAW_URL')?.replace(/\/+$/, '');
const secret = setting('BAW_PASSWORD') ? { password: setting('BAW_PASSWORD') } : { api_key: setting('BAW_APIKEY') };
if (!BASE || !setting('BAW_USER') || !(secret.password || secret.api_key)) {
  console.error('Missing BAW settings: BAW_URL, BAW_USER, and BAW_PASSWORD or BAW_APIKEY (environment or .env)');
  process.exit(2);
}
const BROWSERS = [process.env.BROWSER_PATH, '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Helium.app/Contents/MacOS/Helium',
  '/usr/bin/chromium', '/usr/bin/google-chrome'];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const auth = await fetch(`${BASE}/icp4d-api/v1/authorize`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: setting('BAW_USER'), ...secret }),
});
const { token } = await auth.json();
if (!token) throw new Error(`Login failed (HTTP ${auth.status})`);

let item = { runURL: args.url && new URL(args.url, BASE).href };
if (!args.url) {
  const exposed = await (await fetch(`${BASE}/bas/rest/bpm/wle/v1/exposed/service`, { headers: { Authorization: `Bearer ${token}` } })).json();
  item = exposed.data.exposedItemsList.find((i) => i.processAppAcronym === args.app && i.display === args.service
    && (args.snapshot ? i.snapshotName === args.snapshot : i.tip));
  if (!item) throw new Error(`No exposed service "${args.service}" in ${args.app} ${args.snapshot || '(tip)'}`);
}
const presses = [...args.press];
const typing = args.value.map((v) => {
  const at = v.indexOf('=');
  if (at < 1) { console.error(`--value needs "Label=text", got "${v}"`); process.exit(2); }
  return { label: v.slice(0, at).trim(), text: v.slice(at + 1) };
});

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

// Runs inside each frame: the visible field whose label reads `label` (UI Toolkit labels are not always
// tied to the input, so fall back to the nearest label around a field that has no sibling field).
function findField(label) {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').replace(/[\s*:]+$/, '').trim().toLowerCase();
  const fields = [...document.querySelectorAll('input:not([type=hidden]):not([type=button]):not([type=submit]):not([type=checkbox]):not([type=radio]), textarea, select')]
    .filter((el) => !!el.offsetParent);
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
  return fields.find((el) => labelsOf(el).includes(want)) || fields.find((el) => labelsOf(el).some((t) => t.includes(want))) || null;
}

// Type text into the field labelled `label`, replacing what is there. Returns false when the coach has no such field.
async function typeInto(frame, label, text) {
  const field = (await frame.evaluateHandle(findField, label)).asElement();
  if (!field) return false;
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

// --fill: type into the React form's empty editable fields (the field's example placeholder,
// today's date for date pickers, or "Test"), tick unticked checkboxes, turn on switches that are off (a Toggle
// widget), pick the first option of empty dropdowns and of radio groups with nothing chosen. Returns the count.
async function fill(frame) {
  let count = 0;
  for (const input of await frame.$$('.pp-app input:not([readonly]):not([type=checkbox]):not([type=radio]), .pp-app textarea:not([readonly])')) {
    const { empty, placeholder, visible } = await input.evaluate((el) => ({ empty: !el.value, placeholder: el.placeholder, visible: !!el.offsetParent }));
    if (!empty || !visible) continue;
    const today = new Date().toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
    await input.type(placeholder === 'mm/dd/yyyy' ? today : placeholder || 'Test');
    await input.press('Tab');
    count++;
  }
  for (const box of await frame.$$('.pp-app input[type=checkbox]:not(:checked):not([readonly])')) {
    await box.evaluate((el) => el.parentElement.querySelector('label')?.click());
    count++;
  }
  for (const toggle of await frame.$$('.pp-app button[role=switch][aria-checked=false]:not([disabled]):not([aria-readonly=true])')) {
    if (!(await toggle.evaluate((el) => !!el.offsetParent))) continue;
    await toggle.click();
    count++;
  }
  for (const select of await frame.$$('.pp-app select:not([disabled])')) {
    const value = await select.evaluate((el) => (!el.value && el.offsetParent ? [...el.options].find((o) => o.value)?.value : null));
    if (value) { await select.select(value); count++; }
  }
  for (const group of await frame.$$('.pp-app fieldset')) {
    const picked = await group.evaluate((el) => {
      const radios = [...el.querySelectorAll('input[type=radio]:not([readonly]):not([disabled])')];
      if (!radios.length || radios.some((r) => r.checked) || !el.offsetParent) return false;
      el.querySelector(`label[for="${radios[0].id}"]`)?.click();
      return true;
    });
    if (picked) count++;
  }
  return count;
}

const executablePath =BROWSERS.find((p) => p && fs.existsSync(p));
const browser = await puppeteer.launch({
  executablePath, headless: 'new', acceptInsecureCerts: true,
  args: ['--no-first-run', '--ignore-certificate-errors', `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), 'baw-verify-'))}`],
});
const report = { app: args.app, service: args.service || args.url, snapshot: item.snapshotName, steps: [], errors: [], ok: false };
try {
  fs.mkdirSync(args.out, { recursive: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000 });
  await page.setCookie({ name: 'ibm-private-cloud-session', value: token, domain: new URL(BASE).hostname, path: '/', secure: true });
  await page.setExtraHTTPHeaders({ Authorization: `Bearer ${token}` });
  page.on('pageerror', (e) => report.errors.push(String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error') report.errors.push(`console: ${m.text().slice(0, 300)}`); });
  page.on('response', (r) => { // a server error says why in its body (for example a service call from the coach that BAW rejects)
    if (r.status() >= 500) r.text().then((body) => report.errors.push(`HTTP ${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}: ${body.replace(/\s+/g, ' ').slice(0, 300)}`)).catch(() => {});
  });
  await page.goto(item.runURL, { waitUntil: 'networkidle2', timeout: 90000 });

  const coach = async (timeout = 30000) => {
    for (const end = Date.now() + timeout; Date.now() < end; await sleep(500)) {
      for (const frame of page.frames()) {
        const info = await frame.evaluate(inspectCoach).catch(() => null);
        if (info) return { frame, info };
      }
    }
    return null;
  };
  const hashes = new Set();
  let current = await coach();
  if (!current) {
    await page.screenshot({ path: path.join(args.out, '00-no-coach.png'), fullPage: true });
    throw new Error('no coach rendered (see 00-no-coach.png)');
  }
  for (let step = 1; current && step <= Number(args['max-steps']); step++) {
    await sleep(1500); // let React and BAW finish rendering
    current = (await coach()) || current;
    const typed = [];
    for (const field of typing.filter((t) => !t.done)) {
      if (await typeInto(current.frame, field.label, field.text)) { field.done = true; typed.push(field.label); }
    }
    if (typed.length) await sleep(500);
    const file = path.join(args.out, `${String(step).padStart(2, '0')}-${current.info.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase().slice(0, 40)}.png`);
    // The coach scrolls inside a frame as tall as the window, so grow the window to the whole coach first.
    const top = (await (await current.frame.frameElement())?.boundingBox())?.y || 0;
    const height = await current.frame.evaluate(() => document.documentElement.scrollHeight).catch(() => 0);
    await page.setViewport({ width: 1400, height: Math.min(Math.max(1000, Math.ceil(top + height)), 8000) });
    await sleep(300);
    const shot = await page.screenshot({ path: file, fullPage: true });
    await page.setViewport({ width: 1400, height: 1000 });
    const hash = crypto.createHash('md5').update(shot).digest('hex');
    const { signature, buttons, ...info } = current.info;
    if (presses.length && buttons.includes(presses[0])) info.button = presses.shift();
    report.steps.push({ step, ...info, typed: typed.length ? typed : undefined, screenshot: file, duplicate: hashes.has(hash) || undefined });
    hashes.add(hash);
    if (!info.button) { report.failure = 'no forward button'; break; }
    if (args.fill && info.react) report.steps.at(-1).filled = await fill(current.frame);
    // Compare against the screen as it is now (typed and filled), not as it was when first inspected.
    const now = await current.frame.evaluate(inspectCoach).catch(() => null);
    const before = now ? now.signature : signature;
    await current.frame.evaluate((label) => {
      const react = document.querySelector('.pp-app');
      [...document.querySelectorAll(react ? '.pp-app .pp-actions button' : 'button')]
        .find((b) => b.offsetParent && b.textContent.trim() === label).click();
    }, info.button);
    let next = null;
    for (const end = Date.now() + 30000; Date.now() < end; await sleep(1000)) {
      next = await coach(3000);
      if (!next || next.info.signature !== before) break;
    }
    if (next && next.info.signature === before) {
      report.failure = `stuck on "${info.title}" after pressing "${info.button}"${next.info.alert ? `: ${next.info.alert}` : ''}`;
      break;
    }
    current = next;
  }
  const unpressed = presses, untyped = typing.filter((t) => !t.done).map((t) => t.label);
  if (unpressed.length) report.unpressed = unpressed;
  if (untyped.length) report.untyped = untyped;
  if (!report.failure && current) report.failure = `still on a coach after ${args['max-steps']} steps`;
  if (!report.failure && report.steps.some((s) => s.duplicate)) report.failure = 'duplicate screenshots';
  report.ok = !report.failure && report.errors.length === 0;
} catch (e) {
  report.failure = String(e).slice(0, 300);
} finally {
  await browser.close();
  console.log(JSON.stringify(report, null, 1));
  process.exit(report.ok ? 0 : 1);
}
