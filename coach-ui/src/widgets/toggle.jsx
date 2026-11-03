// Yes/No Toggle: a Carbon switch bound to one Boolean, standing for the UI Toolkit Switch (On label, Off label, Size;
// Large is styled in styles.scss, since Carbon's Toggle has sm and md only). Off is a valid "No", so REQUIRED is ignored
// (unlike Checkbox, where REQUIRED means "must be ticked").
import { Toggle } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';
import { fieldWidget } from './field-widget.js';

// Carbon's Toggle has no helper text of its own, so the field's help text goes below it in Carbon's helper style.
function ToggleInput({ id, field, binding, readOnly }) {
  return (
    <div className="pp--form-item">
      <Toggle id={id} size={field.sizeStyle === 'S' ? 'sm' : 'md'} labelText={field.label} toggled={!!binding.value} labelA={field.offLabel || 'No'} labelB={field.onLabel || 'Yes'}
        readOnly={readOnly} onToggle={(on) => binding.set(on)} />
      {field.help && <div className="pp--form__helper-text">{field.help}</div>}
    </div>
  );
}

registerWidget('toggle', fieldWidget('toggle', {
  Input: ToggleInput,
  display: (field, value) => (value ? field.onLabel || 'Yes' : field.offLabel || 'No'),
  isEmpty: () => false,
}));
