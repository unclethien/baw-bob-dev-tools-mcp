#!/usr/bin/env python3
"""
Inventory the coaches of an exported BAW process app (.twx) into an editable JSON spec.

For every client-side human service the spec lists its coaches in flow order. For
each coach it records the sections, the fields bound under the coach's business
object (label, path, type, read-only, required), the buttons and where they lead,
and anything the React form cannot render (kept native) or will leave out (dropped).

Coaches built from Modernizer Widgets (modernize_coaches.py) are read back the same way: field widgets
as fields with their options, Panels and Tab Sections as sections, the Header's title and intro, and
Button widgets as buttons. Such a service is not offered for modernizing again. In coaches built from
App Builder Widgets (generate_app.py), Sections and Review Lists are sections, the App Header gives the
coach's intro, and the Button Bar holds the buttons.

Reusable groups that Bob built (group_views.py: Views carrying its fingerprint) are read back too; other composite
Views stay native, as before. The spec lists the groups the services to modernize place ("groups", each with its fields), and a coach's
placement of a group becomes a section {"title", "group", "readonly", "hide"}: the group's fields are listed once, under
"groups", so one edit there changes every placement. "groupCandidates" lists the sections whose fields (at least three)
appear again on another coach: groups Bob can propose.

With --previous, the edits made to an earlier coach spec of the app (its labels, types, help, titles, theme and the
rest) are carried onto the new one. An edit is what that spec says and a fresh inventory of its "source" .twx does
not; it is matched by keys a rebuild keeps (service, coach, field path, group, button). When the app changed the same
value since, the app's value stays and the edit is reported; edits whose field, coach or group is gone are reported too.

Review the spec before running modernize_coaches.py. Fix labels, mark fields
"required" or give them a "pattern" (a regular expression), a "message" and an
"example" (shown as the placeholder, and typed by verify-service.mjs --fill), set
"modernize" to false for services to skip, set "intro" for a coach's lead text, and set "theme" to
the app's theme file (*.theme.json, see coach_theme.py).

Example:
    python3 server/coach_inventory.py zzeq.twx -o zzeq.coaches.json
    python3 server/coach_inventory.py work/ZZEQ-1.0.3.twx -o work/ZZEQ-1.0.3.coaches.json --previous work/ZZEQ-1.0.1.coaches.json
"""

import argparse
import html
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import group_views
from app_template import SYSTEM_VIEWS
from widget_toolkit import ui_toolkit_names, widget_kinds, widgets

XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
FIELD_TYPES = {
    "Text": "text", "Text Area": "textarea", "Date Time Picker": "date", "Checkbox": "checkbox", "Switch": "checkbox",
    "Output Text": "output", "Integer": "number", "Decimal": "number",
    "Single Select": "select", "Radio Button Group": "radio",
}
CHOICE_VIEWS = {"Single Select", "Radio Button Group"}
WIDGETS = widget_kinds("modernizer")  # view ID -> kind
BUILDER = widget_kinds("builder")
CONTRACT = widgets("modernizer")
FIELD_WIDGETS = {kind for kind, w in CONTRACT.items() if w["binding"]}  # widgets that bind one value
# Field widgets with a list of choices: their option "options" holds NameValuePair items.
CHOICE_WIDGETS = {kind for kind in FIELD_WIDGETS
                  if any((name, type_, is_list) == ("options", "NameValuePair", True) for name, _, type_, is_list in CONTRACT[kind]["options"])}
