# Demo script: coaches you can rearrange

A 75-minute test run of the widget toolkits. IBM Bob builds a small app whose coaches are made of **App Builder Widgets**, then modernizes ZZQI into coaches made of **Modernizer Widgets**. Each time, Bob must build and install the toolkit before the app. Then you open both apps in Coach Designer and drag, drop and relabel the widgets.

**How to read this script.** Each step tells you what to **do**, what to **paste** into Bob, what **Bob does**, and what to **check**. Tick the checks in section 6 as you go; the page remembers them.

---

## 1. Run of show

| Time | Part | What you test |
|---|---|---|
| T−15 | Before you start | Fresh toolkit files, a backup, Bob restarted |
| 00:00 | Opening | What changed: widgets instead of one block |
| 03:00 | The two toolkits | Which widgets, which tool, installed once per server |
| 08:00 | Test 1: App Builder | Toolkit first, then the app, then drag and drop in Coach Designer |
| 35:00 | Test 2: Modernizer | Toolkit first, then ZZQI modernized, then drag and drop, relabel and Required |
| 65:00 | Checks | The scorecard, what to do if it breaks, what to send back |

---

## 2. Before you start (15 min)

1. **Get the code.** Check out `feat/coach-widget-toolkits`. In Bob's MCP panel, restart **baw-dev-tools**. It must show **15 tools**; the new one is `build_widget_toolkit`.
2. **Move the old toolkit file aside.** Bob reuses the newest installed toolkit snapshot that also has its `.twx` in `work/`. `work/MDW-1.0.0.twx` is an early test build, and MDW 1.0.0 is installed, so Bob would reuse it. Move it, so Bob builds a fresh one:
   ```
   mkdir -p work/old && mv work/MDW-1.0.0.twx work/old/
   ```
   `work/` has no `ABW-*.twx`, so Bob builds App Builder Widgets fresh too.
3. **Back up the ZZQI coach spec.** `inspect_coaches` rewrites `work/ZZQI-v1.0.coaches.json`, which holds ZZQI's hand-written screen setup:
   ```
   cp work/ZZQI-v1.0.coaches.json work/old/
   ```
4. **Know the names already taken.** The server has ABW 1.0.0 to 1.0.3, and MDW 0.0.1 to 0.0.6 and 1.0.0 to 1.5.0. Bob must pick a new snapshot name; a refusal saying "already exists" is a safety rule working.
5. **Open the tools.** Pick **🏗️ BAW App Builder** in Bob and allow **Mode** in Bob's auto-approve settings. Open Business Automation Studio in a second browser tab.

---

## 3. Opening (3 min)

**Say.**
- "Until now, a modernized coach was one block. In Coach Designer you could not see inside it, move a field or reuse a part."
- "Bob still works through the same connector, an MCP server, now with 15 tools."[^mcp]
- "Now every coach is a layout of small widgets. They sit in the palette with their own icons, draw a preview on the canvas, and can be dragged, dropped and relabelled like any BAW view."
- "The widgets ship as two toolkits, so every process app on the server can use them."

---

## 4. The two toolkits (5 min)

| Toolkit | Used by | Widgets | Built with |
|---|---|---|---|
| **App Builder Widgets** (`ABW`) | `create_app`, 🏗️ BAW App Builder | Theme, App Header, Section, Review List, Button Bar | BAW markup and plain JavaScript, no framework. The fields inside are UI Toolkit views |
| **Modernizer Widgets** (`MDW`) | `modernize_app`, ✨ BAW Coach Modernizer | Theme, Header, Error Summary, Text Field, Text Area, Number Field, Date Field, Checkbox, Select, Radio Group, Button | React + Carbon, behind a framework-neutral contract |

**How Bob decides.** Before it builds an app, Bob asks one question: is there an installed snapshot of the toolkit whose `.twx` is in `work/`?
- **Yes:** Bob passes that snapshot as `toolkit_snapshot`.
- **No:** Bob calls `build_widget_toolkit`, installs the result with `install_app`, then builds the app.

A toolkit is installed **once per server**. A process app depends on one snapshot of it, and keeps that snapshot until it is built again; in Designer, a newer snapshot shows as an available upgrade.[^toolkits]

**Say.** "A toolkit is how BAW shares views between process apps. IBM recommends putting a view in a toolkit when it has to be reused across apps."[^reuse]

---

## 5. Test 1: App Builder Widgets (27 min)

