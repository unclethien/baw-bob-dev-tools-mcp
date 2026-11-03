# Sprint 2 vs Sprint 3: from single widgets to whole sections that remember

A short presentation for the client team and their managers. It shows what changed in the Coach UI between Sprint 2 and Sprint 3. In Sprint 2 you dragged one field at a time; in Sprint 3 you drag a whole section, and the screen saves to the database. Five slides, about six minutes. The word-for-word talk track is in [talk-track.md](talk-track.md).

- **Sprint 2, "Quote widgets":** the Quote screen built from small widgets in two toolkits.
- **Sprint 3, "Groups and the database":** the same screen built from reusable groups (Views inside the app) that save and load each quote.

---

## Slide 1. From single widgets to whole sections that remember

**Headline.** Sprint 2 gave us the bricks. Sprint 3 gives us whole walls, and the screen remembers.

**Say.**
- "In Sprint 2 Bob built your Quote screen from small widgets. Each one is a single field or control you can drag in Coach Designer."
- "You asked for bigger reusable pieces that your team can maintain in BAW, and for a screen that keeps what people type."
- "Sprint 3 delivers both: whole sections you drag and drop as one piece, and a Quote screen that saves to the database and loads back."

---

## Slide 2. At a glance

| | Sprint 2: Quote widgets | Sprint 3: Groups and the database |
|---|---|---|
| **What you drag in Coach Designer** | One widget: a text field, a checkbox, a button | A whole section, a group such as "Group Contact" |
| **Where it lives** | A toolkit every app can use (ABW classic, MDW React + Carbon)[^toolkits] | Inside your app, as a View under User interface[^reuse] |
| **Reuse across steps** | Rebuild the same fields on each screen | Place the same group on the form and on the review |
| **Read-only review** | A separate review list | The same group, placed read-only[^visibility] |
| **Change it once** | Change each screen | Change the group; every screen that uses it follows |
| **Data** | Nothing saved to a database | Submit saves the quote; Load brings it back |

**Say.** "Sprint 2 was about the pieces. Sprint 3 is about putting the pieces together, and keeping the data."

---

## Slide 3. Drag a whole section, not one field

**Sprint 2.** Each widget is a normal BAW view with a palette icon and a live preview, so a developer can drag it, drop it and see it change.[^preview] To make a section, you drop a Section, then each field into it, on every screen that needs it.

**Sprint 3.** Bob builds each repeated section once, as a **group**: a View inside the app that combines the widgets.[^reuse]

- **Drag it in once.** The group sits in Coach Designer's palette. Drop it on any screen and all its fields come with it.[^palette]
- **Configure each placement.** Show it editable on the form and read-only on the review. Hide its optional fields where they are not needed.[^visibility][^options]
- **Change it in one place.** Add, remove, move or relabel a field in the group and every screen follows. Bob sees the change in the next snapshot and keeps it on a rebuild, unless you ask to replace it.
- **Test it alone.** Each group has its own Preview service, so it can be run on its own.
- **Modern too.** The React + Carbon copy gets a "(Modernized)" version of every group, built from Modernizer Widgets.

**Say.** "In Sprint 2 a section was a dozen drags. In Sprint 3 it is one drag, and your developers own it in BAW."

---

## Slide 4. The screen now remembers

**Sprint 2.** The screen was a form only: nothing it collected was stored in a database.

**Sprint 3.** The app saves each quote to a table in the app database, and loads it back by its key.

1. **Type and submit.** Submit saves the quote, one column per field. The confirmation shows a reference number.
2. **Load it back.** Open an empty form, type the Group Name and press Load. Every field comes back.
3. **No Bob needed at run time.** The app saves and loads through BAW's own connection to the app database.[^sql] Load and Save are BAW service flows, so a developer can open and run them in the designer.
4. **Safe by design.** Bob writes to the app database only. BAW's own records it can read; changing one needs a person's approval, and Bob backs up the tables first.

**Say.** "That quote now lives in the database, not in someone's inbox or spreadsheet. And Bob designed the table from the form itself, so nobody wrote database code."

---

## Slide 5. What changes for your team

1. **Build faster.** One group replaces the same fields rebuilt on every screen. Bob proposes groups for three or more fields that repeat on two or more screens, and shows them before building.
2. **Maintain in BAW.** Groups are ordinary BAW Views. Your developers change them in Coach Designer, without going back to Bob.
3. **Keep the data.** Every quote is saved and can be loaded again, ready for reports and for the next step of the work.

**Say.** "Sprint 2 proved Bob can build with your toolkit. Sprint 3 makes the result reusable, maintainable and connected to your data."

---

## References

[^reuse]: IBM, Developing reusable views (BAW 26.0.x). https://www.ibm.com/docs/en/baw/SS8JB4_26.0.x/com.ibm.wbpm.wle.editor.doc/topics/tcreatingviews.html
[^toolkits]: IBM, Creating, changing, and deleting a toolkit dependency in the Designer view. https://www.ibm.com/docs/en/baw/19.0.0?topic=mut-creating-changing-deleting-toolkit-dependency-in-designer-view
[^preview]: IBM, Event handlers for view design-time preview (BAW 26.0.x). https://www.ibm.com/docs/en/baw/26.0.x?topic=api-event-handlers-view-design-time-preview
[^palette]: IBM, Laying out a coach or coach view using the grid layout. https://www.ibm.com/docs/en/bpm/8.6.0?topic=cui-laying-out-coach-coach-view-using-grid-layout
[^visibility]: IBM, Setting the visibility of coach views. https://www.ibm.com/docs/en/bpm/8.6.0?topic=views-setting-visibility-coach
[^options]: IBM, Configuration properties and configuration options. https://www.ibm.com/docs/en/SSFPJS_8.6.0/com.ibm.wbpm.wle.editor.doc/topics/c_config_options.html
[^sql]: IBM, Invoking SQL integration flows (Business Automation Workflow). https://www.ibm.com/docs/en/baw/20.0.0?topic=service-invoking-sql-integration-flows

Project sources: `README.md` (Reusable groups, Database access), `docs/showoff/quote-widgets-demo-script/`, `docs/showoff/groups-and-database-demo-script/`.
