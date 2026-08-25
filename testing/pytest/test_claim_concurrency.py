"""
Ticket-claim race safety under SQLite.

app.py claims a ready ticket via a single atomic
`UPDATE tickets SET status='claimed' WHERE id=(SELECT ... LIMIT 1) AND
status='ready' RETURNING id` rather than SELECT-then-UPDATE, specifically to
avoid double-claims when multiple provider daemons poll concurrently. This
test proves that property empirically rather than by inspection.
"""
import concurrent.futures


def test_concurrent_claims_exactly_one_winner(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup

    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    ticket_id = int(r.text.strip())
    r = consumer.post(
        server.base_url + "/api/tickets/%d/status" % ticket_id, data={"status": "ready"}
    )
    assert r.status_code == 200

    def try_claim(i):
        return provider_sess.post(
            server.base_url + "/api/pro/services/%s/claims" % githash,
            data={"provider": provider_name, "code": "worker%d" % i},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(try_claim, range(10)))

    for r in responses:
        assert r.status_code == 200

    bodies = [r.text.strip() for r in responses]
    winners = [b for b in bodies if b == str(ticket_id)]
    losers = [b for b in bodies if b == "-1"]

    assert len(winners) == 1, "expected exactly one winner, got: %r" % bodies
    assert len(losers) == 9, "expected 9 empty-queue responses, got: %r" % bodies

    conn = server.db()
    try:
        n = conn.execute(
            "select count(*) as n from claim_history where ticket_id=?", (ticket_id,)
        ).fetchone()["n"]
    finally:
        conn.close()
    assert n == 1

    r = consumer.get(server.base_url + "/api/tickets/%d/status" % ticket_id)
    assert r.text.strip() == "claimed"
