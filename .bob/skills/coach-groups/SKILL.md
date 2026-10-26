---
name: coach-groups
description: Build reusable groups of fields - BAW Views inside the app, listed under its User interface, each with a "<group> Preview" service - for the classic coaches (create_app) and the React + Carbon coaches (modernize_app), propose them from fields that repeat across screens, and handle groups someone changed in BAW on the next rebuild. Use when the same information appears on several screens, when the user names groups, or when a build reports changedInBaw.
---

# Coach groups

A **group** is a set of fields that appears on several screens, for example a member's contact details on the form, again for reference on a later step, and on Review. Instead of repeating the fields, the app gets one **View** for the group, and every coach places it.

- The View is listed in Workflow Center under the app's **User interface**, next to its services. Users open it, add, remove or move fields, and every coach that places it follows.
- Each group also gets a client-side human service, **"<group> Preview"**, that shows only the group, so it can be run and tested on its own.
- Classic coaches place "<group>" (BAW's own fields); modernized coaches place "<group> (Modernized)" (Modernizer Widgets).
- Each placement has settings: a **"<field> visibility"** dropdown per optional field ("Same as parent", or "Hidden" to hide it there), and the placement's own **Visibility** ("Read only" makes every field in the group read-only).

## When to propose groups

At the design stop (baw-app-builder step 3, screenshot-to-app section 5, the Modernizer's analyze stop):

- When the user named groups in the request, use them.
- Otherwise propose a group for a set of **at least three fields that appears on at least two screens** (a form section and the Review that repeats it, or the same details on two steps). `inspect_coaches` lists these as `groupCandidates`. Do not propose smaller groups unless the user asks.
- Show each proposed group: its name, its fields, and where it is placed (editable, read-only, fields hidden). Build only after the user approves.

## Classic app (create_app)

In the app spec (see `app-specs/example-grouped-quote.json`), list the groups once at the top, with their fields, and place them in sections:

```json
"groups": [
  { "name": "Group Contact", "columns": 2, "fields": [
    { "name": "groupName", "label": "Group Name", "required": true },
    { "name": "contactEmail", "label": "Contact Email", "icon": "mail" } ] }
],
"steps": [
  { "title": "Group", "sections": [ { "group": "Group Contact" } ] },
  { "title": "Rating", "sections": [
    { "group": "Group Contact", "title": "Contact (for reference)", "readonly": true, "hide": ["contactEmail"] } ] }
]
```

- A group's fields follow the rules of any field and belong to the business object once, however often the group is placed. A field is in one group or in a section, not both.
- A section that names a group has no `fields`; `title` defaults to the group's name, and `intro` shows above the group as in any section; `readonly` and `hide` set that placement. A required or read-only field cannot be hidden.
- Name a group with words, digits, spaces and hyphens ("Waivers and Credits", not "Waivers/Credits"): the name becomes a View and a service name. The section's `title` can still show the original text.
- A group can have any number of fields; propose groups of three or more yourself, and make smaller ones only when the user asks.
- Review places every group read-only, once, so a group repeated for reference is not shown twice. It hides only the fields that every placement hides.

## Modernized app (modernize_app)

`inspect_coaches` reads the groups of a classic app back: the coach spec's `"groups"` and a section `{"title", "group", "readonly", "hide"}` where a coach places one. Keep them; `modernize_app` builds "<group> (Modernized)" and its Preview service from them. To add groups to an app that has none, add `"groups": [{"name", "fields": [fields as in a section]}]` to the coach spec and replace each section that repeats them with `{"title", "group", "readonly", "hide"}`. A group belongs to one business object, and a coach with a hand-written `"screen"` cannot place one.

## When someone changed a group in BAW

Bob notices when someone changed **which fields** a group has in Coach Designer: added, removed, moved or relabelled a field. Other edits to a group (help text, choices, styling) are not noticed and a rebuild replaces them, so make those in the spec. Only groups Bob built are read back as groups; other Views the app has stay as they are.

Bob sees changes made in BAW only once they are in a **snapshot**: `create_app` builds on the app's newest snapshot, and `export_app` / `inspect_coaches` read snapshots. Before a rebuild, when the user says they changed the app in Coach Designer, ask them to create a snapshot of it first (Workflow Center, the app, Snapshots).

`inspect_coaches` lists the groups changed in BAW since Bob built them (`changedInBaw`). On a rebuild, `create_app` and `modernize_app` keep such a group exactly as it is on the server and list it in their result's `changedInBaw`. Then, **before `install_app`**:

1. Tell the user which groups were changed in BAW and kept.
2. Describe each change: compare the group's fields in `inspect_coaches` of the newest snapshot with the spec (labels, order, fields added or removed).
3. Ask, per group: keep BAW's version, or replace it with the version from the spec?
4. For the ones to keep, change the spec to match BAW's version (labels, order, added fields), so the next rebuild does not ask again.
5. For the ones to replace, build again with `replace_groups: ["<group>", ...]` and the same snapshot name. Use the group's name ("Group Contact"); for `modernize_app` the View's name ("Group Contact (Modernized)") works too. A name that is not a group of the spec is refused.

If the build says a kept group "uses fields the app spec does not have", someone added a field in BAW: add that field to the spec (same name and type) and build again, or replace the group.

## Report

List each group with its fields, where it is placed (and how: editable, read-only, hidden fields), its Preview service, and any group changed in BAW with what the user chose. Mention that the groups open from the app's User interface in Workflow Center.
