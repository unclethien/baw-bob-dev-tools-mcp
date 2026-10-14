# Demo script: Screenshot in, running BAW app out

A one-hour working-session script for showing IBM Bob and the BAW Bob Dev Tools MCP server. It starts with what MCP is, the tools and the modes, and how to write a prompt for them. Then you keep talking while Bob works: Bob rebuilds an old CRM screen in IBM Business Automation Workflow (BAW) from screenshots, gives it a React + Carbon UI laid out like the client's newer quote screen, then adds dynamic fields and connected tabs. For every prompt, the script says why it is written that way and which tools Bob will call.

---

## 1. Opening: one session, two working sessions' worth of work

We planned two working sessions: first rebuild the old screen and modernize it, then make it smarter. Bob is fast enough to do both in one sitting. Before the demo, the room learns how it works, so they can follow every step and write their own prompts afterwards.

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
| 02:00 | Part 1: what MCP is | How an agent gets tools; this server and what it talks to |
| 06:00 | Part 2: the tools and the modes | 14 tools in four groups; the two Bob modes and their skills |
| 12:00 | Part 3: prompt 101 | The five parts of a good prompt |
| 15:00 | Act 1: the old screen, rebuilt in BAW | Upload screenshots; replica as JSON and TWX; import, UI matches; a two-lane workflow (BPMN), editable in BAW |
| 30:00 | Act 2: a modern React version | React + Carbon UI laid out like the newer quote screen (tabs, four columns); import, show it works; fields that change other fields; tabs that work together |
| 48:00 | Guardrails and questions | |
| 52:00 | Feedback and next steps | Client feedback; agree on what comes next |

---

## 2. Before you start (setup)

Checklist, 30 minutes before:

1. `.env` holds `BAW_URL`, `BAW_USER` and `BAW_PASSWORD` or `BAW_APIKEY`. Never show it on screen.
2. The repo is open as Bob's workspace; `.bob/mcp.json` points to `server/baw_mcp.py`; the MCP panel shows **baw-dev-tools, 14 tools**.
3. Put the six screenshots of the old CRM's Info tab (`image (1).png` to `image (6).png`) and the client's newer quote screen `generate-quote.png` in `screenshots/Quote/`. Git ignores that folder, so client screens never reach the public repo. Never put the client's name or pictures in this deck or its public copy.
4. Rehearse the whole run once, so you know how long each install takes. Keep each rehearsal snapshot as a backup.
5. Log in to Business Automation Studio in a second browser tab, for the BPMN step and to run the services.
6. Mode: 🏗️ BAW App Builder. Allow **Mode** in Bob's auto-approve settings, so Bob switches to ✨ BAW Coach Modernizer in Act 2 without a prompt. Font size up, `.env` closed.
7. There is no delete tool, so clean up the ZZ apps after the session.

---

## 3. Part 1: what MCP is (≈4 min)

**Do.** Show the architecture slide. Then open Bob's MCP panel: **baw-dev-tools**, connected, 14 tools. Expand `test_service` to show its description and inputs.

**Say.**
- "MCP, the Model Context Protocol, is an open standard for giving an AI agent tools. A tool server tells the agent: here are my tools, what each one needs and what it returns. The agent decides when to call them, and a person stays in the loop."[^mcp-tools]
- "Think of it as a USB port for AI agents. Bob is the client; any MCP client could plug into the same server."
- "Our server, `baw_mcp.py`, runs on this laptop next to Bob. It holds the BAW login, so Bob never sees a password or a token. It talks to the BAW Operations REST API to install apps, and drives a headless Chrome to test the screens, then hands the screenshots back so Bob can look at them."[^baw-rest]
- "Bob never writes BAW XML. It writes a small JSON spec, and the server's generators turn it into a real process app. The tools are safe by design: they install only into ZZ test apps, always as a new snapshot, and there is no delete tool."

Architecture: Bob (mode + skills) → MCP over stdio → `baw_mcp.py` → generators (spec to TWX) → BAW Operations REST API; `verify-service.mjs` (headless Chrome) → screenshots back to Bob.

