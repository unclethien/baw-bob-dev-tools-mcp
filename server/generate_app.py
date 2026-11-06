#!/usr/bin/env python3
"""
Generate a complete, installable BAW process app (.twx) from an app spec (JSON).

The app holds one client-side human service, exposed as a URL, with one coach per step:

    Start -> Initialize -> Step 1 -> ... -> Step N -> Review -> Assign reference -> Confirmation -> End
                              Back buttons return to the previous step; Review is optional,
                              and so is the confirmation (with its generated reference number).

With "layout": "tabs" the steps become tabs of one form coach instead (Next goes to Review).

"process" adds a workflow (a BPD) that users start from Workplace and edit in Business Automation Studio:
the service becomes the first task, in its own lane; an optional "approval" task in a second lane
shows every field read-only with a comments box and Approve / Send back buttons, and Send back
returns the work to the first task:

    Start -> <form task> -> <approval task> -> Approved? -> End
                  ^-------------- Send back ------'

A "review" task instead (not together with "approval") shows every group read-only, each with an
Edit button that unlocks it, and one button that finishes the work:

    Start -> <form task> -> <review task> -> End

A step lists its fields, or "sections" of fields, each a titled panel; "columns": 2 to 6 lays the
fields out side by side ("wide": true keeps a field full width). By default fields fill the columns left
to right, row by row; give every field a "column" (1, 2, ...) to place it, top to bottom, in that column,
and "widths": [1, 1.6, 1] to make some columns wider. Fields of type Select (dropdown) and Radio take a
list of "options". "cancelLabel" on a step or on "form" adds a button that ends the service.

"database" stores the form in a PostgreSQL table of the bawexternal database (the data source jdbc/bawexternal), which
BAW apps may use: {"table": "public.name", "key": "<field>", "columns": {"<field>": "<column>"}}. The key field
(required) becomes the primary key; a Load button next to it fills the form from the row, and Submit upserts the form
(a "Load <BO>" and a "Save <BO>" service flow each run one fixed statement, sql_service.py). The CREATE TABLE statement is printed; run it
before testing the app. Every simple field is stored, in a column named by its snake_case name unless "columns" says otherwise.
An Integer or Decimal field that is not "required" (and is not the key) is a text field in the app, a String in the business object, because
BAW's number controls turn an empty value into 0: nothing typed is saved as NULL, a number is checked on Submit, and its column is still
integer or numeric. A required number keeps its number control; the required check on Submit treats an empty one as missing.

"theme" names the app's theme file (colours, font, shapes, field icons, banner product and logo), and
"banner" adds the app's own banner title and text; see coach_theme.py.

Every coach is built from standard UI Toolkit views bound to one business object, placed in App Builder
Widgets (--toolkit, an ABW snapshot from widget_toolkit.py build builder, installed on the server): a Theme
with the coach's CSS, an App Header with the banner or title and the intro, a Section per section, a Review
List per read-only section and a Button Bar. The result runs as soon as it is installed, stays editable by
drag and drop in Coach Designer, and can be inventoried and modernized like any app.

The .twx is built from the template in app_template.py, so no server is needed: install it with
baw_ops.py, or import it in Workflow Center. --base takes an app exported from the target server
(any app; export it without toolkits) to match that server's BAW build and toolkit versions. When
the base is the app itself (same acronym), the build becomes a new snapshot of it.

Example:
    python3 server/widget_toolkit.py build builder 1.0.0 work/ABW-1.0.0.twx      # install it once
    python3 server/generate_app.py app-specs/example-equipment-request.json work/ZZEQ.twx --toolkit work/ABW-1.0.0.twx
    python3 server/baw_ops.py install work/ZZEQ.twx
    python3 server/generate_app.py my-app.json work/ZZEQ-1.1.0.twx --base work/ZZEQ-1.0.0.twx --toolkit work/ABW-1.0.0.twx   # new snapshot of ZZEQ
"""

import argparse
import json
import re
import zipfile
from pathlib import Path

import app_template
import coach_theme
import group_views
import sql_service
import widget_toolkit
from coach_builder import SYSTEM_TYPES, TWSYS, Layout, coachflow, uid, write_twx
from process_builder import process_xml

FIELD_TYPES = {  # spec type -> (business object type, input view)
    "String": ("String", "Text"),
    "Text Area": ("String", "Text Area"),
    "Date": ("Date", "Date Time Picker"),
    "Boolean": ("Boolean", "Checkbox"),
    "Integer": ("Integer", "Integer"),
    "Decimal": ("Decimal", "Decimal"),
    "Select": ("String", "Single Select"),
    "Radio": ("String", "Radio Button Group"),
}
CHOICES = {"Select", "Radio"}
CONTROLS = {  # (type, control) -> input view, for a field that picks from a few typed values
    ("Boolean", "Radio"): "Radio Button Group",
    ("Integer", "Select"): "Single Select",
}
NUMBER_TYPES = ("Integer", "Decimal")
MAX_COLUMNS = 6
PROJECT = Path(__file__).resolve().parent.parent
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REFERENCE = "referenceNumber"
DECISION, COMMENTS = "decision", "reviewComments"  # set by the approval task
MESSAGE = sql_service.MESSAGE  # the database message a coach shows
APPROVED, SENT_BACK = "Approved", "Sent back"
TOOLKIT = "builder"
WIDGETS = {}  # App Builder Widgets view ID by kind, from the toolkit generate() builds against
GROUPS = {}  # group name -> (View ID, group_views fields), from generate()
KEPT = {}  # group changed in BAW that the last generate() kept -> its fields the spec does not have

# The settings each part of an app spec may have; load_spec refuses any other key, so a typo is not silently ignored.
# Keys the generator sets itself (numberText, _bo, _database, implicit) are not listed. "database" is checked by
# sql_service and "theme" and "banner" by coach_theme.
SPEC_KEYS = {
    "spec": ("app", "businessObject", "businessObjects", "service", "layout", "steps", "groups", "review", "confirmation",
             "database", "process", "theme", "banner", "form", "reusableViews"),
    "app": ("name", "acronym", "snapshot"),
    "businessObject": ("name", "variable"),
    "service": ("name", "description"),
    "form": ("title", "intro", "nextLabel", "tabNextLabel", "draftLabel", "cancelLabel"),
    "review": ("title", "intro", "submitLabel"),
    "confirmation": ("title", "message", "referencePrefix", "showFields"),
    "process": ("name", "description", "formTask", "approval", "review"),
    "formTask": ("name", "lane"),
    "reviewTask": ("name", "lane", "completeLabel", "editLabel"),
    "approval": ("name", "lane", "commentsLabel", "approveLabel", "returnLabel", "intro"),
    "step": ("title", "intro", "fields", "sections", "columns", "widths", "nextLabel", "backLabel", "cancelLabel", "reusable"),
    "section": ("title", "intro", "fields", "columns", "widths", "group", "hide", "readonly", "hideTitle", "reusable"),
    "group": ("name", "columns", "widths", "fields", "businessObject"),
    "field": ("name", "type", "label", "required", "options", "help", "wide", "column", "icon", "control"),
}


def visibility(value):
    return [("@visibility", json.dumps({"isResponsiveData": True, "values": [{"deviceConfigID": "LargeID", "value": value}]}))]


READ_ONLY, REQUIRED = visibility("READONLY"), visibility("REQUIRED")
CSS = """
div.body { max-width: 960px; margin: 0 auto !important; padding: 16px 24px !important; }
.app-title { font-size: 22px; font-weight: 600; margin: 8px 0 4px 0; }
.app-intro { margin: 0 0 16px 0; color: #525252; }
.panel { margin-bottom: 16px !important; }
.Button.CoachView { flex: 0 0 auto !important; width: auto !important; margin-right: 8px; }
.btn { width: auto !important; }
.Theme.CoachView, .App_Header.CoachView { margin-top: 0 !important; margin-bottom: 0 !important; }
.panel-group.abw-group { margin-bottom: 0; }
.topLevel > .panel-group.abw-group { margin-bottom: 12px; }
@media (max-width: 900px) {
  .layoutSec.hChild { flex-wrap: wrap; }
  .layoutSec.hChild > .Vertical_Layout { width: 100% !important; }
}
"""
# A read-only field in a group (Review, a reference copy) keeps its input box; this makes it read as text.
GROUP_CSS = """
.form-control[readonly], .form-control[disabled] { background: #eef1f4 !important; border-color: transparent !important; box-shadow: none !important; cursor: default; }
"""


# ---------------------------------------------------------------- spec


def key_errors(where, obj, kind):
    """Errors for the keys of one part of a spec that SPEC_KEYS[kind] does not list."""
    if not isinstance(obj, dict):
        return []  # the part's own checks say what shape it needs
    allowed = SPEC_KEYS[kind]
    return [f"{where}: {k!r} is not a setting; use {', '.join(allowed)}" for k in obj if k not in allowed]


