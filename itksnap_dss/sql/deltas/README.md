# Schema deltas

`itksnap_dss/sql/init_db_sqlite.sql` is the schema for a fresh install — it's
always kept up to date and includes everything, so a brand-new database
never needs any of the files in this directory.

This directory is for incremental changes to that schema over time, one file
per change, following the convention used by the PHAS project
(`~/tk/histoannot/histoannot/phas/sql/deltas/`):

- Numbered in the order they were introduced: `01_description.sql`,
  `02_description.sql`, ...
- A short, descriptive name after the number (e.g.
  `03_add_ticket_priority.sql`), not a git commit hash.
- Applied by hand against a running deployment when upgrading it (e.g.
  `sqlite3 /path/to/db.sqlite3 < itksnap_dss/sql/deltas/03_add_ticket_priority.sql`)
  — there is no automated migration runner, matching PHAS's own practice.
- Also fold the same change into `init_db_sqlite.sql`, so a fresh install
  never needs to replay the delta history.