SPEC_KEYS_FIRST = ("pattern", "message", "example", "min", "max")  # the order a spec has always listed these; other options follow
SPEC_RESERVED = {"path", "label", "type", "readonly", "required", "help", "options"}  # spec keys an option must not overwrite
# A UI Toolkit option whose value the widget takes under another name (the contract's uiToolkitNames). The widgets
# name their other options as the UI Toolkit does (tabIndex, selectAll, ...), so those carry over under their own
# name, and so do the event handlers.
UI_TOOLKIT_NAMES = ui_toolkit_names("modernizer")
SCREEN_VIEWS = ("Coach Screen (", "PP React ")  # the screen view, and its name in apps modernized before the rename
CONTAINERS = {"Panel", "Tab Section", "Vertical Layout", "Horizontal Layout", "Collapsible Panel", "Well"}
BACKWARD = re.compile(r"\b(back|previous|prev|cancel|close)\b", re.I)
SUFFIX = " (Modernized)"
MIN_CANDIDATE_FIELDS = 3
# Keys that identify or hold parts of a coach spec, or that the inventory derives: never carried as an edit.
NOT_EDITS = {"id", "name", "path", "viewId", "to", "fields", "sections", "coaches", "services", "buttons", "native", "dropped",
             "groups", "groupViews", "groupCandidates", "source", "app", "acronym", "snapshot", "variable", "classRef", "reason", "objects", "tabBinding", "edit", "role", "blankRequired", "fresh", "tab"}
GONE = object()  # a key the edit removed


def local(tag):
    return tag.rsplit("}", 1)[-1]


def children(el, name):
    return [c for c in el if local(c.tag) == name]


def first(el, name):
    return next((c for c in el.iter() if local(c.tag) == name), None)


def view_names(twx: zipfile.ZipFile):
    """Coach View ID -> name, for the app's own views and those in its toolkits.
    The system toolkits' views come from app_template when the app was exported without them."""
    names = dict(SYSTEM_VIEWS)

    def scan(z):
        for n in z.namelist():
            if n.startswith("objects/64."):
                m = re.search(rb'<coachView id="([^"]+)" name="([^"]+)"', z.read(n)[:1000])
                if m:
                    names[m.group(1).decode()] = m.group(2).decode()

    scan(twx)
    for n in twx.namelist():
        if n.startswith("toolkits/") and n.endswith(".zip"):
            with twx.open(n) as f, zipfile.ZipFile(f) as tk:
                scan(tk)
    return names


def humanize(path):
    word = path.rsplit(".", 1)[-1]
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", word).replace("_", " ").strip().title()


