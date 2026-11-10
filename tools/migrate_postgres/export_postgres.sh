#!/bin/bash
# Export the data of a legacy (Python 2 / PostgreSQL) DSS server for import
# into itksnap-dss-server >= 0.3.1 (SQLite) with import_sqlite.py.
#
# Run on the old server, ideally with the app stopped so the export is
# consistent:
#   PGPASSWORD=... ./export_postgres.sh <outdir> [psql connection options]
# e.g.
#   PGPASSWORD=... ./export_postgres.sh /tmp/dss_export -h localhost -U <user> -d alfabis
#
# Writes one JSON-lines file per table (<table>.jsonl) plus sequences.jsonl.
# Values are converted to what the SQLite schema expects: timestamps become
# Unix epoch seconds, booleans 0/1, enums text, char(n) values are trimmed.
# Session times are exported as UTC text; import_sqlite.py converts them.
#
# Sessions: web.py creates one for every request without a cookie, so most
# are anonymous. Environment variables choose which ones to export:
#   SESSIONS=loggedin  (default) logged-in sessions only. Finding them decodes
#                      every row, which takes a while on a big table.
#            all       every session used within the last year
#            none      no sessions (export only sessions.jsonl to skip the rest)
#   SESSIONS_SINCE='2026-11-10 16:00'  only sessions used since then (UTC).
#                      With an index on sessions(atime) this is quick, e.g. to
#                      add the sessions active since an earlier full export.
#   TABLES='sessions'  export only these tables (default: all)
set -euo pipefail

if [[ $# -lt 1 ]]; then
  sed -n '2,15p' "$0"; exit 2
fi
OUT=$1; shift
mkdir -p "$OUT"

epoch() { echo "extract(epoch from $1)::bigint as $1"; }

declare -A Q
Q[user_tiers]="select tier, max_tickets, priority_minutes from user_tiers"
Q[users]="select id, email, passwd, dispname, sysadmin::int as sysadmin, tier from users"
Q[providers]="select name, current::int as current from providers"
Q[provider_access]="select user_id, provider, admin::int as admin from provider_access"
Q[services]="select name, rtrim(githash) as githash, version, shortdesc, json, $(epoch pingtime), current::int as current from services"
Q[provider_services]="select provider_name, rtrim(service_githash) as service_githash, current::int as current from provider_services"
Q[tickets]="select id, user_id, rtrim(service_githash) as service_githash, status::text as status from tickets"
Q[claim_history]="select id, ticket_id, provider, puser_id, provider_code, $(epoch atime) from claim_history"
Q[ticket_progress]="select ticket_id, chunk_start, chunk_end, progress from ticket_progress"
Q[ticket_log]="select id, ticket_id, category::text as category, message, $(epoch atime) from ticket_log"
Q[ticket_attachment]="select id, ticket_id, mime_type, description, uuid from ticket_attachment"
Q[ticket_log_attachment]="select log_id, attachment_id from ticket_log_attachment"
Q[ticket_history]="select id, ticket_id, status::text as status, $(epoch atime) from ticket_history"
SESS_WHERE="atime > now() - interval '1 year'"
if [[ -n "${SESSIONS_SINCE:-}" ]]; then
  SESS_WHERE="atime > '${SESSIONS_SINCE}'::timestamp"
fi
case "${SESSIONS:-loggedin}" in
  # web.py (Python 2) pickles the session dict with protocol 0, where a true
  # 'loggedin' value reads: S'loggedin' NL p<memo> NL I01
  loggedin) SESS_WHERE="$SESS_WHERE and convert_from(decode(data, 'base64'), 'LATIN1') ~ 'S''loggedin''\np[0-9]+\nI01'" ;;
  all) ;;
  none) SESS_WHERE="false" ;;
  *) echo "SESSIONS must be loggedin, all or none" >&2; exit 2 ;;
esac
Q[sessions]="select rtrim(session_id) as session_id, to_char(atime, 'YYYY-MM-DD HH24:MI:SS.US') as atime, data from sessions where $SESS_WHERE"
Q[sequences]="select 'users' as name, last_value from users_id_seq
  union all select 'tickets', last_value from tickets_id_seq
  union all select 'claim_history', last_value from claim_history_id_seq
  union all select 'ticket_log', last_value from ticket_log_id_seq
  union all select 'ticket_attachment', last_value from ticket_attachment_id_seq
  union all select 'ticket_history', last_value from ticket_history_id_seq"

for t in ${TABLES:-${!Q[@]}}; do
  # row_to_json escapes newlines, so each row is exactly one line
  psql "$@" -X -q -A -t -v ON_ERROR_STOP=1 \
    -c "set timezone to 'UTC'; select row_to_json(t) from (${Q[$t]}) t" > "$OUT/$t.jsonl"
  printf '%-22s %8d rows\n' "$t" "$(wc -l < "$OUT/$t.jsonl")"
done
