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
| Give an existing app a React or modern UI, modernize, restyle or re-theme its screens, or verify modernized services | `baw-coach-modernizer` |

In the reason, repeat what the user asked for, with any app, acronym, files or screenshots they named. Do not start the work before switching: do not load the BAW skills or call the baw-dev-tools build, install or test tools.

Questions about this repository's code, documentation or the MCP server itself stay in the current mode.
