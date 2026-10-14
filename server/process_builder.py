#!/usr/bin/env python3
"""
Build a business process definition (BPD): the workflow diagram users see, edit and start in BAW.

process_xml lays out lanes of nodes (start and end events, user tasks that open a client-side human
service, exclusive gateways) joined by sequence flows, with one private variable holding the app's
business object. Every user task passes that variable into its service and takes it back.

The XML is BAW's own BPD format (objects/25.*.xml in a .twx) carrying the same diagram twice: the
legacy BusinessProcessDiagram the runtime reads, and the BPMN 2 model (bpmn2Data) that Business
Automation Studio's web editor opens. Without the BPMN 2 model Studio lists the process as a BPD that
needs a one-way conversion before it can be edited.
"""

import itertools
import uuid
from xml.sax.saxutils import escape

from coach_builder import ALL_USERS, TWSYS

_count = itertools.count(1)
LANE_HEIGHT = 160
NODE_SIZE = {"start": (24, 24), "end": (24, 24), "task": (95, 70), "gateway": (40, 40)}
LANE_COLORS = ["#F8F8F8", "#F7DBDB"]  # Studio's colours for laneColor 0 and 1
BPMN_NS = {"ns6": "http://www.omg.org/spec/BPMN/20100524/MODEL", "ns2": "http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/wle",
           "ns3": "http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process", "ns4": "http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/case",
           "ns16": "http://www.ibm.com/xmlns/prod/bpm/graph", "xsi": "http://www.w3.org/2001/XMLSchema-instance"}


def bpd_id():
    h = uuid.uuid4().hex
    return f"bpdid:{h[:16]}:{h[16:24]}:{h[24:]}:-{next(_count)}"


def _event(kind):
    return (f"<component><nameVisible>true</nameVisible><eventType>{1 if kind == 'start' else 2}</eventType><cancelActivity>true</cancelActivity>"
            "<repeatable>false</repeatable><doCloseTask>true</doCloseTask></component>")


def _task(node, var, bo_id, team):
    service, (input_id, output_id) = node["service"], node["io"]
    mapping = lambda tag, src, dst, pid, extra="": (
        f'<{tag} id="{bpd_id()}"><mappingMode>basic</mappingMode><name>{var}</name><classId>/{bo_id}</classId>{extra}'
        f"<value>tw.local.{var}</value><sourcePath>{src}</sourcePath><targetPath>{dst}</targetPath><parameterId>{pid}</parameterId></{tag}>")
    subject = escape(node["name"])
    return ("<component><loopType>0</loopType><loopMaximum>1</loopMaximum><startQuantity>1</startQuantity><isAutoflowable>false</isAutoflowable>"
            "<MIOrdering>1</MIOrdering><MIFlowCondition>0</MIFlowCondition><cancelRemainingInstances>false</cancelRemainingInstances>"
            '<metricSettings itemType="4" /><implementationType>1</implementationType><isConditional>false</isConditional><bpmnTaskType>1</bpmnTaskType>'
            "<activityOptionType>REQUIRED</activityOptionType><activityExecutionType>NONE</activityExecutionType>"
            "<activityExecutionTypePreviousValue>AUTOMATIC</activityExecutionTypePreviousValue><isHidden>false</isHidden><isRepeatable>false</isRepeatable>"
            f"<narrative>{subject}</narrative><transactionalBehavior>0</transactionalBehavior><isRobotTask>false</isRobotTask>"
            f"<implementation><attachedActivityId>/{service}</attachedActivityId><sendToType>1</sendToType><taskRouting>0</taskRouting>"
            "<dueDateType>1</dueDateType><dueDateTime>1</dueDateTime><dueDateTimeResolution>1</dueDateTimeResolution><dueDateTimeTOD>00:00</dueDateTimeTOD>"
            f"<priorityType>0</priorityType><priority>30.30</priority><subject>{subject}</subject><narrative>{subject}</narrative><forceSend>true</forceSend>"
            "<timeSchedule>(use default)</timeSchedule><timeScheduleType>0</timeScheduleType><timeZone>(use default)</timeZone><timeZoneType>0</timeZoneType>"
            "<holidaySchedule>(use default)</holidaySchedule><holidayScheduleType>0</holidayScheduleType><isDueDateEnabled>true</isDueDateEnabled>"
            + mapping("inputActivityParameterMapping", f"tw.local.{var}", f"tw.inputs.{var}", input_id, "<input>true</input>")
            + mapping("outputActivityParameterMapping", f"tw.outputs.{var}", f"tw.local.{var}", output_id)
            + f'<laneFilter id="{bpd_id()}"><serviceType>1</serviceType><teamRef>{team}</teamRef></laneFilter>'
            f'<teamFilter id="{bpd_id()}"><serviceType>1</serviceType></teamFilter></implementation></component>')


