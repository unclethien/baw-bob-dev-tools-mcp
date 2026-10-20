#!/usr/bin/env python3
"""
Add React + Carbon copies of an app's client-side human services, driven by a coach spec.

For every service marked "modernize" in the spec (from coach_inventory.py), the service is
copied as "<name> (Modernized)", styled by the spec's theme file (see coach_theme.py).
In the copy, each coach's layout is replaced by one React form screen bound to the
service's business object, rendered from the coach's spec. The coach's original
buttons move into a hidden layout and the React buttons press them, so the coach
flow, its scripts and its variables run unchanged. Views the form cannot render
("native" in the spec) stay under the React screen. A coach with "screen": "<name>" in the
spec shows the screen registered under that name (coach-ui/src/screens/) instead of the form.

The output keeps the source app's identity. Pass --snapshot to install it as a new
snapshot of the same app, next to the original services.

Example:
    python3 server/coach_inventory.py zzeq.twx -o zzeq.coaches.json      # then review the spec
    python3 server/modernize_coaches.py zzeq.twx zzeq.coaches.json zzeq-modern.twx --snapshot 1.1.0
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
from coach_builder import SYSTEM_TYPES
from coach_views import screen_assets, screen_view
from twx_clone import UUID_RE, foreign_uuids

SUFFIX = " (Modernized)"
PROJECT = Path(__file__).resolve().parent.parent
DESIGNER_NS = "http://www.ibm.com/bpm/CoachDesignerNG"
XSI_NS = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
SCREEN_ITEM, ACTIONS_ITEM = "CoachScreen1", "PPNativeActions"
SPEC_KEYS = ("path", "label", "type", "readonly", "required", "pattern", "message", "example", "options")


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


def view_item(p, item_id, view_id, options, binding=None, children=None):
    xml = (f'<{p}:layoutItem {XSI_NS} xsi:type="{p}:ViewRef" version="8550"><{p}:id>{uid()}</{p}:id>'
           f"<{p}:layoutItemId>{item_id}</{p}:layoutItemId>{config(p, options)}<{p}:viewUUID>{view_id}</{p}:viewUUID>")
    if binding:
        xml += f"<{p}:binding>{binding}</{p}:binding>"
    if children is not None:
        xml += f"<{p}:contentBoxContrib><{p}:id>{uid()}</{p}:id><{p}:contentBoxId>ContentBox1</{p}:contentBoxId>{''.join(children)}</{p}:contentBoxContrib>"
    return xml + f"</{p}:layoutItem>"


def screen_spec(app, service, coach):
    return {
        "app": app, "title": coach["title"], "intro": coach.get("intro", ""),
        "steps": [c["title"] for c in service["coaches"]], "step": service["coaches"].index(coach),
        "sectionStyle": coach["sectionStyle"],
        "sections": [{"title": s["title"], "fields": [{k: f[k] for k in SPEC_KEYS if k in f} for f in s["fields"]]} for s in coach["sections"]],
        "buttons": [{k: b[k] for k in ("label", "viewId", "primary", "validate") if k in b} for b in coach["buttons"]],
    }


def new_layout(old, p, coach, screen_view_id, actions_view_id, theme, variable, spec):
    spans = elements(old, p)
    by_id = {vid: old[s:e] for s, e, vid in spans}
    screen = view_item(p, SCREEN_ITEM, screen_view_id, [
        ("@label", ""), ("@helpText", ""), ("@labelVisibility", "HIDE"),
        ("screen", coach.get("screen", "form")), ("theme", json.dumps(theme, separators=(",", ":"))), ("spec", json.dumps(spec, separators=(",", ":")))], binding=f"tw.local.{variable}")
    buttons = [retag(by_id[b["viewId"]], p, "contributions") for b in coach["buttons"] if b["viewId"] in by_id]
    actions = view_item(p, ACTIONS_ITEM, actions_view_id, [("@label", "Actions"), ("@helpText", ""), ("@labelVisibility", "HIDE")], children=buttons)
    native = [retag(by_id[n["viewId"]], p, "layoutItem") for n in coach["native"] if n["viewId"] in by_id]
    return screen + "".join(native) + actions


# ---------------------------------------------------------------- service copies


def copy_service(text, service, app, theme, screen_view_id, actions_view_id, owned):
    p = re.search(rf'xmlns:(\w+)="{re.escape(DESIGNER_NS)}"', text).group(1)
    for coach in service["coaches"]:
        at = text.index(f'id="{coach["id"]}"')
        open_tag = re.compile(rf"<{p}:layout(?:\s[^>]*)?>").search(text, at)
        close = text.index(f"</{p}:layout>", open_tag.end())
        layout = new_layout(text[open_tag.end():close], p, coach, screen_view_id, actions_view_id, theme, service["variable"],
                            screen_spec(app, service, coach))
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


def modernize(source: Path, spec: dict, bundle: Path, dest: Path, theme: dict, snapshot=None):
    """theme: a theme file loaded by coach_theme.load_theme."""
    services = [s for s in spec["services"] if s["modernize"]]
    if not services:
        raise SystemExit("Nothing to modernize: no service in the spec has \"modernize\": true")
    with zipfile.ZipFile(source) as twx:
        package = twx.read("META-INF/package.xml").decode("utf-8")
        names = view_names(twx)
        actions_view_id = next(i for i, n in names.items() if n == "Horizontal Layout")

        # Managed files: reuse the app's coach-screens.* files (new content, new version) so names stay unique.
        # pp-react.* files of apps modernized before the rename stay as they are: their PP React views still use them.
        existing = {}
        for aid, name in re.findall(r'<object id="(61\.[^"]+)" versionId="[^"]+" name="(coach-screens\.[a-z]+)" type="managedAsset"/>', package):
            asset_uuid = re.search(rf'<file path="([^"]+)" id="{re.escape(aid)}"/>', package).group(1)
            existing[name] = (aid, asset_uuid, uid())
            package = re.sub(rf'(<object id="{re.escape(aid)}" versionId=")[^"]+', rf"\g<1>{existing[name][2]}", package)
        script = (bundle / "coach-screens.js").read_text()
        missing = sorted({c["screen"] for s in services for c in s["coaches"] if c.get("screen") and f'"{c["screen"]}"' not in script})
        if missing:
            raise SystemExit(f"Screens not in the bundle: {', '.join(missing)}. Register them in coach-ui/src/screens/ and rebuild")
        asset_ids, entries, files = screen_assets(bundle, existing)
        objects = [e for e, _ in entries]
        file_entries = [f for _, f in entries if f]

        views = {}
        for ref in sorted({s["classRef"] for s in services}):
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
            pid, version, name, xml = copy_service(text, service, spec["app"], theme, views[service["classRef"]], actions_view_id, owned)
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

        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            for info in twx.infolist():
                if info.filename == "META-INF/package.xml":
                    out.writestr(info.filename, package)
                elif info.filename not in files:
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
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    theme, errors = load_theme(args.theme or spec.get("theme"), PROJECT, "the coach spec's theme")
    if errors:
        raise SystemExit("Invalid theme:\n  " + "\n  ".join(errors))
    for name in modernize(args.twx, spec, args.bundle, args.dest, theme, args.snapshot):
        print(f"Added service: {name}")
    print(f"Wrote {args.dest}")


if __name__ == "__main__":
    main()
