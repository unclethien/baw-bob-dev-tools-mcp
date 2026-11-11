# Demo script: Bob builds the Large Group quote app step by step

**What the client sees.** IBM Bob reads the client's Word document and builds the BAW app one heading at a time. After each heading, Bob shows what it made and waits. You check it and reply. At the end, you show the finished app in BAW.

**What you do.** You paste one prompt. Then you reply to Bob eight times, with the replies below. Then you open the app in BAW.

**Status.** The app was checked on the test server. The import offers (steps 3, 5 and 6) and the tab change (step 7) have not been rehearsed with Bob yet. After the next rehearsal, fix any wording that does not match what Bob shows.

---

## The whole demo on one page

| Step | Bob shows | You reply |
|------|-----------|-----------|
| Start | | Paste the prompt. |
| 1. Process | The process and its two tasks | "Looks good, go on." |
| 2. General Information Business Object | GenInfoBO, 19 fields | "Looks good, go on." |
| 3. General Information Coach View | The General Information screen | "Looks good. Yes, import it, and use the built-in template." Then: "Go on." |
| 4. Benefits Business Object | BenefitsBO, 26 fields | "Looks good, go on." |
| 5. Benefits Coach View | The Benefits screen | "Looks good. Yes, import it." Then: "Go on." |
| 6. Client-Side Human Service | The form with two tabs, and Review Quote | "Looks good. Yes, import it." Then: "Go on." |
| 7. UI Validations | The required-field rules | Ask for the change (below). Then: "Yes, build it and test it." Then: "Go on." |
| 8. Validate the workflow | Its own test of the whole workflow | Nothing. Bob reports. |
| BAW | | Show the app in Designer and run it in Workplace. |

At steps 3, 5 and 6, Bob puts what it has built so far into BAW, as a new snapshot (1.0.0, 1.0.1 and 1.0.2). At step 7 it builds 1.0.3 with your change.

---

## Before you start

1. **Restart Bob IDE**, and check that the `baw-dev-tools` server is connected.
2. **Check the acronym.** The prompt uses `ZZLGF`. If an app with that acronym is already on the server, pick another one that starts with ZZ and change it in the prompt.
3. **Put the client's files in `screenshots/Quote/`**: the Word document, the screenshots and the logo. This folder is not in the repository.
4. **Check the ABW toolkit.** It must be installed on the server, with its `.twx` in `work/`. If it is missing, Bob installs it, which adds a few minutes.
5. **Open Workflow Center and Workplace** in two browser tabs, signed in.

---

## Start

**Say.** "The client gave us a Word document with eight headings and screenshots of two screens. Bob will turn it into a BAW app, one heading at a time."

**Paste** in Bob, in 🏗️ BAW App Builder mode:

```
Build the BAW app described in `screenshots/Quote/Customer workflow requirement/IBM_Bob_BAW_Workflow_Requirements (1).docx`. Use the acronym ZZLGF.
The General Information UI screenshot is `screenshots/Quote/generate-quote.png`. The Benefits and Eligibility UI screenshot is `screenshots/Quote/image (1).png` to `image (3).png` (one screen, scrolled). Use `screenshots/Quote/<client logo>.png` as the logo.

Build it step by step: make a to-do list with one item per heading of the document, do one item at a time, and check with me at the end of each item before you go on.

In addition to the document:
- The screenshots show the look and the control style only. Build only the fields the document lists, with the document's data types.
- Every field in the document is required.
- Each tab has a Save as Draft button. Each tab has a Next button; the last tab's button is Review, which goes on to Review Quote.
- Review Quote shows both views read-only, with an Edit button on each section, and the final Submit.
- There is no approve or send-back step.
```

**Bob shows** a to-do list with the eight headings of the document.

**Say.** "The lines at the bottom are all we added to the document. Bob made its plan from the document's headings."

---

## The eight steps

### Step 1. Process

**Bob shows** the process **Large Group Fully Insured Sales**: Start → Generate Quote → Review Quote → End.

**You reply:** "Looks good, go on."

### Step 2. General Information Business Object

**Bob shows** **GenInfoBO** and a table of its 19 fields, all required.

**You reply:** "Looks good, go on."

**Say.** "These are the document's fields and types. Bob did not invent any."

### Step 3. General Information Coach View

**Bob shows** the **QuoteDetails CV** screen: its sections, columns and controls, taken from the screenshot. Bob asks whether to import it into BAW.

**You reply:** "Looks good. Yes, import it, and use the built-in template."

**Bob** builds snapshot 1.0.0, installs it, opens the screen in a browser and shows you the picture.

**You reply:** "Go on."

**Say.** "That is the first time anything went to BAW, and Bob asked first. The process is in BAW now too."

### Step 4. Benefits Business Object

**Bob shows** **BenefitsBO** and a table of its 26 fields, all required.

**You reply:** "Looks good, go on."

### Step 5. Benefits Coach View

**Bob shows** the **BenefitsDetails CV** screen: four columns, with a $ icon on the money fields.

**You reply:** "Looks good. Yes, import it."

**Bob** builds snapshot 1.0.1, installs it, and shows you the screen in a browser.

