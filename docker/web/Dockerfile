# Use official Python as parent image
FROM python:3.12-slim

# Make sure we have git and the sqlite3 CLI (used to initialize a fresh database file)
RUN apt-get update
RUN apt-get install -y git-core curl sqlite3

# Create workdir
WORKDIR /app

# Checkout the server
# RUN git clone -b sandbox https://github.com/pyushkevich/alfabis_server.git alfabis_server
COPY . /app/alfabis_server/

# app.py loads templates/static assets via relative paths (temp/, static/) and
# defaults its datastore/ directory to a relative path too, so the process
# needs to actually run from here -- not rely on docker-compose's
# working_dir: (which may be omitted or overridden by whoever runs this).
WORKDIR /app/alfabis_server

# Install the python dependencies
RUN pip install --trusted-host pypi.python.org -r /app/alfabis_server/requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Create a default database - user can always override
ENV ALFABIS_SQLITE_PATH=/app/data/alfabis.sqlite3
RUN mkdir -p /app/data && sqlite3 $ALFABIS_SQLITE_PATH < /app/alfabis_server/sql/init_db_sqlite.sql

# Run the server (SQLite -- no separate database service to wait for)
CMD ["python", "app.py", "--server"]
