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

create type ticket_status as enum ('init','ready','working','success','error','timeout');

create table tickets
(
  id serial PRIMARY KEY,
  user_id int references users(id),
  service_id int references services(id),
  status ticket_status
);


