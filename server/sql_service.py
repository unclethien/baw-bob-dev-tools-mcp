#!/usr/bin/env python3
"""
SQL from a generated BAW app, through a JNDI data source (jdbc/bawexternal by default).

run_sql_service() builds a heritage general system service: it turns a JSON array of values into System Data
SQLParameters, runs System Data's "SQL Execute Statement (SQLResult)" with the data source mapped explicitly (System
Data's own default is jdbc/TeamWorksDB, BAW's own database), and returns the result as a JSON text:
{"ok": true, "updateCount", "columns", "rows"} (every cell a string or null), or {"ok": false, "error"}.
A client-side human service calls it with a coach_builder service-call step (call_step()).

A service is exposed to the browser (AJAX), so for an app spec's "database" section there is one service per
operation, "Load <BO>" (input: the key) and "Save <BO>" (input: the values), each with its statement fixed inside as a
constant: a caller can choose values, never the statement. No generated service takes a statement as an input.

For the "database" section, table_plan() checks and names the table and its columns, and ddl(), load_sql() and
save_sql() write the statements. Every name goes through quote(), and every value is typed in the statement with
CAST(? AS <type>). check_data_source() verifies a finished package.

The CLI builds ZZSQL, a scratch app that checks the whole path on a server:
    python3 server/sql_service.py work/ZZSQL-0.1.twx --snapshot 0.1
"""

import argparse
import json
import re
import sys
import zipfile
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app_template  # noqa: E402
from coach_builder import (  # noqa: E402
    NO_LINK_LAYOUT,
    SYSTEM_TYPES,
    TWSYS,
    Layout,
    coachflow,
    item_xml,
    uid,
    write_twx,
)

DATA_SOURCE = "jdbc/bawexternal"
MAX_ROWS = 1000
NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}\Z")
PG_TYPES = {"String": "text", "Integer": "integer", "Decimal": "numeric", "Boolean": "boolean", "Date": "timestamptz"}  # by BAW type
ISO_UTC = "YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\""  # to_char pattern: an instant as ISO-8601 in UTC
MESSAGE = "dbMessage"  # the business object property that carries a database message or result between flow steps

BUILD_PARAMS = """__VALUES__
tw.local.sqlParams = new tw.object.listOf.SQLParameter();
for (var i = 0; i < values.length; i++) {
  var p = new tw.object.SQLParameter();
  p.value = values[i] === null ? null : String(values[i]);
  p.type = "VARCHAR";
  p.mode = "IN";
  tw.local.sqlParams[i] = p;
}"""
FIXED_VALUES = """var values = __VALUES__;
if (Object.prototype.toString.call(values) !== "[object Array]" || values.length != __COUNT__) {
  throw new Error("This service takes exactly __COUNT__ value(s)");
}"""
VALUES_FROM = {"key": "[tw.local.key == null || tw.local.key === \"\" ? null : String(tw.local.key)]",
               "values": 'JSON.parse(tw.local.values || "[]")'}

RESULT_JSON = """var out = {ok: true, updateCount: null, columns: [], rows: []};
var rs = tw.local.sqlResults;
if (rs != null && rs.listLength > 0) {
  var r = rs[0];
  if (r.updateCount != null) out.updateCount = Number(r.updateCount);
  for (var k = 0; r.columns != null && k < r.columns.listLength; k++) out.columns.push(String(r.columns[k].columnName));
  for (var j = 0; r.rows != null && j < r.rows.listLength; j++) {
    var cells = [];
    for (var k = 0; k < out.columns.length; k++) {
      var v = r.rows[j].data[k];
      cells.push(v == null ? null : String(v));
    }
    out.rows.push(cells);
  }
}
tw.local.text = JSON.stringify(out);"""

REPORT_ERROR = r"""var message = "";
var read = [function () { return tw.system.error.getErrorText(); }, function () { return tw.system.error.errorText; },
            function () { return tw.system.error.message; }, function () { return tw.system.error.toString(); }];
for (var i = 0; i < read.length && message === ""; i++) {
  try { var text = String(read[i]()); if (text !== "" && text !== "null" && text !== "undefined" && text.indexOf("[object") !== 0) { message = text; } } catch (e) {}
}
var inner = /<message[^>]*>([\s\S]*?)<\/message>/.exec(message);
if (inner) { message = inner[1]; }
message = message.replace(/\s+/g, " ");
if (message === "") { message = "The SQL statement failed"; }
tw.local.text = JSON.stringify({ok: false, error: message.substring(0, 500)});"""


