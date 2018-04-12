/* This is the users table */
drop table if exists users cascade;
create table users (
  id serial PRIMARY KEY,
  email text not null unique,
  passwd text,
  dispname text not null,
  sysadmin boolean default false
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

