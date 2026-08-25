"""
Docker-free integration test harness for the itksnap-dss-server (ITK-SNAP DSS) server.

Starts `python -m itksnap_dss_server --server` as a plain local subprocess
against a temp SQLite file and a temp datastore directory -- no Postgres, no
Docker. The SQLite file is intentionally left non-existent; the server
auto-creates and initializes it on startup (itksnap_dss_server.db), so every
test run also exercises that auto-init path. Users are seeded directly via
sqlite3 (not through OAuth, which is out of scope for this suite -- see the
project plan). The server runs WITHOUT ALFABIS_NOAUTH so the real
token-login path (the one itksnap-wt / dss_daemon.sh actually use) is
exercised.

Requires the package to be installed (editable is fine: `pip install -e .`)
so `python -m itksnap_dss_server` resolves.
"""
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import uuid

import pytest
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_for_server(base_url, timeout=10):
    deadline = time.time() + timeout
    last_exc = None
    while time.time() < deadline:
        try:
            requests.get(base_url + "/about", timeout=1)
            return
        except requests.exceptions.ConnectionError as e:
            last_exc = e
            time.sleep(0.1)
    raise RuntimeError("Server did not start in time: %r" % last_exc)


class Server:
    def __init__(self, base_url, sqlite_path, datastore_root, proc):
        self.base_url = base_url
        self.sqlite_path = sqlite_path
        self.datastore_root = datastore_root
        self.proc = proc

    def db(self):
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def seed_user(self, email, token, dispname="Test User", sysadmin=False, tier="poweruser"):
        conn = self.db()
        try:
            conn.execute(
                "insert into users (email,passwd,dispname,sysadmin,tier) values (?,?,?,?,?)",
                (email, token, dispname, 1 if sysadmin else 0, tier),
            )
            conn.commit()
        finally:
            conn.close()

    def login(self, token):
        sess = requests.Session()
        r = sess.post(self.base_url + "/api/login", data={"token": token})
        assert r.status_code == 200, r.text
        assert r.text.startswith("logged in as "), repr(r.text)
        return sess


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("itksnap_dss_run")
    sqlite_path = str(workdir / "test.sqlite3")
    datastore_root = str(workdir / "datastore")
    os.makedirs(datastore_root, exist_ok=True)

    # sqlite_path is intentionally left non-existent here -- the server
    # itself must create and initialize it on startup (auto-init, exercised
    # implicitly by every test in this suite).

    port = free_port()
    env = dict(os.environ)
    env["ALFABIS_SQLITE_PATH"] = sqlite_path
    env["ALFABIS_DATASTORE_ROOT"] = datastore_root
    env["ALFABIS_COOKIE_DOMAIN"] = ""  # host-only cookies, so requests accepts them on 127.0.0.1
    env.pop("ALFABIS_NOAUTH", None)  # exercise the real token-login path
    env.pop("ALFABIS_GOOGLE_CLIENTSECRET", None)  # OAuth routes are out of scope, never hit

    proc = subprocess.Popen(
        [sys.executable, "-m", "itksnap_dss_server", "--server", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    base_url = "http://127.0.0.1:%d" % port
    try:
        wait_for_server(base_url)
    except Exception:
        proc.terminate()
        out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
        raise RuntimeError("Server failed to start.\n" + out)

    yield Server(base_url, sqlite_path, datastore_root, proc)

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def consumer(server):
    # server is module-scoped but this fixture (and the DB it writes to) is
    # not, so each invocation needs a unique email/token to avoid colliding
    # with other tests in the same module.
    uid = uuid.uuid4().hex[:12]
    token = "consumer-token-" + uid
    server.seed_user("consumer-%s@example.com" % uid, token, dispname="Consumer")
    return server.login(token)


@pytest.fixture
def admin(server):
    uid = uuid.uuid4().hex[:12]
    token = "admin-token-" + uid
    server.seed_user("admin-%s@example.com" % uid, token, dispname="Admin", sysadmin=True)
    return server.login(token)


@pytest.fixture
def provider_setup(server, admin):
    """Registers a provider, a service (via a local git fixture repo), links
    a provider user to it, and returns (provider_session, provider_name, githash)."""
    uid = uuid.uuid4().hex[:12]
    provider_token = "provider-token-" + uid
    server.seed_user("provider-%s@example.com" % uid, provider_token, dispname="Provider")

    provider_name = "testprov-" + uid
    r = admin.post(server.base_url + "/api/admin/providers", data={"name": provider_name})
    assert r.status_code == 200, r.text

    provider_email = "provider-%s@example.com" % uid
    r = admin.post(
        server.base_url + "/api/admin/providers/%s/users" % provider_name,
        data={"email": provider_email, "admin": "1"},
    )
    assert r.status_code == 200, r.text

    # Service name is unique per invocation too: AdminProviderServicesAPI.POST
    # rejects registering a different githash under a name+version that's
    # already registered (a real name-clash guard, not a test-isolation bug),
    # and this fixture may run more than once against the same module-scoped
    # server/DB.
    service_name = "test-svc-" + uid
    repo_dir = _make_git_service_repo(server, service_name=service_name)
    r = admin.post(
        server.base_url + "/api/admin/providers/%s/services" % provider_name,
        data={"repo": repo_dir, "ref": "main"},
    )
    assert r.status_code == 200, r.text
    githash = r.text.strip()

    provider_sess = server.login(provider_token)
    return provider_sess, provider_name, githash, service_name


def _make_git_service_repo(server, service_name):
    import json
    import subprocess as sp

    repo_dir = os.path.join(server.datastore_root, "..", "svc_src_" + service_name)
    repo_dir = os.path.abspath(repo_dir)
    os.makedirs(repo_dir, exist_ok=True)
    with open(os.path.join(repo_dir, "service.json"), "w") as f:
        json.dump(
            {
                "name": service_name,
                "version": "1.0.0",
                "shortdesc": "Test service",
                "longdesc": "A fixture service for tests",
                "url": "https://example.org/test-svc",
            },
            f,
        )
    sp.run(["git", "init", "-q", "-b", "main", repo_dir], check=True)
    sp.run(["git", "-C", repo_dir, "config", "user.email", "test@example.com"], check=True)
    sp.run(["git", "-C", repo_dir, "config", "user.name", "Test"], check=True)
    sp.run(["git", "-C", repo_dir, "add", "-A"], check=True)
    sp.run(["git", "-C", repo_dir, "commit", "-q", "-m", "init"], check=True)
    return repo_dir