def system(type_id: str) -> str:
    return f"{TWSYS}/{type_id}"


def parameter(pid, name, kind, seq, class_id, is_list=False):
    """kind 1: input, 2: output."""
    return (f'<processParameter name="{name}"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />'
            f"<processParameterId>2055.{uid()}</processParameterId><processId>{pid}</processId><parameterType>{kind}</parameterType>"
            f"<isArrayOf>{str(is_list).lower()}</isArrayOf><classId>{class_id}</classId><seq>{seq}</seq><hasDefault>false</hasDefault>"
            f'<defaultValue isNull="true" /><isLocked>false</isLocked><description isNull="true" /><guid>{uid()}</guid>'
            f"<versionId>{uid()}</versionId></processParameter>")


def variable(pid, name, seq, class_id, is_list=False):
    return (f'<processVariable name="{name}"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />'
            f'<processVariableId>2056.{uid()}</processVariableId><description isNull="true" /><processId>{pid}</processId>'
            f"<namespace>2</namespace><seq>{seq}</seq><isArrayOf>{str(is_list).lower()}</isArrayOf><isTransient>false</isTransient>"
            f'<classId>{class_id}</classId><hasDefault>false</hasDefault><defaultValue isNull="true" /><guid>{uid()}</guid>'
            f"<versionId>{uid()}</versionId></processVariable>")


def mapping(parent, name, param, value, class_id, is_input, is_list=False):
    return (f'<parameterMapping name="{name}"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />'
            f"<parameterMappingId>2054.{uid()}</parameterMappingId><processParameterId>{param}</processParameterId>"
            f"<parameterMappingParentId>{parent}</parameterMappingParentId><useDefault>false</useDefault><value>{escape(value)}</value>"
            f"<classRef>{class_id}</classRef><isList>{str(is_list).lower()}</isList><isInput>{str(is_input).lower()}</isInput>"
            f'<mappingMode isNull="true" /><sourcePath isNull="true" /><targetPath isNull="true" /><guid>{uid()}</guid>'
            f'<versionId>{uid()}</versionId><description isNull="true" /></parameterMapping>')


def script_component(script):
    sid = "3011." + uid()
    return sid, (f'<TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><scriptId>{sid}</scriptId>'
                 f"<scriptTypeId>2</scriptTypeId><isActive>true</isActive><script>{escape(script)}</script><isRule>false</isRule>"
                 f"<guid>{uid()}</guid><versionId>{uid()}</versionId></TWComponent>")


def link(pid, src, dst, end_state):
    return (f'<link name="Untitled"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><processLinkId>2027.{uid()}</processLinkId>'
            f'<processId>{pid}</processId><description isNull="true" /><fromProcessItemId>{src}</fromProcessItemId><endStateId>{end_state}</endStateId>'
            f"<toProcessItemId>{dst}</toProcessItemId><guid>{uid()}</guid><versionId>{uid()}</versionId>{NO_LINK_LAYOUT}"
            f'<fromItemPort locationId="rightCenter" portType="1" /><toItemPort locationId="leftCenter" portType="2" />'
            f"<fromProcessItemId>{src}</fromProcessItemId><toProcessItemId>{dst}</toProcessItemId></link>")


