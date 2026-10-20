#!/usr/bin/env python3
"""
Toolkits of coach widgets that Coach Designer shows in its palette, and the link from an app to them.

A toolkit .twx holds one Coach View per widget, each with a palette icon and a Coach Designer
preview, plus the widgets' bundle as web managed files. The toolkit's project and branch IDs are
fixed below, so every build installs as a new snapshot of the same toolkit.

An app uses a toolkit through a dependency in its META-INF/package.xml and a copy of the toolkit's
package in toolkits/<snapshot id>.zip. A layout item names a toolkit view by its plain ID (64.*), as it
does for UI Toolkit views; only type references (classId) carry a "<dependency uuid>/" prefix.

    python3 server/widget_toolkit.py build modernizer 0.0.1 work/MDW-0.0.1.twx
    python3 server/widget_toolkit.py use work/app.twx work/MDW-0.0.1.twx work/app-widgets.twx --swap "Requester:Text1=text" --swap "Requester:Button1=button"
"""

import argparse
import functools
import json
import re
import sys
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, unescape

import app_template
from coach_builder import SYSTEM_TYPES, TWSYS
from coach_views import managed_asset_xml, view_xml

PROJECT = Path(__file__).resolve().parent.parent
COACH_UI = PROJECT / "coach-ui"
BUNDLE = COACH_UI / "bundle"
ICONS = COACH_UI / "widgets" / "icons"

TOOLKITS = {
    "modernizer": {"name": "Modernizer Widgets", "acronym": "MDW",
                   "projectId": "2066.bd5e169d-837c-4cc4-9754-348c6d267872", "branchId": "2063.c491e35e-3dcc-43da-8fd0-5c8af6a6970e"},
}


@functools.cache
def widgets(toolkit):
    """The toolkit's widget contract (coach-ui/widgets/<toolkit>-widgets.json), by kind. Each widget: view, binding,
    label (has a Label property), options [(name, label, type, is list)], boundary, sample (the preview's value)
    and tags (palette categories)."""
    contract = json.loads((COACH_UI / "widgets" / f"{toolkit}-widgets.json").read_text())
    return {w["kind"]: {"view": w["view"], "binding": w["binding"], "label": w["label"],
                        "options": [(o["name"], o["label"], o.get("type", "String"), o.get("list", False)) for o in w["options"]],
                        "boundary": w["boundary"], "sample": w["preview"]["value"], "tags": w["tags"]} for w in contract["widgets"]}


# System Data types that widget bindings and options use, beyond the ones generated apps use.
TYPES = {**SYSTEM_TYPES, "NameValuePair": "12.d2e5a15a-ea53-4793-9e93-29af5bd80b13"}


BUNDLE_FILES = [("mdw.js", "application/javascript"), ("mdw.css", "text/css")]


def uid():
    return str(uuid.uuid4())


def stable_ids(toolkit, name):
    """IDs that stay the same in every build of a toolkit, so apps keep finding its views across snapshots:
    the n-th call for the same toolkit and name always returns the same UUID."""
    space = uuid.UUID(TOOLKITS[toolkit]["projectId"].split(".", 1)[1])
    count = iter(range(1_000_000))
    return lambda: str(uuid.uuid5(space, f"{name}/{next(count)}"))


def widget_kinds(toolkit):
    """{view ID: kind} of the toolkit's widgets. The IDs are the same in every build (see build), so they also
    name the widgets of an app whose package does not carry the toolkit."""
    return {"64." + stable_ids(toolkit, f"view/{kind}")(): kind for kind in widgets(toolkit)}


def metadata_xml(tags):
    """META-INF/metadata.xml: the palette categories of each view. tags: {view id: [tag]}."""
    objects = "".join(f'\n    <object id="{oid}">\n        <tags>' + "".join(f"\n            <tag>{escape(t)}</tag>" for t in names)
                      + "\n        </tags>\n    </object>" for oid, names in tags.items())
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<metadata>{objects}\n</metadata>\n'


def load_js(kind, options):
    """The Coach View's load handler: the toolkit bundle's widget host builds the widget's context from the view."""
    return f"this._ppWidget = window.ModernizerWidgets.attach(this, {json.dumps(kind)}, {json.dumps([o[0] for o in options])});"


