/* Temporary claims: a claim with a non-null expiration (Unix epoch seconds)
   lapses at that time, returning the ticket to 'ready'. Null = permanent claim. */
alter table claim_history add column expires integer default null;
