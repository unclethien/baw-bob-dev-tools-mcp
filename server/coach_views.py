"""
Coach View and managed file XML, shared by the coach screens and the widget toolkits.

The hand-written screens from coach-ui/ live in one generic Coach View per business object,
"Coach Screen (<object>)", which mounts any screen registered in the coach-screens.js bundle. Its configuration options pick the screen, theme and fields (or a
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

VIEW_NAME = "Coach Screen"
ASSETS = [("coach-screens.js", "application/javascript"), ("coach-screens.css", "text/css")]

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
this._ppScreen = window.CoachScreens.mount(this.context.element, option("screen", ""), {
  options: { theme: JSON.parse(option("theme", "{}")), fields: JSON.parse(option("fields", "[]")), spec: JSON.parse(option("spec", "null")) },
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


def managed_asset_xml(asset_id, version, name, asset_uuid, mime, length, guid=None):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><managedAsset id="{asset_id}" name="{name}"><lastModified>0</lastModified><lastModifiedBy>coach_views</lastModifiedBy><tenantId isNull="true" />
<managedAssetId>{asset_id}</managedAssetId><assetUuid>{asset_uuid}</assetUuid><mimeType>{mime}</mimeType><charEncoding isNull="true" />
<assetTypeCode>W</assetTypeCode><length>{length}</length><localLastModification>0</localLastModification><description isNull="true" />
<isDocumentationFile>false</isDocumentationFile><guid>{guid or uid()}</guid><versionId>{version}</versionId></managedAsset></teamworks>
"""


