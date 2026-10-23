#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.16"
# dependencies = ["psycopg[binary]>=3.3.6,<4"]
# ///
"""
PostgreSQL access for baw-dev-tools: Bob's limited login, one safe statement at a time, and catalog reads.

Settings (environment first, then .env):
  POSTGRES_HOST (default: the host of BAW_URL), POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD
      the admin login. It is used only to set up Bob's login and for approved system-database changes.
  POSTGRES_BOB_USER (default bob_mcp), POSTGRES_BOB_PASSWORD
      Bob's login, a plain role that PostgreSQL itself limits. The setup writes both to .env.
  POSTGRES_APP_DATABASE (default bawexternal), POSTGRES_APP_ROLE (default: that database's owner)
      the one database Bob writes to. Its sessions run as the app role, the role BAW's jdbc/bawexternal uses,
      so the tables Bob creates are the ones BAW apps see. Every other database is read-only for Bob.
The passwords stay in this process: never in os.environ, tool output, error messages or SQL text.

Examples:
    uv run --script server/pg_ops.py setup              # create or repair Bob's login (run again: no change)
    uv run --script server/pg_ops.py databases
    uv run --script server/pg_ops.py tables bawexternal
    uv run --script server/pg_ops.py describe bawexternal public.user_db
    uv run --script server/pg_ops.py sql basdb "select count(*) from lsw_bpd"
    uv run --script server/pg_ops.py export basdb "select * from lsw_bpd limit 10" work/bpd.csv
    uv run --script server/pg_ops.py import my_table work/rows.csv [--replace]   # CSV or JSON array, app database only
    uv run --script server/pg_ops.py backup basdb public.some_table --where "id < 10"
    uv run --script server/pg_ops.py restore basdb db-backups/basdb/public.some_table-261023-101500.csv
    uv run --script server/pg_ops.py remove-login       # drop Bob's login and its grants
"""

import argparse
import contextlib
import csv
import datetime
import json
import math
import os
import re
import secrets
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baw_ops import ENV_FILE, load_env_file  # noqa: E402

ROOT = ENV_FILE.parent
WORK = ROOT / "work"
BACKUPS = ROOT / "db-backups"  # outside work/: Bob's modes cannot edit it, and .bobignore hides it
FILE_TX = "-c transaction_timeout=150000"  # a whole export, import or backup, all statements together
ACL_BACKUPS = BACKUPS / "acl-before-bob-login"
EXPORT_MAX = 200 * 1024 * 1024
IMPORT_MAX = 100 * 1024 * 1024
FILE_TIMEOUT = 120
SAFE_FILE_NAME = re.compile(r"^[A-Za-z0-9_$][A-Za-z0-9_.$-]*\Z")
RESULT_BUDGET = 256 * 1024
APP_CEILING = 1024**3
LIMIT_MAX = 1000
NAME = re.compile(r"^[a-z_][a-z0-9_$]{0,62}\Z")
# Roles too strong to run Bob's app-database sessions as.
STRONG_ROLES = ("pg_read_server_files", "pg_write_server_files", "pg_execute_server_program", "pg_signal_backend")
APP_SCHEMAS = "n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname !~ '^pg_(toast|temp)'"
READABLE_KINDS = "('r', 'p', 'v', 'm', 'f')"

# Statement types refused on every database, by their leading words. The role layer is what actually stops
# harm (Bob's login has no superuser powers); this is a second line that gives Bob a clear message.
REFUSED = {
    ("BEGIN",): "transaction control", ("START",): "transaction control", ("COMMIT",): "transaction control",
    ("END",): "transaction control", ("ROLLBACK",): "transaction control", ("ABORT",): "transaction control",
    ("SAVEPOINT",): "transaction control", ("RELEASE",): "transaction control",
    ("PREPARE", "TRANSACTION"): "transaction control",
    ("SET",): "session settings", ("RESET",): "session settings",
    ("COPY",): "COPY (use export_table or import_table)",
    ("DO",): "code blocks", ("CALL",): "procedure calls",
    ("GRANT",): "privileges", ("REVOKE",): "privileges", ("ALTER", "DEFAULT"): "privileges",
    ("REASSIGN",): "ownership changes", ("DROP", "OWNED"): "dropping everything a role owns",
    ("ALTER", "SYSTEM"): "server settings", ("CREATE", "EXTENSION"): "extensions", ("ALTER", "EXTENSION"): "extensions",
    ("LOAD",): "server commands", ("CHECKPOINT",): "server commands", ("VACUUM",): "server commands",
    ("CLUSTER",): "server commands", ("REINDEX",): "server commands", ("LISTEN",): "server commands",
    ("NOTIFY",): "server commands", ("UNLISTEN",): "server commands",
}
# In the app database Bob's session runs as the same role as BAW's pooled connections, which PostgreSQL lets it
# signal. Matched on the raw text, so the names are also caught inside strings handed to a function that runs them.
SIGNALS = re.compile(r"pg_(?:terminate|cancel)_backend", re.IGNORECASE)
RUNS_TEXT = re.compile(r"\b(?:query_to_xml\w*|cursor_to_xml\w*|table_to_xml\w*|schema_to_xml\w*|database_to_xml\w*|ts_stat)\b|U&['\"]",
                       re.IGNORECASE)
CODE_OBJECTS = {"FUNCTION", "PROCEDURE", "TRIGGER", "EVENT", "RULE", "AGGREGATE", "OPERATOR", "CAST", "LANGUAGE",
                "ROUTINE", "CONSTRAINT"}  # CONSTRAINT: CREATE CONSTRAINT TRIGGER
ROLE_OBJECTS = {"ROLE", "USER", "GROUP", "DATABASE"}

MANAGED = "managed by baw-dev-tools"
_lock = threading.Lock()
_ready = {}  # set by ensure_login: {"app_role": ...}


class PgError(Exception):
    pass


# ---------------------------------------------------------------- settings


def settings() -> dict:
    env = load_env_file()

    def get(key, default=None):
        return os.environ.get(key) or env.get(key) or default

    return {"host": get("POSTGRES_HOST") or urlparse(get("BAW_URL", "")).hostname,
            "port": get("POSTGRES_PORT"), "user": get("POSTGRES_USER"), "password": get("POSTGRES_PASSWORD"),
            "bob_user": get("POSTGRES_BOB_USER", "bob_mcp"), "bob_password": get("POSTGRES_BOB_PASSWORD"),
            "app_database": get("POSTGRES_APP_DATABASE", "bawexternal"), "app_role": get("POSTGRES_APP_ROLE")}


def pg_missing_settings() -> list[str]:
    s = settings()
    return [f"POSTGRES_{k.upper()}" for k in ("host", "port", "user", "password") if not s[k]]


def configured() -> bool:
    return not pg_missing_settings()


def scrub(text: str) -> str:
    s = settings()
    for secret in (s["password"], s["bob_password"]):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def _psycopg():
    try:
        import psycopg
    except ImportError as e:
        raise PgError(f"psycopg is not installed ({e}); start the server with uv so it installs psycopg[binary]")
    if psycopg.pq.version() < 160000:  # require_auth needs libpq 16
        raise PgError(f"libpq {psycopg.pq.version()} is too old; it must be 16 or later")
    return psycopg


# ---------------------------------------------------------------- connections


def connect(database: str, admin: bool = False, timeout: int = 30, options: str = ""):
    """One connection, as Bob's login (or the admin login). Keyword arguments only: no connection string ever
    holds a password. In the app database the session starts as the app role, by startup option. `options` adds
    startup options such as "-c transaction_timeout=180000"."""
    psycopg = _psycopg()
    missing = pg_missing_settings()
    if missing:
        raise PgError(f"PostgreSQL is not configured (missing {', '.join(missing)}). Set them in .env; "
                      "see the PostgreSQL card on the CP4BA access portal")
    if not admin:
        ensure_login()
    s = settings()
    user, password = (s["user"], s["password"]) if admin else (s["bob_user"], s["bob_password"])
    options = f"-c statement_timeout={timeout * 1000} -c lock_timeout=5000 -c work_mem=16MB -c max_parallel_workers_per_gather=0 {options}"
    if not admin and database == s["app_database"]:
        options += f" -c role={_ready['app_role']}"
    try:
        return psycopg.connect(host=s["host"], port=int(s["port"]), user=user, password=password, dbname=database,
                               connect_timeout=10, sslmode="prefer", require_auth="scram-sha-256",
                               keepalives=1, keepalives_idle=15, keepalives_interval=5, tcp_user_timeout=45000,
                               application_name="baw-dev-tools", options=options)
    except psycopg.Error as e:
        raise PgError(explain(e, database, connecting=user)) from None


