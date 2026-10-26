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

A step lists its fields, or "sections" of fields, each a titled panel; "columns": 2 to 6 lays the
fields out side by side ("wide": true keeps a field full width). By default fields fill the columns left
to right, row by row; give every field a "column" (1, 2, ...) to place it, top to bottom, in that column,
and "widths": [1, 1.6, 1] to make some columns wider. Fields of type Select (dropdown) and Radio take a
list of "options". "cancelLabel" on a step or on "form" adds a button that ends the service.

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
import widget_toolkit
from coach_builder import SYSTEM_TYPES, Layout, coachflow, uid, write_twx
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
MAX_COLUMNS = 6
PROJECT = Path(__file__).resolve().parent.parent
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REFERENCE = "referenceNumber"
DECISION, COMMENTS = "decision", "reviewComments"  # set by the approval task
APPROVED, SENT_BACK = "Approved", "Sent back"
TOOLKIT = "builder"
WIDGETS = {}  # App Builder Widgets view ID by kind, from the toolkit generate() builds against
GROUPS = {}  # group name -> (View ID, group_views fields), from generate()
KEPT = {}  # group changed in BAW that the last generate() kept -> its fields the spec does not have


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


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text())
    errors = []
    app = spec.get("app", {})
    if not app.get("name"):
        errors.append("app.name is required")
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", app.get("acronym", "")):
        errors.append("app.acronym must be 2-8 upper-case letters or digits, starting with a letter")
    bo = spec.get("businessObject", {})
    for key in ("name", "variable"):
        if not IDENTIFIER.match(bo.get(key, "")):
            errors.append(f"businessObject.{key} must be an identifier")
    if not spec.get("service", {}).get("name"):
        errors.append("service.name is required")
    if spec.get("layout", "steps") not in ("steps", "tabs"):
        errors.append('layout must be "steps" (one screen per step) or "tabs" (one screen, a tab per step)')
    steps = spec.get("steps") or []
    if not steps:
        errors.append("steps must list at least one step")
    seen = {REFERENCE} if spec.get("confirmation") else set()
    process = spec.get("process")
    if process is not None:
        if not isinstance(process, dict) or not process.get("name"):
            errors.append("process.name is required (the workflow's name)")
        elif process.get("approval") is not None and not isinstance(process["approval"], dict):
            errors.append('process.approval must be an object, e.g. {"name": "Review", "lane": "Underwriting"}')
        elif process.get("approval") is not None:
            seen |= {DECISION, COMMENTS}
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
        for f in g.get("fields", []):
            errors += field_errors(where, f, seen)
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
                errors += field_errors(f"step {i}", f, seen)
    for name in groups:
        if name not in used:
            errors.append(f"group {name!r} is not placed in any step; place it in a section ({{\"group\": \"{name}\"}}) or remove it")
    errors += coach_theme.validate(spec, PROJECT)
    for name in (spec.get("confirmation") or {}).get("showFields", []):
        if name not in seen:
            errors.append(f"confirmation.showFields: unknown field {name!r}")
    if errors:
        raise SystemExit("Invalid app spec:\n  " + "\n  ".join(errors))
    return spec


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
    if f.get("type") in CHOICES:
        f["options"] = [o if isinstance(o, dict) else {"value": str(o), "label": str(o)} for o in f.get("options") or []]
        if not f["options"] or not all(o.get("value") for o in f["options"]):
            errors.append(f"{where}: field {name!r} ({f['type']}) needs options: a list of strings or {{\"value\", \"label\"}}")
    return errors


def fields(spec):
    """Every field once, in order; a group placed in several steps has its fields once."""
    out, seen = [], set()
    for f in (f for step in spec["steps"] for f in step["fields"]):
        if f["name"] not in seen:
            seen.add(f["name"])
            out.append(f)
    return out


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


def actions(lay, buttons):
    """buttons: (event, label, colour style P, D or W). Returns the layout item and {event: button item id}."""
    made = [(event, *lay.button(label, style)) for event, label, style in buttons]
    return widget(lay, "buttons", "Actions", children=[xml for _, _, xml in made], show_label=False, item_id="Action_Bar"), {e: i for e, i, _ in made}


def choices(f):
    """Single Select / Radio Button Group with a static list: name is the stored value, value the text shown."""
    if f.get("type") not in CHOICES:
        return []
    items = [{"name": o["value"], "value": o.get("label") or o["value"]} for o in f["options"]]
    return [("itemLookupMode", "L"), ("staticList", json.dumps(items))]


def input_view(lay, var, f, root="tw.local", item_id=None):
    kind = FIELD_TYPES[f.get("type", "String")][1]
    return lay.view(kind, f["label"], binding=f"{root}.{var}.{f['name']}", options=(REQUIRED if f.get("required") else []) + choices(f),
                    help=f.get("help", ""), item_id=item_id)


