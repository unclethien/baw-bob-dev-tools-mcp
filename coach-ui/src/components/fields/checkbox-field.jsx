import { Checkbox } from '@carbon/react';
import { validationMarker } from './validation-marker.jsx';

export function CheckboxField({ id, field, binding, validity, readOnly }) {
  return <Checkbox id={id} labelText={field.label} helperText={field.help} checked={!!binding.value} readOnly={readOnly} onChange={(_, { checked }) => binding.set(checked)}
    decorator={validationMarker(field, validity)} {...validity} />;
}
