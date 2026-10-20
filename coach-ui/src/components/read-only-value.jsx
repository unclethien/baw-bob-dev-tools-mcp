import { formatValue } from './values.js';

// One field as a label and its value as text, a row of a <dl>.
export function ReadOnlyValue({ field, value }) {
  return <div className="pp-review-row"><dt>{field.label}</dt><dd>{formatValue(field, value)}</dd></div>;
}
