import { RadioButton, RadioButtonGroup } from '@carbon/react';
import { validationMarker } from './validation-marker.jsx';

export function RadioField({ id, field, binding, validity, readOnly }) {
  return (
    <RadioButtonGroup legendText={field.label} helperText={field.help} name={id} valueSelected={binding.value ?? ''} readOnly={readOnly}
      onChange={(value) => binding.set(value)} decorator={validationMarker(field, validity)} {...validity}>
      {(field.options || []).map((o) => <RadioButton key={o.value} id={`${id}-${o.value}`} value={o.value} labelText={o.label} />)}
    </RadioButtonGroup>
  );
}
