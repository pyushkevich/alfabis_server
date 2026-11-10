# Migrating a legacy DSS server (PostgreSQL) to itksnap-dss-server

The original DSS server (Python 2, PostgreSQL, run from a git checkout under
uWSGI) and itksnap-dss-server >= 0.3.0 (Python 3, SQLite) have the same
tables and the same datastore layout. Migrating means:

1. exporting the database with `export_postgres.sh` (on the old server);
2. importing it into a new SQLite database with `import_sqlite.py` (anywhere
   itksnap-dss-server is installed);
3. copying the old `datastore/` directory as it is to the new `--datastore-root`.

Users, providers, services, tickets with their logs, attachments and history,
and sessions from the last year are carried over, so ITK-SNAP users,
`itksnap-wt` and provider daemons stay logged in. Ticket ids continue where the
old server left off. Both servers use the same session secret and cookie name.

## Rehearsal (old server keeps running)

```bash
# On the old server
PGPASSWORD=... ./export_postgres.sh /tmp/dss_export -h localhost -U <user> -d alfabis
tar czf /tmp/dss_export.tgz -C /tmp dss_export

# On the new server
python import_sqlite.py dss_export /srv/dss/alfabis.sqlite3
rsync -a old-server:/path/to/alfabis_nginx/datastore/ /srv/dss/datastore/
itksnap-dss-server --server --sqlite-path /srv/dss/alfabis.sqlite3 --datastore-root /srv/dss/datastore
```

The import prints row counts (compare with the export's), any foreign-key
problems in the old data, and sessions it could not convert. Those users just
log in again.

## Copying fewer files

Finished tickets keep their files until the user deletes them, so most of an
old datastore can belong to tickets nobody will open again. To carry over only
recent ones:

```bash
python import_sqlite.py dss_export new.sqlite3 --retire-days 7 --keep-list keep.txt
```

Finished tickets with no activity in the last 7 days are marked deleted (with
a log message). Open tickets are kept whatever their age. `keep.txt` lists the
remaining ticket ids, so on the old server only these need copying:

```bash
cd datastore
{ echo services; while read d; do for a in tickets attachments; do
    [ -d $a/$d ] && echo $a/$d; done; done < keep.txt; } > keep_paths.txt
tar cf - -T keep_paths.txt | ssh new-server 'tar xf - -C /srv/dss/datastore'
```

## Sessions

web.py creates a session for every request without a cookie, so most sessions
are anonymous. By default the export keeps only logged-in ones (`SESSIONS=loggedin`),
which means decoding every row: slow on a large table, but it can run while the
old server is still up. At cut-over, `SESSIONS_SINCE` then adds just the
sessions used since that export (fast with an index on `sessions(atime)`).
Save it as `sessions_recent.jsonl` next to `sessions.jsonl`: the import merges
all `sessions*.jsonl` files.

## Cut-over

1. Stop the old app (`systemctl stop alfabis_uwsgi`). Clients get errors from
   here on, and retry.
2. Export again, and copy the datastore again (with rsync, or with the
   tar pipe above for just the files changed since the rehearsal).
3. Import into a fresh SQLite file (`import_sqlite.py` refuses to overwrite).
4. Start the new server, and move the DNS name or static IP to it.
5. Keep the old server stopped but intact until the new one has run for a while.