def run_sql_service(name, statement, inputs=("values",), data_source=DATA_SOURCE, author="sql_service", sql=app_template.SYSTEM_SQL):
    """A heritage service that runs SQL: (id, versionId, name, type, xml, {input and "text": parameter ids}).
    The statement is fixed in the service (one ? per value) and the input is "key" (the one value) or "values" (a
    JSON array of exactly as many values as the statement has ?; null stays NULL), so a caller cannot change it.
    Output: text, a JSON result (see the module docstring). A failing step reports {"ok": false, "error"}.
    sql: System Data's SQL IDs (app_template.SYSTEM_SQL, or the base app's)."""
    if not statement or inputs not in (("key",), ("values",)):
        raise ValueError("a SQL service has a fixed statement and one input, key or values")
    pid, version = "1." + uid(), uid()
    string, params_type, result_type = system(SYSTEM_TYPES["String"]), system(sql["types"]["SQLParameter"]), system(sql["types"]["SQLResult"])
    params = [parameter(pid, n, 1, i, string) for i, n in enumerate(inputs, 1)] + [parameter(pid, "text", 2, len(inputs) + 1, string)]
    ids = {n: p.split("<processParameterId>")[1].split("<")[0] for n, p in zip((*inputs, "text"), params, strict=True)}
    variables = [variable(pid, "sqlParams", 1, params_type, True), variable(pid, "sqlResults", 2, result_type, True)]
    build, call, text, report, end = ("2025." + uid() for _ in range(5))
    exit_id, sub_id = "3008." + uid(), "3012." + uid()
    values_script = FIXED_VALUES.replace("__VALUES__", VALUES_FROM[inputs[0]]).replace("__COUNT__", str(statement.count("?")))
    build_sid, build_xml = script_component(BUILD_PARAMS.replace("__VALUES__", values_script))
    text_sid, text_xml = script_component(RESULT_JSON)
    report_sid, report_xml = script_component(REPORT_ERROR)
    sub_xml = (f'<TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><subProcessId>{sub_id}</subProcessId>'
               f"<attachedProcessRef>{system(sql['service'])}</attachedProcessRef><guid>{uid()}</guid><versionId>{uid()}</versionId>"
               + mapping(sub_id, "sql", sql["parameters"]["sql"], json.dumps(statement), string, True)
               + mapping(sub_id, "parameters", sql["parameters"]["parameters"], "tw.local.sqlParams", params_type, True, True)
               + mapping(sub_id, "maxRows", sql["parameters"]["maxRows"], str(MAX_ROWS), system(SYSTEM_TYPES["Integer"]), True)
               + mapping(sub_id, "dataSourceName", sql["parameters"]["dataSourceName"], json.dumps(data_source), string, True)
               + mapping(sub_id, "results", sql["parameters"]["results"], "tw.local.sqlResults", result_type, False, True)
               + "</TWComponent>")
    end_xml = (f'<TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><exitPointId>{exit_id}</exitPointId>'
               f"<haltProcess>false</haltProcess><guid>{uid()}</guid><versionId>{uid()}</versionId></TWComponent>")
    items = "".join(item_xml(error_handler=handler, item_id=item, pid=pid, name=label, component=kind, component_id=cid, guid=uid(), version=uid(), x=x, component_xml=xml)
                    for item, label, kind, cid, x, xml, handler in [
                        (build, "Build parameters", "Script", build_sid, 100, build_xml, report),
                        (call, "SQL Execute Statement (SQLResult)", "SubProcess", sub_id, 250, sub_xml, report),
                        (text, "Result as JSON", "Script", text_sid, 400, text_xml, report),
                        (report, "Report error", "Script", report_sid, 400, report_xml, None),
                        (end, "End", "ExitPoint", exit_id, 550, end_xml, None)])
    links = link(pid, build, call, "Out") + link(pid, call, text, sql["exit"]) + link(pid, text, end, "Out") + link(pid, report, end, "Out")
    null = lambda *names: "".join(f'<{n} isNull="true" />' for n in names)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><process id="{pid}" name="{escape(name)}"><lastModified>0</lastModified><lastModifiedBy>{author}</lastModifiedBy>{null("tenantId")}
