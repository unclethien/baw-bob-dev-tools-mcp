# Demo script: from screenshots to a working BAW app

A one-hour demo for managers. IBM Bob, an AI assistant, turns pictures of an old screen into a working app in IBM Business Automation Workflow (BAW), puts it into an approval workflow, then gives it a modern look with smart fields. You explain how it works first, then keep talking while Bob works.

**How to read this script.** Each step tells you what to **do**, what to **paste** into Bob, what **Bob does**, and what to **say**. Text in quotes is meant to be said out loud.

---

## 1. Run of show

| Time | Part | What the room sees |
|---|---|---|
| 00:00 | Opening | Why we are here |
| 02:00 | How it works | Bob, the connector, and BAW |
| 06:00 | What Bob can do | Bob's tools and its two specialist roles |
| 12:00 | How to ask Bob | The five parts of a good request |
| 15:00 | Demo 1: rebuild the old screen | Pictures in, working BAW app out, then a two-step approval workflow |
| 30:00 | Demo 2: a modern version | The same app with a modern look and fields that react |
| 48:00 | Safety and questions | |
| 52:00 | Next steps | What the client wants next |

---

## 2. Before the meeting

Thirty minutes before:

1. Check the BAW login file (`.env`) is filled in. Never show it on screen.
2. Open the project in Bob. The tools panel shows **baw-dev-tools** with 14 tools.
3. Put the six pictures of the old screen (`image (1).png` to `image (6).png`) and the client's newer quote screen (`generate-quote.png`) in `screenshots/Quote/`. Keep nothing else in that folder. It stays on this laptop and is never published.
4. Do one full rehearsal, so you know how long each step takes. Keep the rehearsal apps as a backup.
5. Open Business Automation Studio in a second browser tab.
6. In Bob, pick the **🏗️ BAW App Builder** role, and allow mode switches in Bob's auto-approve settings. Make the font bigger.
7. Afterwards, ask a BAW admin to archive the test apps: Bob cannot delete anything.

---

## 3. Opening (2 min)

**Say.**
- "Today we rebuild a real screen from an old CRM, using only pictures of it. Then we give it a modern look."
- "We planned two working sessions for this. Bob is fast enough to do both in one hour."
- "First, five minutes on how it works, so you can follow every step."

---

## 4. How it works (4 min)

**Do.** Show the diagram slide: Bob, the connector, BAW.

**Say.**
- "Bob is an AI assistant. On its own, it cannot touch BAW."
- "We gave it a connector. The connector follows an open standard called MCP, which is like a USB port for AI assistants: plug in a connector, and the assistant gets new tools."
- "Our connector gives Bob 14 tools to build, install and test BAW apps. It holds the BAW password, so Bob never sees it."
- "Bob never writes BAW code by hand. It writes a short description of the screen, and the connector turns that into a real BAW app."

**Do.** Open Bob's tools panel and show **baw-dev-tools** with its 14 tools.

---

## 5. What Bob can do (6 min)

**Say.** "Bob's 14 tools fall into four groups."

| Group | In plain words |
|---|---|
| Look at BAW | See which apps and versions exist, and download one |
| Look at pictures | Open a screenshot, read its exact colours, cut out a part such as a logo |
| Build | Turn a description into an app, read an app back into a description, build the modern screens |
| Run on BAW | Install an app, and test it in a real browser by clicking through every screen |

**Say.** "Bob also has two specialist roles. Each one has its own instructions and can only change its own files."

| Role | What it does |
|---|---|
| 🏗️ BAW App Builder | Turns a request or pictures into a working app, with a workflow if needed |
| ✨ BAW Coach Modernizer | Gives an existing app a modern look, as a new copy next to the old one |

**Say.**
- "Most tools only look. The ones that change something ask first."
- "Bob also stops twice by itself: it shows us the design before building, and asks before it installs anything on BAW."
- "When the job changes, Bob switches role by itself."

---

## 6. How to ask Bob (3 min)

**Do.** Put the first demo request on screen.

**Say.** "A good request has up to five parts. You describe the result, not the steps: Bob picks its own tools."

| # | Part | In our first request |
|---|---|---|
| 1 | What you want | "Build a ZZ app" |
| 2 | What to work from | "from the screenshots in screenshots/Quote, image (1).png to image (6).png" |
| 3 | What Bob cannot see | "They show one long page, scrolled, so some parts appear twice." |
| 4 | How it should look and behave | (nothing here: the pictures say it all; demo 2 adds this) |
| 5 | How far to go | "Install it, test it and compare the result with the screenshots." |

