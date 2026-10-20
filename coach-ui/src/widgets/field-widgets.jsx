// Field widgets: one Carbon input bound to a single value. When a Button validates the page, each checks its
// own value (required through the REQUIRED visibility, pattern, and min and max for numbers) and shows the error.
// READONLY draws the value as text; HIDDEN and NONE draw nothing (see runtime.jsx).
import { useEffect, useRef, useState } from 'react';
import { registerWidget } from '../runtime.jsx';
import { Field, fieldError, ReadOnlyValue } from '../components.jsx';
import { page } from '../page-registry.js';

const choices = (list) => (Array.isArray(list) ? list.map((o) => ({ value: o.value, label: o.name ?? o.value })) : []);
const blank = (value) => value === null || value === undefined || value === '';

function rangeError(field, value) {
  if (blank(value)) return null;
  if (!blank(field.min) && Number(value) < Number(field.min)) return field.message || `${field.label} must be at least ${field.min}`;
  if (!blank(field.max) && Number(value) > Number(field.max)) return field.message || `${field.label} must be at most ${field.max}`;
  return null;
}

function fieldWidget(type) {
  return function FieldWidget({ id, label, helpText, visibility, options, binding, preview }) {
    const [error, setError] = useState(null);
    const element = useRef(null);
    const key = useRef({});
    const field = {
      prop: id || label || type, label, type, help: helpText || undefined,
      example: options.example, pattern: options.pattern, message: options.message, min: options.min, max: options.max,
      options: choices(options.options), required: visibility === 'REQUIRED', readonly: visibility === 'READONLY',
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

    if (field.readonly) return <dl><ReadOnlyValue field={field} value={binding.value} /></dl>;
    return <div ref={element}><Field field={field} binding={binding} error={error || undefined} /></div>;
  };
}

for (const type of ['text', 'textarea', 'number', 'date', 'checkbox', 'select', 'radio']) {
  registerWidget(type, fieldWidget(type));
}