**You reply:** "Go on."

### Step 6. Client-Side Human Service

**Bob shows** the **Generate Quote** form: tab 1 General Information, tab 2 Benefits Information, with Save as Draft, Next and Review. And the **Review Quote** task: read-only, an Edit button on each section, and Submit.

**You reply:** "Looks good. Yes, import it."

**Bob** builds snapshot 1.0.2, installs it, and shows you the form in a browser.

**You reply:** "Go on."

**Say.** "Each import is a new snapshot, so we can see every step in BAW."

### Step 7. UI Validations: ask for a change

**Bob shows** the rules: every field is required, and Review stays blocked while a field is empty.

**You reply** with a change, in plain words:

```
One change: the user must fill in the General Information tab before going to Benefits Information. Neither Next nor the tab header may skip ahead.
```

**Bob shows** the change and asks whether to build it.

**You reply:** "Yes, build it and test it."

**Bob** builds snapshot 1.0.3, installs it, and tests it in a browser. On the empty form, Next and the Benefits Information tab stay on General Information, and the empty fields turn red (image 01).

**You reply:** "Go on."

**Say.** "We asked for a change in plain words. Bob changed the app, rebuilt it and tested it. Nobody opened Designer."

### Step 8. Validate the workflow

**Bob** runs the whole workflow in a browser: Generate Quote, then Review Quote, to the end. It also saves a draft and reopens it. Then it gives its report and the steps to try it in Workplace.

**You reply:** nothing.

**Say.** "Bob tested the app itself before it said it was done. Now we look at it in BAW."

---

## Show it in BAW

### In Designer

Open **Workflow Center**, find the app, and open it.

| Open | What to show |
|------|--------------|
| Snapshots | 1.0.0 to 1.0.3, one per import |
| Processes, Large Group Fully Insured Sales | Start → Generate Quote → Review Quote → End |
| Data, GenInfoBO and BenefitsBO | 19 and 26 fields |
| User Interface, QuoteDetails CV and BenefitsDetails CV | Each View is bound to its business object |
| User Interface, Generate Quote | Two tabs, the variables, and the data mapping |

**Say.** "These are normal BAW artifacts. Your developers can open and change every one of them."

### In Workplace

Click **Start workflow** and pick **Large Group Fully Insured Sales**.

1. Press **Next** on the empty form. It stays, and the empty fields turn red (image 01). Click the Benefits Information tab: it does not open either.
2. Fill in all of General Information and press **Next**. Benefits Information opens.
3. Fill in part of Benefits and press **Save as Draft**.
4. Open the task again from the task list. Your values and the tab come back (image 02).
5. Fill in the rest (image 03) and press **Review**. The window closes.
6. Open **Review Quote** from the task list (image 04). Press **Edit** on Benefits, clear a field, and press **Submit**: it refuses.
7. Fill the field again and press **Submit**. The workflow is done.

**Say.** "You cannot skip a required field, but you can always save a draft and come back."

The pictures:

- **Image 01.** The empty General Information tab after Next: every field in red.
- **Image 02.** The reopened draft, back on the Benefits Information tab with its values.
- **Image 03.** The Benefits tab: 26 fields in four columns.
- **Image 04.** Review Quote: read-only, Edit on each section, Submit at the bottom.

---

## Close

**What Bob made.** Every artifact the document asks for: the process with both tasks, GenInfoBO and BenefitsBO, the two Views, the Generate Quote form with Save as Draft, Review Quote, the validations and your tab change. Bob also tested the workflow.

**Say.** "Bob made every artifact in the document. No developer work in BAW was needed."

**Still open.** The dropdown options are placeholders until the client sends the real lists.

**If someone asks:**

- "Union group?" is text, because the document says String, even though the screenshot shows a checkbox.
- In a reopened draft, Yes/No and number fields nobody touched show No and 0.
- Bob's layout can differ a little between runs. The names, fields, flow and behaviour stay the same.

---

## If it breaks

| Problem | What to do |
|---------|------------|
| Bob goes on without stopping | Say: "Stop. Check with me after each item." If it keeps going, restart Bob IDE. |
| Bob does not offer the import at step 3, 5 or 6 | Say: "Build it and import it into BAW so I can check it there." |
| Bob says it cannot keep the user on the first tab | Restart Bob IDE, so it loads the current skill. |
| A Bob tool fails | Read the error (an HTTP code or "Cannot reach BAW"), fix it, and ask Bob to continue. |
| Bob refuses to repeat a call after three failures | Start a new Bob task. |
| Workplace shows "Authorization Error" | Sign out and in again, then open the task from the task list. |

---

## Rehearsal checklist

- [ ] Bob showed a to-do list with the eight headings.
- [ ] Bob stopped after every step and waited for you.
- [ ] Steps 2 and 4 showed 19 and 26 fields.
- [ ] Bob offered the import at steps 3, 5 and 6, and snapshots 1.0.0 to 1.0.2 installed.
- [ ] At step 7, Bob made your change and snapshot 1.0.3 installed.
- [ ] Bob's step 8 tests passed.
- [ ] Designer shows what the table above lists.
- [ ] In Workplace, all seven steps worked.
