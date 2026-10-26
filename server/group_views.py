#!/usr/bin/env python3
"""
Reusable field groups: a group is a Coach View inside the app, listed under the app's User interface, that holds
one field view per field and is placed on coaches like any other view. Users open it in Coach Designer to add,
remove or move fields, and every coach that places it shows the change.

How a group works (proven on the server against IBM's own sample views):

- The View's business data binding is named after the app's variable (e.g. "member"), and is of the app's
  business object type. Its fields bind as tw.businessData.<variable>.<path>; a coach places the group with
  binding tw.local.<variable>, so the fields read and write the coach's own object.
- Every field that can be hidden has an option "<path>Visibility" of the app's Selection type GroupFieldVisibility
  ("Same as parent" or "Hidden"), and the field's visibility is bound to it. Unset means shown. A required field keeps
  its own Required visibility and has no option.
- Read only is the placement's own Visibility: every field in the group follows it ("Same as parent"). A field whose
  option is left unset gets an empty visibility, which BAW treats as Editable, and a Required field keeps Required
  under a read-only parent; the View's small load script (GROUP_JS) turns the first into "Same as parent" and makes
  the second read-only while the group is. It walks every view in the group, so fields added in Designer follow too.
- The View's description ends with a fingerprint of its fields (layout_fields), so a later build can tell whether
  someone changed which fields the group has in BAW: added, removed, moved or relabelled (changed_in_baw). Other
  edits (help text, choices, styling) are not detected; they belong in the spec, and a rebuild overwrites them.

Each group also gets a "<group> Preview" client-side human service that shows only the group, so it can be
run and tested on its own (preview_service).

Callers build the field views (classic stock views or Modernizer Widgets) with their own field builders, using
the CoachDesignerNG prefix ns2 of a view's layout, and the coach-side items with their own layout helpers.
"""

import hashlib
import html
import re
import uuid
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from coach_builder import coachflow, service_xml
from coach_views import view_xml

VISIBILITY_TYPE = "GroupFieldVisibility"
VISIBILITY_VALUES = [("DEFAULT", "Same as parent"), ("NONE", "Hidden")]
XSI = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
FINGERPRINT = re.compile(r"fingerprint ([0-9a-f]{12})")
LABEL_MAX = 64  # longest visibility option label written

GROUP_JS = """var view = this;
function each(v, fn) {
  var subs = (v.context && v.context.subview) || {};
  for (var id in subs) {  // view ID -> {DOM ID -> view instance}
    var entry = subs[id], list = entry && entry.context ? [entry] : [];
    if (!list.length) for (var dom in entry) list.push(entry[dom]);
    for (var i = 0; i < list.length; i++) if (list[i] && list[i].context) { fn(list[i]); each(list[i], fn); }
  }
}
view._groupVisibility = function () {
  var own = view.context.options._metadata.visibility, mine = own ? own.get("value") : "";
  var shown = !mine || mine === "DEFAULT" ? (view.context.getInheritedVisibility ? view.context.getInheritedVisibility() : "EDITABLE") : mine;
  each(view, function (sub) {
    var vis = sub.context.options._metadata && sub.context.options._metadata.visibility;
    if (!vis) return;
    var value = vis.get("value");
    if (value === "REQUIRED" || sub._groupRequired) {
      sub._groupRequired = true;
      value = shown === "READONLY" ? "READONLY" : "REQUIRED";
    } else if (!value) {
      value = "DEFAULT";
    } else {
      return;
    }
    if (vis.get("value") !== value) vis.set("value", value);
  });
};
view._groupVisibility();"""
GROUP_CHANGE_JS = 'if (event.type === "config" && this._groupVisibility) this._groupVisibility();'

SELECTION_TYPE = """<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <twClass id="{id}" name="{name}">
        <lastModified>0</lastModified>
        <lastModifiedBy>{author}</lastModifiedBy>
        <tenantId isNull="true" />
        <classId>{id}</classId>
        <type>0</type>
        <isSystem>false</isSystem>
        <shared>false</shared>
        <isShadow>false</isShadow>
        <globalLifetime>false</globalLifetime>
        <internalName isNull="true" />
        <extensionType isNull="true" />
        <saveServiceRef isNull="true" />
        <bpmn2Data isNull="true" />
        <externalId>itm.{id}</externalId>
        <dependencySummary isNull="true" />
        <jsonData>{json}</jsonData>
        <dataName isNull="true" />
        <allowAdditionalProperties>false</allowAdditionalProperties>
        <description>{description}</description>
        <guid>{guid}</guid>
        <versionId>{version}</versionId>
        <definition>
            <validator>
                <className isNull="true" />
                <errorMessage isNull="true" />
                <webWidgetJavaClass isNull="true" />
                <externalType isNull="true" />
                <configData>
                    <schema>
                        <simpleType name="{name}">
                            <restriction base="Selection">
{options}
                            </restriction>
                        </simpleType>
                    </schema>
                </configData>
            </validator>
            <annotation type="com.lombardisoftware.core.xml.XMLTypeAnnotation" version="2.0">
                <exclude isNull="true" />
                <anonymous isNull="true" />
                <local isNull="true" />
                <name isNull="true" />
                <namespace isNull="true" />
                <elementName isNull="true" />
                <elementNamespace isNull="true" />
                <protoTypeName isNull="true" />
                <baseTypeName isNull="true" />
                <specialType isNull="true" />
                <contentTypeVariety isNull="true" />
                <xscRef isNull="true" />
            </annotation>
        </definition>
    </twClass>
</teamworks>
"""


