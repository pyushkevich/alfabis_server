"""
Session storage (0.3.1): atime is epoch seconds, each row records whether the
session is logged in, and anonymous sessions are purged after a day.

The database is created before the server starts, with sessions in the 0.3.0
format (datetime text atime, no loggedin column) upgraded by
sql/deltas/02_session_epoch_and_loggedin.sql, so the server's first request
(made by wait_for_server) runs the once-per-process cleanup on those rows.
"""
import base64
import datetime
import importlib.resources
import os
import pickle
import signal
import sqlite3
import subprocess
import sys
import time

import pytest
import requests

from conftest import REPO_ROOT, free_port, wait_for_server

DAY = 86400


def _text_atime(seconds_ago):
    t = datetime.datetime.fromtimestamp(time.time() - seconds_ago, datetime.timezone.utc)
    return t.strftime("%Y-%m-%d %H:%M:%S.%f")


def _session_data(**values):
    return base64.encodebytes(pickle.dumps(dict(values))).decode()


@pytest.fixture(scope="module")
def legacy_server(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("itksnap_dss_sessions")
    sqlite_path = str(workdir / "test.sqlite3")
    datastore_root = str(workdir / "datastore")
    os.makedirs(datastore_root)

    pkg = importlib.resources.files("itksnap_dss_server") / "sql"
    con = sqlite3.connect(sqlite_path)
    con.executescript((pkg / "init_db_sqlite.sql").read_text())
    con.executescript(
        "drop table sessions; create table sessions (session_id text not null unique, "
        "atime integer not null default (strftime('%s','now')), data text);")
    con.execute("insert into users (email, passwd, dispname, sysadmin, tier) "
                "values ('sess@example.com', 'sess-token', 'S', 0, 'poweruser')")
    uid = con.execute("select id from users where email='sess@example.com'").fetchone()[0]
    logged_in = dict(loggedin=True, acceptterms=True, is_admin=False,
                     email="sess@example.com", user_id=uid)
    anonymous = dict(loggedin=False, acceptterms=False, is_admin=False)
    rows = {
        "a" * 40: (_text_atime(2 * DAY), logged_in),   # kept
        "b" * 40: (_text_atime(2 * DAY), anonymous),   # purged: anonymous, > 1 day
        "c" * 40: (_text_atime(3600), anonymous),      # kept: anonymous, recent
        "d" * 40: (_text_atime(400 * DAY), logged_in), # purged: > 1 year
    }
    for sid, (atime, data) in rows.items():
        con.execute("insert into sessions values (?, ?, ?)",
                    (sid, atime, _session_data(session_id=sid, ip="127.0.0.1", **data)))
    con.commit()
    con.executescript((pkg / "deltas" / "02_session_epoch_and_loggedin.sql").read_text())
    con.close()

    port = free_port()
    env = dict(os.environ, ALFABIS_SQLITE_PATH=sqlite_path,
               ALFABIS_DATASTORE_ROOT=datastore_root, ALFABIS_COOKIE_DOMAIN="")
    env.pop("ALFABIS_NOAUTH", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "itksnap_dss_server", "--server", "--port", str(port)],
        cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_url = "http://127.0.0.1:%d" % port
    try:
        wait_for_server(base_url)
        yield base_url, sqlite_path
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _rows(sqlite_path):
    con = sqlite3.connect(sqlite_path)
    try:
        return {r[0]: (r[1], r[2], r[3]) for r in
                con.execute("select session_id, atime, typeof(atime), loggedin from sessions")}
    finally:
        con.close()


def test_delta_and_startup_cleanup(legacy_server):
    _, sqlite_path = legacy_server
    rows = _rows(sqlite_path)
    assert "a" * 40 in rows and "c" * 40 in rows
    assert "b" * 40 not in rows and "d" * 40 not in rows
    for sid, (atime, atype, loggedin) in rows.items():
        assert atype == "integer"
        assert loggedin is not None
    assert rows["a" * 40][2] == 1 and rows["c" * 40][2] == 0
    assert abs(rows["a" * 40][0] - (time.time() - 2 * DAY)) < 60


def test_legacy_logged_in_session_still_works(legacy_server):
    base_url, sqlite_path = legacy_server
    s = requests.Session()
    s.cookies.set("webpy_session_id", "a" * 40)
    r = s.get(base_url + "/api/tickets")
    assert r.status_code == 200, r.text
    atime, atype, loggedin = _rows(sqlite_path)["a" * 40]
    assert atype == "integer" and loggedin == 1
    assert abs(atime - time.time()) < 60


def test_new_sessions_store_epoch_and_flag(legacy_server):
    base_url, sqlite_path = legacy_server
    before = set(_rows(sqlite_path))
    s = requests.Session()
    s.get(base_url + "/api/tickets")
    sid = s.cookies.get("webpy_session_id")
    assert sid and sid not in before
    atime, atype, loggedin = _rows(sqlite_path)[sid]
    assert atype == "integer" and loggedin == 0 and abs(atime - time.time()) < 60

    r = s.post(base_url + "/api/login", data={"token": "sess-token"})
    assert r.status_code == 200, r.text
    assert _rows(sqlite_path)[sid][2] == 1
