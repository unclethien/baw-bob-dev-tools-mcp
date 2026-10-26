# BAW Bob Dev Tools MCP

An MCP server that lets an AI coding agent such as [IBM Bob](https://bob.ibm.com) build and modernize IBM Business Automation Workflow (BAW) process apps end to end, from a written requirement or from screenshots of the screens. The agent designs and writes: app specs, theme files, coach specs and, where needed, React + Carbon screens. The server does the platform work: it packages TWX files, builds the coaches from two toolkits of drag-and-drop widgets, installs them over the BAW Operations REST API, inspects coaches, and tests every screen in a real browser.

> Not an official IBM project. Use it with test servers and test apps.

**Documentation:** <https://unclethien.github.io/baw-bob-dev-tools-mcp/>: getting started, the app spec reference, a terminal guide for exporting and importing apps, and the BAW REST API usage reference.

## What the agent can do with it

| Tool | What it does |
|---|---|
| `list_apps` | Process apps and toolkits on the server |
| `list_snapshots` | Snapshots of an app, oldest first |
| `list_services` | Services users can launch, with run URLs |
| `export_app` | Download a snapshot to `work/<ACR>-<snapshot>.twx` |
| `view_image` | Show the agent an image from the project: a screenshot to build from, or one `test_service` took |
| `image_colors` | Main colours of a screenshot or one region of it, as hex: the theme colours to build with |
| `crop_image` | Cut a region out of a screenshot into `work/`, e.g. its logo for the banner |
| `inspect_coaches` | Read every coach (sections, fields, buttons, flow, reusable groups) into an editable coach spec; lists sections worth making a group, and groups someone changed in BAW |
| `build_widget_toolkit` | Build App Builder Widgets (`builder`) or Modernizer Widgets (`modernizer`) as a toolkit `.twx`, a new snapshot each time |
| `create_app` | Build an installable `.twx` from an app spec, its coaches made of App Builder Widgets and reusable groups, from a built-in template or matching an app you pick; a new snapshot when the app exists, keeping groups someone changed in BAW unless told to replace them |
| `build_screens` | Compile the widgets and the hand-written React screens; returns compiler errors with file and line |
| `modernize_app` | Add a React + Carbon copy of each service, its coaches made of Modernizer Widgets and the app's groups rebuilt as "(Modernized)" Views, styled by the app's theme file, as a new snapshot |
| `install_app` | Install a `.twx` (an app or a widget toolkit) and wait for the result |
| `test_service` | Walk a service in a browser: screenshot each screen, fill sample values, press the forward button |
| `test_process` | Start an app's workflow and work every task it creates in a browser, pressing the buttons you name (e.g. Send Back once), until it completes |

Guard rails:
- Bob installs into an app it did not create in the same task only after you approve. This is a rule of the Bob modes; the tools do not check it.
- Reusing a snapshot name is refused, because BAW would silently keep the old content.
- There is no delete tool.
- Credentials stay inside the server process and are never returned to the agent.

## How it fits together

```
Agent (Bob) ── writes ──▶ work/*.theme.json, work/*.app.json, work/*.coaches.json, coach-ui/src/screens/*.jsx
     │
     └── calls MCP tools ──▶ server/baw_mcp.py ──▶ generators (TWX) ──▶ BAW Operations REST API
                                        │    └── widget toolkits (ABW, MDW) from coach-ui/widgets/
                                        └──▶ verify-service.mjs (headless browser) ──▶ screenshots in work/
```

- **Theme file** (`*.theme.json`): the look of an app, which Bob writes from the user's description or a screenshot: colours, font, corner shape, field icon boxes, width, button placement, and the header's product name and logo. Bob asks for a look when none is given; there is no default. The same file styles the classic coaches `create_app` builds and the React + Carbon coaches `modernize_app` adds, so changing the look means editing one file and rebuilding. Examples: `app-specs/example-*.theme.json`.
- **App spec** (`app-specs/`): business object, steps or tabs (`"layout": "tabs"`), titled sections with 1-6 columns (fields placed per column, relative column widths), fields (text, text area, date, checkbox, integer, decimal, dropdown, radio group; required markers and help text), button labels including Cancel, review and confirmation, the `theme` file it uses and an optional `banner` (the header strip's title and text). `create_app` turns it into a client-side human service exposed as a URL, built from standard UI Toolkit views placed in App Builder Widgets. `example-equipment-request.json` is a simple multi-step form; `example-supplier-registration.json` was written from `screenshots/example-supplier-registration.png`; `example-themed-quote.json` shows tabs, a banner, placed columns, field icons and Cancel; `example-grouped-quote.json` shows reusable groups (see [Reusable groups](#reusable-groups)). An optional `process` section adds a workflow on top: the form becomes the first task of a process with lanes, and an `approval` adds a review task in a second lane with Approve and Send Back, where Send Back returns the work to the form. The diagram opens and can be edited in Business Automation Studio's process editor.
- **Coach spec**: written by `inspect_coaches` and refined by the agent: labels, required fields, patterns, examples, help text, and the `theme` file for the modernized coaches. A coach with `"screen": "<name>"` shows a React screen the agent wrote in `coach-ui/src/screens/<name>.jsx`; other coaches are rebuilt from Modernizer Widgets inside native Panels or a Tab Section, so they stay editable by drag and drop in Coach Designer. Either way the legacy coach flow, scripts and variables keep running underneath.

## Widget toolkits

The coaches both tools build are layouts of small widgets, so authors can open them in Coach Designer and drag, drop, relabel and rearrange them. The widgets ship as two BAW toolkits that any process app can depend on:

| Toolkit | Acronym | Used by | Widgets | Built with |
|---|---|---|---|---|
| **App Builder Widgets** | `ABW` | `create_app` | Theme, App Header, Section, Review List, Button Bar | BAW markup and plain JavaScript, no framework; the fields inside are UI Toolkit views |
| **Modernizer Widgets** | `MDW` | `modernize_app` | Theme, Header, Error Summary, Text Field, Text Area, Number Field, Date Field, Checkbox, Select, Radio Group, Button | React + Carbon, behind a framework-neutral contract |

Each widget shows in the palette with its icon and draws a preview on the canvas that follows its label and options. `build_widget_toolkit` builds a toolkit as `work/<ACR>-<snapshot>.twx`; install it once per server with `install_app`, then pass its snapshot as `create_app` or `modernize_app`'s `toolkit_snapshot`. Bob does both when the server has no snapshot yet. Each build is a new snapshot of the same toolkit, and an app keeps the snapshot it was built with until it is built again.

The widgets live in `coach-ui/`: `widgets/*-widgets.json` lists each widget's view name, options and icon (`widgets/icons/`, `widgets/builder/icons/`), `widgets/builder/` holds the App Builder widgets' markup and scripts, and `src/widgets/` the Modernizer widgets. `src/screens/` holds the screens hand-written for single coaches; such a coach is one block in Coach Designer. Changing a widget is a code change: ask Bob in Agent mode, then build and install a new toolkit snapshot.

The Modernizer can also add a widget while it modernizes an app, when no Modernizer Widget does the job (for example a Yes/No Toggle for Boolean questions). It lists the new widget in the plan it shows you, then writes three files: the React + Carbon component `coach-ui/src/widgets/<kind>.jsx`, its entry in `coach-ui/widgets/modernizer-widgets.json` and its palette icon `coach-ui/widgets/icons/<kind>.svg`, plus `coach-ui/src/widgets/<kind>.scss` when it uses a Carbon component the other widgets don't. It checks the widget offline, builds and installs a new `MDW` snapshot, and uses it in the app; the widget is then in the palette for every app on that snapshot. A widget binds one value (a String, Integer, Decimal, Boolean or Date). The steps are in the skill [`.bob/skills/modernizer-widget/SKILL.md`](.bob/skills/modernizer-widget/SKILL.md). Changing or removing an existing widget stays a code change for Agent mode, because other apps use it.

## Reusable groups

When the same information appears on several screens, Bob can build it once as a **group**: a View inside the app, listed in Workflow Center under the app's User interface, that every coach places. A contact block can sit editable on the form, read-only for reference on a later step, and on the review, all from one View. Each group also gets a "<group> Preview" client-side human service that shows it alone.

- **Classic UI:** the app spec's `groups` define them, and a section `{"group": "<name>", "readonly": true, "hide": [...]}` places one (details in [docs/app-spec-reference.html](docs/app-spec-reference.html#groups)). The fields inside are BAW's own.
- **Modernized UI:** `inspect_coaches` reads the groups back, and `modernize_app` builds "<group> (Modernized)" from Modernizer Widgets, with its own Preview service.
- **Settings per placement:** a "<field> visibility" setting for each optional field (Same as parent, or Hidden), and the placement's own Visibility for Read only.
- **Proposals:** Bob proposes a group for three or more fields that appear on two or more screens, or uses the groups you name, and shows them for approval before building.
- **Changes in Coach Designer:** users can add, remove, move or relabel a group's fields and every coach follows. Save a snapshot, so Bob sees the change. On the next rebuild Bob keeps that group, says what changed and asks whether to keep it or replace it with the spec's version (`replace_groups`). Other edits to a group (help text, choices, styling) belong in the spec, because a rebuild replaces them.

The steps Bob follows are in [`.bob/skills/coach-groups/SKILL.md`](.bob/skills/coach-groups/SKILL.md).

## Requirements

- An IBM BAW server on Cloud Pak for Business Automation, with an account that can install process apps. Without one, the agent still builds the `.twx` files and you import them yourself (see [Without a BAW server](#without-a-baw-server)).
- [uv](https://docs.astral.sh/uv/) (runs the server with its pinned MCP dependency), Python 3.11+
- Node.js 18+ and Google Chrome, Brave or Helium (for `build_screens`, `build_widget_toolkit("modernizer")`, `modernize_app` and `test_service`). Set `BROWSER_PATH` to use another Chromium.

## Setup

```bash
git clone https://github.com/unclethien/baw-bob-dev-tools-mcp.git
cd baw-bob-dev-tools-mcp
cp .env.example .env            # then fill in BAW_URL, BAW_USER, BAW_PASSWORD or BAW_APIKEY
chmod 600 .env
(cd coach-ui && npm install)
# A clone made before coach-ui/ was renamed from react-coach/: git does not move ignored files, so first run
# mkdir -p coach-ui/src && mv react-coach/src/screens coach-ui/src/ && rm -rf react-coach
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
   - **✨ BAW Coach Modernizer** gives an existing app a React + Carbon UI built from Modernizer Widgets, with a hand-written screen for any coach that needs one.

   Bob switches between them in the same chat, and from Agent mode into the right one (`.bob/rules/baw-mode-routing.md`): ask for a React UI after building an app and it moves to the Modernizer; ask the Modernizer for a new app or new fields, steps or a workflow and it moves back to the App Builder. To skip the switch prompt, allow **Mode** in Bob's auto-approve settings. Both modes edit only `work/` and `app-specs/` (the Modernizer also `coach-ui/src/screens/`, and `coach-ui/src/widgets/` and `coach-ui/widgets/` to add a widget), and do everything else through the MCP tools.
2. Copy `.bob/mcp.example.json` to `.bob/mcp.json` and set the absolute path to `server/baw_mcp.py`. To switch servers without editing `.env`, add an `"env": { "BAW_URL": "..." }` block there.
3. Check that `baw-dev-tools` shows as connected in Bob's MCP panel with 15 tools.
4. Try it in BAW App Builder mode:

   ```
   Build a small ZZ app for an office supply request: one step with requester name,
   item, quantity and needed-by date, then a review screen. Navy header, white text,
   rounded buttons, "Office Supplies" as the product name. Install it and test it.
   ```

   Or build from a screenshot. Attach one in the chat, or put it in `screenshots/` and name it:

   ```
   Build a ZZ app whose screen looks like screenshots/example-supplier-registration.png.
   Install it, test it and compare the result with the screenshot.
   ```

   Bob reads the screen with the screenshot-to-app skill: its layout (tabs, sections, columns and their widths, which field sits where), its controls (labels, dropdowns, radio groups, checkboxes, required markers, help icons, buttons) and its look (colours sampled with `image_colors`, the header banner with the logo cut out by `crop_image`, field icons, shapes, button placement). It writes the theme file and the app spec, shows you the design and waits for your approval, builds it, asks whether to import it into BAW, then installs it and compares the test screenshots with the original and fixes any differences. It lists what it assumed, such as the options of a closed dropdown, and what the spec cannot express, such as tables or file uploads.

Before building a new app, Bob shows you the design (look, screens, fields, buttons, assumptions) and waits for your approval. The first time on a server, it builds and installs the widget toolkit the app needs. After building, it asks whether to import the app into BAW. Bob's tool prompts also ask before `create_app`, `crop_image`, `modernize_app` and `install_app`; the read and test tools run without asking.

## Without a BAW server

Leave `BAW_URL` unset and the build tools still work: `build_widget_toolkit`, `create_app`, `inspect_coaches`, `build_screens`, `modernize_app` and the image tools. `create_app` builds the app from a built-in template in BAW's no-toolkits export format (`server/app_template.py`, matching BAW 26.0.0), so nothing has to be downloaded first. Its result says where the `.twx` is, and which widget toolkit `.twx` to import before it, unless the server already has that snapshot; import both in Workflow Center (Process Apps, Import). The server tools (`list_apps`, `install_app`, `test_service`, ...) say that no server is configured.

To add a snapshot to an app you already have, export it from Workflow Center, put the `.twx` in `work/` and pass it as `create_app`'s `base`. With a server, `base` can name any installed app instead, so the package matches that server's BAW build and toolkit versions.

## Use it with other MCP clients

Any stdio MCP client works:

```json
{ "command": "uv", "args": ["run", "--quiet", "--script", "/ABSOLUTE/PATH/TO/baw-bob-dev-tools-mcp/server/baw_mcp.py"] }
```

The scripts also run on their own, e.g. `python3 server/baw_ops.py list`, `python3 server/widget_toolkit.py build builder 1.0.0 work/ABW-1.0.0.twx`, `python3 server/generate_app.py app-specs/example-equipment-request.json work/ZZEQ.twx --toolkit work/ABW-1.0.0.twx`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