### Step 1. Ask for the app

**Paste.**

> Build a small ZZ app for an office supply request. One step with two sections: Requester (name and work email) and Item (item, quantity and needed-by date), then a review screen. Navy header, white text, rounded buttons, "Office Supplies" as the product name. Install it and test it.

**Bob does.** Picks an unused acronym, writes the theme file and the app spec, then **stops to show the design**. Answer: "Approved."

### Step 2. Toolkit first (the main check)

**Bob does,** in this order:
1. `list_snapshots("ABW")`: finds snapshots 1.0.0 to 1.0.3, but none has its `.twx` in `work/`.
2. `build_widget_toolkit("builder", <new name>)`: writes `work/ABW-<name>.twx`.
3. `install_app` on the toolkit. **Bob's tool prompt asks**; answer yes.
4. `create_app` with `toolkit_snapshot` set to that name.

**Check.** Bob never calls `create_app` before the toolkit is installed. If it does, `create_app` refuses with "pass toolkit_snapshot" or "is not installed on the server", and Bob must recover by itself.

### Step 3. Install and test the app

**Bob does.** `inspect_coaches`, then **asks whether to import the app**: yes. Then `install_app`, `test_service` with sample values, and a report with the run URL and screenshots.

**Check.** `test_service` reports `"ok": true`. The screenshots look like the classic App Builder look: navy header, the two section bars, the buttons.

### Step 4. Drag and drop in Coach Designer

**Do.**
1. In Business Automation Studio, open the new app in Designer, then its client-side human service, the **Coaches** tab and the first coach.
2. **Palette.** Find Theme, App Header, Section, Review List and Button Bar, each with its own icon.
3. **Canvas.** The App Header shows the title; each Section shows its title bar; the fields sit inside the Sections; the buttons sit in the Button Bar.
4. **Drag.** Move *Needed By* from the Item section into the Requester section, under *Work Email*.
5. **Relabel.** Select the Item section. In **General**, change its label to "What you need". The section bar on the canvas changes at once: the preview follows the label.[^preview]
6. **Configure.** Select the App Header. In **Configuration**, change *Title*. The canvas follows.
7. **Save**, then press **Run** in the service editor.[^cshs] The running form shows the moved field, the new section title and the new header title.

**Know this.** Designer edits are not in Bob's app spec. If Bob builds this app again, the new snapshot comes from the spec without them, so make Designer edits after Bob is done.

---

## 6. Test 2: Modernizer Widgets on ZZQI (30 min)

### Step 1. Ask for the plan

**Paste,** in the same chat.

> Modernize the ZZQI app, starting from its snapshot v1.0. Build every coach from Modernizer Widgets, with no hand-written screens, so I can rearrange them in Coach Designer. Keep the ZZQI theme file. Show me the plan before you build.

**Bob does.**
1. **Switches to ✨ BAW Coach Modernizer** by itself.
2. `export_app` ZZQI v1.0, `inspect_coaches`, and maybe `test_service` on the legacy service.
3. Improves the coach spec (labels, sections, required fields, examples), with no `"screen"` on any coach.
4. **Stops to show the plan.** It must also say that it did not create ZZQI in this task, so it will add a snapshot to ZZQI only after you approve.

**Check.** The plan says all six coaches (Benefit Funding, Enrollment and Dependents, Rewards, Waivers and Credits, Review Quote Info, Quote Submitted) are built from Modernizer Widgets.

### Step 2. Build, toolkit first

**Paste.**

> Approved. Build it, install it and test it.

**Bob does,** in this order:
1. `list_snapshots("MDW")`: no installed snapshot has its `.twx` in `work/` now.
2. `build_widget_toolkit("modernizer", <new name>)`, then `install_app` on it (Bob asks; yes).
3. `modernize_app` with the `.twx`, the coach spec, a new ZZQI snapshot name and `toolkit_snapshot`.
4. `install_app` on ZZQI (Bob asks; yes).
5. `test_service` on **Quote Info (Modernized)** with `fill`, then the report.

**Check.** `test_service` reports `"ok": true` for Quote Info (Modernized). The legacy **Quote Info** service is still there, unchanged.

### Step 3. Drag, relabel and Required in Coach Designer