def group_field(lay, var, f):
    """A field inside a group View: bound through the group's data, its control ID is the field's name (field icons
    and Coach Designer use it), and unless it is required its visibility follows the group's option for it."""
    item = input_view(lay, var, f, root="tw.businessData", item_id=f["name"])
    return item if f.get("required") else group_views.bind_visibility(item, f["name"])


def group_fields(g):
    """(path, view kind, label, hideable) of a group's fields, as group_views takes them."""
    return [(f["name"], FIELD_TYPES[f.get("type", "String")][1], f["label"], not f.get("required")) for f in g["fields"]]


def place_group(lay, var, s, readonly=False):
    """A coach's placement of a group View: bound to the coach's object, with the section's hidden fields and,
    for read-only coaches, a read-only visibility that every field in the group follows."""
    view_id, gfields = GROUPS[s["group"]]
    if not (readonly or s.get("readonly")):
        lay.group_fields += [f for f in s["fields"] if f["name"] not in s.get("hide", [])]
    options = group_views.placement_options(gfields, s.get("hide", []), readonly or s.get("readonly", False))
    return lay.view("Group", s["group"], binding=f"tw.local.{var}", view_uuid=view_id, options=options, show_label=False)


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
    content = [place_group(lay, var, s)] if "group" in s else columns(lay, var, s["fields"], s.get("columns", 1), s.get("widths"))
    return widget(lay, "section", s["title"], children=content, options=[("intro", s.get("intro", ""))])


def sections(lay, var, step):
    return [section(lay, var, s) for s in step["sections"]]


def tab_content(lay, var, step):
    """A tab shows its fields directly, or a panel per section when the step names sections."""
    s = step["sections"][0]
    if s.get("implicit"):
        return columns(lay, var, s["fields"], s.get("columns", 1), s.get("widths"))
    return sections(lay, var, step)


def step_coach(spec, i):
    var, step, last = spec["businessObject"]["variable"], spec["steps"][i], i == len(spec["steps"]) - 1
    lay = Layout()
    forward = step.get("nextLabel") or ("Submit" if last and not spec.get("review", True) else "Next")
    buttons = ([(f"back{i}", step.get("backLabel") or "Back", "D")] if i else []) + [(f"next{i}", forward, "P")]
    buttons += [(f"cancel{i}", step["cancelLabel"], "W")] if step.get("cancelLabel") else []
    body = sections(lay, var, step)
    bar, events = actions(lay, buttons)
    count = f"Step {i + 1} of {len(spec['steps'])}: " if len(spec["steps"]) > 1 else ""
    return Layout.wrap([*header(spec, lay, count + step["title"], step.get("intro", "")), *body, bar]), events


def form_coach(spec):
    """layout "tabs": every step is a tab of one screen; Next leaves the screen."""
    var, form = spec["businessObject"]["variable"], spec.get("form") or {}
    lay = Layout()
    tabs = [lay.view("Vertical Layout", s["title"], children=tab_content(lay, var, s)) for s in spec["steps"]]
    body = lay.view("Tab Section", "Steps", children=tabs, show_label=False)
    buttons = [("next0", form.get("nextLabel") or ("Next" if spec.get("review", True) else "Submit"), "P")]
    buttons += [("cancel0", form["cancelLabel"], "W")] if form.get("cancelLabel") else []
    bar, events = actions(lay, buttons)
    return Layout.wrap([*header(spec, lay, form.get("title", spec["service"]["name"]), form.get("intro", "")), body, bar]), events


def output(lay, var, f):
    kind = FIELD_TYPES[f.get("type", "String")][1]
    binding = f"tw.local.{var}.{f['name']}"
    if kind in ("Text", "Text Area"):
        return lay.view("Output Text", f["label"], binding=binding)
    return lay.view(kind, f["label"], binding=binding, options=READ_ONLY + choices(f))


def read_only(lay, var, s, shown, spec):
    """A section on the Review coach: its group placed read-only, once (a group a step shows again for reference is
    skipped), hiding only the fields every placement hides; or an output per field."""
    if "group" not in s:
        return [output(lay, var, f) for f in s["fields"]]
    if s["group"] in shown:
        return []
    shown.add(s["group"])
    hides = [set(p.get("hide", [])) for step in spec["steps"] for p in step["sections"] if p.get("group") == s["group"]]
    return [place_group(lay, var, dict(s, hide=sorted(set.intersection(*hides))), readonly=True)]


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
    return Layout.wrap([*header(spec, lay, review.get("title", "Review and Submit"), intro, editable=False), *panels, bar]), events


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


