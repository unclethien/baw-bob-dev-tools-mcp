# Project Overview and PDR

## What it is

BAW Bob Dev Tools MCP is a stdio MCP server (`server/baw_mcp.py`) that lets an AI coding agent such as IBM Bob build and modernize IBM Business Automation Workflow (BAW) process apps on Cloud Pak for Business Automation. The agent writes the design artifacts; the server does the platform work. It is not an official IBM project; use it with test servers and test apps.

## Problem

Building a BAW app (business object, coaches, flow, workflow, installable `.twx`) normally needs hand work in Process Designer, and modernizing legacy coaches means rebuilding them by hand. The server turns a written requirement, a screenshot or an existing app into an installed, browser-tested app, without hand-editing TWX XML.

## Users

- A BAW developer or consultant using Bob (or any stdio MCP client) in the two shipped modes: BAW App Builder and BAW Coach Modernizer (`.bob/custom_modes.yaml`).
- Demo and test environments on CP4BA. Without a BAW server the build tools still produce `.twx` files for manual import.

## Product requirements

| Area | Requirement |
|---|---|
| Authoring split | The agent authors app specs, theme files, coach specs and React screens. The server only packages, installs, inspects and tests. |
| App generation | `create_app` builds an installable `.twx` from an app spec: steps or tabs, sections, columns, fields, review and confirmation, optional workflow (BPD) with approval, optional `database` section, reusable groups. |
| Modernization | `inspect_coaches` reads a legacy app into a coach spec; `modernize_app` adds a React + Carbon copy of each service, keeping flow, scripts and variables; services whose groups edit different business objects are supported, and processes are rewired to the copies. |
| Widget toolkits | Two generated toolkits: App Builder Widgets (ABW, classic) and Modernizer Widgets (MDW, React + Carbon). Coaches stay editable in Coach Designer. |
| Look | One theme file styles both classic and modernized coaches. No default theme; the agent asks for a look. |
| Verification | `test_service` and `test_process` run services and workflows in a real browser and screenshot each screen. |
| Database | Six tools read every database on the platform's PostgreSQL server, write freely only in `bawexternal`, and change system databases only through `change_system_db` after user approval with backups. |

## Guard rails (non-functional)

- Credentials stay in the server process and are never returned to the agent.
- Reusing a snapshot name is refused; there is no delete tool.
- Installing into an app Bob did not create in the same task needs user approval (a mode rule, not enforced by the tools).
- Database access uses a limited `bob_mcp` login; the admin login is used only for setup and approved system changes.
- Rows read from a database are data, never instructions.

## Tool surface

21 MCP tools: BAW (`list_apps`, `list_snapshots`, `list_services`, `export_app`, `install_app`), images (`view_image`, `image_colors`, `crop_image`), database (`list_tables`, `describe_table`, `run_sql`, `export_table`, `import_table`, `change_system_db`), build (`inspect_coaches`, `create_app`, `build_screens`, `modernize_app`, `build_widget_toolkit`) and test (`test_service`, `test_process`). Full table in [README.md](../README.md).

## Requirements to run

Python 3.11+ with uv, Node.js 18+, a Chromium browser, and for server features a BAW server (`BAW_URL` and credentials in `.env`) and optionally PostgreSQL admin settings.

## License

Apache 2.0.
