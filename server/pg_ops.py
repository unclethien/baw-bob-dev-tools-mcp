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
    uv run --script server/pg_ops.py remove-login       # drop Bob's login and its grants
"""

import argparse
import contextlib
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
ACL_BACKUPS = ROOT / "work" / "db-backups" / "acl-before-bob-login"
RESULT_BUDGET = 256 * 1024
APP_CEILING = 1024**3
LIMIT_MAX = 1000
NAME = re.compile(r"^[a-z_][a-z0-9_$]{0,62}$")
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
CODE_OBJECTS = {"FUNCTION", "PROCEDURE", "TRIGGER", "EVENT", "RULE", "AGGREGATE", "OPERATOR", "CAST", "LANGUAGE",
                "ROUTINE", "CONSTRAINT"}  # CONSTRAINT: CREATE CONSTRAINT TRIGGER
ROLE_OBJECTS = {"ROLE", "USER", "GROUP", "DATABASE"}

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


def connect(database: str, admin: bool = False, timeout: int = 30):
    """One connection, as Bob's login (or the admin login). Keyword arguments only: no connection string ever
    holds a password. In the app database the session starts as the app role, by startup option."""
    psycopg = _psycopg()
    missing = pg_missing_settings()
    if missing:
        raise PgError(f"PostgreSQL is not configured (missing {', '.join(missing)}). Set them in .env; "
                      "see the PostgreSQL card on the CP4BA access portal")
    if not admin:
        ensure_login()
    s = settings()
    user, password = (s["user"], s["password"]) if admin else (s["bob_user"], s["bob_password"])
    options = f"-c statement_timeout={timeout * 1000} -c lock_timeout=5000 -c work_mem=16MB -c max_parallel_workers_per_gather=0"
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
def session(database: str, admin: bool = False, timeout: int = 30):
    """A connection that is always rolled back and closed at the end. Bob's sessions on any database other
    than the app database are READ ONLY."""
    conn = connect(database, admin=admin, timeout=timeout)
    try:
        if not admin and database != settings()["app_database"]:
            conn.read_only = True
        yield conn
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
            existed = one(conn, "SELECT count(*) FROM pg_roles WHERE rolname = %s", [bob])
            if not existed:
                backup_acls(conn)
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(bob)))
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
            for owner in owners:
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


def execute(database: str, sql: str, limit: int = 200) -> dict:
    """Run exactly one statement as Bob. Read-only (and always rolled back) on every database except the app
    database, where a complete statement is committed."""
    psycopg = _psycopg()
    from psycopg import pq
    if not 1 <= limit <= LIMIT_MAX:
        raise PgError(f"limit must be between 1 and {LIMIT_MAX}")
    app = database == settings()["app_database"]
    words = leading_words(sql)
    why = refusal(words, app)
    if why:
        raise PgError(f"Refused: {why} cannot run through run_sql" + ("" if app else f" on {database}") + ".")
    with session(database) as conn:
        try:
            # Parse and describe only, before psycopg opens the transaction. A second statement fails here.
            for step in (lambda: conn.pgconn.prepare(b"", sql.encode(conn.info.encoding)),
                         lambda: conn.pgconn.describe_prepared(b"")):
                described = step()
                if described.status != pq.ExecStatus.COMMAND_OK:
                    raise psycopg.errors.error_from_result(described, encoding=conn.info.encoding)
            columns = [described.fname(i).decode(conn.info.encoding) for i in range(described.nfields)]
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
        else:
            out = execute(a.database, a.statement, a.limit)
    except PgError as e:
        sys.exit(f"error: {e}")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
