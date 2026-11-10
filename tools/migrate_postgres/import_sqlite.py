#!/usr/bin/env python3
"""Import the data exported by export_postgres.sh into a new SQLite database
for itksnap-dss-server >= 0.3.0.

    python import_sqlite.py <export_dir> <new.sqlite3>

The database must not exist yet; it is created from the package's schema.
Files under the old server's datastore/ directory are not touched by this
script: copy them as they are to the new server's --datastore-root (the
directory layout is unchanged).

Notes:
  - Sessions: the old server stored them as Python 2 pickles. Each one is
    re-pickled for Python 3, so logged-in users (ITK-SNAP, itksnap-wt and
    provider daemons) stay logged in. Their atime is stored as text in the
    format web.py's DBStore itself writes: web.py compares atime with a
    datetime when purging expired sessions, and in SQLite an integer atime
    would always compare as older, so integer times would be purged.
  - Ids are kept, and each table's autoincrement counter is set to the old
    Postgres sequence value, so ids of deleted rows are never reused.
  - Foreign keys are not enforced during the import; violations found in the
    old data are reported at the end (the old tickets table had no foreign key
    on service_githash, for example).
"""
import base64
import importlib.resources
import json
import os
import pickle
import sqlite3
import sys

# Insert order: parents before children
TABLES = ['user_tiers', 'users', 'providers', 'provider_access', 'services',
          'provider_services', 'tickets', 'claim_history', 'ticket_progress',
          'ticket_log', 'ticket_attachment', 'ticket_log_attachment',
          'ticket_history', 'sessions']


def read_jsonl(path):
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def convert_session(data: str) -> str:
    """Python 2 pickle (base64) -> Python 3 pickle (base64), as web.py encodes it."""
    raw = base64.decodebytes(data.encode())
    try:
        value = pickle.loads(raw, encoding='utf-8')
    except UnicodeDecodeError:
        value = pickle.loads(raw, encoding='latin1')
    return base64.encodebytes(pickle.dumps(value)).decode()


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    export_dir, db_path = argv
    if os.path.exists(db_path):
        print('%s already exists; refusing to overwrite it' % db_path)
        return 1

    schema = (importlib.resources.files('itksnap_dss_server') / 'sql' /
              'init_db_sqlite.sql').read_text()
    con = sqlite3.connect(db_path)
    con.executescript(schema)
    con.execute('pragma foreign_keys = off')
    # The schema seeds the default tiers; the old server's tiers replace them
    con.execute('delete from user_tiers')

    bad_sessions = 0
    for table in TABLES:
        if table == 'sessions':
            # sessions.jsonl, plus e.g. sessions_recent.jsonl from a later
            # SESSIONS_SINCE export; later files replace earlier rows
            rows = []
            for fn in sorted(f for f in os.listdir(export_dir)
                             if f.startswith('sessions') and f.endswith('.jsonl')):
                rows += read_jsonl(os.path.join(export_dir, fn))
            rows = list({r['session_id']: r for r in rows}.values())
        else:
            rows = list(read_jsonl(os.path.join(export_dir, table + '.jsonl')))
        if table == 'sessions':
            kept = []
            for r in rows:
                try:
                    r['data'] = convert_session(r['data'])
                    kept.append(r)
                except Exception as e:   # unreadable session: drop it, user logs in again
                    bad_sessions += 1
                    print('  dropping session %s...: %s' % (r['session_id'][:8], e))
            rows = kept
        if rows:
            cols = list(rows[0].keys())
            con.executemany(
                'insert into %s (%s) values (%s)' % (table, ', '.join(cols),
                                                     ', '.join('?' * len(cols))),
                [tuple(r[c] for c in cols) for r in rows])
        print('%-22s %8d rows' % (table, len(rows)))

    # Autoincrement counters continue from the old sequences
    for r in read_jsonl(os.path.join(export_dir, 'sequences.jsonl')):
        con.execute('delete from sqlite_sequence where name = ?', (r['name'],))
        con.execute('insert into sqlite_sequence (name, seq) values (?, ?)',
                    (r['name'], max(r['last_value'],
                                    con.execute('select coalesce(max(id), 0) from %s'
                                                % r['name']).fetchone()[0])))
    con.commit()

    problems = con.execute('pragma foreign_key_check').fetchall()
    if problems:
        print('\nForeign key violations in the old data (table, rowid, parent, fk):')
        summary = {}
        for table, rowid, parent, fk in problems:
            summary.setdefault((table, parent), []).append(rowid)
        for (table, parent), rowids in sorted(summary.items()):
            print('  %s -> %s: %d rows, e.g. rowids %s'
                  % (table, parent, len(rowids), rowids[:5]))
    if bad_sessions:
        print('\n%d sessions could not be converted and were dropped' % bad_sessions)
    print('\nIntegrity check:', con.execute('pragma integrity_check').fetchone()[0])
    con.close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
