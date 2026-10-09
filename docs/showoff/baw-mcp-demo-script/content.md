# Demo script: Screenshot in, running BAW app out

A 15-minute presenter script for showing IBM Bob and the BAW Bob Dev Tools MCP server: build, install, test and modernize an IBM Business Automation Workflow (BAW) process app, starting from a screenshot.

*Kịch bản demo 15 phút: IBM Bob cùng MCP server BAW Bob Dev Tools dựng, cài đặt, kiểm thử và hiện đại hóa một ứng dụng IBM BAW, bắt đầu chỉ từ một ảnh chụp màn hình.*

---

## 1. Hero: one conversation, one running app

**EN.** Show a screenshot of an old form. Ask Bob for an app that looks like it. Before the demo ends, the room is clicking through a real BAW process app, then the same app with a React + Carbon UI that Bob wrote.

**VI.** Đưa cho Bob ảnh chụp một biểu mẫu cũ và yêu cầu dựng ứng dụng giống như vậy. Trước khi buổi demo kết thúc, khán giả đã bấm thử một ứng dụng BAW thật, rồi chính ứng dụng đó với giao diện React + Carbon do Bob tự viết.

| Number | What it is |
|---|---|
| 11 | MCP tools: list, export, view, inspect, create, build, modernize, install, test |
| 2 | Bob modes: 🏗️ BAW App Builder and ✨ BAW Coach Modernizer |
| 5 | Skills: screenshot-to-app, baw-app-builder, coach-inventory, react-coach-screen, coach-modernize |
| 0 | Lines of TWX, BPMN or coach XML written by hand |

Run of show: 00:00 opening · 01:00 Act 1, screenshot to app · 07:00 Act 2, modernize · 12:00 guardrails and Q&A · 15:00 close.

---

## 2. Before you start (setup and architecture)

**Who does what.** Bob designs and writes: app specs, coach specs and React screens. The MCP server does the platform work: it packages TWX files, installs them through the BAW Operations REST API, reads coaches back, and tests every screen in a headless browser.[^mcp-tools][^baw-rest]

*Bob thiết kế và viết spec, còn MCP server lo phần nền tảng: đóng gói TWX, cài qua REST API, đọc lại coach và kiểm thử từng màn hình trong trình duyệt.*

Architecture: Bob (custom mode + skills) → MCP over stdio → `baw_mcp.py` → generators (TWX) → BAW Operations REST API; `verify-service.mjs` (headless Chrome) → screenshots back to Bob.

Checklist, 30 minutes before:

1. `.env` holds `BAW_URL`, `BAW_USER` and `BAW_PASSWORD` or `BAW_APIKEY`. Never show it on screen.
2. The repo is open as Bob's workspace; `.bob/mcp.json` points to `server/baw_mcp.py`; the MCP panel shows **baw-dev-tools, 13 tools**.
3. Run one rehearsal build and install, so you know the server accepts the app and how long an install takes.
4. Mode: 🏗️ BAW App Builder. Font size up, `.env` closed, the sample screenshot open in a tab.
5. Keep the rehearsal app as a backup. There is no delete tool, so clean up after the demo.

---

## 3. Act 1: screenshot → running app (≈6 min)

**Do.** Show `screenshots/example-supplier-registration.png`: three boxed sections, two columns, dropdowns, radio groups, required stars, a Continue button.

**Paste.**

> Build a ZZ app whose screen looks like screenshots/example-supplier-registration.png. Install it, test it and compare the result with the screenshot.

**Bob does:** `view_image` → writes `work/<ACR>.app.json` → `create_app` → `install_app` (asks approval) → `test_service` → `view_image` on each test screenshot, side by side with the original → fixes and rebuilds if anything differs.

**Say.**
- "Bob is reading the picture the way a developer would: sections, columns, which control is a dropdown, which fields are required."
- "It never writes BAW XML. It writes a small JSON spec; the server turns that into a real process app with standard UI Toolkit views."
- "Watch the approval prompt. Nothing lands on the server without a human saying yes." The MCP spec itself asks clients to keep a human in the loop for tool calls.[^mcp-tools]
- "Now it checks its own work: it opens the test screenshot next to the original and compares them."

**VI. Nói gì:** Bob đọc ảnh như một lập trình viên: phân vùng, số cột, đâu là dropdown, đâu là trường bắt buộc. Bob không viết XML của BAW, chỉ viết một spec JSON nhỏ. Mọi thao tác cài đặt đều chờ người duyệt. Cuối cùng Bob tự so ảnh kiểm thử với ảnh gốc.

**Point at the result.** Same sections, same two-column order, the same dropdown and radio options, red required markers, a "Continue" button. Bob reports its assumptions, for example the dropdown options it could not see in a closed dropdown.

---

## 4. Act 2: modernize to React + Carbon (≈5 min)

**Paste.**

> Give the app you just built a React + Carbon UI. Inspect its coaches, improve the coach spec and show me before you build.

