#!/usr/bin/env python3
"""
Add modernized copies of an app's client-side human services, driven by a coach spec.

For every service marked "modernize" in the spec (from coach_inventory.py), the service is
copied as "<name> (Modernized)", styled by the spec's theme file (see coach_theme.py).
In the copy, each coach's layout is rebuilt from Modernizer Widgets (widget_toolkit.py): a Theme,
a Header and an Error Summary, a Panel per section (or a Tab Section with a tab per section) holding
one field widget per spec field, bound to tw.local.<variable>.<path>, and the coach's own buttons
turned into Button widgets that keep their layout item IDs. The coach flow, its scripts and its
variables run unchanged, and the coach stays editable by drag and drop in Coach Designer. Views
the widgets cannot render ("native" in the spec) stay, after the sections.

A coach with "screen": "<name>" in the spec instead shows the hand-written screen registered under
that name (coach-ui/src/screens/) as one view; its original buttons move into a hidden layout and
the screen's buttons press them.

The output keeps the source app's identity. Pass --snapshot to install it as a new
snapshot of the same app, next to the original services. Coaches built from widgets need
--toolkit, the Modernizer Widgets snapshot (installed on the server) the app is to depend on.

Example:
    python3 server/coach_inventory.py zzeq.twx -o zzeq.coaches.json      # then review the spec
    python3 server/widget_toolkit.py build modernizer 1.1.0 work/MDW-1.1.0.twx   # install it once
    python3 server/modernize_coaches.py zzeq.twx zzeq.coaches.json zzeq-modern.twx --snapshot 1.1.0 --toolkit work/MDW-1.1.0.twx
    python3 server/baw_ops.py install zzeq-modern.twx
"""

import argparse
import json
import re
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, unescape

from coach_inventory import view_names
from coach_theme import load_theme
from coach_builder import SYSTEM_TYPES, VIEWS, Layout
from coach_views import screen_assets, screen_view
from twx_clone import UUID_RE
import app_template
import generate_app
import group_views
import widget_toolkit

SUFFIX = " (Modernized)"
PROJECT = Path(__file__).resolve().parent.parent
DESIGNER_NS = "http://www.ibm.com/bpm/CoachDesignerNG"
XSI_NS = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
SCREEN_ITEM, ACTIONS_ITEM = "CoachScreen1", "PPNativeActions"
SPEC_KEYS = ("path", "label", "type", "readonly", "required", "pattern", "message", "example", "options", "min", "max", "help", "events")
TOOLKIT = "modernizer"
GROUP_VIEWS = {}  # group name -> (View ID, group_views fields, fresh), from modernize()
ID_MAP = {}  # service id -> {old id: new id} for the ids its copy declares, from modernize()
REWIRED = []  # one line per process activity that now runs a copy, from modernize()
KEPT = []  # groups changed in BAW that the last modernize() kept as they are
UNRECOGNISED = []  # button event code the last modernize() copied as it was, for review
# The event code the generator writes for a Next button and for a finishing button's required-fields check.
NEXT_PANE = re.compile(r'page\.ui\.get\("[^"]+"\)\.setCurrentPane\((\d+)\);\s*return false;')


def generated_required_check():
    """The generator's required-fields check (generate_app.required_check) as a pattern for its whole code, so only that
    exact handler is dropped; code someone changed in BAW is copied and listed instead."""
    parts = generate_app.REQUIRED_CHECK.split("%s")
    switch = r'(?:  if \(first !== null\) page\.ui\.get\("[^"]+"\)\.setCurrentPane\(first\);\n)?'
    return re.compile(re.escape(parts[0]) + r"\[.*?\]" + re.escape(parts[1]) + re.escape(generate_app.REQUIRED_MESSAGE)
                      + re.escape(parts[2]) + re.escape(generate_app.REQUIRED_SUMMARY) + re.escape(parts[3]) + switch
                      + re.escape(parts[4]), re.S)


REQUIRED_CHECK = generated_required_check()


def uid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------- layout text surgery


def elements(text, p):
    """(start, end, viewId) for every layoutItem/contributions element, outermost first."""
    tag = re.compile(rf"<(/?){p}:(?:layoutItem|contributions)\b[^>]*?(/?)>")
    found, stack = [], []
    for m in tag.finditer(text):
        if m.group(1):
            start = stack.pop()
            item = re.search(rf"<{p}:layoutItemId>([^<]*)</{p}:layoutItemId>", text[start:m.end()])
            found.append((start, m.end(), item.group(1) if item else ""))
        elif not m.group(2):
            stack.append(m.start())
    return sorted(found)


def retag(xml, p, tag):
    """Use xml as a layoutItem (top level) or contributions (nested) element."""
    xml = re.sub(rf"^<{p}:(layoutItem|contributions)\b", f"<{p}:{tag}", xml)
    xml = re.sub(rf"</{p}:(layoutItem|contributions)>$", f"</{p}:{tag}>", xml)
    return xml if "xmlns:xsi=" in xml.split(">", 1)[0] else xml.replace(f"<{p}:{tag}", f"<{p}:{tag} {XSI_NS}", 1)


