// The stock field widgets: one Carbon input bound to a single value (see field-widget.js for what each does).
// A new field widget is its own file in this folder that registers itself the same way.
import { registerWidget } from '../runtime.jsx';
import { fieldWidget } from './field-widget.js';

for (const type of ['text', 'textarea', 'number', 'date', 'checkbox', 'select', 'radio']) {
  registerWidget(type, fieldWidget(type));
}
