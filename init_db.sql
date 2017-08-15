create table users (
  id serial PRIMARY KEY,
  email text not null unique,
  passwd text,
  dispname text not null
);

create table sessions (
  session_id char(128) unique not null,
  atime timestamp not null default current_timestamp,
  data text
);

create table services
(
  id SERIAL PRIMARY KEY,
  name varchar(40) not null unique,
  shortdesc varchar(78) not null,
  longdesc text
);

/* Create an example service */
insert into services (name,shortdesc) values ('ASHS-PMC','Hippocampal subfield segmentation in 3 Tesla T2w-MRI');

create type ticket_status as enum ('init','ready','claimed','success','failed','timeout');

create table tickets
(
  id serial PRIMARY KEY,
  user_id int references users(id),
  service_id int references services(id),
  status ticket_status
);

/* Which users are authorized to provide what services */
create table providers
(
  user_id int references users(id),
  service_id int references services(id),
  primary key (user_id, service_id)
);

/* History of ticket claims */
create table claim_history
(
  id serial primary key,
  ticket_id int references tickets(id),
  provider_id int references users(id),
  provider_code varchar(78),
  atime timestamp not null default current_timestamp
);

/* Progress for a ticket */
create table ticket_progress
(
  ticket_id int references tickets(id),
  chunk_start real not null,
  chunk_end real not null,
  progress real not null default 0,
  primary key (ticket_id, chunk_start)
);

/* Allowable categories of error messages */
create type log_category as enum ('info','warning','error');

/* Allowable log entry states */
create type log_state as enum ('open', 'closed');

/* Log messages for a ticket */
create table ticket_log
(
  id serial PRIMARY KEY,
  ticket_id int references tickets(id),
  category log_category not null,
  state log_state not null default 'closed',
  message text not null,
  attachments int not null default 0,
  atime timestamp not null default current_timestamp
);

/* Ticket attachments - images, dump files, etc. */
create table ticket_log_attachment
(
  id serial PRIMARY KEY,
  log_id int references ticket_log(id),
  mime_type text,
  description text,
  uuid text not null
);

