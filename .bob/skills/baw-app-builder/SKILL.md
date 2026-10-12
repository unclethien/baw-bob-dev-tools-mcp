---
name: baw-app-builder
description: Build a complete, installable BAW process app (.twx) from a written requirement - business object, multi-step coaches (or one tabbed screen) with bound fields, Back/Next/Submit wiring, review and confirmation screens - by writing an app spec JSON, then build, install and test it with the baw-dev-tools MCP tools. Use when the user asks to create, build or generate a new BAW app, form, workflow screens or coaches from a description, and wants it running on the server without Process Designer work.
---

# BAW app builder

You design the app and write **one JSON spec**. The baw-dev-tools MCP tools build, install and test it. Never write or edit TWX, BPMN or coach XML yourself.

## Steps

1. **Get the theme file.** Every app needs one. Follow the app-theme skill: reuse a theme file the user names, or ask them to describe the look and write `work/<name>.theme.json`. To build from a screenshot or mockup, use the screenshot-to-app skill instead: it reads the theme and the layout from the image.

2. **Write the spec** at `work/<ACRONYM>.app.json`. Copy the shape of `app-specs/example-equipment-request.json` (simple steps), `app-specs/example-supplier-registration.json` (sections, columns, dropdowns, radio groups, required fields) or `app-specs/example-themed-quote.json` (tabs, banner, placed columns, field icons, Cancel):

   | Key | Rule |
   |---|---|
   | `app.name`, `app.acronym` | New app: name starts with "ZZ ", acronym 2-8 upper-case letters or digits, not used on the server (`list_apps`; without a server, ask the user) |
   | `app.snapshot` | `1.0.0` for a new app |
   | `businessObject.name` / `.variable` | e.g. `LeaveRequest` / `leave` (JavaScript identifiers) |
   | `service.name` | What users see, e.g. "Leave Request" |
   | `layout` | `"steps"` (default): one screen per step with Back / Next. `"tabs"`: one screen with a tab per step, the user moves freely between tabs, then Next goes to the review |
   | `form` | Only for `"tabs"`: optional `title`, `intro`, `nextLabel` and `cancelLabel` of the tabbed screen (default title: `service.name`) |
   | `steps[]` | In order: `title`, optional `intro` (`"steps"` layout only), optional `nextLabel` / `backLabel` / `cancelLabel` (button text; Cancel ends the service), and either `fields[]` (one panel titled like the step, optional `columns` and `widths`) or `sections[]`. With `"tabs"` each step is one tab |
   | `sections[]` | Titled panels within a step: `title`, optional `intro`, `columns` (1 to 6; fields fill left to right, row by row, unless every field has a `column`), optional `widths` (one relative width per column, e.g. `[1, 1.6, 1]`) and `fields[]` |
   | `fields[]` | `name` (identifier, unique across all steps), `label`, `type`: `String`, `Text Area`, `Date`, `Boolean`, `Integer`, `Decimal`, `Select` (dropdown) or `Radio`. Optional: `required` (shows the required marker), `help` (help icon with this text), `wide` (full width in a multi-column section), `column` (1, 2, …: the column it sits in, top to bottom in list order), `icon` (when the theme file sets `fieldIcons`: `text`, `file`, `user`, `users`, `calendar`, `list`, `options`, `check`, `hash`, `search`, `id`, `mail`, `phone`, `building`, `dollar`, `info`, `briefcase`) |
   | `options` | For `Select` and `Radio`: a list of strings, or of `{ "value": ..., "label": ... }` when the stored value differs from the text shown |
   | `review` | `{ "title": ..., "submitLabel": ... }` for a read-only review screen, or `false` |
   | `confirmation` | Optional: `title`, `message`, `referencePrefix`, `showFields` (field names) |
   | `theme` | Required: path of the theme file from step 1, e.g. `"work/acme.theme.json"` |
   | `banner` | Optional header strip in the theme's `primary` instead of the plain title: `title` (default: the coach title) and `text` (a short greeting or note at the right). The product name and logo come from the theme file's `banner` |

   Use only the fields the requirement names. A yes/no question is `Boolean`; a choice from a short fixed list is `Radio` (up to about 4 options) or `Select`; long free text is `Text Area`; money and percentages are `Decimal`; counts are `Integer`. Address parts are separate `String` fields. Group more than about six fields into titled `sections`.

3. **Build:** `create_app` with the spec path. It validates the spec and its theme file first and lists every problem; fix them and call it again. If the app already exists on the server, the build becomes a new snapshot of it, so bump `app.snapshot` for every change.

   The package comes from a built-in template, so no app has to be downloaded first. For a **new** app on a server, ask the user once which installed app to match (show them `list_apps`): any app works, its export only supplies the server's BAW build and toolkit versions. Pass its acronym as `base`, or no `base` to use the built-in template (BAW 26.0.0). An app that already exists is its own base.

4. **Check the flow:** `inspect_coaches` on the returned `.twx`. Every step must show its fields and a button leading to the next coach. With `"tabs"` the first coach shows one section per tab and `sectionStyle: "tabs"`.

5. **Install:** `install_app`. Continue only when `"ok": true`.

6. **Test:** `test_service` with the app acronym and `service.name` (`fill: false` for the legacy screens). `"ok": true` means every coach rendered and every button moved on. Look at the screenshots.

7. **Report** the app, acronym, snapshot, the theme file, the run URL (`list_services`), the steps and field counts, and the screenshot folder.

### Without a BAW server

When `create_app` returns `install`, no server is configured: the server tools (`list_apps`, `install_app`, `test_service`, ...) are not available. Do steps 1 to 4, then stop and give the user:

- the `.twx` path and the import steps from `install`;
- the app name, acronym and snapshot, and that the snapshot name must be new in that app;
- to add a snapshot to an app they already have, rebuild with `base` set to a `.twx` they exported from it (same acronym);
- what to check when they run the service: each step, the buttons, the review and the confirmation.

To give the app a React + Carbon UI next, continue with the coach-inventory skill (step 4 already wrote the coach spec), then the coach-modernize skill.

## When something fails

| Symptom | Action |
|---|---|
| `Invalid app spec` | Fix each listed problem in the spec or its theme file. No theme file: ask the user for the look (app-theme skill) |
| `Snapshot … already exists` | Bump `app.snapshot` |
| `No BAW server is configured` | Continue without a server (see above) |
| Install fails | Read the error; an acronym already in use by another app means pick another one |
| `stuck ...` in the test report | Report it with the screenshot; it is a generator bug, do not patch XML |
| `no coach rendered` | Report it with `00-no-coach.png` and the page errors |