def uid():
    return str(uuid.uuid4())


def stable_ids(acronym, name):
    """IDs that stay the same in every build of an app, so each snapshot updates the same group View and the coaches
    that place it keep finding it: the n-th call for the same app and name always returns the same UUID."""
    space = uuid.uuid5(uuid.NAMESPACE_URL, f"baw-dev-tools/{acronym}")
    count = iter(range(1_000_000))
    return lambda: str(uuid.uuid5(space, f"{name}/{next(count)}"))


def visibility_type(acronym, author="group_views"):
    """The app's Selection type for a group field's visibility option: (class id, version, xml)."""
    new_id = stable_ids(acronym, f"type/{VISIBILITY_TYPE}")
    class_id, version = "12." + new_id(), uid()
    enum = ",".join('{"annotation":{"appinfo":[{"displayName":["%s"]}]},"value":"%s"}' % (label, value) for value, label in VISIBILITY_VALUES)
    json = ('{"simpleType":[{"annotation":{"documentation":[{}],"appinfo":[{"advancedProperties":[{}]}]},"name":"%s",'
            '"restriction":{"annotation":{"appinfo":[{"simpleBaseType":["Selection"]}]},"enumeration":[%s],'
            '"base":"{http:\\/\\/www.w3.org\\/2001\\/XMLSchema}string"}}],"attributeFormDefault":"unqualified",'
            '"elementFormDefault":"unqualified","targetNamespace":"http:\\/\\/%s","id":"_%s"}') % (VISIBILITY_TYPE, enum, acronym, class_id)
    options = "\n".join(f'                                <option value="{value}" display="{label}" />' for value, label in VISIBILITY_VALUES)
    xml = SELECTION_TYPE.format(id=class_id, name=VISIBILITY_TYPE, author=author, json=escape(json), guid=new_id(), version=version,
                                options=options, description="Visibility of a field in a reusable group: Same as parent, or Hidden.")
    return class_id, version, xml


def binding_name(view_text):
    m = re.search(r'<bindingType name="([^"]+)"', view_text)
    return m.group(1) if m else None


def layout_fields(view_text):
    """The fields of a group View as its layout has them, in document order: [{"path", "viewUUID", "label", "config"}]
    for every view bound under the View's data (tw.businessData.<binding name>.<path>). Reads what this module
    builds and what Coach Designer saves alike."""
    name, m = binding_name(view_text), re.search(r"<layout>(.*?)</layout>", view_text, re.S)
    if not name or not m:
        return []
    prefix, out = f"tw.businessData.{name}.", []
    try:
        root = ET.fromstring(html.unescape(m.group(1)).encode())
    except ET.ParseError:
        return []
    for el in root.iter():
        binding = next((c.text for c in el if c.tag.rsplit("}", 1)[-1] == "binding"), None) or ""
        if not binding.startswith(prefix):
            continue
        config = {}
        for c in (c for c in el if c.tag.rsplit("}", 1)[-1] == "configData"):
            parts = {p.tag.rsplit("}", 1)[-1]: p.text for p in c}
            config[parts.get("optionName")] = parts.get("value")
        view = next((c.text for c in el if c.tag.rsplit("}", 1)[-1] == "viewUUID"), "")
        out.append({"path": binding[len(prefix):], "viewUUID": view, "label": (config.get("@label") or "").strip(), "config": config,
                    "controlId": next((c.text for c in el if c.tag.rsplit("}", 1)[-1] == "layoutItemId"), "")})
    return out


def fields_fingerprint(fields):
    """fields: layout_fields() of a View. Changes when a field is added, removed, moved, relabelled or swapped for
    another view; not when IDs, versions or other settings change."""
    text = "\n".join(f"{f['path']}|{f['viewUUID']}|{f['label']}" for f in fields)
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def read_fingerprint(view_text):
    """The fingerprint a build stored in a group View's description, or None for a View this module did not build."""
    m = re.search(r"<description>([^<]*)</description>", view_text)
    found = FINGERPRINT.search(html.unescape(m.group(1))) if m else None
    return found.group(1) if found else None


def changed_in_baw(view_text):
    """Whether someone changed a group View this module built: its fields no longer match the stored fingerprint, or
    the fingerprint itself is gone from its description. Call it only for a View at a group's own ID."""
    stored = read_fingerprint(view_text)
    return stored is None or stored != fields_fingerprint(layout_fields(view_text))


