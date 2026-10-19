import { InlineNotification } from '@carbon/react';

// Up to three of the screen's validation messages in one notification.
export function ErrorSummary({ errors }) {
  if (!errors.length) return null;
  return (
    <InlineNotification kind="error" lowContrast hideCloseButton
      title={errors.length === 1 ? '1 field needs attention' : `${errors.length} fields need attention`}
      subtitle={errors.slice(0, 3).map((e) => e.message).join(' · ')} />
  );
}
