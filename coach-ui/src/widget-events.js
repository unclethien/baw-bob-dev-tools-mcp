// A widget's events and its script API, as the UI Toolkit (BPM UI) controls have them, free of any UI framework.
//
// Coach Designer lists a widget's events in its Events tab (EVENT options named eventON_LOAD, eventON_CHANGE, ...,
// see widgets/modernizer-widgets.json). The code written there runs the way it runs for a UI Toolkit control:
// - When the page has BPM UI (window.bpmext, which UI Toolkit views such as Panel bring), the view is registered
//   with it, so handlers get `me`, ${Control} references and page.ui.get(), and BPM UI runs them:
//   bpmext.ui.loadView(view) also runs eventON_LOAD, registerEventHandlingFunction(view, event, ...argument names)
//   declares one handler's arguments, executeEventHandlingFunction(view, event, ...arguments) runs it.
// - Without BPM UI the handler is compiled here, with `me` (and `view`) bound to the view and the same arguments.
// A handler that returns false cancels what it can cancel: a Button's click, a keystroke (eventON_INPUT).

const LOAD = 'eventON_LOAD';
const blank = (code) => code === null || code === undefined || String(code).trim() === '';

function bpmUi() {
  const ui = typeof window !== 'undefined' && window.bpmext && window.bpmext.ui;
  return ui && typeof ui.loadView === 'function' && typeof ui.executeEventHandlingFunction === 'function' ? ui : null;
}

// events: { event name: [argument names] }. Returns { load(), fire(event, ...args), unload() }; fire returns the
// handler's result (undefined when the widget has no handler for the event).
export function widgetEvents(view, events = {}) {
  const option = (name) => {
    const opt = view.context.options && view.context.options[name];
    return opt && typeof opt.get === 'function' ? opt.get('value') : undefined;
  };
  const own = ownHandlers(view, events, option);
  const ui = bpmUi();
  if (!ui) return own;
  let viaBpm = true;
  return {
    load() {
      try {
        ui.loadView(view);
        Object.keys(events).filter((name) => name !== LOAD).forEach((name) => ui.registerEventHandlingFunction(view, name, ...events[name]));
      } catch (e) {
        console.error('Modernizer Widgets: BPM UI could not take the view, so its events run without it', e);
        viaBpm = false;
        own.load();
      }
    },
    fire: (name, ...args) => {
      if (!viaBpm) return own.fire(name, ...args);
      if (blank(option(name))) return undefined;
      try {
        return ui.executeEventHandlingFunction(view, name, ...args);
      } catch (e) { // BPM UI has logged it; the widget carries on, as a UI Toolkit control does
        console.error(`Modernizer Widgets: the ${name} handler of ${view.context.viewid || 'widget'} failed`, e);
        return undefined;
      }
    },
    unload() { if (viaBpm && typeof ui.unloadView === 'function') ui.unloadView(view); },
  };
}

// The handlers compiled here, each the first time it runs: `me` and `view` are the view, then the event's arguments.
function ownHandlers(view, events, option) {
  const compiled = {};
  const where = () => view.context.viewid || view.context.controlidpath || 'widget';
  const handler = (name) => {
    if (!(name in compiled)) {
      compiled[name] = null;
      const code = option(name);
      if (!blank(code) && events[name]) {
        try {
          compiled[name] = new Function('me', 'view', ...events[name], code); // eslint-disable-line no-new-func
        } catch (e) {
          console.error(`Modernizer Widgets: the ${name} handler of ${where()} does not compile`, e);
        }
      }
    }
    return compiled[name];
  };
  const fire = (name, ...args) => {
    const fn = handler(name);
    if (!fn) return undefined;
    try {
      return fn.call(view, view, view, ...args);
    } catch (e) {
      console.error(`Modernizer Widgets: the ${name} handler of ${where()} failed`, e);
      return undefined;
    }
  };
  return { load: () => fire(LOAD), fire, unload() {} };
}

