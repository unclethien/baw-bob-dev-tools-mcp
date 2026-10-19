import { TextArea } from '@carbon/react';

export function TextAreaField({ id, field, binding, validity, readOnly }) {
  return <TextArea id={id} labelText={field.label} placeholder={field.example} rows={3} readOnly={readOnly} value={binding.value || ''} onChange={(e) => binding.set(e.target.value)} {...validity} />;
}
