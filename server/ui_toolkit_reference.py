#!/usr/bin/env python3
"""
The UI Toolkit's controls as Coach Designer shows them, read from the BAW database: for each control its
Configuration settings (name, English label, section, type and, for a dropdown, its choices) and its Events.
A new Modernizer Widget starts from its UI Toolkit counterpart's entry, so authors find the same settings
in the same sections (see .bob/skills/modernizer-widget/SKILL.md).

    uv run --with 'psycopg[binary]' python server/ui_toolkit_reference.py [coach-ui/widgets/ui-toolkit-reference.json]
    python3 server/ui_toolkit_reference.py show Slider      # one control, from the file (no database)

The database stores each setting's type under an internal ID that the exported views do not use. The script names
each ID from the settings that share it: a dropdown by the Selection type whose name matches the setting (Text's
sizeStyle is TextSizeStyle), a plain value by a setting of known type (tabIndex is an Integer). It prints the IDs it
could not name; their settings get the type null.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import pg_ops

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT / "coach-ui" / "widgets" / "ui-toolkit-reference.json"
PREFIX = "tw.resource.BPMUI."
# Settings whose type every UI Toolkit release has kept: they name the plain types' internal IDs.
KNOWN = {"tabIndex": "Integer", "placeHolder": "String", "width": "String", "selectAll": "Boolean", "ghostMode": "Boolean",
         "decimalPlaces": "Integer", "startDate": "Date", "endDate": "Date", "staticList": "NameValuePair"}


def rows(sql, limit=1000):
    return pg_ops.execute("basdb", sql, limit=limit)["rows"]


def english():
    """{"tw.resource.<bundle>.<key>": English text} of every resource bundle (the UI Toolkit's is BPMUI)."""
    out, offset = {}, 0
    while True:
        page = rows(f"""select g.name, k.akey, k.value from basdb.lsw_resource_bundle_key k
            join basdb.lsw_resource_bundle b on b.resource_bundle_id = k.resource_bundle_id
            join basdb.lsw_resource_bundle_group g on g.resource_bundle_group_id = b.resource_bundle_group_id
            where coalesce(b.locale_language, '') = '' order by g.name, k.akey limit 1000 offset {offset}""")
        out.update({f"tw.resource.{g}.{k}": v for g, k, v in page})
        if len(page) < 1000:
            return out
        offset += 1000


def selection_types():
    """{type name: [{value, label}]} of every Selection type on the server."""
    out, offset = {}, 0
    while True:
        # Only the restriction is read, since the query tool shortens long values.
        page = rows(f"""select name, substring(encode(xml_data, 'escape') from '<restriction base="Selection">(?:[^<]|<option[^>]*>)*</restriction>')
            from basdb.lsw_class order by class_id limit 1000 offset {offset}""")
        for name, restriction in page:
            if restriction:
                out[name] = [{"value": v, "label": d} for v, d in re.findall(r'<option value="([^"]*)" display="([^"]*)"', restriction)]
        if len(page) < 1000:
            return out
        offset += 1000


def text(key, labels):
    """A label or section as Coach Designer shows it in English: a resource key's text, else the text itself."""
    return labels.get(key, key) if key else None


def controls():
    """{control name: [(name, property type, class id, section key, label key, is list)]}: the newest version of
    every UI Toolkit view."""
    views = rows(f"""select distinct on (v.name) v.name, v.coach_view_id from basdb.bpm_coach_view v
        where exists (select 1 from basdb.bpm_coach_view_config_option o where o.coach_view_id = v.coach_view_id and o.label like '{PREFIX}%')
        order by v.name, v.last_modified desc nulls last""")
    out = {}
    for name, view_id in views:
        out[name] = rows(f"""select * from (select distinct on (name) name, property_type, class_id, group_name, label, is_list, seq
            from basdb.bpm_coach_view_config_option where coach_view_id = '{view_id}' order by name, last_modified desc nulls last) o
            order by seq::int, name""")
    return out


def type_names(views, selections):
    """{internal class ID: type name}, and the IDs left unnamed."""
    names, unnamed = {}, set()
    for opts in views.values():
        for name, prop, class_id, *_ in opts:
            if prop != "EVENT" and name in KNOWN and class_id:
                names.setdefault(class_id, KNOWN[name])
    for control, opts in views.items():
        for name, prop, class_id, *_ in opts:
            if prop == "EVENT" or not class_id or class_id in names:
                continue
            cap = name[0].upper() + name[1:]
            for candidate in (control.replace(" ", "") + cap, cap, control.replace(" ", "") + cap.replace("Style", "")):
                if candidate in selections:
                    names[class_id] = candidate
                    break
    for opts in views.values():
        unnamed |= {class_id for name, prop, class_id, *_ in opts if prop != "EVENT" and class_id and class_id not in names}
    return names, unnamed


def build():
    labels, selections, views = english(), selection_types(), controls()
    names, unnamed = type_names(views, selections)
    used, out = set(), {}
    for control, opts in views.items():
        settings, events = [], []
        for name, prop, class_id, group, label, is_list, _ in opts:
            if prop == "EVENT":
                events.append({"name": name, "label": text(label, labels)})
                continue
            type_ = names.get(class_id)
            used.add(type_)
            setting = {"name": name, "label": text(label, labels), "group": text(group, labels), "type": type_}
            if str(is_list).upper() in ("T", "TRUE"):
                setting["list"] = True
            settings.append(setting)
        out[control] = {"settings": settings, "events": events}
    for class_id in sorted(unnamed):
        users = sorted({f"{c}.{n}" for c, opts in views.items() for n, p, i, *_ in opts if i == class_id})
        print(f"unnamed type {class_id}: {', '.join(users)}", file=sys.stderr)
    return {
        "about": "The UI Toolkit's controls as Coach Designer shows them, read from BAW by server/ui_toolkit_reference.py on "
                 f"{date.today().isoformat()}: each control's Configuration settings (label, section, type) and Events. types: the "
                 "choices of each dropdown type, as {value, label}; the value is what a coach stores. A setting whose type could "
                 "not be read has the type null.",
        "types": {t: selections[t] for t in sorted(used - {None}) if t in selections},
        "controls": out,
    }


def show(control, path=DEFAULT_OUT):
    """One control's settings and events as text, with each dropdown's choices: what a widget standing for it declares."""
    reference = json.loads(Path(path).read_text())
    control = next((k for k in reference["controls"] if k.lower() == control.lower()), control)
    found = reference["controls"].get(control)
    if not found:
        raise SystemExit(f"No UI Toolkit control {control!r}. Controls: {', '.join(sorted(reference['controls']))}")
    lines = [f"{control}: settings (name, label, section, type)"]
    for st in found["settings"]:
        choices = reference["types"].get(st["type"])
        extra = f" = {', '.join(c['value'] + ' ' + c['label'] for c in choices)}" if choices else ""
        lines.append(f"  {st['name']}: {st['label']} | {st['group']} | {st['type'] or 'type not read'}{' list' if st.get('list') else ''}{extra}")
    lines.append("events (name, label)")
    lines += [f"  {e['name']}: {e['label']}" for e in found["events"]]
    return "\n".join(lines)


def main():
    if sys.argv[1:2] == ["show"]:
        print(show(" ".join(sys.argv[2:])))
        return
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    reference = build()
    dest.write_text(json.dumps(reference, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {dest}: {len(reference['controls'])} controls, {len(reference['types'])} dropdown types")


if __name__ == "__main__":
    main()
