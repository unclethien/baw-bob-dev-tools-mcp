// Generic coach screen driven by a screen spec from coach_inventory.py (see modernize_coaches.py).
// The spec lists sections of fields bound to paths under the coach's business object, and the
// coach's original buttons. The buttons stay in the coach, hidden; pressing one here clicks the
// original, so the coach flow's wiring and scripts run unchanged.
import { useState } from 'react';
import { Button, InlineNotification, Tab, TabList, TabPanel, TabPanels, Tabs, Tile } from '@carbon/react';
import { registerScreen } from './runtime.jsx';
import { Field, fieldKind, formatValue, Header } from './components.jsx';

const isEmpty = (field, value) => (fieldKind(field) === 'checkbox' ? !value : value === null || value === undefined || value === '');
const buttonLabel = (label) => label.replace(/^[\s<>«»]+|[\s<>«»]+$/g, '') || label;

function validate(sections, read) {
  const errors = [];
  sections.forEach((section, tab) => section.fields.forEach((f) => {
    if (f.readonly) return;
    const value = read(f.path);
    if (f.required && isEmpty(f, value)) {
      errors.push({ tab, path: f.path, message: f.message || `${f.label} is required` });
    } else if (f.pattern && !isEmpty(f, value) && !new RegExp(f.pattern).test(String(value))) {
      errors.push({ tab, path: f.path, message: f.message || `${f.label} is not valid` });
    }
  }));
  return errors;
}

function Section({ section, field, read, errorFor }) {
  if (section.fields.every((f) => f.readonly)) {
    return (
      <Tile className="pp-review-tile">
        {section.title && <h2>{section.title}</h2>}
        <dl>
          {section.fields.map((f) => (
            <div key={f.path} className="pp-review-row"><dt>{f.label}</dt><dd>{formatValue(f, read(f.path))}</dd></div>
          ))}
        </dl>
      </Tile>
    );
  }
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

function FormScreen({ field, read, fire, options }) {
  const spec = options.spec || { sections: [], buttons: [] };
  const sections = spec.sections.filter((s) => s.fields.length);
  const [tab, setTab] = useState(0);
  const [errors, setErrors] = useState([]);
  const [busy, setBusy] = useState(false);
  const errorFor = (path) => errors.find((e) => e.path === path)?.message;
  const tabs = spec.sectionStyle === 'tabs' && sections.length > 1;

  const press = (button) => {
    if (button.validate ?? button.primary) {
      const found = validate(sections, read);
      setErrors(found);
      if (found.length) {
        if (tabs) setTab(found[0].tab);
        return;
      }
    }
    setBusy(true);
    fire(button.viewId);
  };

  const body = (section) => <Section section={section} field={field} read={read} errorFor={errorFor} />;
  return (
    <>
      <Header theme={options.theme} brand={spec.brand} subtitle={spec.app} title={spec.title} steps={spec.steps} step={spec.step} />
      {spec.intro && <p className="pp-lead">{spec.intro}</p>}
      {errors.length > 0 && (
        <InlineNotification kind="error" lowContrast hideCloseButton
          title={errors.length === 1 ? '1 field needs attention' : `${errors.length} fields need attention`}
          subtitle={errors.slice(0, 3).map((e) => e.message).join(' · ')} />
      )}
      {tabs ? (
        <Tabs selectedIndex={tab} onChange={({ selectedIndex }) => setTab(selectedIndex)}>
          <TabList aria-label={spec.title} contained>
            {sections.map((s, i) => <Tab key={s.title || i}>{s.title}{errors.some((e) => e.tab === i) ? ' •' : ''}</Tab>)}
          </TabList>
          <TabPanels>
            {sections.map((s, i) => <TabPanel key={s.title || i} className="pp-panel">{body({ ...s, title: '' })}</TabPanel>)}
          </TabPanels>
        </Tabs>
      ) : (
        <div className="pp-stack">{sections.map((s, i) => <div key={s.title || i}>{body(s)}</div>)}</div>
      )}
      {spec.buttons.length > 0 && (
        <div className="pp-actions">
          {spec.buttons.map((b) => (
            <Button key={b.viewId} kind={b.primary ? 'primary' : 'secondary'} disabled={busy} onClick={() => press(b)}>
              {buttonLabel(b.label)}
            </Button>
          ))}
        </div>
      )}
    </>
  );
}

registerScreen('form', FormScreen);
