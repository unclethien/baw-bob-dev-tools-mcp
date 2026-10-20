// Text Field widget: one Carbon text input bound to a String.
import { registerWidget } from '../runtime.jsx';
import { Field } from '../components.jsx';

function TextField({ label, helpText, visibility, options, binding }) {
  const field = { prop: options.id || label || 'text', label, type: 'text', example: options.example || helpText, readonly: visibility === 'READONLY' };
  return <Field field={field} binding={binding} />;
}

registerWidget('text', TextField);
