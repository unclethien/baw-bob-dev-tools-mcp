# Graph Report - baw-bob-dev-tools-mcp  (2026-11-02)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 950 nodes · 2116 edges · 47 communities (43 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 62 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `82c2fb70`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PostgreSQL Access Layer
- Coach Modernization Pipeline
- SQL Services and Flows
- MCP Tools and Skills Docs
- Architecture and Demo Docs
- Widget Toolkit Builder
- Coach Inventory and Groups
- TWX Packaging Templates
- React Widget Runtime
- Group Views
- BAW REST Client
- Coach Reader
- App Flow Generator
- MCP Server Core
- Browser Service Verifier
- Coach View XML
- React Components and Validation
- Page Registry and Buttons
- Database MCP Tools
- TWX Cloning
- Carbon Field Components
- Layout and Coach Builders
- Process (BPD) Builder
- App Spec Generation
- Node Package Dependencies
- BAW Tool Wrappers
- Settings and Env Loading
- Widget Browser Checks
- Error Summary Widget
- Read-only Value Formatting
- Image Tools
- Snapshot and Install Tools
- Modernize and Toolkit Install
- Spec Validation
- Section and Column Layout
- Field Widget Dispatch
- Approval and Review Coaches
- Field Type Mapping
- Bob Custom Modes
- Groups Demo Script UI
- Quote Widgets Demo UI
- Widget Bundle Build
- BAW MCP Demo Script UI
- Database Load and Save Steps
- Builder Header Widget

## God Nodes (most connected - your core abstractions)
1. `PgError` - 24 edges
2. `uid()` - 23 edges
3. `change_system_db()` - 21 edges
4. `session()` - 21 edges
5. `BawOps` - 20 edges
6. `Layout` - 20 edges
7. `settings()` - 19 edges
8. `modernize()` - 19 edges
9. `generate()` - 19 edges
10. `backup()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Modernization Component (coach_inventory.py, modernize_coaches.py, twx_clone.py)` --semantically_similar_to--> `modernize_app tool`  [INFERRED] [semantically similar]
  docs/system-architecture.md → README.md
- `App spec reference` --semantically_similar_to--> `theme file (work/<name>.theme.json: primary, font, shape, fieldIcons, banner)`  [INFERRED] [semantically similar]
  docs/app-spec-reference.html → .bob/skills/app-theme/SKILL.md
- `coach group (reusable BAW View with Preview service; changedInBaw, replace_groups)` --semantically_similar_to--> `App spec reference`  [INFERRED] [semantically similar]
  .bob/skills/coach-groups/SKILL.md → docs/app-spec-reference.html
- `Codebase summary (directory map, server modules, coach-ui layout)` --semantically_similar_to--> `README (project overview and setup)`  [INFERRED] [semantically similar]
  docs/codebase-summary.md → README.md
- `Getting started guide (10 steps)` --semantically_similar_to--> `README (project overview and setup)`  [INFERRED] [semantically similar]
  docs/getting-started.html → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Demo Script Family (three presenter scripts for BAW Dev Tools MCP)** — docs_showoff_baw_mcp_demo_script_content_md_demo_script, docs_showoff_quote_widgets_demo_script_content_md_demo_script, docs_showoff_groups_and_database_demo_script_content_md_demo_script [EXTRACTED 1.00]
- **BAW App Build-Install-Test Flow** — docs_project_overview_pdr_md_create_app_tool, docs_system_architecture_md_app_generation_component, docs_system_architecture_md_browser_verification_component, docs_system_architecture_md_baw_client_component [INFERRED 0.85]
- **BAW app-building skill pipeline** — bob_skills_app_theme_skill, bob_skills_baw_app_builder_skill, bob_skills_screenshot_to_app_skill, bob_skills_coach_groups_skill [INFERRED 0.85]
- **Coach modernization skill pipeline** — bob_skills_coach_inventory_skill, bob_skills_coach_modernize_skill, bob_skills_modernizer_widget_skill, bob_skills_react_coach_screen_skill [INFERRED 0.85]
- **Database tools sharing the bob_mcp / postgres login safety model** — readme_database_tools, readme_tool_run_sql, readme_tool_change_system_db, bob_skills_baw_database_skill_write_rules [INFERRED 0.85]
- **Coach Modernization Flow (inspect, edit, modernize, install, test)** — docs_project_overview_pdr_md_inspect_coaches_tool, readme_tool_modernize_app, docs_system_architecture_md_modernization_component, docs_project_overview_pdr_md_baw_coach_modernizer_mode [INFERRED 0.85]

## Communities (47 total, 4 thin omitted)

### Community 0 - "PostgreSQL Access Layer"
Cohesion: 0.05
Nodes (57): admin_refusal(), app_size(), backup(), backup_acls(), backup_table(), change_system_db(), check_app_role(), check_where() (+49 more)

### Community 1 - "Coach Modernization Pipeline"
Cohesion: 0.06
Nodes (33): css(), icon_url(), load_theme(), shrink(), validate(), visibility(), add_objects(), check_field_types() (+25 more)

