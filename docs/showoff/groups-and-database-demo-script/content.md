# Demo script: from pictures to a Quote screen that remembers

A one-hour session for the client's team and their managers. Last session the team asked for **reusable, configurable pieces** they can maintain in IBM Business Automation Workflow (BAW). Today IBM Bob builds the client's Quote screen from pictures, as **reusable groups**, and makes it **remember** every quote. Then Bob adds a modern version with a widget it writes on the spot, fills the app's table with sample quotes right on the server, works on them together with the app, and shows that it cannot change BAW's own database.

1. **Act 1. Pictures in; a screen that remembers out.** Bob builds the app from pictures of the old screen, every section a reusable group, and saves each quote to the database. Submit a quote, then Load it back.
2. **Act 2. Modern, with a new widget.** Bob gives the same app a React and Carbon version of every group, and **writes a new Toggle widget** for the yes/no questions.
3. **Act 3. Your data, live in BAW.** Bob adds 20 quotes straight into the app's table on the server, and a question comes back as a table. A quote typed in the app is read by Bob, and Bob's change shows up in the app.
4. **Act 4. Safety.** Bob reads BAW's own database, and its attempt to change it is refused.

**How to read this script.** Each step tells you what to **do**, what to **paste** into Bob, what **Bob does**, and what to **say**. Text in quotes is meant to be said out loud. The pictures on the demo page come from a neutral example app; on the day, Bob builds from the client's own pictures.

---

## 1. Run of show

| Time | Part | What the room sees |
|---|---|---|
| 00:00 | Opening | What the team asked for, and today's goal |
| 02:00 | How it works | Toolkits, groups, and where the data lives |
| 07:00 | Act 1: pictures in, a screen that remembers out | The app built from pictures, in groups; a quote saved and loaded back |
| 23:00 | Act 2: modern, with a new widget | The same groups in React and Carbon, and a new Toggle in the toolkit |
| 40:00 | Act 3: your data, live in BAW | 20 quotes added on the server, and the table shown there; a question answered as a table; a quote typed in the app read by Bob, and Bob's change shown in the app |
| 49:00 | Act 4: safety | Bob reads BAW's own record of what we built today; its change there is refused |
| 52:00 | Questions | |
| 57:00 | Next steps | |

The timings are tight. If Bob runs long in Act 1 or Act 2, shorten Act 3 to Steps 1 and 2, one Load, and Step 6.

---

## 2. Before the meeting

Thirty minutes before:

1. Check the login file (`.env`) has the BAW and PostgreSQL settings. Never show it on screen.
2. Get the latest project (`git switch main && git pull`). Open it in Bob; the tools panel shows **baw-dev-tools** with **21 tools**. If it shows fewer, restart baw-dev-tools in that panel.
3. **Make sure the Toggle does not exist yet**, so Bob creates it live, and **start from an empty table**, so Bob creates it live. After a rehearsal, reset both:
   ```
   rm -f coach-ui/src/widgets/toggle.jsx coach-ui/src/widgets/toggle.scss coach-ui/widgets/icons/toggle.svg
   git checkout -- coach-ui/widgets/modernizer-widgets.json
   uv run --script server/pg_ops.py sql bawexternal "DROP TABLE IF EXISTS public.group_quote"
   ```
   The table holds only sample quotes and test quotes.
4. Keep `screenshots/Quote/` as it is: the six pictures of the old screen (`image (1).png` to `image (6).png`) and the client's newer quote screen (`generate-quote.png`). It stays on this laptop and is never published.
5. Keep only the two toolkit builds in `work/` (`ABW-1.0.4.twx` and the newest `MDW-*.twx`), so Bob reads nothing from earlier runs.
6. Pick a **new acronym** and put it in the Act 1 request (the script uses `ZZGDB`; use `ZZGDB2` after a rehearsal). Names already used on the test server:
   - Apps: ZZQI, ZZLGQ, ZZLGQI, ZZSLX, ZZGRP, ZZGRP2, ZZGWQ, ZZLGG, ZZGQ3, ZZGDEMO, ZZGDBR, ZZQDBR
   - App Builder Widgets (ABW): up to 1.0.4
   - Modernizer Widgets (MDW): up to 2.1.0, so Bob's new widget goes into 2.2.0 or later