CHANGE_JS = "if (this._ppWidget) this._ppWidget.update();"
UNLOAD_JS = "if (this._ppWidget) this._ppWidget.unmount();"

PREVIEW_HTML = '<div class="pp-preview"></div>\n'


def preview_js(kind, acronym, sample, options):
    """Coach Designer preview: loads the toolkit's own bundle into Designer and mounts the real widget."""
    return f"""var mixObject = {{
  createPreview: function (containingDiv, labelText, callback) {{
    var self = this, doc = containingDiv.ownerDocument, win = doc.defaultView;
    function initial(name) {{
      try {{
        var o = self.context.options && self.context.options[name];
        return o && o.get ? o.get("value") : undefined;
      }} catch (e) {{ return undefined; }}
    }}
    this._ppState = {{ label: labelText, help: "", options: {{}} }};
    {json.dumps([o[0] for o in options])}.forEach(function (name) {{ self._ppState.options[name] = initial(name); }});
    function options() {{
      var out = {{}};
      var plain = win.ModernizerWidgets.plain || function (value) {{ return value; }};
      for (var name in self._ppState.options) out[name] = plain(self._ppState.options[name]);
      return out;
    }}
    function url(name) {{ return self.context.getManagedAssetUrl(name, self.context.assetType_WEB, {json.dumps(acronym)}); }}
    function mount() {{
      try {{
        self._ppWidget = win.ModernizerWidgets.mountWidget(containingDiv, {json.dumps(kind)}, {{
          read: function () {{ return {{ label: self._ppState.label, helpText: self._ppState.help, visibility: "EDITABLE", options: options(), preview: true }}; }},
          binding: {{ get: function () {{ return self._ppState.options.example ? "" : {json.dumps(sample)}; }}, set: function () {{}} }},
          trigger: function () {{}}
        }});
      }} finally {{ callback(); }}
    }}
    if (!doc.getElementById("mdw-css")) {{
      var link = doc.createElement("link");
      link.id = "mdw-css"; link.rel = "stylesheet"; link.href = url("mdw.css");
      doc.head.appendChild(link);
    }}
    if (win.ModernizerWidgets) return mount();
    // One script per toolkit snapshot: its URL names the snapshot, so previews of two versions never wait on each other.
    var src = url("mdw.js"), script = doc.querySelector('script[data-mdw="' + src + '"]');
    if (script && script.getAttribute("data-done")) return callback();
    if (!script) {{
      script = doc.createElement("script");
      script.setAttribute("data-mdw", src); script.src = src;
      script.addEventListener("load", function () {{ script.setAttribute("data-done", "1"); }});
      script.addEventListener("error", function () {{ script.setAttribute("data-done", "1"); }});
      doc.head.appendChild(script);
    }}
    script.addEventListener("load", mount);
    script.addEventListener("error", function () {{ callback(); }});
  }},
  propertyChanged: function (name, value) {{
    if (!this._ppState) return;
    if (name === "@label") this._ppState.label = value;
    else if (name === "@helpText") this._ppState.help = value;
    else this._ppState.options[name] = value;
    if (this._ppWidget) this._ppWidget.update();
  }},
  modelChanged: function () {{}},
  getLabelDomElement: function () {{ return null; }}
}};
"""


def managed_file(name, mime, data, files, objects, file_entries, new_id):
    asset_id, asset_uuid, version = "61." + new_id(), new_id(), uid()
    files[f"objects/{asset_id}.xml"] = managed_asset_xml(asset_id, version, name, asset_uuid, mime, len(data), guid=new_id())
    files[f"files/{asset_id}/{asset_uuid}"] = data
    objects.append((asset_id, version, name, "managedAsset"))
    file_entries.append((asset_uuid, asset_id))
    return asset_id


