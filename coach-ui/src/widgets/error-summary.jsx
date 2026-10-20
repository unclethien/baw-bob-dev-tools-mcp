// Error Summary widget: the messages of the last validation on the page, like the generic form's banner.
import { useSyncExternalStore } from 'react';
import { registerWidget } from '../runtime.jsx';
import { ErrorSummary } from '../components.jsx';
import { page } from '../page-registry.js';

const SAMPLE = [{ message: 'A required field is empty' }];

function ErrorSummaryWidget({ preview }) {
  const errors = useSyncExternalStore(page.subscribe, () => page.errors);
  return <ErrorSummary errors={preview ? SAMPLE : errors} />;
}

registerWidget('errors', ErrorSummaryWidget);