class CoachReader:
    """Turns one coach layout into sections, buttons, native and dropped items."""

    def __init__(self, names, groups=None):
        self.names = names
        self.groups = groups or {}  # group View ID -> group (read_groups)

    def item(self, el):
        config = {}
        for c in children(el, "configData"):
            value = next((v.text for v in children(c, "value")), None)
            config[next(o.text for o in children(c, "optionName"))] = value
        kind = (el.get(XSI_TYPE) or "").rsplit(":", 1)[-1]
        view_id = next((v.text for v in children(el, "viewUUID")), "")
        view = "Custom HTML" if kind == "CustomHTML" else self.names.get(view_id, "")
        kids = [k for box in children(el, "contentBoxContrib") for k in children(box, "contributions")]
        return {
            "viewId": next((v.text for v in children(el, "layoutItemId")), ""),
            "viewUUID": view_id,
            "view": view or "unknown view",
            "widget": WIDGETS.get(view_id),
            "builder": BUILDER.get(view_id),
            "config": config,
            "label": (config.get("@label") or "").strip(),
            "visibility": config.get("@visibility") or "",
            "colorStyle": config.get("colorStyle") or "",
            "options": widget_options(config) if WIDGETS.get(view_id) in CHOICE_WIDGETS else static_options(config),
            "binding": next((b.text for b in children(el, "binding")), "") or "",
            "children": kids,
        }

    def read(self, layout):
        self.sections = [{"title": "", "fields": []}]
        self.buttons, self.native, self.dropped, self.leaves = [], [], [], []
        self.tabs, self.header, self.widgets, self.tab_binding, self.tab = False, {}, False, "", 0
        self.edit = ""  # label of the Edit button of the Section that wraps what is being read
        self.hint = None  # title of the Panel or Section that wraps what is being read, for a group placed in it
        for el in [c for c in layout if local(c.tag) == "layoutItem"]:
            self.walk(el, top=True)
        return self

    def section(self, title):
        if self.sections[-1]["fields"] or self.sections[-1]["title"]:
            self.sections.append({"title": title, "fields": []})
        else:
            self.sections[-1]["title"] = title

    def columns(self, kids, in_tabs):
        """Side-by-side columns: list their fields row by row, the order people read them."""
        section = self.sections[-1]
        runs = []
        for kid in kids:
            start = len(section["fields"])
            self.walk(kid, in_tabs=in_tabs)
            runs.append(section["fields"][start:])
        if self.sections[-1] is section:  # no panel inside the columns started a new section
            flat = [f for run in runs for f in run]
            rows = [run[i] for i in range(max(map(len, runs))) for run in runs if i < len(run)]
            section["fields"][len(section["fields"]) - len(flat):] = rows

    def place(self, it):
        """A placement of a group: its own section, holding the group's fields bound under the placement's variable."""
        g = self.groups[it["viewUUID"]]
        variable = it["binding"][len("tw.local."):]
        section, title = self.sections[-1], self.hint or it["label"] or g["base"]
        if section["fields"] or section.get("group"):
            self.sections.append({"title": title, "fields": []})
            section = self.sections[-1]
        else:  # the title of its own Section or Panel, not of a tab or Review panel around several groups
            section["title"] = title
        section["group"], section["variable"] = g["base"], variable
        if "READONLY" in it["visibility"]:
            section["readonly"] = True
            if self.edit:
                section["edit"] = {"label": self.edit}
        hide = [g["optionPaths"][k] for k, v in it["config"].items() if v == "NONE" and k in g["optionPaths"]]
        if hide:
            section["hide"] = hide
        for f in g["items"]:
            leaf = dict(f, binding=f"tw.local.{variable}.{f['path']}", group=g["base"])
            self.leaves.append(leaf)
            section["fields"].append(leaf)
        self.sections.append({"title": "", "fields": []})  # what follows the group is not part of it

    def walk(self, el, top=False, in_tabs=False):
        it = self.item(el)
        if it["viewUUID"] in self.groups and it["binding"].startswith("tw.local.") and it["binding"].count(".") == 2:
            return self.place(it)
        view = it["view"]
        self.widgets = self.widgets or bool(it["widget"])
        if it["widget"] in ("theme", "errors") or it["builder"] == "theme":
            return
        if it["widget"] == "header":
            self.header = it["config"]
        elif it["builder"] == "header":
            self.header = {"intro": it["config"].get("intro")}
        elif view == "Button" or (it["widget"] in CONTRACT and CONTRACT[it["widget"]]["boundary"]):
            self.buttons.append(dict(it, tab=self.tab) if in_tabs else it)
        elif view == "Custom HTML":
            self.dropped.append(f'{it["viewId"]} (Custom HTML)')
        elif view in CONTAINERS or it["children"]:
            outer, outer_edit = self.hint, self.edit
            if it["builder"] == "section":
                self.edit = it["config"].get("editLabel") or ""
            if (view in ("Panel", "Collapsible Panel", "Well") or it["builder"] == "section") and it["label"]:
                self.hint = it["label"]
            elif view == "Tab Section" or it["builder"] == "review":
                # A review panel around one group names it (the step's title); around several, each keeps its own.
                self.hint = it["label"] if it["builder"] == "review" and it["label"] and len(it["children"]) == 1 else None
            if view == "Tab Section":
                self.tabs, self.tab_binding = True, it["binding"] or self.tab_binding
                if (it["config"].get("eventON_TABCHANGE") or "").strip():  # e.g. the generator's form.tabsInOrder check
                    self.dropped.append(f'{it["viewId"]} (Tab Section "On Tab changed" handler: the modernized tabs do not keep '
                                        'the user on a tab until its required fields are filled)')
                for self.tab, kid in enumerate(it["children"]):
                    self.section(self.item(kid)["label"])
                    self.walk(kid, in_tabs=True)
                self.section("")
            elif view == "Horizontal Layout" and len(it["children"]) > 1 and all(self.item(k)["view"] == "Vertical Layout" for k in it["children"]):
                self.columns(it["children"], in_tabs)
            elif not it["children"]:
                self.dropped.append(f'{it["viewId"]} (empty {view} "{it["label"]}")')
            elif (view in ("Panel", "Collapsible Panel", "Well") or it["builder"] in ("section", "review")) and it["label"] and not in_tabs:
                self.section(it["label"])
                for kid in it["children"]:
                    self.walk(kid)
                self.section("")
            else:
                for kid in it["children"]:
                    self.walk(kid, in_tabs=in_tabs)
            self.hint, self.edit = outer, outer_edit
        elif it["binding"].startswith("tw.local."):
            self.leaves.append(it)
            self.sections[-1]["fields"].append(it)
        else:
            self.dropped.append(f'{it["viewId"]} ({view}{", no binding" if not it["binding"] else ""})')


