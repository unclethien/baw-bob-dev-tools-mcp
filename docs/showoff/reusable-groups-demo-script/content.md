# Demo script: reusable groups, built by Bob and owned in BAW

A 45-minute working session for the client team. In the last session the team asked for **reusable, configurable pieces**: smaller widgets combined into a larger "Group", placed by drag and drop, with settings to show or hide parts, and maintainable in IBM Business Automation Workflow (BAW) without going back to Bob. Today IBM Bob builds the Quote screen from such groups, and the team changes one in BAW:

1. **Act 1:** Bob builds the Quote app from the old screen's pictures, with every section as a **reusable group**: a View inside the app that each screen places, editable on the form and read-only on the review.
2. **Act 2:** the team changes a group in Coach Designer. Bob then rebuilds the app for another change, **keeps the team's version of the group**, says what changed and asks before replacing anything.

**How to read this script.** Each step tells you what to **do**, what to **paste** into Bob, what **Bob does**, and what to **say**. Text in quotes is meant to be said out loud. The pictures on the demo page come from a neutral example app, "ZZ Grouped Quote"; on the day, Bob builds from the client's own pictures.

---

## 1. Run of show

| Time | Part | What the room sees |
|---|---|---|
| 00:00 | Opening | What the team asked for last time, and today's goal |
| 03:00 | How it works | What a group is, where it lives in BAW, and its settings |
| 10:00 | Act 1: build with groups | Pictures in; an app made of reusable groups out; the groups under the app's User interface |
| 25:00 | Act 2: change it in BAW | The team edits a group; Bob rebuilds, keeps their version and asks |
| 37:00 | Safety and questions | The open questions from last session |
| 42:00 | Next steps | Which information repeats across the team's screens |

---

## 2. Before the meeting

Thirty minutes before:

1. Check the BAW login file (`.env`) is filled in. Never show it on screen.
2. Get the latest project (`git switch main && git pull`). Open it in Bob; the tools panel shows **baw-dev-tools** with **15 tools**. If it shows fewer, restart baw-dev-tools in that panel.
3. Run `git status`: it should be clean. Bob writes only in `work/` during this demo, so the same check after the rehearsal shows nothing new outside it. If an earlier demo left Toggle widget files, remove them first:
   ```
   rm -f coach-ui/src/widgets/toggle.jsx coach-ui/src/widgets/toggle.scss coach-ui/widgets/icons/toggle.svg
   git checkout -- coach-ui/widgets/modernizer-widgets.json
   ```
4. Keep `screenshots/Quote/` as it is: the six pictures of the old screen (`image (1).png` to `image (6).png`). It stays on this laptop and is never published.
5. Pick a **new acronym** for the app and put it in the Act 1 request (the script uses `ZZGDEMO`; use `ZZGDEMO2` after a rehearsal). Acronyms already used on the test server: ZZQI, ZZLGQ, ZZLGQI, ZZSLX, ZZGRP, ZZGRP2, ZZGWQ, ZZLGG. App Builder Widgets (ABW) 1.0.4 is installed, and `work/ABW-1.0.4.twx` is on this laptop.
6. Do one full rehearsal, so you know how long each step takes. Keep the rehearsal app as a backup.
7. Open Workflow Center (Business Automation Studio) in a second browser tab.
8. In Bob, pick the **🏗️ BAW App Builder** mode. Make the font bigger.
9. Afterwards, ask a BAW admin to archive the test snapshots: Bob cannot delete anything.

---

## 3. Opening (3 min)

**Say.**
- "Last time you asked for reusable pieces: small widgets combined into a larger group, so the same information isn't rebuilt on every screen, with settings to show or hide parts."
- "You also asked a fair question: after Bob builds it, who maintains it? Today you'll change a group yourselves in BAW, and see what Bob does with your change."

---

## 4. How it works (7 min)

**Do.** Show the diagram: one group, placed on three screens, plus its Preview service.

**Say.**
- "In BAW a screen is a coach, and its building blocks are views. A view can contain other views and bind to the app's data. That is exactly what a group is."[^reuse]
- "Bob builds each group as a **View inside the app**. It is listed in Workflow Center under the app's User interface, next to the services. Open it, and you change it for every screen that uses it."
- "Each group also gets a small service, '<group> Preview', that shows only the group, so you can run and test it on its own."

| Where it is placed | How it shows |
|---|---|
| The form step | Editable |
| A later step, "for reference" | Read-only, one field hidden |
| The review | Read-only, shown once |
| `<group> Preview` | The group alone, for testing |

