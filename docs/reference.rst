*****************************
ITK-SNAP DSS Reference Manual
*****************************

.. _refman_service_json:

service.json Files
==================

These files are used by ITK-SNAP and the middleware server web interface to describe the service to the user. They contain descriptive information such as the explanation of what the service does, as well as codify what kinds of input must be provided to the service.

See an example ``service.json`` file: `<https://github.com/pyushkevich/alfabis-svc-ashs-pmc/blob/master/service.json>`_

Top-Level Fields
----------------

**name**
  The official name of the service. May not contain spaces.

**version**
  The `semantic version <https://semver.org/>`_ of the service. The version refers to the iteration of the service itself, rather than to the version of the underlying tool that it is running. For example, you may have multple versions of a service that calls MyTool 2.0 (say version 1.0.0 of your service called MyTool with the wrong parameters, so you created version 1.0.1 to fix the parameters).

**shortdesc**
  The short description of the service. This is shown in the ITK-SNAP dropdown used to select services. Do not include the name and version of the service in the short description.

**longdesc**
  A paragraph describing the service in more detail. This is shown in ITK-SNAP in a small font once the service has been selected from a dropdown.

**citation**
  ``optional`` A URL pointing to the paper that you wish to be cited for your service. 

**url**
  ``optional`` A URL pointing a webpage describing your service

**author**
  ``optional,notused`` Name of the author

**keywords**
  ``optional,notused`` A list of keywords that can be used to help find the service.

**tags**
  A list of tags that point to various "objects" in the ITK-SNAP workspace that is passed to your service. See below.

**parameters**
  ``optional,notused`` A list of parameters that the user must provide for running your service. This has not yet been implemented.

Tags Directive
--------------

The tags directive includes a list of tags, each representing a separate object in the ITK-SNAP workspace. Currently, only image layers can be tagged, but in the near future, it will be possible to tag annotations (e.g., landmarks) and individual segmentation labels. An example tags section look like this

.. code-block:: json

    {
      "tags": [
        {
          "name": "T2-MRI",
          "type": "MainImage",
          "hint": "A high-resolution (e.g., 0.4x0.4x2.0mm^3) T2-weighted MRI scan with oblique coronal orientation parallel to hippocampal main axis. This scan must be the main image in the workspace.",
          "required": true
        },
        {
          "name": "T1-MRI",
          "type": "OverlayImage",
          "hint": "Roughtly isotropic (e.g., 1x1x1mm^3) T1-weighted MRI scan of the whole brain.",
          "required": true
        },
        {
          "name": "AC",
          "type": "PointLandmark",
          "hint": "Anterior commissure point can be optionally specified to help align the MRI scan to the brain template.",
          "required": false
        },
        {
          "name": "PC",
          "type": "PointLandmark",
          "hint": "Posterior commissure point can be optionally specified to help align the MRI scan to the brain template.",
          "required": false
        }
      ]
    }


**name**
  The unique name of the tag, which may not contain spaces.

**type**
  Describes the type of the ITK-SNAP object to which the tags refers. Currently implemented objects are ``MainImage``, ``AnatomicImage``, ``OverlayImage``, ``Segmentation``. In the future, we will implement ``Label`` and ``PointLandmark``.

**hint**
  A text string shown to the user when assigning tags to items in the ITK-SNAP workspace.

**required**
  A boolean indicating whether the tag must be assigned before the service can be executed


DSS REST API
============
This section describes the RESTful API for the DSS middleware server.

.. http:get::  /api/v2/project/



