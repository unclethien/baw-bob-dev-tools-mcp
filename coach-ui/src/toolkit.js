// Entry of the Modernizer Widgets toolkit bundle (window.ModernizerWidgets). A widget's Coach View calls
// attach(this, kind, optionNames) in its load handler; Coach Designer previews call mountWidget directly.
import { mountWidget } from './runtime.jsx';
import { widgetContext } from './widget-host.js';

export { mountWidget };
export { page } from './page-registry.js';
export { plain } from './widget-host.js';
export const attach = (view, kind, optionNames) => mountWidget(view.context.element, kind, widgetContext(view, optionNames));
