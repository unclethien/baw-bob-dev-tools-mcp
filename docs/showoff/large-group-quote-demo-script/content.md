# Demo script: IBM Bob builds the Large Group Fully Insured Sales app in BAW from the client's Word document

> **Replaced.** The current script is `../large-group-quote-step-by-step-demo-script/`. It builds the same app, one heading of the document at a time, with a check after each step. This page is kept as a record of the earlier rehearsals.

The client wants to see how much of the BAW work IBM Bob generates, so their developers do not have to build all the BAW artifacts by hand. In this demo, Bob reads the client's own Word document and screenshots, and builds the whole app in BAW. The script has five parts:

1. **The input.** What the client gave Bob, and the prompt that starts the run.
2. **Bob builds the app.** Bob reads, shows a design, builds, installs and tests. You answer two questions.
3. **Show the result in BAW.** Ten checks, each with the place to click in Workflow Center.
4. **The live moment.** You use the finished app in Workplace.
5. **What Bob generated, and what is still open.**

**How to read this script.** **Do** is what you click or type. **Paste** is text you paste into Bob. **Bob does** is what Bob does on its own. **Say** is what you say aloud to the room; the quoted lines are written to be spoken. The pictures were taken during a rehearsal.

---

## 1. Before the meeting

Thirty minutes before:

1. **Restart Bob IDE.** Bob then runs the current `baw-dev-tools` MCP server. Check that the server is connected.
2. **Check the App Builder Widgets toolkit (ABW).** Its snapshot must be installed on the BAW server. If it is missing, Bob can build and install it with `build_widget_toolkit` and `install_app`.
3. **Pick an acronym that nobody has used.** It must start with ZZ. This script uses `ZZLGD`. If an app with that acronym already exists on the server, pick another one and change the prompt.
4. **Put the client's files in `screenshots/Quote/`.** This folder stays out of the repository. It holds the Word document, the two screenshot references and the logo (see part 2).
5. **Know your two answers.** Bob stops twice and waits for you: once to approve the design, and once to approve the import into BAW.
6. **Open Workflow Center and Workplace** in two browser tabs, signed in, so you can switch quickly later.

---

## 2. The input

Say.

- "This is what the client gave us: a Word document that lists the fields, and screenshots of two screens. Nothing else. Bob has to turn this into a BAW app."

What the client gave Bob:

- The Word document `IBM_Bob_BAW_Workflow_Requirements (1).docx`. It lists the fields of the app with their data types. (The document is not in this repository.)
- Two screenshot references: the **General Information** screen, and the **Benefits and Eligibility** screen, which is one long screen saved as three scrolled images.
- The client's logo file.

The prompt adds five lines to the document. They are shown separately below, so the client sees exactly what was added.

**Paste.** In Bob, in BAW App Builder mode:

```
Build the BAW app described in `screenshots/Quote/Customer workflow requirement/IBM_Bob_BAW_Workflow_Requirements (1).docx`. Use the acronym ZZLGD.
The General Information UI screenshot is `screenshots/Quote/generate-quote.png`. The Benefits and Eligibility UI screenshot is `screenshots/Quote/image (1).png` to `image (3).png` (one screen, scrolled). Use `screenshots/Quote/<client logo>.png` as the logo.

In addition to the document:
- The screenshots show the look and the control style only. Build only the fields the document lists, with the document's data types.
- Every field in the document is required.
- Each tab has a Save as Draft button. Each tab has a Next button; the last tab's button is Review, which goes on to Review Quote.
- Review Quote shows both views read-only, with an Edit button on each section, and the final Submit.
- There is no approve or send-back step.
```

Say.

- "The five lines at the bottom are everything we added to the client's document. The screenshots give the look. The document gives the fields. Everything else is Bob's work."

---

## 3. Bob builds the app

The rehearsal runs took about 8 to 12 minutes from sending the prompt to Bob's final report, including your two approvals. While Bob works, talk through the steps below.

### Step 1. Bob reads the document and the screenshots

**Do.** Paste the prompt and send it.

**Bob does.**

- Reads the Word document with `office_read`. The field tables are read from a document dump.
- Looks at the screenshots with `view_image`.
- Samples the colours of the screenshots with `image_colors`.

**Say.**

- "Bob reads the document the same way a person would: the field tables, then the pictures. It takes the colours from the client's own screenshots."

### Step 2. The design stop

**Bob does.** Bob shows its design and waits. The design has:

- Two business objects: **GenInfoBO** with 19 fields and **BenefitsBO** with 26 fields. All fields are required.
- Two reusable Views: **QuoteDetails CV** and **BenefitsDetails CV**.
- One **Generate Quote** screen with two tabs.
- **Review Quote**, a second screen that shows both views read-only.
- The process.

**Point out.**

- The field names and types come from the document.
- The dropdown options are placeholders, because the document lists no options.

**Do.** Answer: "Use the built-in template, and I approve."

**Say.**

- "This is the first of two stops. Bob does not build anything until a person agrees with the design."

### Step 3. Build and install

**Bob does.**

- `create_app` writes the app as a .twx file.
- `inspect_coaches` checks the screens in that file.
- Bob asks you to approve the import.
- `install_app` installs the app in BAW.

**Do.** Approve the import.

**Say.**

- "This is the second stop. Bob asks before anything is installed on the server."

### Step 4. Bob tests the app on its own

You do not have to do anything here. Bob runs three tests:

- **`test_service`.** The Review button stays blocked while required fields are empty, and no request is sent. Both tabs then fill: 19 fields and 26 fields.
- **`test_process`.** The process runs Start, Generate Quote, Review Quote, End, and completes.
- **`test_process` with `draft_then_resume`.** Save as Draft works with required fields still empty. The task stays in the inbox. Reopening it brings back the values on the tab the user left, for example Self Only 12.5, shown as 12.50.