def view_xml(view_id, version, name, *, binding_ref=None, options=(), asset_ids=(), load="", change="", unload="",
             description="", palette_icon=None, preview_html=None, preview_js=None, has_label=False, emit_boundary=True, new_id=None):
    """Coach View object XML. options: (name, label, class ref) or (name, label, class ref, is list) config options.
    palette_icon, preview_html and preview_js are managed file IDs (61.*) for Coach Designer.
    new_id makes the IDs and guids inside the view (a toolkit keeps them across builds); versionIds are always new."""
    new_id = new_id or uid
    def config_option(opt, label, class_ref, seq, is_list=False):
        return (f'<configOption name="{opt}">{BOOKKEEPING}<coachViewConfigOptionId>66.{new_id()}</coachViewConfigOptionId><coachViewId>{view_id}</coachViewId>'
                f"<isList>{str(is_list).lower()}</isList><propertyType>OBJECT</propertyType><label>{escape(label)}</label><classId>{class_ref}</classId>"
                f'<processId isNull="true" /><actionflowId isNull="true" /><isAdaptive>false</isAdaptive><seq>{seq}</seq><description isNull="true" />'
                f'<groupName isNull="true" /><guid>{new_id()}</guid><versionId>{uid()}</versionId></configOption>')

    def inline_script(script, kind, seq):
        return (f'<inlineScript name="{script}">{BOOKKEEPING}<coachViewInlineScriptId>68.{new_id()}</coachViewInlineScriptId><coachViewId>{view_id}</coachViewId>'
                f'<scriptType>{kind}</scriptType><scriptBlock isNull="true" /><seq>{seq}</seq><description isNull="true" /><guid>{new_id()}</guid><versionId>{uid()}</versionId></inlineScript>')

    def resource(asset_id, seq):
        return (f"<resource>{BOOKKEEPING}<coachViewResourceId>67.{new_id()}</coachViewResourceId><coachViewId>{view_id}</coachViewId>"
                f'<filePath isNull="true" /><ieCondition isNull="true" /><mediaQuery isNull="true" /><scriptLoadStyle isNull="true" />'
                f"<assetUuid>/{asset_id}</assetUuid><seq>{seq}</seq><guid>{new_id()}</guid><versionId>{uid()}</versionId></resource>")

    def asset(tag, asset_id):
        return f"<{tag}>/{asset_id}</{tag}>" if asset_id else f'<{tag} isNull="true" />'

    def script(tag, js):
        return f"<{tag}>{escape(js)}</{tag}>" if js else f'<{tag} isNull="true" />'

    binding = (f'<bindingType name="data">{BOOKKEEPING}<coachViewBindingTypeId>65.{new_id()}</coachViewBindingTypeId><coachViewId>{view_id}</coachViewId><isList>false</isList>\n'
               f'<classId>{binding_ref}</classId><seq>0</seq><description isNull="true" /><guid>{new_id()}</guid><versionId>{uid()}</versionId></bindingType>') if binding_ref else ""
    empty_layout = escape('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><ns2:layout xmlns:ns2="http://www.ibm.com/bpm/CoachDesignerNG" xmlns:ns3="http://www.ibm.com/bpm/coachview"/>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><coachView id="{view_id}" name="{name}"><lastModified>0</lastModified><lastModifiedBy>coach_views</lastModifiedBy><tenantId isNull="true" />
<coachViewId>{view_id}</coachViewId><isTemplate>false</isTemplate><layout>{empty_layout}</layout>{asset("paletteIcon", palette_icon)}<previewImage isNull="true" />
<hasLabel>{str(has_label).lower()}</hasLabel><labelPosition>0</labelPosition><nineSliceX1Coord>0</nineSliceX1Coord><nineSliceX2Coord>0</nineSliceX2Coord><nineSliceY1Coord>0</nineSliceY1Coord><nineSliceY2Coord>0</nineSliceY2Coord>
<emitBoundary>{str(emit_boundary).lower()}</emitBoundary><isPrototypeFunc>false</isPrototypeFunc><enableDevMode>false</enableDevMode><isMobileReady>true</isMobileReady>
{script("loadJsFunction", load)}{script("unloadJsFunction", unload)}<viewJsFunction isNull="true" />
{script("changeJsFunction", change)}<collaborationJsFunction isNull="true" />
<description>{escape(description)}</description>
<validateJsFunction isNull="true" />{asset("previewAdvHtml", preview_html)}{asset("previewAdvJs", preview_js)}<useUrlBinding>false</useUrlBinding>
<guid>{new_id()}</guid><versionId>{version}</versionId><field1 isNull="true" /><field2 isNull="true" /><field3>0</field3><field4 isNull="true" /><field5>false</field5><clobField1 isNull="true" />
{binding}
{"".join(config_option(o[0], o[1], o[2], i, *o[3:]) for i, o in enumerate(options))}
{"".join(resource(a, i) for i, a in enumerate(asset_ids))}
{inline_script("Inline CSS", "CSS", 0)}{inline_script("Inline Javascript", "JS", 1)}{inline_script("Header HTML", "HTML", 2)}
</coachView></teamworks>
"""


def coach_view_xml(view_id, version, bo_ref, string_type_ref, asset_ids, name=VIEW_NAME):
    return view_xml(view_id, version, name, binding_ref=bo_ref, asset_ids=asset_ids, load=LOAD_JS, change=CHANGE_JS, unload=UNLOAD_JS,
                    options=[("screen", "Screen", string_type_ref), ("theme", "Theme", string_type_ref),
                             ("fields", "Fields (JSON)", string_type_ref), ("spec", "Screen spec (JSON)", string_type_ref)],
                    description="Renders a screen from the coach-screens.js managed file. Options: screen (registered screen name), theme (JSON: the app's theme file), fields (JSON list of sections and fields), spec (JSON screen spec for the form screen).")


def screen_assets(bundle_dir: Path, existing=None):
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


def screen_view(asset_ids, bo_ref, string_type_ref, name=VIEW_NAME):
    """A screen Coach View bound to bo_ref: (view id, package entry, {zip path: bytes})."""
    view_id, view_version = "64." + uid(), uid()
    entry = f'<object id="{view_id}" versionId="{view_version}" name="{escape(name)}" type="coachView"/>'
    return view_id, entry, {f"objects/{view_id}.xml": coach_view_xml(view_id, view_version, bo_ref, string_type_ref, asset_ids, escape(name))}
