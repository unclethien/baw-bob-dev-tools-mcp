import { Tooltip } from '@carbon/react';
import { WarningFilled } from '@carbon/react/icons';
import { on } from '../values.js';

// Show validation marker (the UI Toolkit's showValidationMarker): on an error, a warning icon beside the label whose
// tooltip gives the error, as on a UI Toolkit Checkbox or Radio Button Group. The error text below stays either way.
// Pass it as the Carbon component's decorator; undefined when the option is off or the field is valid.
export function validationMarker(field, validity) {
  if (!on(field.showValidationMarker) || !validity.invalid) return undefined;
  return (
    <Tooltip label={validity.invalidText} align="top">
      <button type="button" className="pp-validation-marker" aria-label={validity.invalidText}>
        <WarningFilled size={16} aria-hidden="true" />
      </button>
    </Tooltip>
  );
}
