// The sections one under the other.
export function SectionStack({ sections, body }) {
  return <div className="pp-stack">{sections.map((s, i) => <div key={s.title || i}>{body(s)}</div>)}</div>;
}