def static_options(config):
    """A select's or radio group's fixed items as [{value, label}]; None when they come from a service or variable."""
    if config.get("itemLookupMode") != "L" or not config.get("staticList"):
        return None
    try:
        return [{"value": i["name"], "label": i.get("value") or i["name"]} for i in json.loads(config["staticList"])]
    except (ValueError, KeyError, TypeError):
        return None


def widget_options(config):
    """A Select or Radio Group widget's items, a JSON list of NameValuePair (name shown, value stored), as [{value, label}]."""
    try:
        items = json.loads(config.get("options") or "[]")
        return [{"value": i["value"], "label": i.get("name") or i["value"]} for i in items] or None
    except (ValueError, KeyError, TypeError):
        return None


def option_value(value):
    """A layout option's value; a responsive one (a value per screen size) as its value on large screens."""
    if not (value or "").startswith('{"isResponsiveData"'):
        return value
    try:
        values = json.loads(value)["values"]
        return next((v["value"] for v in values if v.get("deviceConfigID") == "LargeID"), values[0]["value"] if values else None)
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def widget_config(it):
    """A view's options under the names of the widget that replaces it: a Modernizer widget's own, a UI Toolkit
    control's with UI_TOOLKIT_NAMES applied."""
    if it["widget"]:
        return it["config"]
    return {UI_TOOLKIT_NAMES.get(k, k): option_value(v) for k, v in it["config"].items() if not k.startswith("@")}


def widget_events(config, kind):
    """The event handlers in a view's options that the widget of this kind has: {event: code}."""
    return {name: config[name] for name, *_ in CONTRACT[kind]["events"] if (config.get(name) or "").strip()}


def renderable(it):
    """A widget renders this view: a field widget, a known input, and a select or radio group only with fixed items."""
    if it["widget"]:
        return it["widget"] in FIELD_WIDGETS
    return it["view"] in FIELD_TYPES and (it["view"] not in CHOICE_VIEWS or bool(it["options"]))


def widget_spec_keys(kind):
    """The options of a field widget that are spec keys: every option its contract declares, except the choice list
    (read from the items) and those the spec uses for something else."""
    names = [name for name, *_ in CONTRACT[kind]["options"] if name != "options" and name not in SPEC_RESERVED]
    return sorted(names, key=lambda n: SPEC_KEYS_FIRST.index(n) if n in SPEC_KEYS_FIRST else len(SPEC_KEYS_FIRST))


def field_spec(it, variable):
    path = it["binding"][len(f"tw.local.{variable}."):]
    kind = it["widget"] or FIELD_TYPES[it["view"]]
    spec = {"path": path, "label": it["label"] or humanize(path), "type": kind}
    if it["options"]:
        spec["options"] = it["options"]
    if it["viewId"]:
        spec["viewId"] = it["viewId"]
    widget = "text" if kind == "output" else kind
    config = widget_config(it)
    spec.update({k: config[k] for k in widget_spec_keys(widget) if config.get(k)})
    if widget_events(config, widget):
        spec["events"] = widget_events(config, widget)
    if it["widget"] and (it["config"].get("@helpText") or "").strip():
        spec["help"] = it["config"]["@helpText"].strip()
    if kind == "output" or "READONLY" in it["visibility"]:
        spec["readonly"] = True
    if "REQUIRED" in it["visibility"]:
        spec["required"] = True
    return spec


def flow_order(task):
    """Nodes reachable from the start event, breadth first, flows in document order."""
    flows = [f for f in task if local(f.tag) == "sequenceFlow"]
    start = next(n.get("id") for n in task if local(n.tag) == "startEvent")
    order, queue = [], [start]
    while queue:
        node = queue.pop(0)
        if node in order:
            continue
        order.append(node)
        queue += [f.get("targetRef") for f in flows if f.get("sourceRef") == node]
    return order


