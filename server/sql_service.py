#!/usr/bin/env python3
"""
SQL from a generated BAW app, through a JNDI data source (jdbc/bawexternal by default).

run_sql_service() builds a heritage general system service, "Run SQL": it turns a JSON array of values into
System Data SQLParameters, runs System Data's "SQL Execute Statement (SQLResult)" with the data source mapped
explicitly (System Data's own default is jdbc/TeamWorksDB, BAW's own database), and returns the result as text.
A client-side human service calls it with a coach_builder service-call step (call_step()).

The CLI builds ZZSQL, a scratch app that checks the whole path on a server:
    python3 server/sql_service.py work/ZZSQL-0.1.twx --snapshot 0.1
"""

import argparse
import json
import sys
from itertools import pairwise
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app_template  # noqa: E402
from coach_builder import (  # noqa: E402
    ITEM,
    NO_LINK_LAYOUT,
    SYSTEM_TYPES,
    TWSYS,
    Layout,
    coachflow,
    uid,
    write_twx,
)

DATA_SOURCE = "jdbc/bawexternal"
# System Data's "SQL Execute Statement (SQLResult)", its parameters and its exit point (8.6.0.0_TC).
SQL_RESULT_SERVICE = "1.4e480adb-5741-4f5e-aead-27b3654e9cd2"
SQL_PARAMS = {"sql": "2055.25f5990f-9abf-4cf6-9101-497d43dee141", "parameters": "2055.8b844f2a-0a1f-4f12-b34b-e9fd5191dc43",
              "maxRows": "2055.53ee0328-837f-427d-b0a1-0255f36f7e0c", "dataSourceName": "2055.81a41d09-a504-4a63-bdaa-a92bac26ad7e",
              "results": "2055.976cdc78-9d8d-41d4-ae85-f6c9a50c6764"}
SQL_EXIT = "guid:d7766b7587753602:16bdf27c:11586c10093:-7fe7"
SQL_TYPES = {"SQLParameter": "12.f453f500-ca4e-4264-a371-72c1892e8b7c", "SQLResult": "12.3b1e3757-a1f4-4c3f-bbb8-16fecd4d65c1"}
MAX_ROWS = 1000

BUILD_PARAMS = """var values = JSON.parse(tw.local.values || "[]");
tw.local.sqlParams = new tw.object.listOf.SQLParameter();
for (var i = 0; i < values.length; i++) {
  var p = new tw.object.SQLParameter();
  p.value = values[i] === null ? null : String(values[i]);
  p.type = "VARCHAR";
  p.mode = "IN";
  tw.local.sqlParams[i] = p;
}"""

RESULT_TEXT = """var out = [];
try {
  var rs = tw.local.sqlResults;
  for (var i = 0; rs != null && i < rs.listLength; i++) {
    var r = rs[i], names = [];
    for (var k = 0; r.columns != null && k < r.columns.listLength; k++) names.push(r.columns[k].columnName);
    out.push("columns: " + names.join(","));
    for (var j = 0; r.rows != null && j < r.rows.listLength; j++) {
      var cells = [];
      for (var k = 0; k < names.length; k++) {
        var v = r.rows[j].data[k];
        cells.push(names[k] + "=" + (v == null ? "NULL" : String(v)));
      }
      out.push(cells.join("; "));
    }
    out.push("updateCount=" + r.updateCount);
  }
} catch (e) {
  out.push("error: " + e);
  try { out.push(tw.local.sqlResults.toXMLString()); } catch (e2) {}
}
tw.local.text = out.join(" | ");"""


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


def run_sql_service(name="Run SQL", data_source=DATA_SOURCE, author="sql_service"):
    """The "Run SQL" service: (id, versionId, name, type, xml, {"sql", "values", "text": parameter ids}).
    Inputs: sql (one statement, ? for each value) and values (a JSON array; null stays NULL). Output: text."""
    pid, version = "1." + uid(), uid()
    string = system(SYSTEM_TYPES["String"])
    params = [parameter(pid, "sql", 1, 1, string), parameter(pid, "values", 1, 2, string), parameter(pid, "text", 2, 3, string)]
    ids = {n: p.split("<processParameterId>")[1].split("<")[0] for n, p in zip(("sql", "values", "text"), params, strict=True)}
    variables = [variable(pid, "sqlParams", 1, system(SQL_TYPES["SQLParameter"]), True),
                 variable(pid, "sqlResults", 2, system(SQL_TYPES["SQLResult"]), True)]
    build, call, text, end = ("2025." + uid() for _ in range(4))
    exit_id, sub_id = "3008." + uid(), "3012." + uid()
    build_sid, build_xml = script_component(BUILD_PARAMS)
    text_sid, text_xml = script_component(RESULT_TEXT)
    sub_xml = (f'<TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><subProcessId>{sub_id}</subProcessId>'
               f"<attachedProcessRef>{system(SQL_RESULT_SERVICE)}</attachedProcessRef><guid>{uid()}</guid><versionId>{uid()}</versionId>"
               + mapping(sub_id, "sql", SQL_PARAMS["sql"], "tw.local.sql", string, True)
               + mapping(sub_id, "parameters", SQL_PARAMS["parameters"], "tw.local.sqlParams", system(SQL_TYPES["SQLParameter"]), True, True)
               + mapping(sub_id, "maxRows", SQL_PARAMS["maxRows"], str(MAX_ROWS), system(SYSTEM_TYPES["Integer"]), True)
               + mapping(sub_id, "dataSourceName", SQL_PARAMS["dataSourceName"], json.dumps(data_source), string, True)
               + mapping(sub_id, "results", SQL_PARAMS["results"], "tw.local.sqlResults", system(SQL_TYPES["SQLResult"]), False, True)
               + "</TWComponent>")
    items = "".join(ITEM.format(item_id=item, pid=pid, name=label, component=kind, component_id=cid, guid=uid(), version=uid(), x=x, component_xml=xml)
                    for item, label, kind, cid, x, xml in [
                        (build, "Build parameters", "Script", build_sid, 100, build_xml),
                        (call, "SQL Execute Statement (SQLResult)", "SubProcess", sub_id, 250, sub_xml),
                        (text, "Result as text", "Script", text_sid, 400, text_xml),
                        (end, "End", "ExitPoint", exit_id, 550,
                         (f'<TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" /><exitPointId>{exit_id}</exitPointId>'
                         f"<haltProcess>false</haltProcess><guid>{uid()}</guid><versionId>{uid()}</versionId></TWComponent>"))])
    links = link(pid, build, call, "Out") + link(pid, call, text, SQL_EXIT) + link(pid, text, end, "Out")
    null = lambda *names: "".join(f'<{n} isNull="true" />' for n in names)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks><process id="{pid}" name="{name}"><lastModified>0</lastModified><lastModifiedBy>{author}</lastModifiedBy>{null("tenantId")}
