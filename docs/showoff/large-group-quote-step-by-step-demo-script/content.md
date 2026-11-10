# Demo script: IBM Bob builds the Large Group quote app step by step from the client's Word document

The client wants to see how much of the BAW work IBM Bob generates, so their developers do not have to build all the BAW artifacts by hand. In this demo Bob reads the client's own Word document and screenshots, and builds the app one heading of the document at a time: the process, each business object, each Coach View, the client-side human service, the validations, and then a run of the whole workflow. After every step Bob shows what it made and waits for you.

The script has six parts:

1. **The input.** What the client gave Bob, and the prompt that starts the run.
2. **Bob builds the app, step by step.** Eight steps, one per heading of the document. You check each one.
3. **Show the result in BAW.** Ten checks, each with the place to click in Workflow Center.
4. **The live moment.** You use the finished app in Workplace.
5. **What Bob generated, and what is still open.**
6. **If it breaks, and the rehearsal checklist.**

This replaces the earlier scripts in `../large-group-quote-demo-script/`. The app is the same: Start, Generate Quote, Review Quote, End, with two tasks. The difference is that Bob now follows the document's headings and stops after each one.

**Status.** The app this script builds was checked on the test server on 6 November 2026, with a test app of the same shape. In the first Bob rehearsal, Bob stopped after every step and the app installed and passed its tests. The import offers at steps 3, 5 and 6 were added after it and have not been rehearsed yet. The tab change at step 7 was checked on the test server with a small test app on 10 November 2026, but not yet with Bob. After the next rehearsal, fill in the timings and fix any wording that does not match what Bob shows.

**How to read this script.** **Do** is what you click or type. **Paste** is text you paste into Bob. **Bob does** is what Bob does on its own. **Bob shows** is what Bob puts in the chat for you to check. **Say** is what you say aloud to the room. The pictures were taken during a rehearsal, with the client's logo hidden.

---

## 1. Before the meeting

Thirty minutes before:

1. **Restart Bob IDE.** Bob then runs the current `baw-dev-tools` MCP server and the current App Builder rules. Check that the server is connected.
2. **Check the App Builder Widgets toolkit (ABW).** Its snapshot must be installed on the BAW server, with its `.twx` file in `work/`. If it is missing, Bob builds and installs it with `build_widget_toolkit` and `install_app`. That adds a few minutes.
3. **Pick an acronym that nobody has used.** It must start with ZZ. This script uses `ZZLGE`. If an app with that acronym already exists on the server, pick another one and change the prompt.
4. **Put the client's files in `screenshots/Quote/`.** This folder stays out of the repository. It holds the Word document, the two screenshot references and the logo.
5. **Know your answers.** Bob stops at the end of each of the eight steps. At steps 3, 5 and 6 it also asks whether to import what it has built so far into BAW, so you can look at it there. At step 7 you ask for one change: General Information must be complete before Benefits Information opens.
6. **Open Workflow Center and Workplace** in two browser tabs, signed in, so you can switch quickly later. Workplace is at `/bas/Workplace` on the server.

---

## 2. The input

**Say.**

- "This is what the client gave us: a Word document with eight headings, from the process to the expected outcome, and screenshots of two screens. Nothing else. Bob has to turn this into a BAW app, one heading at a time."

What the client gave Bob:

- The Word document `IBM_Bob_BAW_Workflow_Requirements (1).docx`. Its headings are: 1. Process, 2. General Information Business Object, 3. General Information Coach View, 4. Benefits Business Object, 5. Benefits Coach View, 6. Client-Side Human Service, 7. UI Validations, 8. Expected Outcome. (The document is not in this repository.)
- Two screenshot references: the **General Information** screen, and the **Benefits and Eligibility** screen, which is one long screen saved as three scrolled images.
- The client's logo file.

The prompt adds one line that asks for the step-by-step build, and five lines to the document. They are shown separately below, so the client sees exactly what was added.

**Paste.** In Bob, in 🏗️ BAW App Builder mode:

```
Build the BAW app described in `screenshots/Quote/Customer workflow requirement/IBM_Bob_BAW_Workflow_Requirements (1).docx`. Use the acronym ZZLGE.
The General Information UI screenshot is `screenshots/Quote/generate-quote.png`. The Benefits and Eligibility UI screenshot is `screenshots/Quote/image (1).png` to `image (3).png` (one screen, scrolled). Use `screenshots/Quote/<client logo>.png` as the logo.

Build it step by step: make a to-do list with one item per heading of the document, do one item at a time, and check with me at the end of each item before you go on.

In addition to the document:
- The screenshots show the look and the control style only. Build only the fields the document lists, with the document's data types.
- Every field in the document is required.
- Each tab has a Save as Draft button. Each tab has a Next button; the last tab's button is Review, which goes on to Review Quote.
- Review Quote shows both views read-only, with an Edit button on each section, and the final Submit.
- There is no approve or send-back step.
```