<processId>{pid}</processId>{null("image", "tabGroup")}<startingProcessItemId>{build}</startingProcessItemId><isRootProcess>false</isRootProcess><processType>6</processType>
<isErrorHandlerEnabled>false</isErrorHandlerEnabled>{null("errorHandlerItemId")}<isLoggingVariables>false</isLoggingVariables><isTransactional>false</isTransactional>
{null("processTimingLevel", "participantRef", "exposedType")}<isTrackingEnabled>true</isTrackingEnabled>{null("xmlData")}<cachingType>false</cachingType>
{null("itemLabel")}<cacheLength>43200</cacheLength><mobileReady>false</mobileReady><sboSyncEnabled>true</sboSyncEnabled>{null("externalId")}<isSecured>false</isSecured>
<isAjaxExposed>true</isAjaxExposed><isInvokedAsynchronously>false</isInvokedAsynchronously><isTransactionalFlow>false</isTransactionalFlow>
<description>{escape(f"Runs a fixed statement through {data_source}.")}</description><guid>{uid()}</guid><versionId>{version}</versionId>
{null("dependencySummary", "jsonData", "businessDataAliases", "field1", "field2")}<field3>0</field3>{null("field4")}<field5>false</field5>{null("clobField1", "blobField1")}
{"".join(params)}{"".join(variables)}{items}<startingProcessItemId>{build}</startingProcessItemId>{null("errorHandlerItemId")}
<layoutData noConversion="true"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
<startPoint><layoutData x="20" y="100"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData></startPoint>
<startLink><fromPort locationId="rightCenter" portType="1" /><toPort locationId="leftCenter" portType="2" />{NO_LINK_LAYOUT}</startLink>
{links}</process></teamworks>
"""
    return pid, version, name, "process", xml, ids


def call_step(service, result_expr: str, **inputs: str) -> dict:
    """A coach_builder service-call step. inputs: a JavaScript expression (giving a string) for each input of the service."""
    pid, ids, string = service[0], service[5], SYSTEM_TYPES["String"]
    return {"call": pid, "in": [(ids[name], expr, string) for name, expr in inputs.items()], "out": [(ids["text"], result_expr, string)]}


def database_services(plan: dict, bo: str, sql=app_template.SYSTEM_SQL) -> dict:
    """The two services of a database section: {"load": "Load <BO>" (input key), "save": "Save <BO>" (input values)},
    each as run_sql_service() gives it, with its statement fixed inside."""
    return {"load": run_sql_service(f"Load {bo}", load_sql(plan), ("key",), sql=sql), "save": run_sql_service(f"Save {bo}", save_sql(plan), ("values",), sql=sql)}


# ---------------------------------------------------------------- app spec "database" section


def quote(name: str) -> str:
    """A table, schema or column name as a PostgreSQL identifier: the only way a name enters SQL text."""
    if not NAME.match(name):
        raise ValueError(f"{name!r} is not a valid name")
    return f'"{name}"'


def name_error(name, what: str, schema=False):
    """Why a schema, table or column name is refused, or None."""
    if not isinstance(name, str) or not NAME.match(name):
        return f"{what} {name!r} is not allowed: use lower case letters, digits and underscores, starting with a letter or underscore, at most 63 characters"
    if schema and (name in ("pg_catalog", "information_schema") or name.startswith("pg_")):
        return f"{what} {name!r} is a system schema; use a schema for app data, such as public"
    return None


def snake_case(name: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)).lower()


def table_plan(db, fields: list) -> tuple[dict | None, list]:
    """Check a spec's "database" section against the form's fields; returns (plan, errors).
    fields: {"name", "label", "type": a BAW type name} for every field to store, in order (all are simple); a field
    with "derived" set (the reference number) is stored but cannot be the key.
    A field with "text" set is an Integer or Decimal that the form holds as text (empty means NULL).
    The plan: {"schema", "table", "key", "keyLabel", "columns": [{"field", "label", "column", "type", "pg", "key", "text"}]}."""
    if not isinstance(db, dict):
        return None, ['database must be an object: {"table": "public.name", "key": "<field>", "columns": {"<field>": "<column>"}}']
    errors = [f"database.{k} is not a setting (the data source is always {DATA_SOURCE}); use table, key and columns" for k in db if k not in ("table", "key", "columns")]
    schema, _, table = (db.get("table") or "").partition(".")
    if not table:
        errors.append('database.table must be "schema.name", e.g. "public.equipment_request"')
    else:
        errors += [e for e in (name_error(schema, "database.table schema", schema=True), name_error(table, "database.table name")) if e]
    by_name = {f["name"]: f for f in fields}
    key = db.get("key")
    choices = [n for n, f in by_name.items() if not f.get("derived")]
    if key not in choices:
        errors.append(f"database.key must name one of the form's fields ({', '.join(choices)}), not {key!r}")
    renames = db.get("columns") or {}
    if not isinstance(renames, dict):
        errors.append("database.columns must map field names to column names")
        renames = {}
    columns = []
    for f in fields:
        column = renames.get(f["name"], snake_case(f["name"]))
        if f["type"] not in PG_TYPES:
            errors.append(f"database: field {f['name']!r} has type {f['type']!r}; only String, Integer, Decimal, Boolean and Date fields can be stored")
        elif error := name_error(column, f"database column for field {f['name']!r} named"):
            errors.append(error)
        columns.append({"field": f["name"], "label": f["label"], "column": column, "type": f["type"], "pg": PG_TYPES.get(f["type"]), "key": f["name"] == key,
                        "text": bool(f.get("text"))})
    errors += [f"database.columns: {n!r} is not a field of the form" for n in renames if n not in by_name]
    names = [c["column"] for c in columns]
    errors += [f"database: column {n!r} is used for more than one field" for n in sorted({n for n in names if names.count(n) > 1})]
    if errors:
        return None, errors
    return {"schema": schema, "table": table, "key": key, "keyLabel": by_name[key]["label"], "columns": columns}, []


def qualified(plan: dict) -> str:
    return f"{quote(plan['schema'])}.{quote(plan['table'])}"


def ddl(plan: dict) -> str:
    """CREATE TABLE IF NOT EXISTS for the plan, one statement; the key column is the primary key."""
    cols = ", ".join(f"{quote(c['column'])} {c['pg']}" + (" PRIMARY KEY" if c["key"] else "") for c in plan["columns"])
    return f"CREATE TABLE IF NOT EXISTS {qualified(plan)} ({cols})"


def key_column(plan: dict) -> dict:
    return next(c for c in plan["columns"] if c["key"])


def load_sql(plan: dict) -> str:
    """SELECT of every column by key (one ? for the key). Every column comes back as text, and an instant as
    ISO-8601 in UTC, so a row is read the same whatever the Java type behind it."""
    cols = ", ".join(f"to_char({quote(c['column'])} AT TIME ZONE 'UTC', '{ISO_UTC}')" if c["pg"] == "timestamptz"
                     else f"CAST({quote(c['column'])} AS text)" for c in plan["columns"])
    key = key_column(plan)
    return f"SELECT {cols} FROM {qualified(plan)} WHERE {quote(key['column'])} = CAST(? AS {key['pg']})"


def save_sql(plan: dict) -> str:
    """Upsert of every column (one ? per column, in plan order, each typed with CAST)."""
    cols = plan["columns"]
    key = key_column(plan)
    values = ", ".join(f"CAST(? AS {c['pg']})" for c in cols)
    others = [c for c in cols if not c["key"]]
    action = "DO UPDATE SET " + ", ".join(f"{quote(c['column'])} = EXCLUDED.{quote(c['column'])}" for c in others) if others else "DO NOTHING"
    return (f"INSERT INTO {qualified(plan)} ({', '.join(quote(c['column']) for c in cols)}) VALUES ({values}) "
            f"ON CONFLICT ({quote(key['column'])}) {action}")


def database_result(plan: dict) -> dict:
    """What create_app reports to Bob: the table, the DDL to run, and the columns to compare with describe_table."""
    return {"table": f"{plan['schema']}.{plan['table']}", "ddl": ddl(plan),
            "columns": [{"name": c["column"], "type": c["pg"], "primaryKey": c["key"]} for c in plan["columns"]]}


# Client-side scripts and expressions of the Load and Save steps. Values travel as one JSON array of strings (an
# empty value is null), and the called service answers with the JSON result in the business object's dbMessage.

def cell(var: str, column: dict) -> str:
    v = f"tw.local.{var}.{column['field']}"
    if column["text"]:  # a number typed as text: spaces around it do not count, and nothing typed is NULL
        return f'({v} == null || String({v}).trim() === "" ? null : String({v}).trim())'
    text = f"({v}.toISOString ? {v}.toISOString() : String({v}))" if column["type"] == "Date" else f"String({v})"
    return f'({v} == null || {v} === "" ? null : {text})'


def values_expression(var: str, columns: list) -> str:
    return "JSON.stringify([" + ", ".join(cell(var, c) for c in columns) + "])"


def reply(var: str) -> str:
    """JavaScript that parses the service's answer into res (null when there is none)."""
    return f"var res = null;\ntry {{ res = JSON.parse(tw.local.{var}.{MESSAGE}); }} catch (e) {{ res = null; }}"