def _gateway():
    return "<component><nameVisible>true</nameVisible><gatewayType>1</gatewayType><splitJoinType>0</splitJoinType></component>"


def process_xml(pid, version, name, var, bo_id, lanes, nodes, flows, author, description=""):
    """pid: "25.<uuid>". lanes: lane names, top to bottom.
    nodes: {"key", "kind" (start | end | task | gateway), "name", "lane", "x"}; a task also has
    "service" (the service's "1.<uuid>") and "io" (its input and output parameter ids).
    flows: {"from", "to", "name", "condition" (JavaScript, for a gateway's branch; the branch without one
    is the default), "out", "in" (port positions such as rightCenter, topCenter)}."""
    team = f"{TWSYS}/{ALL_USERS}"
    ids = {n["key"]: bpd_id() for n in nodes}
    flow_ids = [bpd_id() for _ in flows]
    lane_ids, var_id, case_folder = [bpd_id() for _ in lanes], bpd_id(), str(uuid.uuid4())
    pool_id, start_scenario = bpd_id(), bpd_id()
    # Studio names an unnamed flow after its target.
    flows = [{**f, "label": f.get("name") or f"to {next(n['name'] for n in nodes if n['key'] == f['to'])}"} for f in flows]

    def ports(key):
        out = "".join(f'<inputPort id="{bpd_id()}"><positionId>{f.get("in", "leftCenter")}</positionId><input>true</input><flow ref="{flow_ids[i]}" /></inputPort>'
                      for i, f in enumerate(flows) if f["to"] == key)
        # A gateway's conditional branches come before its default one.
        mine = sorted((i for i, f in enumerate(flows) if f["from"] == key), key=lambda i: not flows[i].get("condition"))
        return out + "".join(f'<outputPort id="{bpd_id()}"><positionId>{flows[i].get("out", "rightCenter")}</positionId><flow ref="{flow_ids[i]}" /></outputPort>'
                             for i in mine)

    def flow_object(n):
        kind = n["kind"]
        component = _event(kind) if kind in ("start", "end") else _task(n, var, bo_id, team) if kind == "task" else _gateway()
        w, h = NODE_SIZE[kind]
        y = (LANE_HEIGHT - h) // 2
        ctype = {"start": "Event", "end": "Event", "task": "Activity", "gateway": "Gateway"}[kind]
        return (f'<flowObject id="{ids[n["key"]]}" componentType="{ctype}"><name>{escape(n["name"])}</name><documentation />'
                f'<position><location x="{n["x"]}" y="{y}" /></position><dropIconUrl>0</dropIconUrl><colorInput>{"#75AFFF" if kind == "task" else "#A5B7CD"}</colorInput>'
                f"{component}{ports(n['key'])}</flowObject>")

    lane_xml = "".join(
        f'<lane id="{lane_ids[i]}"><name>{escape(lane)}</name><height>{LANE_HEIGHT}</height><laneColor>{i % len(LANE_COLORS)}</laneColor><systemLane>false</systemLane>'
        f"<attachedParticipant>{team}</attachedParticipant>{''.join(flow_object(n) for n in nodes if n['lane'] == lane)}</lane>"
        for i, lane in enumerate(lanes))
    flow_xml = "".join(
        f'<flow id="{flow_ids[i]}" connectionType="SequenceFlow"><name>{escape(f["label"])}</name><documentation /><nameVisible>{"true" if f.get("name") else "false"}</nameVisible>'
        f'<metricSettings itemType="32" /><connection><lineType>0</lineType><condition id="{bpd_id()}">'
        + (f"<expression>{escape(f['condition'])}</expression>" if f.get("condition") else "") + "</condition></connection></flow>"
        for i, f in enumerate(flows))
    variable = (f'<privateVariable id="{var_id}"><name>{var}</name><description /><classId>/{bo_id}</classId><arrayOf>false</arrayOf>'
                "<hasDefault>false</hasDefault><defaultValue /><visibleInSearch>false</visibleInSearch><isProcessInstanceCorrelator>false</isProcessInstanceCorrelator>"
                "<isSharedContext>false</isSharedContext></privateVariable>")
    start = next(n["key"] for n in nodes if n["kind"] == "start")
    width = max(n["x"] for n in nodes) + 200
    title, desc = escape(name), escape(description or name)
    null = lambda *names: "".join(f'<{n} isNull="true" />' for n in names)
    tracking = pid.replace("25.", "p").replace("-", "")[:30]
    bpmn2 = bpmn2_xml(pid, name, description or name, var, bo_id, lanes, nodes, flows,
                      dict(ids=ids, flows=flow_ids, lanes=lane_ids, var=var_id, case=case_folder, tracking=tracking))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><bpd id="{pid}" name="{title}"><lastModified>0</lastModified><lastModifiedBy>{author}</lastModifiedBy>{null("tenantId")}<bpdId>{pid}</bpdId>
