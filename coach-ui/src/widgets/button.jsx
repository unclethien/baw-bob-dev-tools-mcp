// Button widget: fires the Coach View's boundary event, so the coach flow wires it like any button. With
// "validate" (the default for primary buttons) it first checks every field widget on the page, shows the
// tab that holds the first error, and does not fire while any field is invalid.
import { useState } from 'react';
import { Button } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';
import { buttonLabel } from '../components.jsx';
import { page, reveal } from '../page-registry.js';

function ActionButton({ label, options, trigger, preview }) {
  const [busy, setBusy] = useState(false);
  const secondary = String(options.kind || '').toLowerCase() === 'secondary';
  const validates = options.validate === null || options.validate === undefined ? !secondary : options.validate === true || options.validate === 'true';
  const press = () => {
    if (preview) return;
    if (validates) {
      const errors = page.validateAll();
      if (errors.length) {
        reveal(errors[0].element);
        return;
      }
    }
    setBusy(true);
    trigger(() => setBusy(false));
  };
  return (
    <div className="pp-actions">
      <Button kind={secondary ? 'secondary' : 'primary'} disabled={busy} onClick={press}>{buttonLabel(label || 'Button')}</Button>
    </div>
  );
}

registerWidget('button', ActionButton);
