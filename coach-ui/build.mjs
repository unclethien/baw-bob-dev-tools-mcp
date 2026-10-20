// Bundle the coach UI into BAW web managed files, each an IIFE that sets one global:
// - coach-screens.js / .css (window.CoachScreens): the screens hand-written for an app's coaches; each app
//   ships its own copy.
// - mdw.js / .css (window.ModernizerWidgets): the widgets of the Modernizer Widgets toolkit, shared by apps.
//
// BAW pages run Dojo's AMD loader. The bundle is wrapped so a global `define` is
// hidden from any UMD code inside it; otherwise those modules would register with
// Dojo instead of the bundle and break.
import { build } from 'esbuild';
import { compile } from 'sass';
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';

mkdirSync('bundle', { recursive: true });

// Screens written for specific coaches live in src/screens/*.jsx and register themselves
// with registerScreen(name, Component); every one of them goes into the bundle.
const screens = existsSync('src/screens') ? readdirSync('src/screens').filter((f) => f.endsWith('.jsx')).sort() : [];
// Widgets of the Modernizer Widgets toolkit live in src/widgets/*.jsx and register with registerWidget(kind, Component).
const widgetFiles = existsSync('src/widgets') ? readdirSync('src/widgets').filter((f) => f.endsWith('.jsx')).sort() : [];
const screensEntry = ["export { mount } from './runtime.jsx';", ...screens.map((f) => `import './screens/${f}';`)].join('\n');
// Screens written for one app's coaches never go into the toolkit that every app shares.
const toolkitEntry = ["export * from './toolkit.js';", ...widgetFiles.map((f) => `import './widgets/${f}';`)].join('\n');

// Carbon sizes everything in rem for a 16px root, but BAW's bpmUI.css sets the coach page's
// root to 62.5% (10px), which shrinks the screen to 62.5%. Fixed pixels keep Carbon's sizes.
// The same applies to the CSS and inline styles in our own .jsx files.
const toPx = (css) => css.replace(/(?<![\w.-])(-?\d*\.?\d+)rem(?![\w-])/g, (_, n) => `${+(n * 16).toFixed(3)}px`);
const css = toPx(compile('src/styles.scss', { loadPaths: ['node_modules'], style: 'compressed', quietDeps: true }).css);
writeFileSync('bundle/coach-screens.css', css);
writeFileSync('bundle/mdw.css', css);

const bundle = (contents, globalName, outfile) => build({
  stdin: { contents, resolveDir: 'src', loader: 'jsx', sourcefile: 'index.jsx' },
  bundle: true,
  format: 'iife',
  globalName,
  minify: true,
  jsx: 'automatic',
  target: 'es2019',
  define: { 'process.env.NODE_ENV': '"production"' },
  loader: { '.scss': 'empty' },
  plugins: [{
    name: 'rem-to-px',
    setup: (b) => b.onLoad({ filter: /[\\/]src[\\/].*\.jsx$/ }, ({ path }) => ({ contents: toPx(readFileSync(path, 'utf8')), loader: 'jsx' })),
  }],
  banner: { js: '(function(define){' },
  footer: { js: `window.${globalName}=${globalName};})();` },
  outfile,
  logLevel: 'info',
});

await Promise.all([bundle(screensEntry, 'CoachScreens', 'bundle/coach-screens.js'), bundle(toolkitEntry, 'ModernizerWidgets', 'bundle/mdw.js')])
  .catch(() => process.exit(1)); // esbuild has already printed the errors
