"""Start the real APIs and Vite against a private, persistent local Postgres cluster."""

import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local"


def postgres_bin() -> Path:
    if value := os.environ.get("POSTGRES_BIN"):
        directory = Path(value)
    elif value := shutil.which("initdb"):
        directory = Path(value).parent
    else:
        candidates = sorted(
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")).glob("PostgreSQL/*/bin"),
            reverse=True,
        )
        if not candidates:
            raise RuntimeError("Install PostgreSQL and set POSTGRES_BIN to its bin directory.")
        directory = candidates[0]
    if not (directory / ("initdb.exe" if os.name == "nt" else "initdb")).exists():
        raise RuntimeError(f"PostgreSQL binaries not found in {directory}")
    return directory


def run(*args):
    # Keep PostgreSQL out of the terminal's Ctrl+C group. The supervisor stops
    # it through pg_ctl after the HTTP processes have closed their connections.
    subprocess.run(
        [str(arg) for arg in args],
        cwd=ROOT,
        check=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


def prepare_database(owner_url: str, app_password: str):
    with psycopg.connect(owner_url, autocommit=True) as conn:
        if not conn.execute("select 1 from pg_roles where rolname = 'survey_app'").fetchone():
            conn.execute(
                sql.SQL("create role survey_app login password {}").format(
                    sql.Literal(app_password)
                )
            )
        if not conn.execute("select 1 from pg_database where datname = 'survey'").fetchone():
            conn.execute("create database survey")
    with psycopg.connect(make_conninfo(owner_url, dbname="survey"), autocommit=True) as conn:
        conn.execute(
            "create table if not exists schema_migrations (version varchar(128) primary key)"
        )
        for migration in sorted((ROOT / "backend/db/migrations").glob("*.sql")):
            version = migration.name.split("_", 1)[0]
            with conn.transaction():
                if conn.execute(
                    "select 1 from schema_migrations where version = %s", (version,)
                ).fetchone():
                    continue
                up = migration.read_text(encoding="utf-8").split("-- migrate:down")[0]
                conn.execute(up, prepare=False)
                conn.execute("insert into schema_migrations values (%s)", (version,))
                print(f"Applied {migration.name}")
        conn.execute("grant connect on database survey to survey_app")
        conn.execute("grant usage on schema public to survey_app")
        conn.execute(
            "grant select, insert, update, delete on all tables in schema public to survey_app"
        )
        # Migration bookkeeping is not application data.
        conn.execute("revoke all on schema_migrations from survey_app")
        conn.execute(
            "alter default privileges in schema public grant select, insert, update, "
            "delete on tables to survey_app"
        )
        conn.execute((ROOT / "backend/db/seed/seed.sql").read_text(encoding="utf-8"), prepare=False)


def check_port(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(
                f"Port {port} is busy. Stop the other local development server."
            ) from error


def main():
    os.chdir(ROOT)
    children = []
    started_db = False
    pg_ctl = None
    cluster = LOCAL / "postgres"
    try:
        backend_only = "--backend-only" in sys.argv
        if not backend_only:
            check_port(4200)
        check_port(8000)
        port = int(os.environ.get("LOCAL_POSTGRES_PORT", "55432"))
        check_port(port)
        binaries = postgres_bin()
        pg_ctl = binaries / "pg_ctl"
        LOCAL.mkdir(exist_ok=True)
        password_file = LOCAL / "postgres-password"
        if not password_file.exists():
            password_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
            if os.name != "nt":
                password_file.chmod(0o600)
        password = password_file.read_text(encoding="utf-8").strip()
        if not (cluster / "PG_VERSION").exists():
            run(
                binaries / "initdb",
                "-D",
                cluster,
                "-U",
                "liana_local_owner",
                "--pwfile",
                password_file,
                "--auth=scram-sha-256",
                "--encoding=UTF8",
            )
        run(
            pg_ctl,
            "-D",
            cluster,
            "-l",
            LOCAL / "postgres.log",
            "-o",
            f"-p {port} -h 127.0.0.1",
            "-w",
            "start",
        )
        started_db = True
        owner_url = make_conninfo(
            host="127.0.0.1",
            port=port,
            user="liana_local_owner",
            password=password,
            dbname="postgres",
        )
        prepare_database(owner_url, password)
        # Only subprocesses get this configuration; .env and Docker settings are untouched.
        env = {
            **os.environ,
            "DATABASE_URL": make_conninfo(
                host="127.0.0.1", port=port, user="survey_app", password=password, dbname="survey"
            ),
            "AUTH_MODE": "dev",
        }
        commands = [
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.scripts.local_gateway:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            [
                os.environ.get("LIANA_NODE", "node"),
                str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
                "--host",
                "127.0.0.1",
            ],
        ]
        if backend_only:
            commands = commands[:1]
        if os.environ.get("LOCAL_QUEUE_WORKERS") == "1":
            commands.extend(
                [
                    [sys.executable, "-m", module]
                    for module in ("survey_worker.main", "liana_connector.main")
                ]
            )
        for index, command in enumerate(commands):
            children.append(
                subprocess.Popen(
                    command,
                    cwd=ROOT / "frontend" if index == 1 and not backend_only else ROOT,
                    env=env,
                )
            )
        print("\nBackend: http://localhost:8000")
        if not backend_only:
            print("Frontend: http://localhost:4200")
        print("Local PostgreSQL data: .local/postgres. Press Ctrl+C to stop.\n")
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise RuntimeError("A development process stopped; see its output above.")
    except KeyboardInterrupt:
        print("\nStopping local development...")
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if started_db:
            run(pg_ctl, "-D", cluster, "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, psycopg.Error) as error:
        print(f"Local development failed: {error}", file=sys.stderr)
        sys.exit(1)
