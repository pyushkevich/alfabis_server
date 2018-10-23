# Start with an image that includes ITK-SNAP command-line tools
FROM pyushkevich/itksnap:v3.8.0-beta

# Standard stuff
RUN apt-get update
RUN apt-get install -y git-core curl

# Working directory
WORKDIR /service

# Install the neck cutting script and service script
COPY testing/example_service /service/

# Run the daemon, capturing output
CMD ["bash","-c","/service/dss_daemon.sh $DSS_URL $DSS_SERVICE_HASH > >(tee -a dss_out.log) 2> >(tee -a dss_err.log >&2)"]