def build(toolkit: str, snapshot: str, dest: Path, bundle: Path = BUNDLE, author="widget_toolkit"):
    """Write the toolkit .twx. Returns the names of its widgets. Object IDs are the same in every build;
    versionIds and the snapshot ID are new, so BAW installs the new content as a new snapshot."""
    tk = TOOLKITS[toolkit]
    base = app_template.builtin()
    files, objects, file_entries, tags = {}, [], [], {}
    asset = lambda name, mime, data: managed_file(name, mime, data, files, objects, file_entries, stable_ids(toolkit, f"file/{name}"))  # noqa: E731
    assets = [asset(name, mime, (bundle / name).read_bytes()) for name, mime in BUNDLE_FILES]
    preview_html = asset("mdw-preview.html", "text/html", PREVIEW_HTML.encode())
    for kind, w in widgets(toolkit).items():
        icon_path = ICONS / f"{kind}.svg"
        icon = asset(f"{kind}.svg", "image/svg+xml", icon_path.read_bytes()) if icon_path.exists() else None
        preview = asset(f"{kind}-preview.js", "application/javascript", preview_js(kind, tk["acronym"], w["sample"], w["options"]).encode())
        new_id = stable_ids(toolkit, f"view/{kind}")
        view_id, version = "64." + new_id(), uid()
        files[f"objects/{view_id}.xml"] = view_xml(
            view_id, version, escape(w["view"]), binding_ref=f"{TWSYS}/{TYPES[w['binding']]}" if w["binding"] else None,
            options=[(o, label, f"{TWSYS}/{TYPES[t]}", is_list) for o, label, t, is_list in w["options"]], asset_ids=assets,
            load=load_js(kind, w["options"]), change=CHANGE_JS, unload=UNLOAD_JS, description=f"{tk['name']}: {w['view']}",
            palette_icon=icon, preview_html=preview_html, preview_js=preview, has_label=w["label"], emit_boundary=w["boundary"], new_id=new_id)
        objects.append((view_id, version, w["view"], "coachView"))
        tags[view_id] = w["tags"] + [tk["name"]]
    settings_id = stable_ids(toolkit, "settings")
    defaults = ("63." + settings_id(), uid())
    files[f"objects/{defaults[0]}.xml"] = app_template.PROJECT_DEFAULTS.format(
        id=defaults[0], version=defaults[1], guid=settings_id(), author=author, theme=app_template.DEFAULT_THEME, environment=base["environment"]
    ).replace('name="Process App Settings"', 'name="Toolkit Settings"')
    objects.insert(0, (*defaults, "Toolkit Settings", "projectDefaults"))
    ids = {"projectId": tk["projectId"], "branchId": tk["branchId"], "branchName": "Main", "snapshotId": "2064." + uid()}
    app = {"name": tk["name"], "acronym": tk["acronym"], "snapshot": snapshot}
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        for name, text in {**app_template.META_INF, "META-INF/metadata.xml": metadata_xml(tags)}.items():
            out.writestr(name, text)
        out.writestr("META-INF/package.xml", app_template.package_xml(base, app, ids, objects, toolkit=True, files=file_entries))
        for name, data in files.items():
            out.writestr(name, data)
    return [w["view"] for w in widgets(toolkit).values()]


def toolkit_dependency(toolkit_twx: Path, rank):
    """The dependency entry an app needs for a built toolkit, with a dependency ID of the app's own, and the
    toolkit's view IDs by name."""
    with zipfile.ZipFile(toolkit_twx) as z:
        package = z.read("META-INF/package.xml").decode("utf-8")
    views = dict(re.findall(r'<object id="(64\.[^"]+)" versionId="[^"]+" name="([^"]+)" type="coachView"/>', package))
    t = app_template.target(package)
    return {"id": "2069." + uid(), "rank": rank, **{k: t[k] for k in ("projectId", "name", "acronym", "branchId", "branchName", "snapshotId", "snapshot", "created")},
            "views": {name: vid for vid, name in views.items()}}