@contextlib.contextmanager
def session(database: str, admin: bool = False, timeout: int = 30, options: str = ""):
    """A connection that is always rolled back and closed at the end. Bob's sessions on any database other
    than the app database are READ ONLY."""
    conn = connect(database, admin=admin, timeout=timeout, options=options)
    try:
        if not admin and database != settings()["app_database"]:
            conn.read_only = True
        yield conn
    except _psycopg().Error as e:
        raise PgError(explain(e, database)) from None
    finally:
        with contextlib.suppress(Exception):
            conn.rollback()
        conn.close()


# ---------------------------------------------------------------- Bob's limited login


def ensure_login(force: bool = False) -> list[str]:
    """Create or repair Bob's login with the admin login. Idempotent: returns what it changed (empty when
    everything was already in place). Runs once per process; `setup` runs it again with force."""
    with _lock:
        if _ready and not force:
            return []
        s = settings()
        bob, app_db = s["bob_user"], s["app_database"]
        for name in (bob, app_db, s["app_role"] or "x"):
            if not NAME.match(name):
                raise PgError(f"{name!r} is not a plain lower-case PostgreSQL name")
        _psycopg()  # fails closed on a missing driver or an old libpq
        from psycopg import sql
        changes = []
        with session("postgres", admin=True) as conn:
            conn.autocommit = True
            app_role = s["app_role"] or one(conn, "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", [app_db])
            if not app_role:
                raise PgError(f"There is no database {app_db} (POSTGRES_APP_DATABASE)")
            check_app_role(conn, app_role)
            if bob in (s["user"], app_role):
                raise PgError(f"POSTGRES_BOB_USER ({bob}) must differ from the admin login and from the app role")
            existed = one(conn, "SELECT count(*) FROM pg_roles WHERE rolname = %s", [bob])
            marker = one(conn, "SELECT shobj_description(oid, 'pg_authid') FROM pg_roles WHERE rolname = %s", [bob])
            if existed and marker != MANAGED:
                raise PgError(f"A role {bob} already exists and was not created by baw-dev-tools, so the setup leaves it "
                              f"alone. Set POSTGRES_BOB_USER to a new name, or mark it with COMMENT ON ROLE {bob} IS '{MANAGED}'")
            if not existed:
                backup_acls(conn)
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(bob)))
                conn.execute(sql.SQL("COMMENT ON ROLE {} IS {}").format(sql.Identifier(bob), sql.Literal(MANAGED)))
                changes.append(f"created login {bob}")
            attrs = conn.execute("SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, "
                                 "rolconnlimit, coalesce(rolconfig, '{}') FROM pg_roles WHERE rolname = %s", [bob]).fetchone()
            if attrs[:7] != (True, False, False, False, False, False, 5):
                conn.execute(sql.SQL("ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS "
                                     "CONNECTION LIMIT 5").format(sql.Identifier(bob)))
                changes.append(f"reset the attributes of {bob}")
            for setting, value in (("temp_file_limit", "1GB"), ("idle_in_transaction_session_timeout", "60s")):
                if f"{setting}={value}" not in attrs[7]:
                    conn.execute(sql.SQL("ALTER ROLE {} SET {} = {}").format(sql.Identifier(bob), sql.Identifier(setting),
                                                                             sql.Literal(value)))
                    changes.append(f"set {setting} = {value} on {bob}")
            if not one(conn, "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid "
                             "JOIN pg_roles b ON b.oid = m.member WHERE r.rolname = %s AND b.rolname = %s "
                             "AND NOT m.inherit_option AND m.set_option", [app_role, bob]):
                conn.execute(sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(sql.Identifier(app_role),
                                                                                          sql.Identifier(bob)))
                changes.append(f"let {bob} work as {app_role}")
            databases = [r[0] for r in conn.execute("SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate "
                                                    "ORDER BY datname")]
            for db in databases:
                if not one(conn, "SELECT has_database_privilege(%s, %s, 'CONNECT')", [bob, db]):
                    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), sql.Identifier(bob)))
                    changes.append(f"CONNECT on {db}")
            if not s["bob_password"] or not login_works(s):
                changes.append(set_password(conn, bob))
        for db in databases:
            if db != app_db:
                changes += grant_reads(db, bob)
        _ready["app_role"] = app_role
        return changes


def one(conn, query, params=()):
    row = conn.execute(query, params).fetchone()
    return row[0] if row else None


def check_app_role(conn, role: str):
    """Refuse an app role with powers beyond its own tables: Bob's sessions run as it."""
    row = conn.execute("SELECT rolsuper, rolcreaterole, rolbypassrls, rolreplication FROM pg_roles WHERE rolname = %s",
                       [role]).fetchone()
    if not row:
        raise PgError(f"There is no role {role} (POSTGRES_APP_ROLE)")
    powers = [p for p, on in zip(("SUPERUSER", "CREATEROLE", "BYPASSRLS", "REPLICATION"), row, strict=True) if on]
    powers += [r for r in STRONG_ROLES if one(conn, "SELECT pg_has_role(%s, %s, 'MEMBER')", [role, r])]
    if powers:
        raise PgError(f"The app role {role} has {', '.join(powers)}. Bob's app-database sessions run as that role, so the "
                      "tools stop here. Ask the user which role BAW's data source should use (POSTGRES_APP_ROLE)")


def login_works(s: dict) -> bool:
    psycopg = _psycopg()
    try:
        psycopg.connect(host=s["host"], port=int(s["port"]), user=s["bob_user"], password=s["bob_password"],
                        dbname="postgres", connect_timeout=10, require_auth="scram-sha-256").close()
        return True
    except psycopg.OperationalError as e:
        if getattr(e, "sqlstate", None) in ("28P01", "28000") or "password authentication failed" in str(e):
            if os.environ.get("POSTGRES_BOB_PASSWORD"):
                raise PgError("POSTGRES_BOB_PASSWORD from the environment (for example the env block of .bob/mcp.json) "
                              "does not work. Remove it there; the setup keeps Bob's password in .env") from None
            return False
        raise PgError(explain(e, "postgres", connecting=s["bob_user"])) from None


def set_password(conn, bob: str) -> str:
    """A new random password: written to .env first, then sent to PostgreSQL only as a SCRAM verifier."""
    from psycopg import sql
    password = secrets.token_urlsafe(32)
    write_env({"POSTGRES_BOB_USER": bob, "POSTGRES_BOB_PASSWORD": password})
    verifier = conn.pgconn.encrypt_password(password.encode(), bob.encode(), b"scram-sha-256").decode()
    conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(bob), sql.Literal(verifier)))
    return f"set a new password for {bob} (in .env)"


