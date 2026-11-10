/* Sessions (0.3.1): atime holds Unix epoch seconds, like every other time in
   the schema (0.3.0 wrote datetime text, e.g. '2026-11-10 17:12:26.123456',
   in the server's local time zone, normally UTC). The new loggedin column lets
   the server purge anonymous sessions after a day; null values are filled in
   by the server when it starts. */
update sessions set atime = cast(strftime('%s', atime) as integer)
  where typeof(atime) = 'text';
alter table sessions add column loggedin integer default null;
create index if not exists sessions_atime_idx on sessions (atime);
