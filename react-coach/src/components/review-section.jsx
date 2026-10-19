import { Tile } from '@carbon/react';
import { ReadOnlyValue } from './read-only-value.jsx';

// A section whose fields are all read-only: a tile of label and value rows.
export function ReviewSection({ section, read }) {
  return (
    <Tile className="pp-review-tile">
      {section.title && <h2>{section.title}</h2>}
      <dl>
        {section.fields.map((f) => <ReadOnlyValue key={f.path} field={f} value={read(f.path)} />)}
      </dl>
    </Tile>
  );
}