def unknown_keys(spec):
    """Errors for every key the spec has that SPEC_KEYS does not list, at every level."""
    errors = key_errors("the spec", spec, "spec")
    for kind in ("app", "service", "form", "confirmation", "process"):
        errors += key_errors(kind, spec.get(kind), kind)
    if isinstance(spec.get("review"), dict):
        errors += key_errors("review", spec["review"], "review")
    process = spec.get("process") if isinstance(spec.get("process"), dict) else {}
    for kind in ("formTask", "approval"):
        errors += key_errors(f"process.{kind}", process.get(kind), kind)
    errors += key_errors("process.review", process.get("review"), "reviewTask")
    objects = spec.get("businessObjects") if isinstance(spec.get("businessObjects"), list) else [spec.get("businessObject")]
    for k, bo in enumerate(objects, 1):
        errors += key_errors(f"business object {k}" if len(objects) > 1 else "businessObject", bo, "businessObject")
    for i, step in enumerate(spec.get("steps") if isinstance(spec.get("steps"), list) else [], 1):
        errors += key_errors(f"step {i}", step, "step")
        sections = step.get("sections") if isinstance(step, dict) and isinstance(step.get("sections"), list) else []
        for j, s in enumerate(sections, 1):
            errors += key_errors(f"step {i} section {j}", s, "section")
            errors += field_key_errors(f"step {i} section {j}", s)
        errors += field_key_errors(f"step {i}", step)
    for k, g in enumerate(spec.get("groups") if isinstance(spec.get("groups"), list) else [], 1):
        errors += key_errors(f"group {g.get('name', k) if isinstance(g, dict) else k}", g, "group")
        errors += field_key_errors(f"group {g.get('name', k) if isinstance(g, dict) else k}", g)
    return errors


def field_key_errors(where, part):
    """Key errors of the fields a step, section or group lists."""
    fields = part.get("fields") if isinstance(part, dict) and isinstance(part.get("fields"), list) else []
    return [e for f in fields for e in key_errors(f"{where}: field {f.get('name')!r}" if isinstance(f, dict) else where, f, "field")]


def business_objects(spec, errors):
    """The spec's business objects as a list: "businessObjects", or the one "businessObject". Sets
    spec["businessObjects"] and spec["businessObject"] (the first, which also carries the generated properties)."""
    one, many = spec.get("businessObject"), spec.get("businessObjects")
    if one is not None and many is not None:
        errors.append("use businessObject (one) or businessObjects (a list), not both")
    objects = [one if one is not None else {}] if many is None else many
    if not isinstance(objects, list) or not objects:
        errors.append('businessObjects must list at least one object: [{"name": "OrderBO", "variable": "order"}]')
        objects = [{}]
    for k, bo in enumerate(objects, 1):
        where = "businessObject" if many is None else f"businessObjects[{k}]"
        if not isinstance(bo, dict):
            errors.append(f"{where} must be an object with a name and a variable")
            objects[k - 1] = {}
            continue
        for key in ("name", "variable"):
            if not isinstance(bo.get(key), str) or not IDENTIFIER.match(bo[key]):
                errors.append(f"{where}.{key} must be an identifier")
    for key in ("name", "variable"):
        values = [bo.get(key) for bo in objects if bo.get(key)]
        errors += [f"businessObjects: the {key} {v!r} is used twice" for v in sorted({v for v in values if values.count(v) > 1})]
    spec["businessObjects"], spec["businessObject"] = objects, objects[0]
    return objects


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text())
    if not isinstance(spec, dict):
        raise SystemExit("Invalid app spec:\n  the spec must be a JSON object")
    errors = unknown_keys(spec)
    app = spec.get("app", {})
    if not app.get("name"):
        errors.append("app.name is required")
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", app.get("acronym", "")):
        errors.append("app.acronym must be 2-8 upper-case letters or digits, starting with a letter")
    objects = business_objects(spec, errors)
    variables = {bo.get("name"): bo.get("variable") for bo in objects}
    if not spec.get("service", {}).get("name"):
        errors.append("service.name is required")
    if spec.get("layout", "steps") not in ("steps", "tabs"):
        errors.append('layout must be "steps" (one screen per step) or "tabs" (one screen, a tab per step)')
    steps = spec.get("steps") or []
    if not steps:
        errors.append("steps must list at least one step")
    if (spec.get("form") or {}).get("tabNextLabel") is not None:
        label = spec["form"]["tabNextLabel"]
        if spec.get("layout", "steps") != "tabs":
            errors.append('form.tabNextLabel needs layout "tabs": it labels the Next button at the end of each tab')
        elif not isinstance(label, str) or not label.strip():
            errors.append("form.tabNextLabel must be non-empty text, e.g. \"Next\"")
    if (spec.get("form") or {}).get("draftLabel") is not None:
        label = spec["form"]["draftLabel"]
        if spec.get("layout", "steps") != "tabs":
            errors.append('form.draftLabel needs layout "tabs": the Save as Draft button sits on the tabs screen')
        elif not spec.get("process"):
            errors.append("form.draftLabel needs a process: a draft is a postponed task, which only a process task can be")
        elif not isinstance(label, str) or not label.strip():
            errors.append("form.draftLabel must be non-empty text, e.g. \"Save as Draft\"")
    reserved = {REFERENCE} if spec.get("confirmation") else set()  # generated properties, on the first object
    if "database" in spec:
        reserved.add(MESSAGE)
    if "database" in spec and len(objects) > 1:
        errors.append("database works with one business object; list one object, or drop the database section")
    process = spec.get("process")
    if process is not None:
        if not isinstance(process, dict) or not process.get("name"):
            errors.append("process.name is required (the workflow's name)")
        elif process.get("approval") is not None and not isinstance(process["approval"], dict):
            errors.append('process.approval must be an object, e.g. {"name": "Review", "lane": "Underwriting"}')
        elif process.get("review") is not None and not isinstance(process["review"], dict):
            errors.append('process.review must be an object, e.g. {"name": "Review Quote", "lane": "Underwriting"}')
        elif process.get("review") is not None and process.get("approval") is not None:
            errors.append("process.review and process.approval cannot be combined; use review for a task that "
                          "finishes the work, approval for an Approve / Send back decision")
        elif process.get("approval") is not None:
            reserved |= {DECISION, COMMENTS}
    seen = {bo.get("variable"): set(reserved) if bo is objects[0] else set() for bo in objects}  # names taken per object
    groups = {}
    for k, g in enumerate(spec.get("groups") or [], 1):
        if not isinstance(g, dict) or not isinstance(g.get("name"), str) or not g["name"].strip():
            errors.append(f"group {k}: must be an object with a name (text)")
            continue
        where = f"group {g['name']}"
        if g["name"] in groups or g["name"] + " Preview" == spec.get("service", {}).get("name"):
            errors.append(f"{where}: the name is used twice")
        if not g.get("fields"):
            errors.append(f"{where}: fields must list at least one field")
        errors += layout_errors(where, g)
        if g.get("businessObject", objects[0].get("name")) not in variables:
            errors.append(f"{where}: unknown businessObject {g['businessObject']!r}; objects: {', '.join(map(str, variables))}")
        var = variables.get(g.get("businessObject", objects[0].get("name")), objects[0].get("variable"))
        for f in g.get("fields", []):
            f["_bo"] = var
            errors += field_errors(where, f, seen[var])
        groups[g.get("name")] = g
    used = set()
    for i, step in enumerate(steps, 1):
        if not step.get("title"):
            errors.append(f"step {i}: title is required")
        for j, s in enumerate(step.get("sections") or [], 1):
            if "group" not in s:
                continue
            g = groups.get(s["group"])
            if not g:
                errors.append(f"step {i} section {j}: unknown group {s['group']!r}; groups: {', '.join(groups) or 'none'}")
                s["fields"] = []
                continue
            used.add(s["group"])
            names = {f.get("name"): f for f in g.get("fields", [])}
            if not isinstance(s.get("hide", []), list):
                errors.append(f"step {i} section {j}: hide must be a list of field names")
                s["hide"] = []
            for name in s.get("hide", []):
                if name not in names:
                    errors.append(f"step {i} section {j}: hide names {name!r}, which is not a field of group {s['group']!r}")
                elif names[name].get("required"):
                    errors.append(f"step {i} section {j}: {name!r} is required, so group {s['group']!r} cannot hide it")
            s.setdefault("title", g["name"])
            s.update(fields=g.get("fields", []), columns=g.get("columns", 1), widths=g.get("widths"))
        if step.get("sections"):
            step["fields"] = [f for s in step["sections"] for f in s.get("fields", [])]
            for j, s in enumerate(step["sections"], 1):
                if not s.get("fields") and "group" not in s:  # a group's own check covers its fields
                    errors.append(f"step {i} section {j}: fields must list at least one field")
        else:
            step["sections"] = [{"title": step.get("title", ""), "columns": step.get("columns", 1), "widths": step.get("widths"), "fields": step.get("fields", []), "implicit": True}]
        for s in step["sections"]:
            if "group" not in s:
                errors += layout_errors(f"step {i}", s)
        if not step.get("fields"):
            errors.append(f"step {i}: fields (or sections) must list at least one field")
        grouped = [f for s in step["sections"] if "group" in s for f in s["fields"]]
        for f in step.get("fields", []):
            if not any(f is g for g in grouped):  # a group's fields are checked once, with the group
                f["_bo"] = objects[0].get("variable")
                errors += field_errors(f"step {i}", f, seen[f["_bo"]])
    for name in groups:
        if name not in used:
            errors.append(f"group {name!r} is not placed in any step; place it in a section ({{\"group\": \"{name}\"}}) or remove it")
    errors += coach_theme.validate(spec, PROJECT)
    if "database" in spec:
        errors += database_errors(spec)
    shown = set().union(*seen.values())
    for name in (spec.get("confirmation") or {}).get("showFields", []):
        if name not in shown:
            errors.append(f"confirmation.showFields: unknown field {name!r}")
    if errors:
        raise SystemExit("Invalid app spec:\n  " + "\n  ".join(errors))
    default_groups(spec)
    return spec