**Do.**
1. Open ZZQI in Designer, the **Quote Info (Modernized)** service, the **Coaches** tab, then **Benefit Funding**.
2. **Palette.** Find the eleven Modernizer Widgets with their icons.
3. **Canvas.** The Header shows the title and the steps; each section is a Panel (or a tab of a Tab Section) holding field widgets that look like the running Carbon inputs; the original buttons sit in a Horizontal Layout called Actions.
4. **Inspect a field.** Select one. **General** shows its *Label*, *Help* and *Binding* (`tw.local.…`); *View* reads, for example, *Text Field*, from **Modernizer Widgets**.
5. **Relabel and move.** Change a field's label; the canvas follows. Drag the field to another place in its Panel, or into another Panel.
6. **Required.** Pick a field that is not required. In **Visibility**, set it to **Required**.[^visibility]
7. **Save**, then **Run**. Leave that field empty and press the forward button: the Error Summary lists it, the field shows its error, and the coach does not move on. Fill it in and press again: the coach moves on.

---

## 7. The scorecard

**App Builder Widgets**
1. Bob built App Builder Widgets and installed them **before** `create_app`.
2. `create_app` got `toolkit_snapshot`; the app installed and `test_service` passed.
3. The palette shows the five widgets with their icons.
4. The canvas previews the App Header and Section titles, and follows label and option changes.
5. A field moved between Sections, and the run shows the change.

**Modernizer Widgets**
6. Bob switched to the Modernizer by itself, and asked before adding a snapshot to ZZQI.
7. Bob built Modernizer Widgets and installed them **before** `modernize_app`.
8. `test_service` passed on Quote Info (Modernized); the legacy service is unchanged.
9. The palette shows the eleven widgets; fields preview with their labels.
10. Relabel, move and Required all work at run time, and the Error Summary lists the empty field.

## 8. If it breaks

| You see | Do |
|---|---|
| Bob shows 14 tools | The old server process is running. Restart baw-dev-tools in Bob's MCP panel |
| "Snapshot … already exists in ABW / MDW" | A safety rule. Bob picks the next name by itself |
| `create_app` says "pass toolkit_snapshot" | Bob skipped the toolkit. Note it as a fail for check 1, and let Bob recover |
| "… is not installed on the server" | Bob built the toolkit but did not install it. Bob should `install_app` it first |
| Bob reuses MDW 1.0.0 | `work/MDW-1.0.0.twx` is still in `work/`. Move it (section 2) and ask again with a new ZZQI snapshot |
| The install reports success, but the palette has no widgets | BAW can skip a package silently. Send me the toolkit and snapshot names |
| Blank boxes on the canvas | Reload Designer. If they stay blank, send a screenshot |
| Run does not show your edit | Save first. Run only shows saved changes |
| `test_service` fails with "detached frame" | A known flake: ask Bob to run the test again |

## 9. Send back

1. The scorecard, with a note for every failed check.
2. Bob's tool calls in order, from the toolkit check to the last test.
3. The snapshot names: ABW, MDW, the new app, and ZZQI.
4. A screenshot of each palette, and one of each Designer edit.
5. Then restore ZZQI's spec if you need its hand-written screens: `cp work/old/ZZQI-v1.0.coaches.json work/`.

Project: https://github.com/unclethien/baw-bob-dev-tools-mcp (Apache-2.0). Not an official IBM project; use it with test servers and test apps.

---

## References

[^toolkits]: IBM, Creating, changing, and deleting a toolkit dependency in the Designer view. https://www.ibm.com/docs/en/baw/19.0.0?topic=mut-creating-changing-deleting-toolkit-dependency-in-designer-view
[^reuse]: IBM, Developing reusable coach views. https://www.ibm.com/docs/en/bpm/8.6.0?topic=interfaces-developing-reusable-coach-views
[^preview]: IBM, Event handlers for view design-time preview (BAW 26.0.x). https://www.ibm.com/docs/en/baw/26.0.x?topic=api-event-handlers-view-design-time-preview · Configuring the design-time appearance of views. https://www.ibm.com/docs/en/baw/19.x?topic=behavior-configuring-design-time-appearance-views
[^visibility]: IBM, Setting the visibility of coach views. https://www.ibm.com/docs/en/bpm/8.6.0?topic=views-setting-visibility-coach
[^cshs]: IBM, Building a client-side human service (BAW 24.0.x). https://www.ibm.com/docs/en/baw/24.0.x?topic=services-building-client-side-human-service
[^mcp]: Model Context Protocol, Tools. https://modelcontextprotocol.io/specification/2025-06-18/server/tools
