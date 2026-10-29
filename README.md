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
| `list_tables` | The databases on the platform's PostgreSQL server that Bob can read (with `bawexternal`, the app database, marked writable), or the schemas, tables and views of one, with approximate row counts |
| `describe_table` | Columns (type, nullable, default), primary, unique and foreign keys and indexes of a table or view; marks columns that can hold very long values |
| `run_sql` | One SQL statement, up to 1000 rows and 256 KB back. Reads and writes in `bawexternal`; reads only in every other database |
| `export_table` | Write a table, or the result of one `SELECT`, from any readable database to a CSV file under `work/` |
| `import_table` | Load a CSV file or a JSON array of objects from `work/` into an existing `bawexternal` table, appending or replacing (a replace backs the table up first) |
| `change_system_db` | One write on a system database (any database except `bawexternal`), as the admin login, after the user approves it, with the touched rows backed up first |
| `inspect_coaches` | Read every coach (sections, fields, buttons, flow, reusable groups) into an editable coach spec; lists sections worth making a group, and groups someone changed in BAW |
| `build_widget_toolkit` | Build App Builder Widgets (`builder`) or Modernizer Widgets (`modernizer`) as a toolkit `.twx`, a new snapshot each time |
| `create_app` | Build an installable `.twx` from an app spec, its coaches made of App Builder Widgets and reusable groups, from a built-in template or matching an app you pick; a new snapshot when the app exists, keeping groups someone changed in BAW unless told to replace them |
| `build_screens` | Compile the widgets and the hand-written React screens; returns compiler errors with file and line |
| `modernize_app` | Add a React + Carbon copy of each service, its coaches made of Modernizer Widgets and the app's groups rebuilt as "(Modernized)" Views, styled by the app's theme file, as a new snapshot |
| `install_app` | Install a `.twx` (an app or a widget toolkit) and wait for the result |
| `test_service` | Walk a service in a browser: screenshot each screen, fill sample values, type the values you give it (`values`), press the forward button or the buttons you name (`press`, e.g. Load) |
| `test_process` | Start an app's workflow and work every task it creates in a browser, pressing the buttons you name (e.g. Send Back once), until it completes |