def view_name(text):
    """A group name made from a section title: "&" and "+" read as "and", other punctuation becomes a space, so the
    name works as a View and a service name ("Reporting & Location" -> "Reporting and Location")."""
    text = re.sub(r"\s*[&+]\s*", " and ", text or "")
    return " ".join(re.sub(r"[^\w\s-]", " ", text).split())[:group_views.LABEL_MAX]


def taken_names(spec):
    """Names the default groups' Views and Preview services must not take: the app's services and explicit groups."""
    names = {spec["service"]["name"]}
    for kind in ("approval", "review"):
        task = (spec.get("process") or {}).get(kind)
        if task is not None:
            names.add(task.get("name") or "Review")
    if spec.get("_database"):
        names |= {f"Load {spec['businessObject']['name']}", f"Save {spec['businessObject']['name']}"}
    for g in spec.get("groups") or []:
        names |= {g["name"], f"{g['name']} Preview"}
    return names


def default_groups(spec):
    """Reusable Views by default: every section that lists its own fields becomes a group, so its fields live in a
    View under the app's User interface (with a "<name> Preview" service) that the coach places, as if the spec had
    named the group. The section keeps its title; the group is named after it (the step's title for a step without
    sections). "reusableViews": false on the spec, or "reusable": false on a section (or a step without sections),
    keeps the fields inline."""
    if spec.get("reusableViews") is False:
        return
    taken, made = taken_names(spec), []
    for step in spec["steps"]:
        for s in step["sections"]:
            inline = s.get("reusable") is False or (s.get("implicit") and step.get("reusable") is False)
            if "group" in s or inline or not s.get("fields") or len({f.get("_bo") for f in s["fields"]}) > 1:
                continue
            base = view_name(s.get("title")) or view_name(step["title"]) or "Fields"
            prefixed = view_name(f"{step['title']} {base}") if view_name(step["title"]) != base else ""
            candidates = [base, prefixed] + [f"{base} {n}" for n in range(2, 100)]
            name = next(c for c in candidates if c and c not in taken and f"{c} Preview" not in taken)
            taken |= {name, f"{name} Preview"}
            made.append({"name": name, "columns": s.get("columns", 1), "widths": s.get("widths"), "fields": s["fields"]})
            owner = next((o for o in spec["businessObjects"] if o["variable"] == s["fields"][0].get("_bo")), None)
            if owner and owner is not spec["businessObjects"][0]:
                made[-1]["businessObject"] = owner["name"]
            s["group"] = name
    spec["groups"] = (spec.get("groups") or []) + made


def layout_errors(where, s):
    """Columns and widths of a section or a group."""
    errors = []
    count = s.get("columns", 1)
    if count not in range(1, MAX_COLUMNS + 1):
        return [f"{where}: columns must be 1 to {MAX_COLUMNS}"]
    widths = s.get("widths")
    if widths is not None and (len(widths) != count or not all(isinstance(w, (int, float)) and w > 0 for w in widths)):
        errors.append(f"{where}: widths must list {count} positive numbers, one per column")
    placed = [f for f in s.get("fields", []) if not f.get("wide")]
    if any("column" in f for f in placed):
        for f in placed:
            if f.get("column") not in range(1, count + 1):
                errors.append(f"{where}: field {f.get('name')!r} needs a column from 1 to {count} (every field in a section that places fields)")
    return errors


def control_errors(where, f):
    """Errors of a typed choice control; its options are normalized to {"value", "label"} with typed values: a Boolean
    Radio defaults to Yes (true) and No (false), an Integer Select lists whole numbers."""
    kind, control, name = f.get("type", "String"), f["control"], f.get("name")
    if (kind, control) not in CONTROLS:
        pairs = ", ".join(f"{t} + {c}" for t, c in CONTROLS)
        return [f"{where}: field {name!r} cannot use control {control!r} with type {kind!r}; use one of {pairs}"]
    options = f.get("options")
    if kind == "Boolean":
        options = options or ["Yes", "No"]
        if len(options) != 2:
            return [f"{where}: field {name!r} (Boolean Radio) takes two options: the text for Yes, then for No"]
        labels = [o.get("label") if isinstance(o, dict) else o for o in options]
        f["options"] = [{"value": True, "label": str(labels[0])}, {"value": False, "label": str(labels[1])}]
        return []
    items = [o if isinstance(o, dict) else {"value": o} for o in options or []]
    if not items or not all(type(o.get("value")) is int for o in items):
        return [f"{where}: field {name!r} (Integer Select) needs options: a list of whole numbers or {{\"value\", \"label\"}}"]
    f["options"] = [{"value": o["value"], "label": str(o.get("label") or o["value"])} for o in items]
    return []


def field_errors(where, f, seen):
    """One field's errors; adds its name to seen. Choice options are normalized to {"value", "label"}."""
    errors = []
    name = f.get("name", "")
    if not IDENTIFIER.match(name):
        errors.append(f"{where}: field name {name!r} must be an identifier")
    elif name in seen:
        errors.append(f"{where}: field name {name!r} is used twice (or is reserved)")
    seen.add(name)
    if f.get("type", "String") not in FIELD_TYPES:
        errors.append(f"{where}: field {name!r} has unknown type {f.get('type')!r}; use one of {', '.join(FIELD_TYPES)}")
    if not f.get("label"):
        errors.append(f"{where}: field {name!r} needs a label")
    errors += [f"{where}: {e}" for e in coach_theme.field_errors(f)]
    if f.get("control"):
        errors += control_errors(where, f)
    elif f.get("type") in CHOICES:
        f["options"] = [o if isinstance(o, dict) else {"value": str(o), "label": str(o)} for o in f.get("options") or []]
        if not f["options"] or not all(o.get("value") for o in f["options"]):
            errors.append(f"{where}: field {name!r} ({f['type']}) needs options: a list of strings or {{\"value\", \"label\"}}")
    return errors


def fields(spec):
    """Every field once, in order; a group placed in several steps has its fields once."""
    out, seen = [], set()
    for f in (f for step in spec["steps"] for f in step["fields"]):
        if (f["name"], f.get("_bo")) not in seen:
            seen.add((f["name"], f.get("_bo")))
            out.append(f)
    return out


def database_errors(spec) -> list:
    """Check the "database" section, and keep its table plan in spec["_database"] (sql_service.table_plan).
    The key field becomes required, and every other optional Integer or Decimal field becomes a text field (field_type)
    whose column keeps the number type."""
    stored, errors = [], []
    key = spec["database"].get("key") if isinstance(spec["database"], dict) else None
    for f in fields(spec):
        if any(f.get(k) for k in ("list", "items", "fields", "properties")):
            errors.append(f"database: field {f.get('name')!r} is a list or a nested field; only simple fields (String, Integer, Decimal, Boolean, Date) can be stored")
        elif f.get("type", "String") in FIELD_TYPES:
            f["numberText"] = f.get("type") in NUMBER_TYPES and not f.get("required") and f.get("name") != key
            stored.append({"name": f.get("name", ""), "label": f.get("label", ""), "type": FIELD_TYPES[f.get("type", "String")][0], "text": f["numberText"]})
    if spec.get("confirmation"):
        stored.append({"name": REFERENCE, "label": "Reference Number", "type": "String", "derived": True})
    bo_name, process = spec.get("businessObject", {}).get("name"), spec.get("process")
    tasks = [process.get(kind) if isinstance(process, dict) else None for kind in ("approval", "review")]
    taken = {spec.get("service", {}).get("name"), *(t.get("name") for t in tasks if isinstance(t, dict))}
    errors += [f"database: the service name {n!r} is taken by a generated database service; use another name" for n in (f"Load {bo_name}", f"Save {bo_name}") if n in taken]
    plan, plan_errors = sql_service.table_plan(spec["database"], stored)
    if plan:
        spec["_database"] = plan
        for f in fields(spec):
            if f.get("name") == plan["key"]:
                f["required"] = True
        errors += key_placement_errors(spec, plan["key"])
    return errors + plan_errors


