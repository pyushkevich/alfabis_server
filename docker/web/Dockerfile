# Use official Python as parent image
FROM python:3.12-slim

# Make sure we have git (needed at runtime for service registration, which
# git-clones a provider's repo)
RUN apt-get update
RUN apt-get install -y git-core curl

# Create workdir
WORKDIR /app

# Checkout the server
# RUN git clone -b sandbox https://github.com/pyushkevich/alfabis_server.git alfabis_server
COPY . /app/alfabis_server/

# itksnap_dss's default --datastore-root is a relative path, resolved against
# the process's CWD (by design -- it's runtime user data, not package data),
# so the process still needs to run from here.
WORKDIR /app/alfabis_server

# Install the package (and its pinned deps) from pyproject.toml. This also
# bundles sql/, templates/, static/ into the installed package, so the app
# no longer needs to run from any particular directory to find those.
RUN pip install --trusted-host pypi.python.org .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# No build-time DB bake step, and no ALFABIS_SQLITE_PATH override here --
# itksnap-dss's own default (datastore/alfabis.sqlite3, relative to the
# WORKDIR above) is used as-is, same as running it outside Docker. That
# directory is auto-created and the schema auto-initialized on first
# startup if the file doesn't exist yet (see itksnap_dss/db.py).
# docker-compose.yml bind-mounts the host's ./datastore onto it, so the
# database and uploaded ticket files land in a folder visible on the host
# instead of the container's ephemeral filesystem.

# Run the server (SQLite -- no separate database service to wait for)
CMD ["itksnap-dss", "--server"]