7. In Bob's auto-approve settings, allow mode switches, and keep **change_system_db** off, so Bob must ask. Act 4 relies on it.
8. Open Workflow Center (Business Automation Studio) in a second browser tab. Nothing else is needed on stage: every step runs on the server.
9. In Bob, pick the **🏗️ BAW App Builder** mode. Make the font bigger.
10. Do one full rehearsal, so you know how long each step takes. Then repeat step 3 and pick a new acronym. Afterwards, ask a BAW admin to archive the test apps: Bob cannot delete apps or snapshots.

---

## 3. Opening (2 min)

**Say.**
- "Last time you asked for reusable pieces: small widgets combined into larger groups, so the same information isn't rebuilt on every screen, and something your developers can maintain in BAW."
- "Today Bob builds your Quote screen from pictures, made of reusable groups, and this time the screen remembers what people type."
- "Then a modern version, with a widget Bob writes during the demo, your existing data brought in, and a look at the safety rules."

---

## 4. How it works (5 min)

**Do.** Show the diagram.

**Say.**
- "Bob uses two kinds of reusable pieces: **widgets**, in a toolkit every app can use, and **groups**, Views inside your app that combine those widgets."[^reuse]
- "Each placement of a group has its own settings: optional fields can be hidden, and the whole group can be read-only. The form shows a group editable; the review shows the same group read-only."[^visibility][^options]
- "The platform already has a database server. One database on it, the app database, is set aside for your apps' data: Bob can read and write there. BAW's own records are on the same server; Bob can read them but not change them."
- "Once the app is built it doesn't need Bob: it saves and loads through BAW's own connection to the app database."

| Piece | Where it lives | What it is |
|---|---|---|
| App Builder Widgets (ABW) | A toolkit | Classic BAW: Section, Review List, Button Bar and more |
| Modernizer Widgets (MDW) | A toolkit | React + Carbon: Text Field, Select, Checkbox, Date Field, Button and more |
| A group, e.g. "Group Eligibility" | Your app, as a View | Fields bound to the app's data, placed on any step |
| App database (`bawexternal`) | The platform's database server | Your apps' data, such as today's quotes. Bob reads and writes |
| BAW's own database (`basdb`) | The same server | BAW's apps, versions and history. Bob reads only |

**Say.** "Bob has 21 tools and two roles, App Builder and Modernizer. The ones that change something important ask a person first."

---

## 5. Act 1: pictures in, a screen that remembers out (16 min)

### Step 1. Show the old screen

**Do.** Flip through the six pictures: one long "Info" tab of a quote in an old CRM, captured while scrolling. Point at the yes/no checkboxes (ERISA group?, Union group?, Reinsurance Declined). We come back to those in Act 2.

**Say.** "All we have is pictures. The pictures are the requirement. And today the screen should also remember every quote."

### Step 2. Ask Bob

**Paste.**

> Build a ZZ app from the screenshots in screenshots/Quote, image (1).png to image (6).png. They show one long page, scrolled, so some parts appear twice. Build it from App Builder Widgets, with the acronym ZZGDB. Add a review screen before Final Val., and make each section a reusable group so we can reuse it on other screens. Add a Group Name field at the top, and save every quote to a new table group_quote in bawexternal, keyed by Group Name, so a saved quote can be loaded again. Show me the design first.

**Bob does.**
1. Opens each picture and reads the screen: sections, columns, drop-downs, checkboxes. Reads the colours and the logo file. Looks at the app database: there is no `group_quote` table yet.
2. Writes the design: **the groups** (each section, its fields, editable on the form, read-only on the review) and **the table** (its key, Group Name, and one column per field).
3. **Stops and shows us the design**, with a few questions.

**Paste**, to answer them.

> Approved. Use the built-in template, build only the Info. tab, and leave out the product name. Create the table, install the app and test it, compare it with the screenshots, and delete your test quote when you are done.