def key_placement_errors(spec, key):
    """The key is required, so no group placement may hide it, and the section that first shows it (where Load is)
    must be editable."""
    placed = [(i, j, s) for i, step in enumerate(spec["steps"], 1) for j, s in enumerate(step["sections"], 1)
              if any(f.get("name") == key for f in s.get("fields", []))]
    errors = [f"step {i} section {j}: {key!r} is the database key, which is required, so group {s['group']!r} cannot hide it"
              for i, j, s in placed if key in s.get("hide", [])]
    if placed and placed[0][2].get("readonly"):
        i, j, _ = placed[0]
        errors.append(f"step {i} section {j}: the database key {key!r} is first shown here read-only; place it editable there, so Load can use it")
    return errors


def database_result(spec):
    """What create_app reports about the table: {"table", "ddl", "columns": [{"name", "type", "primaryKey"}]}, or None."""
    return sql_service.database_result(spec["_database"]) if spec.get("_database") else None


def key_step(spec):
    """Index of the coach that holds the key field (every field of the tabs layout is on coach 0)."""
    key = spec["_database"]["key"]
    return 0 if spec.get("layout") == "tabs" else next(i for i, s in enumerate(spec["steps"]) if any(f["name"] == key for f in s["fields"]))


def submit_coach(spec):
    """Key (as in flow()) of the coach whose Submit ends the form: the review, or else the last step."""
    return "review" if spec.get("review", True) else f"s{0 if spec.get('layout') == 'tabs' else len(spec['steps']) - 1}"


def message_view(spec, lay, coach):
    """The database message (a failed Load or Save, or no record) on the coaches that start them."""
    if not spec.get("_database") or coach not in (f"s{key_step(spec)}", submit_coach(spec)):
        return []
    return [lay.view("Output Text", "", binding=f"tw.local.{spec['businessObject']['variable']}.{MESSAGE}", show_label=False)]


# ---------------------------------------------------------------- coaches


def widget(lay, kind, label="", **kw):
    """An App Builder Widgets view in the layout."""
    return lay.view(widget_toolkit.widgets(TOOLKIT)[kind]["view"], label, view_uuid=WIDGETS[kind], **kw)


def header(spec, lay, title, intro, editable=True):
    """The coach's Theme (its CSS) and App Header (the banner or a plain title, then the intro) widgets.
    Built after the rest of the coach, so the theme can style every input on it; read-only coaches
    (editable=False) get no field icons."""
    style = CSS + (GROUP_CSS if spec.get("groups") else "")
    if spec.get("theme"):
        by_name = {f["name"]: f for f in fields(spec)}
        prefix = f"tw.local.{spec['businessObject']['variable']}."
        inputs = [(vid, by_name[b[len(prefix):]].get("type", "String"), by_name[b[len(prefix):]].get("icon"))
                  for vid, b in (lay.bound if editable else []) if b.startswith(prefix) and b[len(prefix):] in by_name and not vid.startswith("Output_Text")]
        inputs += [(f["name"], f.get("type", "String"), f.get("icon")) for f in lay.group_fields] if editable else []
        widest = max((s.get("columns", 1) for step in spec["steps"] for s in step["sections"]), default=1)
        style += coach_theme.css(spec["theme"], inputs, 1400 if widest > 3 else 960)
    banner = json.dumps(spec["banner"]) if spec.get("banner") else ""
    return [widget(lay, "theme", options=[("css", style)], show_label=False),
            widget(lay, "header", options=[("title", title), ("intro", intro), ("banner", banner)], show_label=False)]


REQUIRED_MESSAGE = "This field is required"
REQUIRED_SUMMARY = "Required_Summary"
REQUIRED_CHECK = """var fields = %s;
var missing = 0, first = null;
for (var i = 0; i < fields.length; i++) {
  var field = fields[i], control = page.ui.get(field[0]);
  if (!control) continue;
  var group = field[2] ? page.ui.get(field[2]) : null;
  if (group && group.context.options._metadata.visibility.get("value") === "READONLY") continue;
  var value = control.getData();
  if (value === null || value === undefined || (typeof value === "string" && value.trim() === "")) {
    control.setValid(false, "%s");
    missing++;
    if (first === null) first = field[1];
  } else {
    control.setValid(true);
  }
}
var summary = document.getElementById("%s");
if (summary) {
  summary.innerHTML = missing
    ? '<div role="alert" style="color:#da1e28;font-weight:600;margin:8px 0">' + missing + (missing === 1 ? " required field is empty" : " required fields are empty") + '</div>'
    : "";
}
if (missing) {
%s  return false;
}
return true;"""


def required_check(fields, tabs_id=None):
    """The On click handler that blocks a finishing button while a required field is empty. fields is the generator's
    list of [control path, tab index or None, group path or None]; the paths are computed here because the
    toolkit cannot know how the generator nests a field's Section and group. false and 0 are answers, and a field in
    a read-only group placement is skipped, as its value is not the user's to give."""
    switch = f'  if (first !== null) page.ui.get("{tabs_id}").setCurrentPane(first);\n' if tabs_id else ""
    return REQUIRED_CHECK % (json.dumps(fields, separators=(",", ":")), REQUIRED_MESSAGE, REQUIRED_SUMMARY, switch)


def required_fields(lay):
    """The [control path, tab index, group path] of every required field placed on a coach."""
    return [["/".join(e["path"]), e["tab"], "/".join(e["group"]) if e["group"] else None] for e in lay.required]


def required_summary(lay, checks):
    """The line above the button bar that the check fills with how many required fields are empty; none without a check."""
    return [lay.html(f'<div id="{REQUIRED_SUMMARY}"></div>', item_id=f"Custom_{REQUIRED_SUMMARY}")] if checks else []


def nest(lay, start, level):
    """Required fields placed since start now sit inside one more container, which adds a level to their paths."""
    for e in lay.required[start:]:
        e["path"].insert(0, level)
        if e["group"]:
            e["group"].insert(0, level)


def actions(lay, buttons, checks=None, bar_id="Action_Bar"):
    """buttons: (event, label, colour style P, D or W[, extra options]). Returns the layout item and {event: button item id}.
    A button whose event is in checks runs that On click handler first. A button with an event of None is
    client-side only: it has no boundary event, so it is left out of the returned ids."""
    checks = checks or {}
    made = []
    for event, label, style, *extra in buttons:
        options = list(extra[0]) if extra else []
        if event in checks:
            options.append(("eventON_CLICK", checks[event]))
        made.append((event, *lay.button(label, style, options)))
    bar = widget(lay, "buttons", "Actions", children=[xml for _, _, xml in made], show_label=False, item_id=bar_id)
    return bar, {event: item for event, item, _ in made if event}


def choices(f):
    """Single Select / Radio Button Group with a static list: name is the stored value, value the text shown."""
    if f.get("type") not in CHOICES and not f.get("control"):
        return []
    items = [{"name": o["value"], "value": o.get("label") or o["value"]} for o in f["options"]]
    return [("itemLookupMode", "L"), ("staticList", json.dumps(items))]


def field_type(f):
    """(business object type, input view) of a field. With a database, an optional number is held as text: BAW's number
    controls turn an empty value into 0, so only a text field can tell "not given" (stored as NULL) from 0."""
    if f.get("control"):
        return f["type"], CONTROLS[(f["type"], f["control"])]
    return ("String", "Text") if f.get("numberText") else FIELD_TYPES[f.get("type", "String")]


INTEGER_SELECT_CHANGE = """var v = me.getData(); if (typeof v === "string") { me.context.binding.set("value", v === "" ? null : Number(v)); }"""
# The Decimal control formats with no decimals when decimalPlaces is unset, and keeps the formatted value: 12.5 becomes 13.
DECIMAL_PLACES = [("decimalPlaces", "2")]


def input_view(lay, var, f, root="tw.local", item_id=None):
    kind, var = field_type(f)[1], f.get("_bo", var)
    # A Single Select hands an Integer field its choice as text; the change handler turns it back into a number.
    change = [("eventON_CHANGE", INTEGER_SELECT_CHANGE)] if f.get("control") == "Select" and f.get("type") == "Integer" else []
    places = DECIMAL_PLACES if kind == "Decimal" else []
    item = lay.view(kind, f["label"], binding=f"{root}.{var}.{f['name']}",
                    options=(REQUIRED if f.get("required") else []) + choices(f) + change + places,
                    help=f.get("help", ""), item_id=item_id)
    if f.get("required") and root == "tw.local":
        lay.required.append({"path": [lay.last_id], "group": None, "tab": None})
    return item


def group_field(lay, var, f):
    """A field inside a group View: bound through the group's data, its control ID is the field's name (field icons
    and Coach Designer use it), and unless it is required its visibility follows the group's option for it."""
    item = input_view(lay, var, f, root="tw.businessData", item_id=f["name"])
    return item if f.get("required") else group_views.bind_visibility(item, f["name"])


def group_fields(g):
    """(path, view kind, label, hideable) of a group's fields, as group_views takes them."""
    return [(f["name"], field_type(f)[1], f["label"], not f.get("required")) for f in g["fields"]]