def failure(what: str) -> str:
    return f'"Could not {what}: " + (res != null && res.error ? res.error : "the database service did not answer")'


NUMBER_PATTERNS = {"Integer": (r"^-?\d+$", "a whole number"), "Decimal": (r"^-?(\d+\.?\d*|\.\d+)$", "a number, such as 1234.56")}


def missing_key_script(var: str, plan: dict, action: str, numbers=False) -> str:
    """Sets the message to ask for the key, or to nothing when the key is there. With numbers, a number typed as text
    that is not a number also gets a message (the database would refuse it)."""
    obj, key, ask = f"tw.local.{var}", f"tw.local.{var}.{plan['key']}", json.dumps(f"Enter {plan['keyLabel']} {action}.")
    script = f'{obj}.{MESSAGE} = ({key} == null || {key} === "") ? {ask} : "";'
    for c in plan["columns"] if numbers else []:
        if c["text"]:
            pattern, kind = NUMBER_PATTERNS[c["type"]]
            v, bad = f"{obj}.{c['field']}", json.dumps(f"{c['label']} must be {kind}.")
            script += f'\nif ({obj}.{MESSAGE} === "" && {v} != null && String({v}).trim() !== "" && !/{pattern}/.test(String({v}).trim())) {{ {obj}.{MESSAGE} = {bad}; }}'
    return script


