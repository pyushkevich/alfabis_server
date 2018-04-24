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

insert into user_tiers values ('guest', 10, 30);
insert into user_tiers values ('poweruser', 60, 60);
insert into user_tiers values ('xnat', 100000, 600);

alter table users add column tier varchar(40) default 'guest' references user_tiers(tier);

/*
 * Reinstate the service - ticket foreign constraint
 */
delete from claim_history where ticket_id in (select id from tickets where service_githash not in (select githash from services));
delete from ticket_log_attachment where log_id in (select id from ticket_log where ticket_id in (select id from tickets where service_githash not in (select githash from services)));
delete from ticket_log where ticket_id in (select id from tickets where service_githash not in (select githash from services));
delete from ticket_progress where ticket_id in (select id from tickets where service_githash not in (select githash from services));
delete from ticket_attachment where ticket_id in (select id from tickets where service_githash not in (select githash from services));
delete from ticket_history where ticket_id in (select id from tickets where service_githash not in (select githash from services));
delete from tickets where service_githash not in (select githash from services);
alter table tickets add constraint tickets_svc_fk foreign key (service_githash) references services(githash);

/*
 * Add an active flag to service listings
 */
alter table services add column current boolean default true;
alter table provider_services add column current boolean default true;
alter table providers add column current boolean default true;

