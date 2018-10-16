/*
 * Usage tiers - define priviliges of users globally 
 */
drop table if exists user_tiers;
create table user_tiers
(
  tier varchar(40) primary key,
  max_tickets int not null,
  priority_minutes int not null
);

/* Define some tiers */
insert into user_tiers values ('guest', 10, 30);
insert into user_tiers values ('poweruser', 60, 60);
insert into user_tiers values ('xnat', 100000, 600);

/* This is the users table */
drop table if exists users cascade;
create table users (
  id serial PRIMARY KEY,
  email text not null unique,
  passwd text,
  dispname text not null,
  sysadmin boolean default false,
  tier varchar(40) default 'guest' references user_tiers(tier)
);

/* 
 * The provider access table specifies access to providers by user. 
 * Since the provider table can be rebuilt programmatically, we do
 * not explicitly reference it (to avoid cascaded deletes) 
 */
drop table if exists provider_access cascade;
create table provider_access
(
  user_id int references users(id),
  provider varchar(78) not null,
  admin boolean default false,
  primary key (user_id, provider)
);