**Say.**
- "Each placement has its own settings. Every optional field has a visibility setting: Same as parent, or Hidden. And the placement's own Visibility can make the whole group read-only."[^visibility][^options]
- "Bob proposes a group when three or more fields appear on two or more screens, or uses the groups you name. It shows them in the design before it builds anything."
- "Bob has 15 tools. The ones that change something ask first."

---

## 5. Act 1: build with groups (15 min)

### Step 1. Show the old screen

**Do.** Flip through the six pictures: one long "Info" tab of a quote in an old CRM, captured while scrolling.

**Say.** "All we have is pictures. Today we ask Bob for the same screen, but made of reusable groups."

### Step 2. Ask Bob

**Paste.**

> Build a ZZ app from the screenshots in screenshots/Quote, image (1).png to image (6).png. They show one long page, scrolled, so some parts appear twice. Build it from App Builder Widgets, with the acronym ZZGDEMO. Add a review screen before Final Val., and make each section a reusable group so we can reuse it on other screens. Install it, test it and compare the result with the screenshots.

**Bob does.**
1. Opens each picture and reads the screen: sections, columns, drop-downs, checkboxes. Reads the colours and the logo file.
2. Writes the design, **with a Groups part**: each section as a group, its fields, and where it is placed (editable on the form, read-only on the review).
3. **Stops and shows us the design**, with a few questions.

**Paste**, to answer its questions.

> Approved. Use the built-in template, build only the Info. tab, and leave out the product name.

**Say, while it works.**
- "Bob doesn't build anything before you approve the design, groups included."
- "A group is about the information, not the look: the same fields, kept together, wherever they appear."

### Step 3. Build, install and test

**Bob does.**
1. Builds the app (`create_app`): one View per group, one Preview service per group, and the screens that place them.
2. **Asks before installing.** Answer yes.
3. Opens it in a real browser, clicks through every screen, takes a picture of each and compares them with the originals.

**Do.** Show the form, then the review: each group appears once, read-only.

**Say.** "About 60 fields in 8 groups. The review isn't a copy of the fields: it places the same groups, read-only."

### Step 4. Find the groups in BAW

**Do.** In Workflow Center, open the new app and go to **User interface**.
1. Under **View**: the 8 groups, for example Rating Method and Waivers and Credits.
2. Under **Client-side human service**: the Quote service, and one "<group> Preview" per group. Run one.
3. Open a coach, click a group: its settings show a visibility setting per optional field.

**Say.**
- "These are ordinary BAW views in your app. Your developers can open them, add, remove or move fields, and reuse them on other screens of this app."
- "Nothing here needs Bob any more."

---

## 6. Act 2: change it in BAW (12 min)

### Step 1. Change a group in Coach Designer

**Do.** Open the **Waivers and Credits** View.
1. Relabel "Waive Dependent Eligibility on Initial Enrollment" to "Waive Dependent Eligibility". Optionally drag one field above another.
2. Save.
3. On the app, **create a snapshot**, for example `1.0.0-edited`.[^snapshots]

**Say.**
- "Every screen that places this group shows the new label. We changed it once."
- "The snapshot matters: Bob only sees changes that are in a snapshot."

### Step 2. Ask Bob for an unrelated change

**Paste.**

> In the classic app, make Rewards Eligibility a required field.

**Bob does.** Shows the change it will make (Rewards Eligibility becomes required) and waits. Answer: "Yes."

**Then Bob does.**
1. Changes its app spec and builds the next snapshot (`create_app`), on top of our snapshot.
2. Notices that **Waivers and Credits was changed in BAW**, keeps our version, and does **not** install yet.
3. Shows what changed (the label), and asks: **keep BAW's version, or replace it with the spec's?**

**Say.**
- "Bob compares each group with what it built. It noticed our change without being told."
- "It asks, because only we know whether the change was on purpose."

### Step 3. Keep your version

**Paste.**

> Keep BAW's version.

**Bob does.**
1. Updates its own spec to match our group, so the next rebuild doesn't ask again.
2. Installs the new snapshot (our yes to importing this app in Act 1 covers its new snapshots) and tests it.

**Do.** Run the app. Rewards Eligibility now has a required marker, and the Waivers and Credits label is still ours.

**Say.**
- "Two people changed the same app: you in BAW, Bob from a request. Nothing was lost, and nothing was overwritten without asking."
- "Had we said 'replace', Bob would rebuild the group from its spec instead. That's also one sentence."

---

## 7. Safety and questions

