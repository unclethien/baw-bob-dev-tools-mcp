// Generic coach screen driven by a screen spec from coach_inventory.py (see modernize_coaches.py).
// The spec lists sections of fields bound to paths under the coach's business object, and the
// coach's original buttons. The buttons stay in the coach, hidden; pressing one here clicks the
// original, so the coach flow's wiring and scripts run unchanged.
import { useState } from 'react';
import { registerScreen } from './runtime.jsx';
import {
  ActionBar, EditSection, ErrorSummary, Header, ReviewSection, SectionStack, SectionTabs, useValidation,
} from './components.jsx';

function Section({ section, field, read, errorFor }) {
  return section.fields.every((f) => f.readonly)
    ? <ReviewSection section={section} read={read} />
    : <EditSection section={section} field={field} errorFor={errorFor} />;
}

function FormScreen({ field, read, fire, options }) {
  const spec = options.spec || { sections: [], buttons: [] };
  const sections = spec.sections.filter((s) => s.fields.length);
  const [tab, setTab] = useState(0);
  const [busy, setBusy] = useState(false);
  const { errors, check, errorFor } = useValidation(sections, read);
  const tabs = spec.sectionStyle === 'tabs' && sections.length > 1;

  const press = (button) => {
    if (button.validate ?? button.primary) {
      const found = check();
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
      <Header theme={options.theme} subtitle={spec.app} title={spec.title} steps={spec.steps} step={spec.step} />
      {spec.intro && <p className="pp-lead">{spec.intro}</p>}
      <ErrorSummary errors={errors} />
      {tabs
        ? <SectionTabs sections={sections} label={spec.title} tab={tab} onTab={setTab} errors={errors} body={body} />
        : <SectionStack sections={sections} body={body} />}
      <ActionBar buttons={spec.buttons} busy={busy} onPress={press} />
    </>
  );
}

registerScreen('form', FormScreen);
