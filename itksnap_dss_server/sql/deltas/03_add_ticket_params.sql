/* Job parameters: a JSON object of values for the 'parameters' declared in the
   service's service.json. Null means no parameters have been set. */
alter table tickets add column params text default null;
