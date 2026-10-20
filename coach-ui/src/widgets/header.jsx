// Header widget: the app's banner (logo and product name from the page's theme), the title and the steps.
import { useSyncExternalStore } from 'react';
import { registerWidget } from '../runtime.jsx';
import { Header } from '../components.jsx';
import { page } from '../page-registry.js';

function HeaderWidget({ options }) {
  const theme = useSyncExternalStore(page.subscribe, () => page.theme);
  const steps = Array.isArray(options.steps) ? options.steps : [];
  return <Header theme={theme} subtitle={options.subtitle} title={options.title} steps={steps} step={Number(options.step) || 0} />;
}

registerWidget('header', HeaderWidget);