def write_env(values: dict):
    """Replace or add KEY=value lines in .env, atomically, readable only by its owner."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if line.split("=", 1)[0].strip() not in values]
    lines += [f"{k}={v}" for k, v in values.items() if v is not None]
    tmp = ENV_FILE.with_name(".env.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV_FILE)


def grant_reads(db: str, bob: str) -> list[str]:
    """Read access to one system database's application schemas: USAGE, SELECT on every table and view, and
    default privileges so tables created later by the same owners stay readable. Only missing grants are made."""
    from psycopg import sql
    changes = []
    with session(db, admin=True) as conn:
        conn.autocommit = True
        bob_oid = one(conn, "SELECT oid FROM pg_roles WHERE rolname = %s", [bob])
        rows = conn.execute(f"""
            SELECT n.nspname, has_schema_privilege(%(bob)s, n.oid, 'USAGE'),
                   EXISTS (SELECT 1 FROM pg_class c WHERE c.relnamespace = n.oid AND c.relkind IN {READABLE_KINDS}
                           AND NOT has_table_privilege(%(bob)s, c.oid, 'SELECT')),
                   ARRAY(SELECT DISTINCT pg_get_userbyid(c.relowner) FROM pg_class c
                         WHERE c.relnamespace = n.oid AND c.relkind IN {READABLE_KINDS}
                         AND NOT EXISTS (SELECT 1 FROM pg_default_acl d, aclexplode(d.defaclacl) a
                                         WHERE d.defaclrole = c.relowner AND d.defaclnamespace = n.oid
                                         AND d.defaclobjtype = 'r' AND a.grantee = %(oid)s AND a.privilege_type = 'SELECT'))
            FROM pg_namespace n WHERE {APP_SCHEMAS} ORDER BY 1""", {"bob": bob, "oid": bob_oid}).fetchall()
        for schema, usage, missing, owners in rows:
            s, b = sql.Identifier(schema), sql.Identifier(bob)
            if not usage:
                conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(s, b))
            if missing:
                conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(s, b))
            for owner in (o for o in owners if o != settings()["user"]):
                conn.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} GRANT SELECT ON TABLES TO {}")
                             .format(sql.Identifier(owner), s, b))
            if not usage or missing or owners:
                changes.append(f"read access to {db}.{schema}")
        # Unqualified names resolve the way they do for the platform's own logins.
        names = list(dict.fromkeys([r[0] for r in rows] + ["public"]))
        path = ", ".join(sql.Identifier(n).as_string(conn) for n in names)
        current = one(conn, "SELECT setconfig FROM pg_db_role_setting WHERE setrole = %s "
                            "AND setdatabase = (SELECT oid FROM pg_database WHERE datname = current_database())", [bob_oid])
        stored = next((c.split("=", 1)[1] for c in current or [] if c.startswith("search_path=")), "")
        if [n.strip().strip('"') for n in stored.split(",")] != names:
            conn.execute(sql.SQL("ALTER ROLE {} IN DATABASE {} SET search_path = " + path.replace("{", "{{").replace("}", "}}"))
                         .format(sql.Identifier(bob), sql.Identifier(db)))
            changes.append(f"search_path in {db}: {path}")
    return changes


def backup_acls(conn):
    """Before the first setup: save every database's and schema's privileges and the table privileges that the
    setup changes, so they can be compared or restored by hand. Removal (remove-login) undoes the setup itself."""
    ACL_BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dbs = conn.execute("SELECT datname, datacl::text FROM pg_database WHERE datallowconn AND NOT datistemplate").fetchall()
    for db, datacl in dbs:
        with session(db, admin=True) as c:
            data = {"database": db, "datacl": datacl,
                    "schemas": c.execute(f"SELECT n.nspname, n.nspacl::text FROM pg_namespace n WHERE {APP_SCHEMAS}").fetchall(),
                    "tables": c.execute(f"SELECT n.nspname || '.' || c.relname, c.relacl::text FROM pg_class c "
                                        f"JOIN pg_namespace n ON n.oid = c.relnamespace WHERE {APP_SCHEMAS} "
                                        f"AND c.relkind IN {READABLE_KINDS}").fetchall(),
                    "default_acls": c.execute("SELECT pg_get_userbyid(defaclrole), defaclnamespace::regnamespace::text, "
                                              "defaclobjtype, defaclacl::text FROM pg_default_acl").fetchall()}
        path = ACL_BACKUPS / f"{stamp}-{db}.json"
        path.write_text(json.dumps(data, indent=1))
        os.chmod(path, 0o600)


def remove_login() -> list[str]:
    """Undo the setup: drop every grant to Bob's login, the login itself, and its lines in .env."""
    from psycopg import sql
    s = settings()
    bob = s["bob_user"]
    if not NAME.match(bob):
        raise PgError(f"{bob!r} is not a plain lower-case PostgreSQL name")
    done = []
    with session("postgres", admin=True) as conn:
        conn.autocommit = True
        if one(conn, "SELECT count(*) FROM pg_roles WHERE rolname = %s", [bob]):
            dbs = [r[0] for r in conn.execute("SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate")]
            for db in dbs:
                with session(db, admin=True) as c:
                    c.autocommit = True
                    c.execute(sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(sql.Identifier(bob)))
                    c.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(bob)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(bob)))
            done.append(f"dropped {bob} and its grants in {len(dbs)} databases")
    write_env({"POSTGRES_BOB_USER": None, "POSTGRES_BOB_PASSWORD": None})
    _ready.clear()
    return done + ["removed POSTGRES_BOB_* from .env"]


# ---------------------------------------------------------------- statement checks


TOKEN = re.compile(r"""
    (?P<space>\s+)
  | (?P<line>--[^\n]*)
  | (?P<dollar>\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$)
  | (?P<escaped>[Ee]'(?:[^'\\]|\\.|'')*')
  | (?P<string>(?:[BbXxNn]|[Uu]&)?'(?:[^']|'')*')
  | (?P<quoted>(?:[Uu]&)?"(?:[^"]|"")*")
  | (?P<word>[A-Za-z_\x80-\U0010ffff][A-Za-z0-9_$\x80-\U0010ffff]*)
  | (?P<other>.)
""", re.X | re.S)


def tokens(sql: str):
    """The words and symbols of a statement, skipping whitespace, comments (nested too), string literals,
    quoted identifiers and dollar-quoted bodies. Words come back upper-case; anything else as "?"."""
    i = 0
    while i < len(sql):
        if sql.startswith("/*", i):
            depth, i = 1, i + 2
            while i < len(sql) and depth:
                if sql.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif sql.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            continue
        m = TOKEN.match(sql, i)
        kind = m.lastgroup
        if kind == "dollar":
            end = sql.find(m.group(), m.end())
            i = len(sql) if end < 0 else end + len(m.group())
            yield "?"
            continue
        i = m.end()
        if kind == "word":
            yield m.group().upper()
        elif kind == "other":
            yield m.group()
        elif kind != "space" and kind != "line":
            yield "?"


def schema_elements(sql: str) -> str | None:
    """CREATE SCHEMA may carry GRANT, CREATE TRIGGER and other statements inside it, past the leading-word checks."""
    toks = list(tokens(sql))
    if toks[:2] == ["CREATE", "SCHEMA"] and any(t in ("CREATE", "GRANT", "REVOKE", "TRIGGER", "TABLE", "VIEW", "INDEX",
                                                       "SEQUENCE") for t in toks[2:]):
        return "CREATE SCHEMA with statements inside it (create the schema, then each object on its own)"
    return None


def leading_words(sql: str, count: int = 4) -> tuple[str, ...]:
    """The first words of a statement, after any opening parentheses."""
    words = []
    for t in tokens(sql):
        if t == "(" and not words:
            continue
        words.append(t)
        if len(words) == count:
            break
    return tuple(words)


def refusal(words: tuple, app: bool) -> str | None:
    """Why a statement is refused, or None."""
    if not words:
        return "an empty statement"
    for n in (2, 1):
        if words[:n] in REFUSED:
            return REFUSED[words[:n]]
    rest = words[1:]
    if words[0] in ("CREATE", "ALTER", "DROP"):
        if rest[:2] == ("OR", "REPLACE"):
            rest = rest[2:]
        if rest and rest[0] in ("CONSTRAINT", "EVENT"):
            rest = ("TRIGGER",)
        if rest and rest[0] in CODE_OBJECTS and words[0] != "DROP":
            return f"{rest[0].lower()}s (code that runs inside the database)"
        if rest and rest[0] in ROLE_OBJECTS:
            return "roles and databases"
        if not app and words[0] == "CREATE":
            return "creating objects outside the app database"
    return None


# ---------------------------------------------------------------- execution


def jsonable(value):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, str):
        return value if len(value) <= 2000 else value[:2000] + f"... [cut: {len(value)} characters]"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<{len(value)} bytes>"
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    return str(value)  # Decimal, timedelta, UUID, ranges, IP addresses


def app_size(conn) -> int:
    return one(conn, "SELECT pg_database_size(current_database())")


def describe_one(conn, sql: str) -> list[str]:
    """Parse one statement without running it and return its column names. A second statement or a syntax
    error raises a psycopg error. Call it before psycopg opens a transaction."""
    psycopg = _psycopg()
    from psycopg import pq
    encoding = conn.info.encoding
    for step in (lambda: conn.pgconn.prepare(b"", sql.encode(encoding)), lambda: conn.pgconn.describe_prepared(b"")):
        described = step()
        if described.status != pq.ExecStatus.COMMAND_OK:
            raise psycopg.errors.error_from_result(described, encoding=encoding)
    return [described.fname(i).decode(encoding) for i in range(described.nfields)]