---

## 4. Part 2: the tools and the modes (≈6 min)

### The 14 tools, in four groups

| Group | Tools | What they do |
|---|---|---|
| Look at the server | `list_apps`, `list_snapshots`, `list_services`, `export_app` | Read-only: which apps, snapshots and services exist; download an app as a `.twx` |
| Look at pictures | `view_image`, `image_colors`, `crop_image` | Show Bob a screenshot, sample its exact colours, cut out a region such as a logo |
| Build | `create_app`, `inspect_coaches`, `build_screens`, `modernize_app` | Spec to app; app back to an editable spec; compile the React screens; add a React copy of each service |
| Run on the server | `install_app`, `test_service`, `test_process` | Install a `.twx`; walk a service in a browser; run a workflow task by task |

**Say.**
- "Most tools only read. The ones that change something, `create_app`, `modernize_app`, `install_app` and `crop_image`, ask for approval first; the others run without a prompt."
- "Bob picks the tools itself. You describe the result you want; you never name a tool in a prompt."

### Modes and skills

A Bob **mode** is a job description: a role, the tools it may use, the files it may edit, and its rules. A **skill** is a playbook Bob loads when a task matches, such as how to read a screenshot into a spec.[^bob-modes][^bob-custom-modes]

| Mode | Does | Edits | Skills |
|---|---|---|---|
| 🏗️ BAW App Builder | A requirement or screenshots become a running app, optionally with a workflow | `work/`, `app-specs/` | screenshot-to-app, app-theme, baw-app-builder |
| ✨ BAW Coach Modernizer | An existing app gets a React + Carbon UI, as a new "(Modernized)" service | `work/`, `app-specs/`, `react-coach/src/screens/` | coach-inventory, react-coach-screen, coach-modernize, app-theme |

**Say.**
- "The mode is the job description, the skills are the playbooks, and the MCP tools are the hands."
- "Each mode stops twice: it shows the design before it builds, and it asks before it imports into BAW."
- "When the work changes, Bob switches mode by itself: ask the App Builder for a React UI and it hands the app to the Modernizer."

---

## 5. Part 3: prompt 101 (≈3 min)

**Do.** Put the Act 1 prompt on screen and walk through its parts.

A good prompt for Bob has up to five parts:

| # | Part | In the Act 1 prompt |
|---|---|---|
| 1 | **Outcome**: what you want at the end | "Build a ZZ app" |
| 2 | **Inputs**: the files to work from, by path | "from the screenshots in screenshots/Quote, image (1).png to image (6).png" |
| 3 | **What Bob cannot know**: context that is not in the files | "They show one long page, scrolled, so some parts appear twice." |
| 4 | **Constraints**: layout, look, rules, in the words users see | (none here: the screenshots are the spec; Act 2 adds them) |
| 5 | **How far, and where to stop** | "Install it, test it and compare the result with the screenshots." |

**Say.**
- "Say what you want, not how. No tool names, no BAW terms: Bob picks the tools."
- "Point at files by path, and say what Bob cannot see, like the pictures overlapping."
- "One goal per prompt. Change things with short follow-ups, and answer a stop with 'Approved.'"
- "End with how far to go: build only, or install, test and compare."

---

## 6. Act 1: the old screen, rebuilt in BAW (≈15 min)

### Upload the screenshots

**Do.** Flip through `screenshots/Quote/image (1).png` to `image (6).png`: the "Info" tab of a large-group quote in the old CRM, captured while scrolling. Point at the benefit dropdowns with their "Other" boxes, the broker commission, the eligibility and HSA/HRA settings, the rewards checkboxes and the read-only rewards list.

**Say.** "This is the screen we agreed to start with. All we have is pictures of it."

### Prompt 1: the replica

**Paste.**

> Build a ZZ app from the screenshots in screenshots/Quote, image (1).png to image (6).png. They show one long page, scrolled, so some parts appear twice. Install it, test it and compare the result with the screenshots.

