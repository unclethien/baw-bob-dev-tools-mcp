# Talk track: Sprint 2 vs Sprint 3

The words to say with the slides in [index.html](index.html). The slide content and references are in [content.md](content.md).

Word for word, about 6 minutes of talk. Actions are in italics. On the page, press **N** or the **Notes** button to show this slide's lines at the bottom of the screen; press it again to hide them before you share your screen.

**Slide 1. Opening** (45 s)

"Thanks for joining. In the next few minutes I want to show you one thing: what changed between Sprint 2 and Sprint 3, and why it matters for your team."

*Point at the grey 2 and the loose pieces under it.*

"A quick reminder of where we were. In Sprint 2, Bob rebuilt your Quote screen from small widgets: a text field, a checkbox, a button. Each one is a piece your developers can drag around in BAW's Coach Designer."

"That was a big step forward. But you asked for bigger pieces. The same block of fields shows up on several screens, and nobody wants to build it again every time. And there was a second gap: nothing the screen collected was saved to a database."

*Point at the blue 3 and the group under it.*

"Sprint 3 closes both gaps. A whole section is now one piece you drag in, and the screen remembers every quote."

*Next slide.*

**Slide 2. At a glance** (1 min)

"Here is the whole story in one table. Grey is Sprint 2, blue is Sprint 3."

*Go down the rows.*

"What you drag: before, one field at a time. Now, a whole section, like Group Contact."

"Where it lives: the widgets live in a shared toolkit that every app can use. The new groups live inside your own app, where your team finds them under User interface."

"The review screen: before, it had its own separate list. Now we drop the same group on the review, set to read-only."

"And the last two rows are the ones I'd ask you to remember. Change a group once, and every screen follows. And the data is saved."

"So: Sprint 2 was about the pieces. Sprint 3 puts the pieces together, and keeps the data."

*Next slide.*

**Slide 3. Drag a whole section** (1½ min)

*Press Replay, so the room sees both sides move.*

"On the left is Sprint 2. To build the contact section, a developer drags in a Section, then four fields, one at a time. Five drags. And the review screen needs all of that again."

"On the right is Sprint 3. Group Contact is one item in the palette. One drag on the form, one on the review, and all four fields come along."

*Point at the read-only review.*

"Same group, two settings. On the form, people can type. On the review it's read-only, so nobody changes a quote by accident. And optional fields can be hidden where they aren't needed."

"Here's the part that matters for maintenance. If your team adds, moves or renames a field in the group, every screen that uses it follows. Once they save a snapshot, Bob sees the change, and when it rebuilds the app later it keeps their work. It tells you what changed, and asks before replacing anything."

"Two more things. Each group can be tested on its own. And the modern React and Carbon version of the app gets a matching modern copy of every group."

*Next slide.*

**Slide 4. The screen now remembers** (1½ min)

"Now the second change. In Sprint 2 the form collected the data, but nothing went into a database. In Sprint 3 every quote becomes a row in a table."

*Point at the first picture, then the green row.*

"Someone fills in a quote and presses Submit. The quote is saved, and they get a reference number. That's the green row in the middle: Lighthouse Bakery, just saved."

*Point at the blue row, then the last picture.*

"Later, anyone opens an empty form, types the group name and presses Load. The whole quote comes back. That's the blue row, Northwind Logistics, loaded back into the form."

*Point at the three notes along the bottom.*

"Three things I want everyone to hear. One: the app doesn't need Bob to run. It saves and loads through BAW's own connection to the database, and your developers can open and run those steps in BAW themselves."

"Two: it's safe. Bob only writes to the database set aside for apps. Changing BAW's own records needs a person to approve it, and Bob backs up first."

"Three: nobody wrote database code. Bob designed the table from the form itself, one column for each field."

*Next slide.*

**Slide 5. What changes for your team** (1 min)

"So what does this mean for your team?"

"Build faster. A section is built once and reused, instead of rebuilt on every screen. Bob suggests which sections should become groups, and shows you before it builds anything."

"Maintain in BAW. Groups are normal BAW building blocks. Your developers change them in the designer, without going back to Bob."

"Keep the data. Every quote is saved and can be loaded again, ready for reports and for the next step of the work."

*Pause on the closing line.*

"Sprint 2 proved Bob can build with your toolkit. Sprint 3 makes the result reusable, maintainable and connected to your data. Thank you. Happy to take questions."

**If someone asks**

- *"Can we still drag single widgets?"* "Yes. The widget toolkits are still there, and every group is made from those same widgets. Groups just save you from placing them one by one."
- *"What if our developer changes a group, and then Bob rebuilds the app?"* "Save a snapshot after the change. Bob keeps the changed group, tells you what changed and asks whether to keep it or replace it."
- *"Where does the data actually live?"* "On the platform's own database server, in the database set aside for your apps. BAW's own records are on the same server; Bob can read them, but changing them needs a person's approval."
- *"Who decides what becomes a group?"* "Bob proposes a group when three or more fields appear on two or more screens, or uses the groups you name. It shows them to you before it builds."