def execute(database: str, sql: str, limit: int = 200) -> dict:
    """Run exactly one statement as Bob. Read-only (and always rolled back) on every database except the app
    database, where a complete statement is committed."""
    psycopg = _psycopg()
    from psycopg import pq
    if not 1 <= limit <= LIMIT_MAX:
        raise PgError(f"limit must be between 1 and {LIMIT_MAX}")
    app = database == settings()["app_database"]
    words = leading_words(sql)
    why = refusal(words, app) or (SIGNALS.search(sql) and "signalling other sessions") \
        or (RUNS_TEXT.search(sql) and "functions that run SQL given as text") or schema_elements(sql)
    if why:
        raise PgError(f"Refused: {why} cannot run through run_sql" + ("" if app else f" on {database}") + ".")
    with session(database) as conn:
        try:
            # Parse and describe only, before psycopg opens the transaction. A second statement fails here.
            columns = describe_one(conn, sql)
            if not app and not columns and words[0] in ("SELECT", "WITH", "TABLE", "VALUES", "EXPLAIN"):
                raise PgError(f"Refused: SELECT ... INTO creates a table, and {database} is read-only for Bob.")
            if app and app_size(conn) > APP_CEILING and not (columns and words[0] in ("SELECT", "WITH", "TABLE", "VALUES")) \
                    and words[0] not in ("DELETE", "TRUNCATE", "DROP"):
                raise PgError(f"{database} is over its {APP_CEILING >> 30} GB ceiling: only reads, DELETE, TRUNCATE and DROP "
                              "TABLE run until it shrinks. Only TRUNCATE or DROP TABLE frees space at once.")
            cur = conn.cursor()
            rows, used, truncated = [], 0, None
            if columns:
                with contextlib.closing(cur.stream(sql)) as stream:
                    for row in stream:
                        if len(rows) == limit:
                            truncated = f"more than {limit} rows"
                            break
                        item = [jsonable(v) for v in row]
                        used += len(json.dumps(item, default=str))
                        if used > RESULT_BUDGET:
                            truncated = f"over {RESULT_BUDGET >> 10} KB"
                            break
                        rows.append(item)
                status = f"SELECT {len(rows)}"
            else:
                cur.execute(sql, prepare=True)
                status = cur.statusmessage
            if conn.info.transaction_status not in (pq.TransactionStatus.INTRANS, pq.TransactionStatus.INERROR):
                raise PgError("Refused: the statement ended the transaction.")
        except psycopg.Error as e:
            raise PgError(explain(e, database)) from None
        result = {"database": database, "columns": columns, "rows": rows, "row_count": len(rows),
                  "truncated": bool(truncated), "truncated_reason": truncated, "status": status, "committed": False}
        if not app:
            return result
        if truncated:
            result["note"] = (f"Result cut at {len(rows)} rows; nothing was committed. "
                              "For a write, drop RETURNING or add a LIMIT.")
            return result
        try:
            if app_size(conn) > APP_CEILING:
                raise PgError(f"Rolled back: this statement took {database} over its {APP_CEILING >> 30} GB ceiling.")
        except psycopg.Error as e:
            raise PgError(explain(e, database)) from None
        try:
            conn.commit()
            result["committed"] = True
        except psycopg.Error as e:
            result["committed"] = "unknown"
            result["note"] = scrub(f"The commit failed ({first_line(e)}); it may or may not have been applied. "
                                   "Check the data before running the statement again.")
        return result


# ---------------------------------------------------------------- catalog reads


def databases() -> list[dict]:
    app_db = settings()["app_database"]
    with session("postgres") as conn:
        rows = conn.execute("SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database "
                            "WHERE datallowconn AND NOT datistemplate AND has_database_privilege(datname, 'CONNECT') "
                            "ORDER BY pg_database_size(datname) DESC").fetchall()
    return [{"database": name, "size": size, "writable": name == app_db} for name, size in rows]


def tables(database: str) -> dict:
    app_db = settings()["app_database"]
    with session(database) as conn:
        rows = conn.execute(f"""
            SELECT n.nspname, c.relname,
                   CASE c.relkind WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized view' WHEN 'f' THEN 'foreign table'
                                  ELSE 'table' END,
                   CASE WHEN c.reltuples < 0 THEN NULL ELSE c.reltuples::bigint END
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN {READABLE_KINDS} AND {APP_SCHEMAS} AND has_table_privilege(c.oid, 'SELECT')
            ORDER BY 1, 2""").fetchall()
        schemas = {}
        for schema, name, kind, count in rows:
            schemas.setdefault(schema, []).append({"name": name, "kind": kind, "approx_rows": count})
        result = {"database": database, "writable": database == app_db,
                  "schemas": [{"schema": s, "tables": t} for s, t in schemas.items()]}
        if database == app_db:
            result.update(size=one(conn, "SELECT pg_size_pretty(pg_database_size(current_database()))"),
                          ceiling=f"{APP_CEILING >> 30} GB", runs_as=one(conn, "SELECT current_user"))
    return result


def describe(database: str, table: str) -> dict:
    with session(database) as conn:
        oid = one(conn, "SELECT to_regclass(%s)::oid", [table])
        if oid is None or not one(conn, "SELECT has_table_privilege(%s, 'SELECT')", [oid]):
            like = conn.execute(f"""
                SELECT n.nspname || '.' || c.relname FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN {READABLE_KINDS} AND {APP_SCHEMAS} AND c.relname ILIKE %s
                AND has_table_privilege(c.oid, 'SELECT') ORDER BY 1 LIMIT 20""", [f"%{table.split('.')[-1].strip(chr(34))}%"]).fetchall()
            raise PgError(f"No readable table {table!r} in {database}" +
                          (f"; did you mean: {', '.join(r[0] for r in like)}" if like else "; list_tables shows what there is"))
        name = one(conn, "SELECT %s::regclass::text", [oid])
        columns = [{"name": n, "type": t, "nullable": nullable, "default": default,
                    **({"large": True} if large else {})}
                   for n, t, nullable, default, large in conn.execute("""
            SELECT a.attname, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull, pg_get_expr(d.adbin, d.adrelid),
                   ty.typname IN ('bytea', 'text', 'json', 'jsonb', 'xml') AND coalesce(s.avg_width, 2049) > 2048
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_type ty ON ty.oid = a.atttypid
            LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            LEFT JOIN pg_catalog.pg_stats s ON s.schemaname = n.nspname AND s.tablename = c.relname AND s.attname = a.attname
            WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum""", [oid])]
        constraints = conn.execute("SELECT contype, conname, pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint "
                                   "WHERE conrelid = %s AND contype IN ('p', 'f', 'u') ORDER BY contype, conname", [oid]).fetchall()
        indexes = conn.execute("SELECT pg_get_indexdef(indexrelid) FROM pg_catalog.pg_index WHERE indrelid = %s ORDER BY 1",
                               [oid]).fetchall()
    return {"database": database, "table": name, "columns": columns,
            "primary_key": next((d for t, _, d in constraints if t == "p"), None),
            "unique": [d for t, _, d in constraints if t == "u"],
            "foreign_keys": [{"name": n, "definition": d} for t, n, d in constraints if t == "f"],
            "indexes": [r[0] for r in indexes]}


# ---------------------------------------------------------------- files and paths


def inside(path: Path, folder: Path) -> bool:
    """True when path is the folder or below it, even if the letter case differs on a case-insensitive disk."""
    folder = folder.resolve()
    if Path(str(path).casefold()).is_relative_to(Path(str(folder).casefold())):
        return True
    return any(folder.exists() and p.exists() and os.path.samefile(p, folder) for p in (path, *path.parents))


def work_path(file: str, for_export: bool = False) -> Path:
    """A path relative to the project that must stay under work/ once resolved. Exports may not land in the
    backup folder."""
    if not file or Path(file).is_absolute():
        raise PgError(f"{file!r} must be a path relative to the project, under work/")
    path = (ROOT / file).resolve()
    if not path.is_relative_to(WORK.resolve()) or path == WORK.resolve():
        raise PgError(f"{file!r} must be a file under work/")
    if for_export and inside(path, BACKUPS):
        raise PgError("Exports may not write into db-backups/; that folder holds backups only")
    return path


def rel(path: Path) -> str:
    return os.path.relpath(path, ROOT)


