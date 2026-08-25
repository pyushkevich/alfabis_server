"""
/blobs/<hash> is a deliberately unauthenticated shareable-link download path
(DirectDownloadAPI in app.py) -- no session/token required.
"""
import requests


def test_direct_download_requires_no_auth(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup

    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    ticket_id = int(r.text.strip())
    r = consumer.post(
        server.base_url + "/api/tickets/%d/status" % ticket_id, data={"status": "ready"}
    )
    r = provider_sess.post(
        server.base_url + "/api/pro/services/%s/claims" % githash,
        data={"provider": provider_name, "code": "w1"},
    )
    assert int(r.text.strip()) == ticket_id

    attachment_bytes = b"attachment payload \x00\xff"
    files = {"myfile": ("log.png", attachment_bytes, "image/png")}
    r = provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/attachments" % ticket_id,
        files=files,
        data={"desc": "a screenshot"},
    )
    assert r.status_code == 200
    assert r.text.strip().isdigit()

    conn = server.db()
    try:
        uuid = conn.execute(
            "select uuid from ticket_attachment where ticket_id=?", (ticket_id,)
        ).fetchone()["uuid"]
    finally:
        conn.close()

    # No cookies, no token -- plain unauthenticated GET
    r = requests.get(server.base_url + "/blobs/" + uuid[:8])
    assert r.status_code == 200
    assert r.content == attachment_bytes
    assert r.headers["Content-Type"] == "image/png"


def test_direct_download_unknown_hash(server):
    r = requests.get(server.base_url + "/blobs/" + "a" * 8)
    assert r.status_code == 400