### Community 2 - "SQL Services and Flows"
Cohesion: 0.06
Nodes (37): coachflow(), sequence_flow(), step_xml(), uid(), node(), bare(), cell(), check_data_source() (+29 more)

### Community 3 - "MCP Tools and Skills Docs"
Cohesion: 0.06
Nodes (46): baw-mode-routing rule, app-theme skill, theme file (work/<name>.theme.json: primary, font, shape, fieldIcons, banner), baw-app-builder skill, app spec (work/<ACR>.app.json), build flow: create_app, inspect_coaches, install_app, test with two STOP points, baw-database skill, basdb tables (lsw_project, lsw_snapshot, lsw_usr_xref, lsw_task, lsw_bpd_instance) (+38 more)

### Community 4 - "Architecture and Demo Docs"
Cohesion: 0.06
Nodes (39): ABW button bar markup (buttons.html), ABW section markup (section.html), BAW Dev Tools MCP Documentation Index, 21 MCP Tools Surface, Reusable Groups (BAW Views), Widget Toolkits (ABW and MDW), BAW App Builder Mode, BAW Bob Dev Tools MCP Project Overview (+31 more)

### Community 5 - "Widget Toolkit Builder"
Cohesion: 0.09
Nodes (21): add_dependency(), build(), classic_layout(), config(), custom_html(), classic_load_js(), classic_preview_js(), embed() (+13 more)

### Community 6 - "Coach Inventory and Groups"
Cohesion: 0.09
Nodes (17): carry_over(), describe(), field_spec(), group_candidates(), humanize(), inventory(), main(), parts() (+9 more)

### Community 7 - "TWX Packaging Templates"
Cohesion: 0.10
Nodes (12): builtin(), dependency_xml(), package_xml(), read_base(), sql_ids(), target(), toolkit_dependencies(), business_object_xml() (+4 more)

### Community 8 - "React Widget Runtime"
Cohesion: 0.14
Nodes (19): ALIGN, createStore(), darker(), Host(), mount(), mountWidget(), RADII, registerWidget() (+11 more)

### Community 9 - "Group Views"
Cohesion: 0.14
Nodes (11): bind_visibility(), fields_fingerprint(), group_view(), option_label(), option_name(), placement_options(), preview_service(), stable_ids() (+3 more)

### Community 11 - "Coach Reader"
Cohesion: 0.12
Nodes (9): children(), CoachReader, first(), flow_order(), inventory_service(), local(), renderable(), static_options() (+1 more)

### Community 12 - "App Flow Generator"
Cohesion: 0.18
Nodes (12): assign_script(), clear_message_steps(), flow(), key_step(), load_flows(), message_set(), message_view(), save_check_flows() (+4 more)

### Community 13 - "MCP Server Core"
Cohesion: 0.15
Nodes (6): build_screens(), build_widget_toolkit(), child_env(), inspect_coaches(), python(), run()

### Community 14 - "Browser Service Verifier"
Cohesion: 0.12
Nodes (12): BASE, BROWSERS, envFile, executablePath, findField(), inspectCoach(), item, presses (+4 more)

### Community 15 - "Coach View XML"
Cohesion: 0.18
Nodes (9): coach_view_xml(), managed_asset_xml(), screen_assets(), screen_view(), uid(), view_xml(), config_option(), inline_script() (+1 more)

### Community 16 - "React Components and Validation"
Cohesion: 0.24
Nodes (11): Brand(), Header(), Steps(), SectionStack(), SectionTabs(), fieldError(), patternOf(), useValidation() (+3 more)

### Community 17 - "Page Registry and Buttons"
Cohesion: 0.18
Nodes (12): ActionBar(), buttonLabel(), errors, fields, listeners, markTabs(), page, reveal() (+4 more)

### Community 18 - "Database MCP Tools"
Cohesion: 0.15
Nodes (8): change_system_db(), db(), describe_table(), export_table(), import_table(), list_tables(), pg(), run_sql()

### Community 19 - "TWX Cloning"
Cohesion: 0.23
Nodes (9): build_mapping(), clone(), collect_toolkit_uuids(), foreign_uuids(), is_text(), main(), pin_target(), rename_project() (+1 more)

### Community 20 - "Carbon Field Components"
Cohesion: 0.22
Nodes (9): INPUTS, CheckboxField(), NO_GROUPING, NumberField(), RadioField(), SelectField(), TextAreaField(), TextField() (+1 more)

### Community 21 - "Layout and Coach Builders"
Cohesion: 0.24
Nodes (5): Layout, confirmation_coach(), form_coach(), main(), spike_app()

### Community 22 - "Process (BPD) Builder"
Cohesion: 0.24
Nodes (8): bpd_id(), bpmn2_xml(), _event(), _gateway(), process_xml(), flow_object(), ports(), _task()

### Community 23 - "App Spec Generation"
Cohesion: 0.19
Nodes (8): database_result(), fields(), generate(), group_objects(), header(), init_script(), main(), process_definition()

### Community 24 - "Node Package Dependencies"
Cohesion: 0.19
Nodes (12): description, devDependencies, esbuild@^0.28.2, puppeteer-core@^23.11.1, sass@^1.105.1, name, private, scripts (+4 more)