def config(p, options):
    """configData for (name, value) options; a third item "dynamic" makes the value a JavaScript expression."""
    return "".join(
        f"<{p}:configData><{p}:id>{uid()}</{p}:id><{p}:optionName>{name}</{p}:optionName>"
        + (f"<{p}:value>{escape(value)}</{p}:value>" if value else f"<{p}:value />")
        + (f"<{p}:valueType>dynamic</{p}:valueType>" if dynamic else "") + f"</{p}:configData>"
        for name, value, *dynamic in options)


def view_item(p, item_id, view_id, options, binding=None, children=None, tag="layoutItem"):
    """A view in a layout: tag is layoutItem at the top level (which carries the xsi namespace) and contributions inside a container."""
    xmlns = f" {XSI_NS}" if tag == "layoutItem" else ""
    xml = (f'<{p}:{tag}{xmlns} xsi:type="{p}:ViewRef" version="8550"><{p}:id>{uid()}</{p}:id>'
           f"<{p}:layoutItemId>{item_id}</{p}:layoutItemId>{config(p, options)}<{p}:viewUUID>{view_id}</{p}:viewUUID>")
    if binding:
        xml += f"<{p}:binding>{binding}</{p}:binding>"
    if children is not None:
        xml += f"<{p}:contentBoxContrib><{p}:id>{uid()}</{p}:id><{p}:contentBoxId>ContentBox1</{p}:contentBoxId>{''.join(children)}</{p}:contentBoxContrib>"
    return xml + f"</{p}:{tag}>"


def spec_keys():
    """The keys a field keeps in the layout spec: those above, then every option of a field widget in the contract."""
    options = (name for w in widget_toolkit.widgets(TOOLKIT).values() if w["binding"] for name, *_ in w["options"])
    return SPEC_KEYS + tuple(dict.fromkeys(name for name in options if name not in SPEC_KEYS))


def screen_spec(app, service, coach):
    keys = spec_keys()
    return {
        "app": app, "title": coach["title"], "intro": coach.get("intro", ""),
        "steps": [c["title"] for c in service["coaches"]], "step": service["coaches"].index(coach),
        "sectionStyle": coach["sectionStyle"],
        "sections": [{"title": s["title"], "fields": [{k: f[k] for k in keys if k in f} for f in s["fields"]],
                      **{k: s[k] for k in ("group", "readonly", "hide") if k in s}} for s in coach["sections"]],
        "buttons": [{k: b[k] for k in ("label", "viewId", "primary", "validate") if k in b} for b in coach["buttons"]],
    }


def section_variable(service, section):
    """(variable, classRef) of the business object a section shows: its own when the section carries them (a group
    placed by a service with several objects), else the service's."""
    return section.get("variable", service["variable"]), section.get("classRef", service["classRef"])


def screen_layout(old, p, coach, screen_view_id, actions_view_id, theme, variable, spec):
    """The single hand-written screen view, the coach's native items, and its own buttons in a hidden layout."""
    spans = elements(old, p)
    by_id = {vid: old[s:e] for s, e, vid in spans}
    screen = view_item(p, SCREEN_ITEM, screen_view_id, [
        ("@label", ""), ("@helpText", ""), ("@labelVisibility", "HIDE"),
        ("screen", coach["screen"]), ("theme", json.dumps(theme, separators=(",", ":"))), ("spec", json.dumps(spec, separators=(",", ":")))], binding=f"tw.local.{variable}")
    buttons = [retag(by_id[b["viewId"]], p, "contributions") for b in coach["buttons"] if b["viewId"] in by_id]
    actions = view_item(p, ACTIONS_ITEM, actions_view_id, [("@label", "Actions"), ("@helpText", ""), ("@labelVisibility", "HIDE")], children=buttons)
    native = [retag(by_id[n["viewId"]], p, "layoutItem") for n in coach["native"] if n["viewId"] in by_id]
    return screen + "".join(native) + actions


def item_ids(taken):
    """Readable layout item IDs, as Coach Designer names them (Text_Field1, Panel2), that the coach does not use yet."""
    counts = {}

    def next_id(name):
        while True:
            counts[name] = counts.get(name, 0) + 1
            item_id = f"{name.replace(' ', '_')}{counts[name]}"
            if item_id not in taken:
                taken.add(item_id)
                return item_id
    return next_id


def visibility(value):
    return json.dumps({"isResponsiveData": True, "values": [{"deviceConfigID": "LargeID", "value": value}]})


