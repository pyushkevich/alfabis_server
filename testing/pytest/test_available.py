"""
/api/pro/services/available: lists the services with 'ready' tickets, in claim
priority order, without claiming anything -- so a provider can allocate
resources (e.g. a GPU) before taking a ticket out of the queue.
"""
import uuid

from conftest import _make_git_service_repo


def _add_service(server, admin, provider_name):
    service_name = "test-svc-" + uuid.uuid4().hex[:12]
    repo_dir = _make_git_service_repo(server, service_name=service_name)
    r = admin.post(
        server.base_url + "/api/admin/providers/%s/services" % provider_name,
        data={"repo": repo_dir, "ref": "main"},
    )
    assert r.status_code == 200, r.text
    return r.text.strip(), service_name


def _ready_ticket(server, consumer, githash):
    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    ticket_id = int(r.text.strip())
    r = consumer.post(
        server.base_url + "/api/tickets/%d/status" % ticket_id, data={"status": "ready"}
    )
    assert r.status_code == 200
    return ticket_id


def _available(server, provider_sess, githashes):
    r = provider_sess.post(
        server.base_url + "/api/pro/services/available",
        data={"services": ",".join(githashes)},
    )
    assert r.status_code == 200, r.text
    assert r.headers["Content-Type"] == "text/csv"
    return [line.split(",") for line in r.text.strip().splitlines()]


def test_available_priority_order_and_no_claim(server, admin, consumer, provider_setup):
    provider_sess, provider_name, githash_a, name_a = provider_setup
    githash_b, name_b = _add_service(server, admin, provider_name)
    githash_c, _ = _add_service(server, admin, provider_name)

    # Service B gets the oldest ticket, so it comes first; C has no ready tickets
    t_b = _ready_ticket(server, consumer, githash_b)
    _ready_ticket(server, consumer, githash_a)
    _ready_ticket(server, consumer, githash_a)

    rows = _available(server, provider_sess, [githash_a, githash_b, githash_c])
    assert rows == [[githash_b, name_b, "1"], [githash_a, name_a, "2"]]

    # Polling did not claim anything: the same answer comes back again
    assert _available(server, provider_sess, [githash_a, githash_b, githash_c]) == rows

    # A subsequent multi-service claim picks the ticket from the first listed service
    r = provider_sess.post(
        server.base_url + "/api/pro/services/claims",
        data={"services": ",".join([githash_a, githash_b]), "provider": provider_name},
    )
    assert r.status_code == 200
    assert r.text.strip().split(",")[:2] == [str(t_b), githash_b]

    rows = _available(server, provider_sess, [githash_a, githash_b, githash_c])
    assert rows == [[githash_a, name_a, "2"]]


def test_available_empty(server, provider_setup):
    provider_sess, _, githash, _ = provider_setup
    assert _available(server, provider_sess, [githash]) == []


def test_available_json_format(server, consumer, provider_setup):
    provider_sess, _, githash, service_name = provider_setup
    _ready_ticket(server, consumer, githash)
    r = provider_sess.post(
        server.base_url + "/api/pro/services/available?format=json",
        data={"services": githash},
    )
    assert r.status_code == 200
    assert r.json()["result"] == [
        {"service_githash": githash, "service_name": service_name, "ready_tickets": 1}
    ]


def test_available_requires_service_access(server, consumer, provider_setup):
    _, _, githash, _ = provider_setup
    r = consumer.post(
        server.base_url + "/api/pro/services/available", data={"services": githash}
    )
    assert r.status_code == 401


def test_available_missing_services(server, provider_setup):
    provider_sess, _, _, _ = provider_setup
    r = provider_sess.post(server.base_url + "/api/pro/services/available")
    assert r.status_code == 400


def test_available_updates_pingtime(server, provider_setup):
    provider_sess, _, githash, _ = provider_setup
    conn = server.db()
    try:
        conn.execute("update services set pingtime = 0 where githash = ?", (githash,))
        conn.commit()
    finally:
        conn.close()

    _available(server, provider_sess, [githash])

    conn = server.db()
    try:
        row = conn.execute(
            "select strftime('%s','now') - pingtime as since from services where githash = ?",
            (githash,),
        ).fetchone()
    finally:
        conn.close()
    assert row["since"] < 60