| Safety rule | Why it matters |
|---|---|
| A person approves every change, groups included | Bob shows the design, or the change, and waits before building |
| Bob asks before importing an app | Nothing reaches BAW unasked; that yes covers the app's later snapshots |
| Every install is a new snapshot | Nothing is overwritten; you can always go back |
| A group changed in BAW is kept until you say otherwise | Your edits survive Bob's next rebuild |
| Bob cannot delete anything | No tool for it exists |
| The password stays in the connector | Bob never sees it |

**Questions to expect** (the open questions from last session)

- *Can smaller widgets be combined into larger reusable ones, keeping configuration and data binding?* Yes. A group is a View made of field views, bound to the app's data, with a visibility setting per field and a read-only setting per placement.[^reuse][^options] Groups inside groups, and repeating groups (lists), are not built yet.
- *Which changes can we make in BAW, and which need Bob?* Changes to a group's fields (add, remove, move, relabel) are yours: save a snapshot and Bob keeps them. Other edits to a group, such as help text, choice lists or styling, belong in Bob's spec, because a rebuild replaces them.
- *Will the generated code stay readable?* Groups are ordinary BAW Views with BAW's own fields, opened and edited in Coach Designer. Each group has a short load script for read-only behaviour.
- *How are versions managed?* Every build is a new snapshot of the same app. A group keeps the same ID in every snapshot, so the screens keep finding it.[^snapshots]
- *Can a group be shared across apps?* Not yet: groups live in one app. Sharing them means moving them into a toolkit, a next step.
- *Does the modern (React + Carbon) version keep the groups?* Yes. Bob reads the groups back and builds a "(Modernized)" copy of each, with its own Preview service. Modernized groups show one field per row.
- *Can other AI assistants do this?* Yes. The connector follows the open MCP standard, so any assistant that supports MCP can use the same 15 tools.[^mcp]

**If something breaks on stage**

| Problem | What to do |
|---|---|
| Bob's tools panel shows 0 tools | Restart baw-dev-tools in that panel |
| "Snapshot already exists", or the acronym is taken | Let Bob pick the next version, or give it a new acronym: a safety rule working |
| Bob proposes no groups | Say: "Make each section a reusable group." One long screen with no review repeats nothing, so Bob won't propose groups by itself |
| Bob doesn't notice your change in Act 2 | The change isn't in a snapshot yet: create one, then ask again |
| A Preview test fails with "detached Frame" | A test-runner timing issue when a one-screen service ends; run it again |
| An install is slow | Talk through the groups diagram while it runs |

---

## 8. Next steps

**Do.** Ask the client, and write the answers down:
1. Which information repeats across your screens? Those are your first groups.
2. Should groups be shared across apps? That decides whether they move into a toolkit.
3. Who on your team edits groups in BAW, and who asks Bob for rebuilds?
4. Which screen comes next?

**Say.** "In 45 minutes: pictures became an app made of reusable groups, you changed one in BAW, and Bob kept your change when it rebuilt. Every step was tested in a browser and approved by a person before it reached BAW."

Project: https://github.com/unclethien/baw-bob-dev-tools-mcp (Apache-2.0). Not an official IBM project; use it with test servers and test apps.

---

## Rehearsal checklist

1. Bob's design lists the groups and where each is placed, before anything is built.
2. Bob asks before importing the app.
3. `test_service` passes; the review shows each group once, read-only.
4. Under the app's User interface, the groups are under View and their Preview services under Client-side human service.
5. A Preview service runs.
6. The group's relabel saves, and a snapshot of it exists.
7. Bob's rebuild reports the group as changed in BAW and says what changed.
8. Bob waits for a yes before rebuilding, and asks keep or replace before installing.
9. After "keep", the label is still yours and Rewards Eligibility is required.
10. `git status` shows nothing new outside `work/`.

---

## References

[^reuse]: IBM, Developing reusable views (BAW 26.0.x). https://www.ibm.com/docs/en/baw/SS8JB4_26.0.x/com.ibm.wbpm.wle.editor.doc/topics/tcreatingviews.html
[^visibility]: IBM, Setting the visibility of coach views. https://www.ibm.com/docs/en/bpm/8.6.0?topic=views-setting-visibility-coach
[^options]: IBM, Configuration properties and configuration options. https://www.ibm.com/docs/en/SSFPJS_8.6.0/com.ibm.wbpm.wle.editor.doc/topics/c_config_options.html
[^snapshots]: IBM, Managing snapshots (BAW 23.x). https://www.ibm.com/docs/SS8JB4_23.x/com.ibm.wbpm.admin.doc/topics/managing_snapshots.html
[^mcp]: Model Context Protocol, Tools. https://modelcontextprotocol.io/specification/2025-06-18/server/tools