def field_widget(p, next_id, views, variable, field, root="tw.local", item_id=None):
    """One field widget bound to the business object (root tw.businessData inside a group View). Required and read-only
    become the view's own visibility, so Coach Designer shows and edits them like any view's; the other spec keys
    become the widget's options."""
    kind = "text" if field["type"] == "output" else field["type"]
    w = widget_toolkit.widgets(TOOLKIT)[kind]
    state = "READONLY" if field.get("readonly") or field["type"] == "output" else "REQUIRED" if field.get("required") else None
    options = [("@label", field["label"]), ("@helpText", field.get("help", "")), ("@labelVisibility", "SHOW")]
    options += [("@visibility", visibility(state))] if state else []
    for name, *_ in w["options"]:
        value = field.get(name)
        if name == "options" and value:
            value = [{"name": o.get("label") or o["value"], "value": o["value"]} for o in value]
        if value not in (None, "", []):
            options.append((name, widget_toolkit.option_text(value)))
    options += widget_events(w, field)
    return view_item(p, item_id or next_id(w["view"]), views[kind], options, binding=f"{root}.{variable}.{field['path']}", tag="contributions")


def widget_events(w, part):
    """The (event, code) options of a spec field or button: the handlers its widget has (the inventory carries them
    over from the view the widget replaces)."""
    events = part.get("events") or {}
    return [(name, events[name]) for name, *_ in w["events"] if (events.get(name) or "").strip()]


def button_events(w, b, tabs_id):
    """The (event, code) options of a button. The generator's Next code moves to the next tab of the modernized Tab
    Section, found with page.ui.get (bpmext.ui.getView does not see that control in the running coach); its
    required-fields check is dropped from a finishing button. Any other code is copied as it is and listed for review."""
    events = []
    for name, code in widget_events(w, b):
        pane = NEXT_PANE.fullmatch(code.strip())
        if pane and tabs_id:
            code = f'page.ui.get("{tabs_id}").setCurrentPane({pane.group(1)}); return false;'
        elif REQUIRED_CHECK.fullmatch(code.strip()) and b.get("role") == "finish":
            continue
        else:
            UNRECOGNISED.append(f"{b['label']}: {name}")
        events.append((name, code))
    return events


