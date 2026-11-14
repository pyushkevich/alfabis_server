"""
Job parameters: a service declares typed parameters in the 'parameters' list of
its service.json; the consumer sets values on a ticket while it is in 'init'
(any number of calls, each merging into the stored values; a JSON null removes
a value); defaults are filled in and required values enforced when the ticket
becomes 'ready'; the provider that claimed the ticket reads the values.
"""
import uuid

from conftest import _make_git_service_repo

PARAMS = [
    {
        "name": "corr_mode",
        "displayname": "Correction Mode",
        "type": "choice",
        "default": "shape",
        "choices": [
            {"name": "none", "displayname": "No error correction"},
            {"name": "shape", "displayname": "Shape correction"},
        ],
    },
    {"name": "flip", "type": "boolean", "default": False},
    {"name": "atlas_url", "type": "string", "required": False},
    {"name": "iters", "type": "integer", "default": 100, "min": 1, "max": 1000},
    {"name": "sigma", "type": "number", "min": 0},  # required: no default
]


def _register(server, admin, provider_name, parameters):
    service_name = "test-svc-" + uuid.uuid4().hex[:12]
    repo_dir = _make_git_service_repo(
        server, service_name=service_name, extra={"parameters": parameters}
    )
    return admin.post(
        server.base_url + "/api/admin/providers/%s/services" % provider_name,
        data={"repo": repo_dir, "ref": "main"},
    )


def _service(server, admin, provider_name, parameters=PARAMS):
    r = _register(server, admin, provider_name, parameters)
    assert r.status_code == 200, r.text
    return r.text.strip()


def _new_ticket(server, consumer, githash):
    r = consumer.post(server.base_url + "/api/tickets", data={"githash": githash})
    assert r.status_code == 200, r.text
    return int(r.text.strip())


def _set(server, consumer, ticket_id, values):
    return consumer.post(
        server.base_url + "/api/tickets/%d/params" % ticket_id, json=values
    )


def _get(server, consumer, ticket_id):
    r = consumer.get(server.base_url + "/api/tickets/%d/params" % ticket_id)
    assert r.status_code == 200, r.text
    assert r.headers["Content-Type"] == "application/json"
    return r.json()


def _ready(server, consumer, ticket_id):
    return consumer.post(
        server.base_url + "/api/tickets/%d/status" % ticket_id, data={"status": "ready"}
    )


def test_invalid_specs_rejected(server, admin, provider_setup):
    _, provider_name, _, _ = provider_setup
    bad_specs = [
        [{"name": "x", "type": "float"}],
        [{"name": "x", "type": "choice"}],
        [{"name": "x", "type": "choice", "choices": []}],
        [{"name": "x", "type": "string"}, {"name": "x", "type": "integer"}],
        [{"name": "bad name", "type": "string"}],
        [{"name": "x", "type": "integer", "default": "abc"}],
        [{"name": "x", "type": "integer", "min": 10, "max": 1}],
        [{"name": "x", "type": "string", "min": 1}],
        [{"name": "x", "type": "choice", "default": "c",
          "choices": [{"name": "a"}, {"name": "b"}]}],
        {"x": {"type": "string"}},
    ]
    for spec in bad_specs:
        r = _register(server, admin, provider_name, spec)
        assert r.status_code == 400, spec
        assert "Invalid parameters" in r.text


def test_set_merge_and_remove(server, consumer, admin, provider_setup):
    _, provider_name, _, _ = provider_setup
    githash = _service(server, admin, provider_name)
    ticket_id = _new_ticket(server, consumer, githash)

    assert _get(server, consumer, ticket_id) == {}

    r = _set(server, consumer, ticket_id, {"corr_mode": "none", "iters": 5})
    assert r.status_code == 200, r.text
    assert r.json() == {"corr_mode": "none", "iters": 5}

    # A second call with other names merges into the stored values
    r = _set(server, consumer, ticket_id, {"flip": True, "iters": 7})
    assert r.status_code == 200, r.text
    assert _get(server, consumer, ticket_id) == {"corr_mode": "none", "iters": 7, "flip": True}

    # null removes a value
    r = _set(server, consumer, ticket_id, {"corr_mode": None})
    assert r.status_code == 200, r.text
    assert _get(server, consumer, ticket_id) == {"iters": 7, "flip": True}

    # Form posts send strings, which are converted to the parameter types
    r = consumer.post(
        server.base_url + "/api/tickets/%d/params" % ticket_id,
        data={"flip": "false", "sigma": "0.5", "iters": "9"},
    )
    assert r.status_code == 200, r.text
    assert _get(server, consumer, ticket_id) == {"iters": 9, "flip": False, "sigma": 0.5}