**Say.**

- "Bob tested the app itself, in a browser, before it told us it was done. We will look at the same things by hand in a moment."

---

## 4. Show the result in BAW

When Bob's final report appears, open **Workflow Center**, find the app, and open it in **Designer**. Go through the ten checks in this order.

| # | Check | Where to click in BAW |
|---|-------|-----------------------|
| 1 | The process diagram is Start, Generate Quote, Review Quote, End. There is no approve or send-back step. | Processes, open the process. |
| 2 | **GenInfoBO** has 19 properties: 11 String, 5 Date and 3 Boolean. | Data, open GenInfoBO. |
| 3 | **BenefitsBO** has 26 properties: 16 String, 4 Decimal, 3 Boolean and 3 Integer. | Data, open BenefitsBO. |
| 4 | The View **QuoteDetails CV** is bound to GenInfoBO. | User Interface, open QuoteDetails CV. |
| 5 | The View **BenefitsDetails CV** is bound to BenefitsBO. | User Interface, open BenefitsDetails CV. |
| 6 | The client-side human service **Generate Quote** has two tabs, the variables `genInfo` and `benefits`, and the task data mapping. | User Interface, open Generate Quote, look at the diagram, the variables and the Benefits tab (image 03). |
| 7 | Required-field validation blocks Review while a required field is empty, and shows the first tab with errors (image 01). | Preview Generate Quote, or Workplace. Open the Benefits Information tab and press Review on the empty form. |
| 8 | The whole process runs to completion. | Workplace, run it once, or show Bob's `test_process` result. |
| 9 | Save as Draft and resume work (image 02). | Workplace, see part 5. |
| 10 | Review Quote is read-only, with an Edit button on each section and a Submit button (image 04). | Workplace, checked by hand, see part 5. |

### What to point out in each picture

**Image 01. The empty form is blocked.** All fields on the General Information tab are empty. Review was pressed on the last tab. Every required field is outlined in red, and the user stays on the form. The buttons are Save as Draft and Next.

**Image 02. The draft comes back.** The task was reopened after Save as Draft, and it opens on the Benefits Information tab, the tab the user left. Broker Commission shows 12.50, Age shows 0, and "ERISA group?" keeps its No. The other fields are still empty.

**Image 03. The Benefits tab.** It has 26 fields in 4 columns: dropdowns, Yes/No radio buttons, and boxes with a $ icon. The buttons are Save as Draft and Review.

**Image 04. Review Quote.** Both sections are read-only. Each section header has an Edit button. Submit is at the bottom.

**Say.**

- "Everything on this list is a normal BAW artifact. Your developers can open each one, change it, and extend it."

---

## 5. The live moment

**Do.** In Workplace, start the process, and then:

1. Open the Benefits Information tab and press **Review** on the empty form. It is blocked, and the first tab shows its errors (image 01).
2. Fill in part of the form.
3. Press **Save as Draft**.
4. Reopen the task from the inbox. The values and the tab come back (image 02).
5. Finish filling in the form.
6. Press **Review**. The Review Quote task opens (image 04).
7. Press **Edit** on Benefits. Clear a required field. Press **Submit**. Submit refuses.
8. Fill the field again. Press **Submit**. The process completes.

**Say.**

- "The form will not let you go on while a required field is empty. But you can always save what you have and come back to it later."
- "Review Quote is read-only until you press Edit, and Submit checks the fields again."

---

## 6. What Bob generated, and what is still open

**Say plainly.**

- "In the final rehearsal, Bob generated every artifact on the list. No developer edits in BAW were needed."

Bob generated the process, the two business objects, the two reusable Views, the Generate Quote screen with two tabs, Review Quote, the validation, Save as Draft and the task data mapping.

### One-time engineering work

This was done once, ahead of the demo. It is not part of the demo itself:

- A reference Save as Draft sample was built once in Designer, so that the generator could reproduce BAW's Postpone pattern.
- The generator and test fixes made during the rehearsals.

### Known items

Mention these honestly if they come up:

- The dropdown options are placeholders until the client supplies the real lists.
- "Union group?" follows the document's String type, not the screenshot's checkbox.
- The document names no lanes, so Bob may place both tasks in one lane or use two.
- Bob's layout can vary slightly between runs. The names, types, flow and behaviour stay the same.

---

## 7. If it breaks

| Problem | What to do |
|---------|------------|
| One of Bob's BAW tools fails | The tool error now states the reason, either an HTTP code or "Cannot reach BAW". Fix that, then ask Bob to continue. |
| The login to BAW has expired | It is renewed automatically. |
| Bob still behaves as before a fix | Restart Bob IDE. |
| Bob refuses to repeat a call after three identical failures | Start a fresh Bob task. |
| The toolkit install fails | Import the .twx by hand in Workflow Center (Process Apps, Import). |
| A browser test fails | Look at the screenshots it saved in `work/`, and run it again. |

---

## 8. Rehearsal checklist

- [ ] Bob IDE was restarted and the `baw-dev-tools` server is connected.
- [ ] The ABW snapshot is installed on the server.
- [ ] The ZZ acronym is unused.
- [ ] The Word document, the screenshots and the logo are in `screenshots/Quote/`.
- [ ] Bob shows the design with GenInfoBO (19 fields) and BenefitsBO (26 fields) and stops.
- [ ] You approved the design and then the import.
- [ ] Bob's tests pass: the blocked Review, both tabs filled, the process completed, Save as Draft and resume.
- [ ] The ten checks match what Designer shows.
- [ ] In Workplace, the empty form is blocked, the draft comes back on the right tab, and Submit refuses a cleared required field.
- [ ] After a refill, Submit completes the process.