def widget_layout(old, p, coach, views, theme, service, spec):
    """The coach as Modernizer Widgets inside UI Toolkit containers: Theme, Header and Error Summary, the sections,
    the coach's native items, then its own buttons as Button widgets with their layout item IDs, which the coach
    flow's wiring names."""
    spans = elements(old, p)
    by_id = {vid: old[s:e] for s, e, vid in spans}
    next_id = item_ids(set(by_id))
    # A field widget keeps its old layout item ID, which handlers in the coach's event scripts reference, only while
    # that item's own binding (not a nested child's) is still the same variable path and no other item of the new
    # layout has taken the ID; otherwise field_widget mints a new one. screen_spec keeps every section and field of
    # the coach in order, so a spec field pairs with its old item by position: a path that repeats on one coach
    # keeps each field's own ID.
    view_ids = {id(f): raw.get("viewId") for s, r in zip(spec["sections"], coach["sections"])
                for f, raw in zip(s["fields"], r.get("fields", []))}
    variables = {id(s): section_variable(service, r)[0] for s, r in zip(spec["sections"], coach["sections"])}
    variables.update({id(f): variables[id(s)] for s in spec["sections"] for f in s["fields"]})
    used = {n["viewId"] for n in coach["native"]} | {b["viewId"] for b in coach["buttons"]}

    def field_id(f):
        vid = view_ids.get(id(f))
        own = by_id.get(vid, "").split(f"<{p}:contentBoxContrib>", 1)[0]
        bound = re.search(rf"<{p}:binding>([^<]*)</{p}:binding>", own)
        if vid and vid not in used and bound and bound.group(1) == f"tw.local.{variables[id(f)]}.{f['path']}":
            used.add(vid)
            return vid
        return None

    widget = lambda kind, options, tag="layoutItem": view_item(  # noqa: E731
        p, next_id(widget_toolkit.widgets(TOOLKIT)[kind]["view"]), views[kind], options, tag=tag)
    head = [
        widget("theme", [("theme", json.dumps(theme, separators=(",", ":")))]),
        widget("header", [("title", spec["title"]), ("subtitle", spec["app"]), ("intro", spec["intro"]),
                          ("steps", json.dumps(spec["steps"])), ("step", str(spec["step"]))]),
        widget("errors", []),
    ]
    sections = [s for s in spec["sections"] if s["fields"]]
    edits = {id(s): r["edit"]["label"] for s, r in zip(spec["sections"], coach["sections"]) if r.get("edit") and "group" in s}

    def fields(s):
        """The section's controls: its group or its fields, then its Edit button when the spec gives it one. Edit
        sets the group's visibility to editable, so it stays on the coach, validates nothing and has no boundary event."""
        if "group" not in s:
            return [field_widget(p, next_id, views, variables[id(s)], f, item_id=field_id(f)) for f in s["fields"]]
        group_id = next_id("Group")
        group = place_group(p, next_id, variables[id(s)], s, "contributions", item_id=group_id)
        if id(s) not in edits:
            return [group]
        unlock = f'bpmext.ui.getView("{group_id}").context.options._metadata.visibility.set("value","EDITABLE"); return false;'
        options = [("@label", edits[id(s)]), ("kind", "secondary"), ("validate", "false"), ("eventON_CLICK", unlock)]
        edit = view_item(p, next_id("Button"), views["button"], options, tag="contributions")
        row = view_item(p, next_id("Horizontal Layout"), VIEWS["Horizontal Layout"], [("@label", "Actions"), *hide], children=[edit], tag="contributions")
        # Side by side in a Panel, the group shrank to a narrow column beside its Edit button: Edit gets its own row
        # above the group, and a Vertical Layout gives the group the full width, as a tab does.
        return [view_item(p, next_id("Vertical Layout"), VIEWS["Vertical Layout"], [("@label", s["title"]), *hide], children=[row, group], tag="contributions")]

    hide = [("@helpText", ""), ("@labelVisibility", "HIDE")]
    tabbed = spec["sectionStyle"] == "tabs" and len(sections) > 1
    tabs_id = next_id("Tab Section") if tabbed else None
    native = [retag(by_id[n["viewId"]], p, "layoutItem") for n in coach["native"] if n["viewId"] in by_id]
    buttons = {}  # tab index (None: below the form) -> its buttons
    for b in coach["buttons"]:
        if b["viewId"] not in by_id:
            continue
        # A button's "type" names the boundary widget it becomes (default Button); it keeps the options that widget has.
        kind = b.get("type") or "button"
        w = widget_toolkit.widgets(TOOLKIT)[kind]
        names = {name for name, *_ in w["options"]}
        # Only a finishing button validates the form (the widgets check their own required fields); the others save,
        # go back or move between tabs without being blocked.
        validate = b["role"] == "finish" if b.get("role") else b.get("validate")
        options = {"kind": "primary" if b.get("primary") else "secondary", **({"validate": validate} if validate is not None else {}),
                   **({"tabIndex": b["tabIndex"]} if b.get("tabIndex") not in (None, "") else {})}
        options = {**{k: v for k, v in options.items() if k in names}, **dict(button_events(w, b, tabs_id))}
        item = retag(by_id[b["viewId"]], p, "contributions")
        # A button that sat in a tab stays in that tab, as on the classic coach; the others go below the form.
        tab = b.get("tab") if tabbed and b.get("tab") is not None and b["tab"] < len(sections) else None
        buttons.setdefault(tab, []).append(widget_toolkit.swap_view(item, b["viewId"], views[kind], options))

    def actions(tab):
        row = buttons.get(tab)
        return [view_item(p, next_id("Horizontal Layout"), VIEWS["Horizontal Layout"], [("@label", "Actions"), *hide], children=row, tag="contributions")] if row else []

    if tabbed:
        tabs = [view_item(p, next_id("Vertical Layout"), VIEWS["Vertical Layout"], [("@label", s["title"]), *hide],
                          children=fields(s) + actions(i), tag="contributions")
                for i, s in enumerate(sections)]
        body = [view_item(p, tabs_id, VIEWS["Tab Section"], [("@label", spec["title"]), *hide], children=tabs, binding=coach.get("tabBinding"))]
    else:
        body = [view_item(p, next_id("Panel"), VIEWS["Panel"], [("@label", s["title"]), ("@helpText", ""), ("@labelVisibility", "SHOW")], children=fields(s))
                if s["title"] else view_item(p, next_id("Vertical Layout"), VIEWS["Vertical Layout"], [("@label", ""), *hide], children=fields(s))
                for s in sections]
    bottom = [view_item(p, next_id("Horizontal Layout"), VIEWS["Horizontal Layout"], [("@label", "Actions"), *hide], children=buttons[None])] if buttons.get(None) else []
    return "".join(head + body + native + bottom)


# ---------------------------------------------------------------- groups


# Field kinds BAW loads as 0 or false when nothing was stored: a required one goes back to blank on a new form.
BLANKED_KINDS = ("number", "select", "radio")


def control_id(path):
    return path.replace(".", "_")


def group_fields(g):
    """(path, kind, label, hideable) of a group's fields, as group_views takes them; a required or read-only field
    keeps its own visibility."""
    return [(f["path"], f["type"], f["label"], not (f.get("required") or f.get("readonly") or f["type"] == "output")) for f in g["fields"]]


def place_group(p, next_id, variable, s, tag, item_id=None):
    """A coach's placement of a group View: bound to the coach's object, with the section's hidden fields and its
    read-only visibility, which every field in the group follows."""
    view_id, gfields, fresh = GROUP_VIEWS[s["group"]]
    options = [("@label", s["title"]), ("@helpText", ""), ("@labelVisibility", "HIDE")]
    options += group_views.placement_options(gfields, s.get("hide", []), s.get("readonly", False), fresh=fresh and not s.get("readonly", False))
    return view_item(p, item_id or next_id("Group"), view_id, options, binding=f"tw.local.{variable}", tag=tag)