def test_bad_values_rejected(server, consumer, admin, provider_setup):
    _, provider_name, _, _ = provider_setup
    githash = _service(server, admin, provider_name)
    ticket_id = _new_ticket(server, consumer, githash)
    _set(server, consumer, ticket_id, {"iters": 3})

    for values in [
        {"iters": "many"},
        {"iters": 2.5},
        {"iters": 0},
        {"iters": 5000},
        {"iters": True},
        {"sigma": -1},
        {"flip": "maybe"},
        {"corr_mode": "intensity"},
        {"atlas_url": 5},
        {"nope": 1},
        {"nope": None},
    ]:
        r = _set(server, consumer, ticket_id, values)
        assert r.status_code == 400, values

    # A rejected call changes nothing
    assert _get(server, consumer, ticket_id) == {"iters": 3}

    r = consumer.post(
        server.base_url + "/api/tickets/%d/params" % ticket_id,
        data="[1, 2]",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_ready_fills_defaults_and_requires(server, consumer, admin, provider_setup):
    provider_sess, provider_name, _, _ = provider_setup
    githash = _service(server, admin, provider_name)
    ticket_id = _new_ticket(server, consumer, githash)

    # 'sigma' is required and has no default
    r = _ready(server, consumer, ticket_id)
    assert r.status_code == 400
    assert "sigma" in r.text

    assert _set(server, consumer, ticket_id, {"sigma": 1.5}).status_code == 200
    r = _ready(server, consumer, ticket_id)
    assert r.status_code == 200, r.text

    expected = {"corr_mode": "shape", "flip": False, "iters": 100, "sigma": 1.5}
    assert _get(server, consumer, ticket_id) == expected

    # Can no longer change parameters
    assert _set(server, consumer, ticket_id, {"iters": 2}).status_code == 400

    # The provider can read them only after claiming the ticket
    url = server.base_url + "/api/pro/tickets/%d/params" % ticket_id
    assert provider_sess.get(url).status_code == 400

    r = provider_sess.post(
        server.base_url + "/api/pro/services/%s/claims" % githash,
        data={"provider": provider_name, "code": "worker1"},
    )
    assert int(r.text.strip()) == ticket_id
    r = provider_sess.get(url)
    assert r.status_code == 200, r.text
    assert r.headers["Content-Type"] == "application/json"
    assert r.json() == expected

    # They also appear in the ticket detail
    r = consumer.get(server.base_url + "/api/tickets/%d/detail" % ticket_id)
    assert r.json()["result"]["params"] == expected


def test_other_provider_cannot_read(server, consumer, admin, provider_setup):
    _, provider_name, _, _ = provider_setup
    githash = _service(server, admin, provider_name, [{"name": "x", "type": "string", "default": "a"}])
    ticket_id = _new_ticket(server, consumer, githash)
    assert _ready(server, consumer, ticket_id).status_code == 200

    # A different provider user, not linked to this service
    uid = uuid.uuid4().hex[:12]
    server.seed_user("other-%s@example.com" % uid, "other-" + uid)
    other = server.login("other-" + uid)
    r = other.get(server.base_url + "/api/pro/tickets/%d/params" % ticket_id)
    assert r.status_code == 400

    # The consumer of another ticket cannot read them either
    uid = uuid.uuid4().hex[:12]
    server.seed_user("c2-%s@example.com" % uid, "c2-" + uid)
    c2 = server.login("c2-" + uid)
    r = c2.get(server.base_url + "/api/tickets/%d/params" % ticket_id)
    assert r.status_code == 400


def test_legacy_choose_one(server, consumer, admin, provider_setup):
    # The format used by the ASHS-PMC service.json
    _, provider_name, _, _ = provider_setup
    githash = _service(server, admin, provider_name, [
        {
            "name": "corr_mode",
            "displayname": "Correction Mode",
            "hint": "...",
            "type": "choose_one",
            "choices": [
                {"name": "none", "displayname": "No error correction"},
                {"name": "shape", "displayname": "Shape correction"},
                {"name": "intensity", "displayname": "Intensity correction"},
            ],
        }
    ])
    ticket_id = _new_ticket(server, consumer, githash)
    assert _set(server, consumer, ticket_id, {"corr_mode": "bogus"}).status_code == 400
    assert _ready(server, consumer, ticket_id).status_code == 400  # required, no default
    assert _set(server, consumer, ticket_id, {"corr_mode": "intensity"}).status_code == 200
    assert _ready(server, consumer, ticket_id).status_code == 200


def test_service_without_parameters(server, consumer, provider_setup):
    _, _, githash, _ = provider_setup
    ticket_id = _new_ticket(server, consumer, githash)
    assert _set(server, consumer, ticket_id, {"x": 1}).status_code == 400
    assert _ready(server, consumer, ticket_id).status_code == 200
    assert _get(server, consumer, ticket_id) == {}