def place_group(lay, var, s, readonly=False, unlockable=False):
    """A coach's placement of a group View: bound to the coach's object, with the section's hidden fields and,
    for read-only coaches, a read-only visibility that every field in the group follows."""
    view_id, gfields = GROUPS[s["group"]]
    var = s["fields"][0].get("_bo", var) if s.get("fields") else var
    if not (readonly or s.get("readonly")):
        lay.group_fields += [f for f in s["fields"] if f["name"] not in s.get("hide", [])]
    options = group_views.placement_options(gfields, s.get("hide", []), readonly or s.get("readonly", False),
                                            fresh=getattr(lay, "fresh", False) and not (readonly or s.get("readonly")))
    item = lay.view("Group", s["group"], binding=f"tw.local.{var}", view_uuid=view_id, options=options, show_label=False)
    if not (readonly or s.get("readonly")):
        lay.required += [{"path": [lay.last_id, f["name"]], "group": [lay.last_id], "tab": None} for f in s["fields"] if f.get("required")]
    elif unlockable:  # placed read-only, but the reader can unlock it, so its required fields are checked once it is editable
        lay.required += [{"path": [lay.last_id, f["name"]], "group": [lay.last_id], "tab": None}
                         for f in s["fields"] if f.get("required") and f["name"] not in s.get("hide", [])]
    return item


def column_widths(count, weights=None):
    """Percent widths that leave a little room for the gaps: 2 columns are 49% each, 3 are 32.3%."""
    weights = weights or [1] * count
    return [f"{int((100 - count) * w / sum(weights) * 10) / 10}%" for w in weights]


def columns(lay, var, fields, count, weights=None, make=input_view):
    """Lay fields out in count columns; a "wide" field takes the full width.
    Fields fill the columns row by row, unless they say which "column" they belong to.
    make builds each field's view: input_view, or output for a read-only screen."""
    if count <= 1:
        return [make(lay, var, f) for f in fields]
    widths = column_widths(count, weights)
    width = lambda c: [("@width", json.dumps({"isResponsiveData": True, "values": [{"deviceConfigID": "LargeID", "value": widths[c]}]}))]
    out, run = [], []

    def flush():
        if run:
            if any("column" in f for f in run):
                groups = [[make(lay, var, f) for f in run if f["column"] == c + 1] for c in range(count)]
            else:
                views = [make(lay, var, f) for f in run]
                groups = [views[c::count] for c in range(min(count, len(views)))]
            cols = [lay.view("Vertical Layout", f"Column {c + 1}", children=g, options=width(c), show_label=False) for c, g in enumerate(groups)]
            out.append(lay.view("Horizontal Layout", "Columns", children=cols, show_label=False))
            run.clear()

    for f in fields:
        if f.get("wide"):
            flush()
            out.append(make(lay, var, f))
        else:
            run.append(f)
    flush()
    return out


def section(lay, var, s):
    start = len(lay.required)
    content = [place_group(lay, var, s)] if "group" in s else columns(lay, var, s["fields"], s.get("columns", 1), s.get("widths"))
    item = widget(lay, "section", s["title"], children=content, options=[("intro", s.get("intro", ""))], show_label=not s.get("hideTitle"))
    nest(lay, start, lay.last_id)
    return item


def sections(lay, var, step):
    return [section(lay, var, s) for s in step["sections"]]


def tab_content(lay, var, step):
    """A tab shows its fields directly, or a panel per section when the step names sections."""
    s = step["sections"][0]
    if s.get("implicit"):
        return [place_group(lay, var, s)] if "group" in s else columns(lay, var, s["fields"], s.get("columns", 1), s.get("widths"))
    return sections(lay, var, step)


def step_coach(spec, i):
    var, step, last = spec["businessObject"]["variable"], spec["steps"][i], i == len(spec["steps"]) - 1
    lay = Layout()
    forward = step.get("nextLabel") or ("Submit" if last and not spec.get("review", True) else "Next")
    load = [(f"load{i}", "Load", "D")] if spec.get("_database") and i == key_step(spec) else []
    buttons = ([(f"back{i}", step.get("backLabel") or "Back", "D")] if i else []) + load + [(f"next{i}", forward, "P")]
    buttons += [(f"cancel{i}", step["cancelLabel"], "W")] if step.get("cancelLabel") else []
    body = [*message_view(spec, lay, f"s{i}"), *sections(lay, var, step)]
    checks = {f"next{i}": required_check(required_fields(lay))} if lay.required else {}  # each step checks its own fields
    bar, events = actions(lay, buttons, checks)
    count = f"Step {i + 1} of {len(spec['steps'])}: " if len(spec["steps"]) > 1 else ""
    return Layout.wrap([*header(spec, lay, count + step["title"], step.get("intro", "")), *body, *required_summary(lay, checks), bar]), events


def form_coach(spec):
    """layout "tabs": every step is a tab of one screen; Next leaves the screen. With form.tabNextLabel each tab ends
    with its own button bar instead: Next switches to the next tab, and the last tab's bar finishes the task."""
    var, form = spec["businessObject"]["variable"], spec.get("form") or {}
    lay = Layout()
    tabs_id = lay._item_id("Tab Section")
    per_tab, draft = bool(form.get("tabNextLabel")), form.get("draftLabel")
    lay.fresh = bool(draft)  # editable group placements get the freshForm option
    last = len(spec["steps"]) - 1
    tabs, contents, drafts = [], [], {}
    for n, s in enumerate(spec["steps"]):
        start = len(lay.required)
        content = tab_content(lay, var, s)
        for e in lay.required[start:]:
            e["tab"] = n
        if per_tab and n < last:
            switch = f'page.ui.get("{tabs_id}").setCurrentPane({n + 1});\nreturn false;'
            bar, made = actions(lay, [*([(f"draft{n}", draft, "D")] if draft else []),
                                      (None, form["tabNextLabel"], "P", [("eventON_CLICK", switch)])], bar_id=f"Action_Bar{n + 1}")
            drafts.update(made)
            content = [*content, bar]
        contents.append(content)
        if not per_tab:
            tabs.append(lay.view("Vertical Layout", s["title"], children=content))
    finish = ("next0", form.get("nextLabel") or ("Next" if spec.get("review", True) else "Submit"), "P")
    buttons = [("load0", "Load", "D")] if spec.get("_database") else []
    buttons += [(f"draft{last}" if per_tab else "draft0", draft, "D")] if draft else []  # never checked for required fields
    buttons += [finish]
    buttons += [("cancel0", form["cancelLabel"], "W")] if form.get("cancelLabel") else []
    checks = {"next0": required_check(required_fields(lay), tabs_id)} if lay.required else {}
    if per_tab:
        bar, events = actions(lay, buttons, checks, bar_id=f"Action_Bar{last + 1}")
        events = {**drafts, **events}
        contents[last] = [*contents[last], *required_summary(lay, checks), bar]
        tabs = [lay.view("Vertical Layout", s["title"], children=c) for s, c in zip(spec["steps"], contents)]
    body = lay.view("Tab Section", "Steps", binding="tw.local.currentTab" if draft else None, children=tabs, show_label=False, item_id=tabs_id)
    top = [*header(spec, lay, form.get("title", spec["service"]["name"]), form.get("intro", "")), *message_view(spec, lay, "s0")]
    if per_tab:
        return Layout.wrap([*top, body]), events
    bar, events = actions(lay, buttons, checks)
    return Layout.wrap([*top, body, *required_summary(lay, checks), bar]), events


def output(lay, var, f):
    kind, var = field_type(f)[1], f.get("_bo", var)
    binding = f"tw.local.{var}.{f['name']}"
    if kind in ("Text", "Text Area"):
        return lay.view("Output Text", f["label"], binding=binding)
    return lay.view(kind, f["label"], binding=binding, options=READ_ONLY + choices(f) + (DECIMAL_PLACES if kind == "Decimal" else []))


def read_only(lay, var, s, shown, spec, unlockable=False):
    """A section on the Review coach: its group placed read-only, once (a group a step shows again for reference is
    skipped), hiding only the fields every placement hides; or an output per field."""
    if "group" not in s:
        return [output(lay, var, f) for f in s["fields"]]
    if s["group"] in shown:
        return []
    shown.add(s["group"])
    hides = [set(p.get("hide", [])) for step in spec["steps"] for p in step["sections"] if p.get("group") == s["group"]]
    return [place_group(lay, var, dict(s, hide=sorted(set.intersection(*hides))), readonly=True, unlockable=unlockable)]


def review_coach(spec):
    var, review = spec["businessObject"]["variable"], spec.get("review")
    review = review if isinstance(review, dict) else {}
    lay = Layout()
    shown, panels = set(), []
    for step in spec["steps"]:
        children = [item for s in step["sections"] for item in read_only(lay, var, s, shown, spec)]
        panels += [widget(lay, "review", step["title"], children=children)] if children else []
    bar, events = actions(lay, [("backReview", "Back", "D"), ("submit", review.get("submitLabel") or "Submit", "P")])
    intro = review.get("intro", "Check your answers. Press Back to change them or Submit to send them.")
    return Layout.wrap([*header(spec, lay, review.get("title", "Review and Submit"), intro, editable=False), *message_view(spec, lay, "review"), *panels, bar]), events


