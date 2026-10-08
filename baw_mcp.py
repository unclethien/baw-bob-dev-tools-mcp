#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""
BAW Dev Tools: an MCP server (stdio) that gives an agent the platform operations it needs to
build and modernize IBM BAW process apps, so the agent only designs and writes code.

The agent authors the artifacts (app specs, coach specs, React screens). These tools package,
install, inspect and test them on the BAW server set by BAW_URL (environment first, then .env;
see baw_ops.py). Credentials stay in this process and are never returned. Installs are limited to "ZZ" demo apps, and there is
no delete tool.

Run:  uv run --script baw_mcp.py      (Bob starts it from .bob/mcp.json)
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import zipfile
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
REACT = ROOT / "react-coach"
sys.path.insert(0, str(ROOT))

from baw_ops import BawOps, ConfigError  # noqa: E402

mcp = MCPServer("baw-dev-tools", instructions=(
    "Platform tools for IBM BAW on CP4BA. You design and write: app specs (work/<ACR>.app.json), "
    "coach specs (work/*.coaches.json) and React screens (react-coach/src/screens/*.jsx). "
    "These tools build, install, inspect and test them. Paths are relative to the project root."))
_ops = None


def ops() -> BawOps:
    global _ops
    if _ops is None:
        try:
            _ops = BawOps()
        except ConfigError as e:
            raise ToolError(str(e))
        except urllib.error.HTTPError as e:
            raise ToolError(f"Login to BAW_URL ({os.environ['BAW_URL']}) failed with HTTP {e.code}; check BAW_USER and BAW_PASSWORD / BAW_APIKEY")
        except (urllib.error.URLError, OSError) as e:
            raise ToolError(f"Cannot reach BAW_URL ({os.environ['BAW_URL']}): {getattr(e, 'reason', e)}")
    return _ops


def local(path: str) -> Path:
    """A path inside the project; anything outside is refused."""
    full = (ROOT / path).resolve()
    if ROOT not in full.parents:
        raise ToolError(f"{path} is outside the project")
    return full


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def run(args, cwd=ROOT, timeout=600):
    """Run a project script; return its output, or raise with it so the agent can fix the input."""
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    output = (result.stdout + result.stderr).strip()
    if result.returncode:
        raise ToolError(output[:4000] or f"{args[0]} failed with exit code {result.returncode}")
    return output


def python(script, *args, timeout=600):
    return run([sys.executable, str(ROOT / script), *map(str, args)], timeout=timeout)


def package_xml(twx: Path) -> str:
    with zipfile.ZipFile(twx) as z:
        return z.read("META-INF/package.xml").decode("utf-8")


def target_of(twx: Path) -> dict:
    """App acronym, name and snapshot that a .twx installs into."""
    target = re.search(r"<target>(.*?)</target>", package_xml(twx), re.S).group(1)
    attr = lambda tag, key: re.search(rf'<{tag} [^>]*\b{key}="([^"]*)"', target).group(1)  # noqa: E731
    return {"acronym": attr("project", "shortName"), "name": attr("project", "name"), "snapshot": attr("snapshot", "name"),
            "projectId": attr("project", "id"), "branchId": attr("branch", "id")}


def snapshots(acronym: str) -> list[dict]:
    try:
        versions = ops().versions(acronym)["versions"]
    except Exception:
        return []
    return sorted((v for v in versions if not v.get("archived")), key=lambda v: v.get("creation_date", ""))


def newest(found: list[dict]) -> dict:
    return found[-1]


def require_new_snapshot(acronym: str, snapshot: str):
    if any(v["version_name"] == snapshot or v["version"] == snapshot for v in snapshots(acronym)):
        raise ToolError(f"Snapshot {snapshot} already exists in {acronym}; BAW would keep the old content. Use a new snapshot name")


# ---------------------------------------------------------------- server: read


@mcp.tool()
def list_apps() -> list[dict]:
    """Process apps and toolkits installed on the BAW server."""
    return [{"acronym": c.get("container"), "name": c.get("container_name"), "toolkit": bool(c.get("toolkit"))}
            for c in ops().list_containers().get("containers", []) if not c.get("archived")]


@mcp.tool()
def list_snapshots(acronym: str) -> list[dict]:
    """Snapshots of one process app, oldest first."""
    return [{"snapshot": v["version_name"], "created": v.get("creation_date")} for v in snapshots(acronym)]


@mcp.tool()
def list_services(acronym: str, snapshot: str | None = None) -> list[dict]:
    """Services of an app that users can launch, with their run URLs (newest snapshot unless one is named)."""
    return [{"service": i.get("display"), "snapshot": i.get("snapshotName"), "url": i.get("runURL")}
            for i in ops().services(acronym, snapshot)]


@mcp.tool()
def export_app(acronym: str, snapshot: str | None = None) -> dict:
    """Download a snapshot of a process app (the newest unless named) to work/<ACR>-<snapshot>.twx."""
    found = snapshots(acronym)
    if not found:
        raise ToolError(f"No process app {acronym} on the server")
    match = [v for v in found if snapshot in (v["version_name"], v["version"])] if snapshot else [newest(found)]
    if not match:
        raise ToolError(f"{acronym} has no snapshot {snapshot}; it has {', '.join(v['version_name'] for v in found)}")
    version = match[0]
    WORK.mkdir(exist_ok=True)
    dest = WORK / f"{acronym}-{re.sub(r'[^A-Za-z0-9.]+', '_', version['version_name'])}.twx"
    size = ops().export(acronym, version["version"], dest)
    return {"twx": rel(dest), "snapshot": version["version_name"], "bytes": size}


