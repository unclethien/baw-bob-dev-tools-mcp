---
name: coach-modernize
description: Give a BAW app's client-side human services a React + Carbon UI from an approved coach spec - generate a modernized copy of each service whose coaches are drag-and-drop layouts of Modernizer Widgets (or a hand-written React screen where one is needed), in the app's theme file, as a new snapshot, then install and test every copy in a browser - using the baw-dev-tools MCP tools. Use after the coach-inventory spec is approved, or when the user asks to modernize, re-theme or verify an app's coaches.
---

# Coach modernize

Inputs: an app `.twx` in `work/` and an **approved** coach spec from `inspect_coaches` whose `"theme"` names the app's theme file. If the spec has not been reviewed, use the coach-inventory skill first; without a theme file, use the app-theme skill. When the user gives a picture of the new look, write a new theme file from it with the app-theme skill, set the coach spec's `"theme"` to that file, and follow the picture's grouping and button placement in the spec's sections (or in a hand-written screen when the widgets cannot match it).

Each modernized coach is a layout of Modernizer Widgets (Theme, Header, Error Summary, one field widget per field, Button) inside UI Toolkit Panels, a Tab Section or a Horizontal Layout for the buttons. Authors can open it in Coach Designer and drag, drop, relabel and rearrange the widgets. A coach with `"screen"` in the spec shows a hand-written React screen instead, as one block.

## Steps

1. **Hand-written screens (optional).** By default no coach has `screen`, and every coach is built from widgets out of its spec entry. Write a screen with the react-coach-screen skill only when the user asks for a screen designed for a coach, or when the design needs a layout, component or behaviour the spec cannot express; then set `"screen": "<name>"` on that coach and run `build_screens` until it compiles. Tell the user such a coach is one block in Coach Designer, not a drag-and-drop layout.

2. **Choose the target.** The output is a new snapshot of the same app. When you did not create the app in this task, tell the user the snapshot will be added to it and install only after they approve; to keep the original app untouched, build or copy it as a new app with the user first.

3. **Generate:** the widget layouts need an installed snapshot of the Modernizer Widgets (`MDW`) toolkit: pass the newest snapshot that `list_snapshots("MDW")` shows and that has its `work/MDW-<snapshot>.twx`. When there is none, or the widgets changed since it was built, call `build_widget_toolkit("modernizer", <new snapshot>)` and `install_app` it first. Without a BAW server, use the newest `work/MDW-*.twx` or build one; the user imports it before the app. Once installed, every app on the server can use that snapshot. If the plan adds a widget, follow the modernizer-widget skill first, and build a new snapshot. Then `modernize_app` with the `.twx`, the coach spec, a snapshot name not used in the app (`list_snapshots`) and `toolkit_snapshot`. It adds `<service> (Modernized)` next to each legacy service, styled by the spec's theme file: colours, font, shape, width, button placement, and the header's logo and product name. To change the look, edit the theme file and generate again with a new snapshot.

4. **Install:** `install_app` with the returned `.twx`. Continue only when `"ok": true`. If `modernize_app` returned `install`, there is no BAW server: stop, give the user the `.twx` and its import steps, and list the services to check by hand.

5. **Test every copy:** `test_service` for each `<service> (Modernized)` with `snapshot` set and `fill: true`. It walks each screen, types sample values (each field's `example`), presses the primary button and screenshots every step.

6. **Look at the screenshots.** Check titles, grouping, labels, validation, the summary screens and the theme's look against your design. Fix the spec (or a screen, then `build_screens`) and repeat from step 3 with a new snapshot.

7. **Report** the app and snapshot, the MDW snapshot, each service with its result and steps, the screenshot folders, any screens you wrote, and the spec's native and dropped items. Mention that the coaches open in Coach Designer as editable layouts. A change to an existing widget (for every app) is code in `coach-ui/`: hand it to Agent mode. Adding a new widget stays here, with the modernizer-widget skill.

## When a test fails

| Report says | Likely cause | Action |
|---|---|---|
| `stuck … fields need attention` or your own error banner | Validation blocked the press | Give the fields `example` values that pass your rules |
| `stuck …` with no alert | The screen fired the wrong button, or none | Fire `spec.buttons[].viewId`; check the button's `to` in the spec |
| `no coach rendered` / page errors mention your screen | The screen threw while rendering | Read the error, fix the screen, `build_screens` |
| `Invalid theme` from `modernize_app` | The spec has no `"theme"`, or the theme file has a problem | Fix the listed problem (app-theme skill) |
| `pass toolkit_snapshot` or `is not installed` from `modernize_app` | No Modernizer Widgets snapshot given, or not installed yet | `build_widget_toolkit`, `install_app`, then `modernize_app` with `toolkit_snapshot` |
| `Screens not in the bundle` from `modernize_app` | Registered name differs from `"screen"` | Make the `registerScreen` name, the file name and `"screen"` match |
