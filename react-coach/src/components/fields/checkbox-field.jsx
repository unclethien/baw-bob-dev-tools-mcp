import { Checkbox } from '@carbon/react';

export function CheckboxField({ id, field, binding, validity, readOnly }) {
  return <Checkbox id={id} labelText={field.label} checked={!!binding.value} readOnly={readOnly} onChange={(_, { checked }) => binding.set(checked)} {...validity} />;
}