**Say, while it works.**
- "Bob reads the pictures the way a developer would, and designs the table from the form itself. Nobody writes database code."
- "It doesn't build anything before we approve the design."

### Step 3. Build, install and test

**Bob does.**

| Order | Bob's step | Tool |
|---|---|---|
| 1 | Builds the app: one View and one Preview service per group, a **Load** button, and saving on Submit | `create_app` |
| 2 | Creates the table, and checks it matches the design | `run_sql`, `describe_table` |
| 3 | **Asks before installing.** Answer yes | `install_app` |
| 4 | Opens it in a real browser, clicks through, compares it with the pictures, and deletes its test quote | `test_service`, `run_sql` |

**Say.** "About 60 fields in 8 or 9 groups, in the same layout and colours, and a table with a column for each."

### Step 4. Save a quote, then load it back

**Do.**
1. Open the app. Type **Lighthouse Bakery Co** as the Group Name, pick a Proposed Rating Method, tick **ERISA group?**, press Review, then Submit. The confirmation shows a reference number.
2. Open the app again: an empty form. Type **Lighthouse Bakery Co** and press **Load**. Everything comes back.

**Say.** "That quote now lives in the database, not in someone's inbox or spreadsheet. And the review placed the same groups, read-only."

### Step 5. The groups in BAW (optional, if time allows)

**Do.** In Workflow Center, open the app, **User interface**: the groups under **View**, a Preview service per group under **Client-side human service**. Run one Preview.

**Say.** "These are ordinary BAW views. Your developers can open a group, change its fields, and every screen that uses it follows. Bob got us here fast; BAW owns the result."

---

## 6. Act 2: modern, with a new widget (17 min)

### Step 1. Show the target look

**Do.** Open `screenshots/Quote/generate-quote.png`, the client's newer quote screen. Point at the tabs, the fields side by side and the buttons at the bottom right. Then point at the three yes/no checkboxes. Stay in the same chat.

**Say.** "A checkbox is a poor fit for a yes/no question. A switch reads better, and nobody has one in the toolkit yet."

### Step 2. One request: modernize, keep the groups, create the widget

**Paste.**

> Give the app you just built a React UI with IBM Carbon, from Modernizer Widgets, and keep its reusable groups. Lay it out like screenshots/Quote/generate-quote.png: the sections as tabs, the fields side by side, the client's blue from that screen on a white page, Submit and Cancel at the bottom right. Show the yes/no questions (ERISA group?, Union group?, Reinsurance Declined) as a Carbon toggle switch with Yes and No. No Modernizer Widget does that yet, so add a new Toggle widget to the toolkit that other apps can reuse. Keep Load on the classic screen only: leave the Load button and the database message out of the modern copy. Show me the plan before you build.

**Bob does.**
1. **Switches to its second role**, the Modernizer, by itself.
2. Reads the app it just built: every step, and **every group** with its fields and placements.
3. Plans the modern screens, a modern copy of each group, and the **new Toggle widget**.
4. **Stops and shows us the plan.**

**Say, while it works.** "Bob found the groups by itself. The modern version keeps the same structure: the same groups, placed the same way."

### Step 3. Build it

**Paste.**

> Approved. Build it, install it and test it, and delete your test quotes when you are done.

**Bob does.**

| Order | Bob's step | Tool |
|---|---|---|
| 1 | Writes the Toggle: its React component with Carbon's toggle, its styles, one entry in the toolkit's list, and a palette icon | (files) |
| 2 | Checks every widget in a browser, the new one included | (offline check) |
| 3 | Builds a **new** Modernizer Widgets version that contains the Toggle | `build_widget_toolkit` |
| 4 | **Asks before installing the toolkit.** Answer yes | `install_app` |
| 5 | Builds the modern screens, and a "(Modernized)" copy of every group, with toggles on the three questions | `modernize_app` |
| 6 | **Asks before installing the app.** Answer yes | `install_app` |
| 7 | Tests every step in a real browser, then deletes its test quotes | `test_service`, `run_sql` |

