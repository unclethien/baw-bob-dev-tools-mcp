#!/usr/bin/env python3
"""
Clone an exported BAW process app (.twx) into a new, independent process app.

Every UUID owned by the source project is replaced with a fresh one, consistently
across object XML, file names and META-INF/package.xml. UUIDs that also appear in
the bundled dependency toolkits (toolkits/*.zip) are left alone, so references to
System Data and UI Toolkit keep working.

Example:
    python3 server/twx_clone.py source.twx clone.twx --name "ZZ Spike - HSS Clone" --acronym ZZHSS

Pass --project-id and --branch-id of an installed app (with a new --snapshot) to
install the clone as a new snapshot of that app instead of a separate app.
"""

import argparse
import re
import uuid
import zipfile
from pathlib import Path

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TEXT_SUFFIXES = (".xml", ".json", ".MF")


def collect_toolkit_uuids(src: zipfile.ZipFile) -> set:
    """UUIDs referenced by dependency toolkits must never be rewritten."""
    keep = set()
    for name in src.namelist():
        if name.startswith("toolkits/") and name.endswith(".zip"):
            with zipfile.ZipFile(src.open(name)) as tk:
                for inner in tk.namelist():
                    keep.update(UUID_RE.findall(inner))
                    if inner.endswith(TEXT_SUFFIXES):
                        keep.update(UUID_RE.findall(tk.read(inner).decode("utf-8", "ignore")))
    return keep


def is_text(name: str) -> bool:
    return name.startswith(("META-INF/", "objects/")) and name.endswith(TEXT_SUFFIXES)


def target_uuids(src: zipfile.ZipFile) -> set:
    """Project, track and snapshot IDs always belong to the clone, even if a toolkit happens to mention them."""
    target = src.read("META-INF/package.xml").decode("utf-8").split("</target>", 1)[0]
    return set(UUID_RE.findall(target))


def build_mapping(src: zipfile.ZipFile, keep: set) -> dict:
    keep = keep - target_uuids(src)
    owned = set()
    for name in src.namelist():
        if name.startswith("toolkits/"):
            continue
        owned.update(UUID_RE.findall(name))
        if is_text(name):
            owned.update(UUID_RE.findall(src.read(name).decode("utf-8")))
    return {u: str(uuid.uuid4()) for u in sorted(owned - keep)}


def rename_project(package_xml: str, name: str, acronym: str, snapshot: str) -> str:
    target, rest = package_xml.split("</target>", 1)
    target = re.sub(r'(<project [^>]*?)name="[^"]*"', rf'\1name="{name}"', target, count=1)
    target = re.sub(r'(<project [^>]*?)description="[^"]*"', rf'\1description="{name}"', target, count=1)
    target = re.sub(r'(<project [^>]*?)shortName="[^"]*"', rf'\1shortName="{acronym}"', target, count=1)
    target = re.sub(r'(<snapshot [^>]*?)name="[^"]*"', rf'\1name="{snapshot}"', target, count=1)
    target = re.sub(r'(<snapshot [^>]*?)acronym="[^"]*"', rf'\1acronym="{snapshot}"', target, count=1)
    return target + "</target>" + rest


def pin_target(src: zipfile.ZipFile, mapping: dict, project_id: str, branch_id: str):
    """Map the source project and branch onto an existing app so the clone installs as a new snapshot of it."""
    target = src.read("META-INF/package.xml").decode("utf-8").split("</target>", 1)[0]
    for tag, new_id in (("project", project_id), ("branch", branch_id)):
        if new_id:
            old = re.search(rf'<{tag} id="20\d\d\.({UUID_RE.pattern})"', target).group(1)
            mapping[old] = new_id.split(".", 1)[-1]


def clone(source: Path, dest: Path, name: str, acronym: str, snapshot: str, project_id=None, branch_id=None) -> int:
    with zipfile.ZipFile(source) as src:
        mapping = build_mapping(src, collect_toolkit_uuids(src))
        pin_target(src, mapping, project_id, branch_id)
        swap = lambda text: UUID_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            for info in src.infolist():
                data = src.read(info.filename)
                new_name = info.filename if info.filename.startswith("toolkits/") else swap(info.filename)
                if is_text(info.filename):
                    text = swap(data.decode("utf-8"))
                    if info.filename == "META-INF/package.xml":
                        text = rename_project(text, name, acronym, snapshot)
                    data = text.encode("utf-8")
                out.writestr(new_name, data)
    return len(mapping)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("--name", required=True, help="New process app name")
    parser.add_argument("--acronym", required=True, help="New process app acronym (unique on the server)")
    parser.add_argument("--snapshot", default="v1", help="Snapshot name and acronym")
    parser.add_argument("--project-id", help="Existing process app ID (2066.*) to add the snapshot to")
    parser.add_argument("--branch-id", help="Existing branch ID (2063.*) to add the snapshot to")
    args = parser.parse_args()
    count = clone(args.source, args.dest, args.name, args.acronym, args.snapshot, args.project_id, args.branch_id)
    print(f"Cloned {args.source.name} -> {args.dest} ({count} UUIDs regenerated)")


if __name__ == "__main__":
    main()
