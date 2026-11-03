// Entry of the Modernizer Widgets toolkit bundle (window.ModernizerWidgets). A widget's Coach View calls
// attach(this, kind, optionNames, events) in its load handler, change(event) in its change handler and unmount() in
// its unload handler; Coach Designer previews call mountWidget directly, so no event code runs in Designer.
import { mountWidget } from './runtime.jsx';
import { widgetContext } from './widget-host.js';
import { addMethods, domEvents, widgetEvents } from './widget-events.js';

export { mountWidget };
export { page } from './page-registry.js';
export { plain } from './widget-host.js';

// events: { event name: [argument names] }, the widget's events in the contract (widgets/modernizer-widgets.json).
export function attach(view, kind, optionNames, events = {}) {
  const handlers = widgetEvents(view, events);
  const handle = mountWidget(view.context.element, kind, widgetContext(view, optionNames, handlers.fire));
  addMethods(view, kind, handle.update);
  const removeListeners = domEvents(view.context.element, events, handlers.fire);
  handlers.load();
  return {
    update: handle.update,
    // BAW's change event: a config change redraws; a binding change (also one a script makes) fires eventON_CHANGE.
    change(event) {
      handle.update();
      if (event && event.type !== 'config' && event.newVal !== event.oldVal) handlers.fire('eventON_CHANGE', event.newVal, event.oldVal);
    },
    unmount() {
      removeListeners();
      handlers.unload();
      handle.unmount();
    },
  };
}
