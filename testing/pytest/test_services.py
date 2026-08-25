"""
Service catalog endpoints. The real client (itksnap-wt) never passes
?format=json for services listing -- CSV is the live default, not a legacy
fallback -- so the CSV shape here is load-bearing, not incidental.
"""


def test_services_list_csv_default(server, consumer, provider_setup):
    # /api/services lists ALL current services -- since this fixture registers
    # a fresh service per test against the shared module-scoped DB, other
    # tests' services may also be present; check membership, not exact equality.
    _, _, githash, service_name = provider_setup
    r = consumer.get(server.base_url + "/api/services")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/csv"
    rows = [line.split(",") for line in r.text.strip().splitlines()]
    assert [service_name, githash, "1.0.0", "Test service"] in rows


def test_services_list_json_format(server, consumer, provider_setup):
    _, _, githash, service_name = provider_setup
    r = consumer.get(server.base_url + "/api/services?format=json")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/json"
    result = r.json()["result"]
    assert {
        "name": service_name, "githash": githash, "version": "1.0.0", "shortdesc": "Test service"
    } in result


def test_service_detail_is_always_json(server, consumer, provider_setup):
    _, _, githash, service_name = provider_setup
    r = consumer.get(server.base_url + "/api/services/%s/detail" % githash)
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/json"
    detail = r.json()
    assert detail["name"] == service_name
    assert detail["longdesc"] == "A fixture service for tests"


def test_service_detail_unknown_githash(server, consumer):
    r = consumer.get(server.base_url + "/api/services/%s/detail" % ("f" * 40))
    assert r.status_code == 400


def test_service_stats(server, consumer, provider_setup):
    _, _, githash, _ = provider_setup
    r = consumer.get(server.base_url + "/api/services/%s/stats" % githash)
    assert r.status_code == 200
    row = r.text.strip().split(",")
    # n_success, n_failed, last_heard_from, queue_length (avg_duration column
    # only appears once n_success > 0, per ServicesStatsAPI)
    assert row[0] == "0"  # n_success
    assert row[1] == "0"  # n_failed


def test_registering_service_with_bad_repo_fails(server, admin):
    r = admin.post(server.base_url + "/api/admin/providers", data={"name": "badprov"})
    assert r.status_code == 200
    r = admin.post(
        server.base_url + "/api/admin/providers/badprov/services",
        data={"repo": "/nonexistent/path/to/repo", "ref": "main"},
    )
    assert r.status_code == 400