def init_script(spec):
    var = spec["businessObject"]["variable"]
    lines = [f"tw.local.{var} = {{}};"]  # client-side scripts have no tw.object factory
    lines += [f"tw.local.{var}.{f['name']} = false;" for f in fields(spec) if f.get("type") == "Boolean"]
    if spec.get("confirmation"):
        lines.append(f'tw.local.{var}.{REFERENCE} = "";')
    if spec.get("process"):  # a process task gets the object from the process; start fresh only the first time
        return f"if (!tw.local.{var}) {{\n  " + "\n  ".join(lines) + "\n}"
    return "\n".join(lines)


def assign_script(spec):
    prefix = json.dumps(spec["confirmation"].get("referencePrefix", "REF-"))
    return f"tw.local.{spec['businessObject']['variable']}.{REFERENCE} = {prefix} + new Date().getTime().toString().slice(-8);"


def flow(spec):
    """Steps and sequence flows for coach_builder.coachflow."""
    review, confirm = spec.get("review", True), spec.get("confirmation")
    tabs = spec.get("layout") == "tabs"
    count = 1 if tabs else len(spec["steps"])  # coaches before the review
    steps = [("init", "Initialize", init_script(spec))]
    if tabs:
        steps.append(("s0", (spec.get("form") or {}).get("title", spec["service"]["name"]), form_coach(spec)))
    else:
        steps += [(f"s{i}", s["title"], step_coach(spec, i)) for i, s in enumerate(spec["steps"])]
    finish = "assign" if confirm else "end"
    flows = [("start", "init", None, "rightCenter", "leftCenter"), ("init", "s0", None, "rightCenter", "leftCenter")]
    for i in range(count):
        target = f"s{i + 1}" if i < count - 1 else ("review" if review else finish)
        flows.append((f"s{i}", target, f"next{i}", "rightCenter", "leftCenter"))
        if i:
            flows.append((f"s{i}", f"s{i - 1}", f"back{i}", "topCenter", "topCenter"))
    cancels = [0] if tabs and (spec.get("form") or {}).get("cancelLabel") else [] if tabs else [i for i, s in enumerate(spec["steps"]) if s.get("cancelLabel")]
    flows += [(f"s{i}", "end", f"cancel{i}", "bottomCenter", "bottomCenter") for i in cancels]
    if review:
        steps.append(("review", (review if isinstance(review, dict) else {}).get("title", "Review and Submit"), review_coach(spec)))
        flows += [("review", f"s{count - 1}", "backReview", "topCenter", "topCenter"), ("review", finish, "submit", "rightCenter", "leftCenter")]
    if confirm:
        steps += [("assign", "Assign reference", assign_script(spec)), ("confirm", confirm.get("title", "Submitted"), confirmation_coach(spec))]
        flows += [("assign", "confirm", None, "rightCenter", "leftCenter"), ("confirm", "end", "done", "rightCenter", "leftCenter")]
    return steps, flows


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


def approval_flow(spec):
    var = spec["businessObject"]["variable"]
    steps = [("init", "Initialize", f"if (!tw.local.{var}) {{ tw.local.{var} = {{}}; }}"),
             ("s0", spec["process"]["approval"].get("name") or "Review", approval_coach(spec)),
             ("ok", APPROVED, f"tw.local.{var}.{DECISION} = {json.dumps(APPROVED)};"),
             ("back", SENT_BACK, f"tw.local.{var}.{DECISION} = {json.dumps(SENT_BACK)};")]
    flows = [("start", "init", None, "rightCenter", "leftCenter"), ("init", "s0", None, "rightCenter", "leftCenter"),
             ("s0", "ok", "approve", "rightCenter", "leftCenter"), ("s0", "back", "sendBack", "bottomCenter", "leftCenter"),
             ("ok", "end", None, "rightCenter", "leftCenter"), ("back", "end", None, "rightCenter", "bottomCenter")]
    return steps, flows


def process_definition(spec, form, approval, bo_id):
    """The workflow as an extra .twx object (id, versionId, name, type, xml).
    form, approval: (service id, (input id, output id)); approval may be None."""
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
    else:
        nodes.append({"key": "end", "kind": "end", "name": "End", "lane": first_lane, "x": 300})
        flows.append({"from": "form", "to": "end"})
    pid, version = "25." + uid(), uid()
    return pid, version, proc["name"], "bpd", process_xml(pid, version, proc["name"], var, bo_id, lanes, nodes, flows, "generate_app", proc.get("description", ""))


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


