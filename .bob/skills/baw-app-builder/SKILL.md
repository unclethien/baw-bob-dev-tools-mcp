---
name: baw-app-builder
description: Build a complete, installable BAW process app (.twx) from a written requirement - business object, multi-step coaches (or one tabbed screen) with bound fields, Back/Next/Submit wiring, review and confirmation screens - by writing an app spec JSON, then build, install and test it with the baw-dev-tools MCP tools. Optionally adds a workflow (BPD) with lanes and an approval task with Send Back, editable in Business Automation Studio. Use when the user asks to create, build or generate a new BAW app, form, workflow, approval process, workflow screens or coaches from a description, and wants it running on the server without Process Designer work.
---

# BAW app builder

You design the app and write **one JSON spec**. The baw-dev-tools MCP tools build, install and test it. Never write or edit TWX, BPMN or coach XML yourself.

**STOP RULES:** stop twice and wait for the user: before building (step 3) and before installing (step 6). Skip a stop only when the user said to go ahead without it.

## Steps

1. **Get the theme file.** Every app needs one. Follow the app-theme skill: reuse a theme file the user names, or ask them to describe the look and write `work/<name>.theme.json`. To build from a screenshot or mockup, use the screenshot-to-app skill instead: it reads the theme and the layout from the image.

2. **Write the spec** at `work/<ACRONYM>.app.json`. Copy the shape of `app-specs/example-equipment-request.json` (simple steps), `app-specs/example-supplier-registration.json` (sections, columns, dropdowns, radio groups, required fields) or `app-specs/example-themed-quote.json` (tabs, banner, placed columns, field icons, Cancel):

   | Key | Rule |
   |---|---|
   | `app.name`, `app.acronym` | New app: any name; acronym 2-8 upper-case letters or digits, not used on the server (`list_apps`; without a server, ask the user) |
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
   | `process` | Optional workflow: `name` (required), `formTask` (`name`, `lane`), and `approval` (`name`, `lane`, `intro`, `approveLabel`, `returnLabel`, `commentsLabel`; `{}` for the defaults). The form becomes the first task; the approval task shows every field read-only with comments and Approve / Send Back, and Send Back returns the work to the form. The approval adds the fields `decision` and `reviewComments`, so do not use those names. Add it when the requirement has a hand-off between people (submit for review, approve, send back) |
   | `banner` | Optional header strip in the theme's `primary` instead of the plain title: `title` (default: the coach title) and `text` (a short greeting or note at the right). The product name and logo come from the theme file's `banner` |

   Use only the fields the requirement names. A yes/no question is `Boolean`; a choice from a short fixed list is `Radio` (up to about 4 options) or `Select`; long free text is `Text Area`; money and percentages are `Decimal`; counts are `Integer`. Address parts are separate `String` fields. Group more than about six fields into titled `sections`.

3. **STOP: approve the design.** Do not call `create_app` yet. Show the user:
   - the app name, acronym and snapshot;
   - the theme file and its main values (colours, font, shape, product name, logo);
   - each step or tab with its sections, fields (label and type), required fields and buttons, then the review and confirmation;
   - with a `process`: the lanes, the tasks in each lane, and the approval buttons, drawn as `Start → <form task> (<lane>) → <approval task> (<lane>) → Approved? → End`, with Send Back to the form;
   - your assumptions, such as dropdown options you chose and help texts you wrote;
   - for a **new** app on a server, which installed app the package should match (show them `list_apps`): any app works, since its export only supplies the server's BAW build and toolkit versions. Or the built-in template (BAW 26.0.0). An app that already exists is its own base.

   Then ask:
   > Approve this design, or tell me what to change. When approved, I will build the app.

   Change the spec or the theme file as asked and show the changes again, until the user approves.

4. **Build:** the coaches are built from App Builder Widgets, so the server needs a snapshot of the ABW toolkit: if `list_snapshots("ABW")` shows none built from the current widgets, call `build_widget_toolkit("builder", <new snapshot>)` and `install_app` it. Then `create_app` with the spec path, `toolkit_snapshot`, and the chosen app's acronym as `base` (no `base` for the built-in template). It validates the spec and its theme file first and lists every problem; fix them and call it again. If the app already exists on the server, the build becomes a new snapshot of it, so bump `app.snapshot` for every change.

5. **Check the flow:** `inspect_coaches` on the returned `.twx`. Every step must show its fields and a button leading to the next coach. With `"tabs"` the first coach shows one section per tab and `sectionStyle: "tabs"`.

6. **STOP: ask before importing.** Do not call `install_app` yet. Tell the user the `.twx` path, the app, acronym and snapshot, and what `inspect_coaches` shows (one line per coach), then ask:
   > The app is built. Do you want me to import it into BAW now?

   If the user says no, stop and give them the `.twx` path and the import steps (Workflow Center, Process Apps, Import), so they can import it later.

7. **Install:** `install_app`. Continue only when `"ok": true`.

8. **Test:** `test_service` with the app acronym and `service.name` (`fill: false` for the legacy screens). `"ok": true` means every coach rendered and every button moved on. Look at the screenshots.
   With a `process`, also run `test_process` with `process.name` and `press: ["<returnLabel>"]`: it starts the workflow and works each task in a browser, sending the work back once, then approving it. `"ok": true` means the workflow completed and every task's screens rendered. Look at the screenshots of each task.

9. **Report** the app, acronym, snapshot, the theme file, the run URL (`list_services`), the steps and field counts, and the screenshot folder. With a `process`: that users start it from Workplace, and that the diagram opens in Business Automation Studio (the app, then Processes) for changes such as more steps or a team per lane.

**Later changes** (a new field, another look, a fix after testing): show what will change and wait for approval before building. Once the user has said yes to importing this app, that one approval covers building and importing the new snapshot; otherwise ask again before importing.

### Without a BAW server

When `create_app` returns `install`, no server is configured: the server tools (`list_apps`, `install_app`, `test_service`, ...) are not available. Do steps 1 to 5 (with the stop at step 3), then stop and give the user:

- the `.twx` path and the import steps from `install`;
- the app name, acronym and snapshot, and that the snapshot name must be new in that app;
- to add a snapshot to an app they already have, rebuild with `base` set to a `.twx` they exported from it (same acronym);
- what to check when they run the service: each step, the buttons, the review and the confirmation.

When the user asks for a React + Carbon UI next, call `switch_mode` to `baw-coach-modernizer` without asking, with the app, acronym, snapshot, `.twx`, coach spec (step 5 wrote it) and theme file in the reason. That mode writes the screens.

## When something fails

| Symptom | Action |
|---|---|
| `Invalid app spec` | Fix each listed problem in the spec or its theme file. No theme file: ask the user for the look (app-theme skill) |
| `Snapshot … already exists` | Bump `app.snapshot` |
| `No BAW server is configured` | Continue without a server (see above) |
| Install fails | Read the error; an acronym already in use by another app means pick another one |
| `test_process`: `No startable process` | Check `process.name` against the names it lists, and that the snapshot is installed |
| `test_process`: state not `Completed`, or `unpressed` not empty | A button in `press` never appeared: check its text against `approval.returnLabel`. Otherwise report the task and its screenshots |
| `stuck ...` in the test report | Report it with the screenshot; it is a generator bug, do not patch XML |
| `no coach rendered` | Report it with `00-no-coach.png` and the page errors |