def flow_target(nodes, flows, start):
    """Where the flow from a node goes before it comes back to a coach: ("draft", None) when it reaches the Postpone Task event,
    ("coach", id) for the first coach it reaches, or ("end", None)."""
    seen, queue = set(), [start]
    while queue:
        node = queue.pop(0)
        if node in seen or node not in nodes:
            continue
        seen.add(node)
        if any(local(c.tag) == "postponeTaskEventDefinition" for c in nodes[node]):
            return "draft", None
        if local(nodes[node].tag) == "formTask":
            return "coach", node
        queue += [f.get("targetRef") for f in flows if f.get("sourceRef") == node]
    return "end", None


def inventory_service(root, names, groups=None):
    process = root.find("process")
    task = first(process, "userTaskImplementation")
    if task is None:
        return None
    nodes = {n.get("id"): n for n in task}
    forms = [nodes[i] for i in flow_order(task) if i in nodes and local(nodes[i].tag) == "formTask"]
    if not forms:
        return None
    variables = {v.get("name"): v.findtext("classId") for v in process.findall("processVariable") + process.findall("processParameter")}
    flows = [f for f in task if local(f.tag) == "sequenceFlow"]
    service = {"id": process.get("id"), "name": process.get("name"), "modernize": True, "coaches": []}

    readers = []
    for form in forms:
        reader = CoachReader(names, groups).read(first(form, "layout"))
        readers.append((form, reader))
    react = [r for _, r in readers for leaf in r.leaves + r.native if leaf["view"].startswith(SCREEN_VIEWS)]
    react += [b for _, r in readers for b in r.dropped if any(name in b for name in SCREEN_VIEWS)]
    bound = [leaf for _, r in readers for leaf in r.leaves
             if (leaf["view"] in FIELD_TYPES or leaf["widget"]) and leaf["binding"].count(".") >= 3]
    counts = Counter(leaf["binding"].split(".")[2] for leaf in bound)
    own_counts = Counter(leaf["binding"].split(".")[2] for leaf in bound if "group" not in leaf)  # fields a group does not place
    built = any(r.widgets for _, r in readers)
    if react or built or not counts:
        service["modernize"] = False
        service["reason"] = ("already uses React screens" if react else "already built from Modernizer Widgets" if built
                             else "no fields bound to a business object")
    variable = (own_counts or counts).most_common(1)[0][0] if counts else ""
    service["variable"], service["classRef"] = variable, variables.get(variable, "")
    service["objects"] = [variable, *sorted(set(counts) - {variable})] if variable else []
    if len(own_counts) > 1 and service["modernize"]:
        names = ", ".join(f"tw.local.{name}" for name in sorted(own_counts))
        service["modernize"], service["reason"] = False, f"binds fields to several business objects ({names})"
    untyped = next((name for name in service["objects"] if not variables.get(name)), "")
    if untyped and service["modernize"]:
        service["modernize"], service["reason"] = False, f"no declared type for tw.local.{untyped}"
    previews = {f"{g['base']} Preview" for g in (groups or {}).values()} | {f"{g['base']}{SUFFIX} Preview" for g in (groups or {}).values()}
    if service["name"] in previews:
        service["modernize"], service["reason"] = False, "the Preview service of a reusable group"

    for form, reader in readers:
        native = []
        for section in reader.sections:
            kept = []
            for it in section["fields"]:
                # a group placement keeps its fields under its own variable, which may be another business object
                own = it["binding"].split(".")[2] if section.get("group") and it["binding"].count(".") >= 3 else variable
                if renderable(it) and it["binding"].startswith(f"tw.local.{own}."):
                    kept.append(field_spec(it, own))
                else:
                    native.append({"viewId": it["viewId"], "view": it["view"], "label": it["label"], "binding": it["binding"]})
            section["fields"] = kept
            if section.get("group"):
                section["classRef"] = variables.get(section["variable"], "")
        buttons = []
        for b in reader.buttons:
            target = next((nodes[f.get("targetRef")].get("name") for f in flows
                           if f.get("sourceRef") == form.get("id") and first(f, "coachEventPath") is not None
                           and first(f, "coachEventPath").text == b["viewId"] and f.get("targetRef") in nodes), "")
            if b["widget"]:
                primary = (b["config"].get("kind") or "").lower() in ("", "primary", "danger")
            else:
                primary = b["colorStyle"] == "P" or (b["colorStyle"] != "D" and not BACKWARD.search(b["label"]))
            button = {"label": b["label"] or b["viewId"], "viewId": b["viewId"], "primary": primary, "to": target or "(no flow: stays on the coach)",
                      **({"tab": b["tab"]} if "tab" in b else {})}  # the tab it sits in, on a coach with tabs
            ahead = next((f.get("targetRef") for f in flows if f.get("sourceRef") == form.get("id") and first(f, "coachEventPath") is not None
                          and first(f, "coachEventPath").text == b["viewId"]), "")
            where, coach = flow_target(nodes, flows, ahead) if ahead else ("coach", form.get("id"))
            order = [f.get("id") for f in forms]
            button["role"] = ("draft" if where == "draft" else "stay" if coach == form.get("id")
                              else "back" if coach in order and order.index(coach) < order.index(form.get("id")) else "finish")
            kind = b["widget"] if b["widget"] in CONTRACT else "button"
            if kind != "button":  # another boundary widget of the toolkit
                button["type"] = kind
            if b["widget"] and b["config"].get("validate") in ("true", "false"):
                button["validate"] = b["config"]["validate"] == "true"
            config = widget_config(b)
            if (config.get("tabIndex") or "").strip():
                button["tabIndex"] = config["tabIndex"]
            if widget_events(config, kind):
                button["events"] = widget_events(config, kind)
            buttons.append(button)
        if len(buttons) == 1 and not b["widget"]:  # a Button widget says whether it is primary
            buttons[0]["primary"] = True
        service["coaches"].append({
            "id": form.get("id"), "name": form.get("name"), "title": reader.header.get("title") or form.get("name"),
            "intro": reader.header.get("intro") or "",
            "sectionStyle": "tabs" if reader.tabs else "stack",
            "sections": [s for s in reader.sections if s["fields"]],
            "buttons": buttons, "native": native, "dropped": reader.dropped,
            **({"tabBinding": reader.tab_binding} if reader.tab_binding else {}),
        })
    return service


