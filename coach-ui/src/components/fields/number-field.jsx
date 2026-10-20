import { NumberInput } from '@carbon/react';

export function NumberField({ id, field, binding, validity, readOnly }) {
  return (
    <NumberInput id={id} label={field.label} placeholder={field.example} hideSteppers readOnly={readOnly} value={binding.value ?? ''} {...validity}
      onChange={(_, { value }) => binding.set(value === '' ? null : Number(value))} />
  );
}
