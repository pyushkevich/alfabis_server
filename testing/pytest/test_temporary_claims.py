"""
Temporary claims: a provider can claim a ticket with a 'timeout' (seconds), e.g.
while it queues the work on SLURM. If the claim is not renewed before it
expires, the ticket returns to 'ready' for other providers.
/api/pro/tickets/<id>/claim lets the job that picks the ticket up take it: it
succeeds if the caller (same provider and code) holds a live temporary claim, or
if the ticket is 'ready'; it fails if the ticket is permanently claimed (even by
the caller), so only one job can start working on a ticket.

Most tests force expiry by back-dating claim_history.expires directly, rather
than sleeping.
"""
import concurrent.futures
import time
import uuid


def _ready_ticket(server, consumer, githash):
    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    ticket_id = int(r.text.strip())
    r = consumer.post(
        server.base_url + "/api/tickets/%d/status" % ticket_id, data={"status": "ready"}
    )
    assert r.status_code == 200
    return ticket_id


def _claim(server, sess, githash, provider_name, timeout=None, code="default"):
    data = {"provider": provider_name, "code": code}
    if timeout is not None:
        data["timeout"] = str(timeout)
    return sess.post(server.base_url + "/api/pro/services/%s/claims" % githash, data=data)


def _renew(server, sess, ticket_id, provider_name, timeout=None, code="default"):
    data = {"provider": provider_name, "code": code}
    if timeout is not None:
        data["timeout"] = str(timeout)
    return sess.post(server.base_url + "/api/pro/tickets/%d/claim" % ticket_id, data=data)


def _expire(server, ticket_id):
    conn = server.db()
    try:
        conn.execute(
            "update claim_history set expires = strftime('%s','now') - 1 "
            "where id = (select max(id) from claim_history where ticket_id = ?)",
            (ticket_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _latest_expires(server, ticket_id):
    conn = server.db()
    try:
        return conn.execute(
            "select expires from claim_history where ticket_id = ? order by id desc limit 1",
            (ticket_id,),
        ).fetchone()["expires"]
    finally:
        conn.close()


def _status(server, consumer, ticket_id):
    return consumer.get(server.base_url + "/api/tickets/%d/status" % ticket_id).text.strip()


def _second_provider_user(server, admin, provider_name):
    uid = uuid.uuid4().hex[:12]
    token = "provider2-token-" + uid
    email = "provider2-%s@example.com" % uid
    server.seed_user(email, token, dispname="Provider 2")
    r = admin.post(
        server.base_url + "/api/admin/providers/%s/users" % provider_name,
        data={"email": email, "admin": "0"},
    )
    assert r.status_code == 200, r.text
    return server.login(token)


def test_permanent_claim_has_no_expiration(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)
    r = _claim(server, provider_sess, githash, provider_name)
    assert r.text.strip() == str(ticket_id)
    assert _latest_expires(server, ticket_id) is None


def test_expired_claim_returns_ticket_to_queue(server, admin, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    other_sess = _second_provider_user(server, admin, provider_name)

    ticket_id = _ready_ticket(server, consumer, githash)
    before = int(time.time())
    r = _claim(server, provider_sess, githash, provider_name, timeout=60)
    assert r.text.strip() == str(ticket_id)
    assert _status(server, consumer, ticket_id) == "claimed"
    assert before + 60 <= _latest_expires(server, ticket_id) <= int(time.time()) + 60

    # While the temporary claim is live, nobody else can take the ticket
    assert _claim(server, other_sess, githash, provider_name).text.strip() == "-1"

    # Once expired, the next claim attempt releases it and hands it over
    _expire(server, ticket_id)
    r = _claim(server, other_sess, githash, provider_name)
    assert r.text.strip() == str(ticket_id)

    conn = server.db()
    try:
        hist = [row["status"] for row in conn.execute(
            "select status from ticket_history where ticket_id = ? order by id", (ticket_id,))]
    finally:
        conn.close()
    assert hist[-3:] == ["claimed", "ready", "claimed"]

    # The original provider has lost access and cannot renew or finish the ticket
    r = _renew(server, provider_sess, ticket_id, provider_name)
    assert r.status_code == 400
    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/status" % ticket_id, data={"status": "success"}
    )
    assert r.status_code == 400
    assert _status(server, consumer, ticket_id) == "claimed"


def test_expired_claim_listed_as_available(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)
    _claim(server, provider_sess, githash, provider_name, timeout=60)

    r = provider_sess.post(server.base_url + "/api/pro/services/available",
                           data={"services": githash})
    assert r.text.strip() == ""

    _expire(server, ticket_id)
    r = provider_sess.post(server.base_url + "/api/pro/services/available",
                           data={"services": githash})
    assert r.text.strip().split(",")[0] == githash
    assert _status(server, consumer, ticket_id) == "ready"


def test_renew_without_timeout_makes_claim_permanent(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)
    _claim(server, provider_sess, githash, provider_name, timeout=60)

    r = _renew(server, provider_sess, ticket_id, provider_name)
    assert r.status_code == 200, r.text
    assert _latest_expires(server, ticket_id) is None

    # A permanent claim never lapses: a later claim attempt does not release it
    assert _claim(server, provider_sess, githash, provider_name).text.strip() == "-1"
    assert _status(server, consumer, ticket_id) == "claimed"

    # Once permanently claimed, the ticket cannot be claimed again, even by the
    # same provider instance (e.g., a second job queued for the same ticket)
    assert _renew(server, provider_sess, ticket_id, provider_name).status_code == 400
    assert _renew(server, provider_sess, ticket_id, provider_name, timeout=60).status_code == 400

    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/status" % ticket_id, data={"status": "success"}
    )
    assert r.status_code == 200
    assert _status(server, consumer, ticket_id) == "success"


def test_renew_with_timeout_extends_claim(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)
    _claim(server, provider_sess, githash, provider_name, timeout=10)
    r = _renew(server, provider_sess, ticket_id, provider_name, timeout=600)
    assert r.status_code == 200, r.text
    assert _latest_expires(server, ticket_id) >= int(time.time()) + 590


def test_renew_after_expiry_reclaims_ready_ticket(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)
    _claim(server, provider_sess, githash, provider_name, timeout=60)
    _expire(server, ticket_id)

    # Nobody else took the ticket, so the late job can still have it
    r = _renew(server, provider_sess, ticket_id, provider_name)
    assert r.status_code == 200, r.text
    assert _status(server, consumer, ticket_id) == "claimed"
    assert _latest_expires(server, ticket_id) is None
    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/status" % ticket_id, data={"status": "success"}
    )
    assert r.status_code == 200