def add_dependency(package: str, toolkit_twx: Path):
    """Make an app's META-INF/package.xml depend on the toolkit built in toolkit_twx. An existing dependency on the
    same toolkit moves to this snapshot and keeps its ID, which the app's type references use. Returns (package, dep)."""
    dep = toolkit_dependency(toolkit_twx, 0)
    existing = next((d for d in app_template.toolkit_dependencies(package) if d["projectId"] == dep["projectId"]), None)
    if existing:
        dep.update(id=existing["id"], rank=existing["rank"], previous=existing["snapshotId"])
        block = re.search(rf'<dependency [^>]*\bid="{re.escape(existing["id"])}">.*?</dependency>', package, re.S).group(0)
        return package.replace(block, app_template.dependency_xml(dep).strip(), 1), dep
    if dep["projectId"] in package.split("</dependencies>", 1)[0].split("<dependencies>", 1)[-1]:
        raise SystemExit(f"META-INF/package.xml lists {dep['acronym']} as a dependency in a form this script cannot read")
    dep["rank"] = max((int(r) for r in re.findall(r'<dependency rank="(\d+)"', package)), default=-1) + 1
    if "\n    </dependencies>" not in package:
        raise SystemExit("META-INF/package.xml has no </dependencies>")
    return package.replace("\n    </dependencies>", app_template.dependency_xml(dep) + "\n    </dependencies>", 1), dep


def option_text(value):
    """A layout option's value as text: lists and objects as JSON, booleans as true/false."""
    if isinstance(value, bool):
        return str(value).lower()
    return value if isinstance(value, str) else json.dumps(value)


def swap_view(layout, item_id, view_ref, options):
    """Point one layout item at another view, keeping its layoutItemId, binding and @ options; add options."""
    found = re.search(rf"<(\w+):layoutItemId>{re.escape(item_id)}</\1:layoutItemId>", layout)
    if not found:
        raise SystemExit(f"No layout item {item_id}")
    p = found.group(1)
    start = max(layout.rfind(f"<{p}:layoutItem ", 0, found.start()), layout.rfind(f"<{p}:contributions ", 0, found.start()))
    view_at = layout.find(f"<{p}:viewUUID>", found.end())
    later = [i for i in (layout.find(f"<{p}:layoutItem ", found.end()), layout.find(f"<{p}:contributions ", found.end())) if i >= 0]
    if view_at < 0 or (later and view_at > min(later)):
        raise SystemExit(f"Layout item {item_id} is not a view")
    end = layout.index(f"</{p}:viewUUID>", view_at) + len(f"</{p}:viewUUID>")
    item = layout[start:end]
    # Drop the old view's own options (BAW exports are indented, so allow whitespace between the tags); keep @ options.
    item = re.sub(rf"<{p}:configData>\s*<{p}:id>[^<]*</{p}:id>\s*<{p}:optionName>(?!@)[^<]*</{p}:optionName>\s*"
                  rf"(?:<{p}:value\s*/>|<{p}:value>[^<]*</{p}:value>)\s*</{p}:configData>\s*", "", item)
    extra = "".join(f"<{p}:configData><{p}:id>{uid()}</{p}:id><{p}:optionName>{k}</{p}:optionName><{p}:value>{escape(option_text(v))}</{p}:value></{p}:configData>"
                    for k, v in options.items())
    item = re.sub(rf"<{p}:viewUUID>[^<]*</{p}:viewUUID>$", f"{extra}<{p}:viewUUID>{view_ref}</{p}:viewUUID>", item)
    return layout[:start] + item + layout[end:]


