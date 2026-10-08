// Bundle the React screens into two BAW web managed files: pp-react.js (IIFE that
// sets window.PPReact) and pp-react.css.
//
// BAW pages run Dojo's AMD loader. The bundle is wrapped so a global `define` is
// hidden from any UMD code inside it; otherwise those modules would register with
// Dojo instead of the bundle and break.
import { build } from 'esbuild';
import { compile } from 'sass';
import { existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';

mkdirSync('bundle', { recursive: true });

// Screens written for specific coaches live in src/screens/*.jsx and register themselves
// with registerScreen(name, Component); every one of them goes into the bundle.
const screens = existsSync('src/screens') ? readdirSync('src/screens').filter((f) => f.endsWith('.jsx')).sort() : [];
const entry = ["export { mount } from './runtime.jsx';", "import './form-screen.jsx';", ...screens.map((f) => `import './screens/${f}';`)].join('\n');

const css = compile('src/styles.scss', { loadPaths: ['node_modules'], style: 'compressed', quietDeps: true }).css;
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
  banner: { js: '(function(define){' },
  footer: { js: 'window.PPReact=PPReact;})();' },
  outfile: 'bundle/pp-react.js',
  logLevel: 'info',
}).catch(() => process.exit(1)); // esbuild has already printed the errors
