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
  // field.validate() returns { message, ... } or null. Returns the function that unregisters the field and
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
  validateAll() {
    errors = [...fields].map(([id, field]) => {
      const error = field.validate();
      return error && { ...error, id };
    }).filter(Boolean);
    notify();
    return errors;
  },
};
