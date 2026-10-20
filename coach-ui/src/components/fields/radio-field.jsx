import { RadioButton, RadioButtonGroup } from '@carbon/react';

export function RadioField({ id, field, binding, validity, readOnly }) {
  return (
    <RadioButtonGroup legendText={field.label} name={id} valueSelected={binding.value ?? ''} readOnly={readOnly}
      onChange={(value) => binding.set(value)} {...validity}>
      {(field.options || []).map((o) => <RadioButton key={o.value} id={`${id}-${o.value}`} value={o.value} labelText={o.label} />)}
    </RadioButtonGroup>
  );
}
