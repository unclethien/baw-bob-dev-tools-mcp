---
name: modernizer-widget
description: Add one new field widget to the Modernizer Widgets (MDW) toolkit while modernizing an app - write its React + Carbon component, its entry in the widget contract and its palette icon, check it offline, build and install a new MDW snapshot, and use it in the coach spec - with the baw-dev-tools MCP tools. Use only when the approved modernization plan names a new widget that no existing Modernizer Widget can replace (for example a Yes/No Toggle). Never use it to change or remove an existing widget; that is a code change for Agent mode.
---

# Modernizer widget

A new Modernizer Widget is one field widget that binds one System Data value. Authors then find it in Coach Designer's palette like the stock widgets, and the modernized coaches use it. You add it only when the approved plan names it.

## 1. Decide

- Add a widget only when no widget in `coach-ui/widgets/modernizer-widgets.json` does the job. Read the contract first.
- Never edit or remove an existing widget, its file, or its contract entry. When the request is to change one, stop and hand it to Agent mode.
- A widget writes one value only: a String, Integer, Decimal, Boolean or Date. One that needs several values or a business object is out of scope; use a stock widget and say so.
- Settle: the `kind` (lower-case, unique, the file name), the palette name (`view`), the binding type, the options authors can set, a preview value, and the tags.

Example: kind `toggle`, view "Toggle", binding `Boolean`, options `onText` and `offText` (default "Yes" and "No"), tags `Basic` and `Input`.

## 2. Copy the closest widget

The example below is complete for a one-value widget; read `coach-ui/src/components/fields/checkbox-field.jsx` (an input) and `coach-ui/src/widgets/field-widget.js` (the shared helper `fieldWidget`) only when yours needs more, and no other platform file. The build picks up every `coach-ui/src/widgets/*.jsx` by itself, so the new file needs no import anywhere. A field widget gets its label, help text, REQUIRED / READONLY / HIDDEN handling, validation and error message from the shared helper, so you write only the input:

```jsx
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

- `Input` gets `{ id, field, binding, validity, readOnly }`. `binding.value` reads, `binding.set(value)` writes. `validity` is `{ invalid, invalidText }`; pass it on only when the Carbon component takes those props (Toggle does not).
- `field.help` is the help text and `field.label` the label. Show both: the helper passes them on but does not draw them around a custom input.
- `display(field, value)` returns the text READONLY shows.
- `isEmpty(field, value)` is required: it decides when REQUIRED fails. A Boolean is empty as `false` or `null`. A toggle ignores REQUIRED because off is a valid "No", so it returns `false`. Say so in the header comment of the component file, since it differs from Checkbox, where REQUIRED means "must be ticked".
- Every option the contract declares for the kind (`onText`, `offText`) reaches the input on `field` under its contract name, the way `min` and `max` do for Number Field.

## 3. Write the files

1. `coach-ui/src/widgets/<kind>.jsx`, as above.
2. One entry added at the end of the `widgets` array in `coach-ui/widgets/modernizer-widgets.json`, copied from the closest entry: `kind`, `view`, `binding`, `label`, `options` (`name`, `label`, `type`, and `list` for a list), `boundary` (false for fields), `preview` (`value`) and `tags`. The tags come from Coach Designer's categories (Input, Informational, Layout, Operational, Chart) plus `Basic` or `Advanced` as the other entries use. Edit no other entry.
3. `coach-ui/widgets/icons/<kind>.svg`, like the other icons: `width` and `height` 16, `viewBox="0 0 16 16"`, Carbon blue `#0f62fe` for the main shape, `#fff` or `#161616` for details, strokes about 1.5 wide, filled shapes where the stock icons use them, no text. For the toggle: a blue rounded track with a white knob on the right.
4. Only when the Carbon component is not one the stock widgets use (they use Button, Checkbox, TextInput, TextArea, DatePicker, NumberInput, Select, RadioButton, Tabs, Tile, Notification, ProgressIndicator): `coach-ui/src/widgets/<kind>.scss` with its Carbon styles, for example `@use '@carbon/react/scss/components/toggle';`. Without it the component renders unstyled.

No other list, map or shared file needs editing; the build and the check read the contract and the widget folder.

## 4. Check, build and install a new MDW snapshot

1. `list_snapshots("MDW")`. Take the next name after the newest one. Never reuse a name: BAW silently keeps the old content of an existing snapshot name.
2. `build_widget_toolkit("modernizer", <new snapshot>)`. It compiles the widgets, then checks every contract widget in a browser before it builds anything: each renders at runtime and as a Coach Designer preview, its Carbon component has styles, and no page error occurs (READONLY, HIDDEN and REQUIRED come from the shared helper, checked on the stock fields). When a check fails it builds no toolkit and returns the failures: fix the widget and call it again. Its `checks` lists what passed. It returns `work/MDW-<snapshot>.twx`.
3. `install_app` with that `.twx` (the user approves). Continue only when `"ok": true`. With no BAW server, give the user the `.twx` and its import steps.

The check does not test what is particular to the new widget. Check its own behaviour in the modernized app with `test_service` and its screenshots: with `fill` it turns on every switch that is off and ticks every checkbox on screen, so for a toggle the review shows the on text. A field on a tab that is not open is reached through its group's Preview service.

## 5. Use it

In the coach spec from `inspect_coaches`, set `"type"` to the new kind on every field the plan assigned to it, and keep each field's other values. A field of a group is set once, in the spec's `"groups"`; every placement follows. Continue the coach-modernize skill from its toolkit step, passing this MDW snapshot as `toolkit_snapshot` to `modernize_app`. A later `inspect_coaches` reads the field back with the same `"type"`.

## 6. Fallback

If the widget check fails twice, do not stall. Set the fields back to their stock kind (Checkbox for a Boolean), delete the new component, icon and contract entry, continue the modernization with the stock widget, and say in the report that the widget was not done and why.

## Pitfalls

- Never `document.getElementById`: BAW rewrites IDs. Stay inside the widget's own element.
- Write sizes in `rem` as the other widgets do. The build converts `rem` to px for BAW's 62.5% root font size.
- The palette shows the contract's `view` name and the icon, so choose a name an author will recognise.
- Verify the widget in Coach Designer's preview, and with `test_service` on the modernized app, before you report done.

## Report

List the files you added and the one added contract entry (you added only new files and changed only `modernizer-widgets.json`), the MDW snapshot, what `checks` reported, which fields use the widget, and whether the fallback was taken.