def new_file(path: Path, exclusive: bool = True):
    """Open a file for writing, readable only by its owner, never through a symbolic link."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_EXCL if exclusive else os.O_TRUNC)
    return os.fdopen(os.open(path, flags, 0o600), "wb")


def qualified(conn, table: str, kinds: str = "('r', 'p')") -> tuple[int, str, str]:
    """The oid, schema and name of an existing table, as PostgreSQL resolves the given name."""
    oid = one(conn, "SELECT to_regclass(%s)::oid", [table])
    if oid is None:
        raise PgError(f"There is no table {table!r}; list_tables shows what there is")
    row = conn.execute(f"SELECT n.nspname, c.relname FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                       f"ON n.oid = c.relnamespace WHERE c.oid = %s AND c.relkind IN {kinds}", [oid]).fetchone()
    if not row:
        raise PgError(f"{table!r} is not a table")
    return oid, row[0], row[1]


def copy_out(conn, select: str, dest: Path, exclusive: bool) -> tuple[int, int]:
    """Stream `COPY (select) TO STDOUT` as CSV with a header into a file, through a partial file that is removed on
    any error or at the size cap. With exclusive, an existing file is never replaced. Returns (rows, bytes).
    `select` must already be known to be one statement."""
    partial = dest.with_name(dest.name + ".partial")
    size = 0
    try:
        with new_file(partial, exclusive=False) as out, conn.cursor() as cur:
            with cur.copy(f"COPY (\n{select}\n) TO STDOUT WITH (FORMAT csv, HEADER)") as copy:
                for data in copy:
                    size += len(data)
                    if size > EXPORT_MAX:
                        raise PgError(f"The output is over {EXPORT_MAX >> 20} MB; narrow it down (a where condition, "
                                      "or fewer columns) and try again")
                    out.write(data)
            rows = cur.rowcount
        if exclusive:
            os.link(partial, dest)  # fails if the file appeared meanwhile
            os.unlink(partial)
        else:
            os.replace(partial, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            partial.unlink()
        raise
    return rows, size


# ---------------------------------------------------------------- export


def export_csv(database: str, source: str, dest: str, overwrite: bool = False) -> dict:
    """Write a table, or the result of one SELECT, to a CSV file with a header, as Bob and read-only. `dest` is
    relative to the project and must be under work/. An existing file is replaced only with overwrite=True.
    At most 200 MB; the partial file is removed if the export fails or reaches the cap."""
    psycopg = _psycopg()
    out = work_path(dest, for_export=True)
    if out.is_dir():
        raise PgError(f"{dest!r} is a folder; give a file name")
    if out.exists() and not overwrite:
        raise PgError(f"{dest!r} already exists; choose another name or pass overwrite")
    words = leading_words(source)
    is_select = bool(words) and words[0] in ("SELECT", "WITH", "TABLE", "VALUES")
    with session(database, timeout=FILE_TIMEOUT, options=FILE_TX) as conn:
        conn.read_only = True
        try:
            if is_select:
                describe_one(conn, source)  # one statement, or an error
                select = source.strip().rstrip(";")
            else:
                from psycopg import sql as pgsql
                _, schema, name = qualified(conn, source, READABLE_KINDS)
                select = pgsql.SQL("SELECT * FROM {}").format(pgsql.Identifier(schema, name)).as_string(conn)
            out.parent.mkdir(parents=True, exist_ok=True)
            rows, size = copy_out(conn, select, out, exclusive=not overwrite)
        except psycopg.Error as e:
            raise PgError(explain(e, database)) from None
        except FileExistsError:
            raise PgError(f"{dest!r} already exists; choose another name or pass overwrite") from None
    return {"database": database, "file": rel(out), "rows": rows, "bytes": size}


# ---------------------------------------------------------------- import


def csv_text(value) -> str:
    """One JSON value as a CSV cell: null is empty and unquoted, every string is quoted (so "" stays an empty
    string), numbers and booleans stay bare, objects and arrays become JSON text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return '"' + value.replace('"', '""') + '"'


def json_as_csv(rows: list, header: list[str]):
    yield (",".join(csv_text(c) for c in header) + "\n").encode()
    for start in range(0, len(rows), 1000):
        yield ("\n".join(",".join(csv_text(r.get(c)) for c in header) for r in rows[start:start + 1000]) + "\n").encode()


def file_chunks(path: Path):
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            yield chunk


def read_source(path: Path) -> tuple[list[str], object]:
    """The column names of an import file, and an iterator of the bytes to load as CSV."""
    try:
        path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise PgError(f"{rel(path)} must be UTF-8 text ({e.reason} at byte {e.start})") from None
    if path.suffix.lower() == ".json":
        try:
            rows = json.loads(path.read_bytes().decode("utf-8-sig"), parse_float=str, parse_constant=str)
        except ValueError as e:
            raise PgError(f"{rel(path)} is not valid JSON: {e}") from None
        if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
            raise PgError(f"{rel(path)} must be a JSON array of objects, with at least one object")
        header = list(dict.fromkeys(k for r in rows for k in r))
        return header, json_as_csv(rows, header)
    with open(path, newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f), None)
    if not header or not all(header):
        raise PgError(f"{rel(path)} needs a first line with the column names")
    return header, file_chunks(path)


def import_file(table: str, src: str, mode: str = "append") -> dict:
    """Load a CSV file (a header line, then rows) or a .json file (an array of objects) into an existing table of
    the app database, as Bob, in one transaction. The columns come from the header or the JSON keys and must exist
    in the table. mode="append" adds the rows. mode="replace" backs the table up first, then empties it and loads the
    file; the table is locked for the whole load, so apps using it wait. JSON values go in as text and PostgreSQL
    converts them. At most 100 MB; a file that fails to load leaves the table as it was."""
    psycopg = _psycopg()
    from psycopg import sql as pgsql
    if mode not in ("append", "replace"):
        raise PgError("mode must be append or replace")
    path = work_path(src)
    if not path.is_file():
        raise PgError(f"{src!r} is not a file")
    if path.stat().st_size > IMPORT_MAX:
        raise PgError(f"{src!r} is over {IMPORT_MAX >> 20} MB; split it")
    header, chunks = read_source(path)
    if len(set(header)) != len(header):
        raise PgError("The column names in the file repeat: " + ", ".join(sorted({c for c in header if header.count(c) > 1})))
    app_db = settings()["app_database"]
    result = {"database": app_db, "mode": mode, "file": rel(path)}
    with session(app_db, timeout=FILE_TIMEOUT, options=FILE_TX) as conn:
        try:
            oid, schema, name = qualified(conn, table)
            if schema == "information_schema" or schema.startswith("pg_"):
                raise PgError(f"{table!r} is a system table")
            result["table"] = f"{schema}.{name}"
            columns = [r[0] for r in conn.execute("SELECT attname FROM pg_catalog.pg_attribute WHERE attrelid = %s "
                                                  "AND attnum > 0 AND NOT attisdropped ORDER BY attnum", [oid])]
            unknown = [c for c in header if c not in columns]
            if unknown:
                raise PgError(f"The file has columns that {schema}.{name} does not: {', '.join(unknown)}. "
                              f"The table's columns: {', '.join(columns)}")
            if app_size(conn) > APP_CEILING:
                raise PgError(f"{app_db} is over its {APP_CEILING >> 30} GB ceiling: free space with run_sql "
                              "(TRUNCATE or DROP TABLE) before importing")
            into = pgsql.Identifier(schema, name)
            if mode == "replace":
                conn.execute(pgsql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(into))
                result["backup"] = backup(conn, app_db, [f"{schema}.{name}"])
                conn.execute(pgsql.SQL("TRUNCATE TABLE {}").format(into))
            query = pgsql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER)").format(
                into, pgsql.SQL(", ").join(pgsql.Identifier(c) for c in header))
            with conn.cursor() as cur:
                with cur.copy(query) as copy:
                    for chunk in chunks:
                        copy.write(chunk)
                result["rows"] = cur.rowcount
            if app_size(conn) > APP_CEILING:
                raise PgError(f"Rolled back: the import took {app_db} over its {APP_CEILING >> 30} GB ceiling.")
        except psycopg.Error as e:
            raise PgError(explain(e, app_db) + ". Nothing was imported.") from None
        try:
            conn.commit()
            result["committed"] = True
        except psycopg.Error as e:
            result["committed"] = "unknown"
            result["note"] = scrub(f"The commit failed ({first_line(e)}); the rows may or may not have been loaded. "
                                   "Check the table before importing again.")
    return result


