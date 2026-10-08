---
name: baw-app-builder
description: Build a complete, installable BAW process app (.twx) from a written requirement - business object, multi-step coaches (or one tabbed screen) with bound fields, Back/Next/Submit wiring, review and confirmation screens - by writing an app spec JSON, then build, install and test it with the baw-dev-tools MCP tools. Use when the user asks to create, build or generate a new BAW app, form, workflow screens or coaches from a description, and wants it running on the server without Process Designer work.
---

# BAW app builder

You design the app and write **one JSON spec**. The baw-dev-tools MCP tools build, install and test it. Never write or edit TWX, BPMN or coach XML yourself.

## Steps

1. **Write the spec** at `work/<ACRONYM>.app.json`. Copy the shape of `app-specs/example-equipment-request.json` (simple steps) or `app-specs/example-supplier-registration.json` (sections, columns, dropdowns, radio groups, required fields):

   | Key | Rule |
   |---|---|
   | `app.name`, `app.acronym` | New app: name starts with "ZZ ", acronym 2-8 upper-case letters or digits, not used on the server (`list_apps`) |
   | `app.snapshot` | `1.0.0` for a new app |
   | `businessObject.name` / `.variable` | e.g. `LeaveRequest` / `leave` (JavaScript identifiers) |
   | `service.name` | What users see, e.g. "Leave Request" |
   | `layout` | `"steps"` (default): one screen per step with Back / Next. `"tabs"`: one screen with a tab per step, the user moves freely between tabs, then Next goes to the review |
   | `form` | Only for `"tabs"`: optional `title`, `intro` and `nextLabel` of the tabbed screen (default title: `service.name`) |
   | `steps[]` | In order: `title`, optional `intro` (`"steps"` layout only), optional `nextLabel` / `backLabel` (button text), and either `fields[]` (one panel titled like the step, optional `columns`) or `sections[]`. With `"tabs"` each step is one tab |
   | `sections[]` | Titled panels within a step: `title`, optional `intro`, `columns` (1, 2 or 3; fields fill left to right, row by row) and `fields[]` |
   | `fields[]` | `name` (identifier, unique across all steps), `label`, `type`: `String`, `Text Area`, `Date`, `Boolean`, `Integer`, `Decimal`, `Select` (dropdown) or `Radio`. Optional: `required` (shows the required marker), `help` (text under the field), `wide` (full width in a multi-column section) |
   | `options` | For `Select` and `Radio`: a list of strings, or of `{ "value": ..., "label": ... }` when the stored value differs from the text shown |
   | `review` | `{ "title": ..., "submitLabel": ... }` for a read-only review screen, or `false` |
   | `confirmation` | Optional: `title`, `message`, `referencePrefix`, `showFields` (field names) |

   Use only the fields the requirement names. A yes/no question is `Boolean`; a choice from a short fixed list is `Radio` (up to about 4 options) or `Select`; long free text is `Text Area`; money and percentages are `Decimal`; counts are `Integer`. Address parts are separate `String` fields. Group more than about six fields into titled `sections`.

   To build from a screenshot or mockup instead of a written requirement, use the screenshot-to-app skill.

2. **Build:** `create_app` with the spec path. It validates the spec first and lists every problem; fix the spec and call it again. If the app already exists on the server, the build becomes a new snapshot of it, so bump `app.snapshot` for every change.

3. **Check the flow:** `inspect_coaches` on the returned `.twx`. Every step must show its fields and a button leading to the next coach. With `"tabs"` the first coach shows one section per tab and `sectionStyle: "tabs"`.

4. **Install:** `install_app`. Continue only when `"ok": true`.

5. **Test:** `test_service` with the app acronym and `service.name` (`fill: false` for the legacy screens). `"ok": true` means every coach rendered and every button moved on. Look at the screenshots.

6. **Report** the app, acronym, snapshot, the run URL (`list_services`), the steps and field counts, and the screenshot folder.

To give the app a React + Carbon UI next, continue with the coach-inventory skill (step 3 already wrote the coach spec), then the coach-modernize skill.

## When something fails

| Symptom | Action |
|---|---|
| `Invalid app spec` | Fix each listed problem in the spec |
| `Snapshot … already exists` | Bump `app.snapshot` |
| Install fails | Read the error; an acronym already in use by another app means pick another one |
| `stuck ...` in the test report | Report it with the screenshot; it is a generator bug, do not patch XML |
| `no coach rendered` | Report it with `00-no-coach.png` and the page errors |
