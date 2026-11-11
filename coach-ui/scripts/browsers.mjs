// The Chromium browser the browser scripts drive: BROWSER_PATH, then Brave, Chrome, Chrome for Testing from the
// Puppeteer cache (`npx @puppeteer/browsers install chrome@stable --path ~/.cache/puppeteer`), then Helium.
// Helium comes last because it aborts a BAW task link (process.lsw) before the task's coach loads.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const HELIUM = '/Applications/Helium.app/Contents/MacOS/Helium';

// The newest Chrome for Testing in the Puppeteer cache, or null.
function chromeForTesting() {
  const root = path.join(process.env.PUPPETEER_CACHE_DIR || path.join(os.homedir(), '.cache', 'puppeteer'), 'chrome');
  let builds;
  try { builds = fs.readdirSync(root); } catch { return null; }
  const version = (name) => (name.split('-').pop() || '').split('.').map(Number);
  builds.sort((a, b) => {
    const [x, y] = [version(a), version(b)];
    for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] || 0) !== (y[i] || 0)) return (y[i] || 0) - (x[i] || 0);
    return 0;
  });
  for (const build of builds) {
    for (const exe of ['chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',
      'chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing', 'chrome-linux64/chrome']) {
      const file = path.join(root, build, exe);
      if (fs.existsSync(file)) return file;
    }
  }
  return null;
}

export function findBrowser() {
  const candidates = [process.env.BROWSER_PATH, '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', chromeForTesting(), HELIUM,
    '/usr/bin/chromium', '/usr/bin/google-chrome'];
  return candidates.find((p) => p && fs.existsSync(p));
}

export const isHelium = (exe) => /helium/i.test(path.basename(exe || ''));
