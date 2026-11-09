import { RadioButton, RadioButtonGroup } from '@carbon/react';
import { optionKey, optionValue } from '../values.js';
import { validationMarker } from './validation-marker.jsx';

export function RadioField({ id, field, binding, validity, readOnly }) {
  return (
    <RadioButtonGroup legendText={field.label} helperText={field.help} name={id} valueSelected={optionKey(binding.value)} readOnly={readOnly}
      onChange={(value) => binding.set(optionValue(field, value))} decorator={validationMarker(field, validity)} {...validity}>
      {(field.options || []).map((o) => <RadioButton key={optionKey(o.value)} id={`${id}-${optionKey(o.value)}`} value={optionKey(o.value)} labelText={o.label} />)}
    </RadioButtonGroup>
  );
}
