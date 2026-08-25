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

# Install the python dependencies
RUN pip install --trusted-host pypi.python.org -r /app/alfabis_server/requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run the server (SQLite -- no separate database service to wait for)
CMD ["python", "alfabis_server/app.py", "--server"]
