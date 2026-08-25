# Use official Python as parent image
FROM python:3.9-slim

LABEL version="3.8.0"
LABEL maintainer="pyushkevich@gmail.com"
LABEL description="ITK-SNAP docker container"

# Make sure we have git
RUN apt-get update
RUN apt-get install -y curl

# Create workdir
WORKDIR /app

# Download ITK-SNAP experimental
ADD https://sourceforge.net/projects/itk-snap/files/itk-snap/Experimental/itksnap-experimental-master-Linux-gcc64-qt4.tar.gz/download /usr/local/itksnap.tar.gz
# ADD https://sourceforge.net/projects/itk-snap/files/itk-snap/3.8.0/itksnap-3.8.0-20190612-Linux-x86_64-qt4.tar.gz/download /usr/local/itksnap.tar.gz

# Unpack ITK-SNAP experimental into the local directory
RUN cd /usr/local \
  && tar -xzvf itksnap.tar.gz \
  && rm itksnap.tar.gz \
  && ln -s /usr/local/itksnap-*-Linux-gcc64-qt4/bin/* /usr/local/bin/ \
  && ln -s /usr/local/itksnap-*-Linux-gcc64-qt4/lib/* /usr/local/lib/ \
