#!/usr/bin/env python3
"""
Generate a complete, installable BAW process app (.twx) from an app spec (JSON).

The app holds one client-side human service, exposed as a URL, with one coach per step:

    Start -> Initialize -> Step 1 -> ... -> Step N -> Review -> Assign reference -> Confirmation -> End
                              Back buttons return to the previous step; Review is optional,
                              and so is the confirmation (with its generated reference number).

With "layout": "tabs" the steps become tabs of one form coach instead (Next goes to Review).

Every coach is built from standard UI Toolkit views bound to one business object, so the
result runs as soon as it is installed and can be inventoried and modernized like any app.

Packaging metadata and the System Data / UI Toolkit dependencies come from an exported base
app. When --base does not exist yet, the Hiring Sample (HSS) is exported from the server.

Example:
    python3 generate_app.py app-specs/example-equipment-request.json work/ZZEQ.twx
    python3 baw_ops.py install work/ZZEQ.twx
"""

import argparse
import json
import re
import tempfile
from pathlib import Path

from coach_builder import SYSTEM_TYPES, Layout, coachflow, uid, write_twx
from twx_clone import clone

FIELD_TYPES = {  # spec type -> (business object type, input view)
    "String": ("String", "Text"),
    "Text Area": ("String", "Text Area"),
    "Date": ("Date", "Date Time Picker"),
    "Boolean": ("Boolean", "Checkbox"),
    "Integer": ("Integer", "Integer"),
    "Decimal": ("Decimal", "Decimal"),
}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REFERENCE = "referenceNumber"
READ_ONLY = [("@visibility", '{"isResponsiveData":true,"values":[{"deviceConfigID":"LargeID","value":"READONLY"}]}')]
CSS = """
div.body { max-width: 960px; margin: 0 auto !important; padding: 16px 24px !important; }
.app-title { font-size: 22px; font-weight: 600; margin: 8px 0 4px 0; }
.app-intro { margin: 0 0 16px 0; color: #525252; }
.panel { margin-bottom: 16px !important; }
.Button.CoachView { flex: 0 0 auto !important; width: auto !important; margin-right: 8px; }
.btn { width: auto !important; }
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
    for i, step in enumerate(steps, 1):
        if not step.get("title"):
            errors.append(f"step {i}: title is required")
        if not step.get("fields"):
            errors.append(f"step {i}: fields must list at least one field")
        for f in step.get("fields", []):
            name = f.get("name", "")
            if not IDENTIFIER.match(name):
                errors.append(f"step {i}: field name {name!r} must be an identifier")
            elif name in seen:
                errors.append(f"step {i}: field name {name!r} is used twice (or is reserved)")
            seen.add(name)
            if f.get("type", "String") not in FIELD_TYPES:
                errors.append(f"step {i}: field {name!r} has unknown type {f.get('type')!r}; use one of {', '.join(FIELD_TYPES)}")
            if not f.get("label"):
                errors.append(f"step {i}: field {name!r} needs a label")
    for name in (spec.get("confirmation") or {}).get("showFields", []):
        if name not in seen:
            errors.append(f"confirmation.showFields: unknown field {name!r}")
    if errors:
        raise SystemExit("Invalid app spec:\n  " + "\n  ".join(errors))
    return spec


def fields(spec):
    return [f for step in spec["steps"] for f in step["fields"]]


# ---------------------------------------------------------------- coaches


def header(title, intro):
    return f'<style>{CSS}</style><div class="app-title">{title}</div>' + (f'<div class="app-intro">{intro}</div>' if intro else "")


def actions(lay, buttons):
    """buttons: (event, label, primary). Returns the layout item and {event: button item id}."""
    made = [(event, *lay.button(label, primary)) for event, label, primary in buttons]
    return lay.view("Horizontal Layout", "Actions", children=[xml for _, _, xml in made], show_label=False), {e: i for e, i, _ in made}


def input_views(lay, var, step):
    return [lay.view(FIELD_TYPES[f.get("type", "String")][1], f["label"], binding=f"tw.local.{var}.{f['name']}") for f in step["fields"]]


def inputs(lay, var, step):
    return lay.view("Panel", step["title"], children=input_views(lay, var, step))


def step_coach(spec, i):
    var, step, last = spec["businessObject"]["variable"], spec["steps"][i], i == len(spec["steps"]) - 1
    lay = Layout()
    forward = "Submit" if last and not spec.get("review", True) else "Next"
    buttons = ([(f"back{i}", "Back", False)] if i else []) + [(f"next{i}", forward, True)]
    bar, events = actions(lay, buttons)
    count = f"Step {i + 1} of {len(spec['steps'])}: " if len(spec["steps"]) > 1 else ""
    items = [lay.html(header(count + step["title"], step.get("intro", ""))), inputs(lay, var, step), bar]
    return Layout.wrap(items), events


def form_coach(spec):
    """layout "tabs": every step is a tab of one screen; Next leaves the screen."""
    var, form = spec["businessObject"]["variable"], spec.get("form") or {}
    lay = Layout()
    tabs = [lay.view("Vertical Layout", s["title"], children=input_views(lay, var, s)) for s in spec["steps"]]
    bar, events = actions(lay, [("next0", "Next" if spec.get("review", True) else "Submit", True)])
    items = [lay.html(header(form.get("title", spec["service"]["name"]), form.get("intro", ""))), lay.view("Tab Section", "Steps", children=tabs, show_label=False), bar]
    return Layout.wrap(items), events


def output(lay, var, f):
    kind = FIELD_TYPES[f.get("type", "String")][1]
    binding = f"tw.local.{var}.{f['name']}"
    if kind in ("Text", "Text Area"):
        return lay.view("Output Text", f["label"], binding=binding)
    return lay.view(kind, f["label"], binding=binding, options=READ_ONLY)


def review_coach(spec):
    var, review = spec["businessObject"]["variable"], spec.get("review")
    review = review if isinstance(review, dict) else {}
    lay = Layout()
    panels = [lay.view("Panel", s["title"], children=[output(lay, var, f) for f in s["fields"]]) for s in spec["steps"]]
    bar, events = actions(lay, [("backReview", "Back", False), ("submit", "Submit", True)])
    intro = review.get("intro", "Check your answers. Press Back to change them or Submit to send them.")
    items = [lay.html(header(review.get("title", "Review and Submit"), intro)), *panels, bar]
    return Layout.wrap(items), events


def confirmation_coach(spec):
    var, conf = spec["businessObject"]["variable"], spec["confirmation"]
    by_name = {f["name"]: f for f in fields(spec)}
    lay = Layout()
    outputs = [lay.view("Output Text", "Reference Number", binding=f"tw.local.{var}.{REFERENCE}")]
    outputs += [output(lay, var, by_name[n]) for n in conf.get("showFields", [])]
    bar, events = actions(lay, [("done", "Done", True)])
    items = [lay.html(header(conf.get("title", "Submitted"), conf.get("message", ""))), lay.view("Panel", "Summary", children=outputs), bar]
    return Layout.wrap(items), events


# ---------------------------------------------------------------- flow


def init_script(spec):
    var = spec["businessObject"]["variable"]
    lines = [f"tw.local.{var} = {{}};"]  # client-side scripts have no tw.object factory
    lines += [f"tw.local.{var}.{f['name']} = false;" for f in fields(spec) if f.get("type") == "Boolean"]
    if spec.get("confirmation"):
        lines.append(f'tw.local.{var}.{REFERENCE} = "";')
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
    if review:
        steps.append(("review", (review if isinstance(review, dict) else {}).get("title", "Review and Submit"), review_coach(spec)))
        flows += [("review", f"s{count - 1}", "backReview", "topCenter", "topCenter"), ("review", finish, "submit", "rightCenter", "leftCenter")]
    if confirm:
        steps += [("assign", "Assign reference", assign_script(spec)), ("confirm", confirm.get("title", "Submitted"), confirmation_coach(spec))]
        flows += [("assign", "confirm", None, "rightCenter", "leftCenter"), ("confirm", "end", "done", "rightCenter", "leftCenter")]
    return steps, flows


# ---------------------------------------------------------------- package


def ensure_base(base: Path) -> Path:
    """Export the Hiring Sample once; it supplies packaging metadata and the toolkit dependencies."""
    if not base.exists():
        from baw_ops import BawOps
        ops = BawOps()
        versions = [v for v in ops.get("/bas/ops/std/bpm/containers/HSS/versions")["versions"] if not v.get("archived")]
        base.parent.mkdir(parents=True, exist_ok=True)
        ops.export("HSS", versions[0]["version"], base)
        print(f"Exported base app HSS {versions[0]['version_name']} to {base}")
    return base


def generate(spec: dict, base: Path, dest: Path):
    bo, svc = spec["businessObject"], spec["service"]
    props = [(f["name"], FIELD_TYPES[f.get("type", "String")][0]) for f in fields(spec)]
    if spec.get("confirmation"):
        props.append((REFERENCE, "String"))
    steps, flows = flow(spec)
    service = {"name": svc["name"], "description": svc.get("description", svc["name"])}
    services = [("1." + uid(), uid(), "2056." + uid(), service, lambda b, v: coachflow(service, steps, flows, b, v, bo["variable"]))]
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "app.twx"
        write_twx(base, raw, {"id": "12." + uid(), "version": uid(), "name": bo["name"], "props": props}, bo["variable"], services, "generate_app")
        app = spec["app"]
        clone(raw, dest, app["name"], app["acronym"], app.get("snapshot", "1.0.0"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", type=Path, help="App spec JSON (see app-specs/example-equipment-request.json)")
    parser.add_argument("dest", type=Path, help="Output .twx")
    parser.add_argument("--base", type=Path, default=Path("work/base-HSS.twx"), help="Exported base app; exported from HSS when missing")
    args = parser.parse_args()
    spec = load_spec(args.spec)
    generate(spec, ensure_base(args.base), args.dest)
    app = spec["app"]
    print(f"Wrote {args.dest}: app {app['name']} ({app['acronym']}), snapshot {app.get('snapshot', '1.0.0')}")
    print(f"Service: {spec['service']['name']}, {len(spec['steps'])} step(s) as {'tabs' if spec.get('layout') == 'tabs' else 'screens'}, {len(fields(spec))} field(s)"
          + (", review" if spec.get("review", True) else "") + (", confirmation" if spec.get("confirmation") else ""))


if __name__ == "__main__":
    main()
