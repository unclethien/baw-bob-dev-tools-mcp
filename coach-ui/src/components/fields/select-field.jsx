import { Select, SelectItem } from '@carbon/react';
import { carbonSize, optionKey, optionValue } from '../values.js';

export function SelectField({ id, field, binding, validity, readOnly }) {
  return (
    <Select id={id} size={carbonSize(field.sizeStyle)} labelText={field.label} helperText={field.help} readOnly={readOnly} value={optionKey(binding.value)} onChange={(e) => binding.set(optionValue(field, e.target.value))} {...validity}>
      <SelectItem value="" text={field.example || 'Choose an option'} />
      {(field.options || []).map((o) => <SelectItem key={optionKey(o.value)} value={optionKey(o.value)} text={o.label} />)}
    </Select>
  );
}