**Prompt 101.** Outcome, inputs, what Bob cannot know, how far: four of the five parts. There is no field list and no colours: the screenshots are the spec. There is no "show me first" either: the mode stops before it builds anyway.

**Tools Bob will use, in order.**

1. `use_skill` screenshot-to-app: loads the playbook.
2. `view_image` on each screenshot: reads the screen, merging the parts that appear twice.
3. `image_colors`: samples the old colours into a theme file, `work/<acr>.theme.json`.
4. `list_apps`: picks an unused ZZ acronym.
5. Writes `work/<ACR>.app.json`, then **stops and shows the design**, and asks which installed app to match (or the built-in template).
6. `create_app`: packages it as `work/<ACR>-1.0.0.twx`; `inspect_coaches` checks every screen.
7. **Asks whether to import**, then `install_app`.
8. `test_service`: runs it in a headless browser; `view_image` on the result next to the originals.

**Say, while it runs.**
- At the screenshots: "Bob reads the picture the way a developer would: sections, columns, which control is a dropdown, which fields are required."
- At the design stop: open `work/<ACR>.app.json`. "This is the screen as data: sections, columns, fields, options. Bob never writes BAW XML; the server turns this into a real process app with standard UI Toolkit views." Approve.
- At the `.twx`: "And this is the same screen as a BAW package."
- At the import question: "Nothing lands on the server without a person saying yes."[^mcp-tools] Say yes.
- At the test: "A real browser, on the real server, pressing the real buttons. Now it checks its own work against the screenshots."

**Point at the result.** One screen with the same groups as the old tab (about 60 fields in 7 sections, up to three columns), the old navy and grey-blue colours, and the "Final Val." button. Bob reports its assumptions and what it left out:
- dropdown options it could not see, because the screenshots show only the selected value;
- the read-only rewards list, shown as text above the rewards fields;
- the last waiver rows, cut off at the bottom of the last screenshot;
- the old CRM's menu, toolbar, other tabs and the Activities grid, which are not part of the form.

### Prompt 2: the workflow (BPMN), editable in BAW

**Paste.**

> Put this screen in a workflow: Sales fills it in, then Underwriting reviews it and approves it or sends it back to Sales with comments. Import it and run it once with a send-back.

**Prompt 101.** "This screen" builds on the conversation: no need to repeat the app. The process is described in business words: who (Sales, Underwriting), what each does, the loop back. No BPMN terms. It ends with how far: import, and run it once the hard way, with a send-back.

**Tools Bob will use, in order.**

1. Adds a `process` to the spec: the form as the Sales task, a "Review Quote" task in an Underwriting lane, Approve and Send Back. **Stops and shows the lanes.**
2. `create_app`: builds the next snapshot.
3. **Asks before importing**, then `install_app`.
4. `test_process`: starts the workflow, fills the form, presses Send Back on the review, fills the form again and approves it.

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

## 7. Act 2: a modern React version (≈18 min)

**Say.** "We planned this for two working sessions: a modern version today, the smarter rules next time. Bob is quick, so let's do both now."

### Prompt 1: the look, from the client's layout

**Do.** Open `screenshots/Quote/generate-quote.png`: the client's newer quote screen, the layout they already like. Point at the tabs across the top, the four columns of fields and the buttons at the bottom right. Stay in the same chat.

**Paste.**

> Give the app you just built a React UI with IBM Carbon components. Lay it out like screenshots/Quote/generate-quote.png, the client's newer quote screen: the fields split into tabs by section, four columns, labels close to their fields, the title in the header, Submit and Cancel at the bottom right. Use a clean look in the client's blue from that screen, on a white page. Improve the labels and add help text and validation. Inspect the coaches, improve the coach spec and show me before you build.

**Prompt 101.** All five parts: the outcome (a React UI with Carbon), the input by path (the newer screen), the constraints in the words users see (tabs, four columns, labels close, buttons bottom right, the blue on white), the quality asks (labels, help text, validation), and where to stop ("show me before you build").