def test_renew_fails_for_other_instance_temporary_claim(server, admin, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    other_sess = _second_provider_user(server, admin, provider_name)
    ticket_id = _ready_ticket(server, consumer, githash)
    _claim(server, provider_sess, githash, provider_name, timeout=60, code="inst1")

    # Same user, different instance code
    assert _renew(server, provider_sess, ticket_id, provider_name, code="inst2").status_code == 400
    # Different user
    assert _renew(server, other_sess, ticket_id, provider_name, code="inst1").status_code == 400
    # The holder itself
    assert _renew(server, provider_sess, ticket_id, provider_name, code="inst1").status_code == 200


def test_renew_fails_for_finished_ticket(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)
    _claim(server, provider_sess, githash, provider_name)
    provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/status" % ticket_id, data={"status": "failed"}
    )
    assert _renew(server, provider_sess, ticket_id, provider_name).status_code == 400
    assert _status(server, consumer, ticket_id) == "failed"


def test_concurrent_renew_of_ready_ticket_one_winner(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)

    def try_renew(i):
        return _renew(server, provider_sess, ticket_id, provider_name, code="w%d" % i)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        codes = [r.status_code for r in pool.map(try_renew, range(10))]
    assert sorted(codes) == [200] + [400] * 9, codes

    conn = server.db()
    try:
        n = conn.execute(
            "select count(*) as n from claim_history where ticket_id=?", (ticket_id,)
        ).fetchone()["n"]
    finally:
        conn.close()
    assert n == 1


def test_multiservice_temporary_claim(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    ticket_id = _ready_ticket(server, consumer, githash)
    r = provider_sess.post(
        server.base_url + "/api/pro/services/claims",
        data={"services": githash, "provider": provider_name, "timeout": "1"},
    )
    assert r.text.strip().split(",")[0] == str(ticket_id)

    # Real-time expiry, no back-dating
    time.sleep(2.1)
    r = provider_sess.post(
        server.base_url + "/api/pro/services/claims",
        data={"services": githash, "provider": provider_name},
    )
    assert r.text.strip().split(",")[0] == str(ticket_id)
    assert _latest_expires(server, ticket_id) is None


def test_invalid_timeout_rejected(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup
    _ready_ticket(server, consumer, githash)
    for bad in ("0", "-5", "abc"):
        r = _claim(server, provider_sess, githash, provider_name, timeout=bad)
        assert r.status_code == 400, bad