def read_groups(twx, package, names):
    """The group Views Bob built in the app (they carry its fingerprint): View ID -> {"name", "base" (without
    " (Modernized)"), "items" (its fields as coach items, in reading order, path relative to the View's data),
    "optionPaths" (visibility option -> path), "changedInBaw"}. Other composite Views are not groups."""
    groups = {}
    for oid, name in re.findall(r'<object id="(64\.[^"]+)" versionId="[^"]+" name="([^"]+)" type="coachView"/>', package):
        text = twx.read(f"objects/{oid}.xml").decode("utf-8")
        binding = group_views.binding_name(text)
        if group_views.read_fingerprint(text) is None or not binding or not group_views.layout_fields(text):
            continue
        # Read the View's layout as a coach whose object is its data, so columns come back row by row.
        layout = html.unescape(re.search(r"<layout>(.*?)</layout>", text, re.S).group(1))
        reader = CoachReader(names).read(ET.fromstring(layout.replace(f"tw.businessData.{binding}.", f"tw.local.{binding}.").encode()))
        items = [dict(it, path=it["binding"][len(f"tw.local.{binding}."):]) for s in reader.sections for it in s["fields"]]
        option_paths = {it["visibility"][len("tw.options."):]: it["path"] for it in items if it["visibility"].startswith("tw.options.")}
        groups[oid] = {"name": html.unescape(name), "base": html.unescape(name).removesuffix(SUFFIX), "items": items,
                       "optionPaths": option_paths, "changedInBaw": group_views.changed_in_baw(text), "variable": binding,
                       "blankRequired": "function blankRequired" in text, "fresh": "freshForm" in text}
    return groups


