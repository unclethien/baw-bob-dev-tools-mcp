import { TextInput } from '@carbon/react';

export function TextField({ id, field, binding, validity, readOnly }) {
  return <TextInput id={id} labelText={field.label} placeholder={field.example} readOnly={readOnly} value={binding.value ?? ''} onChange={(e) => binding.set(e.target.value)} {...validity} />;
}
