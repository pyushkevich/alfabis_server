"""
Database connection setup for the itksnap-dss-server: opens the SQLite
connection, applies per-connection PRAGMAs, and auto-initializes the schema
from the bundled sql/init_db_sqlite.sql if the database file is missing or
not yet initialized (i.e. has no `users` table).
"""
import importlib.resources
import os
import sqlite3
import sys
import time

import web
import web.session


def _schema_sql():
    """Return the bundled schema SQL as text (package data, not a filesystem
    path -- works the same whether itksnap_dss_server was installed editable
    or as a real, non-editable wheel/sdist install)."""
    return (importlib.resources.files("itksnap_dss_server") / "sql" / "init_db_sqlite.sql").read_text()


def connect(sqlite_path):
    """Open (creating and initializing if necessary) the SQLite database at
    `sqlite_path`, apply the PRAGMAs web.py's per-thread connections need
    re-applied on every connect, and return a web.database() handle ready
    for use."""
    # sqlite3.connect() does not create parent directories -- so the default
    # path fails outright the first time the app is run somewhere that
    # doesn't already have a datastore/ directory.
    sqlite_dir = os.path.dirname(sqlite_path)
    if sqlite_dir:
        # exist_ok=True: multiple uWSGI/gunicorn workers can race this on
        # startup.
        os.makedirs(sqlite_dir, exist_ok=True)

    db = web.database(dbn="sqlite", db=sqlite_path, timeout=5.0)

    # Install the per-connection PRAGMA wrapper BEFORE issuing any queries,
    # so the very first connection (opened lazily below) gets it too. web.py
    # opens one connection per thread, with no pooling, via db._connect() --
    # `foreign_keys` is not persisted per-file (unlike journal_mode) and has
    # no native connect() kwarg, so it must be (re-)applied on every new
    # connection.
    orig_connect = db._connect

    def _connect_with_pragmas(keywords):
        conn = orig_connect(keywords)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    db._connect = _connect_with_pragmas

    try:
        # Rollback journal mode (SQLite's own default) rather than WAL: WAL
        # needs proper shared-memory (mmap) + byte-range locking support
        # from the filesystem, which Docker Desktop's bind-mounted host
        # directories on macOS don't reliably provide. With WAL enabled,
        # this database's schema-existence check below would intermittently
        # see a stale/empty view of an already-initialized database over a
        # bind mount, re-running the (destructive -- DROP TABLE IF EXISTS)
        # init script on every container restart. Explicitly setting DELETE
        # here (not just relying on the compiled-in default) also converts
        # any database file that was already switched to WAL by an earlier
        # version of this code. DELETE mode is slower under heavy concurrent
        # access than WAL, but this app's actual concurrency (a handful of
        # provider daemons polling) doesn't come close to needing WAL.
        db.query("PRAGMA journal_mode = DELETE")
    except sqlite3.OperationalError as e:
        sys.exit(
            "itksnap-dss-server: could not open SQLite database at '%s': %s\n"
            "(Set ALFABIS_SQLITE_PATH to point at a writable database file.)"
            % (sqlite_path, e)
        )

    _ensure_schema(db, sqlite_path)

    return db


def _ensure_schema(db, sqlite_path):
    """Auto-initialize the schema if the `users` table doesn't exist yet --
    i.e. this is a brand-new/empty database file. Applies the bundled
    schema directly so the server can start against a freshly-created,
    empty file with no manual setup step."""
    has_users_table = db.query(
        "select count(*) as n from sqlite_master where type='table' and name='users'"
    )[0].n

    if has_users_table:
        return

    # flush=True: stdout is block-buffered (not line-buffered) when it isn't
    # a tty -- e.g. under Docker/uWSGI -- so without this the message can sit
    # unflushed in the buffer instead of showing up in container/service logs.
    print("itksnap-dss-server: initializing new SQLite database at '%s'" % sqlite_path, flush=True)
    # db.ctx.db is the current thread's already-open, PRAGMA-configured
    # connection (opened lazily by the PRAGMA journal_mode query above) --
    # reuse it rather than opening a second one, which needs web.py's
    # internal connection keywords to construct correctly.
    conn = db.ctx.db
    conn.executescript(_schema_sql())
    conn.commit()


class SessionStore(web.session.DBStore):
    """web.py's DBStore, adapted to this app's sessions table.

    - atime is stored as integer Unix epoch seconds, like every other time in
      the schema. web.py's DBStore writes a datetime (stored by SQLite as
      text) and purges with `$cutoff > atime`; in SQLite every integer sorts
      below every text value, so it would purge rows with integer times and
      never purge rows with text times.
    - web.py creates and saves a session for every request without a cookie
      (bots, health checks, first visits), so the table fills up with
      anonymous sessions. Each row records whether the session is logged in,
      and anonymous sessions are purged after `anonymous_timeout` seconds,
      checked at most once per `purge_interval` seconds.
    """

    anonymous_timeout = 86400
    purge_interval = 3600

    def __init__(self, db, table_name):
        super().__init__(db, table_name)
        self._last_purge = 0

    def __getitem__(self, key):
        rows = list(self.db.select(self.table, where="session_id=$key", vars=locals()))
        if not rows:
            raise KeyError(key)
        self.db.update(self.table, where="session_id=$key", atime=int(time.time()),
                       vars=locals())
        return self.decode(rows[0].data)

    def __setitem__(self, key, value):
        # encode() returns bytes; the column holds the base64 text
        pickled = self.encode(value).decode()
        now = int(time.time())
        loggedin = 1 if value.get("loggedin") else 0
        if key in self:
            self.db.update(self.table, where="session_id=$key", data=pickled,
                           atime=now, loggedin=loggedin, vars=locals())
        else:
            self.db.insert(self.table, False, session_id=key, atime=now,
                           data=pickled, loggedin=loggedin)
            self._purge_anonymous(now)

    def _purge_anonymous(self, now):
        if now - self._last_purge >= self.purge_interval:
            self._last_purge = now
            cutoff = now - self.anonymous_timeout
            self.db.delete(self.table, where="loggedin = 0 and atime < $cutoff",
                           vars=locals())

    def cleanup(self, timeout):
        """Called by web.py once per process: purge sessions unused for
        `timeout` seconds, and fill in the loggedin flag of rows written
        before it existed (see sql/deltas/02_session_epoch_and_loggedin.sql)."""
        for r in list(self.db.select(self.table, what="session_id, data",
                                     where="loggedin is null")):
            try:
                loggedin = 1 if self.decode(r.data).get("loggedin") else 0
            except Exception:
                loggedin = 0
            self.db.update(self.table, where="session_id=$sid", loggedin=loggedin,
                           vars={"sid": r.session_id})
        cutoff = int(time.time()) - int(timeout)
        self.db.delete(self.table, where="atime < $cutoff", vars=locals())
        self._purge_anonymous(int(time.time()))
