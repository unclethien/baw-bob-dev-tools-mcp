import { DatePicker, DatePickerInput } from '@carbon/react';
import { toDate } from '../values.js';

// A date typed as mm/dd/yyyy, or null when it is not a real date (02/31/2026). whole: only the full two-digit form,
// for use while typing, when 1/2/2026 may still be on its way to 1/28/2026.
function parseTyped(text, whole) {
  const m = (whole ? /^(\d{2})\/(\d{2})\/(\d{4})$/ : /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/).exec(text.trim());
  if (!m) return null;
  const date = new Date(Number(m[3]), Number(m[1]) - 1, Number(m[2]));
  return date.getMonth() === Number(m[1]) - 1 ? date : null;
}

// Picking from the calendar sets the date at once. A typed date is kept as soon as it reads as a full mm/dd/yyyy date,
// and in any form on blur. Waiting for blur alone is not enough: tabbing into the input opens the calendar, and Tab
// then stays in the input.
export function DateField({ id, field, binding, validity, readOnly }) {
  const commit = (text, whole) => {
    const date = parseTyped(text, whole);
    if (date && toDate(binding.value)?.getTime() !== date.getTime()) binding.set(date);
  };
  return (
    <DatePicker datePickerType="single" value={toDate(binding.value) || undefined} readOnly={readOnly} onChange={([d]) => d && binding.set(d)}>
      <DatePickerInput id={id} labelText={field.label} helperText={field.help} placeholder="mm/dd/yyyy" onChange={(e) => commit(e.target.value, true)} onBlur={(e) => commit(e.target.value, false)} {...validity} />
    </DatePicker>
  );
}
