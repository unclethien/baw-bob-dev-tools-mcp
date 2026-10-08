---
name: screenshot-to-app
description: Build a running BAW process app (.twx) whose coaches reproduce the screens in one or more screenshots - layout (sections, tabs, side-by-side columns and their widths, which field sits in which column), controls (labels, dropdowns, radio groups, checkboxes, dates, required markers, help icons, buttons) and look (colours, header banner and logo, field icons, shapes, button placement) - by reading the images, writing an app spec, then building, installing and comparing the result with the baw-dev-tools MCP tools. Use when the user attaches or points to a screenshot, mockup or picture of a form and wants it as BAW coaches, optionally followed by a React + Carbon version.
---

# Screenshot to app

You read the screenshots and write **one app spec**. The baw-dev-tools MCP tools build, install and test it, and you compare their screenshots with the originals. Never write TWX, coach XML or CSS.

The result must match the screenshot in **layout and look**, not only in fields: same columns, same theme colours, same header, same button placement. You may make it cleaner, for example with even spacing and aligned fields, but never swap the screenshot's theme for a default one.

## 1. Get the images

- **A file in the project** (for example `work/form.png`): call `view_image` with its path. `screenshots/example-supplier-registration.png` is a demo.
- **Attached in the chat:** you can see it, but `image_colors` and `crop_image` need a file. Ask the user to save it in `work/` (not committed, so client screens stay private) so you can read exact colours and cut out the logo. If they can't, read the colours by eye and report the logo as not built.
- **An attached image and a named file that show different screens:** the attached image is the one the user means. Say which one you built from.
- Several screenshots are several steps, in the order the user gives them. A screenshot with tabs across the top is one screen with `"layout": "tabs"`, one step per tab.

## 2. Read the layout and the fields

Write down, top to bottom and left to right:

| In the screenshot | In the app spec |
|---|---|
| Page heading and the sentence under it | step `title` and `intro` (with tabs: `form.title`, `form.intro`) |
| Tabs across the top | `"layout": "tabs"`, one step per tab, titles copied exactly |
| Coloured bar, bordered box or bold heading over a group of fields | a `sections[]` entry with that `title` |
| Fields side by side | section `"columns"`: count the columns (up to 6). A field across the whole width gets `"wide": true` |
| Fields stacked **down** each column (the usual case) | give every field `"column": 1`, `2`, … and list each column's fields top to bottom. Without `column`, fields fill left, right, left, right, row by row |
| Columns of different widths | section `"widths"`, one number per column relative to the others, e.g. `[1, 1.6, 1, 1, 1]` when the second column is about 1.6 times as wide |
| Text box | `String` |
| Large multi-line box | `Text Area`, `"wide": true` |
| Box with a date format, calendar icon or "Date" in the label | `Date` |
| Box for a count or a year | `Integer`. Money, rates and percentages: `Decimal` |
| Dropdown (box with ▼) | `Select` with `options` |
| Round option buttons, `( )` or `◯` | `Radio` with `options`, in the order shown |
| Square tick box, even a small one next to an icon | `Boolean`; its label is the `label` |
| `*` or "(required)" next to a label | `"required": true` |
| Small grey text under a field, or a `?` / ⓘ icon next to the label | `help` (write a short, plausible sentence for an icon) |
| Forward button text ("Continue", "Submit") | step `nextLabel` (with tabs: `form.nextLabel`); back button: `backLabel` |
| Cancel, Close or Exit button | `cancelLabel` on the step (with tabs: on `form`). It ends the service |

- **Labels:** copy the visible text exactly, without the `*` or a trailing colon.
- **Field names:** camelCase from the label (`Tax ID` becomes `taxId`), unique across the whole app.
- **Dropdown options:** a closed dropdown hides its options. Use the options the user gives you. Otherwise choose short, plausible ones for the domain and list them as assumptions in the report.
- **Values typed into the screenshot** are not part of the design. Never copy names, numbers, addresses or anything that looks like real data into the spec. The same goes for a person's name in a greeting: keep the greeting, drop the name.

## 3. Read the look

Add a `theme` whenever the screenshot has its own colours, and a `banner` when it has a header strip. Sample every colour with `image_colors` on the screenshot file: `box` is `[left, top, right, bottom]` as fractions of the image, so `[0, 0, 1, 0.15]` is the top 15 %. Take the colour with the largest share in a box drawn tightly inside the element.