**Say, while it works.**
- "Bob is writing a real BAW widget, not a picture of one. It uses IBM's Carbon toggle, which is meant for exactly this: an on/off choice."[^toggle]
- "It tests the widget before it builds the toolkit, so a broken widget never reaches BAW."

### Step 4. The reveal

**Do.**
1. Run the "(Modernized)" version. Show the tabs and the groups with their fields side by side. Flip **ERISA group?** to Yes. Carry on to the review: the groups are read-only, and it shows "Yes".
2. In Coach Designer, search the palette for "Modernizer": the **Toggle** is there with its icon. Drag one onto a step; show **On text** and **Off text**.

**Say.**
- "Twenty minutes ago this widget did not exist. Now it is in your toolkit, with an icon, a preview and options, like IBM's own."
- "The modern copy saves on Submit too. Loading a saved quote stays on the classic screen for now."

---

## 7. Act 3: your data, live in BAW (9 min)

### Step 1. Fill the table, on the server

**Paste.**

> Add 20 made-up employer groups to the group_quote table, directly in the database. Make the first one Northwind Logistics, Self-Funded. Fill the rating method, the commissions and the yes/no questions from the app's own choices, so every quote opens in the app. Then tell me how many quotes the table holds.

**Bob does.** Reads the table's columns (`describe_table`) and the app's choices, adds the 20 quotes in one statement (`run_sql`), then counts: **21 quotes in all**, counting Lighthouse Bakery from Act 1.

**Say.**
- "No spreadsheet on anyone's laptop, no upload. Bob wrote straight into the database the BAW app uses, on the server."
- "One statement, so it's all or nothing: if one quote were wrong, none would go in."

### Step 2. Look inside the database server

**Paste.**

> Show me the databases on the server, and which one our app uses. Then show me 10 quotes from group_quote: group name, rating method and reference number.

**Bob does.**
- Lists the server's databases with their sizes (`list_tables`): 33 on the test server. They include BAW's own `basdb`, the largest, and `bawexternal`, the app database, which is the only one marked writable.
- Shows 10 quotes as a table (`run_sql`).

**Say.**
- "This is the platform's database server, not a copy on this laptop. BAW keeps its own records here too, in basdb."
- "Bob can read all of them, and it writes to one: the app database, where these quotes live."

### Step 3. Open one in the app

**Do.** In the classic app, type **Northwind Logistics** and press **Load**. The fields Bob filled come back on every tab, with Self-Funded as the rating method.

**Say.** "Bob put it in the database a minute ago, and the BAW app opens it like any other quote."

### Step 4. Ask in plain English

**Paste.**

> Which rating methods do our quotes use, and what is the average medical commission percentage for each?

**Bob does.** Writes a query (`run_sql`) and answers with a table. The numbers depend on the quotes Bob made up; it looks like this:

| Rating method | Quotes | Average medical commission |
|---|---:|---:|
| Fully Insured | 9 | 4.33% |
| Self-Funded | 7 | 3.86% |
| Level Funded | 4 | 4.63% |

**Say.** "No report request, no waiting. If you ask, Bob shows the query it ran, so an analyst can check it."

### Step 5. The app writes, Bob reads

**Do.** In the classic app, start a new quote: type **Juniper Street Clinic** as the Group Name, pick **Fully Insured**, press Review, then Submit. Leave the confirmation, with its reference number, on screen.

**Paste.**

> Is Juniper Street Clinic's quote in the table? Give me its rating method and reference number.

**Bob does.** Reads the table (`run_sql`): Juniper Street Clinic, Fully Insured, and the same reference number as the confirmation.

**Say.** "I typed that into BAW a few seconds ago. Bob reads the same table the app saves to: no export, no copy."

### Step 6. Bob writes, the app reads

**Paste.**

> Northwind Logistics is moving to Level Funded. Update its quote in the table.

**Bob does.** Changes that one row (`run_sql`) and confirms: **1 row updated**.

**Do.** Open the classic app again, type **Northwind Logistics** and press **Load**. The rating method now reads **Level Funded**; in Step 3 it was Self-Funded.

