// Theme widget: publishes the app's theme file (JSON) to every widget on the page, and dresses the page around
// them: its background, width and font, and the pp-widget-page class that styles BAW's own containers like the
// screen components' sections, tabs and button row (styles.scss). It draws nothing on the page; in Coach Designer it
// shows a marker so the author can find and select it.
import { useEffect } from 'react';
import { registerWidget, themeStyle } from '../runtime.jsx';
import { page } from '../page-registry.js';

function parse(json) {
  try {
    return json ? JSON.parse(json) : {};
  } catch {
    console.warn('Theme widget: the theme option is not valid JSON; using the default look');
    return {};
  }
}

// The next coach's Theme widget may mount before this one unmounts, so the page stays dressed while any is mounted.
let dressed = 0;

function dressPage(body, theme) {
  const style = themeStyle(theme);
  const vars = Object.entries(style).filter(([name]) => name.startsWith('--'));
  vars.push(['--pp-page-width', style.maxWidth || '1056px']);
  if (style.fontFamily) vars.push(['--pp-page-font', style.fontFamily]);
  dressed += 1;
  body.classList.add('pp-widget-page');
  vars.forEach(([name, value]) => body.style.setProperty(name, value));
  return () => {
    dressed -= 1;
    if (dressed) return;
    body.classList.remove('pp-widget-page');
    vars.forEach(([name]) => body.style.removeProperty(name));
  };
}

function ThemeWidget({ options, preview }) {
  useEffect(() => {
    if (preview) return undefined;
    const theme = parse(options.theme);
    page.setTheme(theme);
    return dressPage(document.body, theme);
  }, [options.theme, preview]);
  return preview ? <div className="pp-widget-marker">Theme</div> : null;
}

registerWidget('theme', ThemeWidget);