### Community 25 - "BAW Tool Wrappers"
Cohesion: 0.19
Nodes (7): list_apps(), list_services(), offline(), ops(), test_process(), test_service(), configured()

### Community 26 - "Settings and Env Loading"
Cohesion: 0.19
Nodes (4): ConfigError, load_env(), load_env_file(), missing_settings()

### Community 27 - "Widget Browser Checks"
Cohesion: 0.17
Nodes (3): BROWSERS, results, { values: args }

### Community 28 - "Error Summary Widget"
Cohesion: 0.20
Nodes (9): dependencies, @carbon/react@^1.117.0, react@^18.3.1, react-dom@^18.3.1, ErrorSummary(), ErrorSummaryWidget(), SAMPLE, react (+1 more)

### Community 29 - "Read-only Value Formatting"
Cohesion: 0.35
Nodes (7): DateField(), parseTyped(), ReadOnlyValue(), ReviewSection(), formatValue(), optionLabel(), toDate()

### Community 30 - "Image Tools"
Cohesion: 0.22
Nodes (5): crop_image(), image_colors(), local(), open_image(), view_image()

### Community 31 - "Snapshot and Install Tools"
Cohesion: 0.22
Nodes (7): create_app(), export_app(), install_app(), list_snapshots(), newest(), require_new_snapshot(), snapshots()

### Community 32 - "Modernize and Toolkit Install"
Cohesion: 0.27
Nodes (6): installed_toolkit(), modernize_app(), package_xml(), rel(), run_browser(), target_of()

### Community 33 - "Spec Validation"
Cohesion: 0.18
Nodes (6): field_errors(), database_errors(), field_errors(), key_placement_errors(), layout_errors(), load_spec()

### Community 34 - "Section and Column Layout"
Cohesion: 0.20
Nodes (6): column_widths(), columns(), place_group(), section(), sections(), tab_content()

### Community 35 - "Field Widget Dispatch"
Cohesion: 0.38
Nodes (8): EditSection(), Field(), fieldKind(), blank(), choices(), fieldWidget(), FieldWidget(), rangeError()

### Community 36 - "Approval and Review Coaches"
Cohesion: 0.27
Nodes (6): actions(), approval_coach(), approval_flow(), read_only(), review_coach(), widget()

### Community 37 - "Field Type Mapping"
Cohesion: 0.22
Nodes (6): choices(), field_type(), group_field(), group_fields(), input_view(), output()

### Community 38 - "Bob Custom Modes"
Cohesion: 0.22
Nodes (8): customModes, groups, name, roleDefinition, slug, whenToUse, description, fileRegex

### Community 39 - "Groups Demo Script UI"
Cohesion: 0.31
Nodes (4): paintTimer(), resetTimer(), say(), toggleTimer()

### Community 40 - "Quote Widgets Demo UI"
Cohesion: 0.31
Nodes (4): paintTimer(), resetTimer(), say(), toggleTimer()

### Community 41 - "Widget Bundle Build"
Cohesion: 0.29
Nodes (6): bundle(), css, screensEntry, styles, toolkitEntry, toPx()

### Community 42 - "BAW MCP Demo Script UI"
Cohesion: 0.36
Nodes (4): paintTimer(), resetTimer(), say(), toggleTimer()

### Community 43 - "Database Load and Save Steps"
Cohesion: 0.29
Nodes (4): database_call(), load_steps(), save_steps(), call_step()

## Knowledge Gaps
- **17 isolated node(s):** `baw-export.sh / baw-import.sh scripts`, `basdb tables (lsw_project, lsw_snapshot, lsw_usr_xref, lsw_task, lsw_bpd_instance)`, `screen contract (registerScreen, props field/read/fire/options, Header, Field; coach-screens.js)`, `spec field types (String, Text Area, Date, Boolean, Integer, Decimal, Select, Radio) and 17 field icons`, `BAW authentication and CSRF token (/icp4d-api/v1/authorize, /bas/bpm/system/login, BPMCSRFToken)` (+12 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 348 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BawOps` connect `BAW REST Client` to `BAW Tool Wrappers`, `Settings and Env Loading`, `MCP Server Core`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **What connects `baw-export.sh / baw-import.sh scripts`, `basdb tables (lsw_project, lsw_snapshot, lsw_usr_xref, lsw_task, lsw_bpd_instance)`, `screen contract (registerScreen, props field/read/fire/options, Header, Field; coach-screens.js)` to the rest of the system?**
  _17 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `PostgreSQL Access Layer` be split into smaller, more focused modules?**
  _Cohesion score 0.05402930402930403 - nodes in this community are weakly interconnected._
- **Why does `CoachReader` connect `Coach Reader` to `Coach Inventory and Groups`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Should `Coach Modernization Pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.05721153846153846 - nodes in this community are weakly interconnected._
- **Why does `main()` connect `BAW REST Client` to `Coach Modernization Pipeline`, `Settings and Env Loading`, `Widget Toolkit Builder`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Should `SQL Services and Flows` be split into smaller, more focused modules?**
  _Cohesion score 0.05683060109289618 - nodes in this community are weakly interconnected._