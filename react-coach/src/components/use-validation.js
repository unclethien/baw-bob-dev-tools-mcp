// Required fields and patterns of a screen's sections; each error names its section (tab) and field path.
import { useState } from 'react';
import { isEmpty } from './values.js';

// The message for one field's value, or null when it passes. Read-only fields always pass.
export function fieldError(field, value) {
  if (field.readonly) return null;
  if (field.required && isEmpty(field, value)) return field.message || `${field.label} is required`;
  if (field.pattern && !isEmpty(field, value) && !new RegExp(field.pattern).test(String(value))) return field.message || `${field.label} is not valid`;
  return null;
}

export function validate(sections, read) {
  const errors = [];
  sections.forEach((section, tab) => section.fields.forEach((f) => {
    const message = fieldError(f, read(f.path));
    if (message) errors.push({ tab, path: f.path, message });
  }));
  return errors;
}

// check() validates and shows the errors; it returns them so the caller can switch tabs or stop.
export function useValidation(sections, read) {
  const [errors, setErrors] = useState([]);
  const check = () => {
    const found = validate(sections, read);
    setErrors(found);
    return found;
  };
  return { errors, check, errorFor: (path) => errors.find((e) => e.path === path)?.message };
}
