// What a field is and how its value reads as text, from a coach inventory spec field.
export const toDate = (value) => (value instanceof Date ? value : value ? new Date(value) : null);

// Field types come from a coach inventory spec (text, date, checkbox, textarea, number, select, radio, output);
// BAW type names (String, Date, Boolean, Text Area) are accepted too. select and radio carry options: [{value, label}].
export function fieldKind(field) {
  return {
    Boolean: 'checkbox', checkbox: 'checkbox', Date: 'date', date: 'date',
    'Text Area': 'textarea', textarea: 'textarea', number: 'number', output: 'output',
    Select: 'select', select: 'select', Radio: 'radio', radio: 'radio',
  }[field.type] || 'text';
}

// Option values may be booleans or numbers while the browser hands back text, so options compare as strings.
export const optionKey = (value) => (value === null || value === undefined ? '' : String(value));

const optionLabel = (field, value) => (field.options || []).find((o) => optionKey(o.value) === optionKey(value))?.label ?? value;

// What a picked option writes to the binding: true/false when the options are exactly those two, numbers when every
// option is a number, otherwise the text. Nothing picked (the blank item) writes null.
export function optionValue(field, picked) {
  if (picked === '' || picked === null || picked === undefined) return null;
  const keys = (field.options || []).map((o) => optionKey(o.value));
  if (keys.length === 2 && keys.includes('true') && keys.includes('false')) return picked === 'true';
  if (keys.length && keys.every((key) => key.trim() !== '' && Number.isFinite(Number(key)))) return Number(picked);
  return picked;
}

// A field may carry its own display(field, value) and isEmpty(field, value) (a widget of its own kind); they win.
export function formatValue(field, value) {
  if (field.display) return field.display(field, value);
  const kind = fieldKind(field);
  if (kind === 'checkbox') return value ? 'Yes' : 'No';
  if (kind === 'date') return toDate(value)?.toLocaleDateString() || '—';
  if (kind === 'select' || kind === 'radio') return value === null || value === undefined || value === '' ? '—' : String(optionLabel(field, value));
  return value === 0 ? '0' : value || '—';
}

export const isEmpty = (field, value) => {
  if (field.isEmpty) return field.isEmpty(field, value);
  return fieldKind(field) === 'checkbox' ? !value : value === null || value === undefined || value === '';
};

// A Boolean option as a coach stores it: true, or "true" when it was carried over from a UI Toolkit coach as text.
export const on = (flag) => flag === true || flag === 'true';

// A CSS length option (Width, Label width, Height): a bare number is pixels.
export const cssLength = (value) => (value === null || value === undefined || value === '' ? undefined
  : /^\d+(\.\d+)?$/.test(String(value)) ? `${value}px` : String(value));

// The Size option (the UI Toolkit's TextSizeStyle: D Default, S Small, L Large) as a Carbon input's size prop.
export const carbonSize = (sizeStyle) => ({ S: 'sm', L: 'lg' })[sizeStyle];
