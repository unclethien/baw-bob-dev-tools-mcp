#!/usr/bin/env python3
"""
Shared building blocks for generating BAW process apps (.twx) from Python.

- Layout builds CoachDesignerNG coach layouts from UI Toolkit views and Custom HTML.
- coachflow builds a client-side human service flow (scripts, coaches, button wiring).
- service_xml and business_object_xml produce the object XML that BAW installs.
- write_twx packages the objects with the metadata and toolkits of an exported base app.

Every object gets fresh IDs and versionIds, so BAW never keeps old content on install.
"""

import re
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

TWSYS = "7692552a-ea18-49ce-bd93-a1dd62100cd9"
SYSTEM_TYPES = {
    "String": "12.db884a3c-c533-44b7-bb2d-47bec8ad4022",
    "Date": "12.68474ab0-d56f-47ee-b7e9-510b45a2a8be",
    "Boolean": "12.83ff975e-8dbc-42e5-b738-fa8bc08274a2",
    "Integer": "12.3fa0d7a0-828a-4d60-99cc-db5ed143fc2d",
    "Decimal": "12.536b2aa5-a30f-4eca-87fa-3a28066753ee",
}
ALL_USERS = "24.da7e4d23-78cb-4483-98ed-b9c238308a03"
VIEWS = {
    "Panel": "64.455e44ab-b77b-4337-b3f9-435e234fb569",
    "Tab Section": "64.c05b439f-a4bd-48b0-8644-fa3b59052217",
    "Vertical Layout": "64.ef447b87-24a2-42a7-b2b9-cd471e9f7b67",
    "Horizontal Layout": "64.44f463cc-615b-43d0-834f-c398a82e0363",
    "Text": "64.5663dd71-ff18-4d33-bea0-468d0b869816",
    "Text Area": "64.0e61869e-73fd-4401-b156-8c11adaec3f8",
    "Date Time Picker": "64.54643ff2-8363-4976-bb5e-d4eb1094cca3",
    "Checkbox": "64.fffd1628-baee-44e8-b7ca-5ae48644b0be",
    "Output Text": "64.f634f22e-7800-4bd7-9f1e-87177acfb3bc",
    "Button": "64.7133c7d4-1a54-45c8-89cd-a8e8fa4a8e36",
    "Integer": "64.a6946c4c-f73d-4ced-9216-90018985ca96",
    "Decimal": "64.e0ede0f2-f3af-408c-af7b-e7a58eb5e2b4",
}


def uid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------- coach layout


class Layout:
    """Builds CoachDesignerNG layout XML with unique, readable layout item IDs."""

    def __init__(self):
        self.counts = {}

    def _item_id(self, kind):
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return f"{kind.replace(' ', '_')}{self.counts[kind]}"

    @staticmethod
    def _config(options):
        out = []
        for name, value in options:
            val = "<ns19:value />" if value in (None, "") else f"<ns19:value>{escape(value)}</ns19:value>"
            out.append(f"<ns19:configData><ns19:id>{uid()}</ns19:id><ns19:optionName>{name}</ns19:optionName>{val}</ns19:configData>")
        return "".join(out)

    def view(self, kind, label="", binding=None, children=None, options=(), show_label=True, item_id=None, tag="contributions", view_uuid=None):
        item_id = item_id or self._item_id(kind)
        config = [("@label", label), ("@helpText", ""), ("@labelVisibility", "SHOW" if show_label else "HIDE"), *options]
        xml = f'<ns19:{tag} xsi:type="ns19:ViewRef" version="8550"><ns19:id>{uid()}</ns19:id><ns19:layoutItemId>{item_id}</ns19:layoutItemId>'
        xml += self._config(config) + f"<ns19:viewUUID>{view_uuid or VIEWS[kind]}</ns19:viewUUID>"
        if binding:
            xml += f"<ns19:binding>{binding}</ns19:binding>"
        if children is not None:
            xml += f"<ns19:contentBoxContrib><ns19:id>{uid()}</ns19:id><ns19:contentBoxId>ContentBox1</ns19:contentBoxId>{''.join(children)}</ns19:contentBoxContrib>"
        return xml + f"</ns19:{tag}>"

    def html(self, content, tag="contributions"):
        item_id = self._item_id("CustomHTML")
        return (f'<ns19:{tag} xsi:type="ns19:CustomHTML" version="8550"><ns19:id>{uid()}</ns19:id><ns19:layoutItemId>{item_id}</ns19:layoutItemId>'
                + self._config([("@customHTML.contentType", "TEXT"), ("@customHTML.textContent", content)]) + f"</ns19:{tag}>")

    def button(self, label, primary=False):
        item_id = self._item_id("Button")
        return item_id, self.view("Button", label, item_id=item_id, options=[("colorStyle", "P" if primary else "D")], show_label=False)

    @staticmethod
    def wrap(items):
        """Top-level items use the layoutItem tag and carry the xsi namespace."""
        tops = [re.sub(r"^<ns19:contributions ", '<ns19:layoutItem xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ', i, count=1) for i in items]
        tops = [re.sub(r"</ns19:contributions>$", "</ns19:layoutItem>", i) for i in tops]
        return "<ns19:layout>" + "".join(tops) + "</ns19:layout>"