def confirmation_coach(spec):
    var, conf = spec["businessObject"]["variable"], spec["confirmation"]
    by_name = {f["name"]: f for f in fields(spec)}
    lay = Layout()
    outputs = [lay.view("Output Text", "Reference Number", binding=f"tw.local.{var}.{REFERENCE}")]
    outputs += [output(lay, var, by_name[n]) for n in conf.get("showFields", [])]
    summary = widget(lay, "review", "Summary", children=outputs)
    bar, events = actions(lay, [("done", "Done", "P")])
    return Layout.wrap([*header(spec, lay, conf.get("title", "Submitted"), conf.get("message", ""), editable=False), summary, bar]), events


# ---------------------------------------------------------------- flow


def draft_label(spec):
    return (spec.get("form") or {}).get("draftLabel") if spec.get("layout") == "tabs" else None


def init_script(spec, only=None):
    """Creates every business object, or only the one with variable `only` (a process task gets them from the process;
    start fresh only the first time). A Boolean checkbox starts false; a Boolean Radio starts null, so the user has to answer."""
    first, blocks = spec["businessObjects"][0]["variable"], []
    for o in spec["businessObjects"]:
        var = o["variable"]
        if only and var != only:
            continue
        lines = [f"tw.local.{var} = {{}};"]  # client-side scripts have no tw.object factory
        lines += [f"tw.local.{var}.{f['name']} = false;" for f in fields(spec)
                  if f.get("type") == "Boolean" and not f.get("control") and f.get("_bo", first) == var]
        if var == first and spec.get("confirmation"):
            lines.append(f'tw.local.{var}.{REFERENCE} = "";')
        if var == first and spec.get("_database"):
            lines.append(f'tw.local.{var}.{MESSAGE} = "";')
        blocks.append(f"if (!tw.local.{var}) {{\n  " + "\n  ".join(lines) + "\n}" if spec.get("process") else "\n".join(lines))
    if draft_label(spec) and not only:  # a task resumed from a draft keeps freshForm false, so its answers stay as typed
        blocks.append("if (tw.local.freshForm !== false) {\n  tw.local.freshForm = true;\n}")
    return "\n".join(blocks)


def assign_script(spec):
    prefix, ref = json.dumps(spec["confirmation"].get("referencePrefix", "REF-")), f"tw.local.{spec['businessObject']['variable']}.{REFERENCE}"
    assign = f"{ref} = {prefix} + new Date().getTime().toString().slice(-8);"
    return f'if (!{ref}) {{ {assign} }}' if spec.get("_database") else assign  # a loaded record keeps its stored reference


def flow(spec, run_sql=None):
    """Steps and sequence flows for coach_builder.coachflow. run_sql: sql_service.database_services(), when the spec has a database."""
    review, confirm, plan = spec.get("review", True), spec.get("confirmation"), spec.get("_database")
    tabs = spec.get("layout") == "tabs"
    count = 1 if tabs else len(spec["steps"])  # coaches before the review
    steps = [("init", "Initialize", init_script(spec))]
    if tabs:
        steps.append(("s0", (spec.get("form") or {}).get("title", spec["service"]["name"]), form_coach(spec)))
    else:
        steps += [(f"s{i}", s["title"], step_coach(spec, i)) for i, s in enumerate(spec["steps"])]
    if draft_label(spec):
        steps += [("draftmark", "Mark as draft", "tw.local.freshForm = false;"),  # a reopened draft keeps what was typed
                  ("postpone", "Postpone Task", {"postpone": True})]
    finish = "assign" if confirm else "end"
    submit = "save_key" if plan else finish  # where Submit leads
    flows = [("start", "init", None, "rightCenter", "leftCenter"), ("init", "s0", None, "rightCenter", "leftCenter")]
    if draft_label(spec):  # every Save as Draft button leaves through the one Postpone event, which returns to the tabs
        buttons = len(spec["steps"]) if (spec.get("form") or {}).get("tabNextLabel") else 1
        flows += [("s0", "draftmark", f"draft{n}", "rightCenter", "topCenter", (None, None)) for n in range(buttons)]
        flows += [("draftmark", "postpone", None, "rightCenter", "leftCenter", (None, None), True),
                  ("postpone", "s0", None, "bottomCenter", "leftBottom", (None, None), True)]
    for i in range(count):
        target = f"s{i + 1}" if i < count - 1 else ("review" if review else submit)
        flows.append((f"s{i}", target, f"next{i}", "rightCenter", "leftCenter"))
        if i:
            flows.append((f"s{i}", f"s{i - 1}", f"back{i}", "topCenter", "topCenter"))
    cancels = [0] if tabs and (spec.get("form") or {}).get("cancelLabel") else [] if tabs else [i for i, s in enumerate(spec["steps"]) if s.get("cancelLabel")]
    flows += [(f"s{i}", "end", f"cancel{i}", "bottomCenter", "bottomCenter") for i in cancels]
    if review:
        steps.append(("review", (review if isinstance(review, dict) else {}).get("title", "Review and Submit"), review_coach(spec)))
        flows += [("review", f"s{count - 1}", "backReview", "topCenter", "topCenter"), ("review", submit, "submit", "rightCenter", "leftCenter")]
    if plan:
        steps += save_check_steps(spec)
        flows += save_check_flows(spec, "assign" if confirm else "save")
    if confirm:
        steps.append(("assign", "Assign reference", assign_script(spec)))
        flows.append(("assign", "save" if plan else "confirm", None, "rightCenter", "leftCenter"))
    if plan:
        steps += save_steps(spec, run_sql)
        flows += save_flows(spec, "confirm" if confirm else "end")
    if confirm:
        steps.append(("confirm", confirm.get("title", "Submitted"), confirmation_coach(spec)))
        flows.append(("confirm", "end", "done", "rightCenter", "leftCenter"))
    if plan:
        steps += load_steps(spec, run_sql)
        flows += load_flows(spec)
        steps, flows = clear_message_steps(spec, steps, flows)
    return steps, flows


# ---------------------------------------------------------------- database: Load and Save


def database_call(spec, service, **inputs):
    return sql_service.call_step(service, f"tw.local.{spec['businessObject']['variable']}.{MESSAGE}", **inputs)


def message_set(spec):
    return f'tw.local.{spec["businessObject"]["variable"]}.{MESSAGE} != ""'


def save_check_steps(spec):
    """Submit checks the form first: without the key, or with a number that is not one, it goes back to the coach it was submitted from, with a message."""
    var, plan = spec["businessObject"]["variable"], spec["_database"]
    return [("save_key", "Check form", sql_service.missing_key_script(var, plan, "before you submit", numbers=True)), ("save_key_ok", "Form ready?", {"gateway": True})]


def save_check_flows(spec, next_step):
    return [("save_key", "save_key_ok", None, "rightCenter", "leftCenter"),
            ("save_key_ok", submit_coach(spec), None, "topCenter", "topCenter", ("Fix first", message_set(spec))),
            ("save_key_ok", next_step, None, "rightCenter", "leftCenter", ("Ready", None))]


def save_steps(spec, run_sql):
    """Save <BO> (after "Assign reference", so the reference is stored too), then a check of what the service answered."""
    var, plan, name = spec["businessObject"]["variable"], spec["_database"], spec["businessObject"]["name"]
    values = sql_service.values_expression(var, plan["columns"])
    return [("save", f"Save {name}", database_call(spec, run_sql["save"], values=values)),
            ("save_done", "Check save", sql_service.save_apply_script(var)), ("save_ok", "Saved?", {"gateway": True})]


def save_flows(spec, next_step):
    """A failed Save returns to the coach where the user pressed Submit, with the message; otherwise on."""
    return [("save", "save_done", None, "rightCenter", "leftCenter"), ("save_done", "save_ok", None, "rightCenter", "leftCenter"),
            ("save_ok", submit_coach(spec), None, "topCenter", "topCenter", ("Failed", message_set(spec))),
            ("save_ok", next_step, None, "rightCenter", "leftCenter", ("Saved", None))]


def clear_message_steps(spec, steps, flows):
    """A database message belongs to the coach it was raised on: moving to another coach (Next or Back) from the coaches that
    show it clears it first, so a failed Load does not follow the user to the review."""
    shown, var = {f"s{key_step(spec)}", submit_coach(spec)}, spec["businessObject"]["variable"]
    moving = lambda f: f[0] in shown and f[2] and f[2].startswith(("next", "back")) and f[1] != "save_key"
    cleared = [f for f in flows if moving(f)]
    steps = steps + [(f"clear_{f[2]}", "Clear message", f'tw.local.{var}.{MESSAGE} = "";') for f in cleared]
    flows = [f for f in flows if not moving(f)]
    for f in cleared:
        flows += [(f[0], f"clear_{f[2]}", f[2], f[3], f[4]), (f"clear_{f[2]}", f[1], None, "rightCenter", "leftCenter")]
    return steps, flows


def load_steps(spec, run_sql):
    """Load <BO>: look the row up by the key typed on the coach, then fill the form (or set a message)."""
    var, plan, name = spec["businessObject"]["variable"], spec["_database"], spec["businessObject"]["name"]
    key = sql_service.cell(var, sql_service.key_column(plan))
    return [("load", f"Load {name}", database_call(spec, run_sql["load"], key=key)),
            ("load_done", "Fill form", sql_service.load_apply_script(var, plan))]


