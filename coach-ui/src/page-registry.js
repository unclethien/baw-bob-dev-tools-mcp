// What the widgets on one coach page share, whatever framework draws them: the app's theme, and the fields a
// button checks before it fires its boundary event. Widgets must not register while drawn as Coach Designer
// previews, because several previews share the Designer page.
const listeners = new Set();
const fields = new Map();
let theme = {};
let errors = [];
const notify = () => listeners.forEach((listener) => listener());

export const page = {
  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  get theme() { return theme; },
  setTheme(next) {
    theme = next || {};
    notify();
  },
  // field: { validate(), element }; validate() returns { message, ... } or null. Returns the function that unregisters the field and
  // drops its error. A field registered again under the same id (the next coach) is left alone.
  register(id, field) {
    fields.set(id, field);
    return () => {
      if (fields.get(id) !== field) return;
      fields.delete(id);
      errors = errors.filter((error) => error.id !== id);
      notify();
    };
  },
  get errors() { return errors; },
  // Errors in screen order: fields register as they mount, which need not be the order they appear in.
  validateAll() {
    errors = [...fields].map(([id, field]) => {
      const error = field.validate();
      return error && { ...error, id, element: field.element };
    }).filter(Boolean).sort(byPosition);
    notify();
    return errors;
  },
};

function byPosition(a, b) {
  if (!a.element || !b.element) return 0;
  return a.element.compareDocumentPosition(b.element) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
}

// Shows a field that sits in a tab that is not selected: selects the tab whose panel holds it (ARIA tabs).
export function reveal(element) {
  const panel = element && element.closest('[role="tabpanel"]');
  const tab = panel && panel.id && element.ownerDocument.querySelector(`[role="tab"][aria-controls="${panel.id}"]`);
  if (tab && tab.getAttribute('aria-selected') !== 'true') tab.click();
}
