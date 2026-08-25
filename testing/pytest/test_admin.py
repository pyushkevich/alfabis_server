"""
Admin API/page auth and the purge endpoint. Admin auth (AdminAbstractAPI.check_auth
in app.py) reads users.sysadmin from the DB -- under SQLite this comes back as
a plain int, not a Python bool, which is why the check must use `not x` rather
than `x is not True` (fixed during the port; this test guards the regression).
"""


def test_non_admin_denied_admin_api(server, consumer):
    r = consumer.get(server.base_url + "/api/admin/providers")
    assert r.status_code == 401


def test_admin_can_list_providers(server, admin):
    r = admin.get(server.base_url + "/api/admin/providers")
    assert r.status_code == 200


def test_admin_html_pages_render(server, admin):
    for path in ("/admin", "/admintickets", "/adminservices", "/about", "/services"):
        r = admin.get(server.base_url + path)
        assert r.status_code == 200, "%s -> %d" % (path, r.status_code)


def test_purge_completed_tickets(server, consumer, provider_setup):
    provider_sess, provider_name, githash, _ = provider_setup

    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    ticket_id = int(r.text.strip())
    consumer.post(
        server.base_url + "/api/tickets/%d/status" % ticket_id, data={"status": "ready"}
    )
    r = provider_sess.post(
        server.base_url + "/api/pro/services/%s/claims" % githash,
        data={"provider": provider_name, "code": "w1"},
    )
    assert int(r.text.strip()) == ticket_id
    provider_sess.post(
        server.base_url + "/api/pro/tickets/%d/status" % ticket_id, data={"status": "success"}
    )

    admin_token = "admin-token-purge"
    server.seed_user("adminpurge@example.com", admin_token, sysadmin=True)
    admin = server.login(admin_token)

    # The purge window is "now - H.atime > threshold" against the ticket's
    # 'init' history row, in epoch-seconds. Real time can't be fast-forwarded,
    # and this test can run start-to-finish within the same wall-clock second
    # (atime has 1-second granularity), so backdate directly rather than
    # relying on elapsed wall-clock time -- this is what actually exercises
    # the purge window, not a way to work around a flaky test.
    conn = server.db()
    try:
        conn.execute(
            "update ticket_history set atime = atime - 10 where ticket_id=? and status='init'",
            (ticket_id,),
        )
        conn.commit()
    finally:
        conn.close()

    r = admin.post(
        server.base_url + "/api/admin/tickets/purge/completed", data={"days": "0"}
    )
    assert r.status_code == 200
    assert r.text.startswith("Purged ")

    # delete_ticket() marks the row status='deleted' rather than removing it,
    # so the ticket is still visible to its owner -- just with status 'deleted'.
    r = consumer.get(server.base_url + "/api/tickets/%d/status" % ticket_id)
    assert r.status_code == 200
    assert r.text.strip() == "deleted"
