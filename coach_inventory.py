#!/usr/bin/env python3
"""
Inventory the coaches of an exported BAW process app (.twx) into an editable JSON spec.

For every client-side human service the spec lists its coaches in flow order. For
each coach it records the sections, the fields bound under the coach's business
object (label, path, type, read-only, required), the buttons and where they lead,
and anything the React form cannot render (kept native) or will leave out (dropped).

Review the spec before running modernize_coaches.py. Fix labels, mark fields
"required" or give them a "pattern" (a regular expression), a "message" and an
"example" (shown as the placeholder, and typed by verify-service.mjs --fill), set
"modernize" to false for services to skip, and set "intro" for a coach's lead text.

Example:
    python3 coach_inventory.py zzeq.twx -o zzeq.coaches.json
"""

import argparse
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
FIELD_TYPES = {
    "Text": "text", "Text Area": "textarea", "Date Time Picker": "date", "Checkbox": "checkbox", "Switch": "checkbox",
    "Output Text": "output", "Integer": "number", "Decimal": "number",
    "Single Select": "select", "Radio Button Group": "radio",
}
CHOICE_VIEWS = {"Single Select", "Radio Button Group"}
CONTAINERS = {"Panel", "Tab Section", "Vertical Layout", "Horizontal Layout", "Collapsible Panel", "Well"}
BACKWARD = re.compile(r"\b(back|previous|prev|cancel|close)\b", re.I)


def local(tag):
    return tag.rsplit("}", 1)[-1]


def children(el, name):
    return [c for c in el if local(c.tag) == name]


def first(el, name):
    return next((c for c in el.iter() if local(c.tag) == name), None)


def view_names(twx: zipfile.ZipFile):
    """Coach View ID -> name, for the app's own views and those in its toolkits."""
    names = {}

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

    def __init__(self, names):
        self.names = names

    def item(self, el):
        config = {}
        for c in children(el, "configData"):
            value = next((v.text for v in children(c, "value")), None)
            config[next(o.text for o in children(c, "optionName"))] = value
        kind = (el.get(XSI_TYPE) or "").rsplit(":", 1)[-1]
        view = "Custom HTML" if kind == "CustomHTML" else self.names.get(next((v.text for v in children(el, "viewUUID")), ""), "")
        kids = [k for box in children(el, "contentBoxContrib") for k in children(box, "contributions")]
        return {
            "viewId": next((v.text for v in children(el, "layoutItemId")), ""),
            "view": view or "unknown view",
            "label": (config.get("@label") or "").strip(),
            "visibility": config.get("@visibility") or "",
            "colorStyle": config.get("colorStyle") or "",
            "options": static_options(config),
            "binding": next((b.text for b in children(el, "binding")), "") or "",
            "children": kids,
        }

    def read(self, layout):
        self.sections = [{"title": "", "fields": []}]
        self.buttons, self.native, self.dropped, self.leaves = [], [], [], []
        self.tabs = False
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

    def walk(self, el, top=False, in_tabs=False):
        it = self.item(el)
        view = it["view"]
        if view == "Button":
            self.buttons.append(it)
        elif view == "Custom HTML":
            self.dropped.append(f'{it["viewId"]} (Custom HTML)')
        elif view in CONTAINERS or it["children"]:
            if view == "Tab Section":
                self.tabs = True
                for kid in it["children"]:
                    self.section(self.item(kid)["label"])
                    self.walk(kid, in_tabs=True)
                self.section("")
            elif view == "Horizontal Layout" and len(it["children"]) > 1 and all(self.item(k)["view"] == "Vertical Layout" for k in it["children"]):
                self.columns(it["children"], in_tabs)
            elif not it["children"]:
                self.dropped.append(f'{it["viewId"]} (empty {view} "{it["label"]}")')
            elif view in ("Panel", "Collapsible Panel", "Well") and it["label"] and not in_tabs:
                self.section(it["label"])
                for kid in it["children"]:
                    self.walk(kid)
                self.section("")
            else:
                for kid in it["children"]:
                    self.walk(kid, in_tabs=in_tabs)
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


def renderable(it):
    """The React form renders this view: a known input, and a select or radio group only with fixed items."""
    return it["view"] in FIELD_TYPES and (it["view"] not in CHOICE_VIEWS or bool(it["options"]))


def field_spec(it, variable):
    path = it["binding"][len(f"tw.local.{variable}."):]
    kind = FIELD_TYPES[it["view"]]
    spec = {"path": path, "label": it["label"] or humanize(path), "type": kind}
    if it["options"]:
        spec["options"] = it["options"]
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