LINK_VISUAL = ("<ns13:linkVisualInfo><ns13:sourcePortLocation>{src}</ns13:sourcePortLocation><ns13:targetPortLocation>{dst}</ns13:targetPortLocation>"
               "<ns13:showLabel>false</ns13:showLabel><ns13:showCoachControlLabel>{ctl}</ns13:showCoachControlLabel><ns13:labelPosition>0.0</ns13:labelPosition>"
               "<ns13:saveExecutionContext>false</ns13:saveExecutionContext></ns13:linkVisualInfo>")


def coachflow(service, steps, flows, bo_id, var_id, var):
    """Build the BPMN for a client-side human service.

    steps: (key, name, script text | (coach layout, {event: button item id})) in diagram order.
    flows: (source, target, coach event or None, source port, target port); "start" and "end" are implicit.
    """
    ids = {"start": uid(), "end": uid(), **{key: "2025." + uid() for key, _, _ in steps}}
    flow_ids = ["2027." + uid() for _ in flows]
    incoming = lambda node: "".join(f"<ns16:incoming>{flow_ids[i]}</ns16:incoming>" for i, f in enumerate(flows) if f[1] == node)
    outgoing = lambda node: "".join(f"<ns16:outgoing>{flow_ids[i]}</ns16:outgoing>" for i, f in enumerate(flows) if f[0] == node)
    end_x = 110 + 150 * len(steps)
    nvi = lambda i: f'<ns13:nodeVisualInfo x="{110 + 150 * i}" y="182" width="95" height="70" />'
    buttons = {event: item for _, _, content in steps if isinstance(content, tuple) for event, item in content[1].items()}

    def step_xml(i, key, name, content):
        head = f"<ns16:extensionElements>{nvi(i)}</ns16:extensionElements>{incoming(key)}{outgoing(key)}"
        if isinstance(content, tuple):
            return (f'<ns2:formTask name="{name}" id="{ids[key]}">{head}'
                    f"<ns2:formDefinition><ns19:coachDefinition>{content[0]}</ns19:coachDefinition></ns2:formDefinition></ns2:formTask>")
        default = next(flow_ids[j] for j, f in enumerate(flows) if f[0] == key)
        return (f'<ns16:scriptTask scriptFormat="text/x-javascript" default="{default}" name="{name}" id="{ids[key]}">'
                f"{head}<ns16:script>{escape(content)}</ns16:script></ns16:scriptTask>")

    def sequence_flow(i, src, dst, event, sp, tp):
        binding = f"<ns2:coachEventBinding id=\"{uid()}\"><ns2:coachEventPath>{buttons[event]}</ns2:coachEventPath></ns2:coachEventBinding>" if event else ""
        visual = LINK_VISUAL.format(src=sp, dst=tp, ctl="true" if event else "false")
        return (f'<ns16:sequenceFlow sourceRef="{ids[src]}" targetRef="{ids[dst]}" name="{event or ""}" id="{flow_ids[i]}">'
                f"<ns16:extensionElements>{visual}{binding}</ns16:extensionElements></ns16:sequenceFlow>")

    body = (
        f'<ns16:startEvent name="Start" id="{ids["start"]}"><ns16:extensionElements><ns13:nodeVisualInfo x="40" y="205" width="24" height="24" color="#F8F8F8" /></ns16:extensionElements>{outgoing("start")}</ns16:startEvent>'
        f'<ns16:endEvent name="End" id="{ids["end"]}"><ns16:extensionElements><ns13:nodeVisualInfo x="{end_x}" y="205" width="24" height="24" color="#F8F8F8" />'
        f"<ns2:navigationInstructions><ns2:targetType>Default</ns2:targetType></ns2:navigationInstructions></ns16:extensionElements>{incoming('end')}</ns16:endEvent>"
        + "".join(step_xml(i, *step) for i, step in enumerate(steps))
        + "".join(sequence_flow(i, *f) for i, f in enumerate(flows))
        + f'<ns16:dataObject itemSubjectRef="itm.{bo_id}" isCollection="false" name="{var}" id="{var_id}" />'
        + f'<ns2:htmlHeaderTag id="{uid()}"><ns2:tagName>viewport</ns2:tagName><ns2:content>width=device-width,initial-scale=1.0</ns2:content><ns2:enabled>true</ns2:enabled></ns2:htmlHeaderTag>'
    )
    ns = " ".join(f'xmlns:ns{n}="{u}"' for n, u in [
        (16, "http://www.omg.org/spec/BPMN/20100524/MODEL"), (2, "http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process"),
        (13, "http://www.ibm.com/xmlns/prod/bpm/graph"), (19, "http://www.ibm.com/bpm/CoachDesignerNG")])
    return (f'<coachflow><ns16:definitions {ns} id="{uid()}" targetNamespace="" expressionLanguage="http://www.ibm.com/xmlns/prod/bpm/expression-lang/javascript">'
            f'<ns16:globalUserTask name="{service["name"]}" id="1.{uid()}"><ns16:documentation>{service["description"]}</ns16:documentation>'
            f'<ns16:extensionElements><ns2:userTaskImplementation id="{uid()}">{body}</ns2:userTaskImplementation>'
            f"<ns2:mobileReady>true</ns2:mobileReady><ns2:participantRef>{ALL_USERS}</ns2:participantRef><ns2:exposedAs>URL</ns2:exposedAs></ns16:extensionElements>"
            "<ns16:ioSpecification><ns16:inputSet /><ns16:outputSet /></ns16:ioSpecification></ns16:globalUserTask></ns16:definitions></coachflow>")