**Say.**

- "The lines at the bottom are everything we added to the client's document. The screenshots give the look. The document gives the steps and the fields. Everything else is Bob's work."

---

## 3. Bob builds the app, step by step

**Do.** Paste the prompt and send it.

**Bob does.**

- Reads the Word document with `office_read`. The field tables are read from a document dump.
- Looks at the screenshots with `view_image`, and samples their colours with `image_colors`.
- Checks that the acronym is free with `list_apps`.

**Bob shows.** A to-do list with eight items, named after the document's headings, and a note that it will stop after each item. Steps 3, 5 and 6 are marked: they end with an offer to import into BAW.

**Say.**

- "Bob turned the document's headings into its plan. It will do one item at a time and show us the result before it goes on, the same way a developer would walk a reviewer through it."

In steps 1 to 5 Bob writes the app spec part by part and shows each part in the chat. Steps 1, 2 and 4 are checked in the chat only: a process, or a business object without a screen, cannot be built on its own. From step 3 on, Bob offers to build and import what is agreed so far, one snapshot per import, so you can check it in BAW. The process goes in with the first import.

### Step 1. Process

**Bob shows.**

- The process **Large Group Fully Insured Sales**.
- Two human activities in sequence: **Generate Quote**, then **Review Quote**.
- The flow: Start → Generate Quote → Review Quote → End. There is no approve or send-back step.

**Point out.** The names and the flow are the document's heading 1, word for word.

**Do.** Answer: "Looks good, go on."

### Step 2. General Information Business Object

**Bob shows.** **GenInfoBO**, with a table of its 19 fields: 11 String, 5 Date and 3 Boolean. Every field is required.

**Point out.** The field names and types are the document's table. Bob did not invent any field.

**Do.** Answer: "Looks good, go on."

### Step 3. General Information Coach View

**Bob shows.**

- The reusable View **QuoteDetails CV**, bound to GenInfoBO.
- Its sections and columns, taken from the General Information screenshot.
- The control for each field: text boxes, date pickers, dropdowns and Yes/No radio buttons, all native BAW controls.

**Point out.** The dropdown options are placeholders, because the document lists no options.

**Bob asks** whether to import it into BAW so you can check it there.

**Do.** Answer: "Looks good. Yes, import it, and use the built-in template."

**Bob does.**

- `create_app` writes snapshot 1.0.0: GenInfoBO, QuoteDetails CV, the Generate Quote service with its first tab, and the process with both tasks.
- `inspect_coaches` checks the screens, and `install_app` installs the app.
- `test_service` opens the "QuoteDetails CV Preview" service in a browser. Bob shows the screenshots and the run links, then asks whether to go on.

**Say.**

- "This is the first time anything goes to the server, and Bob asked before it did. The process is already there, with both tasks."

**Do.** Answer: "Go on."

### Step 4. Benefits Business Object

**Bob shows.** **BenefitsBO**, with a table of its 26 fields: 16 String, 4 Decimal, 3 Boolean and 3 Integer. Every field is required.

**Do.** Answer: "Looks good, go on."

### Step 5. Benefits Coach View

**Bob shows.**

- The reusable View **BenefitsDetails CV**, bound to BenefitsBO.
- Its four columns, taken from the Benefits and Eligibility screenshot, with the $ icon on the money fields.

**Do.** Answer: "Looks good. Yes, import it."

**Bob does.** Snapshot 1.0.1 adds BenefitsBO, BenefitsDetails CV and the Benefits Information tab. `test_service` opens the "BenefitsDetails CV Preview" service. Bob shows the screenshots and asks whether to go on.

**Do.** Answer: "Go on."

### Step 6. Client-Side Human Service

**Bob shows.**

- The client-side human service **Generate Quote** for the Generate Quote activity.
- Tab 1 **General Information** with QuoteDetails CV, and tab 2 **Benefits Information** with BenefitsDetails CV.
- The buttons: Save as Draft and Next on tab 1, Save as Draft and Review on tab 2.
- The variables `genInfo` and `benefits`, mapped to the process.
- The **Review Quote** service for the second activity: both Views read-only, an Edit button on each section, and Submit.

**Do.** Answer: "Looks good. Yes, import it."

**Bob does.**

- `create_app` writes snapshot 1.0.2 with the buttons and the Review Quote service, and `inspect_coaches` checks the screens.
- `install_app` installs it. Your yes was the import approval, so Bob does not ask again.
- `test_service` opens the Generate Quote form with both tabs. Bob shows the screenshots, the run link and what the app holds, and asks whether to go on.

**Say.**

- "Each import is a new snapshot, so we can see every step in BAW and go back to an earlier one."

**Do.** Answer: "Go on."

### Step 7. UI Validations

