#!/usr/bin/env python3
"""Import the data exported by export_postgres.sh into a new SQLite database
for itksnap-dss-server >= 0.3.1.

    python import_sqlite.py <export_dir> <new.sqlite3>

The database must not exist yet; it is created from the package's schema.
Files under the old server's datastore/ directory are not touched by this
script: copy them as they are to the new server's --datastore-root (the
directory layout is unchanged).

Notes:
  - Sessions: the old server stored them as Python 2 pickles. Each one is
    re-pickled for Python 3, so logged-in users (ITK-SNAP, itksnap-wt and
    provider daemons) stay logged in. atime becomes epoch seconds and the
    loggedin column is set, as itksnap-dss-server >= 0.3.1 expects.
  - Ids are kept, and each table's autoincrement counter is set to the old
    Postgres sequence value, so ids of deleted rows are never reused.
  - Foreign keys are not enforced during the import; violations found in the
    old data are reported at the end (the old tickets table had no foreign key
    on service_githash, for example).
"""
import argparse
import base64
import calendar
import datetime
import importlib.resources
import json
import os
import pickle
import sqlite3
import sys
import time

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


def convert_session(row):
    """Convert an exported session row in place: the Python 2 pickle (base64)
    becomes a Python 3 pickle (base64), as web.py encodes it; atime (UTC text)
    becomes epoch seconds; loggedin is set from the session data."""
    raw = base64.decodebytes(row['data'].encode())
    try:
        value = pickle.loads(raw, encoding='utf-8')
    except UnicodeDecodeError:
        value = pickle.loads(raw, encoding='latin1')
    row['data'] = base64.encodebytes(pickle.dumps(value)).decode()
    row['atime'] = calendar.timegm(datetime.datetime.strptime(
        row['atime'].split('.')[0], '%Y-%m-%d %H:%M:%S').timetuple())
    row['loggedin'] = 1 if value.get('loggedin') else 0


def retire_old_tickets(con, days):
    """Mark finished tickets with no activity in the last `days` days as
    deleted, as the server does when a user deletes a ticket, so that tickets
    whose files are not carried over do not show up with missing results."""
    cutoff = int(time.time()) - days * 86400
    ids = [r[0] for r in con.execute(
        "select id from tickets T where status in ('success', 'failed', 'timeout') "
        "and coalesce((select max(atime) from ticket_history where ticket_id = T.id), 0) < ? "
        "and coalesce((select max(atime) from ticket_log where ticket_id = T.id), 0) < ?",
        (cutoff, cutoff))]
    for tid in ids:
        con.execute("update tickets set status = 'deleted' where id = ?", (tid,))
        con.execute("insert into ticket_history (ticket_id, status) values (?, 'deleted')", (tid,))
        con.execute("insert into ticket_log (ticket_id, category, message) values (?, 'info', ?)",
                    (tid, 'Ticket removed when DSS moved to a new server: no activity for '
                          'more than %d days' % days))
    con.commit()
    return ids


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('export_dir')
    p.add_argument('db_path')
    p.add_argument('--retire-days', type=int, metavar='N',
                   help='mark finished tickets with no activity in the last N days '
                        'as deleted (their files need not be copied)')
    p.add_argument('--keep-list', metavar='FILE',
                   help='write the ids (%%08d, as datastore directory names) of the '
                        'tickets that are not deleted, i.e. whose files to copy')
    a = p.parse_args(argv)
    export_dir, db_path = a.export_dir, a.db_path
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
                    convert_session(r)
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
    if a.retire_days is not None:
        retired = retire_old_tickets(con, a.retire_days)
        print('\nRetired %d finished tickets with no activity in the last %d days'
              % (len(retired), a.retire_days))
    if a.keep_list:
        keep = [r[0] for r in con.execute(
            "select id from tickets where status != 'deleted' order by id")]
        with open(a.keep_list, 'w') as f:
            f.writelines('%08d\n' % t for t in keep)
        print('%d tickets are not deleted; their ids are in %s' % (len(keep), a.keep_list))
    print('\nIntegrity check:', con.execute('pragma integrity_check').fetchone()[0])
    con.close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
