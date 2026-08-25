"""
End-to-end ticket lifecycle: create -> upload input -> ready -> claim ->
progress/log -> upload results -> success -> download -> detail -> delete.

Response-shape assertions here are grounded in the real itksnap-wt client
(WorkspaceAPI.cxx / WorkspaceTool.cxx):
  - ticket creation and claim responses are bare ints, parsed via atoi()
  - file listings are headerless CSV, column 0/1 = index/filename
  - claim endpoints are never called with ?format=json by the real client
"""


def test_ticket_lifecycle_end_to_end(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup

    # --- create ticket: response is a bare int, not JSON ---
    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    assert r.status_code == 200
    assert r.text.strip().isdigit()
    ticket_id = int(r.text.strip())

    # --- upload an input file with non-UTF8 bytes; must round-trip exactly ---
    payload = b"\x89PNG\x0d\x0a\x1a\x0a" + bytes(range(256))
    files = {"myfile": ("scan.bin", payload, "application/octet-stream")}
    r = consumer.post(
        server.base_url + "/api/tickets/%d/files/input" % ticket_id,
        files=files,
        data={"filename": "scan.bin", "submit": "send"},
    )
    assert r.status_code == 200
    assert r.text == "success"

    # --- list input files: headerless CSV, (index, filename) ---
    r = consumer.get(server.base_url + "/api/tickets/%d/files/input" % ticket_id)
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/csv"
    rows = [line.split(",") for line in r.text.strip().splitlines()]
    assert rows == [["0", "scan.bin"]]

    # --- mark ready ---
    r = consumer.post(
        server.base_url + "/api/tickets/%d/status" % ticket_id, data={"status": "ready"}
    )
    assert r.status_code == 200
    assert r.text.strip() == "ready"

    # --- provider claims it: bare int response ---
    r = provider_sess.post(
        server.base_url + "/api/pro/services/%s/claims" % githash,
        data={"provider": provider_name, "code": "worker1"},
    )
    assert r.status_code == 200
    assert int(r.text.strip()) == ticket_id

    # --- provider downloads the input file, byte-exact ---
    r = provider_sess.get(
        server.base_url + "/api/pro/tickets/%d/files/input/0" % ticket_id
    )
    assert r.status_code == 200
    assert r.content == payload
    # Provider download does NOT set Content-Length (pre-existing asymmetry,
    # intentionally preserved -- see app.py ProviderTicketFileDownloadAPI)
    assert "Content-Length" not in r.headers

    # --- provider reports progress ---
    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/progress" % ticket_id,
        data={"chunk_start": "0", "chunk_end": "1", "progress": "1.0"},
    )
    assert r.status_code == 200

    r = provider_sess.get(server.base_url + "/api/pro/tickets/%d/progress" % ticket_id)
    assert r.status_code == 200
    assert float(r.text.strip()) == 1.0

    # --- provider logs a message ---
    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/info" % ticket_id,
        data={"message": "All done"},
    )
    assert r.status_code == 200
    assert r.text.strip().isdigit()  # bare log id

    # --- provider uploads results ---
    result_bytes = b"segmentation output bytes \x00\x01\x02"
    files = {"myfile": ("out.nii", result_bytes, "application/octet-stream")}
    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/files/results" % ticket_id, files=files
    )
    assert r.status_code == 200
    assert r.text == "success"

    # --- provider marks success ---
    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/status" % ticket_id,
        data={"status": "success"},
    )
    assert r.status_code == 200
    assert r.text.strip() == "success"

    # --- consumer downloads the result, byte-exact, WITH Content-Length ---
    r = consumer.get(server.base_url + "/api/tickets/%d/files/results/0" % ticket_id)
    assert r.status_code == 200
    assert r.content == result_bytes
    assert int(r.headers["Content-Length"]) == len(result_bytes)

    # --- ticket detail JSON: envelope + log entries in order ---
    r = consumer.get(server.base_url + "/api/tickets/%d/detail" % ticket_id)
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/json"
    detail = r.json()["result"]
    assert detail["status"] == "success"
    assert detail["progress"] == 1.0
    messages = [entry["message"] for entry in detail["log"]]
    assert messages == [
        "Ticket received and queued for processing",
        "Ticket claimed by provider %s instance worker1" % provider_name,
        "All done",
    ]

    # --- consumer status endpoint returns bare string ---
    r = consumer.get(server.base_url + "/api/tickets/%d/status" % ticket_id)
    assert r.status_code == 200
    assert r.text.strip() == "success"

    # --- delete the ticket ---
    r = consumer.get(server.base_url + "/api/tickets/%d/delete" % ticket_id)
    assert r.status_code == 200
    assert r.text.strip() == "deleted"


def test_ticket_creation_rejects_unknown_service(server, consumer):
    r = consumer.post(server.base_url + "/api/tickets", data={"githash": "0" * 40})
    assert r.status_code == 400


def test_ticket_access_denied_to_other_user(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup

    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    ticket_id = int(r.text.strip())

    other_token = "other-consumer-token"
    server.seed_user("otherconsumer@example.com", other_token)
    other_sess = server.login(other_token)

    r = other_sess.get(server.base_url + "/api/tickets/%d/status" % ticket_id)
    assert r.status_code == 400


def test_max_open_tickets_enforced(server, provider_setup):
    _, _, githash, _ = provider_setup

    token = "guest-token-limit"
    server.seed_user("guestlimit@example.com", token, tier="guest")
    sess = server.login(token)

    # guest tier allows 10 open tickets (sql/init_db_users.sql)
    for _ in range(10):
        r = sess.post(server.base_url + "/api/tickets", data={"githash": githash})
        assert r.status_code == 200

    r = sess.post(server.base_url + "/api/tickets", data={"githash": githash})
    assert r.status_code == 400