def inventory_service(root, names):
    process = root.find("process")
    task = first(process, "userTaskImplementation")
    if task is None:
        return None
    nodes = {n.get("id"): n for n in task}
    forms = [nodes[i] for i in flow_order(task) if i in nodes and local(nodes[i].tag) == "formTask"]
    if not forms:
        return None
    variables = {v.get("name"): v.findtext("classId") for v in process.findall("processVariable")}
    flows = [f for f in task if local(f.tag) == "sequenceFlow"]
    service = {"id": process.get("id"), "name": process.get("name"), "modernize": True, "coaches": []}

    readers = []
    for form in forms:
        reader = CoachReader(names).read(first(form, "layout"))
        readers.append((form, reader))
    react = [r for _, r in readers for leaf in r.leaves + r.native if leaf["view"].startswith("PP React")]
    react += [b for _, r in readers for b in r.dropped if "PP React" in b]
    counts = Counter(leaf["binding"].split(".")[2] for _, r in readers for leaf in r.leaves
                     if leaf["view"] in FIELD_TYPES and leaf["binding"].count(".") >= 3)
    if react or not counts:
        service["modernize"] = False
        service["reason"] = "already uses React screens" if react else "no fields bound to a business object"
    variable = counts.most_common(1)[0][0] if counts else ""
    service["variable"], service["classRef"] = variable, variables.get(variable, "")
    if variable and not service["classRef"]:
        service["modernize"], service["reason"] = False, f"no declared type for tw.local.{variable}"

    for form, reader in readers:
        native = []
        for section in reader.sections:
            kept = []
            for it in section["fields"]:
                if renderable(it) and it["binding"].startswith(f"tw.local.{variable}."):
                    kept.append(field_spec(it, variable))
                else:
                    native.append({"viewId": it["viewId"], "view": it["view"], "label": it["label"], "binding": it["binding"]})
            section["fields"] = kept
        buttons = []
        for b in reader.buttons:
            target = next((nodes[f.get("targetRef")].get("name") for f in flows
                           if f.get("sourceRef") == form.get("id") and first(f, "coachEventPath") is not None
                           and first(f, "coachEventPath").text == b["viewId"] and f.get("targetRef") in nodes), "")
            primary = b["colorStyle"] == "P" or (b["colorStyle"] != "D" and not BACKWARD.search(b["label"]))
            buttons.append({"label": b["label"] or b["viewId"], "viewId": b["viewId"], "primary": primary, "to": target or "(not wired)"})
        if len(buttons) == 1:
            buttons[0]["primary"] = True
        service["coaches"].append({
            "id": form.get("id"), "name": form.get("name"), "title": form.get("name"), "intro": "",
            "sectionStyle": "tabs" if reader.tabs else "stack",
            "sections": [s for s in reader.sections if s["fields"]],
            "buttons": buttons, "native": native, "dropped": reader.dropped,
        })
    return service


def inventory(twx_path: Path):
    with zipfile.ZipFile(twx_path) as twx:
        package = twx.read("META-INF/package.xml").decode("utf-8")
        project = re.search(r'<project id="[^"]+" name="([^"]+)"[^>]* shortName="([^"]*)"', package)
        snapshot = re.search(r'<target>.*?<snapshot id="[^"]+" name="([^"]+)"', package, re.S)
        names = view_names(twx)
        services = []
        for oid, typ in re.findall(r'<object id="(1\.[^"]+)" versionId="[^"]+" name="[^"]*" type="([^"]+)"/>', package):
            root = ET.fromstring(twx.read(f"objects/{oid}.xml"))
            if root.findtext("process/processType") == "10":
                service = inventory_service(root, names)
                if service:
                    services.append(service)
    return {
        "source": twx_path.name, "app": project.group(1), "acronym": project.group(2), "snapshot": snapshot.group(1),
        "brand": "", "themes": ["brand", "carbon"], "services": services,
    }


def summary(spec):
    lines = [f'{spec["app"]} ({spec["acronym"]} {spec["snapshot"]}): {len(spec["services"])} client-side human service(s)']
    for s in spec["services"]:
        state = "modernize" if s["modernize"] else f'skip: {s["reason"]}'
        lines.append(f'  {s["name"]} [{state}] variable tw.local.{s["variable"]}')
        for c in s["coaches"]:
            fields = sum(len(sec["fields"]) for sec in c["sections"])
            buttons = ", ".join(f'{b["label"]} -> {b["to"]}' for b in c["buttons"])
            extra = f', {len(c["native"])} kept native' if c["native"] else ""
            lines.append(f'    {c["name"]}: {len(c["sections"])} section(s), {fields} field(s){extra}; buttons: {buttons or "none"}')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("twx", type=Path, help="Exported process app")
    parser.add_argument("-o", "--output", type=Path, help="Spec file to write (default: <twx name>.coaches.json)")
    args = parser.parse_args()
    spec = inventory(args.twx)
    out = args.output or args.twx.with_suffix(".coaches.json")
    out.write_text(json.dumps(spec, indent=2) + "\n")
    print(summary(spec))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
