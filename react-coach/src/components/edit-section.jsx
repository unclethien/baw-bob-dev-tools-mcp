import { Field } from './field.jsx';
import { fieldKind } from './values.js';

// A section of inputs in a two-column grid; text areas take the whole row.
export function EditSection({ section, field, errorFor }) {
  return (
    <div className="pp-section">
      {section.title && <h2 className="pp-section-title">{section.title}</h2>}
      <div className="pp-grid">
        {section.fields.map((f) => (
          <div key={f.path} className={fieldKind(f) === 'textarea' ? 'pp-span' : undefined}>
            <Field field={f} binding={field(f.path)} error={errorFor(f.path)} />
          </div>
        ))}
      </div>
    </div>
  );
}