**Say.** "One goal per request. When Bob stops to check with us, we just answer 'Approved.'"

---

## 7. Demo 1: rebuild the old screen (15 min)

### Step 1. Show the old screen

**Do.** Flip through the six pictures: one long "Info" tab of a quote in an old CRM, captured while scrolling. Point at the drop-down lists, the checkboxes and the rewards list.

**Say.** "This screen lives in an old CRM. All we have is pictures of it."

### Step 2. Ask Bob to rebuild it

**Paste.**

> Build a ZZ app from the screenshots in screenshots/Quote, image (1).png to image (6).png. They show one long page, scrolled, so some parts appear twice. Install it, test it and compare the result with the screenshots.

**Bob does.**
1. Opens each picture and reads the screen: sections, columns, which field is a drop-down, which is required.
2. Reads the colours from the pictures.
3. Writes a short description of the screen, then **stops and shows us the design**.

**Say, while it works.**
- "Bob reads the pictures the way a developer would."
- "Notice that we did not list any fields or colours. The pictures are the requirement."

**Do.** When Bob stops, scroll through its design summary. Answer: "Approved."

### Step 3. Build, install and test

**Bob does.**
1. Builds the BAW app from its description.
2. **Asks before installing it on BAW.** Answer yes.
3. Installs it, then opens it in a real browser, clicks through it and takes a picture of every screen.
4. Puts its picture next to the originals and fixes anything that differs.

**Say, while it works.**
- "Nothing reaches BAW until a person says yes."
- "This is a real browser on the real server, clicking the real buttons. Bob checks its own work."

**Do.** Show Bob's test picture next to the originals.

**Say.** "About 60 fields in 7 sections, the same layout and the same colours. Bob also tells us what it guessed, such as drop-down options it could not see, because the pictures only show the selected value."

### Step 4. Put it in an approval workflow

**Paste.**

> Put this screen in a workflow: Sales fills it in, then Underwriting reviews it and approves it or sends it back to Sales with comments. Import it and run it once with a send-back.

**Say.** "We describe the process the way we would to a colleague: who does what, and what happens when it is sent back."

**Bob does.**
1. Adds the workflow, **stops and shows us the steps**. Answer: "Approved."
2. Builds a new version and **asks before installing it**. Answer yes.
3. Runs the workflow once: fills the form, sends it back, fills it again, approves it.

**Do.** While Bob runs it, open Business Automation Studio, the new app, then **Processes**. Show the two lanes, Sales and Underwriting, the review step and the "send back" path. Drag a box a little to show it can be edited, then undo.

**Say.**
- "This is a normal BAW workflow, not a picture. Our developers can open it and change it like anything they built themselves."
- "Bob ran it the way people will: the work went to Underwriting, came back to Sales, and was approved the second time."

---

## 8. Demo 2: a modern version (18 min)

**Say.** "We planned this for a second session. Let's do it now."

### Step 1. Show the target look

**Do.** Open `screenshots/Quote/generate-quote.png`: the client's newer quote screen, the layout they already like. Point at the tabs across the top, the four columns and the buttons at the bottom right. Stay in the same chat.

### Step 2. Ask for the modern version

**Paste.**

> Give the app you just built a React UI with IBM Carbon components. Lay it out like screenshots/Quote/generate-quote.png, the client's newer quote screen: the fields split into tabs by section, four columns, labels close to their fields, the title in the header, Submit and Cancel at the bottom right. Use a clean look in the client's blue from that screen, on a white page. Improve the labels and add help text and validation. Show me the plan before you build.

**Say.** "This request has all five parts: what we want, what to work from, how it should look, extras like help text, and where to stop."

**Bob does.**
1. **Switches to its second role**, the Modernizer, by itself.
2. Opens the client's screen and reads its blue.
3. Reads the app it just built, plans the tabs and the four columns, and improves the labels, help text and checks.
4. **Stops and shows us the plan.**

**Say, while it works.**
- "Bob changed role by itself. Same conversation, same app."
- "React and Carbon are the modern web technology and IBM's design system. Only the screen changes; the process behind it stays the same."

### Step 3. Build it

**Paste.**

