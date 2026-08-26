"""
Tests for the itksnap-dss-server admin CLI (`set-sysadmin`/`unset-sysadmin`)
in itksnap_dss_server/cli.py -- the bootstrap path for granting the very
first sysadmin on a deployment, since AdminAbstractAPI.check_auth (app.py)
requires an *existing* sysadmin to grant that status through the web UI.

Runs the CLI as a real subprocess (not by importing cli.py directly) against
the same SQLite file the `server` fixture's live server process is using, to
exercise the actual --sqlite-path/ALFABIS_SQLITE_PATH resolution and confirm
it operates on the running server's database, not some other one.
"""
import os
import subprocess
import sys
import uuid


def _run_cli(server, *args):
    env = dict(os.environ)
    env["ALFABIS_SQLITE_PATH"] = server.sqlite_path
    env["ALFABIS_DATASTORE_ROOT"] = server.datastore_root
    return subprocess.run(
        [sys.executable, "-m", "itksnap_dss_server"] + list(args),
        env=env,
        capture_output=True,
        text=True,
    )


def _sysadmin_flag(server, email):
    conn = server.db()
    try:
        row = conn.execute("select sysadmin from users where email=?", (email,)).fetchone()
    finally:
        conn.close()
    return row["sysadmin"] if row else None


def test_set_and_unset_sysadmin(server):
    uid = uuid.uuid4().hex[:12]
    email = "cli-%s@example.com" % uid
    server.seed_user(email, "cli-token-" + uid, sysadmin=False)

    r = _run_cli(server, "set-sysadmin", email)
    assert r.returncode == 0, r.stderr
    assert "sysadmin=True" in r.stdout
    assert _sysadmin_flag(server, email) == 1

    r = _run_cli(server, "unset-sysadmin", email)
    assert r.returncode == 0, r.stderr
    assert "sysadmin=False" in r.stdout
    assert _sysadmin_flag(server, email) == 0


def test_set_sysadmin_unknown_user_fails(server):
    email = "nobody-%s@example.com" % uuid.uuid4().hex[:12]
    r = _run_cli(server, "set-sysadmin", email)
    assert r.returncode != 0
    assert "no user with email" in r.stderr
    assert _sysadmin_flag(server, email) is None


def test_admin_command_requires_email(server):
    r = _run_cli(server, "set-sysadmin")
    assert r.returncode != 0
