# Project Roadmap

Status reconstructed from git history and `plans/` (plans are gitignored and local).

## Done

| Area | Outcome |
|---|---|
| Theme files | One theme file styles classic and React coaches |
| Coach widget toolkits | ABW and MDW toolkits, framework-neutral runtime, widget layouts in Coach Designer |
| Bob-built widget toolkits | `build_widget_toolkit` builds either toolkit; `create_app` and `modernize_app` use their snapshots |
| Quote toggle widget demo | Modernizer can add a new widget during modernization (`modernizer-widget` skill) |
| BPMN process and database | Optional `process` section (lanes, approval, Send Back); `database` section with Load and Save |
| PostgreSQL tools | Six database tools, limited `bob_mcp` login, backups and restore CLI |
| Reusable groups | Groups as Views in classic and modernized apps; `inspect_coaches` reports changes made in BAW |
| SQL services | Load and Save generated as service flows (latest merge, PR #12) |
| Demo scripts | Three scripts under `docs/showoff/` (baw-mcp, quote widgets, groups and database) |

## Open items

- Real automated tests: none exist; verification is by building examples and running `test_service`.
- Unverified: behavior of pooled connections after a column type change in a table an installed app uses.
- Encrypted PostgreSQL traffic on the cluster: the client verifies the certificate by default (`POSTGRES_SSLMODE=verify-full`), but SSL is off on the NodePort, so today it needs `POSTGRES_SSLMODE=prefer` and traffic is unencrypted.
- Possible growth: tables and file uploads in app specs (not expressible today), more widget kinds.

## Maintenance

Update this file and the README when a tool is added, a spec field changes, or a toolkit gains a widget.
