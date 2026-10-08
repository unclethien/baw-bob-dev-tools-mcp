---
name: coach-inventory
description: Inventory the coaches of a BAW process app (.twx) into an editable JSON spec with the inspect_coaches MCP tool, then improve the spec (labels, sections, required fields, patterns, examples) and stop for the user's review. Use before modernizing an app's coaches, or when the user asks what screens, fields or buttons an app has.
---

# Coach inventory

**STOP RULE: write and improve the spec, show the summary, then stop and wait for approval. Do not generate or install anything in the same turn.**

## Steps

1. **Run the inventory** with the `inspect_coaches` MCP tool on the app's `.twx` (from `export_app` or `create_app`). It writes the coach spec and returns one line per coach: sections, fields, how many items stay native, and each button with the coach it leads to.

2. **Read the spec.** Each service has a `variable` (the business object behind its fields) and its `coaches` in flow order. Each coach has:
   - `sections`, each holding `fields` (`path`, `label`, `type`, `readonly`, `required`);
   - `buttons` (`label`, `viewId`, `primary`, `to`);
   - `native`, the items that stay as BAW views under the React form;
   - `dropped`, the items that will not appear at all.

3. **Improve the spec.** Edit only these keys:

   | Key | Change |
   |---|---|
   | `label` | Use human labels. "Empname" becomes "Employee Name", and an acronym like SSO stays in capitals |
   | section `title` | Name each section. The `dropped` list often holds a heading such as `empty Panel "Step 1 of 5: General Information"` |
   | `required: true` | Set for fields the business must have |
   | `pattern` + `message` | Use a JavaScript regular expression and a plain sentence, e.g. `"^\\d{10}$"` with "Account number must be 10 digits" |
   | `example` | Add a sample value, shown as the placeholder. Never use real data |
   | `readonly: true` | Set on every field of a review or summary coach, which then renders as a read-only summary |
   | `intro` | Add one sentence of lead text for a coach |
   | `sectionStyle` | Use `"tabs"` for long single-coach forms, `"stack"` otherwise |
   | `modernize: false` | Set to skip a service |
   | button `primary` | Make sure exactly the forward button is primary. Primary buttons validate before they are pressed |

   Keep `path`, `viewId`, `id` and `type` as they are. Do not delete buttons: a button missing from the spec cannot be pressed.

4. **Check what will not be modernized.** Read `native` and `dropped` for every coach. Tell the user about anything important that is dropped, such as a Custom HTML block with instructions, and add its text to the coach's `intro` when it matters.

5. **STOP.** Show the inventory summary, a short list of your changes, and the native or dropped items. Then ask:
   > Approve this spec, or tell me what to change. When approved, I will write a React screen for each coach.

   Skip the stop only when the user said to continue without review.

## Rules

- Never copy client or personal data into the spec. `example` values are obvious samples (`1234567890`, `name@example.com`, `(423) 555-0100`).
- If a service shows `"modernize": false` with a `reason`, report the reason. Do not force it on.
