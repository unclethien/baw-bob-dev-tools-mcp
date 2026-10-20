// The bridge between a BAW Coach View and a widget, free of any UI framework: it turns the view's context
// (binding, options, label, help text, visibility, boundary event) into the widget context a framework mounts.

// Option values as plain data: a list becomes an array, a NameValuePair becomes { name, value }.
const get = (object, key) => (typeof object.get === 'function' ? object.get(key) : object[key]);
export function plain(value) {
  if (value === null || value === undefined || typeof value !== 'object' || value instanceof Date) return value;
  if (Array.isArray(value)) return value.map(plain);
  if (Array.isArray(value.items)) return value.items.map(plain);
  return { name: get(value, 'name'), value: get(value, 'value') };
}

export function widgetContext(view, optionNames) {
  const { context } = view;
  const options = context.options;
  const meta = (name, fallback) => {
    const value = options._metadata && options._metadata[name] && options._metadata[name].get('value');
    return value === undefined || value === null || value === '' ? fallback : value;
  };
  const option = (name) => (options[name] ? plain(options[name].get('value')) : null);
  // DEFAULT means "as my container". A hidden container hides the widget whatever its own setting, so a field
  // nobody can see never blocks a button.
  const visibility = () => {
    const own = meta('visibility', 'DEFAULT');
    const inherited = typeof context.getInheritedVisibility === 'function' ? context.getInheritedVisibility() : null;
    if (inherited === 'HIDDEN' || inherited === 'NONE') return inherited;
    return own === 'DEFAULT' ? inherited || 'EDITABLE' : own;
  };
  return {
    read: () => ({
      // controlidpath is unique per instance; viewid repeats when a view is reused (a table row, a reused coach view).
      id: context.controlidpath || context.viewid,
      label: meta('label', ''),
      helpText: meta('helpText', ''),
      visibility: visibility(),
      options: Object.fromEntries(optionNames.map((name) => [name, option(name)])),
      preview: false,
    }),
    binding: {
      get: () => (context.binding ? context.binding.get('value') : null),
      set: (value) => { if (context.binding) context.binding.set('value', value); },
    },
    // done() runs once BAW has handled the boundary event, whether the coach moved on or stayed (a validation
    // failure, a loop back), so a button can take presses again.
    trigger: (done) => (done ? context.trigger(() => done(), { callBackForAll: true }) : context.trigger()),
  };
}