// The DOM events of a field widget: eventON_FOCUS when the focus enters the widget, eventON_BLUR when it leaves it
// (moving between the radio buttons of one group is neither), and eventON_INPUT before a keystroke changes a text
// input, with the text as it is and as it would be. Returns the function that removes the listeners.
export function domEvents(element, events, fire) {
  const has = (name) => Object.prototype.hasOwnProperty.call(events, name);
  const inside = (node) => node && element.contains(node);
  const listeners = [];
  const on = (type, listener) => {
    element.addEventListener(type, listener);
    listeners.push([type, listener]);
  };
  if (has('eventON_FOCUS')) on('focusin', (e) => { if (!inside(e.relatedTarget)) fire('eventON_FOCUS'); });
  if (has('eventON_BLUR')) on('focusout', (e) => { if (!inside(e.relatedTarget)) fire('eventON_BLUR'); });
  if (has('eventON_INPUT')) {
    on('beforeinput', (e) => {
      const input = e.target;
      if (!input || typeof input.value !== 'string' || typeof input.selectionStart !== 'number') return;
      const current = input.value;
      const selection = { start: input.selectionStart, end: input.selectionEnd };
      if (fire('eventON_INPUT', current, potentialText(current, selection, e), selection, e.inputType) === false) e.preventDefault();
    });
  }
  return () => listeners.forEach(([type, listener]) => element.removeEventListener(type, listener));
}

// The text an input would hold after a beforeinput event.
function potentialText(text, { start, end }, e) {
  const type = e.inputType || '';
  if (type.startsWith('insert')) return text.slice(0, start) + (e.data ?? (type === 'insertLineBreak' ? '\n' : '')) + text.slice(end);
  if (start !== end) return text.slice(0, start) + text.slice(end);
  if (type === 'deleteContentBackward') return text.slice(0, Math.max(0, start - 1)) + text.slice(end);
  if (type === 'deleteContentForward') return text.slice(0, start) + text.slice(end + 1);
  return text;
}

// The methods a handler calls on `me`, by the names the UI Toolkit controls use: getData and setData, the value
// accessor of the widget's kind (getText on a Text, isChecked on a Checkbox, ...), the label, help text, tab index,
// placeholder, visibility and enabled state. A method the view already has (one BPM UI added) is left alone.
// update() redraws the widget after an option changed.
const ACCESSORS = {
  text: ['getText', 'setText'], textarea: ['getText', 'setText'], number: ['getValue', 'setValue'], date: ['getDate', 'setDate'],
  checkbox: ['isChecked', 'setChecked'], toggle: ['isChecked', 'setChecked'], select: ['getSelectedItem', 'setSelectedItem'],
  radio: ['getSelectedItem', 'setSelectedItem'],
};

export function addMethods(view, kind, update) {
  const { context } = view;
  const holder = (name) => (name.startsWith('@') ? context.options._metadata && context.options._metadata[name.slice(1)] : context.options[name]);
  const read = (name) => { const h = holder(name); return h && typeof h.get === 'function' ? h.get('value') : undefined; };
  // BAW creates the option objects of the options the layout sets only, so a script that sets another option
  // gets a plain one (the widget reads options with get("value") alone).
  const write = (name, value) => {
    const h = holder(name);
    if (h && typeof h.set === 'function') h.set('value', value);
    else if (!name.startsWith('@')) {
      let current = value;
      context.options[name] = { get: () => current, set: (_, next) => { current = next; } };
    } else {
      console.warn(`Modernizer Widgets: ${context.viewid || kind} has no ${name}`);
      return;
    }
    update();
  };
  const visibility = () => read('@visibility') || 'DEFAULT';
  const methods = {
    getData: () => (context.binding ? context.binding.get('value') : undefined),
    setData: (value) => { if (context.binding) context.binding.set('value', value); },
    getLabel: () => read('@label'),
    setLabel: (text) => write('@label', text),
    getHelpText: () => read('@helpText'),
    setHelpText: (text) => write('@helpText', text),
    getTabIndex: () => read('tabIndex'),
    setTabIndex: (index) => write('tabIndex', index),
    isVisible: () => !['HIDDEN', 'NONE'].includes(visibility()),
    setVisible: (visible, collapse) => write('@visibility', visible ? 'DEFAULT' : collapse ? 'NONE' : 'HIDDEN'),
    isEnabled: () => visibility() !== 'READONLY',
    setEnabled: (enabled) => write('@visibility', enabled ? 'DEFAULT' : 'READONLY'),
  };
  if (['text', 'textarea', 'number', 'select'].includes(kind)) {
    methods.getPlaceholder = () => read('example');
    methods.setPlaceholder = (text) => write('example', text);
  }
  if (kind === 'button') {
    methods.getText = methods.getLabel;
    methods.setText = methods.setLabel;
  }
  const [get, set] = ACCESSORS[kind] || [];
  if (get) {
    methods[get] = methods.getData;
    methods[set] = methods.setData;
  }
  for (const [name, method] of Object.entries(methods)) {
    if (typeof view[name] !== 'function') view[name] = method;
  }
}
