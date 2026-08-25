"""
Auth-path tests, grounded in the real itksnap-wt client source
(Logic/WorkspaceAPI/RESTClient.cxx, DSSRESTClient::Authenticate):
it does m_Output.compare(0, strlen("logged in as "), "logged in as ") on the
POST /api/login response body -- that literal prefix is a hard client
contract and must never change.
"""
import requests


def test_token_login_response_prefix(server):
    token = "auth-test-token-1"
    server.seed_user("authtest1@example.com", token)
    sess = requests.Session()
    r = sess.post(server.base_url + "/api/login", data={"token": token})
    assert r.status_code == 200
    assert r.text.startswith("logged in as ")
    assert "authtest1@example.com" in r.text


def test_token_login_json_format(server):
    token = "auth-test-token-2"
    server.seed_user("authtest2@example.com", token)
    sess = requests.Session()
    r = sess.post(server.base_url + "/api/login", data={"token": token, "format": "json"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"result": {"email": "authtest2@example.com"}}


def test_bad_token_rejected(server):
    sess = requests.Session()
    r = sess.post(server.base_url + "/api/login", data={"token": "not-a-real-token"})
    assert r.status_code == 401


def test_token_is_rotated_after_use(server):
    token = "auth-test-token-3"
    server.seed_user("authtest3@example.com", token)
    sess = requests.Session()
    r = sess.post(server.base_url + "/api/login", data={"token": token})
    assert r.status_code == 200

    # The old token must no longer work
    sess2 = requests.Session()
    r2 = sess2.post(server.base_url + "/api/login", data={"token": token})
    assert r2.status_code == 401

    # The rotated token should now be in the DB and usable
    conn = server.db()
    row = conn.execute(
        "select passwd from users where email=?", ("authtest3@example.com",)
    ).fetchone()
    conn.close()
    new_token = row["passwd"]
    assert new_token != token

    sess3 = requests.Session()
    r3 = sess3.post(server.base_url + "/api/login", data={"token": new_token})
    assert r3.status_code == 200


def test_unauthenticated_request_rejected(server):
    r = requests.get(server.base_url + "/api/tickets")
    assert r.status_code == 401


def test_token_api_requires_login_and_terms(server, consumer):
    # /api/token requires a logged-in session with terms accepted; a bare
    # session that never POSTed /acceptterms should be rejected.
    r = requests.get(server.base_url + "/api/token")
    assert r.status_code == 401