# ---------------------------------------------------------------- backup


def check_where(where: str):
    """A row filter must stay a filter: balanced parentheses and none of the clauses that follow WHERE or
    combine statements (UNION and the like), so the backup SELECT cannot be turned into another query."""
    depth = 0
    for t in tokens(where):
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
            if depth < 0:
                break
        elif depth == 0 and t in ("UNION", "INTERSECT", "EXCEPT", "ORDER", "GROUP", "HAVING", "LIMIT", "OFFSET", "FETCH",
                                  "FOR", "WINDOW", "INTO", ";"):
            raise PgError(f"A where condition cannot contain {t}")
    if depth != 0:
        raise PgError("The parentheses in the where condition do not balance")


def backup(conn, database: str, tables: list) -> list[dict]:
    """Export tables (or rows of them) to db-backups/<database>/<schema>.<table>-<YYMMDD-HHMMSS>.csv, each
    with a .json sidecar (columns, primary key, other indexes and constraints), through the connection it is given,
    so a transaction that goes on to write sees the same snapshot. Each entry of `tables` is "schema.table" or
    {"table": "schema.table", "where": "<condition>"}. Raises when a backup fails or reaches 200 MB, and removes
    the files of this call; the caller must then not write. Files are never overwritten."""
    from psycopg import sql as pgsql
    if not SAFE_FILE_NAME.match(database):
        raise PgError(f"Cannot back up database {database!r}: its name is not usable in a file name")
    folder = BACKUPS / database
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
    done, written = [], []
    try:
        for entry in tables:
            table, where = (entry, None) if isinstance(entry, str) else \
                (entry.get("table"), entry.get("where")) if isinstance(entry, dict) else (None, None)
            if not isinstance(table, str) or not table:
                raise PgError('Each backup entry is "schema.table" or {"table": "schema.table", "where": "<condition>"}')
            oid, schema, name = qualified(conn, table)
            select = pgsql.SQL("SELECT * FROM {}").format(pgsql.Identifier(schema, name)).as_string(conn)
            if where:
                check_where(where)
                denied = denied_names(where)
                if denied:
                    raise PgError(f"A where condition cannot name {denied}")
                select += f" WHERE {where}"
                describe_one(conn, select)  # one SELECT, or an error
            base = re.sub(r"[^A-Za-z0-9_.$-]", "_", f"{schema}.{name}")
            csv_path = None
            for n in range(1, 100):
                candidate = folder / f"{base}-{stamp}{'' if n == 1 else f'-{n}'}.csv"
                if not candidate.exists() and not candidate.with_suffix(".json").exists():
                    csv_path = candidate
                    break
            if not csv_path:
                raise PgError("Too many backups of one table in one second")
            written.append(csv_path)
            rows, size = copy_out(conn, select, csv_path, exclusive=True)
            sidecar = csv_path.with_suffix(".json")
            written.append(sidecar)
            with new_file(sidecar) as f:
                f.write(scrub(json.dumps(sidecar_data(conn, oid, database, schema, name, where, stamp, rows), indent=1,
                                         default=str)).encode())
            done.append({"table": f"{schema}.{name}", "where": where, "rows": rows, "bytes": size,
                         "file": rel(csv_path), "sidecar": rel(sidecar)})
    except BaseException:
        for path in written:
            with contextlib.suppress(OSError):
                path.unlink()
        raise
    return done


def sidecar_data(conn, oid: int, database: str, schema: str, name: str, where, stamp: str, rows: int) -> dict:
    columns = [{"name": n, "type": t, "type_oid": o, "typmod": m, "not_null": nn, "default": d, "generated": bool(g),
                "identity": i or None} for n, t, o, m, nn, d, g, i in conn.execute("""
        SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.atttypid::int, a.atttypmod, a.attnotnull,
               pg_get_expr(d.adbin, d.adrelid), a.attgenerated <> '',
               CASE a.attidentity WHEN 'a' THEN 'always' WHEN 'd' THEN 'by default' END
        FROM pg_catalog.pg_attribute a LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum""", [oid])]
    return {"database": database, "schema": schema, "table": name, "taken": stamp, "where": where, "rows": rows,
            "columns": columns, "primary_key": primary_key(conn, oid),
            "constraints": [{"name": n, "definition": d} for n, d in conn.execute(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint WHERE conrelid = %s "
                "AND contype NOT IN ('p', 'n') ORDER BY conname", [oid])],
            "indexes": [r[0] for r in conn.execute("SELECT pg_get_indexdef(indexrelid) FROM pg_catalog.pg_index "
                                                   "WHERE indrelid = %s AND NOT indisprimary ORDER BY 1", [oid])]}


def primary_key(conn, oid: int) -> list[str] | None:
    return one(conn, "SELECT array_agg(a.attname ORDER BY k.ord) FROM pg_catalog.pg_constraint c "
                     "CROSS JOIN unnest(c.conkey) WITH ORDINALITY k(attnum, ord) JOIN pg_catalog.pg_attribute a "
                     "ON a.attrelid = c.conrelid AND a.attnum = k.attnum WHERE c.conrelid = %s AND c.contype = 'p'", [oid])


def backup_table(database: str, table: str, where: str | None = None) -> list[dict]:
    """Back one table (or some of its rows) up as Bob, read-only, to db-backups/<database>/."""
    psycopg = _psycopg()
    with session(database, timeout=FILE_TIMEOUT, options=FILE_TX) as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        try:
            return backup(conn, database, [{"table": table, "where": where}] if where else [table])
        except psycopg.Error as e:
            raise PgError(explain(e, database)) from None


# ---------------------------------------------------------------- system-database changes

# Names that an admin session must never reach: files, programs, signals, replication, string-executing
# functions and the catalogs that hold password hashes. Matched anywhere in the text, comments and strings
# included, and in decoded quoted names.
DENIED = re.compile(r"(?<![a-z0-9_$])(?:pg_read_\w*|pg_ls_\w*|pg_stat_file|lo_\w*|dblink\w*|pg_terminate_backend|"
                    r"pg_cancel_backend|pg_reload_conf|pg_\w*replication_slot\w*|pg_replication_origin_\w*|pg_logical_\w*|"
                    r"pg_switch_wal|pg_backup_\w*|pg_stat_reset\w*|pg_log_\w*|set_config|\w*_to_xml\w*|ts_stat|"
                    r"pg_authid|pg_shadow|pg_user_mappings?|pg_subscription|pg_stat_activity|pg_stat_statements\w*|pg_file_settings|"
                    r"pg_hba_file_rules|pg_ident_file_mappings|pg_largeobject\w*)(?![a-z0-9_$])")
UNICODE_NAME = re.compile(r'[Uu]&"((?:[^"]|"")*)"')
UNICODE_ESCAPE = re.compile(r"\\(?:(\\)|([0-9A-Fa-f]{4})|\+([0-9A-Fa-f]{6}))")
QUOTED_NAME = re.compile(r'"((?:[^"]|"")*)"')
# Objects that hold credentials or reach outside the database.
OUTSIDE_OBJECTS = {"SUBSCRIPTION", "SERVER", "FOREIGN", "TABLESPACE"}
WRITE_WORDS = {"INSERT", "UPDATE", "DELETE", "MERGE"}


def denied_names(sql: str) -> str | None:
    """The first denied function or catalog name in a statement, or None."""
    text = [sql.lower()]
    for m in UNICODE_NAME.finditer(sql):
        decoded = UNICODE_ESCAPE.sub(lambda e: "\\" if e.group(1) else chr(int(e.group(2) or e.group(3), 16)), m.group(1))
        text.append(decoded.replace('""', '"').lower())
    text += [m.group(1).replace('""', '"').lower() for m in QUOTED_NAME.finditer(sql)]
    found = DENIED.search("\n".join(text))
    return found.group() if found else None


