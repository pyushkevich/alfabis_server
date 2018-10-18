# Use official Python as parent image
FROM python:2.7-slim

# Make sure we have git
RUN apt-get update
RUN apt-get install -y git-core curl

# Create workdir
WORKDIR /app

# Checkout the server 
# RUN git clone -b sandbox https://github.com/pyushkevich/alfabis_server.git alfabis_server
COPY . /app/alfabis_server/

# Install the python dependencies
RUN pip install --trusted-host pypi.python.org -r /app/alfabis_server/requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run server on port 80887650
CMD ["python", "alfabis_server/app.py --server"] 