def use_widgets(app_twx: Path, toolkit_twx: Path, dest: Path, swaps, snapshot=None):
    """Make an app depend on the toolkit (or move it to this toolkit snapshot) and point layout items at its widgets.

    swaps: (service name or None for every service, coach name, layout item id, widget kind, {option: value}).
    """
    with zipfile.ZipFile(app_twx) as twx:
        package, dep = add_dependency(twx.read("META-INF/package.xml").decode("utf-8"), toolkit_twx)
        toolkit = next(k for k, t in TOOLKITS.items() if t["acronym"] == dep["acronym"])
        if snapshot:
            target, rest = package.split("</target>", 1)
            target = re.sub(r'<snapshot id="2064\.[^"]+" name="[^"]*" acronym="[^"]*"',
                            f'<snapshot id="2064.{uid()}" name="{escape(snapshot)}" acronym="{escape(snapshot)}"', target)
            package = target + "</target>" + rest
        changed, swapped = {}, set()
        for name in twx.namelist():
            if not re.match(r"objects/1\.", name):
                continue
            text = twx.read(name).decode("utf-8")
            service_name = unescape(re.search(r'<process id="[^"]+" name="([^"]*)"', text).group(1))
            for service, coach, item_id, kind, options in swaps:
                m = re.search(rf'<\w+:formTask name="{re.escape(escape(coach))}"', text)
                if not m or (service and service != service_name):
                    continue
                close = m.end() + re.search(r"</\w+:layout>", text[m.end():]).start()
                view_ref = dep["views"][widgets(toolkit)[kind]["view"]]
                text = text[:m.end()] + swap_view(text[m.end():close], item_id, view_ref, options) + text[close:]
                changed[name] = text
                swapped.add((service, coach, item_id))
        missing = [f"{s + '/' if s else ''}{c}:{i}" for s, c, i, _, _ in swaps if (s, c, i) not in swapped]
        if missing:
            raise SystemExit(f"No coach for: {', '.join(missing)}")
        # BAW keeps an object's installed content when its versionId is unchanged, so changed objects get new ones.
        for name, text in changed.items():
            oid = name[len("objects/"):-len(".xml")]
            old_version = re.search(r"<versionId>([^<]+)</versionId>", text).group(1)
            new_version = uid()
            changed[name] = text.replace(f"<versionId>{old_version}</versionId>", f"<versionId>{new_version}</versionId>", 1)
            entry = f'<object id="{oid}" versionId="{old_version}"'
            if entry not in package:
                raise SystemExit(f"META-INF/package.xml has no entry {entry}")
            package = package.replace(entry, f'<object id="{oid}" versionId="{new_version}"', 1)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            toolkit_zip = f"toolkits/{dep['snapshotId']}.zip"
            stale = {toolkit_zip} | ({f"toolkits/{dep['previous']}.zip"} if dep.get("previous") else set())
            for info in twx.infolist():
                if info.filename == "META-INF/package.xml":
                    out.writestr(info.filename, package)
                elif info.filename in changed:
                    out.writestr(info.filename, changed[info.filename])
                elif info.filename not in stale:
                    out.writestr(info, twx.read(info.filename))
            # BAW's own exports carry every non-system toolkit an app depends on, even without toolkits.
            out.writestr(toolkit_zip, toolkit_twx.read_bytes())
    return dep


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="Build a widget toolkit .twx")
    b.add_argument("toolkit", choices=sorted(TOOLKITS))
    b.add_argument("snapshot")
    b.add_argument("dest", type=Path)
    v = sub.add_parser("preview", help="Print a widget's Coach Designer preview script (for offline checks)")
    v.add_argument("toolkit", choices=sorted(TOOLKITS))
    v.add_argument("kind")
    u = sub.add_parser("use", help="Make an app use a toolkit's widgets in place of some layout items")
    u.add_argument("app", type=Path)
    u.add_argument("toolkit", type=Path)
    u.add_argument("dest", type=Path)
    u.add_argument("--swap", action="append", default=[],
                   help='"[Service/]Coach:LayoutItemId=kind" or "...=kind:{json options}"; without Service, every service with that coach')
    u.add_argument("--snapshot")
    args = parser.parse_args()
    if args.command == "preview":
        w = widgets(args.toolkit)[args.kind]
        print(preview_js(args.kind, TOOLKITS[args.toolkit]["acronym"], w["sample"], w["options"]))
    elif args.command == "build":
        names = build(args.toolkit, args.snapshot, args.dest)
        print(f"Wrote {args.dest}: {TOOLKITS[args.toolkit]['name']} ({TOOLKITS[args.toolkit]['acronym']}) {args.snapshot}, widgets: {', '.join(names)}")
    else:
        swaps = []
        for s in args.swap:
            where, what = s.split("=", 1)
            coach, item = where.rsplit(":", 1)
            service, _, coach = coach.rpartition("/")
            kind, _, opts = what.partition(":")
            swaps.append((service or None, coach, item, kind, json.loads(opts) if opts else {}))
        dep = use_widgets(args.app, args.toolkit, args.dest, swaps, args.snapshot)
        print(f"Wrote {args.dest}: depends on {dep['name']} ({dep['acronym']}) {dep['snapshot']}, {len(swaps)} item(s) swapped")


if __name__ == "__main__":
    sys.exit(main())
