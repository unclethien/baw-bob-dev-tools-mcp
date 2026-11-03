---
name: modernizer-widget
description: Add one new widget to the Modernizer Widgets (MDW) toolkit while modernizing an app. It can be a field (binds one value, a choice list included), an action (fires the boundary event, like Button), a display (shows its options or the page's state, like Header and Error Summary) or a page-level widget (draws nothing on the page, like Theme). Write its React + Carbon component, its entry in the widget contract (Configuration groups, Events, accessor) and its palette icon; check it, build and install a new MDW snapshot, and use it in the coach spec, with the baw-dev-tools MCP tools. Use only when the approved modernization plan names a new widget that no existing Modernizer Widget can replace. Never use it to change or remove an existing widget; that is a code change for Agent mode.
---

# Modernizer widget

A new Modernizer Widget is one Coach View of the MDW toolkit. Authors find it in Coach Designer's palette like the stock widgets. Its options appear in Configuration under Behavior, Items and Appearance, and its events in the Events tab, as on a UI Toolkit control. You add it only when the approved plan names it.

## 1. Decide

- Add a widget only when no widget in `coach-ui/widgets/modernizer-widgets.json` does the job. Read the contract first.
- Never edit or remove an existing widget, its file, or its contract entry. When the request is to change one, stop and hand it to Agent mode.
- Settle: the `kind` (lower-case letters and digits, unique, the file name), the palette name (`view`), which of the four kinds below it is, the options authors can set, a preview value and the tags.

| Kind | What it does | `binding` | `label` | `boundary` | Copy from | Stock examples |
|---|---|---|---|---|---|---|
| Field | Binds one value: String, Integer, Decimal, Boolean or Date. With an `options` list it is a choice | the type | `true` | `false` | `coach-ui/src/widgets/toggle.jsx` | Text Field, Number Field, Date Field, Checkbox, Select, Radio Group, Toggle |
| Action | Fires the view's boundary event, so the coach flow wires it like a button | `null` | `true` | `true` | `coach-ui/src/widgets/button.jsx` | Button |
| Display | Shows its options or the page's state, binds nothing | `null` | `false` | `false` | `coach-ui/src/widgets/header.jsx`, `error-summary.jsx` | Header, Error Summary |
| Page-level | Changes the page, draws nothing there, and shows a marker in Coach Designer | `null` | `false` | `false` | `coach-ui/src/widgets/theme.jsx` | Theme |

A widget that needs several values or a whole business object is out of scope. Use stock widgets, or a hand-written screen (react-coach-screen skill), and say so.

Read only the file in the "Copy from" column for your kind, plus `coach-ui/src/widgets/field-widget.js` for a field. Read no other platform file. The build picks up every `coach-ui/src/widgets/*.jsx` by itself, so the new file needs no import anywhere.

## 2. Write the component: `coach-ui/src/widgets/<kind>.jsx`

Every widget calls `registerWidget('<kind>', Component)` from `'../runtime.jsx'`. The component gets these props:

| Prop | What it is |
|---|---|
| `id` | The view's unique ID on the page |
| `label`, `helpText` | The view's label and help text |
| `visibility` | `EDITABLE`, `REQUIRED` or `READONLY` (the host already hides `HIDDEN` and `NONE`) |
| `options` | Every option the contract declares, by name, as plain data (a NameValuePair list becomes `[{ name, value }]`) |
| `binding` | `{ value, set(value) }`, the bound value (fields only) |
| `trigger(done)` | Fires the boundary event; `done()` runs once BAW has handled it (actions only) |
| `fire(event, ...args)` | Runs one of the view's event handlers and returns its result |
| `preview` | `true` in Coach Designer's preview, where nothing may fire, register or change the page |

The widget host already does the shared work, so the component does none of it:
- It applies `tabIndex` to every input, select, textarea and button the widget draws.
- It runs `eventON_LOAD` once the widget is drawn, `eventON_CHANGE` when the binding changes, and `eventON_FOCUS`, `eventON_BLUR` and `eventON_INPUT` from the DOM. It also runs `eventON_BOUNDARYEVT` once `trigger` is done.
- It adds the `me` methods (getData, setData, label, help, visibility, the placeholder when there is an `example` option, and the contract's `accessor`).

The component fires only `eventON_CLICK`, and only on an action. Wrap every part of the widget in Carbon's styles, as the stock widgets do.

### Field

The shared helper `fieldWidget` gives a field its label, help text, REQUIRED, READONLY, page validation, error message and read-only view. You write only the input:

```jsx
// Yes/No Toggle: a Carbon switch bound to one Boolean. Off is a valid "No", so REQUIRED is ignored
// (unlike Checkbox, where REQUIRED means "must be ticked").
import { Toggle } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';
import { fieldWidget } from './field-widget.js';

// Carbon's Toggle has no helper text of its own, so the field's help text goes below it in Carbon's helper style.
function ToggleInput({ id, field, binding, readOnly }) {
  return (
    <div className="pp--form-item">
      <Toggle id={id} labelText={field.label} toggled={!!binding.value} labelA={field.offText || 'No'} labelB={field.onText || 'Yes'}
        readOnly={readOnly} onToggle={(on) => binding.set(on)} />
      {field.help && <div className="pp--form__helper-text">{field.help}</div>}
    </div>
  );
}

registerWidget('toggle', fieldWidget('toggle', {
  Input: ToggleInput,
  display: (field, value) => (value ? field.onText || 'Yes' : field.offText || 'No'),
  isEmpty: () => false,
}));
```

- `Input` gets `{ id, field, binding, validity, readOnly }`.
  - `binding.value` reads and `binding.set(value)` writes.
  - `validity` is `{ invalid, invalidText }`. Pass it on only when the Carbon component takes those props (Toggle does not).
  - `field.label` is the label and `field.help` the help text. Show both, because the helper does not draw them around a custom input.
  - Every option the contract declares reaches `field` under its own name (`field.onText`). `field.example` is the placeholder.
- A choice field declares an `options` option (`"type": "NameValuePair", "list": true, "group": "Items"`). It then reads the choices as `field.options`, a list of `{ value, label }`.
- `display(field, value)` returns the text that READONLY shows.
- `isEmpty(field, value)` is required: it decides when REQUIRED fails. If your widget's rule differs from the stock widget of the same type, say so in the file's header comment, as the toggle does.
- `validate(field, value)` is optional. It runs after REQUIRED and the pattern, and returns an error message or `null`. Import `rangeError` from `./field-widget.js` for `min` and `max` on a number, or `dateRangeError` for `startDate` and `endDate` on a date. For anything else, write your own; use `field.message` when the author set one.

### Action

```jsx
// Link Action: a Carbon link that fires the view's boundary event, for a quiet "Skip" or "Save for later".
import { useState } from 'react';
import { Link } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';
import { buttonLabel } from '../components.jsx';
import { page, reveal } from '../page-registry.js';

function LinkAction({ label, options, trigger, fire, preview }) {
  const [busy, setBusy] = useState(false);
  const press = (event) => {
    event.preventDefault();
    if (preview || busy) return;
    if (fire('eventON_CLICK') === false) return; // the author's click handler cancelled the press
    if (options.validate === true || options.validate === 'true') {
      const errors = page.validateAll();
      if (errors.length) { reveal(errors[0].element); return; }
    }
    setBusy(true);
    trigger(() => setBusy(false));
  };
  return <div className="pp-actions"><Link href="#" onClick={press} disabled={busy}>{buttonLabel(label || 'Link')}</Link></div>;
}

registerWidget('link', LinkAction);
```

- Run `fire('eventON_CLICK')` first, and stop when it returns `false`.
- Then validate the page, when the widget validates. Decide whether that is the default: Button validates by default only when primary.
- Then call `trigger(done)` and take no more presses until `done` runs.
- Draw a `button` or an `a` element: the check presses the first one.

### Display

```jsx
// Notice: a Carbon inline notification with a title and a message, for a note authors place on a coach.
import { InlineNotification } from '@carbon/react';
import { registerWidget } from '../runtime.jsx';

// A preview has no options set yet, so it shows a sample title: every preview must draw some text.
function NoticeWidget({ options, preview }) {
  const title = options.title || (preview ? 'Notice' : '');
  return <InlineNotification kind={options.tone || 'info'} title={title} subtitle={options.message || ''} hideCloseButton lowContrast />;
}

registerWidget('notice', NoticeWidget);
```

- Read the page's state from `page` in `'../page-registry.js'`, with `useSyncExternalStore(page.subscribe, () => page.theme)` (or `page.errors`).
- In a preview the page has no state, so show sample content when `preview` is true, as Error Summary does. A preview must draw some text.

### Page-level

Copy `theme.jsx`:
- Do the widget's work in a `useEffect` that returns early when `preview` is true, and undo it in the effect's cleanup.
- Return `null` on the page. In a preview, return `<div className="pp-widget-marker">Name</div>` so the author can find and select it.
- Never use `document.getElementById`. A page-level widget may touch `document.body`, as Theme does.

## 3. Write the contract entry

Add one entry at the end of the `widgets` array in `coach-ui/widgets/modernizer-widgets.json`. Copy the closest entry of your kind and edit no other entry. The keys are:

| Key | What to write |
|---|---|
| `kind`, `view`, `binding`, `label`, `boundary` | As decided in step 1 |
| `options` | Each option has a `name`, a `label`, a `type` (a binding type, or `NameValuePair`), `"list": true` for a list, and a `group`. The group is one of these: `Behavior` (what it does and checks: `tabIndex`, `message`, `min`, `max`, `example`, `validate`), `Items` (the choices, `options`) or `Appearance` (how it looks: texts, `kind`, `height`) |
| `events` | `{ event: [argument names] }`, from the table below |
| `accessor` | `[getter, setter]`, the names a handler calls on `me` for the value, from the table below. Leave it out on display and page-level widgets |
| `preview` | `{ "value": ... }`, the value a Coach Designer preview shows (`null` when it binds nothing) |
| `tags` | One of Coach Designer's categories (`Input`, `Informational`, `Layout`, `Operational`, `Chart`), plus `Basic` or `Advanced` as the other entries use |

Use the UI Toolkit's name for an option the UI Toolkit also has. The modernizer then carries the old control's value over, and authors know the name. The names are `tabIndex`, `selectAll`, `height`, `decimalPlaces`, `startDate`, `endDate`, and `example` for a placeholder. Use `message` for the author's own error message, and `options` for a choice list. Give every field and every action a `tabIndex` option (`Integer`, `Behavior`).

| Kind | `events` | `accessor` |
|---|---|---|
| Field you type into (String, Integer, Decimal) | `eventON_LOAD: []`, `eventON_CHANGE`, `eventON_FOCUS: []`, `eventON_BLUR: []`, `eventON_INPUT: ["current", "potential", "selection", "type"]` | String: `getText`, `setText`. Number: `getValue`, `setValue` |
| Field you pick with (Boolean, Date, a choice) | `eventON_LOAD: []`, `eventON_CHANGE`, `eventON_FOCUS: []`, `eventON_BLUR: []` | Boolean: `isChecked`, `setChecked`. Date: `getDate`, `setDate`. Choice: `getSelectedItem`, `setSelectedItem` |
| Action | `eventON_LOAD: []`, `eventON_CLICK: []`, `eventON_BOUNDARYEVT: ["status"]` | `getText`, `setText` (they read and write the label) |
| Display, page-level | `eventON_LOAD: []` | none |

`eventON_CHANGE` takes the arguments the UI Toolkit names for the same value:
- a String: `["newText", "oldText"]`;
- a number or a Boolean: `["newValue", "oldValue"]`;
- a Date or a choice: `["newVal", "oldVal"]`.

Use only the events in the contract's top-level `events`.

## 4. Write the icon, and the styles when needed

1. `coach-ui/widgets/icons/<kind>.svg`, drawn like the other icons:
   - `width` and `height` 16, `viewBox="0 0 16 16"`;
   - Carbon blue `#0f62fe` for the main shape, `#fff` or `#161616` for details;
   - strokes about 1.5 wide, filled shapes where the stock icons use them, no text.
2. `coach-ui/src/widgets/<kind>.scss`, only when the Carbon component is not one the shared styles include. Those are Button, Checkbox, TextInput, TextArea, DatePicker, Tabs, Tile, Notification, ProgressIndicator, NumberInput, Select, RadioButton and the form styles. The file is one line, for example `@use '@carbon/react/scss/components/toggle';` or `@use '@carbon/react/scss/components/link';`. Without it the component renders unstyled.

No other list, map or shared file needs editing. The build, the check, the toolkit, the inspector and the modernizer read the contract and the widget folder.

## 5. Check, build and install a new MDW snapshot

1. Call `list_snapshots("MDW")` and take the next name after the newest one. Never reuse a name: BAW silently keeps the old content of an existing snapshot name.
2. Call `build_widget_toolkit("modernizer", <new snapshot>)`. It compiles the widgets and checks every contract widget in a browser before it builds anything:
   - The entry is complete: every option in a group, the events its kind needs and in the catalog, the accessor of a widget with a binding, and the icon file.
   - It renders at runtime and as a Coach Designer preview, its Carbon component has styles, and no page error occurs.
   - Its `eventON_LOAD` runs with `me`, and its accessor writes and reads the value (or the label). A field fires `eventON_CHANGE`, focus, blur and input. An action, once pressed, fires `eventON_CLICK`, the boundary event and `eventON_BOUNDARYEVT`.
   - Every option and event shows in the built view's Configuration groups and Events tab.

   When a check fails, it builds no toolkit and returns the failures with the widget's kind: fix the widget and call it again. Its `checks` lists what passed. It returns `work/MDW-<snapshot>.twx`.
3. Call `install_app` with that `.twx` (the user approves). Continue only when `"ok": true`. With no BAW server, give the user the `.twx` and its import steps.

The check does not test what is particular to the new widget. Check that with `test_service` and its screenshots of the modernized app. With `fill`, it turns on every switch that is off and ticks every checkbox on screen. A field on a tab that is not open is reached through its group's Preview service.

## 6. Use it

- **Field:** in the coach spec from `inspect_coaches`, set `"type"` to the new kind on every field the plan assigned to it, and keep each field's other values. A field of a group is set once, in the spec's `"groups"`; every placement follows.
- **Action:** set `"type"` to the new kind on each button the plan assigned to it, in the coach's `"buttons"`. The button keeps its `viewId`, `to`, events and the options the new widget declares (`kind`, `validate`, `tabIndex`).
- **Display and page-level:** the modernizer places only Theme, Header and Error Summary. A new display or page-level widget is in the palette for authors to place in Coach Designer. Say so in the report.

Then continue the coach-modernize skill from its toolkit step, passing this MDW snapshot as `toolkit_snapshot` to `modernize_app`. A later `inspect_coaches` reads the field or button back with the same `"type"`.

## 7. Fallback

If the widget check fails twice, do not stall:
1. Set the fields and buttons back to their stock kind: Checkbox for a Boolean, Text Field for a String, Button for an action.
2. Delete the new component, icon, styles and contract entry.
3. Continue the modernization with the stock widget, and say in the report that the widget was not done and why.

## Pitfalls

- Never `document.getElementById`: BAW rewrites IDs. Stay inside the widget's own element.
- Write sizes in `rem` as the other widgets do. The build converts `rem` to px for BAW's 62.5% root font size.
- In a preview, fire nothing, register nothing and leave the page alone. Show what the author is configuring.
- The palette shows the contract's `view` name and the icon, so choose a name an author will recognise.
- Verify the widget in Coach Designer's preview, and with `test_service` on the modernized app, before you report done.

## Report

List these:
- the files you added and the one added contract entry (you added only new files and changed only `modernizer-widgets.json`);
- the widget's kind (field, action, display or page-level);
- the MDW snapshot, and what `checks` reported;
- the fields or buttons that use it, or that authors place it themselves;
- whether the fallback was taken.