**Bob shows.** The validation rules: every field is required, the message for a missing field, Review stays blocked while a field is empty, and the user is kept on the tab with errors.

**Do.** Ask for a change, in plain words: "One change: the user must fill in the General Information tab before going to Benefits Information. Neither Next nor the tab header may skip ahead."

**Bob shows.** The changed part of the spec: the form gets `"tabsInOrder": true`. Next, or a click on the Benefits Information tab, stays on General Information while one of its required fields is empty. Going back is always allowed. Bob asks whether to build and test it.

**Do.** Answer: "Yes, build it and test it."

**Bob does.**

- `create_app` writes snapshot 1.0.3, and `install_app` installs it.
- `test_service` presses Next on the empty form. The form stays on General Information, every empty field is marked, and the Benefits Information tab does not open (image 01).
- It fills General Information. Now the Benefits Information tab opens. It presses Review with Benefits still empty: Review is blocked on Benefits Information.
- It fills Benefits and presses Review. Bob shows the screenshots and asks whether to go on.

**Say.**

- "We changed a rule in plain words. Bob changed the app, rebuilt it and tested the change itself. Nobody opened Designer."

**Do.** Answer: "Go on."

### Step 8. Validate the workflow

**Bob does.**

- **`test_process`.** The process runs Start, Generate Quote, Review Quote, End, and completes.
- **`test_process` with `draft_then_resume`.** Save as Draft works with required fields still empty. Bob types a few General Information fields, because Benefits does not open until that tab is complete. The task stays in the inbox, and reopening it brings back the values on General Information.
- Compares its screenshots with the client's screenshots.

**Bob shows.** Its final report: the app, the acronym, the snapshot, the run links, the steps, the field counts, the test results and the screenshot folders. Then the Workplace steps for you to try it.

**Say.**

- "Bob tested the app itself, in a browser, before it told us it was done. We will look at the same things by hand in a moment."

---

## 4. Show the result in BAW

Open **Workflow Center**, find the app, and open it in **Designer**. The checks follow the same headings.

| # | Check | Where to click in BAW |
|---|-------|-----------------------|
| 1 | The process diagram is Start, Generate Quote, Review Quote, End. There is no approve or send-back step. | Processes, open the process. |
| 2 | **GenInfoBO** has 19 properties: 11 String, 5 Date and 3 Boolean. | Data, open GenInfoBO. |
| 3 | The View **QuoteDetails CV** is bound to GenInfoBO. | User Interface, open QuoteDetails CV. |
| 4 | **BenefitsBO** has 26 properties: 16 String, 4 Decimal, 3 Boolean and 3 Integer. | Data, open BenefitsBO. |
| 5 | The View **BenefitsDetails CV** is bound to BenefitsBO. | User Interface, open BenefitsDetails CV. |
| 6 | The client-side human service **Generate Quote** has two tabs, the variables `genInfo` and `benefits`, and the task data mapping. | User Interface, open Generate Quote, look at the diagram, the variables and the Benefits tab (image 03). |
| 7 | Next and the Benefits Information tab stay on General Information while one of its required fields is empty (image 01), and Review is blocked while a Benefits field is empty. | Preview Generate Quote, or Workplace. Press Next on the empty form, then click the Benefits Information tab. |
| 8 | The whole process runs to completion. | Workplace, run it once, or show Bob's `test_process` result. |
| 9 | Save as Draft and resume work (image 02). | Workplace, see part 5. |
| 10 | Review Quote is read-only, with an Edit button on each section and a Submit button (image 04). | Workplace, see part 5. |

### What to point out in each picture

**Image 01. The empty form is blocked.** All fields on the General Information tab are empty. Next was pressed. Every required field is outlined in red, and the user stays on General Information. The buttons are Save as Draft and Next.

**Image 02. The draft comes back.** General Information was complete, so the user could go on to Benefits Information and save a draft there. The task was reopened, and it opens on the Benefits Information tab, the tab the user left. Broker Commission shows 12.50, Age shows 0, and "ERISA group?" keeps its No.

**Image 03. The Benefits tab.** It has 26 fields in 4 columns: dropdowns, Yes/No radio buttons, and boxes with a $ icon. The buttons are Save as Draft and Review.

**Image 04. Review Quote.** Both sections are read-only. Each section header has an Edit button. Submit is at the bottom.

**Say.**

- "Everything on this list is a normal BAW artifact. Your developers can open each one, change it, and extend it."

---

## 5. The live moment

**Do.** In Workplace, click **Start workflow** and pick **Large Group Fully Insured Sales**. Generate Quote opens. Then:

