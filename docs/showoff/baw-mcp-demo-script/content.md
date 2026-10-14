# Demo script: Screenshot in, running BAW app out

A one-hour working-session script for showing IBM Bob and the BAW Bob Dev Tools MCP server. Bob rebuilds an old CRM screen in IBM Business Automation Workflow (BAW) from screenshots, gives it a React + Carbon UI laid out like the client's newer quote screen and in the client's brand, adds dynamic fields and connected tabs, and fixes an issue live, all in the same session.

---

## 1. Hero: one session, two working sessions' worth of work

We planned two working sessions: first rebuild the old screen and modernize it, then brand it and make it smarter. Bob is fast enough to do both in one sitting. The room watches an old CRM tab become a BAW app, then a branded React app whose fields and tabs react to what the user enters.

| Number | What it is |
|---|---|
| 14 | MCP tools: list, export, view, read colours, crop, inspect, create, build, modernize, install, test screens, run workflows |
| 2 | Bob modes: 🏗️ BAW App Builder and ✨ BAW Coach Modernizer |
| 6 | Skills: screenshot-to-app, app-theme, baw-app-builder, coach-inventory, react-coach-screen, coach-modernize |
| 0 | Lines of TWX, BPMN or coach XML written by hand |

Run of show:

| Time | Part | Working-session item |
|---|---|---|
| 00:00 | Opening | |
| 02:00 | Act 1: the old screen, rebuilt in BAW | Upload screenshots; replica as JSON and TWX; import, UI matches; a two-lane workflow (BPMN), editable in BAW |
| 16:00 | Act 2: a modern, branded React version | React + Carbon UI laid out like the newer quote screen (tabs, four columns) in the client's brand (logo, colours); import, show it works; fields that change other fields; tabs that work together; fix an issue |
| 48:00 | Guardrails and questions | |
| 52:00 | Feedback and next steps | Client feedback; agree on what comes next |

---

## 2. Before you start (setup and architecture)

**Who does what.** Bob designs and writes: app specs, theme files, coach specs and React screens. The MCP server does the platform work: it packages TWX files, installs them through the BAW Operations REST API, reads coaches back, and tests every screen in a headless browser.[^mcp-tools][^baw-rest]

Architecture: Bob (custom mode + skills) → MCP over stdio → `baw_mcp.py` → generators (TWX) → BAW Operations REST API; `verify-service.mjs` (headless Chrome) → screenshots back to Bob.

Checklist, 30 minutes before:

1. `.env` holds `BAW_URL`, `BAW_USER` and `BAW_PASSWORD` or `BAW_APIKEY`. Never show it on screen.
2. The repo is open as Bob's workspace; `.bob/mcp.json` points to `server/baw_mcp.py`; the MCP panel shows **baw-dev-tools, 14 tools**.
3. Put the six screenshots of the old CRM's Info tab (`image (1).png` to `image (6).png`), the client's newer quote screen `generate-quote.png`, and the client's old homepage, saved as `brand-reference.png`, in `screenshots/Quote/`. Git ignores that folder, so client screens never reach the public repo. Never put the client's name or pictures in this deck or its public copy.
4. Rehearse the whole run once, so you know how long each install takes. Keep each rehearsal snapshot as a backup.
5. Log in to Business Automation Studio in a second browser tab, for the BPMN step and to run the services.
6. Mode: 🏗️ BAW App Builder. Allow **Mode** in Bob's auto-approve settings, so Bob switches to ✨ BAW Coach Modernizer in Act 2 without a prompt. Font size up, `.env` closed.
7. There is no delete tool, so clean up the ZZ apps after the session.

---

## 3. Act 1: the old screen, rebuilt in BAW (≈14 min)

### Upload the screenshots

**Do.** Flip through `screenshots/Quote/image (1).png` to `image (6).png`: the "Info" tab of a large-group quote in the old CRM, captured while scrolling. Point at the benefit dropdowns with their "Other" boxes, the broker commission, the eligibility and HSA/HRA settings, the rewards checkboxes and the read-only rewards list.

**Say.** "This is the screen we agreed to start with. All we have is pictures of it."

