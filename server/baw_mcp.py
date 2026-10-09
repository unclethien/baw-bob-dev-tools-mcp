#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.3,<3", "pillow>=10"]
# ///
"""
BAW Dev Tools: an MCP server (stdio) that gives an agent the platform operations it needs to
build and modernize IBM BAW process apps, so the agent only designs and writes code.

The agent authors the artifacts (app specs, coach specs, React screens). These tools package,
install, inspect and test them on the BAW server set by BAW_URL (environment first, then .env;
see baw_ops.py). Credentials stay in this process and are never returned. Installs are limited to "ZZ" demo apps, and there is
no delete tool. Without a server, the build tools still work: the user imports the .twx in Workflow Center.

Run:  uv run --script server/baw_mcp.py      (Bob starts it from .bob/mcp.json)
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
from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError

SERVER = Path(__file__).resolve().parent
ROOT = SERVER.parent
WORK = ROOT / "work"
REACT = ROOT / "react-coach"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
sys.path.insert(0, str(SERVER))

from baw_ops import BawOps, ConfigError, configured, missing_settings  # noqa: E402

mcp = MCPServer("baw-dev-tools", instructions=(
    "Platform tools for IBM BAW on CP4BA. You design and write: app specs (work/<ACR>.app.json), "
    "coach specs (work/*.coaches.json) and React screens (react-coach/src/screens/*.jsx). "
    "These tools build, install, inspect and test them; view_image shows a screenshot to build from "
    "or to compare with, image_colors reads its exact colours and crop_image cuts out its logo. "
    "Paths are relative to the project root. Without a BAW server (BAW_URL not set), the build tools still "
    "work and the user imports the .twx in Workflow Center."))
_ops = None
IMPORT_STEPS = ("No BAW server is configured, so import {twx} yourself: in Workflow Center, open Process Apps, click Import, "
                "choose the file and finish the wizard. Its snapshot name must be new in that app. Then run the service "
                "from Workflow Center and test it by hand.")


def offline() -> ToolError:
    return ToolError(f"No BAW server is configured (missing {', '.join(missing_settings())}). create_app, inspect_coaches, "
                     "modernize_app and the image tools work without one; import the .twx in Workflow Center. To use this tool, "
                     "set BAW_URL, BAW_USER and BAW_PASSWORD or BAW_APIKEY in .env or in the env block of .bob/mcp.json")


def ops() -> BawOps:
    global _ops
    if _ops is None:
        if not configured():
            raise offline()
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
    return run([sys.executable, str(SERVER / script), *map(str, args)], timeout=timeout)


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
    except urllib.error.HTTPError:  # no such app
        return []
    return sorted((v for v in versions if not v.get("archived")), key=lambda v: v.get("creation_date", ""))


def newest(found: list[dict]) -> dict:
    return found[-1]


def require_new_snapshot(acronym: str, snapshot: str):
    if not configured():  # checked by the user when importing
        return
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


@mcp.tool()
def view_image(path: str) -> Image:
    """Show an image file from the project: a screenshot of a UI to build an app from, or a
    screenshot test_service took. Paths are relative to the project root, e.g. screenshots/form.png."""
    image = local(path)
    if image.suffix.lower() not in IMAGE_TYPES or not image.is_file():
        raise ToolError(f"{path} is not a PNG, JPEG, GIF or WebP file in the project")
    if image.stat().st_size > 8_000_000:
        raise ToolError(f"{path} is larger than 8 MB; crop or compress it")
    return Image(path=image)


def open_image(path: str, box):
    """The image at path, cropped to box: [left, top, right, bottom] as fractions (0-1) of its width and height."""
    from PIL import Image as Pil
    source = local(path)
    if source.suffix.lower() not in IMAGE_TYPES or not source.is_file():
        raise ToolError(f"{path} is not a PNG, JPEG, GIF or WebP file in the project")
    image = Pil.open(source).convert("RGB")
    if box is None:
        return image
    if len(box) != 4 or not all(0 <= b <= 1 for b in box) or box[0] >= box[2] or box[1] >= box[3]:
        raise ToolError("box must be [left, top, right, bottom] as fractions from 0 to 1, left < right and top < bottom")
    w, h = image.size
    return image.crop((round(box[0] * w), round(box[1] * h), max(round(box[2] * w), round(box[0] * w) + 1), max(round(box[3] * h), round(box[1] * h) + 1)))


@mcp.tool()
def image_colors(path: str, box: list[float] | None = None, count: int = 5) -> list[dict]:
    """The main colours of an image file, or of one region of it, as hex with their share of the area.
    box is [left, top, right, bottom] as fractions (0-1) of the image, e.g. [0, 0, 1, 0.15] for a
    header strip. Use it to read the exact colours of a screenshot's banner, section bars, tabs and buttons."""
    region = open_image(path, box)
    region.thumbnail((400, 400))
    quantized = region.quantize(colors=max(1, min(count, 12)) + 3)
    palette, total = quantized.getpalette(), region.width * region.height
    colours = sorted(quantized.getcolors(), reverse=True)[:count]
    return [{"hex": "#{:02x}{:02x}{:02x}".format(*palette[i * 3:i * 3 + 3]), "share": round(n / total, 3)} for n, i in colours]


