"""Phase 9: container setup.

Static checks always run. The live check (build, two users' data,
`down` + `up`, data still there) runs only where Docker is installed,
and is reported as skipped — not passed — everywhere else.
"""
import json
import os
import shutil
import subprocess
import time
import tomllib
import urllib.request
from pathlib import PurePosixPath, Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def _service():
    return COMPOSE["services"]["nova"]


def _db_path() -> PurePosixPath:
    return PurePosixPath(_service()["environment"]["NOVA_DB_PATH"])


# --- static: runs everywhere --------------------------------------------------

def test_database_lives_on_a_named_volume():
    # The DB file's directory must be a mount of a named volume, so it is
    # outside the container's writable layer and survives down/up.
    mounts = {}
    for spec in _service()["volumes"]:
        source, target = spec.split(":")[:2]
        mounts[target] = source
    assert str(_db_path().parent) in mounts
    assert mounts[str(_db_path().parent)] in COMPOSE["volumes"]  # named, not a temp anon volume


def test_dockerfile_and_compose_agree_on_the_db_path():
    assert f"NOVA_DB_PATH={_db_path()}" in DOCKERFILE.replace(" ", "")
    assert f'VOLUME ["{_db_path().parent}"]' in DOCKERFILE


def test_port_published_on_this_machine_only():
    assert _service()["ports"] == ["127.0.0.1:8501:8501"]


def test_container_runs_as_non_root():
    # The image starts as root only so the entrypoint can chown /data
    # (Fly.io mounts volumes root-owned); it then drops to nova for good.
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["/app/docker-entrypoint.sh"]' in DOCKERFILE
    assert "exec setpriv --reuid=nova --regid=nova --init-groups" in entrypoint
    # Regression: without this HOME stayed /root and Streamlit crashed on
    # startup reading /root/.streamlit/secrets.toml (seen on Fly.io).
    assert "export HOME=/home/nova" in entrypoint


def test_fly_mounts_the_volume_where_the_db_lives():
    fly = tomllib.loads((ROOT / "fly.toml").read_text(encoding="utf-8"))
    assert fly["env"]["NOVA_DB_PATH"] == str(_db_path())
    assert fly["mounts"]["destination"] == str(_db_path().parent)
    assert fly["http_service"]["internal_port"] == 8501
    assert fly["http_service"]["checks"][0]["path"] == "/_stcore/health"


def test_build_context_excludes_local_data_and_venv():
    ignored = (ROOT / ".dockerignore").read_text().split()
    for entry in (".venv", "data", "*.db", ".git"):
        assert entry in ignored


# --- live: only with Docker ---------------------------------------------------

DOCKER = shutil.which("docker")
PROJECT = "nova_persistence_test"

SEED = """
import auth, db
from datetime import date
conn = db.connect()
for email, name, day in [("a@example.com", "A", "2026-01-01"), ("b@example.com", "B", "2026-02-01")]:
    user = auth.signup(conn, email, "password-123", name)
    db.save_log(conn, user.id, db.LogEntry(date.fromisoformat(day), flow="heavy"))
"""
CHECK = """
import auth, db, json
conn = db.connect()
out = {}
for email in ("a@example.com", "b@example.com"):
    user = auth.login(conn, email, "password-123")
    out[email] = [e.date.isoformat() for e in db.get_logs(conn, user.id)] if user else None
print(json.dumps(out))
"""


def _compose(*args, timeout=900) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [DOCKER, "compose", "-p", PROJECT, *args],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout,
    )
    # Fail with the container's own error output, not just an exit code.
    assert result.returncode == 0, (
        f"docker compose {args[0]} failed ({result.returncode}):\n"
        f"{result.stderr[-2000:]}\n{result.stdout[-1000:]}"
    )
    return result


def _wait_healthy(seconds=180):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=3) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(2)
    raise AssertionError("app never became healthy")


def test_docker_check_is_not_silently_skipped_in_ci():
    # CI sets NOVA_REQUIRE_DOCKER so a missing Docker fails loudly there.
    if os.environ.get("NOVA_REQUIRE_DOCKER"):
        assert DOCKER is not None, "NOVA_REQUIRE_DOCKER is set but docker isn't installed"


@pytest.mark.skipif(DOCKER is None, reason="Docker is not installed on this machine")
def test_two_users_data_survives_compose_down_and_up():
    try:
        _compose("up", "-d", "--build")
        _wait_healthy()
        _compose("exec", "-T", "-u", "nova", "nova", "python", "-c", SEED)
        # The Streamlit process (PID 1 after the entrypoint's exec) is nova, not root.
        uid = _compose("exec", "-T", "nova", "python", "-c", "import os; print(os.stat('/proc/1').st_uid)")
        assert uid.stdout.strip() == "1000"

        _compose("down")  # no -v: the named volume must survive
        _compose("up", "-d")
        _wait_healthy()

        result = json.loads(_compose("exec", "-T", "-u", "nova", "nova", "python", "-c", CHECK).stdout)
        assert result == {"a@example.com": ["2026-01-01"], "b@example.com": ["2026-02-01"]}
    finally:
        subprocess.run([DOCKER, "compose", "-p", PROJECT, "down", "-v"], cwd=ROOT,
                       capture_output=True, timeout=300)
