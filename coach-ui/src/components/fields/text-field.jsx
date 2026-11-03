import { TextInput } from '@carbon/react';

// selectAll: the text is selected when the input takes the focus (the UI Toolkit Text's "Select all" option).
const on = (flag) => flag === true || flag === 'true';

export function TextField({ id, field, binding, validity, readOnly }) {
  return <TextInput id={id} labelText={field.label} helperText={field.help} placeholder={field.example} readOnly={readOnly} value={binding.value ?? ''} onChange={(e) => binding.set(e.target.value)}
    onFocus={on(field.selectAll) ? (e) => e.target.select() : undefined} {...validity} />;
}
