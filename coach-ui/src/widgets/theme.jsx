// Theme widget: publishes the app's theme file (JSON) to every widget on the page. It draws nothing on the
// page; in Coach Designer it shows a marker so the author can find and select it.
import { useEffect } from 'react';
import { registerWidget } from '../runtime.jsx';
import { page } from '../page-registry.js';

function parse(json) {
  try {
    return json ? JSON.parse(json) : {};
  } catch {
    console.warn('Theme widget: the theme option is not valid JSON; using the default look');
    return {};
  }
}

function ThemeWidget({ options, preview }) {
  useEffect(() => {
    if (!preview) page.setTheme(parse(options.theme));
  }, [options.theme, preview]);
  return preview ? <div className="pp-widget-marker">Theme</div> : null;
}

registerWidget('theme', ThemeWidget);