def group_objects(spec, bo_id, base=None, replace=()):
    """The app's group Views, their Preview services and the visibility type their options use, as package objects;
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
    acronym, var = spec["app"]["acronym"], spec["businessObject"]["variable"]
    type_id, type_version, type_xml = group_views.visibility_type(acronym)
    objects = [(type_id, type_version, group_views.VISIBILITY_TYPE, "twClass", type_xml)]
    for g in spec["groups"]:
        lay = Layout("ns2")
        items = columns(lay, var, g["fields"], g.get("columns", 1), g.get("widths"), make=group_field)
        view_id, version, xml = group_views.group_view(acronym, g["name"], var, f"/{bo_id}", f"/{type_id}", group_fields(g), items, "generate_app")
        GROUPS[g["name"]] = (view_id, group_fields(g))
        kept = None if g["name"] in replace else kept_view(base, view_id, bo_id, {f["name"] for f in fields(spec)})
        if kept:
            version, xml, missing = kept
            KEPT[g["name"]] = missing
        objects.append((view_id, version, g["name"], "coachView", xml))
    for g in spec["groups"]:
        lay = Layout()
        body = widget(lay, "section", g["name"], children=[place_group(lay, var, {"group": g["name"], "fields": g["fields"]})])
        bar, events = actions(lay, [("ok", "OK", "P")])
        layout = Layout.wrap([*header(spec, lay, f"{g['name']} Preview", "The reusable group on its own."), body, bar])
        objects.append(group_views.preview_service(acronym, f"{g['name']} Preview", var, bo_id, layout, events["ok"], init_script(spec), "generate_app"))
    return objects


def generate(spec: dict, dest: Path, toolkit: Path, base: Path | None = None, replace_groups=()):
    """toolkit: the App Builder Widgets .twx (widget_toolkit.py build builder) the app is to depend on."""
    WIDGETS.clear()
    WIDGETS.update(widget_toolkit.view_ids(TOOLKIT, toolkit))
    bo, svc, app = spec["businessObject"], spec["service"], spec["app"]
    props = [(f["name"], FIELD_TYPES[f.get("type", "String")][0]) for f in fields(spec)]
    if spec.get("confirmation"):
        props.append((REFERENCE, "String"))
    proc = spec.get("process")
    approval = proc and proc.get("approval") is not None
    if approval:
        props += [(DECISION, "String"), (COMMENTS, "String")]
    bo_id = "12." + uid()
    extra = group_objects(spec, bo_id, base, replace_groups)
    steps, flows = flow(spec)
    service = {"name": svc["name"], "description": svc.get("description", svc["name"])}
    io = lambda: ("2055." + uid(), "2055." + uid()) if proc else None
    form_io = io()
    services = [("1." + uid(), uid(), form_io or "2056." + uid(), service,
                 lambda b, v: coachflow(service, steps, flows, b, v, bo["variable"], io=form_io))]
    if proc:
        approval_ids = None
        if approval:
            a_io, a_steps, a_flows = io(), *approval_flow(spec)
            a_service = {"name": proc["approval"].get("name") or "Review", "description": f"{proc['name']}: {proc['approval'].get('name') or 'Review'}",
                         "exposed": False}  # opened only as the process's approval task
            services.append(("1." + uid(), uid(), a_io, a_service, lambda b, v: coachflow(a_service, a_steps, a_flows, b, v, bo["variable"], io=a_io)))
            approval_ids = (services[-1][0], a_io)
        extra.append(process_definition(spec, (services[0][0], form_io), approval_ids, bo_id))
    write_twx(dest, {"name": app["name"], "acronym": app["acronym"], "snapshot": app.get("snapshot", "1.0.0")},
              {"id": bo_id, "version": uid(), "name": bo["name"], "props": props}, bo["variable"], services, "generate_app",
              app_template.read_base(base) if base else None, extra)
    with zipfile.ZipFile(dest) as twx:
        entries = {i.filename: twx.read(i) for i in twx.infolist()}
    package, _, add, drop = widget_toolkit.embed(entries["META-INF/package.xml"].decode("utf-8"), toolkit)
    entries["META-INF/package.xml"] = package.encode("utf-8")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in {**{n: d for n, d in entries.items() if n not in drop}, **add}.items():
            out.writestr(name, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", type=Path, help="App spec JSON (see app-specs/example-equipment-request.json)")
    parser.add_argument("dest", type=Path, help="Output .twx")
    parser.add_argument("--base", type=Path, help="An app exported from the target server, to match its BAW build; the app itself to add a snapshot to it")
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
    if spec.get("process"):
        proc = spec["process"]
        print(f"Process: {proc['name']}, task {(proc.get('formTask') or {}).get('name') or spec['service']['name']}"
              + (f", then approval task {proc['approval'].get('name') or 'Review'} (Send back returns to the first task)" if proc.get("approval") is not None else ""))


if __name__ == "__main__":
    main()
