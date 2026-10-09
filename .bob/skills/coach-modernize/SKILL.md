---
name: coach-modernize
description: Give a BAW app's client-side human services a React + Carbon UI from an approved coach spec - write a React screen per coach, generate the modernized copies (brand and carbon themes) as a new snapshot, install and test every copy in a browser - using the baw-dev-tools MCP tools. Use after the coach-inventory spec is approved, or when the user asks to modernize, re-theme or verify an app's coaches.
---

# Coach modernize

Inputs: an app `.twx` in `work/` and an **approved** coach spec from `inspect_coaches`. If the spec has not been reviewed, use the coach-inventory skill first.

## Steps

1. **Write the screens** with the react-coach-screen skill: one screen per coach of every service marked `"modernize": true`, then `"screen": "<name>"` on each coach in the spec. Run `build_screens` until it compiles. A coach without `screen` uses the generic form (fine for a quick pass when the user asks for one).

2. **Choose the target.** The output is a new snapshot of the same app, so the app must be a ZZ app (`install_app` refuses anything else). To modernize a non-ZZ app, first build or copy it as a ZZ app with the user.

3. **Generate:** `modernize_app` with the `.twx`, the coach spec and a snapshot name not used in the app (`list_snapshots`). It adds `<service> (Modernized)` (brand theme) and `<service> (Modernized - Carbon)` (carbon theme) next to the legacy services.

4. **Install:** `install_app` with the returned `.twx`. Continue only when `"ok": true`. If `modernize_app` returned `install`, there is no BAW server: stop, give the user the `.twx` and its import steps, and list the services to check by hand.

5. **Test every copy:** `test_service` for both services with `snapshot` set and `fill: true`. It walks each screen, types sample values (each field's `example`), presses the primary button and screenshots every step.

6. **Look at the screenshots.** Check titles, grouping, labels, validation and the summary screens against your design. Fix a screen, rebuild and repeat from step 3 with a new snapshot.

7. **Report** the app and snapshot, each service with its result and steps, the screenshot folders, the screens you wrote, and the spec's native and dropped items.

## When a test fails

| Report says | Likely cause | Action |
|---|---|---|
| `stuck … fields need attention` or your own error banner | Validation blocked the press | Give the fields `example` values that pass your rules |
| `stuck …` with no alert | The screen fired the wrong button, or none | Fire `spec.buttons[].viewId`; check the button's `to` in the spec |
| `no coach rendered` / page errors mention your screen | The screen threw while rendering | Read the error, fix the screen, `build_screens` |
| `Screens not in the bundle` from `modernize_app` | Registered name differs from `"screen"` | Make the `registerScreen` name, the file name and `"screen"` match |
