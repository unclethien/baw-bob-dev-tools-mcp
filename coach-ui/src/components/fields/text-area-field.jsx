import { TextArea } from '@carbon/react';

// height: any CSS length; a bare number is pixels.
const cssLength = (value) => (value === null || value === undefined || value === '' ? undefined : /^\d+(\.\d+)?$/.test(String(value)) ? `${value}px` : String(value));

export function TextAreaField({ id, field, binding, validity, readOnly }) {
  const height = cssLength(field.height);
  return <TextArea id={id} labelText={field.label} helperText={field.help} placeholder={field.example} rows={3} readOnly={readOnly} value={binding.value || ''} onChange={(e) => binding.set(e.target.value)}
    style={height && { height }} {...validity} />;
}
