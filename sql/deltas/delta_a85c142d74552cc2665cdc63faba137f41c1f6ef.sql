/* This view presents the duration of each successful ticket */
create or replace view success_ticket_duration as 
  select T.service_githash, T1.ticket_id, T1.atime as endtime, T1.atime - max(T2.atime) as runtime 
  from ticket_history T1, ticket_history T2, tickets T where T1.status='success' 
       and T1.ticket_id = T2.ticket_id and T2.status='claimed' and T.id = T1.ticket_id
  group by T.service_githash, T1.ticket_id, T1.atime order by T1.ticket_id;

/* Add pingtime to services */
ALTER TABLE services ADD COLUMN pingtime timestamp not null default current_timestamp;
