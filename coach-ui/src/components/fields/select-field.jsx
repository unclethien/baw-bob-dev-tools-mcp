import { Select, SelectItem } from '@carbon/react';

export function SelectField({ id, field, binding, validity, readOnly }) {
  return (
    <Select id={id} labelText={field.label} readOnly={readOnly} value={binding.value ?? ''} onChange={(e) => binding.set(e.target.value)} {...validity}>
      <SelectItem value="" text="Choose an option" />
      {(field.options || []).map((o) => <SelectItem key={o.value} value={o.value} text={o.label} />)}
    </Select>
  );
}
