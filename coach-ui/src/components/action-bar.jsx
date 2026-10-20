import { Button } from '@carbon/react';

export const buttonLabel = (label) => label.replace(/^[\s<>«»]+|[\s<>«»]+$/g, '') || label;

// The coach's buttons in spec order, primary or secondary; onPress gets the spec button.
export function ActionBar({ buttons, busy, onPress }) {
  if (!buttons.length) return null;
  return (
    <div className="pp-actions">
      {buttons.map((b) => (
        <Button key={b.viewId} kind={b.primary ? 'primary' : 'secondary'} disabled={busy} onClick={() => onPress(b)}>
          {buttonLabel(b.label)}
        </Button>
      ))}
    </div>
  );
}
