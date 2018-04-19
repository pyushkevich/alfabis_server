
drop table if exists sessions;
create table sessions (
  session_id char(128) unique not null,
  atime timestamp not null default current_timestamp,
  data text
);

drop table if exists services cascade;
create table services
(
  name varchar(40) not null,
  githash char(40) not null primary key,
  version varchar(40) not null,
  shortdesc varchar(78),
  json text,
  pingtime timestamp not null default current_timestamp
);

drop table if exists providers cascade;
create table providers
(
  name varchar(78) not null primary key
);

drop table if exists provider_services;
create table provider_services
(
  provider_name varchar(40) not null references providers(name),
  service_githash char(40) not null references services(githash),
  primary key (provider_name, service_githash)
);

/*
create table services
(
  id SERIAL PRIMARY KEY,
  name varchar(40) not null unique,
  shortdesc varchar(78) not null,
  longdesc text
);
*/

/* Create an example service */
/* insert into services (name,shortdesc) values ('ASHS-PMC','Hippocampal subfield segmentation in 3 Tesla T2w-MRI');
insert into services (name,shortdesc) values ('PICSL-HarP','Hippocampus segmentation with HarP protocol in 3 Tesla T1w-MRI'); */

drop type if exists ticket_status cascade;
create type ticket_status as enum ('init','ready','claimed','success','failed','timeout','deleted');

drop table if exists tickets cascade;
create table tickets
(
  id serial PRIMARY KEY,
  user_id int references users(id) not null,
  service_githash not null,
  status ticket_status
);


/* Which users are authorized to provide what services */
/*create table providers
(
  user_id int references users(id),
  service_id int references services(id),
  primary key (user_id, service_id)
);*/

/* 
 * Providers are labs/groups that provide a set of services. We 
 * do not use numerical ids for providers because this table is 
 * generated dynamically from Git from time to time and we don't
 * want to break user permissions
 */

/* History of ticket claims */
drop table if exists claim_history cascade;
create table claim_history
(
  id serial primary key,
  ticket_id int references tickets(id),
  provider varchar(78),
  puser_id int references users(id),
  provider_code varchar(78),
  atime timestamp not null default current_timestamp
);

/* Progress for a ticket */
drop table if exists ticket_progress cascade;
create table ticket_progress
(
  ticket_id int references tickets(id),
  chunk_start real not null,
  chunk_end real not null,
  progress real not null default 0,
  primary key (ticket_id, chunk_start)
);

/* Allowable categories of error messages */
drop type if exists log_category cascade;
create type log_category as enum ('info','warning','error');

/* Log messages for a ticket */
drop table if exists ticket_log cascade;
create table ticket_log
(
  id serial PRIMARY KEY,
  ticket_id int references tickets(id),
  category log_category not null,
  message text not null,
  atime timestamp not null default current_timestamp
);

/* Ticket attachments - images, dump files, etc. */
drop table if exists ticket_attachment cascade;
create table ticket_attachment
(
  id serial PRIMARY KEY,
  ticket_id int references tickets(id),
  mime_type text,
  description text,
  uuid text not null
);

drop table if exists ticket_log_attachment cascade;
create table ticket_log_attachment
(
  log_id int references ticket_log(id),
  attachment_id int references ticket_attachment(id),
  PRIMARY KEY (log_id, attachment_id)
);

drop table if exists ticket_history cascade;
create table ticket_history
(
  id serial primary key,
  ticket_id int references tickets(id),
  status ticket_status,
  atime timestamp not null default current_timestamp
);

/* This view presents the duration of each successful ticket */
create or replace view success_ticket_duration as 
  select T.service_githash, T1.ticket_id, T1.atime as endtime, T1.atime - max(T2.atime) as runtime 
  from ticket_history T1, ticket_history T2, tickets T where T1.status='success' 
       and T1.ticket_id = T2.ticket_id and T2.status='claimed' and T.id = T1.ticket_id 
  group by T.service_githash, T1.ticket_id, T1.atime order by T1.ticket_id;


