# System Architecture

## Overview

```
Agent (Bob) ── writes ──▶ work/*.theme.json, work/*.app.json, work/*.coaches.json, coach-ui/src/screens/*.jsx
     │
     └── MCP tools (stdio) ──▶ server/baw_mcp.py
                                 ├── generators ──▶ .twx packages ──▶ BAW Operations REST API (baw_ops.py)
                                 ├── widget toolkits (ABW, MDW) built from coach-ui/
                                 ├── coach-ui/scripts/verify-service.mjs (headless Chromium) ──▶ screenshots in work/
                                 └── pg_ops.py ──▶ platform PostgreSQL server
```

## Components

- **MCP server** (`baw_mcp.py`): thin tool layer. It validates inputs, resolves paths, picks the right generator or CLI, and returns small JSON results. Long jobs run as subprocesses with a scrubbed environment.
- **App generation** (`generate_app.py`, `coach_builder.py`, `process_builder.py`, `sql_service.py`, `group_views.py`, `app_template.py`): an app spec becomes one client-side human service exposed as a URL, one coach per step or tab (tabs get Next buttons, and required fields block the finishing button), plus an optional BPD (approval, or a plain review task with read-only views and per-section Edit) and Load/Save SQL services. Packaging uses BAW's `twxWithoutToolkits` format, so no server export is needed (a `base` app can match a server's build).
- **Modernization** (`coach_inventory.py`, `modernize_coaches.py`, `twx_clone.py`): `inspect_coaches` produces a coach spec; `modernize_app` copies each service as "(Modernized)" and rebuilds coaches from Modernizer Widgets inside native Panels or a Tab Section, or shows a hand-written React screen. Coach flow, scripts and variables stay native.
- **Widget toolkits** (`widget_toolkit.py`, `coach-ui/`): ABW (classic markup and JavaScript) and MDW (React + Carbon behind a framework-neutral contract). Toolkits have fixed project and branch IDs, so each build is a new snapshot of the same toolkit. An app keeps the snapshot it was built with.
- **Theme** (`coach_theme.py`): one JSON file drives both the classic and React coaches.
- **BAW client** (`baw_ops.py`): list, export and install over REST; tokens are kept in memory. Certificates are verified (`BAW_CA_FILE` adds that CA to the system roots, `BAW_TLS_INSECURE=true` opts out), and a redirect to another host or to `http` is refused even with the opt-out. The TLS settings are read on each call, so changing them needs no restart.
- **Database** (`pg_ops.py`): see below.
- **Browser verification** (`verify-service.mjs`, `check-widgets.mjs`): puppeteer-core drives Chrome, Brave or Helium (`BROWSER_PATH` overrides) to render every screen, fill fields, press buttons, and report. Chrome checks certificates against the system trust store (the server passes `NODE_EXTRA_CA_CERTS` for Node only), so a private CA must be installed there. The run's token goes to the BAW origin only: the `Authorization` header is sent only to that origin, and the session cookie is bound to the BAW port and scheme (`sourcePort`, `sourceScheme: Secure`, with Chrome's `EnablePortBoundCookies` and `EnableSchemeBoundCookies` features), so another port on the same host does not receive it. The login requests refuse redirects.

## Data flows

1. **New app**: spec → `create_app` → `.twx` in `work/` → `install_app` (if a server is configured) → `test_service` or `test_process`.
2. **Modernize**: `export_app` → `inspect_coaches` → agent edits coach spec → `modernize_app` (new snapshot) → `install_app` → `test_service`.
3. **Toolkit**: `build_widget_toolkit` → `work/<ACR>-<snapshot>.twx` → `install_app` once per server → pass the snapshot as `toolkit_snapshot`.

## Database security model

- `bob_mcp` is a plain PostgreSQL role created on first use by the admin login; its password is generated, sent as a SCRAM verifier, and saved to `.env`. It reads application schemas through `SELECT` grants and, in `bawexternal`, runs as the role BAW's data source uses.
- `change_system_db` is the only path using the admin login; it asks the user, backs up named tables in one transaction with the write, and refuses `DO`, `CALL`, `CASCADE`, `CREATE OR REPLACE`, triggers and similar.
- `export_table`'s SELECT form passes the same refusal checks as `run_sql` (no session signalling, no functions that run SQL given as text, no DDL).
- Limits: one statement per call, 30 s per statement, 256 KB and 1,000 rows per result, 1 GB cap on `bawexternal` for writes. Backups go to `db-backups/` and are restored only by the user with `pg_ops.py restore`.
- PostgreSQL connections use `POSTGRES_SSLMODE`, default `verify-full` (`prefer` when `BAW_TLS_INSECURE=true`). `POSTGRES_CA_FILE` (default `BAW_CA_FILE`) replaces the trusted roots and is passed only for `verify-ca` and `verify-full`. A server with SSL off (the cluster's NodePort) needs `prefer`, and then passwords and rows cross the network unencrypted. Use test clusters and test data.

## Bob integration

`.bob/custom_modes.yaml` defines BAW App Builder and BAW Coach Modernizer with edit permissions limited to `work/`, `app-specs/` and (Modernizer) `coach-ui/src/screens`, `coach-ui/src/widgets`, `coach-ui/widgets`. `.bob/rules/baw-mode-routing.md` routes requests between modes. Nine skills in `.bob/skills/` carry the step-by-step procedures.

## Constraints

- Server-only tools need `BAW_URL`; without it build tools still work and the user imports `.twx` files.
- The `database` feature needs the `jdbc/bawexternal` data source, present on the BAWAUT server.