**Say.** "Bob changed the data, and the BAW screen shows it straight away. One set of data, two ways in: the screen for your team, plain English for everyone else."


### Full talk track

Word for word, about 9 minutes. Actions are in italics.

**Opening** (30 s)

"So far we've built a screen, and we've made it look modern. But a screen is only half the story. The other half is the data behind it: every quote your team saves has to live somewhere."

"For the next few minutes, I'll show you where that data lives and how Bob works with it. Everything you'll see runs on the server. Nothing comes from my laptop."

**Step 1. Fill the table** (1½ min)

*Paste the Step 1 request.*

"Right now our app has exactly one quote in it, the one we saved a few minutes ago. To make this realistic, I'm asking Bob to add twenty made-up employer groups, the kind of quotes your team handles every week."

*While Bob works:*

"Notice what I didn't do. I didn't open a spreadsheet, export a file or upload anything. I asked for it in a sentence. Bob looks at the table first, to see what columns it has and which choices the app allows, so every quote it adds is one the app can open."

*When Bob answers with 21 quotes:*

"Twenty-one: the twenty Bob just added, plus ours from earlier. And Bob did it in one step, so it's all or nothing. If one quote had been wrong, none of them would have gone in. You never end up with half a batch."

**Step 2. Look inside the database server** (1½ min)

*Paste the Step 2 request.*

"People always ask me: where is this data, really? Let's look."

*When the list of databases appears:*

"This is the platform's database server, the real one, not a copy. Every product on the platform keeps its data here. This big one, basdb, is BAW itself: every app, every version and every task."

"And this one, bawexternal, is the app database, where our quotes live. It's the only one marked writable. Bob can read everything on this server, but it's only allowed to change data in one place."

*When the quotes table appears:*

"And here are the quotes themselves, straight out of the table: group name, rating method and reference number."

**Step 3. Open one in the app** (1 min)

*In the classic app, type Northwind Logistics and press Load.*

"Now, the question that matters: does the app see it? Northwind Logistics is one of the quotes Bob added a minute ago. I type the name, and press Load."

*When the form fills in:*

"There it is, on every tab, with the rating method set to Self-Funded. The app doesn't know or care that Bob added it. It's simply a quote in the database."

**Step 4. Ask in plain English** (1½ min)

*Paste the Step 4 question.*

"Now imagine you're a manager and you want a quick answer: which rating methods are our quotes using, and what's the average commission for each? Today that's usually a report request, and a few days of waiting."

*When the table appears:*

"Here's the answer, in seconds. The numbers are made up today, but the question is real. And if anyone wants to check the work, Bob can show the exact query it ran, so an analyst can verify it."

**Step 5. The app writes, Bob reads** (1½ min)

*In the classic app, enter Juniper Street Clinic, pick Fully Insured, press Review, then Submit. Leave the confirmation on screen.*

"So far data has gone from Bob into the app. Let's go the other way. I'm a team member entering a brand-new quote, Juniper Street Clinic, the normal way, in BAW. I submit it, and BAW gives me a reference number. Remember it."

*Paste the Step 5 question. When Bob answers:*

"Same group, same rating method, same reference number. I typed that into BAW ten seconds ago, and Bob is reading it straight from the table the app saves to. No export, no copy, no waiting for a nightly job."

**Step 6. Bob writes, the app reads** (1½ min)

*Paste the Step 6 request.*

"Last one. Say Northwind Logistics calls and tells us they're switching to Level Funded. Instead of opening the quote and editing it, I just tell Bob."

*When Bob confirms one row updated:*

"One quote changed, and only that one."

*In the classic app, load Northwind Logistics again.*

"Back in BAW, I load Northwind again. A minute ago it said Self-Funded. Now it says Level Funded."

"So that's the point of this act: one set of data with two ways in. Your team uses the screen, and anyone else can just ask in plain English. Either way, it's the same data on the same server."

**Bridge to Act 4** (15 s)

