import { NumberInput } from '@carbon/react';

// type="text": the user types freely and Carbon parses the number on blur. With type="number" Carbon keeps its own
// copy of the value, which a bound value written back on every keystroke resets, so decimals could not be typed.
// No thousands separators: a year or an ID reads as typed, as it did with type="number".
const NO_GROUPING = { useGrouping: false, maximumFractionDigits: 20 };

export function NumberField({ id, field, binding, validity, readOnly }) {
  return (
    <NumberInput id={id} type="text" inputMode="decimal" allowEmpty formatOptions={NO_GROUPING} label={field.label} helperText={field.help} placeholder={field.example}
      hideSteppers readOnly={readOnly} value={binding.value ?? ''} {...validity}
      onChange={(_, { value }) => binding.set(value === '' || value === null || value === undefined || Number.isNaN(Number(value)) ? null : Number(value))} />
  );
}