<isTrackingEnabled>false</isTrackingEnabled><isSpcEnabled>false</isSpcEnabled>{null("restrictedName")}<isCriticalPathEnabled>false</isCriticalPathEnabled>
<participantRef>{team}</participantRef><businessDataParticipantRef>{team}</businessDataParticipantRef><perfMetricParticipantRef>{team}</perfMetricParticipantRef>
{null("ownerTeamParticipantRef", "timeScheduleType", "timeScheduleName", "timeScheduleExpression", "holidayScheduleType", "holidayScheduleName", "holidayScheduleExpression",
      "timezoneType", "timezone", "timezoneExpression", "internalName")}<description>{desc}</description><type>1</type>
{null("rootBpdId", "parentBpdId", "parentFlowObjectId", "xmlData")}<bpmn2Data>{escape(bpmn2)}</bpmn2Data>
{null("dependencySummary", "jsonData", "migrationData", "rwfData", "rwfStatus", "templateId", "externalId")}
<guid>{uuid.uuid4()}</guid><versionId>{version}</versionId>{null("field1", "field2")}<field3>0</field3>{null("field4")}<field5>false</field5>{null("clobField1", "blobField1")}
<BusinessProcessDiagram id="{bpd_id()}"><metadata><entry><key>SAP_META.SHOULDRECOVER</key><value>no</value></entry><entry><key>SHOULDRECOVER</key><value>no</value></entry></metadata>
<name>{title}</name><documentation>{desc}</documentation><name>{title}</name><dimension><size w="600" h="150" /></dimension><author>{author}</author>
<isTrackingEnabled>true</isTrackingEnabled><isCriticalPathEnabled>false</isCriticalPathEnabled><isSpcEnabled>false</isSpcEnabled><isDueDateEnabled>true</isDueDateEnabled>
<isAtRiskCalcEnabled>true</isAtRiskCalcEnabled><creationDate>0</creationDate><modificationDate>0</modificationDate>
<participantRef>{team}</participantRef><businessDataParticipantRef>{team}</businessDataParticipantRef><perfMetricParticipantRef>{team}</perfMetricParticipantRef>
<metricSettings itemType="2" /><currentSimulationScenarioId><BpmnObjectId id="{start_scenario}" /></currentSimulationScenarioId>
<instanceNameExpression>{escape(f'"{name} " + tw.system.process.instanceId')}</instanceNameExpression>
<dueDateType>1</dueDateType><dueDateTime>8</dueDateTime><dueDateTimeResolution>1</dueDateTimeResolution><dueDateTimeTOD>00:00</dueDateTimeTOD><dueDateCustom></dueDateCustom>
<officeIntegration><sharePointParentSiteDisabled>true</sharePointParentSiteDisabled><sharePointParentSiteName></sharePointParentSiteName><sharePointParentSiteTemplate></sharePointParentSiteTemplate>
<sharePointWorkspaceSiteName></sharePointWorkspaceSiteName><sharePointWorkspaceSiteDescription></sharePointWorkspaceSiteDescription><sharePointWorkspaceSiteTemplate></sharePointWorkspaceSiteTemplate>
<sharePointLCID>1033</sharePointLCID></officeIntegration><timeScheduleType>0</timeScheduleType><holidayScheduleType>0</holidayScheduleType><timezoneType>0</timezoneType>
<executionProfile>default</executionProfile><isSBOSyncEnabled>false</isSBOSyncEnabled><allowContentOperations>false</allowContentOperations><isLegacyCaseMigrated>false</isLegacyCaseMigrated>
<hasCaseObjectParams>false</hasCaseObjectParams><defaultPool><BpmnObjectId id="{pool_id}" /></defaultPool><defaultInstanceUI id="{bpd_id()}" /><ownerTeamInstanceUI id="{bpd_id()}" />
<simulationScenario id="{start_scenario}"><name>Default</name><simNumInstances>100</simNumInstances><simMinutesBetween>30</simMinutesBetween><maxInstances>100</maxInstances>
<useMaxInstances>true</useMaxInstances><continueFromReal>false</continueFromReal><useParticipantCalendars>false</useParticipantCalendars><useDuration>false</useDuration>
<duration>86400</duration><startTime>0</startTime><startEventId><BpmnObjectId id="{ids[start]}" /></startEventId></simulationScenario>
{flow_xml}<pool id="{pool_id}"><name>Pool</name><documentation /><restrictedName>{tracking}</restrictedName>
<dimension><size w="{width}" h="{LANE_HEIGHT * len(lanes)}" /></dimension><autoTrackingEnabled>true</autoTrackingEnabled>{lane_xml}{variable}</pool>
<extension id="{bpd_id()}" type="CASE"><caseFolder id="{case_folder}"><allowLocalDoc>false</allowLocalDoc><allowExternalDoc>false</allowExternalDoc>
<allowSubfoldersCreation>false</allowSubfoldersCreation><allowExternalFolder>false</allowExternalFolder></caseFolder></extension>
</BusinessProcessDiagram></bpd></teamworks>
"""


def bpmn2_xml(pid, name, description, var, bo_id, lanes, nodes, flows, ref):
    """The BPMN 2 model of the same diagram, as Studio writes it when it converts a BPD. ref holds the ids
    the legacy diagram uses (ids, flows, lanes, var, case, tracking), so both models describe one process."""
    ids, flow_ids, team, bo = ref["ids"], ref["flows"], ALL_USERS, f"/{bo_id}"
    xsi = 'xmlns:xsi="{}"'.format(BPMN_NS["xsi"])
    visual = lambda n: '<ns16:nodeVisualInfo x="{}" y="{}" width="{}" height="{}"/>'.format(
        n["x"], (LANE_HEIGHT - NODE_SIZE[n["kind"]][1]) // 2, *((32, 32) if n["kind"] == "gateway" else NODE_SIZE[n["kind"]]))
    incoming = lambda key: "".join(f"<ns6:incoming>{flow_ids[i]}</ns6:incoming>" for i, f in enumerate(flows) if f["to"] == key)
    out_ids = lambda key: [flow_ids[i] for i, f in enumerate(flows) if f["from"] == key]
    default = lambda key: next((flow_ids[i] for i, f in enumerate(flows) if f["from"] == key and not f.get("condition")), "")
    outgoing = lambda key: "".join(f"<ns6:outgoing>{i}</ns6:outgoing>" for i in out_ids(key))
    performer = "".join(f'<ns6:resourceRole {xsi} xsi:type="ns2:tActivityPerformer" distribution="None" name="{r}"><ns2:teamFilterService/></ns6:resourceRole>'
                        for r in ("Lane", "Team")) + f'<ns6:resourceRole {xsi} xsi:type="ns6:tPerformer" name="Expert"/>'
    expression = lambda end: f'<ns6:{end} {xsi} xsi:type="ns6:tFormalExpression" evaluatesToTypeRef="{bo}">tw.local.{var}</ns6:{end}>'

    def node(n):
        key, title, kind = n["key"], escape(n["name"]), n["kind"]
        head = f'name="{title}" id="{ids[key]}"'
        if kind == "start":
            return (f"<ns6:startEvent {head}><ns6:extensionElements>{visual(n)}<ns3:default>{default(key)}</ns3:default></ns6:extensionElements>"
                    f"{outgoing(key)}</ns6:startEvent>")
        if kind == "end":
            return f"<ns6:endEvent {head}><ns6:extensionElements>{visual(n)}</ns6:extensionElements>{incoming(key)}</ns6:endEvent>"
        if kind == "gateway":
            return (f'<ns6:exclusiveGateway default="{default(key)}" gatewayDirection="Unspecified" {head}><ns6:extensionElements>{visual(n)}'
                    f"</ns6:extensionElements>{incoming(key)}{outgoing(key)}</ns6:exclusiveGateway>")
        input_id, output_id = n["io"]
        return (f'<ns6:callActivity calledElement="{n["service"]}" default="{default(key)}" {head}><ns6:extensionElements>'
                f"<ns2:activityType>UserTask</ns2:activityType><ns2:userTaskSettings><ns2:narrative>{title}</ns2:narrative><ns2:subject>{title}</ns2:subject>"
                "<ns2:enableAutoFlow>false</ns2:enableAutoFlow><ns2:enableCleanState>false</ns2:enableCleanState>"
                '<ns2:activityPriority type="Priority"><ns2:priority>Normal</ns2:priority></ns2:activityPriority>'
                '<ns2:activityDueDate type="TimeCalculation"><ns2:dueDate unit="Hours" timeOfDay="00:00">1</ns2:dueDate>'
                '<ns2:timeZone type="TimeZone"><ns2:value>(use default)</ns2:value></ns2:timeZone></ns2:activityDueDate>'
                "<ns2:activityAssignmentType>Lane</ns2:activityAssignmentType><ns2:activityWorkSchedule><ns2:timeScheduleType>0</ns2:timeScheduleType>"
                "<ns2:timeScheduleName>(use default)</ns2:timeScheduleName><ns2:timezoneType>0</ns2:timezoneType><ns2:holidayScheduleType>0</ns2:holidayScheduleType>"
                "<ns2:holidayScheduleName>(use default)</ns2:holidayScheduleName></ns2:activityWorkSchedule></ns2:userTaskSettings>"
                f'<ns2:activityExtension conditional="false"/>{visual(n)}</ns6:extensionElements>{incoming(key)}{outgoing(key)}'
                f"<ns6:dataInputAssociation><ns6:targetRef>{input_id}</ns6:targetRef><ns6:assignment>{expression('from')}</ns6:assignment></ns6:dataInputAssociation>"
                f"<ns6:dataOutputAssociation><ns6:sourceRef>{output_id}</ns6:sourceRef><ns6:assignment>{expression('to')}</ns6:assignment></ns6:dataOutputAssociation>"
                f"{performer}</ns6:callActivity>")

    def flow(i, f):
        # Studio stores a branch condition as "<expression> == true".
        condition = (f'<ns6:conditionExpression {xsi} xsi:type="ns6:tFormalExpression">{escape(f["condition"])}\t  ==\t  true</ns6:conditionExpression>'
                     if f.get("condition") else "")
        return (f'<ns6:sequenceFlow sourceRef="{ids[f["from"]]}" targetRef="{ids[f["to"]]}" name="{escape(f["label"])}" id="{flow_ids[i]}">'
                "<ns6:extensionElements><ns3:happySequence>true</ns3:happySequence><ns16:linkVisualInfo>"
                f'<ns16:sourcePortLocation>{f.get("out", "rightCenter")}</ns16:sourcePortLocation><ns16:targetPortLocation>{f.get("in", "leftCenter")}</ns16:targetPortLocation>'
                f'<ns16:showLabel>{"true" if f.get("name") else "false"}</ns16:showLabel><ns16:showCoachControlLabel>false</ns16:showCoachControlLabel>'
                "<ns16:labelPosition>0.0</ns16:labelPosition><ns16:saveExecutionContext>false</ns16:saveExecutionContext></ns16:linkVisualInfo>"
                f"</ns6:extensionElements>{condition}</ns6:sequenceFlow>")

    width = max(n["x"] for n in nodes) + 200
    lane_xml = "".join(
        f'<ns6:lane name="{escape(lane)}" partitionElementRef="{team}" id="{ref["lanes"][i]}" ns2:isSystemLane="false"><ns6:extensionElements>'
        f'<ns16:nodeVisualInfo x="0" y="{i * LANE_HEIGHT}" width="{width}" height="{LANE_HEIGHT}" color="{LANE_COLORS[i % len(LANE_COLORS)]}"/></ns6:extensionElements>'
        + "".join(f"<ns6:flowNodeRef>{ids[n['key']]}</ns6:flowNodeRef>" for n in nodes if n["lane"] == lane) + "</ns6:lane>"
        for i, lane in enumerate(lanes))
    roles = "".join(f'<ns6:resourceRole name="{r}"><ns6:resourceRef>{team}</ns6:resourceRef></ns6:resourceRole>'
                    for r in ("participantRef", "businessDataParticipantRef", "perfMetricParticipantRef")) + '<ns6:resourceRole name="ownerTeamParticipantRef"/>'
    namespaces = " ".join(f'xmlns:{k}="{v}"' for k, v in BPMN_NS.items() if k != "xsi")
    title = escape(name)
    instance = escape(f'"{name} " + tw.system.process.instanceId', {'"': "&quot;"})
    return (f'<ns6:definitions {namespaces} id="{uuid.uuid4()}" targetNamespace="" exporter="http://www.ibm.com/BPM" exporterVersion="8.6.11">'
            f'<ns6:process processType="None" isClosed="false" name="{title}" id="{pid}">'
            f'<ns6:documentation textFormat="text/plain">{escape(description)}</ns6:documentation><ns6:extensionElements>'
            f'<ns4:isConvergedProcess>true</ns4:isConvergedProcess><ns2:bpdExtension instanceName="{instance}" dueDateEnabled="true" atRiskCalcEnabled="true" '
            'enableTracking="true" allowProjectedPathManagement="false" optimizeExecForLatency="false" sBOSyncEnabled="false" allowContentOperations="false" '
            f'autoTrackingEnabled="true" autoTrackingName="{ref["tracking"]}"><ns2:defaultInstanceUI/><ns2:bpdOwnerInstanceUI/>'
            '<ns2:dueDateSettings type="TimeCalculation"><ns2:dueDate unit="Hours" timeOfDay="00:00">8</ns2:dueDate></ns2:dueDateSettings>'
            "<ns2:workSchedule><ns2:timeScheduleType>0</ns2:timeScheduleType><ns2:timezoneType>0</ns2:timezoneType><ns2:holidayScheduleType>0</ns2:holidayScheduleType>"
            f'</ns2:workSchedule></ns2:bpdExtension><ns4:caseExtension><ns4:caseFolder id="{ref["case"]}"/></ns4:caseExtension></ns6:extensionElements>'
            f'<ns6:ioSpecification/><ns6:laneSet id="{bpd_id()}">{lane_xml}</ns6:laneSet>'
            + "".join(node(n) for n in nodes)
            + f'<ns6:dataObject itemSubjectRef="itm.{bo_id}" isCollection="false" name="{var}" id="{ref["var"]}"><ns6:extensionElements>'
            '<ns3:defaultValue useDefault="false"/><ns2:isProcessIdentifier>false</ns2:isProcessIdentifier></ns6:extensionElements></ns6:dataObject>'
            + "".join(flow(i, f) for i, f in enumerate(flows))
            + f'{roles}</ns6:process><ns6:interface name="{title}Interface" id="_{uuid.uuid4()}"/></ns6:definitions>')
