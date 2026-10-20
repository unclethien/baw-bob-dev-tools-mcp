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
from xml.sax.saxutils import escape

from coach_inventory import view_names
from coach_theme import load_theme
from coach_builder import SYSTEM_TYPES, VIEWS
from coach_views import screen_assets, screen_view
from twx_clone import UUID_RE, foreign_uuids
import widget_toolkit

SUFFIX = " (Modernized)"
PROJECT = Path(__file__).resolve().parent.parent
DESIGNER_NS = "http://www.ibm.com/bpm/CoachDesignerNG"
XSI_NS = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
SCREEN_ITEM, ACTIONS_ITEM = "CoachScreen1", "PPNativeActions"
SPEC_KEYS = ("path", "label", "type", "readonly", "required", "pattern", "message", "example", "options", "min", "max", "help")
TOOLKIT = "modernizer"


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
    return "".join(
        f"<{p}:configData><{p}:id>{uid()}</{p}:id><{p}:optionName>{name}</{p}:optionName>"
        + (f"<{p}:value>{escape(value)}</{p}:value>" if value else f"<{p}:value />") + f"</{p}:configData>"
        for name, value in options)


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


def screen_spec(app, service, coach):
    return {
        "app": app, "title": coach["title"], "intro": coach.get("intro", ""),
        "steps": [c["title"] for c in service["coaches"]], "step": service["coaches"].index(coach),
        "sectionStyle": coach["sectionStyle"],
        "sections": [{"title": s["title"], "fields": [{k: f[k] for k in SPEC_KEYS if k in f} for f in s["fields"]]} for s in coach["sections"]],
        "buttons": [{k: b[k] for k in ("label", "viewId", "primary", "validate") if k in b} for b in coach["buttons"]],
    }


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


def field_widget(p, next_id, views, variable, field):
    """One field widget bound to the business object. Required and read-only become the view's own visibility,
    so Coach Designer shows and edits them like any view's; the other spec keys become the widget's options."""
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
    return view_item(p, next_id(w["view"]), views[kind], options, binding=f"tw.local.{variable}.{field['path']}", tag="contributions")


def widget_layout(old, p, coach, views, theme, variable, spec):
    """The coach as Modernizer Widgets inside UI Toolkit containers: Theme, Header and Error Summary, the sections,
    the coach's native items, then its own buttons as Button widgets with their layout item IDs, which the coach
    flow's wiring names."""
    spans = elements(old, p)
    by_id = {vid: old[s:e] for s, e, vid in spans}
    next_id = item_ids(set(by_id))
    widget = lambda kind, options, tag="layoutItem": view_item(  # noqa: E731
        p, next_id(widget_toolkit.widgets(TOOLKIT)[kind]["view"]), views[kind], options, tag=tag)
    head = [
        widget("theme", [("theme", json.dumps(theme, separators=(",", ":")))]),
        widget("header", [("title", spec["title"]), ("subtitle", spec["app"]), ("intro", spec["intro"]),
                          ("steps", json.dumps(spec["steps"])), ("step", str(spec["step"]))]),
        widget("errors", []),
    ]
    sections = [s for s in spec["sections"] if s["fields"]]
    fields = lambda s: [field_widget(p, next_id, views, variable, f) for f in s["fields"]]  # noqa: E731
    hide = [("@helpText", ""), ("@labelVisibility", "HIDE")]
    if spec["sectionStyle"] == "tabs" and len(sections) > 1:
        tabs = [view_item(p, next_id("Vertical Layout"), VIEWS["Vertical Layout"], [("@label", s["title"]), *hide], children=fields(s), tag="contributions")
                for s in sections]
        body = [view_item(p, next_id("Tab Section"), VIEWS["Tab Section"], [("@label", spec["title"]), *hide], children=tabs)]
    else:
        body = [view_item(p, next_id("Panel"), VIEWS["Panel"], [("@label", s["title"]), ("@helpText", ""), ("@labelVisibility", "SHOW")], children=fields(s))
                if s["title"] else view_item(p, next_id("Vertical Layout"), VIEWS["Vertical Layout"], [("@label", ""), *hide], children=fields(s))
                for s in sections]
    native = [retag(by_id[n["viewId"]], p, "layoutItem") for n in coach["native"] if n["viewId"] in by_id]
    buttons = []
    for b in coach["buttons"]:
        if b["viewId"] not in by_id:
            continue
        options = {"kind": "primary" if b.get("primary") else "secondary", **({"validate": b["validate"]} if "validate" in b else {})}
        item = retag(by_id[b["viewId"]], p, "contributions")
        buttons.append(widget_toolkit.swap_view(item, b["viewId"], views["button"], options))
    actions = [view_item(p, next_id("Horizontal Layout"), VIEWS["Horizontal Layout"], [("@label", "Actions"), *hide], children=buttons)] if buttons else []
    return "".join(head + body + native + actions)