def expand_groups(spec):
    """Give every section that names a group the group's fields, so the rest of the build sees them, and check the
    groups: known, placed, by services of one business object, not in a hand-written screen, hiding only optional
    fields. Returns {group name: (variable, classRef)}."""
    groups = {g.get("name"): g for g in spec.get("groups") or []}
    errors, users = [], {}
    for g in groups.values():
        if not g.get("name") or not g.get("fields"):
            errors.append(f"group {g.get('name')!r}: name and fields are required")
    for service in (s for s in spec["services"] if s.get("modernize")):
        for coach in service["coaches"]:
            for sec in coach["sections"]:
                if "group" not in sec:
                    continue
                where = f'coach "{coach["name"]}" ({service["name"]})'
                g = groups.get(sec["group"])
                if not g:
                    errors.append(f"{where}: unknown group {sec['group']!r}; groups: {', '.join(groups) or 'none'}")
                    continue
                if coach.get("screen"):
                    errors.append(f"{where} shows the hand-written screen {coach['screen']!r}, so it cannot place group {sec['group']!r}")
                optional = {path for path, _, _, hideable in group_fields(g) if hideable}
                errors += [f"{where}: group {sec['group']!r} cannot hide {path!r} (only its editable, not required fields)" for path in sec.get("hide", []) if path not in optional]
                users.setdefault(sec["group"], set()).add(section_variable(service, sec))
                sec.setdefault("title", sec["group"])
                sec["fields"] = g["fields"]
    for name, used in users.items():
        if any(not ref.startswith("/") for _, ref in used):
            errors.append(f"group {name!r}: its business object comes from a toolkit; a group needs one of the app's own")
        if len(used) > 1:
            errors.append(f"group {name!r} is placed by services of different business objects ({', '.join(v for v, _ in used)}); a group belongs to one")
    errors += [f"group {name!r} is not placed in any coach; place it in a section ({{\"group\": \"{name}\"}}) or remove it" for name in groups if name not in users]
    if errors:
        raise SystemExit("Invalid groups in the coach spec:\n  " + "\n  ".join(errors))
    return {name: next(iter(used)) for name, used in users.items()}


def preview_layout(name, g, variable, views, theme, app):
    """The Preview service's coach: Theme and Header widgets, the group in a Panel, an OK Button widget."""
    lay = Layout()
    widget = lambda kind, options, **kw: lay.view(kind.title(), "", view_uuid=views[kind], options=options, show_label=False, **kw)  # noqa: E731
    view_id, gfields, _ = GROUP_VIEWS[g["name"]]
    group = lay.view("Group", g["name"], binding=f"tw.local.{variable}", view_uuid=view_id, show_label=False)
    ok = lay.view("Button", "OK", view_uuid=views["button"], options=[("kind", "primary")], item_id="OK_Button", show_label=False)
    return Layout.wrap([
        widget("theme", [("theme", json.dumps(theme, separators=(",", ":")))]),
        widget("header", [("title", name), ("subtitle", app), ("intro", "The reusable group on its own."), ("steps", "[]"), ("step", "0")]),
        lay.view("Panel", g["name"], children=[group]),
        lay.view("Horizontal Layout", "Actions", children=[ok], show_label=False),
    ]), "OK_Button"


def group_objects(spec, package, owners, views, theme, twx, replace=()):
    """The group Views ("<group> (Modernized)") and their Preview services, and the visibility type unless the app has
    it already: package objects (id, version, name, type, xml). A group View the app has and someone changed in BAW
    stays as it is (listed in KEPT), unless its group is in replace. Fills GROUP_VIEWS."""
    GROUP_VIEWS.clear()
    KEPT.clear()
    replace = {n.removesuffix(SUFFIX) for n in replace}  # "<group> (Modernized)", as inspect_coaches names the View, works too
    unknown = sorted(replace - {g["name"] for g in spec["groups"]})
    if unknown:
        raise SystemExit(f"--replace-group names no group of the coach spec: {', '.join(unknown)}; groups: {', '.join(g['name'] for g in spec['groups'])}")
    acronym = app_template.target(package)["acronym"]
    type_id, type_version, type_xml = group_views.visibility_type(acronym)
    objects = [] if f'id="{type_id}"' in package else [(type_id, type_version, group_views.VISIBILITY_TYPE, "twClass", type_xml)]
    for g in spec["groups"]:
        variable, class_ref = owners[g["name"]]
        name = g["name"] + SUFFIX
        items = [field_widget("ns2", None, views, variable, f, root="tw.businessData", item_id=control_id(f["path"])) for f in g["fields"]]
        items = [group_views.bind_visibility(item, path) if hideable else item for item, (path, _, _, hideable) in zip(items, group_fields(g))]
        # One layout container holds the fields, so they lay out in the widgets' responsive columns, as in a section.
        items = [view_item("ns2", "Fields", VIEWS["Vertical Layout"], [("@label", ""), ("@helpText", ""), ("@labelVisibility", "HIDE")],
                           children=items, tag="contributions")]
        view_id, version, xml = group_views.group_view(acronym, name, variable, class_ref, f"/{type_id}", group_fields(g), items, "modernize_coaches",
                                                         blank_required=g.get("blankRequired", False),
                                                         fresh_ref=f"{system_data_ref(package)}/{SYSTEM_TYPES['Boolean']}" if g.get("fresh") else None,
                                                         blank_ids=[control_id(f["path"]) for f in g["fields"]
                                                                    if f.get("required") and f["type"] in BLANKED_KINDS])
        GROUP_VIEWS[g["name"]] = (view_id, group_fields(g), bool(g.get("fresh") and g.get("blankRequired")))
        current = f"objects/{view_id}.xml"
        if g["name"] not in replace and current in twx.namelist() and group_views.changed_in_baw(twx.read(current).decode("utf-8")):
            KEPT.append(g["name"])
            continue
        objects.append((view_id, version, name, "coachView", xml))
    for g in spec["groups"]:
        variable, class_ref = owners[g["name"]]
        name = f"{g['name']}{SUFFIX} Preview"
        layout, ok = preview_layout(name, g, variable, views, theme, spec.get("app", ""))
        init = f"tw.local.{variable} = {{}};"
        objects.append(group_views.preview_service(acronym, name, variable, class_ref.lstrip("/"), layout, ok, init, "modernize_coaches"))
    return objects