> Approved. Build the modern screen, then install it and test it.

**Bob does.**
1. Writes the modern screen and checks that it compiles.
2. Adds it to the app as a new copy, next to the old screen.
3. **Asks before installing.** Answer yes.
4. Tests it in a real browser: types sample values and presses every button.

**Do.** In Business Automation Studio, run the "(Modernized)" version. Fill a few fields, leave a required one empty and press Submit to show the check, then complete it.

**Say.**
- "The layout is the client's own newer screen. The old process keeps running underneath; only what people see has changed."
- "The old screen is still there next to the new one, so nothing is lost."

### Step 4. Fields that react to each other

**Paste.**

> Now make the screen react to what the user enters:
> - Add an Other choice to each benefit dropdown. Show its "Other" box only when Other is chosen, and make it required then.
> - Show the commission $ and % boxes only when the broker commission is Custom.
> - Keep the Reward Programs tab locked until a Reward Delivery Method is chosen.
> - Show on each tab how many required fields are still empty, and when Submit finds a problem, open the first tab that has it.
>
> Build, install and test it.

**Say.** "Business rules, one per line, in the words users see."

**Bob does.** Adds the rules to the screen, builds a new version, **asks before installing**, then tests it.

**Do.** Run it. Pick "Other" in a drop-down and watch its box appear. Set the commission to Custom and watch two boxes appear. Leave a required field empty, go to the last tab and press Submit: the screen jumps back to the right tab.

**Say.** "The rules react instantly, and the data still lands in the same place in BAW, so the process does not change."

Agree the exact rules with the client before the session; the request above uses examples from the Info tab.

---

## 9. Safety and questions

| Safety rule | Why it matters |
|---|---|
| Bob asks before changing an app it did not build | Your existing apps stay as they are unless you say yes |
| Every install is a new version | Nothing is overwritten; you can always go back |
| Bob cannot delete anything | No tool for it exists |
| The password stays in the connector | Bob never sees it |
| A person approves every change | Bob stops before building and before installing |

**Questions to expect**

- *Does Bob write the BAW code itself?* No. It writes a short description; the connector builds the app from standard BAW parts.
- *Is the workflow real?* Yes. It opens in Studio like any other BAW process, and developers can change it.
- *Can it read from or save to a database?* Not yet. That is the next step, and it needs a database connection set up on the BAW server.
- *What can it not build from a picture yet?* Tables, file uploads, links and extra buttons. Bob lists them and offers to add them in the modern screen.
- *Does it work with our existing apps?* It can read any app and describe it. It only installs into test copies.
- *Can other AI assistants use it?* Yes. The connector follows the open MCP standard, so any assistant that supports MCP can use the same 14 tools.[^mcp]
- *What happens when something goes wrong?* Bob gets a plain error message, fixes its description, and tries again.

**If something breaks on stage**

| Problem | What to do |
|---|---|
| Bob's tools panel shows 0 tools | Restart baw-dev-tools in that panel |
| "Login failed" | Check the login file off screen; switch to the rehearsal app meanwhile |
| "Version already exists" | Let Bob pick the next version number: that is a safety rule working |
| Bob says fields need attention | A required field was empty; Bob adds sample values and tries again |
| An install is slow | Talk through the diagram slide while it runs |
| The workflow run does not finish | Show the workflow in Studio anyway; it does not depend on the test run |

---

## 10. Next steps

**Do.** Ask the client, and write the answers down:
1. Does the rebuilt screen match the old one? Which drop-down options did Bob guess wrong?
2. Should the production screen use their own brand? Can they send the official logo?
3. Which fields drive other fields, and which tabs depend on each other, in the real process?
4. Which screen comes next?
5. Which data should come from a database, and from which system?

**Say.** "In one hour: pictures became a BAW app with a real workflow, then a modern screen with smart fields. Every step was tested in a browser and approved by a person before it reached BAW."

Encore, if there is time:

> Build a small ZZ app for an office supply request: one step with requester name, item, quantity and needed-by date, then a review screen. Install it and test it.

Project: https://github.com/unclethien/baw-bob-dev-tools-mcp (Apache-2.0). Not an official IBM project; use it with test servers and test apps.

---

## References

[^mcp]: Model Context Protocol, an open standard for connecting AI assistants to tools. https://modelcontextprotocol.io/specification/2025-06-18/server/tools