def admin_refusal(sql: str, toks: list[str], words: tuple) -> str | None:
    """Why change_system_db refuses a statement beyond the refusals every database has, or None."""
    for phrase, why in ((("CASCADE",), "CASCADE (name each dependent object instead)"),
                        (("CREATE", "OR", "REPLACE"), "CREATE OR REPLACE"),
                        (("SECURITY", "DEFINER"), "SECURITY DEFINER"), (("UESCAPE",), "UESCAPE")):
        if any(tuple(toks[i:i + len(phrase)]) == phrase for i in range(len(toks))):
            return why
    if words[:1] in (("CREATE",), ("ALTER",)) and words[1:2] and words[1] in OUTSIDE_OBJECTS:
        return f"{words[1].lower()}s (they reach outside the database)"
    denied = denied_names(sql)
    if denied:
        return f"the name {denied} (files, programs, signals, replication, password hashes)"
    return None


def reads_only(words: tuple, toks: list[str], columns: list[str]) -> bool:
    if words[0] in ("SHOW", "EXPLAIN"):
        return True
    if not columns or words[0] not in ("SELECT", "WITH", "TABLE", "VALUES"):
        return False
    return words[0] != "WITH" or not WRITE_WORDS & set(toks)


def log_change(entry: dict):
    """Append one line to db-backups/log.jsonl."""
    BACKUPS.mkdir(parents=True, exist_ok=True)
    fd = os.open(BACKUPS / "log.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(scrub(json.dumps(entry, default=str)) + "\n")


def change_system_db(database: str, sql: str, backup_tables: list | None = None) -> dict:
    """One write on a system database (any database but the app database), as the admin login. Name every table
    the statement touches in backup_tables, each as "schema.table" or {"table": "schema.table", "where": "<condition>"}
    to back up only some rows. Only CREATE TABLE, CREATE INDEX and CREATE VIEW may go without a backup. The backups
    and the statement run in one REPEATABLE READ transaction, so the backup is the state the statement saw; a backup
    that fails or reaches 200 MB stops the write. The whole call has a 180 s budget. One line per call goes to
    db-backups/log.jsonl. Refused: statements that only read (use run_sql), what run_sql refuses on any
    database, CASCADE, CREATE OR REPLACE, SECURITY DEFINER, and names that reach files, programs, signals,
    replication or password hashes. Undo with `pg_ops.py restore`."""
    psycopg = _psycopg()
    if database == settings()["app_database"]:
        raise PgError(f"{database} is the app database: use run_sql there.")
    if not SAFE_FILE_NAME.match(database):
        raise PgError(f"{database!r} is not a usable database name")
    backup_tables = backup_tables or []
    if not isinstance(backup_tables, list):
        raise PgError("backup_tables must be a list")
    toks, words = list(tokens(sql)), leading_words(sql)
    why = refusal(words, app=True) or schema_elements(sql) or admin_refusal(sql, toks, words)  # app=True: CREATE is allowed here
    if why:
        raise PgError(f"Refused: {why} cannot run through change_system_db.")
    creates = words[:2] in (("CREATE", "TABLE"), ("CREATE", "INDEX"), ("CREATE", "VIEW")) or words[:3] == ("CREATE", "UNIQUE", "INDEX")
    if not backup_tables and not creates:
        raise PgError("Name every table the statement changes in backup_tables; only CREATE TABLE, CREATE INDEX "
                      "and CREATE VIEW run without a backup.")
    conn = connect(database, admin=True, timeout=FILE_TIMEOUT, options="-c transaction_timeout=180000")
    entry = {"time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "database": database,
             "statement": sql, "backups": [], "outcome": "rolled back"}
    result = {"database": database, "committed": False}
    try:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        try:
            columns = describe_one(conn, sql)  # one statement, or an error
        except psycopg.Error as e:
            raise PgError(explain(e, database)) from None
        if reads_only(words, toks, columns):
            raise PgError(f"Refused: this statement only reads. Use run_sql; {database} is readable there.")
        try:
            result["backups"] = backup(conn, database, backup_tables)
            entry["backups"] = [b["file"] for b in result["backups"]]
            with conn.cursor() as cur:
                cur.execute(sql, prepare=True)
                result.update(status=cur.statusmessage, row_count=max(cur.rowcount, 0), columns=columns)
                if columns:
                    result["rows"] = [[jsonable(v) for v in row] for row in cur.fetchmany(200)]
                    result["truncated"] = cur.rowcount > len(result["rows"])
        except psycopg.Error as e:
            raise PgError(explain(e, database) + ". Nothing was changed.") from None
        try:
            conn.commit()
            entry["outcome"] = "committed"
            result["committed"] = True
        except psycopg.Error as e:
            entry["outcome"] = "unknown"
            result["committed"] = "unknown"
            result["note"] = scrub(f"The commit failed ({first_line(e)}); the change may or may not have been applied. "
                                   "Check the data before running it again.")
    except PgError as e:
        entry["error"] = str(e)
        raise
    finally:
        with contextlib.suppress(Exception):
            conn.rollback()
        conn.close()
        if entry["backups"] or entry["outcome"] != "rolled back" or "error" in entry:
            log_change(entry)
    result["log"] = rel(BACKUPS / "log.jsonl")
    return result


# ---------------------------------------------------------------- restore

def restore(database: str, backup_csv: str, confirmed: bool = False) -> dict:
    """Put the rows of a backup file back, as the admin login, in one transaction: the rows of the table whose
    primary key is in the backup are replaced by the backup's rows, and every other row is left alone. A table that
    is gone is recreated first from the sidecar (columns and primary key; defaults, other indexes and constraints
    are returned for manual repair). A table without a primary key is refused. The file must be under
    db-backups/<database>/. Needs no psql."""
    psycopg = _psycopg()
    from psycopg import sql as pgsql
    if not SAFE_FILE_NAME.match(database):
        raise PgError(f"{database!r} is not a usable database name")
    path = (ROOT / backup_csv).resolve()
    if not inside(path, BACKUPS / database) or path.suffix != ".csv" or not path.is_file():
        raise PgError(f"{backup_csv!r} must be a .csv file under db-backups/{database}/")
    sidecar = path.with_suffix(".json")
    if not sidecar.is_file():
        raise PgError(f"The sidecar {rel(sidecar)} is missing")
    if path.stat().st_size > EXPORT_MAX:
        raise PgError("The backup file is over 200 MB")
    meta = json.loads(sidecar.read_text())
    schema, name = meta.get("schema"), meta.get("table")
    if not isinstance(schema, str) or not isinstance(name, str) or schema in ("pg_catalog", "information_schema") \
            or schema.startswith("pg_"):
        raise PgError(f"The sidecar names {schema}.{name}; restore only puts rows back into application tables")
    app = database == settings()["app_database"]
    if not app and not confirmed:
        raise PgError("A restore into a system database runs as the admin login and must be confirmed by a person: "
                      "run `uv run --script server/pg_ops.py restore ...` in a terminal")
    with open(path, newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f), None)
    if not header:
        raise PgError(f"{rel(path)} has no header line")
    result = {"database": database, "table": f"{schema}.{name}", "file": rel(path), "recreated_table": False}
    with session(database, admin=not app, timeout=FILE_TIMEOUT, options=FILE_TX) as conn:
        try:
            into = pgsql.Identifier(schema, name)
            oid = one(conn, "SELECT to_regclass(%s)::oid", [into.as_string(conn)])
            if oid is None:
                oid = recreate_table(conn, meta, into, database)
                result["recreated_table"] = True
                result["manual_repair"] = [f"default of {c['name']}: {c['default']}" for c in meta["columns"] if c["default"]] \
                    + [f"identity ({c['identity']}) on {c['name']}" for c in meta["columns"] if c.get("identity")] \
                    + [f"index: {d}" for d in meta["indexes"]] \
                    + [f"constraint {c['name']}: {c['definition']}" for c in meta["constraints"]]
            key = primary_key(conn, oid)
            if not key:
                raise PgError(f"{schema}.{name} has no primary key, so a restore cannot tell which rows to replace. Load "
                              f"{rel(path)} into a temporary table with COPY ... WITH (FORMAT csv, HEADER) and merge it by hand")
            generated = {r[0]: r[1] for r in conn.execute(
                "SELECT attname, attgenerated <> '' FROM pg_catalog.pg_attribute WHERE attrelid = %s AND attnum > 0 "
                "AND NOT attisdropped", [oid])}
            gone = [c for c in header if c not in generated]
            if gone:
                raise PgError(f"The backup has columns that {schema}.{name} no longer has: {', '.join(gone)}. Add them back "
                              "(ALTER TABLE ... ADD COLUMN) or restore by hand")
            missing_key = [c for c in key if c not in header]
            if missing_key:
                raise PgError(f"The backup lacks the primary key column(s) {', '.join(missing_key)}")
            columns = pgsql.SQL(", ").join(pgsql.Identifier(c) for c in header)
            # Generated columns come back by themselves, not from the file.
            insert = pgsql.SQL(", ").join(pgsql.Identifier(c) for c in header if not generated[c])
            conn.execute(pgsql.SQL("CREATE TEMP TABLE zz_restore ON COMMIT DROP AS SELECT {} FROM {} WITH NO DATA")
                         .format(columns, into))
            with conn.cursor() as cur:
                with cur.copy(pgsql.SQL("COPY zz_restore ({}) FROM STDIN WITH (FORMAT csv, HEADER)").format(columns)) as copy:
                    for chunk in file_chunks(path):
                        copy.write(chunk)
                loaded = cur.rowcount
                cur.execute(pgsql.SQL("DELETE FROM {} t USING zz_restore r WHERE {}").format(
                    into, pgsql.SQL(" AND ").join(pgsql.SQL("t.{0} = r.{0}").format(pgsql.Identifier(c)) for c in key)))
                replaced = cur.rowcount
                cur.execute(pgsql.SQL("INSERT INTO {} ({}) OVERRIDING SYSTEM VALUE SELECT {} FROM zz_restore")
                            .format(into, insert, insert))
            conn.commit()
        except psycopg.Error as e:
            raise PgError(explain(e, database) + ". Nothing was restored.") from None
    result.update(rows_restored=loaded, rows_replaced=replaced)
    return result