def option_name(path):
    return f"{path.replace('.', '_')}Visibility"


def option_label(label):
    """A visibility option's label as Coach Designer shows it: "<field label> visibility", shortened to LABEL_MAX
    characters. Longer labels, and long View descriptions, make BAW refuse the whole install (CWTBG0737E)."""
    text = f"{label} visibility"
    return text if len(text) <= LABEL_MAX else f"{label[:LABEL_MAX - len(' visibility') - 3].rstrip()}... visibility"


def bind_visibility(item, path, prefix="ns2"):
    """Bind a field view's visibility to the group's option for it (a dynamic config value, as Coach Designer saves it)."""
    config = (f"<{prefix}:configData><{prefix}:id>{uid()}</{prefix}:id><{prefix}:optionName>@visibility</{prefix}:optionName>"
              f"<{prefix}:value>tw.options.{option_name(path)}</{prefix}:value><{prefix}:valueType>dynamic</{prefix}:valueType></{prefix}:configData>")
    item = re.sub(rf"<{prefix}:configData><{prefix}:id>[^<]*</{prefix}:id><{prefix}:optionName>@visibility</{prefix}:optionName>.*?</{prefix}:configData>",
                  "", item, count=1)  # a field's own static visibility gives way to the option
    return item.replace(f"<{prefix}:viewUUID>", config + f"<{prefix}:viewUUID>", 1)


def top_level(items, prefix="ns2"):
    """A view layout's top-level items use the layoutItem tag and carry the xsi namespace."""
    out = []
    for item in items:
        item = re.sub(rf"^<{prefix}:contributions ", f"<{prefix}:layoutItem {XSI} ", item, count=1)
        out.append(re.sub(rf"</{prefix}:contributions>$", f"</{prefix}:layoutItem>", item))
    return "".join(out)


def group_view(acronym, name, variable, bo_ref, visibility_ref, fields, items, author="group_views"):
    """A group View: (view id, version, xml).

    fields: (path, kind, label, hideable) per field, in layout order. items: the View's layout items (ns2 prefix), built
    by the caller; each field view must bind to tw.businessData.<variable>.<path>, and the caller has already
    passed each hideable field's item through bind_visibility."""
    new_id = stable_ids(acronym, f"group/{name}")
    view_id, version = "64." + new_id(), uid()
    options = [(option_name(path), option_label(label), visibility_ref) for path, _, label, hideable in fields if hideable]
    description = (f"Reusable group of {len(fields)} fields. Place it on a coach bound to the {variable} variable; "
                   "each field's visibility option hides it there. Built by baw-dev-tools, fingerprint @FINGERPRINT@")
    xml = view_xml(view_id, version, escape(name, {'"': "&quot;"}), binding_ref=bo_ref, binding_name=variable, options=options, load=GROUP_JS,
                   change=GROUP_CHANGE_JS, emit_boundary=False, description=description, new_id=new_id, layout=top_level(items))
    xml = xml.replace("@FINGERPRINT@", fields_fingerprint(layout_fields(xml)), 1)
    return view_id, version, xml.replace("<lastModifiedBy>coach_views</lastModifiedBy>", f"<lastModifiedBy>{author}</lastModifiedBy>", 1)


def placement_options(fields, hide=(), readonly=False):
    """The config of a coach's ViewRef that places a group: hidden fields' options set to NONE, and READONLY as the
    placement's own visibility (the fields follow it)."""
    options = [(option_name(path), "NONE") for path, _, _, hideable in fields if hideable and path in hide]
    if readonly:
        options.append(("@visibility", '{"isResponsiveData":true,"values":[{"deviceConfigID":"LargeID","value":"READONLY"}]}'))
    return options


def preview_service(acronym, name, variable, bo_id, layout, ok_item, init_script, author="group_views"):
    """A client-side human service "<name>" that opens one coach (layout, a wrapped coach layout whose forward button
    has the layout item ID ok_item) after init_script, and ends. Its ID is the same in every build of the app, so a
    rebuild replaces it. Returns the package object (id, version, name, "process", xml) for coach_builder.write_twx's
    extra objects or an app's package."""
    pid, version, var_id = "1." + stable_ids(acronym, f"preview/{name}")(), uid(), "2056." + uid()
    service = {"name": name, "description": f"Shows the {name.removesuffix(' Preview')} group on its own."}
    steps = [("init", "Init", init_script), ("coach", name, (layout, {"ok": ok_item}))]
    flows = [("start", "init", None, "rightCenter", "leftCenter"), ("init", "coach", None, "rightCenter", "leftCenter"),
             ("coach", "end", "ok", "rightCenter", "leftCenter")]
    flow = coachflow(service, steps, flows, bo_id, var_id, variable)
    return pid, version, name, "process", service_xml(pid, version, bo_id, var_id, service, flow, variable, author)