@mcp.tool()
def crop_image(path: str, box: list[float], dest: str) -> Image:
    """Cut a region out of an image file and save it as a PNG in work/, e.g. the logo of a screenshot
    for the app spec's banner.logo. box is [left, top, right, bottom] as fractions (0-1) of the image.
    Returns the crop so you can check it and adjust the box."""
    out = local(dest)
    if WORK not in out.parents or out.suffix.lower() != ".png":
        raise ToolError("dest must be a .png file in work/, e.g. work/logo.png")
    crop = open_image(path, box)
    crop.thumbnail((600, 240))
    out.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out, optimize=True)
    return Image(path=out)


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
def create_app(app_spec: str, base: str | None = None) -> dict:
    """Build an installable .twx from an app spec (see app-specs/example-equipment-request.json, and
    app-specs/example-themed-quote.json for a theme, banner, placed columns and field icons).
    The package comes from a built-in template, so no server is needed. base (optional) is an app on
    the server (its acronym) or an exported .twx in the project, to match that server's BAW build and
    toolkit versions; ask the user which app to use. When the app already exists on the server, the
    build becomes a new snapshot of it, and base is not needed."""
    spec_path = local(app_spec)
    app = json.loads(spec_path.read_text())["app"]
    acronym, snapshot = app.get("acronym", ""), app.get("snapshot", "1.0.0")
    WORK.mkdir(exist_ok=True)
    dest = WORK / f"{acronym}-{snapshot}.twx"
    online = configured()
    existing = snapshots(acronym) if online else []
    note = ""
    with tempfile.TemporaryDirectory() as tmp:
        base_twx = None
        if existing:
            require_new_snapshot(acronym, snapshot)
            base_twx = Path(tmp) / "current.twx"
            ops().export(acronym, newest(existing)["version"], base_twx, toolkits=False)
            note = f"Built as snapshot {snapshot} of the existing app {acronym}"
        elif base and base.endswith(".twx"):
            base_twx = local(base)
            note = (f"Built as snapshot {snapshot} of {acronym} (from {base})" if target_of(base_twx)["acronym"] == acronym
                    else f"Packaged to match {base}")
        elif base:
            found = snapshots(base)
            if not found:
                raise ToolError(f"No process app or toolkit {base} on the server; list_apps shows them")
            base_twx = Path(tmp) / "base.twx"
            ops().export(base, newest(found)["version"], base_twx, toolkits=False)
            note = f"Packaged to match {base} on the server"
        summary = python("generate_app.py", spec_path, dest, *(["--base", base_twx] if base_twx else []))
    result = {"twx": rel(dest), "newApp": not existing, "summary": summary + (f"\n{note}" if note else "")}
    if not online:
        result["install"] = IMPORT_STEPS.format(twx=rel(dest))
    return result


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
    result = {"twx": rel(dest), "summary": summary, "build": build[-500:]}
    if not configured():
        result["install"] = IMPORT_STEPS.format(twx=rel(dest))
    return result


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
    if not configured():
        raise offline()
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
