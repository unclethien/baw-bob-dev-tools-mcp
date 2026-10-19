import { DatePicker, DatePickerInput } from '@carbon/react';
import { toDate } from '../values.js';

export function DateField({ id, field, binding, validity, readOnly }) {
  return (
    <DatePicker datePickerType="single" value={toDate(binding.value) || undefined} readOnly={readOnly} onChange={([d]) => d && binding.set(d)}>
      <DatePickerInput id={id} labelText={field.label} placeholder="mm/dd/yyyy" {...validity} />
    </DatePicker>
  );
}