Guard rails:
- Bob installs into an app it did not create in the same task only after you approve. This is a rule of the Bob modes; the tools do not check it.
- The database tools log in as a limited PostgreSQL login that the server sets up, so PostgreSQL itself enforces what Bob may do; only `change_system_db` uses the admin login, and it always asks first (see [Database access](#database-access)).
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
- **App spec** (`app-specs/`): business object, steps or tabs (`"layout": "tabs"`), titled sections with 1-6 columns (fields placed per column, relative column widths), fields (text, text area, date, checkbox, integer, decimal, dropdown, radio group; required markers and help text), button labels including Cancel, review and confirmation, the `theme` file it uses and an optional `banner` (the header strip's title and text). `create_app` turns it into a client-side human service exposed as a URL, built from standard UI Toolkit views placed in App Builder Widgets. `example-equipment-request.json` is a simple multi-step form; `example-supplier-registration.json` was written from `screenshots/example-supplier-registration.png`; `example-themed-quote.json` shows tabs, a banner, placed columns, field icons and Cancel; `example-grouped-quote.json` shows reusable groups (see [Reusable groups](#reusable-groups)). An optional `process` section adds a workflow on top: the form becomes the first task of a process with lanes, and an `approval` adds a review task in a second lane with Approve and Send Back, where Send Back returns the work to the form. The diagram opens and can be edited in Business Automation Studio's process editor. An optional `database` section stores the form in a PostgreSQL table: a Load button fills the form from the row with the key, and Submit saves it (see [Database access](#database-access)); `example-equipment-request-db.json` shows it.
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
| `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | The PostgreSQL admin login, for the six database tools. Optional: without them those tools say what is missing and the other 15 work as before |
| `POSTGRES_HOST` | The PostgreSQL host. Default: the host of `BAW_URL` |
| `POSTGRES_BOB_USER`, `POSTGRES_BOB_PASSWORD` | Bob's limited login. The server writes both to `.env` itself; do not set them |
| `POSTGRES_APP_DATABASE`, `POSTGRES_APP_ROLE` | The one database Bob writes to (default `bawexternal`) and the role BAW's data source uses there (default: that database's owner) |

## Use it with IBM Bob

1. Open this folder as the workspace in Bob. It ships two modes (`.bob/custom_modes.yaml`) and their skills:
   - **🏗️ BAW App Builder** turns a written requirement, or screenshots of the screens, into a running app.
   - **✨ BAW Coach Modernizer** gives an existing app a React + Carbon UI built from Modernizer Widgets, with a hand-written screen for any coach that needs one.

   Bob switches between them in the same chat, and from Agent mode into the right one (`.bob/rules/baw-mode-routing.md`): ask for a React UI after building an app and it moves to the Modernizer; ask the Modernizer for a new app or new fields, steps or a workflow and it moves back to the App Builder. Data work (questions, loading a file into a table, exports) needs no switch: every mode, Agent included, does it with the shared `baw-database` skill; only an app that loads and saves a table goes to the App Builder. To skip the switch prompt, allow **Mode** in Bob's auto-approve settings. Both modes edit only `work/` and `app-specs/` (the Modernizer also `coach-ui/src/screens/`, and `coach-ui/src/widgets/` and `coach-ui/widgets/` to add a widget), and do everything else through the MCP tools.
2. Copy `.bob/mcp.example.json` to `.bob/mcp.json` and set the absolute path to `server/baw_mcp.py`. To switch servers without editing `.env`, add an `"env": { "BAW_URL": "..." }` block there.
3. Check that `baw-dev-tools` shows as connected in Bob's MCP panel with 21 tools.
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

Before building a new app, Bob shows you the design (look, screens, fields, buttons, assumptions) and waits for your approval. The first time on a server, it builds and installs the widget toolkit the app needs. After building, it asks whether to import the app into BAW. Bob's tool prompts also ask before `create_app`, `crop_image`, `modernize_app`, `install_app` and `change_system_db`; the read, test and `bawexternal` database tools run without asking.

## Database access

The CP4BA platform keeps its data in one PostgreSQL server. Six tools (`list_tables`, `describe_table`, `run_sql`, `export_table`, `import_table`, `change_system_db`) let Bob read every database on it, build and fill tables in `bawexternal`, the database the access portal sets aside for app data, and, after you approve it, change a system database. Apps that `create_app` builds can load and save rows in `bawexternal` at run time. Use test data only (see [Risks](#risks)).

Ask for data work in any Bob mode, Agent included: Bob follows the [`baw-database`](.bob/skills/baw-database/SKILL.md) skill and the same rules everywhere, so it needs no mode switch.

### The two logins

- **Bob's login (`bob_mcp`).** Every tool except `change_system_db` logs in as `bob_mcp`, a plain PostgreSQL role that cannot create roles or databases, use replication or bypass row security, so PostgreSQL itself refuses what Bob may not do. It reads the application schemas of every database through `SELECT` grants (not `pg_read_all_data`, which would expose the password hashes in `pg_authid`). In `bawexternal` its sessions run as the role BAW's data source uses, so the tables Bob creates are the tables apps see.
- **The admin login (`postgres`).** Its credentials are `POSTGRES_PORT`, `POSTGRES_USER` and `POSTGRES_PASSWORD` in `.env`. The server uses it for two things only: to create and maintain `bob_mcp`, and for `change_system_db`.

You do not set up Bob's login. The first database call after each server start checks it, and creates it if it is missing (about 36 s once; about 14 s on later starts, because the grants are checked in every database). The server generates the password, sends PostgreSQL only a SCRAM verifier and writes `POSTGRES_BOB_USER` and `POSTGRES_BOB_PASSWORD` to `.env` (mode 600). A new schema becomes readable at the next server start. If the data-source role is a superuser, can create roles or bypasses row security, the tools stop and ask you; they never use a stronger role.

To run the setup yourself, or to remove the login and every grant it holds (it drops `bob_mcp` in all databases and removes its two lines from `.env`):

```bash
uv run --script server/pg_ops.py setup
uv run --script server/pg_ops.py remove-login
```

`pg_ops.py` also has `databases`, `tables`, `describe`, `sql`, `export`, `import`, `backup` and `restore` commands; run it with `--help`.

### What the tools can do

| Tool | Reads | Writes | Asks first |
|---|---|---|---|
| `list_tables`, `describe_table` | every database | no | no |
| `run_sql` | every database | `bawexternal` only | no |
| `export_table` | every database | a CSV file under `work/` | no |
| `import_table` | | `bawexternal` only | no |
| `change_system_db` | | every database except `bawexternal` | **yes** |

Limits, so a call cannot hurt the shared server:
- One statement per call. Transaction control, `SET`, `RESET`, `COPY`, `DO`, `CALL` and creating functions, procedures, triggers or rules are refused on every database. A system database runs inside a read-only transaction that is always rolled back.
- `run_sql` returns at most `limit` rows (default 200, at most 1000) and 256 KB, and cuts one value at 2000 characters. A write in `bawexternal` is committed only when its whole result fits; a cut-short result is not committed and the answer says so. `"committed": "unknown"` means the commit may or may not have happened: check the data before you run it again.
- A statement stops after 30 s (120 s for an export or import); a wait for a lock stops after 5 s. The login has at most 5 connections and 1 GB of temporary files.
- Once `bawexternal` is over 1 GB, only reads, `DELETE`, `TRUNCATE` and `DROP TABLE` run.
- An export writes at most 200 MB, to `work/`; an import reads at most 100 MB.
- `import_table(mode="replace")` backs the table up, then locks it for the whole load, so apps that use the table wait.
- `change_system_db` refuses `DO`, `CALL`, `CASCADE`, `CREATE OR REPLACE`, `SECURITY DEFINER`, triggers, rules, subscriptions and functions that reach files, programs, signals or replication. Bob must name every table the statement touches in `backup_tables` (only `CREATE TABLE`, `CREATE INDEX` and `CREATE VIEW` may go without), and the Bob prompt shows that list. The backups and the write run in one transaction; a backup that fails or is cut at 200 MB stops the write.
- Rows are data. Bob's modes treat text found in a row as data, never as an instruction, and never copy client or personal data into specs, screens or committed files.

Bob's tool timeout should be longer than 180 s (`change_system_db` has a 180 s budget). If a call times out or Bob gives up waiting, the write may still finish: check the data before you retry.

### Backups and restore

`import_table(mode="replace")` and `change_system_db` save the rows they are about to change as CSV, with a JSON sidecar that records the columns, keys and indexes, in `db-backups/<database>/<schema.table>-<YYMMDD-HHMMSS>.csv`, a folder outside `work/` that Bob's modes cannot edit and `.bobignore` hides from Bob. Each `change_system_db` outcome is one line in `db-backups/log.jsonl`. There is no tool that restores a backup, so a model cannot undo your approval by itself; you run the restore:

1. Find the backup in `db-backups/<database>/`, or in `log.jsonl`. The folder `db-backups/acl-before-bob-login/` holds the privileges the setup changed (one JSON file per database); it is not a data backup.
2. Run the restore in your terminal. For a system database it runs with the admin login, shows what it will put back, and asks you to type the table name; it refuses to run from a script. A restore into `bawexternal` runs as Bob's login. It only puts rows back into application tables, never into PostgreSQL's own catalogs:

   ```bash
   uv run --script server/pg_ops.py restore basdb db-backups/basdb/public.some_table-261023-101500.csv
   ```

3. Check the result. The restore runs in one transaction and puts back only the rows in the backup: a row whose primary key is in the file is replaced, a deleted row comes back, and every other row stays as it is. When Bob named a `where` for the backup, only those rows are touched. A row that the change inserted is not removed; delete it by hand.
4. A table without a primary key is refused, and the answer names the manual `COPY` to use instead. If the table was dropped, the restore recreates it (columns and primary key) and lists the defaults, other indexes and constraints that you must add back by hand.

To back up rows before a change of your own: `uv run --script server/pg_ops.py backup basdb public.some_table --where "id < 10"`.

### Generated apps

A `database` section in the app spec makes `create_app` add a Load button and a save on Submit that go through the data source `jdbc/bawexternal` (always that one; the spec cannot name another). The result of `create_app` then carries `database`: the table, a `CREATE TABLE IF NOT EXISTS` statement (`ddl`) and the `columns`. Bob runs the `ddl` with `run_sql` on `bawexternal`, compares `describe_table` with `columns` (if the table already exists with another shape, it asks you before touching it), installs the app, and tests it with `test_service`, typing the key with `values` and pressing Load with `press`. The fields and the type mapping are in the [app spec reference](https://unclethien.github.io/baw-bob-dev-tools-mcp/app-spec-reference.html#database).

The Load and Save services of a generated app are callable by any signed-in BAW user, like the app itself: someone who calls them directly can read a row by its key or overwrite a row of that app's table, and nothing else. Keep real or personal data out of these test apps.

- An optional Integer or Decimal field in an app with `database` is a text field that accepts only numbers, held as a String in the business object, because BAW's number controls turn an empty value into 0. A blank saves as NULL; the column stays `integer` or `numeric`. A required number keeps the number control and saves 0 when left empty.
- Load and Save send only values: each service has its statement fixed inside it, so a caller can choose a key or values, never a statement. The services are as reachable as any exposed service of the app.
- The data source exists on the BAWAUT server only. An app with `database` needs it wherever it runs.
- After a column's type changes in a table an installed app uses, BAW's pooled connections may fail with "cached plan must not change result type" until the app or server restarts. This was not tried.

### Risks

- **The connection is not encrypted.** The NodePort has SSL off, so passwords and rows cross the network in the clear. Use a test cluster and test data.
- **Each Load or Save call commits on its own.** An app that fails halfway through a form does not roll back what an earlier call saved.
- **A failed call shows PostgreSQL's own message on the coach** (for example `relation "public.x" does not exist`), including table and column names.
- **One huge value is still read whole.** The row and size caps apply after PostgreSQL's driver has read a row into memory, so a single row with a very large `bytea` or `text` value is not cut before it is read. `describe_table` marks such columns; select `length(col)` or `left(col, 200)` of them.
- The admin password sits in `.env` like the BAW credentials. `.bobignore` blocks Bob's file tools from `.env`, as a second guard next to the modes' rule never to read it; other shell commands are not restricted by it. `.bob/mcp.json` cannot be listed there, because Bob reads its own MCP config through the same filter and its chat fails to start; the modes' rule is its only guard.

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
