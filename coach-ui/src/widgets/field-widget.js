// The shared behaviour of the Modernizer Widgets that bind one value: label, help text, visibility (REQUIRED,
// READONLY, HIDDEN), page validation, the error and the read-only view. A widget file passes its own input:
//   registerWidget('toggle', fieldWidget('toggle', { Input: ToggleInput, display, isEmpty }));
// Kept as .js (no JSX) so build.mjs does not take it for a widget: only src/widgets/*.jsx are bundled as widgets.
import { createElement, useEffect, useRef, useState } from 'react';
import { Field, fieldError, fieldKind, ReadOnlyValue } from '../components.jsx';
import { page } from '../page-registry.js';

const choices = (list) => (Array.isArray(list) ? list.map((o) => ({ value: o.value, label: o.name ?? o.value })) : []);
const blank = (value) => value === null || value === undefined || value === '';

function rangeError(field, value) {
  if (blank(value)) return null;
  if (!blank(field.min) && Number(value) < Number(field.min)) return field.message || `${field.label} must be at least ${field.min}`;
  if (!blank(field.max) && Number(value) > Number(field.max)) return field.message || `${field.label} must be at most ${field.max}`;
  return null;
}

// The component for one widget kind (the kind is the widget's name in the contract).
// Input: a component like those in components/fields/, taking { id, field, binding, validity, readOnly };
//   field carries the label, help, example, pattern, message, min, max and options, plus every option the
//   contract declares for the kind. Without it the kind must be one of the stock kinds.
// display(field, value): the value as text, for the read-only view.
// isEmpty(field, value): the test REQUIRED uses.
export function fieldWidget(type, { Input, display, isEmpty } = {}) {
  if (!Input && fieldKind({ type }) === 'text' && type !== 'text') {
    throw new Error(`Modernizer Widgets: "${type}" is not a stock field kind, so fieldWidget needs an Input for it`);
  }
  function FieldWidget({ id, label, helpText, visibility, options, binding, preview }) {
    const [error, setError] = useState(null);
    const element = useRef(null);
    const key = useRef({});
    const field = {
      ...options,
      prop: id || label || type, label, type, help: helpText || undefined,
      options: choices(options.options), required: visibility === 'REQUIRED', readonly: visibility === 'READONLY',
      ...(Input && { Input }), ...(display && { display }), ...(isEmpty && { isEmpty }),
    };
    const latest = useRef();
    latest.current = { field, value: binding.value };

    useEffect(() => {
      if (preview) return undefined;
      return page.register(id || key.current, {
        get element() { return element.current; },
        validate() {
          const { field: f, value } = latest.current;
          const message = fieldError(f, value) || (type === 'number' ? rangeError(f, value) : null);
          setError(message);
          return message && { message };
        },
      });
    }, [id, preview]);

    if (field.readonly) return createElement('dl', null, createElement(ReadOnlyValue, { field, value: binding.value }));
    return createElement('div', { ref: element }, createElement(Field, { field, binding, error: error || undefined }));
  }
  FieldWidget.field = true; // the widget host marks its root pp-widget-field, so the page lays it out as a field
  return FieldWidget;
}
