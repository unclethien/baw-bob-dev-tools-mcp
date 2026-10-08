---
name: screenshot-to-app
description: Build a running BAW process app (.twx) whose coaches reproduce the screens in one or more screenshots - sections, side-by-side columns, labels, dropdowns, radio groups, checkboxes, dates, required markers and button labels - by reading the images, writing an app spec, then building, installing and comparing the result with the baw-dev-tools MCP tools. Use when the user attaches or points to a screenshot, mockup or picture of a form and wants it as BAW coaches, optionally followed by a React + Carbon version.
---

# Screenshot to app

You read the screenshots and write **one app spec**. The baw-dev-tools MCP tools build, install and test it, and you compare their screenshots with the originals. Never write TWX or coach XML.

## 1. Get the images

- **Attached in the chat:** you can see them directly.
- **A file in the project** (for example `screenshots/form.png`): call `view_image` with its path. Try `screenshots/example-supplier-registration.png` for a demo.
- Several screenshots are several steps, in the order the user gives them. A screenshot that shows tabs across the top is one screen with `"layout": "tabs"`, one step per tab.

## 2. Read each screen

Write down, top to bottom and left to right:

| In the screenshot | In the app spec |
|---|---|
| Page heading and the sentence under it | step `title` and `intro` (with tabs: `form.title`, `form.intro`) |
| Bordered box, fieldset or bold heading over a group of fields | a `sections[]` entry with that `title` |
| Fields placed side by side | section `"columns": 2` (or 3). A field across the whole width gets `"wide": true` |
| Text box | `String` |
| Large multi-line box | `Text Area`, `"wide": true` |
| Box with a date format, calendar icon or "Date" in the label | `Date` |
| Box for a count or a year | `Integer`. Money, rates and percentages: `Decimal` |
| Dropdown (box with ▼) | `Select` with `options` |
| Round option buttons, `( )` or `◯` | `Radio` with `options`, in the order shown |
| Square tick box | `Boolean`; the text next to it is the `label` |
| `*` or "(required)" next to a label | `"required": true` |
| Small grey text under a field | `help` |
| Forward button text ("Continue", "Save and next") | step `nextLabel`; back button text: `backLabel` |

- **Labels:** copy the visible text exactly, without the `*` or a trailing colon.
- **Field names:** camelCase from the label (`Tax ID` becomes `taxId`), unique across the whole app.
- **Dropdown options:** a closed dropdown hides its options. Use the options the user gives you. Otherwise choose short, plausible ones for the domain and list them as assumptions in the report.
- **Values typed into the screenshot** are not part of the design. Never copy names, numbers, addresses or anything that looks like real data into the spec.

## 3. Write the spec

Path: `work/<ACRONYM>.app.json`. Follow the baw-app-builder skill for the `app`, `businessObject` and `service` keys, and use `app-specs/example-supplier-registration.json` as the model for sections, columns and choices:

```json
{ "title": "Supplier Registration", "intro": "Register a new supplier.", "nextLabel": "Continue",
  "sections": [
    { "title": "Company", "columns": 2, "fields": [
      { "name": "legalName", "label": "Legal Name", "required": true },
      { "name": "supplierType", "label": "Supplier Type", "type": "Select", "options": ["Manufacturer", "Distributor"] },
      { "name": "businessSize", "label": "Business Size", "type": "Radio", "options": ["Small", "Medium", "Large"], "wide": true }
    ]}
  ]}
```

In two columns the fields fill left, right, left, right, so list them in reading order, row by row.

Build only the screens in the screenshots, plus what they clearly lead to. If the last screen's forward button says "Continue" or "Next", the user expects something after it: add a read-only review (`"review": { "title": ... }`) and, for a submission, a `confirmation`, as the example does. If it says "Submit" and the user asked for nothing more, set `"review": false`.

## 4. Build, install, compare

1. `create_app` with the spec. Fix every problem it lists.
2. `install_app` with the returned `.twx`. Continue only when `"ok": true`.
3. `test_service` with `fill: false`. It returns a screenshot for each coach.
4. **Compare.** `view_image` each test screenshot next to its original and check, in order:
   - section titles and their order;
   - every field: present, same label, same control, same column, same order;
   - required markers;
   - button labels.

   The BAW theme draws fonts, colours and spacing, so those differ. Everything in the list above must match. Fix the spec, bump `app.snapshot`, and repeat from 1.

## 5. Report

- The app, acronym, snapshot and run URL (`list_services`).
- For each screen, its sections, with the field and column counts.
- **Assumptions**, for example dropdown options you chose.
- **Not built**: things in the screenshot that the app spec cannot express, such as tables, file uploads, links, menus, logos and extra buttons. For each one, offer to add it in a React screen.

## Then: a React version (optional)

When the user wants the screens modernized, or closer to the screenshot than the BAW theme allows:

1. `inspect_coaches` on the `.twx`. It writes the coach spec with the sections, columns (in reading order), dropdown and radio options, and required flags you built.
2. Follow the coach-inventory, react-coach-screen and coach-modernize skills.

A React screen can follow the screenshot's layout more closely. `Field` renders `select` and `radio`. `<div className="pp-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>` gives exactly two columns. The screen can also add the items listed under "Not built".