# ---------------------------------------------------------------- service copies


def copy_service(text, service, app, theme, screen_view_id, actions_view_id, widget_views, owned):
    p = re.search(rf'xmlns:(\w+)="{re.escape(DESIGNER_NS)}"', text).group(1)
    for coach in service["coaches"]:
        at = text.index(f'id="{coach["id"]}"')
        open_tag = re.compile(rf"<{p}:layout(?:\s[^>]*)?>").search(text, at)
        close = text.index(f"</{p}:layout>", open_tag.end())
        old, spec = text[open_tag.end():close], screen_spec(app, service, coach)
        layout = (screen_layout(old, p, coach, screen_view_id, actions_view_id, theme, service["variable"], spec) if coach.get("screen")
                  else widget_layout(old, p, coach, widget_views, theme, service["variable"], spec))
        text = text[:open_tag.end()] + layout + text[close:]
    name = escape(service["name"] + SUFFIX, {'"': "&quot;"})
    text = re.sub(r'(<process id="[^"]+" name=")[^"]*(")', rf"\g<1>{name}\g<2>", text, count=1)
    text = re.sub(r'(globalUserTask\b[^>]*?\bname=")[^"]*(")', rf"\g<1>{name}\g<2>", text, count=1)
    mapping = {u: uid() for u in owned}
    text = UUID_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
    text = re.sub(r"<guid>[^<]*</guid>", lambda m: f"<guid>guid:{uid()}</guid>", text)
    pid = re.search(r'<process id="([^"]+)"', text).group(1)
    version = re.search(r"<versionId>([^<]+)</versionId>", text).group(1)
    return pid, version, name, text


def system_data_ref(package):
    """References into System Data use the app's own dependency ID for it, which differs per app."""
    deps = dict((short, dep) for dep, short in re.findall(r'<dependency [^>]*id="2069\.([^"]+)">\s*<project [^>]*shortName="([^"]+)"', package))
    if "TWSYS" not in deps:
        raise SystemExit("The app has no System Data (TWSYS) dependency in META-INF/package.xml")
    return deps["TWSYS"]


def owned_uuids(twx, package, service_id):
    """UUIDs used only inside this service's file: the copy gets fresh ones; references to other objects stay."""
    text = twx.read(f"objects/{service_id}.xml").decode("utf-8")
    elsewhere = foreign_uuids(twx)
    elsewhere.update(UUID_RE.findall("\n".join(l for l in package.splitlines() if service_id not in l)))
    for name in twx.namelist():
        if name.startswith("objects/") and name != f"objects/{service_id}.xml":
            elsewhere.update(UUID_RE.findall(twx.read(name).decode("utf-8", "ignore")))
    return set(UUID_RE.findall(text)) - elsewhere


def modernize(source: Path, spec: dict, bundle: Path, dest: Path, theme: dict, snapshot=None, toolkit: Path | None = None):
    """theme: a theme file loaded by coach_theme.load_theme. toolkit: the Modernizer Widgets .twx (widget_toolkit.py
    build) whose snapshot the app depends on; needed when a coach has no hand-written screen."""
    services = [s for s in spec["services"] if s["modernize"]]
    if not services:
        raise SystemExit("Nothing to modernize: no service in the spec has \"modernize\": true")
    screens = sorted({c["screen"] for s in services for c in s["coaches"] if c.get("screen")})
    built = any(not c.get("screen") for s in services for c in s["coaches"])
    if built and not toolkit:
        raise SystemExit("Coaches without a hand-written screen are built from Modernizer Widgets: pass --toolkit, "
                         "the toolkit .twx from widget_toolkit.py build (installed on the server)")
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

        created = []
        for service in services:
            text = twx.read(f"objects/{service['id']}.xml").decode("utf-8")
            owned = owned_uuids(twx, package, service["id"])
            pid, version, name, xml = copy_service(text, service, spec["app"], theme, views.get(service["classRef"]), actions_view_id, widget_views, owned)
            objects.append(f'<object id="{pid}" versionId="{version}" name="{name}" type="process"/>')
            files[f"objects/{pid}.xml"] = xml.encode("utf-8")
            created.append(name)

        package = package.replace("</objects>", "".join(f"\n        {o}" for o in objects) + "\n    </objects>", 1)
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
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    theme, errors = load_theme(args.theme or spec.get("theme"), PROJECT, "the coach spec's theme")
    if errors:
        raise SystemExit("Invalid theme:\n  " + "\n  ".join(errors))
    for name in modernize(args.twx, spec, args.bundle, args.dest, theme, args.snapshot, args.toolkit):
        print(f"Added service: {name}")
    print(f"Wrote {args.dest}")


if __name__ == "__main__":
    main()
