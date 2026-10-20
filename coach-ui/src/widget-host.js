// The bridge between a BAW Coach View and a widget, free of any UI framework: it turns the view's context
// (binding, options, label, help text, visibility, boundary event) into the widget context a framework mounts.
export function widgetContext(view, optionNames) {
  const options = view.context.options;
  const meta = (name, fallback) => {
    const value = options._metadata && options._metadata[name] && options._metadata[name].get('value');
    return value === undefined || value === null || value === '' ? fallback : value;
  };
  const option = (name) => (options[name] ? options[name].get('value') : null);
  return {
    read: () => ({
      label: meta('label', ''),
      helpText: meta('helpText', ''),
      visibility: meta('visibility', 'DEFAULT'),
      options: Object.fromEntries(optionNames.map((name) => [name, option(name)])),
      preview: false,
    }),
    binding: {
      get: () => (view.context.binding ? view.context.binding.get('value') : null),
      set: (value) => { if (view.context.binding) view.context.binding.set('value', value); },
    },
    trigger: () => view.context.trigger(),
  };
}