**Bob does:** `inspect_coaches` reads every coach into a coach spec (sections, fields in reading order, options, required flags) → improves labels, adds validation and examples → **stops for approval**.

**Paste.**

> Approved. Write a React screen for each coach, then modernize, install and test both themes.

**Bob does:** writes `react-coach/src/screens/*.jsx` → `build_screens` (fixes compiler errors itself) → `modernize_app` (new snapshot, two new services: brand theme and Carbon theme) → `install_app` → `test_service` on both, filling sample values and pressing every button.

**Say.**
- "The legacy coach flow, scripts and buttons keep running underneath. The React screen only replaces what users see, with IBM Carbon components."[^carbon]
- "Both themes are added next to the original service as a new snapshot, so the old UI still works and you can compare."
- "It tested the form by typing, picking dropdown values and choosing radio options, then read the review screen."

**VI. Nói gì:** Luồng coach, script và nút cũ vẫn chạy bên dưới; React chỉ thay phần người dùng nhìn thấy. Hai giao diện mới được thêm cạnh dịch vụ gốc trong snapshot mới, nên giao diện cũ vẫn dùng được để so sánh.

---

## 5. Guardrails and tough questions

| Guardrail | Why it matters |
|---|---|
| Installs only into apps named "ZZ …" with a ZZ acronym | Demo work can never touch a real app |
| Every install is a new snapshot | BAW silently keeps old content when a snapshot name is reused |
| No delete tool | The agent cannot remove anything |
| Credentials stay inside the server process | Bob never sees passwords or tokens |
| Bob asks before create, modernize and install; edits only `work/`, `app-specs/`, `react-coach/src/screens/` | Custom modes restrict tools and file edits[^bob-modes][^bob-custom-modes] |

**Questions to expect**

- *Does Bob write BAW XML?* No. It writes JSON specs and React files; the server generates the TWX.
- *What can it not build from a screenshot yet?* Tables, file uploads, links and extra buttons. Bob lists them and offers to add them in a React screen.
- *Does it work with our existing apps?* Yes, read-only: `export_app` + `inspect_coaches` turn any app into a coach spec. Modernized output installs only into ZZ copies.
- *Can other agents use it?* Yes. It is a standard stdio MCP server; any MCP client can call the same 13 tools.[^mcp-tools]
- *What happens on an error?* Tool errors come back as readable messages (bad login, snapshot exists, compiler error with file and line), and Bob fixes the spec or screen and retries.

**If something breaks on stage**

| Symptom | Recovery |
|---|---|
| MCP panel shows 0 tools | Restart baw-dev-tools in Bob's MCP panel |
| "Login to BAW_URL failed" | Check `.env`; switch to the rehearsal app and screenshots |
| "Snapshot already exists" | Let Bob bump the snapshot; this is the guard working |
| "stuck … fields need attention" | Validation blocked a press; Bob adds example values |
| A slow install | Talk through the architecture slide while it runs |

---

## 6. Close and next steps

**EN.** Recap: a screenshot became a running BAW app, then a modern React + Carbon app, tested in a browser, with a human approving every change to the server. Next: bring your own screenshot, or describe a form in one sentence and let Bob build it.

**VI.** Tóm lại: một ảnh chụp trở thành ứng dụng BAW chạy thật, rồi thành ứng dụng React + Carbon hiện đại, được kiểm thử trên trình duyệt, và mọi thay đổi trên server đều có người duyệt. Bước tiếp theo: mang ảnh màn hình của bạn, hoặc mô tả biểu mẫu trong một câu để Bob dựng.

Encore prompt:

> Build a small ZZ app for an office supply request: one step with requester name, item, quantity and needed-by date, then a review screen. Install it and test it.

Repository: https://github.com/unclethien/baw-bob-dev-tools-mcp (Apache-2.0). Not an official IBM project; use it with test servers and test apps.

---

## References

[^mcp-tools]: Model Context Protocol specification, Tools (2025-06-18): tools are model-controlled, results may contain image content, and clients SHOULD keep a human in the loop. https://modelcontextprotocol.io/specification/2025-06-18/server/tools
[^bob-modes]: IBM Bob documentation, Modes. https://bob.ibm.com/docs/ide/features/modes
[^bob-custom-modes]: IBM Bob documentation, Custom modes (tool access and file permissions). https://bob.ibm.com/docs/ide/configuration/custom-modes ; Skills: https://bob.ibm.com/docs/ide/features/skills
[^baw-rest]: IBM documentation, installing a solution with the BAW REST APIs (`POST /std/bpm/containers/install`, then poll the container version). https://ibm.com/support/knowledgecenter/SS8JB4_23.x/com.ibm.casemgmt.design.doc/tinstallcasesolonprod.html
[^carbon]: Carbon Design System, IBM's open-source design system; React components in `@carbon/react`. https://carbondesignsystem.com/ ; https://www.npmjs.com/package/@carbon/react