def load_apply_script(var: str, plan: dict) -> str:
    """After the Load call: fill the form from the row, or leave a message (no key, no row, or a failure)."""
    obj, key, ask = f"tw.local.{var}", f"tw.local.{var}.{plan['key']}", json.dumps(f"Enter {plan['keyLabel']}, then press Load.")
    parse = {"Integer": "{v} === null ? null : parseInt({v}, 10)", "Decimal": "{v} === null ? null : parseFloat({v})",
             "Boolean": '{v} === "true"', "Date": "{v} === null ? null : new Date({v})", "String": "{v}"}
    fill = "\n".join(f"  {obj}.{c['field']} = {parse['String' if c['text'] else c['type']].format(v=f'row[{i}]')};" for i, c in enumerate(plan["columns"]))
    return (f'{reply(var)}\nif ({key} == null || {key} === "") {{\n  {obj}.{MESSAGE} = {ask};\n}}'
            f' else if (res == null || res.ok !== true) {{\n  {obj}.{MESSAGE} = {failure("load")};\n}}'
            f' else if (res.rows.length == 0) {{\n  {obj}.{MESSAGE} = "No record found for " + {key};\n}}'
            f' else {{\n  var row = res.rows[0];\n{fill}\n  {obj}.{MESSAGE} = "";\n}}')


def save_apply_script(var: str) -> str:
    """After the Save call: an empty message when it worked, else why it did not."""
    return f'{reply(var)}\ntw.local.{var}.{MESSAGE} = (res != null && res.ok === true) ? "" : {failure("save")};'


def check_data_source(twx: Path, sql: dict = app_template.SYSTEM_SQL):
    """Fail unless every call to SQL Execute Statement in the package maps dataSourceName to DATA_SOURCE and takes a
    fixed statement (a constant, not a value that a caller or another step supplies), and nothing in the package
    names System Data's default data source (BAW's own database). Returns the number of calls."""
    errors, calls = [], 0
    with zipfile.ZipFile(twx) as z:
        for name in z.namelist():
            if not name.startswith("objects/") or not name.endswith(".xml"):
                continue
            text = z.read(name).decode("utf-8")
            if "jdbc/TeamWorksDB" in text:
                errors.append(f"{name} names jdbc/TeamWorksDB")
            for item in ElementTree.fromstring(text.encode("utf-8")).iter("item"):
                call = item.find("TWComponent")
                ref = call.findtext("attachedProcessRef") if call is not None else None
                if not ref or ref.rsplit("/", 1)[-1] != sql["service"]:
                    continue
                calls += 1
                mapped = {p: [m.findtext("value") for m in call.iter("parameterMapping") if m.findtext("processParameterId") == sql["parameters"][p]]
                          for p in ("dataSourceName", "sql")}
                if mapped["dataSourceName"] != [json.dumps(DATA_SOURCE)]:
                    errors.append(f"{name}: a call to SQL Execute Statement maps dataSourceName to {mapped['dataSourceName'] or 'nothing'}, not {DATA_SOURCE}")
                if len(mapped["sql"]) != 1 or not is_constant(mapped["sql"][0]):
                    errors.append(f"{name}: a call to SQL Execute Statement does not take a fixed statement")
    if errors:
        raise ValueError("Generated SQL calls do not all use " + DATA_SOURCE + " with a fixed statement:\n  " + "\n  ".join(errors))
    return calls