def group_candidates(services):
    """Sections of the services to modernize, not yet groups, with at least MIN_CANDIDATE_FIELDS fields that all appear
    on another coach of the same service (a form section and the Review that repeats it)."""
    found = []
    for s in (s for s in services if s["modernize"]):
        for c in s["coaches"]:
            for sec in c["sections"]:
                paths = [f["path"] for f in sec["fields"]]
                if "group" in sec or len(paths) < MIN_CANDIDATE_FIELDS or any(paths == f["fields"] for f in found):
                    continue
                again = [o["name"] for o in s["coaches"] if o is not c
                         and any(set(paths) <= {f["path"] for f in other["fields"]} for other in o["sections"])]
                if again:
                    found.append({"title": sec["title"] or c["name"], "service": s["name"], "fields": paths, "coaches": [c["name"], *again]})
    return found


def inventory(twx_path: Path):
    with zipfile.ZipFile(twx_path) as twx:
        package = twx.read("META-INF/package.xml").decode("utf-8")
        project = re.search(r'<project id="[^"]+" name="([^"]+)"[^>]* shortName="([^"]*)"', package)
        snapshot = re.search(r'<target>.*?<snapshot id="[^"]+" name="([^"]+)"', package, re.S)
        names = view_names(twx)
        groups = read_groups(twx, package, names)
        services = []
        for oid, typ in re.findall(r'<object id="(1\.[^"]+)" versionId="[^"]+" name="[^"]*" type="([^"]+)"/>', package):
            root = ET.fromstring(twx.read(f"objects/{oid}.xml"))
            if root.findtext("process/processType") == "10":
                service = inventory_service(root, names, groups)
                if service:
                    services.append(service)
    placed = {}
    for s in (s for s in services if s["modernize"]):
        for sec in (sec for c in s["coaches"] for sec in c["sections"] if sec.get("group")):
            placed.setdefault(sec["group"], dict(sec))
    bases = {g["base"]: g for g in groups.values()}
    candidates = group_candidates(services)
    for sec in (sec for s in services for c in s["coaches"] for sec in c["sections"] if sec.get("group")):
        del sec["fields"]  # listed once, under "groups"; modernize_coaches gives every placement the group's fields
    return {
        "source": twx_path.name, "app": project.group(1), "acronym": project.group(2), "snapshot": snapshot.group(1),
        "theme": None, "services": services,
        "groups": [{"name": name, "variable": sec["variable"], "classRef": sec["classRef"],
                    "blankRequired": bases.get(name, {}).get("blankRequired", False), "fresh": bases.get(name, {}).get("fresh", False),
                    "fields": sec["fields"]} for name, sec in placed.items()],
        "groupViews": [{"name": g["name"], "fieldCount": len(g["items"]), "changedInBaw": g["changedInBaw"]} for g in groups.values()],
        "groupCandidates": candidates,
    }


def parts(spec):
    """Every part of a coach spec an edit can change, by a key a rebuild keeps: {key: dict}. A key that repeats
    (a group placed twice on one coach) is numbered by its order."""
    found = {}

    def add(key, part):
        n = sum(1 for k in found if k[:len(key)] == key)
        found[key + ((n,) if n else ())] = part

    add(("app",), spec)
    for g in spec.get("groups") or []:
        for f in g.get("fields") or []:
            add(("group", g["name"], f["path"]), f)
    for s in spec.get("services") or []:
        add(("service", s["name"]), s)
        for c in s.get("coaches") or []:
            add(("coach", s["name"], c["name"]), c)
            for b in c.get("buttons") or []:
                add(("button", s["name"], c["name"], b["viewId"]), b)
            for sec in c.get("sections") or []:
                fields = [] if sec.get("group") else sec.get("fields") or []
                anchor = sec.get("group") or (fields[0]["path"] if fields else None)
                if anchor:
                    add(("section", s["name"], c["name"], anchor), sec)
                for f in fields:
                    add(("field", s["name"], c["name"], f["path"]), f)
    return found


def describe(key):
    kind, *rest = key
    return {"app": lambda: "the spec",
            "group": lambda: f'field "{rest[1]}" of group "{rest[0]}"',
            "service": lambda: f'service "{rest[0]}"',
            "coach": lambda: f'coach "{rest[1]}"',
            "button": lambda: f'button {rest[2]} on coach "{rest[1]}"',
            "section": lambda: f'section "{rest[2]}" on coach "{rest[1]}"',
            "field": lambda: f'field "{rest[2]}" on coach "{rest[1]}"'}[kind]()