### Replica as JSON and TWX

**Paste.**

> Build a ZZ app from the screenshots in screenshots/Quote, image (1).png to image (6).png. They show one long page, scrolled, so some parts appear twice. Install it, test it and compare the result with the screenshots.

**Bob does:** `view_image` on each picture, merging the parts that appear twice → samples the old colours into `work/<acr>.theme.json` → writes the replica as JSON, `work/<ACR>.app.json` → **stops and shows the design for approval** → `create_app` packages it as `work/<ACR>-1.0.0.twx`.

**Do.** While Bob waits for approval, open `work/<ACR>.app.json`: "this is the screen as data: sections, columns, fields, options". Approve. When `create_app` returns, point at the `.twx` in `work/`: "and this is the same screen as a BAW package".

**Say.**
- "Bob reads the picture the way a developer would: sections, columns, which control is a dropdown, which fields are required."
- "It never writes BAW XML. It writes a small JSON spec; the server turns that into a real process app with standard UI Toolkit views."

### Import into BAW, the UI matches

**Bob does:** **asks whether to import into BAW** → after your yes, `install_app` → `test_service` runs the service in a headless browser → `view_image` on the test screenshot next to the originals → fixes the spec and rebuilds if anything differs.

**Do.** Say yes to the import. Show the test screenshot next to the six originals.

**Say.**
- "Bob stops twice: once to show us the design, once before it imports into BAW. Nothing lands on the server without a person saying yes."[^mcp-tools]
- "Now it checks its own work against the screenshots."

**Point at the result.** One screen with the same groups as the old tab (about 60 fields in 7 sections, up to three columns), the old navy and grey-blue colours, and the "Final Val." button. Bob reports its assumptions and what it left out:
- dropdown options it could not see, because the screenshots show only the selected value;
- the read-only rewards list, shown as text above the rewards fields;
- the last waiver rows, cut off at the bottom of the last screenshot;
- the old CRM's menu, toolbar, other tabs and the Activities grid, which are not part of the form.

### BPMN, editable in BAW

**Paste.**

> Put this screen in a workflow: Sales fills it in, then Underwriting reviews it and approves it or sends it back to Sales with comments. Import it and run it once with a send-back.

**Bob does:** adds a `process` to the spec (the form as the Sales task, a "Review Quote" task in an Underwriting lane, Approve and Send Back) → **stops and shows the lanes for approval** → `create_app` builds the next snapshot → **asks before importing** → `install_app` → `test_process` starts the workflow, fills the form, presses Send Back on the review, fills the form again and approves it.

**Do.** Approve the lanes and the import. While `test_process` runs, switch to Business Automation Studio and open the new ZZ app, then **Processes** and the workflow:
- two lanes, Sales and Underwriting, with the form task, the review task, the "Approved?" decision and the Send Back path back to Sales;
- click **Review Quote**, then **Data mapping**: the quote goes in and comes back out;
- click the **Send Back** line: its condition is the reviewer's decision;
- drag a task a little to show the diagram is editable, then undo.

When `test_process` returns, show its report: four tasks (Sales, Review with Send Back, Sales again, Review with Approve) and the state "Completed".

**Say.**
- "This is not a picture or a mock-up. It is a normal BAW process, built from standard parts, and your developers can open and change it like anything they drew themselves."
- "Bob ran it the way people will: the work went to Underwriting, came back to Sales, and was approved the second time."

---

## 4. Act 2: a modern, branded React version (≈32 min)

**Say.** "We planned this for two working sessions: a modern version today, the brand and the smarter rules next time. Bob is quick, so let's do both now."

### The look: the client's layout and brand, with IBM Carbon

**Do.** Open `screenshots/Quote/generate-quote.png`: the client's newer quote screen, the layout they already like. Point at the tabs across the top, the four columns of fields and the buttons at the bottom right. Then open `screenshots/Quote/brand-reference.png`: the client's homepage from 2004, with the brand people know: the logo at the top left, a blue-violet bar with a thin cyan line above it, beige section headings and light blue side panels. Stay in the same chat: Bob switches to ✨ BAW Coach Modernizer by itself when you ask for a React UI, and takes the app, its coach spec and its theme file with it.

