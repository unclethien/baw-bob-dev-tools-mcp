// Walk a BAW client-side human service in a real browser and report what happened.
//
// Usage:
//   node scripts/verify-service.mjs --app ZZEQ --service "Equipment Request (Modernized)" [--snapshot 1.1.0] [--out shots] [--fill]
//
// Logs in with BAW_URL, BAW_USER and BAW_PASSWORD or BAW_APIKEY from the environment, else from the
// repository's .env (token kept in memory, never printed), opens the service's run URL,
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
    fill: { type: 'boolean', default: false },
  },
});
if (!args.app || !args.service) {
  console.error('Usage: node scripts/verify-service.mjs --app <acronym> --service "<exposed service name>" [--snapshot <name>] [--out <dir>]');
  process.exit(2);
}

process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0'; // Test clusters often use self-signed certificates
const envFile = new URL('../../.env', import.meta.url);
const fileEnv = fs.existsSync(envFile) ? Object.fromEntries(fs.readFileSync(envFile, 'utf8').split('\n')
  .filter((l) => l.includes('=') && !l.trimStart().startsWith('#'))
  .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim().replace(/^["']|["']$/g, '')])) : {};
const setting = (key) => process.env[key] || fileEnv[key];
const BASE = setting('BAW_URL')?.replace(/\/+$/, '');
const secret = setting('BAW_PASSWORD') ? { password: setting('BAW_PASSWORD') } : { api_key: setting('BAW_APIKEY') };
if (!BASE || !setting('BAW_USER') || !(secret.password || secret.api_key)) {
  console.error('Missing BAW settings: BAW_URL, BAW_USER, and BAW_PASSWORD or BAW_APIKEY (environment or .env)');
  process.exit(2);
}
const BROWSERS = [process.env.BROWSER_PATH, '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/chromium', '/usr/bin/google-chrome'];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const auth = await fetch(`${BASE}/icp4d-api/v1/authorize`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: setting('BAW_USER'), ...secret }),
});
const { token } = await auth.json();
if (!token) throw new Error(`Login failed (HTTP ${auth.status})`);

const exposed = await (await fetch(`${BASE}/bas/rest/bpm/wle/v1/exposed/service`, { headers: { Authorization: `Bearer ${token}` } })).json();
const item = exposed.data.exposedItemsList.find((i) => i.processAppAcronym === args.app && i.display === args.service
  && (args.snapshot ? i.snapshotName === args.snapshot : i.tip));
if (!item) throw new Error(`No exposed service "${args.service}" in ${args.app} ${args.snapshot || '(tip)'}`);

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
  const title = (react?.querySelector('h1') || document.querySelector('h1,.panel-title,.BPMSectionHeader'))?.textContent.trim();
  return {
    react: !!react, title: title || document.title, button: forward?.textContent.trim(),
    alert: document.querySelector('.pp--inline-notification--error')?.textContent.trim(),
    signature: document.body.innerText.length + ':' + document.body.innerText.slice(0, 2000),
  };
}

// --fill: type into the React form's empty editable fields (the field's example placeholder,
// today's date for date pickers, or "Test") and tick unticked checkboxes. Returns the count.
async function fill(frame) {
  let count = 0;
  for (const input of await frame.$$('.pp-app input:not([readonly]):not([type=checkbox]), .pp-app textarea:not([readonly])')) {
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
  return count;
}

const executablePath =BROWSERS.find((p) => p && fs.existsSync(p));
const browser = await puppeteer.launch({
  executablePath, headless: 'new', acceptInsecureCerts: true,
  args: ['--no-first-run', '--ignore-certificate-errors', `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), 'baw-verify-'))}`],
});
const report = { app: args.app, service: args.service, snapshot: item.snapshotName, steps: [], errors: [], ok: false };
try {
  fs.mkdirSync(args.out, { recursive: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000 });
  await page.setCookie({ name: 'ibm-private-cloud-session', value: token, domain: new URL(BASE).hostname, path: '/', secure: true });
  await page.setExtraHTTPHeaders({ Authorization: `Bearer ${token}` });
  page.on('pageerror', (e) => report.errors.push(String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error') report.errors.push(`console: ${m.text().slice(0, 300)}`); });
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
    const file = path.join(args.out, `${String(step).padStart(2, '0')}-${current.info.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase().slice(0, 40)}.png`);
    const shot = await page.screenshot({ path: file, fullPage: true });
    const hash = crypto.createHash('md5').update(shot).digest('hex');
    const { signature, ...info } = current.info;
    report.steps.push({ step, ...info, screenshot: file, duplicate: hashes.has(hash) || undefined });
    hashes.add(hash);
    if (!info.button) { report.failure = 'no forward button'; break; }
    if (args.fill && info.react) report.steps.at(-1).filled = await fill(current.frame);
    await current.frame.evaluate((label) => {
      const react = document.querySelector('.pp-app');
      [...document.querySelectorAll(react ? '.pp-app .pp-actions button' : 'button')]
        .find((b) => b.offsetParent && b.textContent.trim() === label).click();
    }, info.button);
    let next = null;
    for (const end = Date.now() + 30000; Date.now() < end; await sleep(1000)) {
      next = await coach(3000);
      if (!next || next.info.signature !== signature) break;
    }
    if (next && next.info.signature === signature) {
      report.failure = `stuck on "${info.title}" after pressing "${info.button}"${next.info.alert ? `: ${next.info.alert}` : ''}`;
      break;
    }
    current = next;
  }
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
