create table ticket_history
(
  id serial primary key,
  ticket_id int references tickets(id),
  status ticket_status,
  atime timestamp not null default current_timestamp
);

alter table tickets drop constraint tickets_service_githash_fkey;
