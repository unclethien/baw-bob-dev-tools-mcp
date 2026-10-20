// Button widget: fires the Coach View's boundary event, so the coach flow wires it like any button.
import { useState } from 'react';
import { Button } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';

function ActionButton({ label, options, trigger, preview }) {
  const [busy, setBusy] = useState(false);
  const press = () => {
    if (preview) return;
    setBusy(true);
    trigger();
  };
  return (
    <div className="pp-actions">
      <Button kind={options.kind === 'secondary' ? 'secondary' : 'primary'} disabled={busy} onClick={press}>{label || 'Button'}</Button>
    </div>
  );
}

registerWidget('button', ActionButton);