def load_flows(spec):
    coach = f"s{key_step(spec)}"
    return [(coach, "load", f"load{key_step(spec)}", "bottomCenter", "bottomCenter"), ("load", "load_done", None, "rightCenter", "leftCenter"),
            ("load_done", coach, None, "bottomCenter", "bottomCenter")]


# ---------------------------------------------------------------- process


def approval_coach(spec):
    """Every field read-only, section by section, then a comments box and Approve / Send back."""
    var, appr = spec["businessObject"]["variable"], spec["process"]["approval"]
    lay = Layout()
    shown = set()
    panels = [widget(lay, "review", s["title"], children=read_only(lay, var, s, shown, spec) if "group" in s
                     else columns(lay, var, s["fields"], s.get("columns", 1), s.get("widths"), make=output))
              for step in spec["steps"] for s in step["sections"] if s.get("group") not in shown]
    comments = widget(lay, "section", "Decision", children=[lay.view("Text Area", appr.get("commentsLabel") or "Comments", binding=f"tw.local.{var}.{COMMENTS}")])
    bar, events = actions(lay, [("approve", appr.get("approveLabel") or "Approve", "P"), ("sendBack", appr.get("returnLabel") or "Send Back", "W")])
    title = appr.get("name") or "Review"
    return Layout.wrap([*header(spec, lay, title, appr.get("intro", ""), editable=False), *panels, comments, bar]), events


def edit_review_coach(spec):
    """Every section read-only, each group with an Edit button that unlocks it, and one button that finishes the task.
    The finishing button checks the required fields of the groups that are editable by then."""
    review = spec["process"]["review"]
    lay = Layout()
    shown, panels = set(), []
    for step in spec["steps"]:
        for s in step["sections"]:
            if s.get("group") in shown:
                continue
            start = len(lay.required)
            section_id = lay._item_id("Section")
            if "group" in s:
                content = read_only(lay, spec["businessObject"]["variable"], s, shown, spec, unlockable=True)
                options = [("intro", ""), ("editLabel", review.get("editLabel") or "Edit"), ("editTarget", f"{section_id}/{lay.last_id}")]
            else:
                content = columns(lay, spec["businessObject"]["variable"], s["fields"], s.get("columns", 1), s.get("widths"), make=output)
                options = [("intro", "")]
            panels.append(widget(lay, "section", s["title"], children=content, options=options, item_id=section_id))
            nest(lay, start, section_id)
    event = "complete"
    checks = {event: required_check(required_fields(lay))} if lay.required else {}
    bar, events = actions(lay, [(event, review.get("completeLabel") or "Submit", "P")], checks)
    title = review.get("name") or "Review"
    return Layout.wrap([*header(spec, lay, title, "", editable=False), *panels, *required_summary(lay, checks), bar]), events


def edit_review_flow(spec):
    init = "\n".join(f"if (!tw.local.{o['variable']}) {{ tw.local.{o['variable']} = {{}}; }}" for o in spec["businessObjects"])
    steps = [("init", "Initialize", init), ("s0", spec["process"]["review"].get("name") or "Review", edit_review_coach(spec))]
    flows = [("start", "init", None, "rightCenter", "leftCenter"), ("init", "s0", None, "rightCenter", "leftCenter"),
             ("s0", "end", "complete", "rightCenter", "leftCenter")]
    return steps, flows


def approval_flow(spec):
    var = spec["businessObject"]["variable"]
    init = "\n".join(f"if (!tw.local.{o['variable']}) {{ tw.local.{o['variable']} = {{}}; }}" for o in spec["businessObjects"])
    steps = [("init", "Initialize", init),
             ("s0", spec["process"]["approval"].get("name") or "Review", approval_coach(spec)),
             ("ok", APPROVED, f"tw.local.{var}.{DECISION} = {json.dumps(APPROVED)};"),
             ("back", SENT_BACK, f"tw.local.{var}.{DECISION} = {json.dumps(SENT_BACK)};")]
    flows = [("start", "init", None, "rightCenter", "leftCenter"), ("init", "s0", None, "rightCenter", "leftCenter"),
             ("s0", "ok", "approve", "rightCenter", "leftCenter"), ("s0", "back", "sendBack", "bottomCenter", "leftCenter"),
             ("ok", "end", None, "rightCenter", "leftCenter"), ("back", "end", None, "rightCenter", "bottomCenter")]
    return steps, flows


def process_definition(spec, form, approval, bo_id, review=None):
    """The workflow as an extra .twx object (id, versionId, name, type, xml). bo_id: {object variable: class id}.
    form, approval: (service id, (input id, output id), or a list of those pairs, one per object); approval and review may be None."""
    proc, var = spec["process"], spec["businessObject"]["variable"]
    task = proc.get("formTask") or {}
    first_lane = task.get("lane") or "Requester"
    nodes = [{"key": "start", "kind": "start", "name": "Start", "lane": first_lane, "x": 30},
             {"key": "form", "kind": "task", "name": task.get("name") or spec["service"]["name"], "lane": first_lane, "x": 120,
              "service": form[0], "io": form[1]}]
    flows = [{"from": "start", "to": "form"}]
    lanes = [first_lane]
    if approval:
        appr = proc["approval"]
        lane = appr.get("lane") or "Approver"
        lanes += [lane] if lane != first_lane else []
        nodes += [{"key": "approval", "kind": "task", "name": appr.get("name") or "Review", "lane": lane, "x": 300, "service": approval[0], "io": approval[1]},
                  {"key": "decision", "kind": "gateway", "name": f"{APPROVED}?", "lane": lane, "x": 470},
                  {"key": "end", "kind": "end", "name": "End", "lane": lane, "x": 600}]
        flows += [{"from": "form", "to": "approval"}, {"from": "approval", "to": "decision"},
                  {"from": "decision", "to": "form", "name": appr.get("returnLabel") or "Send Back", "out": "topCenter", "in": "bottomCenter",
                   "condition": f"tw.local.{var} != null && tw.local.{var}.{DECISION} == {json.dumps(SENT_BACK)}"},
                  {"from": "decision", "to": "end", "name": APPROVED}]
    elif review:
        rev = proc["review"]
        lane = rev.get("lane") or "Reviewer"
        lanes += [lane] if lane != first_lane else []
        nodes += [{"key": "review", "kind": "task", "name": rev.get("name") or "Review", "lane": lane, "x": 300, "service": review[0], "io": review[1]},
                  {"key": "end", "kind": "end", "name": "End", "lane": lane, "x": 450}]
        flows += [{"from": "form", "to": "review"}, {"from": "review", "to": "end"}]
    else:
        nodes.append({"key": "end", "kind": "end", "name": "End", "lane": first_lane, "x": 300})
        flows.append({"from": "form", "to": "end"})
    pid, version = "25." + uid(), uid()
    objects = spec["businessObjects"]
    refs = ([o["variable"] for o in objects], [bo_id[o["variable"]] for o in objects]) if len(objects) > 1 else (var, bo_id[var])
    return pid, version, proc["name"], "bpd", process_xml(pid, version, proc["name"], *refs, lanes, nodes, flows, "generate_app", proc.get("description", ""))


# ---------------------------------------------------------------- package


def kept_view(base_twx, view_id, bo_id, names):
    """A group View from the app on the server that someone changed in BAW, ready to go into this build: pointed at
    this build's business object, with a new version. None when there is none to keep."""
    if not base_twx:
        return None
    with zipfile.ZipFile(base_twx) as z:
        if f"objects/{view_id}.xml" not in z.namelist():
            return None
        text = z.read(f"objects/{view_id}.xml").decode("utf-8")
    if not group_views.changed_in_baw(text):
        return None
    old = re.search(r'<bindingType name="[^"]+">.*?<classId>([^<]+)</classId>', text, re.S)
    if old:  # a group whose data binding someone removed is kept as it is
        text = text.replace(f"<classId>{old.group(1)}</classId>", f"<classId>/{bo_id}</classId>")
    text = re.sub(r"(<coachView id=\"[^\"]+\" name=\"[^\"]+\">.*?<versionId>)[^<]+", lambda m: m.group(1) + uid(), text, count=1, flags=re.S)
    version = re.search(r"<coachView .*?<versionId>([^<]+)</versionId>", text, re.S).group(1)
    return version, text, [f["path"] for f in group_views.layout_fields(text) if f["path"] not in names]


def group_variable(spec, group):
    """The variable of the business object a group's fields live in."""
    return group["fields"][0]["_bo"] if group["fields"] else spec["businessObjects"][0]["variable"]