def add_objects(package, objects, entries, files):
    """Put package objects into the app: a new object gets an entry, one the app already has (a rebuild) gets the
    new version. Returns the package."""
    for oid, version, name, kind, xml in objects:
        files[f"objects/{oid}.xml"] = xml.encode("utf-8")
        if f'<object id="{oid}" ' in package:
            package = re.sub(rf'(<object id="{re.escape(oid)}" versionId=")[^"]+', rf"\g<1>{version}", package)
        else:
            entries.append(f'<object id="{oid}" versionId="{version}" name="{escape(name, {chr(34): "&quot;"})}" type="{kind}"/>')
    return package


# ---------------------------------------------------------------- service copies


def copy_service(text, service, app, theme, screen_view_id, actions_view_id, widget_views):
    p = re.search(rf'xmlns:(\w+)="{re.escape(DESIGNER_NS)}"', text).group(1)
    for coach in service["coaches"]:
        at = text.index(f'id="{coach["id"]}"')
        open_tag = re.compile(rf"<{p}:layout(?:\s[^>]*)?>").search(text, at)
        close = text.index(f"</{p}:layout>", open_tag.end())
        old, spec = text[open_tag.end():close], screen_spec(app, service, coach)
        layout = (screen_layout(old, p, coach, screen_view_id, actions_view_id, theme, service["variable"], spec) if coach.get("screen")
                  else widget_layout(old, p, coach, widget_views, theme, service, spec))
        text = text[:open_tag.end()] + layout + text[close:]
    name = escape(service["name"] + SUFFIX, {'"': "&quot;"})
    text = re.sub(r'(<process id="[^"]+" name=")[^"]*(")', rf"\g<1>{name}\g<2>", text, count=1)
    text = re.sub(r'(globalUserTask\b[^>]*?\bname=")[^"]*(")', rf"\g<1>{name}\g<2>", text, count=1)
    mapping = {u: uid() for u in declared_uuids(text)}
    text = UUID_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
    text = re.sub(r"<guid>[^<]*</guid>", lambda m: f"<guid>guid:{uid()}</guid>", text)
    pid = re.search(r'<process id="([^"]+)"', text).group(1)
    version = re.search(r"<versionId>([^<]+)</versionId>", text).group(1)
    return pid, version, name, text, mapping


def system_data_ref(package):
    """References into System Data use the app's own dependency ID for it, which differs per app."""
    deps = dict((short, dep) for dep, short in re.findall(r'<dependency [^>]*id="2069\.([^"]+)">\s*<project [^>]*shortName="([^"]+)"', package))
    if "TWSYS" not in deps:
        raise SystemExit("The app has no System Data (TWSYS) dependency in META-INF/package.xml")
    return deps["TWSYS"]


DECLARING_ELEMENTS = ("processId", "processParameterId", "processVariableId", "processItemId", "tWComponentId", "exitPointId",
                      "processLinkId", "versionId", "id", "localizationId")


def declared_uuids(text):
    """UUIDs the service file declares as its own (the process, its parameters, variables, flow objects, coaches, layout
    items, localization entries, versions): the copy gets fresh ones. Any other reference (business objects, Views,
    toolkit and system objects) is never declared here and stays."""
    declaring = rf'<(?:\w+:)?(?:{"|".join(DECLARING_ELEMENTS)})>(?:\d+\.)?({UUID_RE.pattern})<'
    attribute = rf'\bid="(?:\d+\.)?({UUID_RE.pattern})"'
    return set(re.findall(declaring, text)) | set(re.findall(attribute, text))


def check_field_types(services):
    """Every field of a coach built from widgets names a field widget of the contract (or output, shown read-only);
    one SystemExit lists all the others, so nothing is written from a spec that cannot be built."""
    allowed = sorted(k for k, w in widget_toolkit.widgets(TOOLKIT).items() if w["binding"]) + ["output"]
    bad = [f'  "{f.get("label") or f.get("path")}" in coach "{c["name"]}" ({s["name"]}): type {f.get("type")!r}'
           for s in services for c in s["coaches"] if not c.get("screen") for sec in c["sections"] for f in sec["fields"]
           if f.get("type") not in allowed]
    if bad:
        raise SystemExit("Unknown field types in the coach spec:\n" + "\n".join(bad) + f"\nAllowed types: {', '.join(allowed)}")