**Paste.**

> Give the app you just built a React UI with IBM Carbon components. Lay it out like screenshots/Quote/generate-quote.png, the client's newer quote screen: the fields split into tabs by section, four columns, labels close to their fields, the title in the header, Submit and Cancel at the bottom right. Take the brand from screenshots/Quote/brand-reference.png, the client's old homepage: cut out its logo, and take its colours from the blue-violet bar, the cyan line, the beige section headings and the light blue panels. Improve the labels and add help text and validation. Inspect the coaches, improve the coach spec and show me before you build.

**Bob does:** switches to ✨ BAW Coach Modernizer → `view_image` on both pictures → `image_colors` samples the bar, the cyan line, the headings and the panels → `crop_image` cuts the logo into `work/`, because the prompt asks for it → writes a theme file (blue-violet header and buttons, beige section bars, light blue accents, the logo) → `inspect_coaches` reads every coach into a coach spec (sections, fields in reading order, options, required flags) → splits the sections into tabs and plans the four-column grid → improves labels, adds help text, validation and examples → **stops for approval**.

**Paste.**

> Approved. Write a React screen for each coach, then modernize, install and test it.

**Bob does:** writes `react-coach/src/screens/*.jsx` → `build_screens` (fixes compiler errors itself) → `modernize_app` (new snapshot, a new "(Modernized)" service next to the original) → **asks whether to import** → `install_app` → `test_service`, filling sample values and pressing every button.

### Import into BAW, show it works

**Do.** In Business Automation Studio, run the "(Modernized)" service. Fill a few fields, leave a required one empty and press the button to show the validation, then complete it.

**Say.**
- "The layout is the client's own newer screen, the brand is theirs, the components are IBM Carbon. The old coach flow, scripts and buttons keep running underneath. The React screen only replaces what people see."[^carbon]
- "The look lives in one theme file. Change a colour or the logo there, rebuild, and every screen follows."
- "The modernized copy sits next to the original in a new snapshot, so the old UI still works and you can compare."

### Fields that change other fields, tabs that work together (the behaviour)

**Paste.**

> Now make the screen react to what the user enters:
> - Add an Other choice to each benefit dropdown. Show its "Other" box only when Other is chosen, and make it required then.
> - Show the commission $ and % boxes only when the broker commission is Custom.
> - Keep the Reward Programs tab locked until a Reward Delivery Method is chosen.
> - Show on each tab how many required fields are still empty, and when Submit finds a problem, open the first tab that has it.
>
> Build, install and test it.

**Bob does:** writes the rules into the React screen (each field can read and set any other field of the business object) → `build_screens` → `modernize_app` → **asks whether to import** → `install_app` → `test_service`.

**Do.** Run it. Pick "Other" in a benefit dropdown and watch its box appear; set a commission to Custom and watch the $ and % boxes appear. Leave a required field empty on the first tab, go to the last tab and press Submit: the screen jumps back to the right tab.

**Say.** "The rules run in the screen, so they react instantly. The data still goes into the same BAW business object as before, so the process behind it does not change."

Agree the exact rules with the client before the session; the prompt above uses examples from the Info tab.

### Fix an issue

Ask the room for something they want changed. If nobody has one, use the planned issue: the commission percentage accepts any number.

**Paste.**

> The Broker Commission % field accepts 250. Only allow 0 to 100 and show a clear error. Rebuild, install and test it.

**Bob does:** edits the screen → `build_screens` → `modernize_app` with the next snapshot → **asks whether to import** → `install_app` → `test_service`.

**Do.** Run the new snapshot, type 250 and show the error.

**Say.** "Every fix is a new snapshot. The previous one is still there if we need to go back."

Backup issues: number fields that start at 0 instead of blank; a label the client wants worded differently.

---

## 5. Guardrails and tough questions

