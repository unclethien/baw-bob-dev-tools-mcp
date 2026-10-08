---
name: react-coach-screen
description: Write a React + Carbon screen for one BAW coach (react-coach/src/screens/<name>.jsx) that replaces the coach's legacy layout while the coach flow, scripts and buttons stay native. Covers the screen contract (props, binding, pressing coach buttons), the shared building blocks, and how to build, attach and test the screen with the baw-dev-tools MCP tools. Use when modernizing a coach and the screen should be designed for that coach rather than rendered by the generic form.
---

# React coach screen

You write one `.jsx` file per coach. The baw-dev-tools MCP server compiles it into the app's React bundle and puts it inside the coach. The coach keeps its buttons (hidden), its flow and its scripts; your screen reads and writes the coach's business object and presses those buttons.

## 1. Design first

From the coach spec (`work/*.coaches.json`, from `inspect_coaches`), read the coach's `sections`, `fields` and `buttons`. Decide what the screen should be for a user, not what the legacy layout was: grouping, order, which fields are required, helper text, what a summary should emphasize. Keep every field the coach collects and every button it has.

## 2. Write the screen

File: `react-coach/src/screens/<acr>-<coach>.jsx`, lower-case kebab, e.g. `zzeq-requester.jsx`. The registered name must equal the file name without `.jsx`.

```jsx
import { useState } from 'react';
import { Button, InlineNotification } from '@carbon/react';
import { registerScreen } from '../runtime.jsx';
import { Field, Header } from '../components.jsx';

function Requester({ field, read, fire, options }) {
  const spec = options.spec;                       // this coach's entry from the coach spec
  const [errors, setErrors] = useState({});
  const next = spec.buttons.find((b) => b.primary);

  const submit = () => {
    const found = {};
    if (!read('employeeName')) found.employeeName = 'Enter the employee name';
    setErrors(found);
    if (!Object.keys(found).length) fire(next.viewId);
  };

  return (
    <>
      <Header theme={options.theme} brand={spec.brand} subtitle={spec.app} title={spec.title} steps={spec.steps} step={spec.step} />
      {Object.keys(errors).length > 0 && <InlineNotification kind="error" lowContrast hideCloseButton title="Check the highlighted fields" />}
      <div className="pp-section">
        <div className="pp-grid">
          <Field field={{ path: 'employeeName', label: 'Employee Name', type: 'text' }} binding={field('employeeName')} error={errors.employeeName} />
        </div>
      </div>
      <div className="pp-actions">
        {spec.buttons.filter((b) => !b.primary).map((b) => <Button key={b.viewId} kind="secondary" onClick={() => fire(b.viewId)}>{b.label}</Button>)}
        <Button kind="primary" onClick={submit}>{next.label}</Button>
      </div>
    </>
  );
}

registerScreen('zzeq-requester', Requester);
```

### Props

| Prop | What it is |
|---|---|
| `field(path)` | `{ value, set(value) }` for a path under the business object, e.g. `field('address.city')` |
| `read(path)` | Current value. Dates are `Date` objects, numbers are numbers, checkboxes are booleans |
| `fire(viewId)` | Presses the coach's own button; the coach flow moves on exactly as the legacy coach did |
| `options.theme` | `"brand"` or `"carbon"`; pass it and `spec.brand` to `Header`, which draws the matching header |
| `options.spec` | `app`, `brand`, `title`, `intro`, `steps[]`, `step`, `sections[].fields[]` (`path`, `label`, `type`, `required`, `pattern`, `message`, `example`, `readonly`) and `buttons[]` (`label`, `viewId`, `primary`) |

### Building blocks

- `../components.jsx`: `Header`, `Field` (`field`, `binding`, `error`; picks the Carbon input from `type`: `text`, `textarea`, `date`, `checkbox`, `number`), `formatValue(field, value)` for read-only display.
- Any `@carbon/react` component (Tabs, Tile, Accordion, ProgressIndicator, InlineNotification, StructuredList…).
- Layout classes: `pp-section`, `pp-section-title`, `pp-grid` (two-column field grid), `pp-span` (full-width cell), `pp-panel`, `pp-stack`, `pp-lead`, `pp-note`, `pp-review-tile`, `pp-review-row`, `pp-actions`. For anything else use inline `style`.

### Rules the tester relies on

- Render `Header` (its `h1` is the screen title).
- Put the buttons in `<div className="pp-actions">`, with exactly one forward button as `kind="primary"`.
- Press buttons only with `fire(button.viewId)` from `spec.buttons`; never click DOM elements.
- Bind only to paths that appear in the coach spec. Never invent fields: the business object has no others.
- No network calls, no `window`/`document` access, no new npm packages.

## 3. Build, attach, test

1. `build_screens` compiles every screen. On an error, fix the file at the reported line and build again.
2. In the coach spec, add `"screen": "<registered name>"` to that coach. Coaches without `screen` keep the generic form.
3. `modernize_app` with a new snapshot, then `install_app`, then `test_service` for both themes. Open the screenshots and check your screen looks as designed. If not, change the screen and repeat with a new snapshot.
