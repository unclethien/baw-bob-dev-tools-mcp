"""
BAW objects that host the React screens from react-coach/ inside a coach.

One generic Coach View, "PP React Screen", mounts any screen registered in the
pp-react.js bundle. Its configuration options pick the screen, theme and fields (or a
whole screen spec), and its binding is the screen's business object. A screen can
fire the view's own boundary event, so a coach flow wires it exactly like a button,
or click one of the coach's original buttons (kept in the coach but hidden), so the
existing flow wiring keeps working. The bundle and its stylesheet ship as web
managed files attached to the view as resources.

Element order and bookkeeping fields follow views exported from BAW 26.0.0.
"""

import uuid
from pathlib import Path
from xml.sax.saxutils import escape

VIEW_NAME = "PP React Screen"
ASSETS = [("pp-react.js", "application/javascript"), ("pp-react.css", "text/css")]

LOAD_JS = """var view = this;
function data() { return view.context.binding ? view.context.binding.get("value") : null; }
function option(name, fallback) {
  var opt = view.context.options[name];
  return (opt && opt.get("value")) || fallback;
}
function step(obj, key) { return obj == null ? undefined : obj.get ? obj.get(key) : obj[key]; }
function parent(path) {
  var keys = String(path).split("."), obj = data();
  for (var i = 0; i < keys.length - 1; i++) obj = step(obj, keys[i]);
  return { obj: obj, key: keys[keys.length - 1] };
}
this._ppData = data;
this._ppBind = function () {
  if (view._ppBound) view._ppBound.unbind();
  var bound = data();
  view._ppBound = bound && bound.bindAll ? bound.bindAll(function () { view._ppScreen.update(); }) : null;
};
this._ppScreen = window.PPReact.mount(this.context.element, option("screen", "form"), {
  options: { theme: option("theme", "brand"), fields: JSON.parse(option("fields", "[]")), spec: JSON.parse(option("spec", "null")) },
  read: function (path) { var p = parent(path); return step(p.obj, p.key); },
  write: function (path, value) {
    var p = parent(path);
    if (p.obj == null) return;
    if (p.obj.set) p.obj.set(p.key, value); else p.obj[p.key] = value;
  },
  boundary: function () { view.context.trigger(); },
  fire: function (viewId) {
    var host = view.context.element.ownerDocument.querySelector('[data-viewid="' + viewId + '"]');
    var button = host && (host.querySelector("button") || host);
    if (button) button.click();
  }
});
this._ppBind();"""

CHANGE_JS = """if (event.type !== "config" && this._ppBind) this._ppBind();
if (this._ppScreen) this._ppScreen.update();"""

UNLOAD_JS = """if (this._ppBound) this._ppBound.unbind();
if (this._ppScreen) this._ppScreen.unmount();"""

BOOKKEEPING = '<lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />'


def uid():
    return str(uuid.uuid4())


