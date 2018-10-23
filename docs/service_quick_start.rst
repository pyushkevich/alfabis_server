Service Developer's Quick Start Guide
=====================================

This quick start guide walks you through creating a new service from scratch. We will first create a local DSS installation using Docker, and then create our own segmentation service.

Prerequisites:
-----
* [ITK-SNAP](itksnap.org) 3.8 or later
* [Docker](www.docker.com)
* Familiarity with Bash scripting 

DSS Architecture Overview
-----
DSS architecture consists of three layers:

.. image:: images/dss_arch.png

**client**
  A GUI or command-line tool that communicates with DSS over the web. Existing DSS clients are the ITK-SNAP GUI (after version 3.8) and the command-line tool **itksnap-wt** which is bundled with ITK-SNAP.
  
**middleware**
  The middleware layer is a web application written in Python that orchestrates communication between multiple service providers and multiple clients. The main *production* DSS middleware is running at https://dss.itksnap.org. However, users can also run their own local copies of the middleware layer, e.g., for testing. 
  
**service**
  Algorithm developers provide their tools as DSS services. For example, an algorithm for segmenting hippocampal subfields, called ASHS, is currently provided as a service at https://dss.itksnap.org. This means that any ITK-SNAP user can take advantage of this service to perform hippocampal subfield segmentation on their MRI data. Services communicate with the DSS middleware layer using **itksnap-wt**.
  
This tutorial describes how to create your own service and hook it up to DSS.

Running DSS locally
-----
The first step to creating your own DSS service is to launch a local DSS middleware layer. This will make it possible to test your service. 

Clone the DSS middlware Git repository::

    git clone https://github.com/pyushkevich/alfabis_server
    cd alfabis_server
    
The following command will create three Docker containers, one containing the SQL database for the middleware layer, another running the middleware web application, and the third running an example DSS service (a simple algorithm that crops out the neck in 3D MRI scans).::

    docker-compose up

After running the command, you will see a lot of output in the terminal, colored by the container producing this output. To test if the container is working, connect to it using the web browser, using the URL <http://localhost:8080>

.. note:: Port 8080 must be available on your host machine. If it is not, edit the file *docker-compose.yml* and change the first number under **ports** to the number of the port that is available to you. 

