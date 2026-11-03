import { TextArea } from '@carbon/react';
import { cssLength } from '../values.js';

// height: any CSS length; a bare number is pixels. Carbon's TextArea has no size, so Size is styled on the widget (styles.scss).
export function TextAreaField({ id, field, binding, validity, readOnly }) {
  const height = cssLength(field.height);
  return <TextArea id={id} labelText={field.label} helperText={field.help} placeholder={field.example} rows={3} readOnly={readOnly} value={binding.value || ''} onChange={(e) => binding.set(e.target.value)}
    style={height && { height }} {...validity} />;
}
