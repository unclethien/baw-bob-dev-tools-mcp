// Yes/No Toggle: a Carbon switch bound to one Boolean. Off is a valid "No", so REQUIRED is ignored
// (unlike Checkbox, where REQUIRED means "must be ticked").
import { Toggle } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';
import { fieldWidget } from './field-widget.js';

// Carbon's Toggle has no helper text of its own, so the field's help text goes below it in Carbon's helper style.
function ToggleInput({ id, field, binding, readOnly }) {
  return (
    <div className="pp--form-item">
      <Toggle id={id} labelText={field.label} toggled={!!binding.value} labelA={field.offText || 'No'} labelB={field.onText || 'Yes'}
        readOnly={readOnly} onToggle={(on) => binding.set(on)} />
      {field.help && <div className="pp--form__helper-text">{field.help}</div>}
    </div>
  );
}

registerWidget('toggle', fieldWidget('toggle', {
  Input: ToggleInput,
  display: (field, value) => (value ? field.onText || 'Yes' : field.offText || 'No'),
  isEmpty: () => false,
}));