def carry_over(spec, previous, base):
    """Apply to spec the edits made to previous, an earlier coach spec, against base, a fresh inventory of its source.
    Returns (number of values carried, values the app changed since and that stay, edits with nothing to go to)."""
    new, was = parts(spec), parts(base)
    carried, kept, unmatched = 0, [], []
    for key, old in parts(previous).items():
        before = was.get(key, {})
        edits = {k: old.get(k, GONE) for k in old.keys() | before.keys()
                 if k not in NOT_EDITS and old.get(k, GONE) != before.get(k, GONE)}
        if not edits:
            continue
        target = new.get(key)
        if target is None:
            unmatched.append(f"{describe(key)}: {', '.join(sorted(edits))}")
            continue
        for k, value in sorted(edits.items()):
            now = target.get(k, GONE)
            if now == value:
                continue
            if now != before.get(k, GONE):
                kept.append(f"{describe(key)}: {k}")
            elif value is GONE:
                del target[k]
                carried += 1
            else:
                target[k] = value
                carried += 1
    return carried, kept, unmatched


def summary(spec):
    lines = [f'{spec["app"]} ({spec["acronym"]} {spec["snapshot"]}): {len(spec["services"])} client-side human service(s)']
    # A group placed only by services that are not modernized is not under "groups"; its View still has the fields.
    sizes = {g["name"]: g.get("fieldCount", 0) for g in spec.get("groupViews") or []}
    sizes.update({g["name"]: len(g["fields"]) for g in spec.get("groups") or []})
    for s in spec["services"]:
        state = "modernize" if s["modernize"] else f'skip: {s["reason"]}'
        objects = ", ".join(f"tw.local.{o}" for o in s.get("objects") or [s["variable"]])
        lines.append(f'  {s["name"]} [{state}] binds {objects}')
        for c in s["coaches"]:
            fields = sum(len(sec["fields"]) if "fields" in sec else sizes.get(sec.get("group"), 0) for sec in c["sections"])
            buttons = ", ".join(f'{b["label"]} -> {b["to"]}' for b in c["buttons"])
            extra = f', {len(c["native"])} kept native' if c["native"] else ""
            groups = [sec["group"] + (" (read-only)" if sec.get("readonly") else "") for sec in c["sections"] if sec.get("group")]
            extra += f', groups: {", ".join(groups)}' if groups else ""
            lines.append(f'    {c["name"]}: {len(c["sections"])} section(s), {fields} field(s){extra}; buttons: {buttons or "none"}')
    for g in spec.get("groupViews", []):
        lines.append(f'  Group View {g["name"]}' + (" (changed in BAW since Bob built it)" if g["changedInBaw"] else ""))
    for c in spec.get("groupCandidates", []):
        lines.append(f'  Candidate group "{c["title"]}": {len(c["fields"])} fields on {", ".join(c["coaches"])}')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("twx", type=Path, help="Exported process app")
    parser.add_argument("-o", "--output", type=Path, help="Spec file to write (default: <twx name>.coaches.json)")
    parser.add_argument("--previous", type=Path, help="An earlier coach spec of the app whose edits to carry over")
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text()) if args.previous else None
    spec = inventory(args.twx)
    if previous:
        name = previous.get("source") or ""
        source = next((p for p in (args.previous.parent / name, Path(__file__).resolve().parent.parent / "work" / name)
                       if name and p.is_file()), None)
        if not source:
            raise SystemExit(f"{args.previous} came from {name or 'an unknown .twx'}, which is not next to it or in work/: "
                             "without it the edits cannot be told apart from what the app had")
        carried, kept, unmatched = carry_over(spec, previous, inventory(source))
    out = args.output or args.twx.with_suffix(".coaches.json")
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(summary(spec))
    if previous:
        print("Carried over: " + json.dumps({"from": str(args.previous), "values": carried, "appChangedSince": kept, "notFound": unmatched}))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