"You might be thinking: if Bob can change data this easily, what stops it from changing something it shouldn't? That's exactly what I'll show you next."

**If something goes off-script**

- Bob is slow in Step 1: “It's checking the table's design first, so it doesn't add anything the app can't open. That's the careful part.”

- Bob asks which fields to fill: “The rating method, the commissions and the yes/no questions. Leave the rest empty.”

- Short on time: do Steps 1, 2, 3 and 6. Together they still show the data on the server and changes going both ways.

---

## 8. Act 4: safety (3 min)

**Paste.**

> What did we build in BAW today? Read it from BAW's own database.

**Bob does.** Reads `basdb`, BAW's own records, and lists today's versions with their times: the app's versions from Acts 1 and 2, and the new Modernizer Widgets version that holds the Toggle. In the rehearsal: ZZGDB3 1.0.0 to 1.0.5 and MDW 2.2.0, all within 25 minutes.

**Say.** "That's BAW's own record of the last forty minutes, and Bob reads it directly. The same goes for audits: what was installed, by whom, and when."

**Paste.**

> Now rename the app you built directly in BAW's database. Use run_sql only.

**Bob does.** Tries, and the database refuses: **basdb is read-only for Bob**. In the rehearsal it answered:

```text
cannot execute UPDATE in a read-only transaction.
basdb is read-only for Bob. Write in bawexternal, or use change_system_db.
```

**Say.**
- "The refusal comes from the database itself, not from Bob being polite. Bob's login there is read-only."
- "When a change there really is needed, Bob must ask a person first, and it saves a backup before it writes anything."

**If** Bob offers to make the change with its approval tool, say no, or press Deny. "That's the point: a person decides."

---

## 9. Safety and questions (5 min)

| Safety rule | Why it matters |
|---|---|
| A person approves every design, plan and install | Bob stops before building and before installing |
| Every install is a new version | Nothing is overwritten; you can always go back |
| Bob adds widgets, never changes existing ones, and tests a new one first | Apps that depend on a widget keep working; a broken widget never reaches BAW |
| Bob writes only in the app database | BAW's own records and the other products' databases are read only for its login |
| A change to a system database asks a person first, and backs up first | Nothing changes there without a decision and a way back |
| Every write is one statement, all or nothing | A bad batch of data never half-lands |
| The app's Load and Save run fixed statements | Nobody can make the app run their own SQL |
| Passwords stay in the connector | Bob never sees them |

**Questions to expect**

- *Can smaller widgets be combined into larger reusable ones, keeping configuration and data binding?* Yes. A group is a View made of field widgets, bound to the app's data, with a visibility setting per field and a read-only setting per placement.[^reuse][^options] Groups inside groups, and repeating groups (lists), are not built yet.
- *Which changes can we make in BAW, and which need Bob?* Changes to a group's fields are yours: on its next rebuild Bob keeps your version and asks before replacing it. Other edits, such as help text or choice lists, belong in Bob's design, because a rebuild replaces them.[^snapshots]
- *Can a group be shared across apps?* Not yet: groups live in one app. Widgets are shared, through the toolkit.
- *Where is our data?* On the platform's own database server, in the app database. Not on this laptop, and not inside Bob.
- *Can Bob break BAW?* Its login can only read BAW's databases. A change there needs a person's approval, and a backup is taken first.
- *Does Bob ask before every change to the app database?* Not by default, because it's where we test. That's a setting: in production, turn on asking for those tools too.
- *Does the modern screen load saved quotes?* Not yet. It saves on Submit; Load is on the classic screen.
- *Other databases, such as Oracle or Db2?* Today, PostgreSQL only.
- *Can other AI assistants do this?* Yes. The connector follows the open MCP standard, so any assistant that supports MCP can use the same 21 tools.[^mcp]

**If something breaks on stage**

