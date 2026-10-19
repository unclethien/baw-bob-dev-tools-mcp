// Bundle the React screens into two BAW web managed files: pp-react.js (IIFE that
// sets window.PPReact) and pp-react.css.
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
const entry = ["export { mount, mountWidget } from './runtime.jsx';", "import './form-screen.jsx';",
  ...widgetFiles.map((f) => `import './widgets/${f}';`), ...screens.map((f) => `import './screens/${f}';`)].join('\n');

// Carbon sizes everything in rem for a 16px root, but BAW's bpmUI.css sets the coach page's
// root to 62.5% (10px), which shrinks the screen to 62.5%. Fixed pixels keep Carbon's sizes.
// The same applies to the CSS and inline styles in our own .jsx files.
const toPx = (css) => css.replace(/(?<![\w.-])(-?\d*\.?\d+)rem(?![\w-])/g, (_, n) => `${+(n * 16).toFixed(3)}px`);
const css = toPx(compile('src/styles.scss', { loadPaths: ['node_modules'], style: 'compressed', quietDeps: true }).css);
writeFileSync('bundle/pp-react.css', css);

await build({
  stdin: { contents: entry, resolveDir: 'src', loader: 'jsx', sourcefile: 'index.jsx' },
  bundle: true,
  format: 'iife',
  globalName: 'PPReact',
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
  footer: { js: 'window.PPReact=PPReact;})();' },
  outfile: 'bundle/pp-react.js',
  logLevel: 'info',
}).catch(() => process.exit(1)); // esbuild has already printed the errors
