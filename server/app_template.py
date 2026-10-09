#!/usr/bin/env python3
"""
The packaging a generated process app needs, built in, so an app can be built without exporting
anything from a server first.

A generated .twx uses BAW's "twxWithoutToolkits" format: META-INF/package.xml lists the two system
toolkits the coaches use (System Data and UI Toolkit) by ID, but their contents are not bundled,
because every BAW server already has them. That is the format the Operations REST API exports with
format=twxWithoutToolkits.

The built-in IDs and header match BAW 26.0.0 on Cloud Pak for Business Automation. To match another
server exactly, read them from any app exported from that server with read_base().
"""

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

# Opening tag of META-INF/package.xml: the BAW build the package says it comes from.
HEADER = ('<p:package buildId="BPM8600-20260825-175823" buildVersion="8.6.11" '
          'buildDescription="IBM Business Process Manager V8.6.11.26000 - 20260825_2032 - BPM8600-20260825-175823" '
          'fixPack="26000" containsECM="false" containsBPMN2="false" xmlns:p="http://lombardisoftware.com/schema/teamworks/7.0.0/package.xsd">')

# System toolkits by short name: (dependency ID, rank, project ID, project name, branch ID, snapshot ID, snapshot name, created).
# The dependency IDs are what object XML refers to (coach_builder.TWSYS is System Data's).
SYSTEM_TOOLKITS = {
    "SYSBPMUI": ("2069.226876e5-23df-4d7f-8029-7383bcb82017", 3, "2066.ec5973da-aebe-40f6-aa02-a77962288f52", "UI Toolkit",
                 "2063.83ee2bb2-72b4-4a4d-b8ae-37ecd983c05e", "2064.304ac881-16c3-47d2-97d5-6e4c4a893177", "8.6.0.0", "2017-05-24T23:23:53.574Z"),
    "TWSYS": ("2069.7692552a-ea18-49ce-bd93-a1dd62100cd9", 0, "2066.1b351583-e5cb-43b7-baee-340a63130ea7", "System Data",
              "2063.0798815e-0346-4ef4-8946-ab4301c9f340", "2064.1080ded6-d153-4654-947c-2d16fce170db", "8.6.0.0_TC", "2015-08-25T00:00:00.000Z"),
}
TARGET_ENVIRONMENT = "BAW_CP4A"
DEFAULT_THEME = "7692552a-ea18-49ce-bd93-a1dd62100cd9/72.993e03e9-2574-40fc-807c-65b06be378fd"  # System Data's theme

ENV_VARS = """<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <environmentVariableSet id="{id}" name="Environment Variables">
        <lastModified>0</lastModified>
        <lastModifiedBy>{author}</lastModifiedBy>
        <tenantId isNull="true" />
        <envVarSetId>{id}</envVarSetId>
        <description isNull="true" />
        <guid>guid:{guid}</guid>
        <versionId>{version}</versionId>
    </environmentVariableSet>
</teamworks>
"""

PROJECT_DEFAULTS = """<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <projectDefaults id="{id}" name="Process App Settings">
        <lastModified>0</lastModified>
        <lastModifiedBy>{author}</lastModifiedBy>
        <tenantId isNull="true" />
        <projectDefaultsId>{id}</projectDefaultsId>
        <description isNull="true" />
        <guid>guid:{guid}</guid>
        <versionId>{version}</versionId>
        <participantRef isNull="true" />
        <defaultXslRef isNull="true" />
        <defaultCssRef isNull="true" />
        <defaultTheme>{theme}</defaultTheme>
        <themeVersion isNull="true" />
        <defaultJsRefs isNull="true" />
        <isWbmEnabled>false</isWbmEnabled>
        <namespace isNull="true" />
        <isIidOptimized>false</isIidOptimized>
        <isQueueBypass>1</isQueueBypass>
        <templateAcronymReference isNull="true" />
        <templateSnapshotReference isNull="true" />
        <targetEnvironment>{environment}</targetEnvironment>
        <subtype isNull="true" />
        <capability isNull="true" />
        <solutionTargetStore isNull="true" />
        <appLoggingEnabled>false</appLoggingEnabled>
        <logName isNull="true" />
        <logLevel>0</logLevel>
    </projectDefaults>
</teamworks>
"""