# ---------------------------------------------------------------- build


@mcp.tool()
def inspect_coaches(twx: str) -> dict:
    """Read every coach of an app's client-side human services into an editable coach spec
    (work/<name>.coaches.json): sections, fields, buttons and where each button goes."""
    source = local(twx)
    out = WORK / f"{source.stem}.coaches.json"
    summary = python("coach_inventory.py", source, "-o", out)
    return {"coachSpec": rel(out), "summary": summary}


@mcp.tool()
def create_app(app_spec: str) -> dict:
    """Build an installable .twx from an app spec (see app-specs/example-equipment-request.json).
    When the app already exists on the server, the build becomes a new snapshot of that app."""
    spec_path = local(app_spec)
    app = json.loads(spec_path.read_text())["app"]
    acronym, snapshot = app.get("acronym", ""), app.get("snapshot", "1.0.0")
    WORK.mkdir(exist_ok=True)
    dest = WORK / f"{acronym}-{snapshot}.twx"
    existing = snapshots(acronym)
    if not existing:
        summary = python("generate_app.py", spec_path, dest)
        return {"twx": rel(dest), "newApp": True, "summary": summary}
    require_new_snapshot(acronym, snapshot)
    with tempfile.TemporaryDirectory() as tmp:
        current, built = Path(tmp) / "current.twx", Path(tmp) / "built.twx"
        ops().export(acronym, newest(existing)["version"], current)
        ids = target_of(current)
        summary = python("generate_app.py", spec_path, built)
        python("twx_clone.py", built, dest, "--name", app["name"], "--acronym", acronym, "--snapshot", snapshot,
               "--project-id", ids["projectId"], "--branch-id", ids["branchId"])
    return {"twx": rel(dest), "newApp": False, "summary": summary + f"\nBuilt as snapshot {snapshot} of the existing app {acronym}"}


@mcp.tool()
def build_screens() -> str:
    """Compile the React screens (react-coach/src) into the bundle. Returns compiler output;
    fix any error it reports in your screen file and build again."""
    return run(["npm", "run", "build", "--silent"], cwd=REACT, timeout=300) or "Built react-coach/bundle"


@mcp.tool()
def modernize_app(twx: str, coach_spec: str, snapshot: str) -> dict:
    """Add React + Carbon copies of the app's services, one per theme, driven by the coach spec.
    A coach with "screen": "<name>" uses the React screen registered under that name; the others
    use the generic form. Builds the screens first. Output: a new snapshot of the same app."""
    source, spec = local(twx), local(coach_spec)
    require_new_snapshot(target_of(source)["acronym"], snapshot)
    build = build_screens()
    dest = WORK / f"{target_of(source)['acronym']}-{snapshot}.twx"
    summary = python("modernize_coaches.py", source, spec, dest, "--snapshot", snapshot)
    return {"twx": rel(dest), "summary": summary, "build": build[-500:]}


# ---------------------------------------------------------------- server: change and test


@mcp.tool()
def install_app(twx: str) -> dict:
    """Install a .twx on the server and wait until it finishes. Only "ZZ" demo apps can be installed."""
    path = local(twx)
    target = target_of(path)
    if not target["acronym"].startswith("ZZ") or not target["name"].startswith("ZZ"):
        raise ToolError(f'Refusing to install into {target["acronym"]} ({target["name"]}): only apps named "ZZ ..." with a ZZ acronym')
    require_new_snapshot(target["acronym"], target["snapshot"])
    result = ops().install(path)
    state = str(result.get("state", result.get("status", ""))).lower()
    return {"acronym": target["acronym"], "name": target["name"], "snapshot": target["snapshot"], "state": state, "ok": state in ("success", "successful", "complete", "completed", "finished"),
            "details": str(result.get("result", ""))[:1000]}


@mcp.tool()
def test_service(acronym: str, service: str, snapshot: str | None = None, fill: bool = True) -> dict:
    """Run a service in a real browser: screenshot every screen, fill empty fields with sample
    values (fill), press the forward button, and report each step. "ok": true means every screen
    rendered and every button moved on. Look at the screenshots before calling the work done."""
    out = WORK / ("shots-" + re.sub(r"[^A-Za-z0-9]+", "-", f"{acronym}-{snapshot or 'tip'}-{service}").strip("-"))
    args = ["node", "scripts/verify-service.mjs", "--app", acronym, "--service", service, "--out", str(out)]
    if snapshot:
        args += ["--snapshot", snapshot]
    if fill:
        args.append("--fill")
    result = subprocess.run(args, cwd=REACT, capture_output=True, text=True, timeout=600)
    try:
        report = json.loads(result.stdout[result.stdout.index("{"):])
    except ValueError:
        raise ToolError((result.stdout + result.stderr)[-3000:])
    for step in report.get("steps", []):
        step["screenshot"] = rel((REACT / step["screenshot"]).resolve())
    return report


if __name__ == "__main__":
    mcp.run()