def group_objects(spec, bo_id, base=None, replace=()):
    """(bo_id: {object variable: class id}.) The app's group Views, their Preview services and the visibility type their options use, as package objects;
    fills GROUPS for the coaches that place them. A group View the app on the server (base) has and someone changed
    in BAW stays as it is (listed in KEPT), unless its group is in replace."""
    GROUPS.clear()
    KEPT.clear()
    unknown = [n for n in replace if n not in {g["name"] for g in spec.get("groups") or []}]
    if unknown:
        raise SystemExit(f"--replace-group names no group of the app spec: {', '.join(unknown)}; groups: "
                         + (", ".join(g["name"] for g in spec.get("groups") or []) or "none"))
    if not spec.get("groups"):
        return []
    acronym = spec["app"]["acronym"]
    type_id, type_version, type_xml = group_views.visibility_type(acronym)
    objects = [(type_id, type_version, group_views.VISIBILITY_TYPE, "twClass", type_xml)]
    for g in spec["groups"]:
        var = group_variable(spec, g)
        lay = Layout("ns2")
        items = columns(lay, var, g["fields"], g.get("columns", 1), g.get("widths"), make=group_field)
        view_id, version, xml = group_views.group_view(acronym, g["name"], var, f"/{bo_id[var]}", f"/{type_id}", group_fields(g), items, "generate_app",
                                                         blank_required=any(f.get("control") == "Radio" or (f.get("required") and f.get("type") in NUMBER_TYPES)
                                                                            for f in g["fields"]),
                                                         fresh_ref=f"{TWSYS}/{SYSTEM_TYPES['Boolean']}" if draft_label(spec) else None)
        GROUPS[g["name"]] = (view_id, group_fields(g))
        kept = None if g["name"] in replace else kept_view(base, view_id, bo_id[var], {f["name"] for f in fields(spec)})
        if kept:
            version, xml, missing = kept
            KEPT[g["name"]] = missing
        objects.append((view_id, version, g["name"], "coachView", xml))
    for g in spec["groups"]:
        var = group_variable(spec, g)
        lay = Layout()
        body = widget(lay, "section", g["name"], children=[place_group(lay, var, {"group": g["name"], "fields": g["fields"]})])
        bar, events = actions(lay, [("ok", "OK", "P")])
        layout = Layout.wrap([*header(spec, lay, f"{g['name']} Preview", "The reusable group on its own."), body, bar])
        objects.append(group_views.preview_service(acronym, f"{g['name']} Preview", var, bo_id[var], layout, events["ok"], init_script(spec, only=var), "generate_app"))
    return objects


def generate(spec: dict, dest: Path, toolkit: Path, base: Path | None = None, replace_groups=()):
    """toolkit: the App Builder Widgets .twx (widget_toolkit.py build builder) the app is to depend on."""
    WIDGETS.clear()
    WIDGETS.update(widget_toolkit.view_ids(TOOLKIT, toolkit))
    objects, svc, app = spec["businessObjects"], spec["service"], spec["app"]
    bo = objects[0]
    props = {o["variable"]: [(f["name"], field_type(f)[0]) for f in fields(spec) if f["_bo"] == o["variable"]] for o in objects}
    first = props[bo["variable"]]
    if spec.get("confirmation"):
        first.append((REFERENCE, "String"))
    proc = spec.get("process")
    approval = proc and proc.get("approval") is not None
    review = proc and proc.get("review") is not None
    if approval:
        first += [(DECISION, "String"), (COMMENTS, "String")]
    if spec.get("_database"):
        first.append((MESSAGE, "String"))
    several = len(objects) > 1
    bo_ids = {o["variable"]: "12." + uid() for o in objects}
    extra = group_objects(spec, bo_ids, base, replace_groups)
    target = app_template.read_base(base) if base else app_template.builtin()
    run_sql = sql_service.database_services(spec["_database"], bo["name"], target["sql"]) if spec.get("_database") else None
    steps, flows = flow(spec, run_sql)
    service = {"name": svc["name"], "description": svc.get("description", svc["name"])}
    if draft_label(spec):  # local variables a postponed task keeps: whether the form is new, and the tab the user left
        service["variables"] = [("freshForm", "Boolean", "2056." + uid()), ("currentTab", "Integer", "2056." + uid())]
    pair = lambda: ("2055." + uid(), "2055." + uid())
    io = lambda: ([pair() for _ in objects] if several else pair()) if proc else None
    variables = [o["variable"] for o in objects]
    names = variables if several else variables[0]
    private = lambda: ["2056." + uid() for _ in objects] if several else "2056." + uid()
    form_io = io()
    services = [("1." + uid(), uid(), form_io or private(), service,
                 lambda b, v: coachflow(service, steps, flows, b, v, names, io=form_io))]
    if run_sql:
        extra += [service[:5] for service in run_sql.values()]
    if proc:
        approval_ids = None
        if approval:
            a_io, a_steps, a_flows = io(), *approval_flow(spec)
            a_service = {"name": proc["approval"].get("name") or "Review", "description": f"{proc['name']}: {proc['approval'].get('name') or 'Review'}",
                         "exposed": False}  # opened only as the process's approval task
            services.append(("1." + uid(), uid(), a_io, a_service, lambda b, v: coachflow(a_service, a_steps, a_flows, b, v, names, io=a_io)))
            approval_ids = (services[-1][0], a_io)
        review_ids = None
        if review:
            r_io, r_steps, r_flows = io(), *edit_review_flow(spec)
            r_service = {"name": proc["review"].get("name") or "Review", "description": f"{proc['name']}: {proc['review'].get('name') or 'Review'}",
                         "exposed": False}  # opened only as the process's review task
            services.append(("1." + uid(), uid(), r_io, r_service, lambda b, v: coachflow(r_service, r_steps, r_flows, b, v, names, io=r_io)))
            review_ids = (services[-1][0], r_io)
        extra.append(process_definition(spec, (services[0][0], form_io), approval_ids, bo_ids, review_ids))
    classes = [{"id": bo_ids[v], "version": uid(), "name": o["name"], "props": props[v]} for v, o in zip(variables, objects)]
    write_twx(dest, {"name": app["name"], "acronym": app["acronym"], "snapshot": app.get("snapshot", "1.0.0")},
              classes if several else classes[0], names, services, "generate_app", target, extra)
    with zipfile.ZipFile(dest) as twx:
        entries = {i.filename: twx.read(i) for i in twx.infolist()}
    package, _, add, drop = widget_toolkit.embed(entries["META-INF/package.xml"].decode("utf-8"), toolkit)
    entries["META-INF/package.xml"] = package.encode("utf-8")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in {**{n: d for n, d in entries.items() if n not in drop}, **add}.items():
            out.writestr(name, data)
    if spec.get("_database"):
        try:
            sql_service.check_data_source(dest, target["sql"])
        except ValueError as e:
            dest.unlink()
            raise SystemExit(str(e)) from e


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", type=Path, help="App spec JSON (see app-specs/example-equipment-request.json)")
    parser.add_argument("dest", type=Path, help="Output .twx")
    parser.add_argument("--base", type=Path, help="An app exported from the target server, to match its BAW build; the app itself to add a snapshot to it")
    parser.add_argument("--database-json", type=Path, help='Write the spec\'s database result ({"table", "ddl", "columns"}) here, when the spec has a database')
    parser.add_argument("--toolkit", type=Path, required=True, help="App Builder Widgets .twx (widget_toolkit.py build builder), installed on the server")
    parser.add_argument("--replace-group", action="append", default=[], metavar="NAME",
                        help="Rebuild this group from the spec even if it was changed in BAW (repeatable)")
    args = parser.parse_args()
    spec = load_spec(args.spec)
    generate(spec, args.dest, args.toolkit, args.base, args.replace_group)
    app = spec["app"]
    print(f"Wrote {args.dest}: app {app['name']} ({app['acronym']}), snapshot {app.get('snapshot', '1.0.0')}")
    print(f"Service: {spec['service']['name']}, {len(spec['steps'])} step(s) as {'tabs' if spec.get('layout') == 'tabs' else 'screens'}, {len(fields(spec))} field(s)"
          + (", review" if spec.get("review", True) else "") + (", confirmation" if spec.get("confirmation") else ""))
    if spec.get("groups"):
        print("Groups: " + ", ".join(f"{g['name']} (View, and service {g['name']} Preview)" for g in spec["groups"]))
    if KEPT:
        print(f"Changed in BAW, kept: {json.dumps(list(KEPT))}")
        for name, missing in KEPT.items():
            if missing:
                print(f"Group {name} uses fields the app spec does not have: {', '.join(missing)}; add them to the spec, or rebuild the group from the spec (replace_groups)")
    result = database_result(spec)
    if result:
        print(f"Database: table {result['table']} in bawexternal (data source {sql_service.DATA_SOURCE}), key {spec['_database']['key']}; Load button, save on Submit")
        print("Run this once before the app is used (run_sql on bawexternal), then compare describe_table with the columns:")
        print(f"  {result['ddl']}")
        if args.database_json:
            args.database_json.write_text(json.dumps(result, indent=2) + "\n")
    if spec.get("process"):
        proc = spec["process"]
        print(f"Process: {proc['name']}, task {(proc.get('formTask') or {}).get('name') or spec['service']['name']}"
              + (f", then approval task {proc['approval'].get('name') or 'Review'} (Send back returns to the first task)" if proc.get("approval") is not None else "")
              + (f", then review task {proc['review'].get('name') or 'Review'}" if proc.get("review") is not None else ""))


if __name__ == "__main__":
    main()