| In the screenshot | Theme setting |
|---|---|
| Header strip, section title bars, icon boxes | `primary` |
| Text and icons drawn on those | `onPrimary` (usually `#ffffff`) |
| Title and product name in the header, when coloured differently | `heading` |
| Main button (Submit / Next) and the active tab | `button` |
| Second button (Cancel / Back) when it is filled with a colour | `secondaryButton`. Leave it out for an outlined button |
| Page behind the form | `background` |
| Font that looks like Open Sans, Roboto, Lato, Arial … | `font` |
| Corners: sharp / slightly rounded / fully round buttons | `shape`: `square` / `rounded` / `pill` |
| A small coloured square with an icon before each input | `"fieldIcons": true`, and per field `icon`: `text`, `file`, `user`, `users`, `calendar`, `list`, `options`, `check`, `hash`, `search`, `id`, `mail`, `phone`, `building`, `dollar`, `info`, `briefcase`. Pick the closest; dates and types without `icon` get a default |
| Form spread across a wide screen | `"width": "full"` (or a pixel width) |
| Buttons at the right / centre of the page | `"buttonAlign": "right"` / `"center"` |

The `banner` replaces the plain page title with a header strip in `primary`:

- `title`: the heading in the strip (default: the coach title);
- `product`: a product or system name shown large, e.g. "QUOTE DESK";
- `text`: a short greeting or note at the right;
- `logo`: cut the logo out with `crop_image` (`dest` in `work/`, e.g. `work/<acr>-logo.png`) and point to that file. Check the returned crop and adjust the box until the whole logo is in and the edges are clean. Keep logos in `work/`, never in `app-specs/`.

## 4. Write the spec

Path: `work/<ACRONYM>.app.json`. Follow the baw-app-builder skill for the `app`, `businessObject` and `service` keys. Use `app-specs/example-supplier-registration.json` as the model for sections and choices, and `app-specs/example-themed-quote.json` for tabs, theme, banner, placed columns, field icons and Cancel:

```json
{ "layout": "tabs",
  "theme": { "primary": "#5aa9d6", "heading": "#1f5f99", "button": "#2f74c0", "secondaryButton": "#e8a33d",
             "background": "#f5f6f8", "font": "Open Sans", "shape": "pill", "fieldIcons": true, "width": "full", "buttonAlign": "right" },
  "banner": { "product": "QUOTE DESK", "text": "Good afternoon", "logo": "work/zzqd-logo.png" },
  "form": { "title": "New Quote", "nextLabel": "Submit", "cancelLabel": "Cancel" },
  "steps": [
    { "title": "General", "sections": [
      { "title": "General", "columns": 3, "widths": [1, 1.5, 1], "fields": [
        { "name": "quoteNumber", "label": "Quote #", "column": 1, "icon": "hash" },
        { "name": "broker", "label": "Broker", "column": 2, "icon": "user" },
        { "name": "renewal", "label": "Renewal", "type": "Boolean", "column": 3 }
      ]}
    ]}
  ]}
```

Build only the screens in the screenshots, plus what they clearly lead to. If the last screen's forward button says "Continue" or "Next", the user expects something after it: add a read-only review (`"review": { "title": ... }`) and, for a submission, a `confirmation`. If it says "Submit" and the user asked for nothing more, set `"review": false`.

## 5. Build, install, compare

1. `create_app` with the spec. Fix every problem it lists.
2. `install_app` with the returned `.twx`. Continue only when `"ok": true`.
3. `test_service` with `fill: false`. It returns a screenshot for each coach.
4. **Compare.** `view_image` each test screenshot next to its original and check, in order:
   - **header:** banner colour, logo, title, product name and text in the same places;
   - **tabs and sections:** titles, order, active tab colour, section bar colour;
   - **columns:** the same number, the same relative widths, and every field in the same column and order;
   - **fields:** same label, same control, icon box when the original has one, required markers, help icons;
   - **buttons:** labels, colours, order and position (left, centre or right);
   - **colours overall:** page background, buttons and bars match the sampled colours.

   Fix the spec, bump `app.snapshot`, and repeat from 1 until all of them match. Font rendering and exact pixel spacing may differ slightly; anything else is a difference to fix.

## 6. Report

- The app, acronym, snapshot and run URL (`list_services`).
- For each screen, its sections, with the field and column counts.
- The theme colours you sampled and where each one is used.
- **Assumptions**, for example dropdown options you chose and help texts you wrote.
- **Not built**: things in the screenshot that the app spec cannot express, such as tables, file uploads, links and menus. For each one, offer to add it in a React screen.

## Then: a React version (optional)

Only when the user asks for the screens to be modernized:

1. `inspect_coaches` on the `.twx`. It writes the coach spec with the sections, columns (in reading order), dropdown and radio options, and required flags you built.
2. Follow the coach-inventory, react-coach-screen and coach-modernize skills.

A React screen can follow the screenshot's layout more closely. `Field` renders `select` and `radio`. `<div className="pp-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>` gives exactly two columns. The screen can also add the items listed under "Not built".
