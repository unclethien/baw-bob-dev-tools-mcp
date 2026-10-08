// Building blocks shared by the screens: the branded header and one input per field type.
import {
  Checkbox, DatePicker, DatePickerInput, NumberInput, ProgressIndicator, ProgressStep, RadioButton, RadioButtonGroup,
  Select, SelectItem, TextArea, TextInput,
} from '@carbon/react';

export function Header({ theme, brand, subtitle, title, steps, step }) {
  return (
    <header className="pp-header">
      <div className="pp-brand">
        <span className="pp-brand-mark">{theme === 'carbon' ? 'IBM BAW' : brand || 'Business Automation Workflow'}</span>
        {subtitle && <span className="pp-brand-sub">{subtitle}</span>}
      </div>
      <h1>{title}</h1>
      {steps?.length > 1 && (
        <ProgressIndicator currentIndex={step} spaceEqually className="pp-progress">
          {steps.map((label) => <ProgressStep key={label} label={label} />)}
        </ProgressIndicator>
      )}
    </header>
  );
}

export const toDate = (value) => (value instanceof Date ? value : value ? new Date(value) : null);

// Field types come from a coach inventory spec (text, date, checkbox, textarea, number, select, radio, output);
// BAW type names (String, Date, Boolean, Text Area) are accepted too. select and radio carry options: [{value, label}].
export function fieldKind(field) {
  return {
    Boolean: 'checkbox', checkbox: 'checkbox', Date: 'date', date: 'date',
    'Text Area': 'textarea', textarea: 'textarea', number: 'number', output: 'output',
    Select: 'select', select: 'select', Radio: 'radio', radio: 'radio',
  }[field.type] || 'text';
}

const optionLabel = (field, value) => (field.options || []).find((o) => o.value === value)?.label ?? value;

export function formatValue(field, value) {
  const kind = fieldKind(field);
  if (kind === 'checkbox') return value ? 'Yes' : 'No';
  if (kind === 'date') return toDate(value)?.toLocaleDateString() || '—';
  if (kind === 'select' || kind === 'radio') return optionLabel(field, value) || '—';
  return value === 0 ? '0' : value || '—';
}

export function Field({ field: f, binding, error }) {
  const id = `pp-${(f.prop || f.path).replace(/\./g, '-')}`;
  const invalid = { invalid: !!error, invalidText: error };
  const readOnly = !!f.readonly;
  switch (fieldKind(f)) {
    case 'checkbox':
      return <Checkbox id={id} labelText={f.label} checked={!!binding.value} readOnly={readOnly} onChange={(_, { checked }) => binding.set(checked)} {...invalid} />;
    case 'date':
      return (
        <DatePicker datePickerType="single" value={toDate(binding.value) || undefined} readOnly={readOnly} onChange={([d]) => d && binding.set(d)}>
          <DatePickerInput id={id} labelText={f.label} placeholder="mm/dd/yyyy" {...invalid} />
        </DatePicker>
      );
    case 'select':
      return (
        <Select id={id} labelText={f.label} readOnly={readOnly} value={binding.value ?? ''} onChange={(e) => binding.set(e.target.value)} {...invalid}>
          <SelectItem value="" text="Choose an option" />
          {(f.options || []).map((o) => <SelectItem key={o.value} value={o.value} text={o.label} />)}
        </Select>
      );
    case 'radio':
      return (
        <RadioButtonGroup legendText={f.label} name={id} valueSelected={binding.value ?? ''} readOnly={readOnly}
          onChange={(value) => binding.set(value)} {...invalid}>
          {(f.options || []).map((o) => <RadioButton key={o.value} id={`${id}-${o.value}`} value={o.value} labelText={o.label} />)}
        </RadioButtonGroup>
      );
    case 'textarea':
      return <TextArea id={id} labelText={f.label} placeholder={f.example} rows={3} readOnly={readOnly} value={binding.value || ''} onChange={(e) => binding.set(e.target.value)} {...invalid} />;
    case 'number':
      return (
        <NumberInput id={id} label={f.label} placeholder={f.example} hideSteppers readOnly={readOnly} value={binding.value ?? ''} {...invalid}
          onChange={(_, { value }) => binding.set(value === '' ? null : Number(value))} />
      );
    default:
      return <TextInput id={id} labelText={f.label} placeholder={f.example} readOnly={readOnly} value={binding.value ?? ''} onChange={(e) => binding.set(e.target.value)} {...invalid} />;
  }
}
