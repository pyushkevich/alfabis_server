/*
 * SQLite schema for alfabis (ITK-SNAP DSS server).
 *
 * This is a consolidated translation of init_db_users.sql + init_db.sql, which
 * already contain everything from sql/deltas/*.sql folded in (the deltas were
 * historical, hand-applied patches to a live production DB; init_db.sql and
 * init_db_users.sql already reflect the final schema state, so the deltas are
 * not translated separately here).
 *
 * Notable translations from the Postgres schema:
 *   - `serial primary key` -> `integer primary key autoincrement` (autoincrement,
 *     not bare rowid aliasing, since ids are exposed externally over the API and
 *     row-id reuse after deletion would be a correctness hazard).
 *   - Postgres `ENUM` types (ticket_status, log_category) -> `text` columns with
 *     a `check (... in (...))` constraint.
 *   - All `timestamp` columns -> `integer` columns storing Unix epoch seconds
 *     (`strftime('%s','now')`), not text timestamps. This keeps every
 *     "now() - x < interval" comparison in app.py as plain integer arithmetic,
 *     and makes the success_ticket_duration view's duration computation a
 *     trivial subtraction yielding whole seconds.
 *
 * Foreign key enforcement is OFF by default per SQLite connection; app.py should
 * issue `PRAGMA foreign_keys = ON` after connecting.
 */

drop table if exists sessions;
create table sessions (
  session_id text not null unique,
  atime integer not null default (strftime('%s','now')),
  data text
);

drop table if exists user_tiers;
create table user_tiers
(
  tier text primary key,
  max_tickets integer not null,
  priority_minutes integer not null
);

insert into user_tiers values ('guest', 10, 30);
insert into user_tiers values ('poweruser', 60, 60);
insert into user_tiers values ('xnat', 100000, 600);

drop table if exists users;
create table users (
  id integer primary key autoincrement,
  email text not null unique,
  passwd text,
  dispname text not null,
  sysadmin boolean default 0,
  tier text default 'guest' references user_tiers(tier)
);

drop table if exists provider_access;
create table provider_access
(
  user_id integer references users(id),
  provider text not null,
  admin boolean default 0,
  primary key (user_id, provider)
);

drop table if exists services;
create table services
(
  name text not null,
  githash text not null primary key,
  version text not null,
  shortdesc text,
  json text,
  pingtime integer not null default (strftime('%s','now')),
  current boolean default 1
);

drop table if exists providers;
create table providers
(
  name text not null primary key,
  current boolean default 1
);

drop table if exists provider_services;
create table provider_services
(
  provider_name text not null references providers(name),
  service_githash text not null references services(githash),
  current boolean default 1,
  primary key (provider_name, service_githash)
);

drop table if exists tickets;
create table tickets
(
  id integer primary key autoincrement,
  user_id integer not null references users(id),
  service_githash text not null references services(githash),
  status text check (status in ('init','ready','claimed','success','failed','timeout','deleted'))
);

drop table if exists claim_history;
create table claim_history
(
  id integer primary key autoincrement,
  ticket_id integer references tickets(id),
  provider text,
  puser_id integer references users(id),
  provider_code text,
  atime integer not null default (strftime('%s','now'))
);

drop table if exists ticket_progress;
create table ticket_progress
(
  ticket_id integer references tickets(id),
  chunk_start real not null,
  chunk_end real not null,
  progress real not null default 0,
  primary key (ticket_id, chunk_start)
);

drop table if exists ticket_log;
create table ticket_log
(
  id integer primary key autoincrement,
  ticket_id integer references tickets(id),
  category text not null check (category in ('info','warning','error')),
  message text not null,
  atime integer not null default (strftime('%s','now'))
);

drop table if exists ticket_attachment;
create table ticket_attachment
(
  id integer primary key autoincrement,
  ticket_id integer references tickets(id),
  mime_type text,
  description text,
  uuid text not null
);

drop table if exists ticket_log_attachment;
create table ticket_log_attachment
(
  log_id integer references ticket_log(id),
  attachment_id integer references ticket_attachment(id),
  primary key (log_id, attachment_id)
);

drop table if exists ticket_history;
create table ticket_history
(
  id integer primary key autoincrement,
  ticket_id integer references tickets(id),
  status text check (status in ('init','ready','claimed','success','failed','timeout','deleted')),
  atime integer not null default (strftime('%s','now'))
);

/* This view presents the duration of each successful ticket, in whole seconds
   (atime columns are epoch-seconds integers, so the subtraction is direct) */
drop view if exists success_ticket_duration;
create view success_ticket_duration as
  select T.service_githash, T1.ticket_id, T1.atime as endtime, T1.atime - max(T2.atime) as runtime
  from ticket_history T1, ticket_history T2, tickets T where T1.status='success'
       and T1.ticket_id = T2.ticket_id and T2.status='claimed' and T.id = T1.ticket_id
  group by T.service_githash, T1.ticket_id, T1.atime order by T1.ticket_id;