**Tools Bob will use, in order.**

1. `switch_mode` to ✨ BAW Coach Modernizer: the work changed from building to modernizing.
2. `use_skill` coach-inventory, then app-theme.
3. `view_image` on the newer quote screen; `image_colors` samples its blue; writes the theme file.
4. `inspect_coaches`: reads every coach into a coach spec (sections, fields in reading order, options, required flags). If Act 1 already wrote one, Bob reuses it.
5. Splits the sections into tabs, plans the four-column grid, improves labels, adds help text, validation and examples. **Stops for approval.**

**Say, while it runs.**
- At the switch: "Bob changed mode by itself. Same chat, same app; now the Modernizer's rules and playbooks apply."
- At the coach spec: "Bob read the app it just built back into an editable spec. The same works for any existing app on the server."

### Prompt 2: build it

**Paste.**

> Approved. Write a React screen for each coach, then modernize, install and test it.

**Prompt 101.** After a stop, the follow-up is short: the plan is already agreed, so the prompt only says go and how far.

**Tools Bob will use, in order.**

1. `use_skill` react-coach-screen, then writes `react-coach/src/screens/*.jsx`.
2. `build_screens`: compiles them; Bob fixes compiler errors itself.
3. `modernize_app`: a new snapshot with a "(Modernized)" service next to the original.
4. **Asks whether to import**, then `install_app`.
5. `test_service`: fills sample values and presses every button.

**Do.** In Business Automation Studio, run the "(Modernized)" service. Fill a few fields, leave a required one empty and press the button to show the validation, then complete it.

**Say.**
- "The layout is the client's own newer screen; the components are IBM Carbon. The old coach flow, scripts and buttons keep running underneath. The React screen only replaces what people see."[^carbon]
- "The look lives in one theme file. Change a colour or the logo there, rebuild, and every screen follows."
- "The modernized copy sits next to the original in a new snapshot, so the old UI still works and you can compare."

### Prompt 3: fields that change other fields, tabs that work together

**Paste.**

> Now make the screen react to what the user enters:
> - Add an Other choice to each benefit dropdown. Show its "Other" box only when Other is chosen, and make it required then.
> - Show the commission $ and % boxes only when the broker commission is Custom.
> - Keep the Reward Programs tab locked until a Reward Delivery Method is chosen.
> - Show on each tab how many required fields are still empty, and when Submit finds a problem, open the first tab that has it.
>
> Build, install and test it.

**Prompt 101.** Rules as a list, one rule per line, each as "when this, then that", using the labels users see. It ends with how far to go.

**Tools Bob will use, in order.**

1. Writes the rules into the React screen: each field can read and set any other field of the business object.
2. `build_screens`, then `modernize_app` with the next snapshot.
3. **Asks whether to import**, then `install_app`.
4. `test_service`.

**Do.** Run it. Pick "Other" in a benefit dropdown and watch its box appear; set a commission to Custom and watch the $ and % boxes appear. Leave a required field empty on the first tab, go to the last tab and press Submit: the screen jumps back to the right tab.

**Say.** "The rules run in the screen, so they react instantly. The data still goes into the same BAW business object as before, so the process behind it does not change."

Agree the exact rules with the client before the session; the prompt above uses examples from the Info tab.

---

## 8. Guardrails and tough questions

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

## 9. Feedback and next steps

**Do.** Ask the client, and write the answers down:
1. Does the rebuilt Info tab match the old one? What did Bob guess wrong, especially the dropdown options?
2. Should the production screen use their own brand? Can they send the official logo file?
3. Which fields drive other fields, and which tabs depend on each other, in the real process?
4. Which tab or screen comes next?
5. Which data should come from a database, and from which system?

Agree the scope of the next session from the answers.

Recap: screenshots became a BAW app you can edit in Studio, then a React + Carbon app in the client's layout, with rules and connected tabs, each step tested in a browser and approved by a person before it reached the server.

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