BUSINESS_OBJECT = """<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <twClass id="{id}" name="{name}">
        <lastModified>0</lastModified>
        <lastModifiedBy>{author}</lastModifiedBy>
        <tenantId isNull="true" />
        <classId>{id}</classId>
        <type>1</type>
        <isSystem>false</isSystem>
        <shared>false</shared>
        <isShadow>false</isShadow>
        <globalLifetime>false</globalLifetime>
        <internalName isNull="true" />
        <extensionType isNull="true" />
        <saveServiceRef isNull="true" />
        <bpmn2Data isNull="true" />
        <externalId isNull="true" />
        <dependencySummary isNull="true" />
        <jsonData isNull="true" />
        <dataName isNull="true" />
        <allowAdditionalProperties>false</allowAdditionalProperties>
        <description isNull="true" />
        <guid>guid:{guid}</guid>
        <versionId>{version}</versionId>
        <definition>
            {properties}
            <validator>
                <className isNull="true" />
                <errorMessage isNull="true" />
                <webWidgetJavaClass isNull="true" />
                <externalType isNull="true" />
                <configData>
                    <schema>
                        <simpleType name="{name}">
                            <restriction base="String" />
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

PROPERTY = """<property>
                <name>{name}</name>
                <description isNull="true" />
                <classRef>{class_ref}</classRef>
                <arrayProperty>false</arrayProperty>
                <propertyDefault isNull="true" />
                <propertyRequired>false</propertyRequired>
                <propertyHidden>false</propertyHidden>
                <annotation type="com.lombardisoftware.core.xml.XMLFieldAnnotation" version="2.0">
                    <exclude isNull="true" />
                    <nodeType isNull="true" />
                    <name isNull="true" />
                    <namespace isNull="true" />
                    <typeName isNull="true" />
                    <typeNamespace isNull="true" />
                    <minOccurs isNull="true" />
                    <maxOccurs isNull="true" />
                    <nillable isNull="true" />
                    <order isNull="true" />
                    <wrapArray isNull="true" />
                    <arrayTypeName isNull="true" />
                    <arrayTypeAnonymous isNull="true" />
                    <arrayItemName isNull="true" />
                    <arrayItemWildcard isNull="true" />
                    <wildcard isNull="true" />
                    <wildcardVariety isNull="true" />
                    <wildcardMode isNull="true" />
                    <wildcardNamespace isNull="true" />
                    <parentModelGroupCompositor isNull="true" />
                    <timeZone isNull="true" />
                </annotation>
            </property>"""


def read_base(path: Path) -> dict:
    """What a generated app takes from an app exported from the target server: the package header,
    the system toolkits' IDs, the target environment, and the app's own identity (to add a snapshot to it)."""
    with zipfile.ZipFile(path) as z:
        package = z.read("META-INF/package.xml").decode("utf-8")
        defaults = next((z.read(f"objects/{oid}.xml").decode("utf-8") for oid in
                         re.findall(r'<object id="([^"]+)" versionId="[^"]+" name="[^"]*" type="projectDefaults"/>', package)), "")
    header = re.search(r"<p:package [^>]*>", package)
    if not header:
        raise ValueError(f"{path} is not a BAW export: META-INF/package.xml has no package header")
    toolkits = {}
    for block in re.findall(r"<dependency [^>]*>.*?</dependency>", package, re.S):
        project = re.search(r'<project id="([^"]+)" name="([^"]*)" shortName="([^"]+)"', block)
        if project and project.group(3) in SYSTEM_TOOLKITS:
            dep_id, rank = SYSTEM_TOOLKITS[project.group(3)][:2]
            branch = re.search(r'<branch id="([^"]+)"', block).group(1)
            snap = re.search(r'<snapshot id="([^"]+)" name="([^"]*)" originalCreationDate="([^"]*)"', block)
            toolkits[project.group(3)] = (dep_id, rank, project.group(1), project.group(2), branch, *snap.groups())
    target = package.split("</target>", 1)[0]
    attr = lambda tag, key: re.search(rf'<{tag} [^>]*\b{key}="([^"]*)"', target).group(1)  # noqa: E731
    environment = re.search(r"<targetEnvironment>([^<]+)</targetEnvironment>", defaults)
    return {"header": header.group(0), "toolkits": {**SYSTEM_TOOLKITS, **toolkits},
            "environment": environment.group(1) if environment else TARGET_ENVIRONMENT,
            "acronym": attr("project", "shortName"), "name": attr("project", "name"),
            "projectId": attr("project", "id"), "branchId": attr("branch", "id"), "branchName": attr("branch", "name"),
            "snapshot": attr("snapshot", "name")}


def builtin() -> dict:
    return {"header": HEADER, "toolkits": SYSTEM_TOOLKITS, "environment": TARGET_ENVIRONMENT}


def package_xml(base: dict, app: dict, ids: dict, objects: list) -> str:
    """META-INF/package.xml of a generated app. app: name, acronym, snapshot.
    ids: projectId, branchId, branchName, snapshotId. objects: (id, versionId, name, type)."""
    name, acronym, snapshot = (escape(app[k], {'"': "&quot;"}) for k in ("name", "acronym", "snapshot"))
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    deps = "".join(
        f'\n        <dependency rank="{rank}" isManaged="false" id="{dep_id}">'
        f'\n            <project id="{project_id}" name="{project}" shortName="{short}" isToolkit="true" isHidden="false" isSystem="true"/>'
        f'\n            <branch id="{branch_id}" name="Main"/>'
        f'\n            <snapshot id="{snap_id}" name="{snap_name}" originalCreationDate="{snap_created}"/>'
        f"\n        </dependency>"
        for short, (dep_id, rank, project_id, project, branch_id, snap_id, snap_name, snap_created) in base["toolkits"].items())
    entries = "".join(f'\n        <object id="{oid}" versionId="{version}" name="{escape(oname, {chr(34): "&quot;"})}" type="{otype}"/>'
                      for oid, version, oname, otype in objects)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
{base["header"]}
    <target>
        <project id="{ids["projectId"]}" name="{name}" description="{name}" shortName="{acronym}" isToolkit="false" isHidden="false" isSystem="false" solutionID="" solutionServerName="" solutionPrefix="" type="" isTemplate="false" isIconSet="false" caseDisplayName=""/>
        <branch id="{ids["branchId"]}" name="{escape(ids.get("branchName", "Main"))}" acronym="Main" description=""/>
        <snapshot id="{ids["snapshotId"]}" name="{snapshot}" acronym="{snapshot}" originalCreationDate="{created}" description=""/>
    </target>
    <dependencies>{deps}
    </dependencies>
    <objects>{entries}
    </objects>
    <files/>
    <migrationPolicies/>
</p:package>
"""


