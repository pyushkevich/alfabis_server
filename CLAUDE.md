# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Middleware server for the ITK-SNAP Distributed Segmentation Service (DSS), published as the `itksnap-dss-server` package (import name `itksnap_dss_server`). It's a web.py 0.76 app backed by a local SQLite database. ITK-SNAP users ("consumers") submit tickets; service-provider daemons ("providers") poll the server, claim tickets, download inputs, and upload results. The Python client library for providers lives in a separate repo (`itksnap-dss`); it is not part of this one. User-facing docs are Sphinx sources in `docs/`, published on Read the Docs.

## Commands

```bash
pip install -e '.[test]'                      # tests need the package installed: they launch `python -m itksnap_dss_server`
itksnap-dss-server --server                   # stand-alone server on :8080, DB auto-created at ./datastore/alfabis.sqlite3
itksnap-dss-server --server --noauth --cookie-domain ''   # local dev: auto-logged-in sysadmin test@example.com
itksnap-dss-server set-sysadmin user@example.com          # bootstrap the first admin (user must have logged in once)
pytest testing/pytest                         # full suite
pytest testing/pytest/test_tickets_lifecycle.py::test_name   # single test
docker compose up                             # server + example ITK-SNAP service (service container is linux/amd64)
make -C docs html                             # build docs (pip install -r docs/requirements.txt)
```

There is no linter or formatter configured. Every CLI flag has an `ALFABIS_*` env var equivalent (`ALFABIS_SQLITE_PATH`, `ALFABIS_DATASTORE_ROOT`, `ALFABIS_COOKIE_DOMAIN`, `ALFABIS_NOAUTH`, `ALFABIS_GOOGLE_CLIENTSECRET`). The cookie domain defaults to `dss.itksnap.org`, so pass `''` when testing against localhost or the session cookie won't be sent back.

## Architecture

- **`app.py` holds nearly everything and does its setup at import time.** Importing it parses argv (using `parse_known_args` so it can coexist with uWSGI flags), connects to and auto-initializes the DB, builds the `urls` route table, and creates the session. Under WSGI, the server imports `itksnap_dss_server.app:application` directly. `main_server()` only runs the stand-alone server. Any code that touches `app.db`, including the admin CLI commands, gets its DB connection just by importing the module.
- **`cli.py`** dispatches on `argv[0]`. Admin subcommands (`set-sysadmin`, `unset-sysadmin`) get their own argparse parser. Anything else falls through to `app`'s parser. Don't let two parsers scan the same argv (see the comment in `main()`).
- **`db.py`** wraps web.py's sqlite connection so `PRAGMA foreign_keys = ON` runs on every new per-thread connection. It forces `journal_mode = DELETE`, not WAL, because WAL breaks on Docker Desktop macOS bind mounts and triggered destructive re-inits. If the DB has no `users` table, it runs `sql/init_db_sqlite.sql`. That script begins with `DROP TABLE IF EXISTS`, so it is destructive.
- **Route classes are grouped by URL prefix:**
  - HTML pages (`/services`, `/admin*`, ...) render Markdown templates from `templates/`.
  - `/api/...`: consumer API. `TicketsAPIBase` checks that the ticket belongs to the user.
  - `/api/pro/...`: provider API. `ProviderAPIBase` checks provider access through `provider_access` and `provider_services`, and checks that the ticket was claimed.
  - `/api/admin/...`: `AdminAbstractAPI`, sysadmin only.
  - Business logic is in `TicketLogic`, `TicketLogLogic`, `ServiceLogic`, `ClaimLogic`, and `ProviderServiceLogic`.
- **Ticket lifecycle:** `init → ready → claimed → success | failed | timeout`, and also `deleted`. The schema enforces this with CHECK constraints in two places, `tickets` and `ticket_history`. `TicketLogic.set_status` writes both tables in one transaction. Claiming uses a single atomic `UPDATE ... WHERE status='ready' ... RETURNING id`. Don't split it into SELECT-then-UPDATE, because `test_claim_concurrency.py` tests for that race.
- **Services are git repos.** An admin registers a repo URL and ref. The server clones it with GitPython, reads `service.json`, and identifies the service by its commit hash (`githash`). Clients can look a service up by `githash`, or by `name`, which resolves to the highest dotted version. The server needs the `git` binary at runtime.
- **File storage** lives under `--datastore-root`: `tickets/%08d/{input,results}`, `attachments/%08d`, `logdata/%08d`, and `services/<githash>`. Both the datastore root and the SQLite path default to paths relative to the working directory.
- **Templates and static files are package data,** resolved with `importlib.resources` and not relative to the working directory. `main_server()` disables web.py's built-in `StaticMiddleware` so that `StaticFileAPI` serves the bundled `static/`. If you add new package-data file patterns, also add them to `[tool.setuptools.package-data]` in `pyproject.toml`.
- **Auth:** browser login uses Google OAuth2 (`OAuthHelper`, `/api/oauth2cb`). Programmatic clients (itksnap-wt, provider daemons) POST a token to `/api/login`, and that token is the `users.passwd` column. Sessions are stored in the `sessions` table.

## Gotchas

- web.py's SQLite result sets don't support `len()`. Use `bool(res)` or `not res`, or wrap the result in `list(...)` first.
- Timestamps are stored as integer Unix epoch seconds (`strftime('%s','now')`). In `db.query` strings, write `%` as `%%`.
- Schema changes: edit `sql/init_db_sqlite.sql` and also add a numbered `sql/deltas/NN_description.sql` that is applied to deployments by hand. There is no migration runner (see `sql/deltas/README.md`).
- Code style is 2-space indentation in `app.py` and `cli.py`, and 4-space in `db.py` and the tests.

## Tests

`testing/pytest/conftest.py` starts a real server subprocess for each test module. It uses a temp SQLite file (left missing on purpose so auto-init gets exercised) and a temp datastore. It runs without `--noauth` and seeds users directly through sqlite3, then logs them in with tokens. The `provider_setup` fixture creates a local git repo to act as a service. Fixtures use uuid-suffixed names because the DB is shared across a whole module. OAuth is not covered by the tests. `testing/example_service/` and `testing/tutorial_service/` hold sample provider scripts written in bash (they use `itksnap-wt`). The docker-compose service container uses them.