| Guardrail | Why it matters |
|---|---|
| Installs only into apps named "ZZ …" with a ZZ acronym | Demo work can never touch a real app |
| Every install is a new snapshot | BAW silently keeps old content when a snapshot name is reused |
| No delete tool | The agent cannot remove anything |
| Credentials stay inside the server process | Bob never sees passwords or tokens |
| Bob asks before create, modernize and install; edits only `work/`, `app-specs/`, `react-coach/src/screens/` | Custom modes restrict tools and file edits[^bob-modes][^bob-custom-modes] |

**Questions to expect**

- *Does Bob write BAW XML?* No. It writes JSON specs, theme files and React files; the server generates the TWX.
- *Is the BPMN a real process?* Yes. Bob generates a business process with lanes: the form is the first task, then a review task with Approve and Send Back. It opens in Studio's process editor, where developers add steps, timers or a team per lane.
- *Can it read from or save to a database?* Not yet. BAW reads and writes databases through its SQL services and a JDBC data source on the server. Loading a record into the form and saving it on submit is the next step, and it needs a data source to use.
- *What can it not build from a screenshot yet?* Tables, file uploads, links and extra buttons. Bob lists them and offers to add them in a React screen.
- *Does it work with our existing apps?* Yes, read-only: `export_app` + `inspect_coaches` turn any app into a coach spec. Modernized output installs only into ZZ copies.
- *Can other agents use it?* Yes. It is a standard stdio MCP server; any MCP client can call the same 14 tools.[^mcp-tools]
- *What happens on an error?* Tool errors come back as readable messages (bad login, snapshot exists, compiler error with file and line), and Bob fixes the spec or screen and retries.

**If something breaks on stage**

| Symptom | Recovery |
|---|---|
| MCP panel shows 0 tools | Restart baw-dev-tools in Bob's MCP panel |
| "Login to BAW_URL failed" | Check `.env`; switch to the rehearsal app and screenshots |
| "Snapshot already exists" | Let Bob bump the snapshot; this is the guard working |
| "stuck … fields need attention" | Validation blocked a press; Bob adds example values |
| A slow install | Talk through the architecture slide while it runs |
| `test_process` does not reach "Completed" | Open the diagram in Studio and the task screenshots in `work/shots-…`; the diagram step does not depend on the test run |

---

## 6. Feedback and next steps

**Do.** Ask the client, and write the answers down:
1. Does the rebuilt Info tab match the old one? What did Bob guess wrong, especially the dropdown options?
2. Is the branded screen right for production? Can they send the official logo file?
3. Which fields drive other fields, and which tabs depend on each other, in the real process?
4. Which tab or screen comes next?
5. Which data should come from a database, and from which system?

Agree the scope of the next session from the answers.

Recap: screenshots became a BAW app you can edit in Studio, then a React + Carbon app in the client's layout and brand, with rules and connected tabs, each step tested in a browser and approved by a person before it reached the server.

Encore prompt:

> Build a small ZZ app for an office supply request: one step with requester name, item, quantity and needed-by date, then a review screen. Install it and test it.

Repository: https://github.com/unclethien/baw-bob-dev-tools-mcp (Apache-2.0). Not an official IBM project; use it with test servers and test apps.

---

## References

[^mcp-tools]: Model Context Protocol specification, Tools (2025-06-18): tools are model-controlled, results may contain image content, and clients SHOULD keep a human in the loop. https://modelcontextprotocol.io/specification/2025-06-18/server/tools
[^bob-modes]: IBM Bob documentation, Modes. https://bob.ibm.com/docs/ide/features/modes
[^bob-custom-modes]: IBM Bob documentation, Custom modes (tool access and file permissions). https://bob.ibm.com/docs/ide/configuration/custom-modes ; Skills: https://bob.ibm.com/docs/ide/features/skills
[^baw-rest]: IBM documentation, installing a solution with the BAW REST APIs (`POST /std/bpm/containers/install`, then poll the container version). https://ibm.com/support/knowledgecenter/SS8JB4_23.x/com.ibm.casemgmt.design.doc/tinstallcasesolonprod.html
[^carbon]: Carbon Design System, IBM's open-source design system; React components in `@carbon/react`. https://carbondesignsystem.com/ ; https://www.npmjs.com/package/@carbon/react
