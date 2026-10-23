# Switching into the BAW modes

This workspace ships two modes for IBM Business Automation Workflow (BAW) apps: 🏗️ BAW App Builder (`baw-app-builder`) and ✨ BAW Coach Modernizer (`baw-coach-modernizer`).

## 1. Never switch in your first reply

Bob fails the whole request when the first reply of a task calls `switch_mode` into a custom mode. In every mode, your first reply of a task must not call `switch_mode`, alone or next to another tool. When a switch is needed, make the first reply a single `list_files` call on `work/`, and call `switch_mode` in your next reply. Do not list the folder of the user's files: the mode you switch to opens exactly the files the user named. Later in a task, switch right away.

## 2. Never switch to the mode you are in

Check your current mode first. In BAW App Builder or BAW Coach Modernizer, do not call `switch_mode` to the same mode, and skip the `list_files` step above: just do the work. Hand-offs between the two BAW modes follow their own rules.

## 3. From any other mode, hand BAW work to a BAW mode

In Agent, Plan, Ask or any other mode, switch without asking (the request is the go-ahead), following section 1:

| The user asks to | Mode slug |
|---|---|
| Build a new BAW app, form, workflow or approval process, from a written requirement or from screenshots; change an app's fields, steps or workflow | `baw-app-builder` |
| Look at, query, import, export or change data in the platform's PostgreSQL databases (the `list_tables`, `describe_table`, `run_sql`, `export_table`, `import_table` and `change_system_db` tools), or build an app that loads and saves a table (the spec's `database` section) | `baw-app-builder` |
| Give an existing app a React or modern UI, modernize, restyle or re-theme its screens, or verify modernized services | `baw-coach-modernizer` |

Database requests go to `baw-app-builder`, even when they have no app: that mode owns the database tools and their rules (read any database, write freely only in `bawexternal`, system databases only through `change_system_db`, which asks first). The Modernizer may read a table to understand an app's data, but it hands any write, and any app that stores data, to the App Builder. The `database` section's Load button and save are built by `create_app`, so the Modernizer's copies of an app's services do not change them.

Ask mode has no `switch_mode`: there, answer in one line which mode to pick (🏗️ BAW App Builder or ✨ BAW Coach Modernizer) and ask the user to switch, instead of doing the work.

In the reason, repeat what the user asked for, with any app, acronym, files or screenshots they named. Do not start the work before switching: do not load the BAW skills or call the baw-dev-tools build, install or test tools.

Questions about this repository's code, documentation or the MCP server itself stay in the current mode.

### The widget toolkits

The coaches these modes build come from two toolkits this repository generates: **App Builder Widgets** (`ABW`, classic widgets, used by `create_app`) and **Modernizer Widgets** (`MDW`, React + Carbon widgets, used by `modernize_app`). They are not the IBM BAW Coach Widget or BAW Package Manager modes' work:

| The user asks to | Where it goes |
|---|---|
| Build or install App Builder Widgets or Modernizer Widgets, or a new snapshot of them | The BAW mode that uses them (`baw-app-builder` for ABW, `baw-coach-modernizer` for MDW), with `build_widget_toolkit` |
| Add a new widget during a modernization (a new Modernizer Widget the plan needs, such as a Yes/No Toggle) | `baw-coach-modernizer`: it follows the modernizer-widget skill and builds a new `MDW` snapshot |
| Change what an existing widget in either toolkit shows or does, add a widget to App Builder Widgets, or change their icons | `agent`: the widgets are code in `coach-ui/widgets/` and `coach-ui/src/widgets/` |
| Rearrange the widgets on one coach | Coach Designer, by hand: drag and drop in the coach's layout |

## 4. From a BAW mode, hand other work back

The BAW modes edit only `work/`, `app-specs/` and, for the Modernizer, `coach-ui/src/screens/` and the files of a new Modernizer widget (`coach-ui/src/widgets/`, `coach-ui/widgets/`). When the user asks a BAW mode for something else, switch without asking, following section 1:

| The user asks to | Mode slug |
|---|---|
| Change this repository's code, scripts, docs or the MCP server; run commands; any other coding task | `agent` |
| Plan or design a larger change before building it | `plan` |

Questions only need reading: answer those in place. In the reason, repeat what the user asked for and name the BAW app and files involved. When that work is done and the user returns to BAW work, switch back to the BAW mode that fits.
