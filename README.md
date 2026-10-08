# BAW Bob Dev Tools MCP

An MCP server that lets an AI coding agent such as [IBM Bob](https://bob.ibm.com) build and modernize IBM Business Automation Workflow (BAW) process apps end to end, from a written requirement or from screenshots of the screens. The agent designs and writes: app specs, coach specs and React + Carbon screens. The server does the platform work: it packages TWX files, installs them over the BAW Operations REST API, inspects coaches, and tests every screen in a real browser.

> Not an official IBM project. Use it with test servers and test apps.

## What the agent can do with it

| Tool | What it does |
|---|---|
| `list_apps` | Process apps and toolkits on the server |
| `list_snapshots` | Snapshots of an app, oldest first |
| `list_services` | Services users can launch, with run URLs |
| `export_app` | Download a snapshot to `work/<ACR>-<snapshot>.twx` |
| `view_image` | Show the agent an image from the project: a screenshot to build from, or one `test_service` took |
| `inspect_coaches` | Read every coach (sections, fields, buttons, flow) into an editable coach spec |
| `create_app` | Build an installable `.twx` from an app spec; a new snapshot when the app exists |
| `build_screens` | Compile the React screens; returns compiler errors with file and line |
| `modernize_app` | Add React + Carbon copies of each service (brand and carbon themes) as a new snapshot |
| `install_app` | Install a `.twx` and wait for the result |
| `test_service` | Walk a service in a browser: screenshot each screen, fill sample values, press the forward button |

Guard rails:
- Only apps whose name starts with "ZZ" and whose acronym starts with `ZZ` can be installed.
- Reusing a snapshot name is refused, because BAW would silently keep the old content.
- There is no delete tool.
- Credentials stay inside the server process and are never returned to the agent.

## How it fits together

```
Agent (Bob) ── writes ──▶ work/*.app.json, work/*.coaches.json, react-coach/src/screens/*.jsx
     │
     └── calls MCP tools ──▶ baw_mcp.py ──▶ generators (TWX) ──▶ BAW Operations REST API
                                        └──▶ verify-service.mjs (headless browser) ──▶ screenshots in work/
```

- **App spec** (`app-specs/`): business object, steps or tabs (`"layout": "tabs"`), titled sections with 1-3 columns, fields (text, text area, date, checkbox, integer, decimal, dropdown, radio group; required markers and help text), button labels, review and confirmation. `create_app` turns it into a client-side human service exposed as a URL, built from standard UI Toolkit views. `example-equipment-request.json` is a simple multi-step form; `example-supplier-registration.json` was written from `screenshots/example-supplier-registration.png`.
- **Coach spec**: written by `inspect_coaches` and refined by the agent: labels, required fields, patterns, examples. A coach with `"screen": "<name>"` shows a React screen the agent wrote in `react-coach/src/screens/<name>.jsx`; other coaches use a generic form. The legacy coach flow, scripts and buttons keep running underneath, and the React screen presses the coach's own buttons.
- **Themes**: `brand` (a neutral palette; set `"brand": "Your Org"` in the coach spec and change the colours in `react-coach/src/styles.scss`) and `carbon` (IBM Carbon).

## Requirements

- An IBM BAW server on Cloud Pak for Business Automation, with an account that can install process apps, and the **Hiring Sample (HSS)** process app installed. `create_app` uses it once as the packaging base.
- [uv](https://docs.astral.sh/uv/) (runs the server with its pinned MCP dependency), Python 3.11+
- Node.js 18+ and Google Chrome or Brave (for `build_screens` and `test_service`). Set `BROWSER_PATH` to use another Chromium.

## Setup

```bash
git clone https://github.com/unclethien/baw-bob-dev-tools-mcp.git
cd baw-bob-dev-tools-mcp
cp .env.example .env            # then fill in BAW_URL, BAW_USER, BAW_PASSWORD or BAW_APIKEY
chmod 600 .env
(cd react-coach && npm install)
```

Settings are read from the environment first, then `.env`:

| Variable | Meaning |
|---|---|
| `BAW_URL` | Cloud Pak base URL, e.g. `https://cpd-<cluster>` |
| `BAW_USER` | Cloud Pak user |
| `BAW_PASSWORD` | That user's password, or |
| `BAW_APIKEY` | A Cloud Pak Platform API key (used when `BAW_PASSWORD` is not set) |

## Use it with IBM Bob

1. Open this folder as the workspace in Bob. It ships two modes (`.bob/custom_modes.yaml`) and their skills:
   - **🏗️ BAW App Builder** turns a written requirement, or screenshots of the screens, into a running app.
   - **✨ BAW Coach Modernizer** gives an existing app a React UI that Bob writes.

   Both modes edit only `work/`, `app-specs/` and `react-coach/src/screens/`, and do everything else through the MCP tools.
2. Copy `.bob/mcp.example.json` to `.bob/mcp.json` and set the absolute path to `baw_mcp.py`. To switch servers without editing `.env`, add an `"env": { "BAW_URL": "..." }` block there.
3. Check that `baw-dev-tools` shows as connected in Bob's MCP panel with 11 tools.
4. Try it in BAW App Builder mode:

   ```
   Build a small ZZ app for an office supply request: one step with requester name,
   item, quantity and needed-by date, then a review screen. Install it and test it.
   ```

   Or build from a screenshot. Attach one in the chat, or put it in `screenshots/` and name it:

   ```
   Build a ZZ app whose screen looks like screenshots/example-supplier-registration.png.
   Install it, test it and compare the result with the screenshot.
   ```

   Bob reads the screen (sections, columns, labels, dropdowns, radio groups, required markers, buttons) with the screenshot-to-app skill, writes the app spec, builds and installs it, then compares the test screenshots with the original and fixes any differences. It lists what it assumed, such as the options of a closed dropdown, and what the spec cannot express, such as tables or file uploads.

Bob asks for approval before `create_app`, `modernize_app` and `install_app`; the read and test tools run without asking.

## Use it with other MCP clients

Any stdio MCP client works:

```json
{ "command": "uv", "args": ["run", "--quiet", "--script", "/ABSOLUTE/PATH/TO/baw_mcp.py"] }
```

The scripts also run on their own, e.g. `python3 baw_ops.py list`, `python3 generate_app.py app-specs/example-equipment-request.json work/ZZEQ.twx`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