def managed_asset_xml(asset_id, version, name, asset_uuid, mime, length):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><managedAsset id="{asset_id}" name="{name}"><lastModified>0</lastModified><lastModifiedBy>react_coach_view</lastModifiedBy><tenantId isNull="true" />
<managedAssetId>{asset_id}</managedAssetId><assetUuid>{asset_uuid}</assetUuid><mimeType>{mime}</mimeType><charEncoding isNull="true" />
<assetTypeCode>W</assetTypeCode><length>{length}</length><localLastModification>0</localLastModification><description isNull="true" />
<isDocumentationFile>false</isDocumentationFile><guid>{uid()}</guid><versionId>{version}</versionId></managedAsset></teamworks>
"""


def coach_view_xml(view_id, version, bo_ref, string_type_ref, asset_ids, name=VIEW_NAME):
    def config_option(name, label, seq):
        return (f'<configOption name="{name}">{BOOKKEEPING}<coachViewConfigOptionId>66.{uid()}</coachViewConfigOptionId><coachViewId>{view_id}</coachViewId>'
                f"<isList>false</isList><propertyType>OBJECT</propertyType><label>{label}</label><classId>{string_type_ref}</classId>"
                f'<processId isNull="true" /><actionflowId isNull="true" /><isAdaptive>false</isAdaptive><seq>{seq}</seq><description isNull="true" />'
                f'<groupName isNull="true" /><guid>{uid()}</guid><versionId>{uid()}</versionId></configOption>')

    def inline_script(name, kind, seq):
        return (f'<inlineScript name="{name}">{BOOKKEEPING}<coachViewInlineScriptId>68.{uid()}</coachViewInlineScriptId><coachViewId>{view_id}</coachViewId>'
                f'<scriptType>{kind}</scriptType><scriptBlock isNull="true" /><seq>{seq}</seq><description isNull="true" /><guid>{uid()}</guid><versionId>{uid()}</versionId></inlineScript>')

    def resource(asset_id, seq):
        return (f"<resource>{BOOKKEEPING}<coachViewResourceId>67.{uid()}</coachViewResourceId><coachViewId>{view_id}</coachViewId>"
                f'<filePath isNull="true" /><ieCondition isNull="true" /><mediaQuery isNull="true" /><scriptLoadStyle isNull="true" />'
                f"<assetUuid>/{asset_id}</assetUuid><seq>{seq}</seq><guid>{uid()}</guid><versionId>{uid()}</versionId></resource>")

    empty_layout = escape('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns2:layout xmlns:ns2="http://www.ibm.com/bpm/CoachDesignerNG" xmlns:ns3="http://www.ibm.com/bpm/coachview"/>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><coachView id="{view_id}" name="{name}"><lastModified>0</lastModified><lastModifiedBy>react_coach_view</lastModifiedBy><tenantId isNull="true" />
<coachViewId>{view_id}</coachViewId><isTemplate>false</isTemplate><layout>{empty_layout}</layout><paletteIcon isNull="true" /><previewImage isNull="true" />
<hasLabel>false</hasLabel><labelPosition>0</labelPosition><nineSliceX1Coord>0</nineSliceX1Coord><nineSliceX2Coord>0</nineSliceX2Coord><nineSliceY1Coord>0</nineSliceY1Coord><nineSliceY2Coord>0</nineSliceY2Coord>
<emitBoundary>true</emitBoundary><isPrototypeFunc>false</isPrototypeFunc><enableDevMode>false</enableDevMode><isMobileReady>true</isMobileReady>
<loadJsFunction>{escape(LOAD_JS)}</loadJsFunction><unloadJsFunction>{escape(UNLOAD_JS)}</unloadJsFunction><viewJsFunction isNull="true" />
<changeJsFunction>{escape(CHANGE_JS)}</changeJsFunction><collaborationJsFunction isNull="true" />
<description>Renders a React screen from the pp-react.js managed file. Options: screen (registered screen name), theme (brand or carbon), fields (JSON list of sections and fields), spec (JSON screen spec for the form screen).</description>
<validateJsFunction isNull="true" /><previewAdvHtml isNull="true" /><previewAdvJs isNull="true" /><useUrlBinding>false</useUrlBinding>
<guid>{uid()}</guid><versionId>{version}</versionId><field1 isNull="true" /><field2 isNull="true" /><field3>0</field3><field4 isNull="true" /><field5>false</field5><clobField1 isNull="true" />
<bindingType name="data">{BOOKKEEPING}<coachViewBindingTypeId>65.{uid()}</coachViewBindingTypeId><coachViewId>{view_id}</coachViewId><isList>false</isList>
<classId>{bo_ref}</classId><seq>0</seq><description isNull="true" /><guid>{uid()}</guid><versionId>{uid()}</versionId></bindingType>
{config_option("screen", "Screen", 0)}{config_option("theme", "Theme", 1)}{config_option("fields", "Fields (JSON)", 2)}{config_option("spec", "Screen spec (JSON)", 3)}
{"".join(resource(a, i) for i, a in enumerate(asset_ids))}
{inline_script("Inline CSS", "CSS", 0)}{inline_script("Inline Javascript", "JS", 1)}{inline_script("Header HTML", "HTML", 2)}
</coachView></teamworks>
"""


def react_assets(bundle_dir: Path, existing=None):
    """Managed files for the bundle: (asset ids, package entries, {zip path: bytes}).

    existing maps a file name to (asset id, asset uuid, version) for managed files the app
    already has; those keep their IDs and only get new content, so names stay unique.
    """
    existing = existing or {}
    entries, files, asset_ids = [], {}, []
    for name, mime in ASSETS:
        data = (bundle_dir / name).read_bytes()
        asset_id, asset_uuid, asset_version = existing.get(name) or ("61." + uid(), uid(), uid())
        asset_ids.append(asset_id)
        if name not in existing:
            entries.append((f'<object id="{asset_id}" versionId="{asset_version}" name="{name}" type="managedAsset"/>',
                            f'<file path="{asset_uuid}" id="{asset_id}"/>'))
        files[f"objects/{asset_id}.xml"] = managed_asset_xml(asset_id, asset_version, name, asset_uuid, mime, len(data))
        files[f"files/{asset_id}/{asset_uuid}"] = data
    return asset_ids, entries, files


def react_view(asset_ids, bo_ref, string_type_ref, name=VIEW_NAME):
    """A React Coach View bound to bo_ref: (view id, package entry, {zip path: bytes})."""
    view_id, view_version = "64." + uid(), uid()
    entry = f'<object id="{view_id}" versionId="{view_version}" name="{escape(name)}" type="coachView"/>'
    return view_id, entry, {f"objects/{view_id}.xml": coach_view_xml(view_id, view_version, bo_ref, string_type_ref, asset_ids, escape(name))}


def react_objects(bundle_dir: Path, bo_ref, string_type_ref):
    """Return (view_id, package entries, {zip path: bytes}) for the view and its managed files."""
    asset_ids, entries, files = react_assets(bundle_dir)
    view_id, entry, view_files = react_view(asset_ids, bo_ref, string_type_ref)
    return view_id, entries + [(entry, None)], {**files, **view_files}