<processId>{pid}</processId>{null("image", "tabGroup")}<startingProcessItemId>{build}</startingProcessItemId><isRootProcess>false</isRootProcess><processType>6</processType>
<isErrorHandlerEnabled>false</isErrorHandlerEnabled>{null("errorHandlerItemId")}<isLoggingVariables>false</isLoggingVariables><isTransactional>false</isTransactional>
{null("processTimingLevel", "participantRef", "exposedType")}<isTrackingEnabled>true</isTrackingEnabled>{null("xmlData")}<cachingType>false</cachingType>
{null("itemLabel")}<cacheLength>43200</cacheLength><mobileReady>false</mobileReady><sboSyncEnabled>true</sboSyncEnabled>{null("externalId")}<isSecured>false</isSecured>
<isAjaxExposed>true</isAjaxExposed><isInvokedAsynchronously>false</isInvokedAsynchronously><isTransactionalFlow>false</isTransactionalFlow>
<description>Runs one SQL statement through {escape(data_source)}.</description><guid>{uid()}</guid><versionId>{version}</versionId>
{null("dependencySummary", "jsonData", "businessDataAliases", "field1", "field2")}<field3>0</field3>{null("field4")}<field5>false</field5>{null("clobField1", "blobField1")}
{"".join(params)}{"".join(variables)}{items}<startingProcessItemId>{build}</startingProcessItemId>{null("errorHandlerItemId")}
<layoutData noConversion="true"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
<startPoint><layoutData x="20" y="100"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData></startPoint>
<startLink><fromPort locationId="rightCenter" portType="1" /><toPort locationId="leftCenter" portType="2" />{NO_LINK_LAYOUT}</startLink>
{links}</process></teamworks>
"""
    return pid, version, name, "process", xml, ids


def call_step(service, sql: str, values_expr: str, result_expr: str) -> dict:
    """A coach_builder service-call step that runs sql with the values (a JavaScript expression giving a JSON string)."""
    pid, ids, string = service[0], service[5], SYSTEM_TYPES["String"]
    return {"call": pid, "in": [(ids["sql"], json.dumps(sql), string), (ids["values"], values_expr, string)],
            "out": [(ids["text"], result_expr, string)]}


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
    run_sql = run_sql_service()
    service = {"name": "SQL Check", "description": "Runs SQL through jdbc/bawexternal and shows the results."}
    lay = Layout()
    outputs = [lay.view("Output Text", label, binding=f"tw.local.check.{prop}") for prop, label, _, _ in CHECKS]
    done_id, done = lay.button("Done", "P")
    coach = (Layout.wrap([lay.html("<h2>SQL through jdbc/bawexternal</h2>"), *outputs, done]), {"done": done_id})
    steps = [("init", "Init", "tw.local.check = {};")]
    steps += [(prop, label, call_step(run_sql, sql, values, f"tw.local.check.{prop}")) for prop, label, sql, values in CHECKS]
    steps += [("results", "Results", coach)]
    keys = [k for k, _, _ in steps]
    flows = [("start", keys[0], None, "rightCenter", "leftCenter")]
    flows += [(a, b, None, "rightCenter", "leftCenter") for a, b in pairwise(keys)]
    flows += [(keys[-1], "end", "done", "rightCenter", "leftCenter")]
    props = [(prop, "String") for prop, _, _, _ in CHECKS]
    write_twx(dest, {"name": "ZZ SQL Check", "acronym": "ZZSQL", "snapshot": snapshot},
              {"id": "12." + uid(), "version": uid(), "name": "SqlCheck", "props": props}, "check",
              [("1." + uid(), uid(), "2056." + uid(), service, lambda b, v: coachflow(service, steps, flows, b, v, "check"))],
              "sql_service", app_template.read_base(base) if base else None, [run_sql[:5]])


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
