// One input for a spec field: picks the Carbon input from the field's kind.
import { fieldKind } from './values.js';
import { CheckboxField } from './fields/checkbox-field.jsx';
import { DateField } from './fields/date-field.jsx';
import { NumberField } from './fields/number-field.jsx';
import { RadioField } from './fields/radio-field.jsx';
import { SelectField } from './fields/select-field.jsx';
import { TextAreaField } from './fields/text-area-field.jsx';
import { TextField } from './fields/text-field.jsx';

const INPUTS = {
  checkbox: CheckboxField, date: DateField, select: SelectField, radio: RadioField,
  textarea: TextAreaField, number: NumberField,
};

export function Field({ field, binding, error }) {
  const Input = INPUTS[fieldKind(field)] || TextField;
  const id = `pp-${String(field.prop || field.path).replace(/[^\w-]/g, '-')}`;
  return <Input id={id} field={field} binding={binding} validity={{ invalid: !!error, invalidText: error }} readOnly={!!field.readonly} />;
}
