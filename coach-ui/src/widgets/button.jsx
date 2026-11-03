// Button widget: fires the Coach View's boundary event, so the coach flow wires it like any button. Its eventON_CLICK
// handler runs first, and returning false cancels the press, as on a UI Toolkit Button. With "validate" (the default
// for primary buttons) it then checks every field widget on the page, shows the tab that holds the first error, and
// does not fire while any field is invalid.
import { useState } from 'react';
import { Button } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';
import { buttonLabel } from '../components.jsx';
import { page, reveal } from '../page-registry.js';

const KINDS = ['primary', 'secondary', 'tertiary', 'ghost', 'danger'];
// Size, as the UI Toolkit's ButtonSizeStyle: X Extra-Small, S Small, D Default, L Large. Width is the widget's (runtime.jsx).
const SIZES = { X: 'sm', S: 'md', D: 'lg', L: 'xl' };

function ActionButton({ label, options, trigger, fire, preview }) {
  const [busy, setBusy] = useState(false);
  const named = String(options.kind || '').toLowerCase();
  const kind = KINDS.includes(named) ? named : 'primary';
  const validates = options.validate === null || options.validate === undefined ? kind === 'primary' || kind === 'danger'
    : options.validate === true || options.validate === 'true';
  const press = () => {
    if (preview) return;
    if (fire('eventON_CLICK') === false) return;
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
      <Button kind={kind} size={SIZES[options.sizeStyle] || 'lg'} disabled={busy} onClick={press}>{buttonLabel(label || 'Button')}</Button>
    </div>
  );
}

registerWidget('button', ActionButton);
