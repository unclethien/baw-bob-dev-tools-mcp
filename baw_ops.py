#!/usr/bin/env python3
"""
Minimal client for the BAW Operations REST API on Cloud Pak for Business Automation.

Settings: BAW_URL, BAW_USER, and BAW_PASSWORD or BAW_APIKEY. Values already in the environment
(e.g. the "env" block of .bob/mcp.json) win; .env in the repository root fills in the rest.
Tokens are kept in memory and never printed.

Examples:
    python3 baw_ops.py list
    python3 baw_ops.py export HSS RHSV180 hss.twx
    python3 baw_ops.py install clone.twx
    python3 baw_ops.py versions ZZHSS
    python3 baw_ops.py services ZZEQ         # exposed services of the tip snapshot, with run URLs
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ENV_FILE = Path(__file__).with_name(".env")
# Test clusters often use self-signed certificates.
SSL_CTX = ssl._create_unverified_context()


class ConfigError(Exception):
    pass


def load_env():
    """Environment first, then .env for anything not set. Fails when a setting is missing."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                if not os.environ.get(key.strip()):
                    os.environ[key.strip()] = value.strip().strip("\"'")
    missing = [k for k in ("BAW_URL", "BAW_USER") if not os.environ.get(k)]
    if not (os.environ.get("BAW_PASSWORD") or os.environ.get("BAW_APIKEY")):
        missing.append("BAW_PASSWORD or BAW_APIKEY")
    if missing:
        raise ConfigError(f"Missing BAW settings: {', '.join(missing)}. Set them in {ENV_FILE} or in the environment.")


class BawOps:
    def __init__(self):
        load_env()
        self.base = os.environ["BAW_URL"].rstrip("/")
        self.token = self._authorize()
        self.csrf = self._csrf()

    def _request(self, method, path, body=None, headers=None, raw=False, timeout=300):
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            data = resp.read()
            return (data, resp.headers) if raw else json.loads(data or b"{}")

    def _authorize(self):
        secret = {"password": os.environ["BAW_PASSWORD"]} if os.environ.get("BAW_PASSWORD") else {"api_key": os.environ["BAW_APIKEY"]}
        body = json.dumps({"username": os.environ["BAW_USER"], **secret}).encode()
        return self._request("POST", "/icp4d-api/v1/authorize", body, {"Content-Type": "application/json"})["token"]

    def _csrf(self):
        body = json.dumps({"requested_lifetime": 7200}).encode()
        return self._request("POST", "/bas/bpm/system/login", body, self._headers({"Content-Type": "application/json"}))["csrf_token"]

    def _headers(self, extra=None):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if getattr(self, "csrf", None):
            headers["BPMCSRFToken"] = self.csrf
        headers.update(extra or {})
        return headers

    def get(self, path, accept="application/json", **kw):
        return self._request("GET", path, headers=self._headers({"Accept": accept}), **kw)

    def list_containers(self):
        return self.get("/bas/ops/std/bpm/containers")

    def versions(self, container):
        return self.get(f"/bas/ops/std/bpm/containers/{container}/versions")

    def export(self, container, version, dest: Path):
        data, _ = self.get(f"/bas/ops/std/bpm/containers/{container}/versions/{version}/export", accept="application/octet-stream", raw=True)
        dest.write_bytes(data)
        return len(data)

    def services(self, acronym, snapshot=None):
        """Exposed services of an app: the tip snapshot unless a snapshot name is given."""
        items = self.get("/bas/rest/bpm/wle/v1/exposed/service")["data"]["exposedItemsList"]
        mine = [i for i in items if i.get("processAppAcronym") == acronym]
        return [i for i in mine if (i.get("snapshotName") == snapshot if snapshot else i.get("tip"))]

    def install(self, twx: Path, poll_seconds=5, max_wait=900):
        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"install_file\"; filename=\"{twx.name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + twx.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        result = self._request(
            "POST", "/bas/ops/std/bpm/containers/install", body,
            self._headers({"Content-Type": f"multipart/form-data; boundary={boundary}"}),
        )
        url = result.get("url", "")
        if not url:
            return result
        queue_path = "/bas" + url[url.index("/ops/"):] if "/ops/" in url else url
        deadline = time.time() + max_wait
        while time.time() < deadline:
            status = self.get(queue_path)
            if str(status.get("state", status.get("status", ""))).lower() not in ("running", "pending", "queued", "in_progress", "inprogress"):
                return status
            time.sleep(poll_seconds)
        return {"status": "timeout", "queue": queue_path}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("versions"); p.add_argument("container")
    p = sub.add_parser("export"); p.add_argument("container"); p.add_argument("version"); p.add_argument("dest", type=Path)
    p = sub.add_parser("install"); p.add_argument("twx", type=Path)
    p = sub.add_parser("services"); p.add_argument("container"); p.add_argument("--snapshot")
    args = parser.parse_args()

    try:
        ops = BawOps()
    except ConfigError as e:
        sys.exit(str(e))
    if args.cmd == "list":
        for c in ops.list_containers().get("containers", []):
            print(f"{c.get('container', ''):10} {'toolkit' if c.get('toolkit') else 'app':8} {c.get('container_name', '')}")
    elif args.cmd == "versions":
        print(json.dumps(ops.versions(args.container), indent=2))
    elif args.cmd == "export":
        print(f"Exported {ops.export(args.container, args.version, args.dest)} bytes to {args.dest}")
    elif args.cmd == "services":
        for item in ops.services(args.container, args.snapshot):
            print(f"{item.get('display')}\t{item.get('runURL')}")
    elif args.cmd == "install":
        result = ops.install(args.twx)
        print(json.dumps(result, indent=2))
        state = str(result.get("state", result.get("status", ""))).lower()
        sys.exit(0 if state in ("success", "successful", "complete", "completed", "finished") else 1)


if __name__ == "__main__":
    main()
