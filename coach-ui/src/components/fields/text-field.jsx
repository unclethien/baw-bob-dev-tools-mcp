import { TextInput } from '@carbon/react';
import { carbonSize, on } from '../values.js';

// selectAll: the text is selected when the input takes the focus (the UI Toolkit Text's "Select all" option).
export function TextField({ id, field, binding, validity, readOnly }) {
  return <TextInput id={id} size={carbonSize(field.sizeStyle)} labelText={field.label} helperText={field.help} placeholder={field.example} readOnly={readOnly} value={binding.value ?? ''} onChange={(e) => binding.set(e.target.value)}
    onFocus={on(field.selectAll) ? (e) => e.target.select() : undefined} {...validity} />;
}