1. Press **Next** on the empty form. It is blocked, and the empty fields are marked (image 01). Click the Benefits Information tab: it does not open.
2. Fill in all of General Information and press **Next**. Benefits Information opens. Fill in part of it, including one Yes/No answered No and one number set to 0.
3. Press **Save as Draft**.
4. Reopen the task from the task list. The values and the tab come back (image 02).
5. Finish filling in the form, and press **Review**. The Generate Quote task closes.
6. Open **Review Quote** from the task list (image 04).
7. Press **Edit** on Benefits. Clear a required field. Press **Submit**. Submit refuses.
8. Fill the field again. Press **Submit**. The process completes.

**Say.**

- "The form will not let you go on while a required field is empty. But you can always save what you have and come back to it later."
- "Review Quote is read-only until you press Edit, and Submit checks the fields again."

---

## 6. What Bob generated, and what is still open

The document's last heading asks which artifacts Bob can generate and where manual BAW work is still needed.

| Document heading | Artifact | Who made it |
|------------------|----------|-------------|
| 1. Process | Large Group Fully Insured Sales, with Generate Quote and Review Quote | Bob |
| 2. General Information Business Object | GenInfoBO, 19 fields | Bob |
| 3. General Information Coach View | QuoteDetails CV | Bob |
| 4. Benefits Business Object | BenefitsBO, 26 fields | Bob |
| 5. Benefits Coach View | BenefitsDetails CV | Bob |
| 6. Client-Side Human Service | Generate Quote with two tabs, Review Quote, Save as Draft, the data mapping | Bob |
| 7. UI Validations | Required fields, messages, the blocked Review, and the tabs in order that you asked for at step 7 | Bob |
| 8. Expected Outcome | The tested workflow | Bob tested it; you ran it in Workplace |
| (not in the document) | The real dropdown option lists | Still to do, once the client supplies them |

**Say plainly.**

- "In the rehearsal, Bob generated every artifact on the list. No developer edits in BAW were needed."

### One-time engineering work

This was done once, ahead of the demo. It is not part of the demo itself:

- A reference Save as Draft sample was built once in Designer, so that the generator could reproduce BAW's Postpone pattern.
- The generator and test fixes made during the rehearsals.

### Known items

Mention these honestly if they come up:

- The dropdown options are placeholders until the client supplies the real lists.
- "Union group?" follows the document's String type, not the screenshot's checkbox.
- When a saved draft is reopened, Yes/No and number fields the user never touched show No and 0, and the required check counts them as answered.
- In Workplace, the window closes after Review on Generate Quote, and Review Quote is opened from the task list.
- The document names no lanes, so Bob may place both tasks in one lane or use two.
- Bob's layout can vary slightly between runs. The names, types, flow and behaviour stay the same.

---

## 7. If it breaks

| Problem | What to do |
|---------|------------|
| Bob does not offer the import at step 3, 5 or 6 | Say: "Build it and import it into BAW so I can check it there." |
| Bob says it cannot keep the user on the first tab | Restart Bob IDE so it loads the current skill, which has the `tabsInOrder` option. |
| Bob does several steps without stopping | Say: "Stop. Go back to the to-do list and check with me after each item." If it keeps going, restart Bob IDE so it loads the current App Builder rules. |
| One of Bob's BAW tools fails | The tool error states the reason, either an HTTP code or "Cannot reach BAW". Fix that, then ask Bob to continue. |
| The login to BAW has expired | It is renewed automatically. |
| Bob still behaves as before a fix | Restart Bob IDE. |
| Bob refuses to repeat a call after three identical failures | Start a fresh Bob task. |
| The toolkit install fails | Import the .twx by hand in Workflow Center (Process Apps, Import). |
| A browser test fails | Look at the screenshots it saved in `work/`, and run it again. |
| Workplace shows "Authorization Error" on a task | Sign out and in again, then open the task from the task list. |

---

## 8. Rehearsal checklist

- [ ] Bob IDE was restarted, the `baw-dev-tools` server is connected, and the ABW snapshot is installed on the server.
- [ ] The ZZ acronym is unused, and the Word document, the screenshots and the logo are in `screenshots/Quote/`.
- [ ] Bob shows a to-do list with one item per heading of the document.
- [ ] Bob stopped at the end of every step and waited for your answer.
- [ ] Steps 2 and 4 show GenInfoBO (19 fields) and BenefitsBO (26 fields).
- [ ] At steps 3, 5 and 6 Bob offered the import, asked the template question once, and snapshots 1.0.0, 1.0.1 and 1.0.2 installed.
- [ ] At step 7 Bob made the tab change you asked for, installed snapshot 1.0.3, and its test shows Benefits Information locked until General Information is complete.
- [ ] Bob's tests pass: the blocked Next, the blocked Review, both tabs filled, the process completed, Save as Draft and resume.
- [ ] The ten checks match what Designer shows.
- [ ] In Workplace, the empty form is blocked, Benefits Information does not open before General Information is complete, the draft comes back on the right tab, and Review Quote opens from the task list.
- [ ] Submit refuses a cleared required field, and after a refill Submit completes the process.