| Problem | What to do |
|---|---|
| Bob's tools panel shows fewer than 21 tools | Restart baw-dev-tools in that panel |
| Bob proposes no groups | Say: "Make each section a reusable group." |
| Bob says the table exists with other columns | The table was not reset. Run the last line of prep step 3, then ask again |
| Bob uses a Checkbox instead of a new widget | Say: "No, add a new Toggle widget to Modernizer Widgets for those three questions." |
| The modern copy shows a Load button or a "Db Message" tab | Say: "Leave the Load button and the database message out of the modern copy, and rebuild it." Load there would not fill the form |
| The new widget fails its check twice | Bob falls back to the stock Checkbox and finishes. Carry on; show the Toggle in the rehearsal app instead |
| Bob asks which fields to fill | Say: "The rating method, the commissions and the yes/no questions. Leave the rest empty." |
| Bob adds the quotes one at a time | Say: "Add them all in one statement." |
| Bob's insert fails with "duplicate key" | The quotes are there from a rehearsal: the table was not reset. Carry on with Step 2 |
| Load says "No record found" | The name must match exactly, including capitals: "Northwind Logistics" |
| "Snapshot already exists", or the acronym is taken | Give Bob a new acronym: a safety rule working |
| An install or the first database answer is slow | Talk through the diagram while it runs |

---

## 10. Next steps (3 min)

**Do.** Ask the room, and write the answers down:
1. Which information repeats across your screens? Those are your first groups.
2. Which forms should remember their data first, and which spreadsheets belong in an app?
3. Which questions wait for a report today?
4. Who on your team will own the groups and the toolkit?
5. What data must never go into the app database, such as personal or health data?

**Say.** "In one hour: pictures became a BAW app made of reusable groups that remembers every quote, a modern version made of the same groups with a widget Bob wrote, Bob filled the app's table on the server and read and changed the data the BAW app works with, in plain English. Bob read BAW's own records, which stayed untouched, and a person approved every step that mattered."

Project: https://github.com/unclethien/baw-bob-dev-tools-mcp (Apache-2.0). Not an official IBM project; use it with test servers and test apps.

---

## Rehearsal checklist

1. Bob's design lists the groups and the table (key Group Name, a column per field) before anything is built.
2. Bob creates the table, asks before installing, and deletes its test quote.
3. A submitted quote shows a reference number, and Load brings it back.
4. Bob switches to the Modernizer by itself and reads every group back.
5. Bob's plan lists the modern groups and the new Toggle, and leaves Load out of the modern copy.
6. Bob builds a **new** Modernizer Widgets version and asks before each install.
7. The modern copy's tabs lay the groups out side by side, a flipped toggle reads "Yes" on the review, and the Toggle is in the palette.
8. Bob adds the 20 quotes in one statement; the table holds 21.
9. Bob lists the server's databases with `bawexternal` as the only writable one, and shows 10 quotes as a table.
10. Northwind Logistics loads in the classic app as Self-Funded.
11. The rating question comes back as a table.
12. Bob reads back Juniper Street Clinic with the reference number the app showed; after Bob's update, Northwind Logistics loads as Level Funded.
13. Bob lists today's versions from BAW's database, and its rename there is refused.
14. Afterwards: the Toggle files and the table are reset (prep step 3), and the test apps are archived.

---

## References

[^reuse]: IBM, Developing reusable views (BAW 26.0.x). https://www.ibm.com/docs/en/baw/SS8JB4_26.0.x/com.ibm.wbpm.wle.editor.doc/topics/tcreatingviews.html
[^visibility]: IBM, Setting the visibility of coach views. https://www.ibm.com/docs/en/bpm/8.6.0?topic=views-setting-visibility-coach
[^options]: IBM, Configuration properties and configuration options. https://www.ibm.com/docs/en/SSFPJS_8.6.0/com.ibm.wbpm.wle.editor.doc/topics/c_config_options.html
[^snapshots]: IBM, Managing snapshots (BAW 23.x). https://www.ibm.com/docs/SS8JB4_23.x/com.ibm.wbpm.admin.doc/topics/managing_snapshots.html
[^toggle]: Carbon Design System, Toggle usage. https://carbondesignsystem.com/components/toggle/usage
[^mcp]: Model Context Protocol, Tools. https://modelcontextprotocol.io/specification/2025-06-18/server/tools
