# Codebase Summary

## Directory map

| Path | Purpose |
|---|---|
| `server/` | Python MCP server and generators (about 6,850 lines across 15 files) |
| `coach-ui/` | Node/React + Carbon widget toolkits and screens, esbuild bundles, browser verification scripts |
| `.bob/` | Bob config: `custom_modes.yaml` (2 modes), `rules/`, `skills/` (9 BAW skills), `mcp.example.json` |
| `app-specs/` | Example app specs and theme files |
| `docs/` | Published HTML docs (GitHub Pages), API swagger specs, demo scripts in `showoff/`, and these Markdown docs |
| `work/`, `screenshots/` | Gitignored working files: `.twx` builds, specs, screenshots |
| `plans/` | Gitignored plans and reports |
| `db-backups/` | Gitignored row backups written by the database tools |

## `server/` modules

| File | Role |
|---|---|
| `baw_mcp.py` | MCP entry point; registers the 21 tools and shells out to the other modules |
| `baw_ops.py` | BAW Operations REST client (list, export, install); settings from env then `.env` |
| `generate_app.py` | App spec JSON to installable `.twx`: coaches, flow, review/confirmation, required-field blocking, process (approval or plain review) and database sections; refuses unknown keys |
| `coach_builder.py` | Shared building blocks: `Layout`, `coachflow`, service and business-object XML, `write_twx` |
| `coach_views.py` | Coach View and managed file XML; the generic "Coach Screen" view that mounts React screens |
| `coach_theme.py` | Theme file loading, validation, CSS and icon helpers |
| `coach_inventory.py` | Reads a `.twx` into an editable coach spec (`CoachReader`, `inventory`, `carry_over`), including each group's business object, tab binding, Edit links and button roles |
| `modernize_coaches.py` | Adds "(Modernized)" copies of services, rebuilt from Modernizer Widgets or React screens; binds groups to their own objects and rewires processes to the copies |
| `widget_toolkit.py` | Builds the ABW and MDW toolkit `.twx` files and links apps to them |
| `group_views.py` | Reusable field groups as Coach Views, with a Preview service each |
| `process_builder.py` | BPD (workflow diagram) XML: lanes, user tasks, gateways, flows |
| `sql_service.py` | Load/Save SQL service flows through the `jdbc/bawexternal` data source |
| `twx_clone.py` | Clones an exported app into a new independent app with fresh UUIDs |
| `app_template.py` | Built-in no-toolkits package template (BAW 26.0.0) so builds need no server |
| `pg_ops.py` | PostgreSQL access: limited login, safe single statements, backup and restore CLI |

## `coach-ui/`

- `src/components/` and `src/components/fields/`: React + Carbon building blocks (fields, header, review, tabs, validation).
- `src/widgets/`: Modernizer widgets (framework-neutral contract wrapping the components); `src/runtime.jsx`, `toolkit.js`, `widget-host.js`, `page-registry.js` mount them in BAW.
- `src/screens/`: hand-written per-coach screens (gitignored).
- `widgets/*-widgets.json`: widget contract (view name, options, icon) for MDW and ABW; `widgets/builder/*.js`: ABW markup and scripts; `widgets/icons/`: palette icons.
- `build.mjs`: esbuild + sass bundling into `bundle/mdw.js` and `bundle/coach-screens.js`.
- `scripts/check-widgets.mjs`, `scripts/verify-service.mjs`: puppeteer-core checks used by `build_widget_toolkit`, `test_service` and `test_process` (they fill Carbon radios, numbers, checkboxes and toggles, and check blocked and resumed-draft tabs).

## Graph

A code and docs knowledge graph lives in `graphify-out/` (`GRAPH_REPORT.md`, `graph.json`). Largest communities: `pg_ops.py` (106 nodes), `baw_mcp.py` (84), widget toolkit (47), `modernize_coaches.py` (44), `group_views.py` (39).
