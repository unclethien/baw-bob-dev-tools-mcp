import { NumberInput } from '@carbon/react';

// type="text": the user types freely and Carbon parses the number on blur. With type="number" Carbon keeps its own
// copy of the value, which a bound value written back on every keystroke resets, so decimals could not be typed.
// No thousands separators: a year or an ID reads as typed, as it did with type="number".
// decimalPlaces: the number is shown with, and kept to, that many decimals.
const NO_GROUPING = { useGrouping: false, maximumFractionDigits: 20 };

function places(field) {
  const n = field.decimalPlaces === null || field.decimalPlaces === undefined || field.decimalPlaces === '' ? NaN : Number(field.decimalPlaces);
  return Number.isInteger(n) && n >= 0 && n <= 20 ? n : null;
}

export function NumberField({ id, field, binding, validity, readOnly }) {
  const decimals = places(field);
  const format = decimals === null ? NO_GROUPING : { useGrouping: false, minimumFractionDigits: decimals, maximumFractionDigits: decimals };
  const keep = (n) => (decimals === null ? n : Number(n.toFixed(decimals)));
  return (
    <NumberInput id={id} type="text" inputMode="decimal" allowEmpty formatOptions={format} label={field.label} helperText={field.help} placeholder={field.example}
      hideSteppers readOnly={readOnly} value={binding.value ?? ''} {...validity}
      onChange={(_, { value }) => binding.set(value === '' || value === null || value === undefined || Number.isNaN(Number(value)) ? null : keep(Number(value)))} />
  );
}