META_INF = {
    "META-INF/MANIFEST.MF": "Manifest-Version: 1.0\n\n",
    "META-INF/metadata.xml": '<?xml version="1.0" encoding="UTF-8"?>\n<metadata />\n\n',
    "META-INF/properties.json": '{"twxWithoutToolkits":"true"}',
}

# Coach views of the system toolkits (ID -> name), for reading coaches of an app exported without its toolkits.
SYSTEM_VIEWS = {
    "64.e6b70dd5-4d8e-4598-a08b-dcb9a9dfaba5": "Alerts",
    "64.2c8ffc35-7cea-4d7b-85d9-e3d02a901bea": "Area Chart SDS",
    "64.dbd042c3-8328-49af-9f0b-a92ba4ffb841": "Badge",
    "64.8d17dda8-175c-49ec-aaa8-cba00f7b5c24": "Bar Chart SDS",
    "64.281a0d61-afa8-4297-bbc8-29a2d1c1bc83": "Breadcrumbs",
    "64.7133c7d4-1a54-45c8-89cd-a8e8fa4a8e36": "Button",
    "64.49c8e80a-9836-44d3-a3a7-97968fc8b4cb": "Caption Box",
    "64.fffd1628-baee-44e8-b7ca-5ae48644b0be": "Checkbox",
    "64.b00a9c90-0931-47ac-ab7c-e9fd9b891ccb": "Checkbox Group",
    "64.aa70e5b9-aade-4334-b92d-1fb5e61f4b0a": "Collapsible Panel",
    "64.a87aa2c7-c36c-4ee8-9b04-c296503ffb15": "Configuration",
    "64.9b679256-e93b-4400-89f2-bd15b0c5578d": "Data",
    "64.90bf9818-cbe7-4435-842a-8ae4559a376c": "Data Export",
    "64.aeae8953-9e72-411e-b35a-93c7ab827c5c": "Date Picker",
    "64.54643ff2-8363-4976-bb5e-d4eb1094cca3": "Date Time Picker",
    "64.e0ede0f2-f3af-408c-af7b-e7a58eb5e2b4": "Decimal",
    "64.dc5fd75e-5b13-460c-8cb8-1e463c729751": "Default Inline User Task Template",
    "64.9ee7a0fd-5b25-497d-85fc-1cc09795f524": "Deferred Section",
    "64.14d6d2be-5be6-48f5-8fd7-949f575c6150": "Device Sensor",
    "64.daacaaf8-7b70-4e3a-9a96-bc291cd97436": "DocumentView",
    "64.0eeb7300-7ef8-4079-b3d2-d10ec7379e58": "Donut Chart SDS",
    "64.38adbdb0-9f2a-47d1-ac5e-27ca6946ad2e": "Event Subscription",
    "64.06a9923f-f2b5-41ff-aeec-257b7d61b29b": "Exit Safeguard",
    "64.bfd6fc27-0b2b-4169-8970-7cb3b382d97f": "Geo Coder",
    "64.e302f8ff-4f48-4730-8a38-a04523ed8b15": "Geo Location",
    "64.44f463cc-615b-43d0-834f-c398a82e0363": "Horizontal Layout",
    "64.5c490b0f-ce12-4f65-a959-6084ee570480": "Horizontal Split",
    "64.1b440a6c-8508-4f95-bc28-728a58f2353c": "Icon",
    "64.49422be7-d203-44dc-951d-7ca4361d7b94": "Image",
    "64.33c2011d-5bc9-4609-9e48-0f42b858f1a0": "Input Group",
    "64.a6946c4c-f73d-4ced-9216-90018985ca96": "Integer",
    "64.0c440db2-90b0-4337-b778-428b289caadf": "JSON Text Area",
    "64.ff97945c-a44b-44d1-8b36-083255daf920": "Line",
    "64.d11572b6-d14b-4267-9eea-98c6709a7dbb": "Line Chart SDS",
    "64.22f864a3-15ab-48ce-9744-14f01b4b2368": "Link",
    "64.4e6c49be-c45f-4571-9e67-1d17ed36b1df": "Map",
    "64.b9c128d5-1c54-4a0a-9b76-0e7ffd6ed2a1": "Masked Text",
    "64.066607d7-6101-4ae6-aa5e-4b8fbbb433a7": "Modal Alert",
    "64.66286dff-19bf-447a-ad5c-4fc385fea67d": "Modal Section",
    "64.c025cd95-70c4-4b5e-924a-7bf69174e123": "Multi Purpose Chart",
    "64.7df3f465-dc52-4d4a-88a1-8d237a5ca563": "Multi Select",
    "64.ecaae891-b5b0-4836-bc25-def71fcad690": "Navigation Event",
    "64.655c6c8a-c4a2-49e1-9174-a47adae9db7d": "Navigation item",
    "64.13e06fc4-c088-4091-9bc9-9f7120b59322": "Navigation list",
    "64.6d3d37fb-3254-4f43-a409-e4f532200678": "Navigation menu",
    "64.32441394-ff38-4ecb-8028-02fc04725fe9": "Note",
    "64.84561e27-ec84-49d3-adb9-de8e060437f0": "Notification",
    "64.d156e24b-e70a-4ffe-80f4-3153048db5cd": "OpenLayers API",
    "64.f634f22e-7800-4bd7-9f1e-87177acfb3bc": "Output Text",
    "64.455e44ab-b77b-4337-b3f9-435e234fb569": "Panel",
    "64.7f521ba9-7450-4ed7-98e3-a0128c2900c9": "Panel Footer",
    "64.23384625-cb80-4295-899a-943504b7aaa1": "Panel Header",
    "64.4da8dcb3-7881-4e0f-8382-4e608751ce2e": "Password",
    "64.ded8f8bd-32de-4fbb-89c6-a335368ea435": "Pie Chart SDS",
    "64.70e410ee-c257-456d-b8a0-051a5c9259cc": "Places",
    "64.c0514f65-f0be-441c-88b7-efcd91e36389": "Popup Menu",
    "64.8f6a9870-14fb-474b-99c6-0e3844e23d67": "Progress Bar",
    "64.32f56581-ee59-45d0-b58e-ed47e8a4d7bb": "QR Code",
    "64.ad2b879f-ee68-4bc9-9b1b-fb7c0856a48e": "Radio Button",
    "64.bdddb841-6b07-4c08-bb5c-236a8da26b6a": "Radio Button Group",
    "64.aa08832f-4366-4941-b213-3c1148b59d32": "Responsive Sensor",
    "64.1feaead9-b1d2-4a7e-80a3-22156e6fe8f9": "Service Call",
    "64.6b29c1bc-c211-43ce-8fbc-904e6e4d57f7": "Service Data Table",
    "64.a62e7774-259f-4e17-914d-97daaf7a7a28": "Signature",
    "64.fd4da558-40d8-47be-92ca-c305708dc7b7": "Single Select",
    "64.5a0a8518-8377-4232-ada1-9a2eaea7f7f7": "Slider",
    "64.71b97b55-fda9-48e8-b21b-58fb4e85ca10": "Spacer",
    "64.be3078bd-3d8c-4bd6-9a47-307c4d14d4f5": "Spinner",
    "64.05d9d0b5-0423-4ab6-b16c-e3554dfaf4a6": "Stack",
    "64.c48318be-0720-43d9-9c02-7fe15244ab79": "Status Box",
    "64.2a8c9084-e5f5-4be3-a15c-1dfbd5f5c109": "Step Chart SDS",
    "64.50e886c4-eede-4bba-9b9a-2f6b51ce6a9b": "Style",
    "64.bff9f5ff-fea4-4a70-87a5-769301740798": "Switch",
    "64.c05b439f-a4bd-48b0-8644-fa3b59052217": "Tab Section",
    "64.f515b79f-fe61-4bd3-8e26-72f00155d139": "Table",
    "64.bd961fbd-60cd-4341-9234-cec3516a5ed8": "Table Layout",
    "64.5aea8d13-714d-4d05-8717-8c744b419365": "Table Layout Cell",
    "64.9ac7d257-d8ad-47e6-a1df-b76cf1a4ec87": "Table Layout Row",
    "64.5663dd71-ff18-4d33-bea0-468d0b869816": "Text",
    "64.0e61869e-73fd-4401-b156-8c11adaec3f8": "Text Area",
    "64.8881a0d8-ba85-4a8a-9c3b-c2f8ab32ece9": "Text Editor",
    "64.933fd33b-4cce-4f8d-8219-7bac494f200d": "Text Reader",
    "64.ec19f655-f26d-45a2-a488-6f73536a03eb": "Timer",
    "64.dc7cb757-a065-44c1-a92d-d186f8eea4e2": "Tooltip",
    "64.847f8ace-ae59-47ef-9b55-e5a4242e7426": "Type Ahead Text",
    "64.b9738f74-c1ec-4483-90e0-e2dd133e4608": "Variant",
    "64.ef447b87-24a2-42a7-b2b9-cd471e9f7b67": "Vertical Layout",
    "64.90af4be1-268b-4bef-8e3d-627a1f3b76ed": "Video",
    "64.64ae2c6c-6c21-491c-b5ab-c58848dd9e48": "Well",
}