def is_constant(expression) -> bool:
    """True when a mapping value is one string literal."""
    try:
        return isinstance(json.loads(expression or ""), str)
    except ValueError:
        return False


CHECKS = [  # (BO property, label, SQL, values as JavaScript giving a JSON string)
    ("whoami", "Who am I", "SELECT current_user AS role_name, session_user AS login, current_database() AS db, now() AS at", '"[]"'),
    ("tx", "Transaction mode", ("SELECT xact_start = query_start AS own_transaction, backend_xid IS NOT NULL AS has_xid, application_name "
     "FROM pg_stat_activity WHERE pid = pg_backend_pid()"), '"[]"'),
    ("upsert", "Typed upsert",
     ("INSERT INTO zz_check_spike (id, label, qty, price, active, due) VALUES (CAST(? AS integer), CAST(? AS text), CAST(? AS integer), "
     "CAST(? AS numeric), CAST(? AS boolean), CAST(? AS timestamptz)) ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label, "
     "qty = EXCLUDED.qty, price = EXCLUDED.price, active = EXCLUDED.active, due = EXCLUDED.due"),
     'JSON.stringify([1, "first", 42, "12.50", "true", "2026-10-23T15:30:00Z"])'),
    ("empty", "Upsert with empty number and date",
     ("INSERT INTO zz_check_spike (id, label, qty, price, active, due) VALUES (CAST(? AS integer), CAST(? AS text), CAST(? AS integer), "
     "CAST(? AS numeric), CAST(? AS boolean), CAST(? AS timestamptz)) ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label, "
     "qty = EXCLUDED.qty, price = EXCLUDED.price, active = EXCLUDED.active, due = EXCLUDED.due"),
     """JSON.stringify([2, "'); DROP TABLE x; --", null, "7", "false", null])"""),
    ("readback", "Read back", "SELECT id, label, qty, price, active, due FROM zz_check_spike WHERE id <= CAST(? AS integer) ORDER BY id",
     'JSON.stringify([2])'),
]


def spike_app(dest: Path, snapshot: str, base: Path | None = None):
    service = {"name": "SQL Check", "description": "Runs SQL through jdbc/bawexternal and shows the results."}
    lay = Layout()
    outputs = [lay.view("Output Text", label, binding=f"tw.local.check.{prop}") for prop, label, _, _ in CHECKS]
    done_id, done = lay.button("Done", "P")
    coach = (Layout.wrap([lay.html("<h2>SQL through jdbc/bawexternal</h2>"), *outputs, done]), {"done": done_id})
    steps = [("init", "Init", "tw.local.check = {};")]
    services = [run_sql_service(label, sql) for _, label, sql, _ in CHECKS]
    steps += [(prop, label, call_step(svc, f"tw.local.check.{prop}", values=values))
              for (prop, label, _, values), svc in zip(CHECKS, services, strict=True)]
    steps += [("results", "Results", coach)]
    keys = [k for k, _, _ in steps]
    flows = [("start", keys[0], None, "rightCenter", "leftCenter")]
    flows += [(a, b, None, "rightCenter", "leftCenter") for a, b in pairwise(keys)]
    flows += [(keys[-1], "end", "done", "rightCenter", "leftCenter")]
    props = [(prop, "String") for prop, _, _, _ in CHECKS]
    write_twx(dest, {"name": "ZZ SQL Check", "acronym": "ZZSQL", "snapshot": snapshot},
              {"id": "12." + uid(), "version": uid(), "name": "SqlCheck", "props": props}, "check",
              [("1." + uid(), uid(), "2056." + uid(), service, lambda b, v: coachflow(service, steps, flows, b, v, "check"))],
              "sql_service", app_template.read_base(base) if base else None, [s[:5] for s in services])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dest")
    parser.add_argument("--snapshot", default="0.1")
    parser.add_argument("--base", help="an export of the installed app, so the package becomes its next snapshot")
    a = parser.parse_args()
    spike_app(Path(a.dest), a.snapshot, Path(a.base) if a.base else None)
    print(a.dest)


if __name__ == "__main__":
    main()