def rewire_processes(twx: zipfile.ZipFile, package: str, files: dict, ids: dict, copies: dict):
    """Point the process (BPD) activities that run a classic service at its copy. ids: classic service id -> {old id:
    new id} (ID_MAP); copies: classic service id -> name of its copy. The whole map of each service a BPD mentions is
    applied to the whole BPD text, so activity references, the escaped bpmn2 calledElement and the data-mapping
    parameter ids all follow. The BPD keeps its id and gets a new version, in its xml and in package.xml, like any
    edited object. Changed BPDs go into files; returns (package, one line per rewired activity).
    Fails if an old id survives outside the classic services, or a BPD reference has no object in the package."""
    lines, bpds = [], {}
    for name in sorted(n for n in twx.namelist() if re.fullmatch(r"objects/25\.[^/]+\.xml", n)):
        text = twx.read(name).decode("utf-8")
        used = [sid for sid in ids if sid.split(".", 1)[1] in text]
        if not used:
            continue
        mapping = {old: new for sid in used for old, new in ids[sid].items()}
        version = uid()
        rewired = UUID_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
        rewired = re.sub(r"<versionId>[^<]+</versionId>", f"<versionId>{version}</versionId>", rewired, count=1)
        bpd = name[len("objects/"):-len(".xml")]
        package = re.sub(rf'(<object id="{re.escape(bpd)}" versionId=")[^"]+', rf"\g<1>{version}", package)
        bpds[name] = rewired
        for activity, sid in re.findall(r"<name>([^<]*)</name>(?:(?!<name>).)*?<attachedActivityId>/([^<]+)</attachedActivityId>", text, re.S):
            if sid in copies:
                lines.append(f"{unescape(activity)} now runs {unescape(copies[sid])}")

    classic = {f"objects/{sid}.xml" for sid in ids}
    old = {u for name in classic for u in declared_uuids(twx.read(name).decode("utf-8"))}
    texts = {n: twx.read(n).decode("utf-8") for n in twx.namelist() if n.startswith("objects/") and n.endswith(".xml")}
    texts.update({n: d.decode("utf-8") for n, d in files.items() if n.startswith("objects/")})
    texts.update(bpds)
    for name, text in sorted(texts.items()):
        left = old & set(UUID_RE.findall(text))
        if left and name not in classic:
            raise SystemExit(f"{name} still holds {len(left)} old service or parameter id(s) after rewiring, e.g. {sorted(left)[0]}")
    for name, text in bpds.items():
        for ref in sorted(set(re.findall(r"<attachedActivityId>/([^<]+)</attachedActivityId>", text)) | set(re.findall(r'calledElement="([^"]+)"', text))):
            if f'<object id="{ref}"' not in package:
                raise SystemExit(f"{name} refers to {ref}, which is not an object of the package")
    files.update({n: t.encode("utf-8") for n, t in bpds.items()})
    return package, lines