ITEM = """<item><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><processItemId>{item_id}</processItemId><processId>{pid}</processId>
<name>{name}</name><tWComponentName>{component}</tWComponentName><tWComponentId>{component_id}</tWComponentId><isLogEnabled>false</isLogEnabled><isTraceEnabled>false</isTraceEnabled>
<traceCategory isNull="true" /><traceLevel isNull="true" /><traceMessage isNull="true" /><traceSymbolTable isNull="true" /><isExecutionContextTraced>false</isExecutionContextTraced>
<saveExecutionContext>true</saveExecutionContext><documentation isNull="true" /><isErrorHandlerEnabled>false</isErrorHandlerEnabled><errorHandlerItemId isNull="true" />
<guid>{guid}</guid><versionId>{version}</versionId><externalServiceRef isNull="true" /><externalServiceOp isNull="true" /><nodeColor isNull="true" />
<layoutData x="{x}" y="100"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>{component_xml}</item>"""

NO_LINK_LAYOUT = "<layoutData><controlPoints /><showEndState>false</showEndState><showName>false</showName></layoutData>"


def service_xml(pid, version, bo_id, var_id, service, flow, var, author):
    wrapper, end = "2025." + uid(), "2025." + uid()
    exit_id = "3008." + uid()
    items = ITEM.format(item_id=wrapper, pid=pid, name="CoachFlowWrapper", component="CoachFlow", component_id="3032." + uid(),
                        guid=uid(), version=uid(), x=0, component_xml="<TWComponent />")
    items += ITEM.format(item_id=end, pid=pid, name="End", component="ExitPoint", component_id=exit_id, guid=uid(), version=uid(), x=700,
                         component_xml=f'<TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><exitPointId>{exit_id}</exitPointId>'
                                       f"<haltProcess>false</haltProcess><guid>{uid()}</guid><versionId>{uid()}</versionId></TWComponent>")
    variable = (f'<processVariable name="{var}"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />'
                f'<processVariableId>{var_id}</processVariableId><description isNull="true" /><processId>{pid}</processId><namespace>2</namespace><seq>1</seq>'
                f"<isArrayOf>false</isArrayOf><isTransient>false</isTransient><classId>/{bo_id}</classId><hasDefault>false</hasDefault>"
                f'<defaultValue isNull="true" /><guid>{uid()}</guid><versionId>{uid()}</versionId></processVariable>')
    link = (f'<link name="Untitled"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><processLinkId>2027.{uid()}</processLinkId>'
            f'<processId>{pid}</processId><description isNull="true" /><fromProcessItemId>{wrapper}</fromProcessItemId><endStateId>Out</endStateId>'
            f"<toProcessItemId>{end}</toProcessItemId><guid>{uid()}</guid><versionId>{uid()}</versionId>{NO_LINK_LAYOUT}"
            f'<fromItemPort locationId="rightCenter" portType="1" /><toItemPort locationId="rightCenter" portType="2" />'
            f"<fromProcessItemId>{wrapper}</fromProcessItemId><toProcessItemId>{end}</toProcessItemId></link>")
    null = lambda *names: "".join(f'<{n} isNull="true" />' for n in names)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><process id="{pid}" name="{service["name"]}"><lastModified>0</lastModified><lastModifiedBy>{author}</lastModifiedBy>{null("tenantId")}
