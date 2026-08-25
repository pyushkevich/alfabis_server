# Install ITK-SNAP and command-line tools in a blank container
FROM python:3.12-slim

# Standard stuff, plus the GL/GLX runtime libraries itksnap-wt links against
# (it's a CLI tool, but still dynamically links Qt's GUI libraries, which
# python:3.12-slim doesn't ship by default)
RUN apt-get update
RUN apt-get install -y git-core curl libgl1 libopengl0

# Install ITK-SNAP and command-line tools
ADD https://sourceforge.net/projects/itk-snap/files/itk-snap/4.4.0/itksnap-4.4.0-20250909-Linux-x86_64.tar.gz/download /usr/local/itksnap.tar.gz

# Unpack ITK-SNAP experimental into the local directory
RUN cd /usr/local \
  && tar -xzvf itksnap.tar.gz \
  && rm itksnap.tar.gz \
  && ln -s /usr/local/itksnap-*-Linux-x86_64/bin/* /usr/local/bin/ \
  && ln -s /usr/local/itksnap-*-Linux-x86_64/lib/* /usr/local/lib/ 

# Working directory
WORKDIR /service

# Install the neck cutting script and service script
COPY testing/example_service /service/

# Run the daemon, capturing output
CMD ["bash","-c","/service/dss_daemon.sh $DSS_URL $DSS_SERVICE_HASH > >(tee -a dss_out.log) 2> >(tee -a dss_err.log >&2)"]