def modernize(source: Path, spec: dict, bundle: Path, dest: Path, theme: dict, snapshot=None, toolkit: Path | None = None,
              replace_groups=(), rewire=True):
    """theme: a theme file loaded by coach_theme.load_theme. toolkit: the Modernizer Widgets .twx (widget_toolkit.py
    build) whose snapshot the app depends on; needed when a coach has no hand-written screen. rewire: also point the
    process activities that run a classic service at its copy (the classic services stay in the app)."""
    services = [s for s in spec["services"] if s["modernize"]]
    if not services:
        raise SystemExit("Nothing to modernize: no service in the spec has \"modernize\": true")
    owners = expand_groups(spec)
    screens = sorted({c["screen"] for s in services for c in s["coaches"] if c.get("screen")})
    built = any(not c.get("screen") for s in services for c in s["coaches"])
    if built and not toolkit:
        raise SystemExit("Coaches without a hand-written screen are built from Modernizer Widgets: pass --toolkit, "
                         "the toolkit .twx from widget_toolkit.py build (installed on the server)")
    check_field_types(services)
    with zipfile.ZipFile(source) as twx:
        package = twx.read("META-INF/package.xml").decode("utf-8")
        names = view_names(twx)
        actions_view_id = next(i for i, n in names.items() if n == "Horizontal Layout")
        objects, files, file_entries, views, widget_views, toolkit_files, stale = [], {}, [], {}, {}, {}, set()

        if built:
            package, _, toolkit_files, stale = widget_toolkit.embed(package, toolkit)
            widget_views = widget_toolkit.view_ids(TOOLKIT, toolkit)

        if screens:
            # Managed files: reuse the app's coach-screens.* files (new content, new version) so names stay unique.
            # pp-react.* files of apps modernized before the rename stay as they are: their PP React views still use them.
            existing = {}
            for aid, name in re.findall(r'<object id="(61\.[^"]+)" versionId="[^"]+" name="(coach-screens\.[a-z]+)" type="managedAsset"/>', package):
                asset_uuid = re.search(rf'<file path="([^"]+)" id="{re.escape(aid)}"/>', package).group(1)
                existing[name] = (aid, asset_uuid, uid())
                package = re.sub(rf'(<object id="{re.escape(aid)}" versionId=")[^"]+', rf"\g<1>{existing[name][2]}", package)
            script = (bundle / "coach-screens.js").read_text()
            missing = [name for name in screens if f'"{name}"' not in script]
            if missing:
                raise SystemExit(f"Screens not in the bundle: {', '.join(missing)}. Register them in coach-ui/src/screens/ and rebuild")
            asset_ids, entries, files = screen_assets(bundle, existing)
            objects = [e for e, _ in entries]
            file_entries = [f for _, f in entries if f]

            for ref in sorted({s["classRef"] for s in services if any(c.get("screen") for c in s["coaches"])}):
                bo = re.search(rf'<object id="{re.escape(ref.rsplit("/", 1)[-1])}" versionId="[^"]+" name="([^"]+)"', package)
                view_id, entry, view_files = screen_view(asset_ids, ref, f"{system_data_ref(package)}/{SYSTEM_TYPES['String']}",
                                                        name=f"Coach Screen ({bo.group(1) if bo else ref})")
                views[ref] = view_id
                objects.append(entry)
                files.update(view_files)

        if spec.get("groups"):
            package = add_objects(package, group_objects(spec, package, owners, widget_views, theme, twx, replace_groups), objects, files)

        created, copies = [], {}
        ID_MAP.clear()
        UNRECOGNISED.clear()
        for service in services:
            text = twx.read(f"objects/{service['id']}.xml").decode("utf-8")
            pid, version, name, xml, ids = copy_service(text, service, spec["app"], theme, views.get(service["classRef"]), actions_view_id, widget_views)
            ID_MAP[service["id"]] = ids
            objects.append(f'<object id="{pid}" versionId="{version}" name="{name}" type="process"/>')
            files[f"objects/{pid}.xml"] = xml.encode("utf-8")
            created.append(name)
            copies[service["id"]] = name

        package = package.replace("</objects>", "".join(f"\n        {o}" for o in objects) + "\n    </objects>", 1)
        REWIRED.clear()
        if rewire:
            package, lines = rewire_processes(twx, package, files, ID_MAP, copies)
            REWIRED.extend(lines)
        if file_entries:
            new_files = "".join(f"\n        {f}" for f in file_entries)
            package = (package.replace("</files>", new_files + "\n    </files>", 1) if "</files>" in package
                       else package.replace("<files/>", f"<files>{new_files}\n    </files>", 1))
        if snapshot:
            target, rest = package.split("</target>", 1)
            target = re.sub(r'<snapshot id="2064\.[^"]+" name="[^"]*" acronym="[^"]*"',
                            f'<snapshot id="2064.{uid()}" name="{escape(snapshot)}" acronym="{escape(snapshot)}"', target)
            package = target + "</target>" + rest

        files.update(toolkit_files)

        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            for info in twx.infolist():
                if info.filename == "META-INF/package.xml":
                    out.writestr(info.filename, package)
                elif info.filename not in files and info.filename not in stale:
                    out.writestr(info, twx.read(info.filename))
            for name, data in files.items():
                out.writestr(name, data)
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("twx", type=Path, help="Exported process app (the spec's source)")
    parser.add_argument("spec", type=Path, help="Coach spec from coach_inventory.py")
    parser.add_argument("dest", type=Path)
    parser.add_argument("--bundle", type=Path, default=PROJECT / "coach-ui" / "bundle",
                        help="Built bundle directory (npm run build in coach-ui/)")
    parser.add_argument("--theme", help="Theme file (default: the spec's theme)")
    parser.add_argument("--snapshot", help="Install as this new snapshot of the same app")
    parser.add_argument("--toolkit", type=Path, help="Modernizer Widgets .twx (widget_toolkit.py build) for coaches built from widgets")
    parser.add_argument("--replace-group", action="append", default=[], metavar="NAME",
                        help="Rebuild this group from the spec even if it was changed in BAW (repeatable)")
    parser.add_argument("--no-rewire", action="store_true",
                        help="Leave the process activities on the classic services (default: point them at the copies)")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    theme, errors = load_theme(args.theme or spec.get("theme"), PROJECT, "the coach spec's theme")
    if errors:
        raise SystemExit("Invalid theme:\n  " + "\n  ".join(errors))
    for name in modernize(args.twx, spec, args.bundle, args.dest, theme, args.snapshot, args.toolkit, args.replace_group,
                         not args.no_rewire):
        print(f"Added service: {name}")
    for line in REWIRED:
        print(f"Rewired: {line}")
    if KEPT:
        print(f"Changed in BAW, kept: {json.dumps(KEPT)}")
    for line in UNRECOGNISED:
        print(f"Event code copied as it was: {line}")
    print(f"Wrote {args.dest}")


if __name__ == "__main__":
    main()
