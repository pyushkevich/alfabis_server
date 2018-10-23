# Use official Python as parent image
FROM python:2.7-slim

LABEL version="3.8.0-beta"
LABEL maintainer="pyushkevich@gmail.com"
LABEL description="ITK-SNAP docker container"

# Make sure we have git
RUN apt-get update
RUN apt-get install -y curl

# Create workdir
WORKDIR /app

# Download ITK-SNAP experimental
ADD https://sourceforge.net/projects/itk-snap/files/itk-snap/Experimental/itksnap-experimental-master-Linux-gcc64.tar.gz/download /app/itksnap.tar.gz
RUN ls -l
# RUN curl -L https://sourceforge.net/projects/itk-snap/files/itk-snap/Experimental/itksnap-experimental-master-Linux-gcc64.tar.gz/download > itksnap.tar.gz

# Unpack ITK-SNAP experimental into the local directory
RUN tar -zxvf itksnap.tar.gz; rm itksnap.tar.gz
RUN cp -av itksnap-*-Linux-gcc64/bin/ /usr/local/
RUN rm -rf itksnap-*-Linux-gcc64
RUN rm -rf /usr/local/bin/itksnap