<processId>{pid}</processId>{null("image", "tabGroup")}<startingProcessItemId>{wrapper}</startingProcessItemId><isRootProcess>false</isRootProcess><processType>10</processType>
<isErrorHandlerEnabled>false</isErrorHandlerEnabled>{null("errorHandlerItemId")}<isLoggingVariables>false</isLoggingVariables><isTransactional>false</isTransactional>{null("processTimingLevel")}
<participantRef>{TWSYS}/{ALL_USERS}</participantRef><exposedType>4</exposedType><isTrackingEnabled>true</isTrackingEnabled>{null("xmlData")}<cachingType>false</cachingType>
{null("itemLabel", "cacheLength")}<mobileReady>true</mobileReady><sboSyncEnabled>true</sboSyncEnabled>{null("externalId")}<isSecured>false</isSecured><isAjaxExposed>false</isAjaxExposed>
<isInvokedAsynchronously>false</isInvokedAsynchronously><isTransactionalFlow>false</isTransactionalFlow><description>{service["description"]}</description>
<guid>{uid()}</guid><versionId>{version}</versionId>{null("dependencySummary", "jsonData", "businessDataAliases", "field1", "field2")}<field3>0</field3>{null("field4")}<field5>false</field5>
{null("clobField1", "blobField1")}{variable}{items}<startingProcessItemId>{wrapper}</startingProcessItemId>{null("errorHandlerItemId")}
<layoutData noConversion="true"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
<startPoint><layoutData x="20" y="100"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData></startPoint>
<startLink><fromPort locationId="rightCenter" portType="1" /><toPort locationId="rightCenter" portType="2" />{NO_LINK_LAYOUT}</startLink>
{flow}{link}</process></teamworks>
"""


def business_object_xml(template, bo_id, version, name, props):
    """Reuse a base-app business object as the template so every bookkeeping element matches the server's format.

    props: (property name, system type name) pairs, e.g. ("employeeName", "String").
    """
    head, rest = template.split("<property>", 1)
    prop_tpl = "<property>" + rest.split("</property>", 1)[0] + "</property>"
    tail = template[template.rindex("</property>") + len("</property>"):]
    old_id = re.search(r'<twClass id="([^"]+)"', head).group(1)
    old_name = re.search(r'<twClass id="[^"]+" name="([^"]+)"', head).group(1)
    head = head.replace(old_id, bo_id).replace(f'name="{old_name}"', f'name="{name}"')
    head = re.sub(r"<versionId>[^<]+</versionId>", f"<versionId>{version}</versionId>", head)
    head = re.sub(r"<guid>[^<]+</guid>", f"<guid>guid:{uid()}</guid>", head)
    head = re.sub(r"<description>.*?</description>", '<description isNull="true" />', head, flags=re.S)
    tail = tail.replace(f'simpleType name="{old_name}"', f'simpleType name="{name}"')
    body = "".join(
        re.sub(r"<classRef>[^<]+</classRef>", f"<classRef>{TWSYS}/{SYSTEM_TYPES[t]}</classRef>",
               re.sub(r"<name>[^<]+</name>", f"<name>{p}</name>", prop_tpl, count=1))
        for p, t in props)
    return head + body + tail


def write_twx(base: Path, dest: Path, bo: dict, var: str, services, author: str):
    """Package a new process app from an exported base app.

    The base app supplies META-INF metadata, its environment variables, project defaults and the
    System Data / UI Toolkit dependencies; its own objects are dropped.
    bo: {"id", "version", "name", "props"}. services: (pid, versionId, variable id, {"name", "description"}, flow(bo_id, var_id)).
    """
    with zipfile.ZipFile(base) as src:
        package = src.read("META-INF/package.xml").decode("utf-8")
        objects = re.findall(r'<object id="([^"]+)" versionId="[^"]+" name="[^"]*" type="([^"]+)"/>', package)
        keep = [oid for oid, typ in objects if typ in ("environmentVariableSet", "projectDefaults")]
        bo_template = next(src.read(f"objects/{oid}.xml").decode("utf-8") for oid, typ in objects if typ == "twClass")
        kept_entries = [e for e in re.findall(r"\s*<object [^>]+/>", package) if any(f'id="{k}"' in e for k in keep)]
        new_entries = [f'\n        <object id="{pid}" versionId="{version}" name="{escape(service["name"])}" type="process"/>' for pid, version, _, service, _ in services]
        new_entries += [f'\n        <object id="{bo["id"]}" versionId="{bo["version"]}" name="{bo["name"]}" type="twClass"/>']
        package = re.sub(r"<objects>.*</objects>", "<objects>" + "".join(new_entries + kept_entries) + "\n    </objects>", package, flags=re.S)
        package = re.sub(r"<files>.*</files>", "<files/>", package, flags=re.S)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
            for info in src.infolist():
                name = info.filename
                if name == "META-INF/package.xml":
                    out.writestr(name, package)
                elif name.startswith(("META-INF/", "toolkits/")) or any(name == f"objects/{k}.xml" for k in keep):
                    out.writestr(name, src.read(name))
            out.writestr(f"objects/{bo['id']}.xml", business_object_xml(bo_template, bo["id"], bo["version"], bo["name"], bo["props"]))
            for pid, version, var_id, service, flow in services:
                out.writestr(f"objects/{pid}.xml", service_xml(pid, version, bo["id"], var_id, service, flow(bo["id"], var_id), var, author))