def recreate_table(conn, meta: dict, into, database: str) -> int:
    """Create a dropped table again from its sidecar: columns, NOT NULL and the primary key. Returns its oid."""
    from psycopg import sql as pgsql
    if not meta.get("primary_key"):
        raise PgError(f"{meta['schema']}.{meta['table']} is gone and its backup has no primary key. Recreate the table by "
                      "hand, then load the backup file with COPY ... WITH (FORMAT csv, HEADER)")
    defs = []
    for c in meta["columns"]:
        oid, mod = c.get("type_oid"), c.get("typmod")
        rendered = one(conn, "SELECT format_type(t.oid, %s) FROM pg_catalog.pg_type t WHERE t.oid = %s", [mod, oid]) \
            if isinstance(oid, int) and isinstance(mod, int) else None
        if not rendered:
            raise PgError(f"The sidecar does not give a usable type for column {c.get('name')!r}; recreate the table by hand")
        defs.append(pgsql.SQL("{} {}{}").format(pgsql.Identifier(c["name"]), pgsql.SQL(rendered),
                                                pgsql.SQL(" NOT NULL" if c["not_null"] else "")))
    defs.append(pgsql.SQL("PRIMARY KEY ({})").format(pgsql.SQL(", ").join(map(pgsql.Identifier, meta["primary_key"]))))
    conn.execute(pgsql.SQL("CREATE TABLE {} ({})").format(into, pgsql.SQL(", ").join(defs)))
    if database == settings()["app_database"] and one(conn, "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"):
        owner = settings()["app_role"] or one(conn, "SELECT pg_get_userbyid(datdba) FROM pg_database "
                                                    "WHERE datname = current_database()")
        conn.execute(pgsql.SQL("ALTER TABLE {} OWNER TO {}").format(into, pgsql.Identifier(owner)))
    return one(conn, "SELECT to_regclass(%s)::oid", [into.as_string(conn)])


# ---------------------------------------------------------------- errors


def first_line(e) -> str:
    diag = getattr(e, "diag", None)
    text = (diag and diag.message_primary) or str(e)
    return text.strip().splitlines()[0] if text.strip() else type(e).__name__


def explain(e, database: str, connecting: str | None = None) -> str:
    code = getattr(e, "sqlstate", None)
    text = f"{code}: {first_line(e)}" if code else first_line(e)
    if code == "25006":
        text += f". {database} is read-only for Bob. Write in {settings()['app_database']}, or use change_system_db"
    elif code == "42501":
        text += (". Bob's login cannot do this. Reads work in every database; writes only in "
                 f"{settings()['app_database']}")
    elif code == "55P03":
        text += ". " + lock_holders(database)
    elif connecting:
        s = settings()
        text += f". Connecting to {s['host']}:{s['port']} as {connecting}, database {database}"
    return scrub(text)


def lock_holders(database: str) -> str:
    """Who holds locks in a database, without their query text (Bob's login cannot see it anyway)."""
    try:
        with session(database) as conn:
            held = conn.execute("""
                SELECT l.relation::regclass::text, l.mode, a.usename, a.application_name, a.state
                FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid
                WHERE l.granted AND l.relation IS NOT NULL AND l.database = (SELECT oid FROM pg_database
                WHERE datname = current_database()) AND l.pid <> pg_backend_pid() LIMIT 5""").fetchall()
            prepared = one(conn, "SELECT count(*) FROM pg_prepared_xacts WHERE database = current_database()")
    except PgError:
        return "Another session holds a lock on the table; try again later."
    text = "Waited 5 s for a lock. Held by: " + ("; ".join(f"{r} {m} by {u} ({a or '?'}, {s or '?'})" for r, m, u, a, s in held)
                                                 or "nobody visible")
    return text + (f". {prepared} prepared transaction(s) are open in this database" if prepared else "")


# ---------------------------------------------------------------- CLI


def confirm_restore(a) -> bool:
    """A person at a terminal confirms a system-database restore, after seeing what the backup will put back."""
    if not sys.stdin.isatty():
        raise PgError("A restore into a system database must be confirmed at a terminal; run it yourself, not from a script")
    meta = json.loads((ROOT / a.backup_csv).resolve().with_suffix(".json").read_text())
    print(f"This puts {meta.get('rows')} row(s) back into {meta.get('schema')}.{meta.get('table')} in {a.database}, as the "
          f"admin login, replacing the rows with the same primary key. Backup taken {meta.get('taken')}"
          + (f", rows where {meta['where']}" if meta.get("where") else "") + ".")
    return input(f"Type {meta.get('table')} to go ahead: ").strip() == meta.get("table")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    sub.add_parser("remove-login")
    sub.add_parser("databases")
    sub.add_parser("tables").add_argument("database")
    p = sub.add_parser("describe")
    p.add_argument("database")
    p.add_argument("table")
    p = sub.add_parser("sql")
    p.add_argument("database")
    p.add_argument("statement")
    p.add_argument("--limit", type=int, default=200)
    p = sub.add_parser("export")
    p.add_argument("database")
    p.add_argument("source", help="a table name, or one SELECT")
    p.add_argument("file", help="relative to the project, under work/")
    p.add_argument("--overwrite", action="store_true")
    p = sub.add_parser("import")
    p.add_argument("table")
    p.add_argument("file", help="a CSV file, or a .json array of objects, under work/")
    p.add_argument("--replace", action="store_true", help="back the table up, empty it, then load")
    p = sub.add_parser("backup")
    p.add_argument("database")
    p.add_argument("table")
    p.add_argument("--where", help="back up only the rows that match")
    p = sub.add_parser("restore")
    p.add_argument("database")
    p.add_argument("backup_csv", help="a backup file under db-backups/<database>/")
    a = parser.parse_args()
    try:
        if a.command == "setup":
            changes = ensure_login(force=True)
            out = {"changes": changes or ["nothing to change"], "app_role": _ready["app_role"]}
        elif a.command == "remove-login":
            out = remove_login()
        elif a.command == "databases":
            out = databases()
        elif a.command == "tables":
            out = tables(a.database)
        elif a.command == "describe":
            out = describe(a.database, a.table)
        elif a.command == "export":
            out = export_csv(a.database, a.source, a.file, a.overwrite)
        elif a.command == "import":
            out = import_file(a.table, a.file, "replace" if a.replace else "append")
        elif a.command == "backup":
            out = backup_table(a.database, a.table, a.where)
        elif a.command == "restore":
            out = restore(a.database, a.backup_csv, confirmed=a.database == settings()["app_database"] or confirm_restore(a))
        else:
            out = execute(a.database, a.statement, a.limit)
    except PgError as e:
        sys.exit(f"error: {e}")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
