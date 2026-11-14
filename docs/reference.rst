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
  ``optional`` A list of parameters (options) that the user can set when running your service. See below.

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

Parameters Directive
--------------------

The parameters directive lists the options that the user can set for a ticket, such as which atlas to use or whether to perform an optional step. Clients such as ITK-SNAP show each parameter as a field in a form. The values the user chooses are stored with the ticket, and your service reads them after claiming the ticket. An example parameters section looks like this

.. code-block:: json

    {
      "parameters": [
        {
          "name": "corr_mode",
          "displayname": "Correction Mode",
          "hint": "Error correction to apply after segmentation.",
          "type": "choice",
          "default": "shape",
          "choices": [
            { "name": "none", "displayname": "No error correction" },
            { "name": "shape", "displayname": "Shape correction" },
            { "name": "intensity", "displayname": "Intensity correction" }
          ]
        },
        { "name": "flip", "displayname": "Flip left and right", "type": "boolean", "default": false },
        { "name": "atlas_url", "displayname": "Custom atlas URL", "type": "string", "required": false },
        { "name": "iterations", "displayname": "Iterations", "type": "integer", "default": 100, "min": 1, "max": 1000 }
      ]
    }

**name**
  The unique name of the parameter. It must start with a letter or an underscore and may contain only letters, digits and underscores.

**type**
  One of ``string``, ``integer``, ``number`` (any real number), ``boolean`` or ``choice`` (one of a list of options). The older name ``choose_one`` is accepted as a synonym of ``choice``.

**displayname**
  ``optional`` The label shown to the user.

**hint**
  ``optional`` A longer explanation shown to the user.

**default**
  ``optional`` The value used if the user does not set the parameter. It must be a valid value for the parameter.

**required**
  ``optional`` Whether the user must set the parameter before submitting the ticket. A parameter that has no ``default`` is required unless ``required`` is ``false``. A parameter that is not required and has no default is left out of the values passed to your service if the user does not set it.

**min**, **max**
  ``optional`` Smallest and largest allowed value of an ``integer`` or ``number`` parameter.

**choices**
  The options of a ``choice`` parameter, each with a ``name`` (the value passed to your service) and an optional ``displayname`` (shown to the user).

The server checks the parameters directive when the service is registered and rejects a ``service.json`` that has an invalid one.

Setting and reading parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The client sets the values while the ticket is in the ``init`` state, by sending a ``POST`` request to ``/api/tickets/<ticket_id>/params``, either as a JSON object (``Content-Type: application/json``), or as form fields. The request can be sent any number of times. Each request adds to or replaces the values sent before it, and a JSON ``null`` removes a value. Each value is checked against its declaration, and a request with an unknown parameter or an invalid value is rejected (HTTP 400) and changes nothing. When the ticket is submitted (its status set to ``ready``), the server fills in the defaults of the parameters that have not been set, and rejects the request if a required parameter has not been set. After that, the values can no longer be changed.

After claiming the ticket, your service reads the values as a JSON object by sending a ``GET`` request to ``/api/pro/tickets/<ticket_id>/params``, for example ``{"corr_mode": "shape", "flip": false, "iterations": 100}``.


DSS REST API
============
This section describes the RESTful API for the DSS middleware server.

/api/login
----------
GET: Check login status

POST: Login

token:
    40-character login token (from https://$URL/token)
    

/api/oauth2cb
-------------
OAuthCallbackAPI

/api/token
----------
TokenAPI

/api/services
-------------
ServicesAPI

/api/services/([a-f0-9]+)/detail
--------------------------------
ServicesDetailAPI

/api/services/([a-f0-9]+)/stats
-------------------------------
ServicesStatsAPI

/api/tickets
------------
TicketsAPI

/api/tickets/(\d+)/files/(input|results)
----------------------------------------
TicketFilesAPI

/api/tickets/(\d+)/files/(input|results)/(\d+)
----------------------------------------------
TicketFileDownloadAPI

/api/tickets/(\d+)/status
-------------------------
TicketStatusAPI

/api/tickets/(\d+)/log
----------------------
TicketLogAPI

/api/tickets/(\d+)/progress
---------------------------
TicketProgressAPI

/api/tickets/(\d+)/queuepos
---------------------------
TicketQueuePositionAPI

/api/tickets/(\d+)/detail
-------------------------
TicketDetailAPI

/api/tickets/(\d+)/delete
-------------------------
TicketDeleteAPI

/api/tickets/(\d+)/retry
------------------------
TicketRetryAPI

/api/tickets/(\d+)/params
-------------------------
GET: Get the job parameters of the ticket as a JSON object

POST: Set some or all of the job parameters, as a JSON object or form fields (ticket must be in ``init`` state). See :ref:`refman_service_json`.

/api/tickets/logs/(\d+)/attachments
-----------------------------------
TicketLogAttachmentAPI

/api/pro/services
-----------------
ProviderServicesAPI

/api/pro/services/([a-f0-9]+)/claims
------------------------------------
ProviderServiceClaimsAPI

/api/pro/services/claims
------------------------
ProviderMultipleServiceClaimsAPI

/api/pro/services/available
---------------------------
ProviderMultipleServiceAvailableAPI

/api/pro/tickets/(\d+)/files/(input|results)
--------------------------------------------
ProviderTicketFilesAPI

/api/pro/tickets/(\d+)/files/(input|results)/(\d+)
--------------------------------------------------
ProviderTicketFileDownloadAPI

/api/pro/tickets/(\d+)/claim
----------------------------
ProviderTicketClaimAPI

/api/pro/tickets/(\d+)/status
-----------------------------
ProviderTicketStatusAPI

/api/pro/tickets/(\d+)/(error|warning|info|log)
-----------------------------------------------
ProviderTicketLogAPI

/api/pro/tickets/(\d+)/attachments
----------------------------------
ProviderTicketAttachmentAPI

/api/pro/tickets/(\d+)/progress
-------------------------------
ProviderTicketProgressAPI

/api/pro/tickets/(\d+)/params
-----------------------------
GET: Get the job parameters of a claimed ticket as a JSON object, with defaults filled in

/api/admin/providers
--------------------
AdminProvidersAPI

/api/admin/providers/([\w\-]+)/delete
-------------------------------------
AdminProviderDeleteAPI"

/api/admin/providers/([\w\-]+)/users
------------------------------------
AdminProviderUsersAPI"

/api/admin/providers/([\w\-]+)/users/(\d+)/delete
-------------------------------------------------
AdminProviderUsersDeleteAPI"

/api/admin/providers/([\w\-]+)/services
---------------------------------------
AdminProviderServicesAPI"

/api/admin/providers/([\w\-]+)/services/([a-f0-9]+)/delete
----------------------------------------------------------
AdminProviderServicesDeleteAPI"

/api/admin/tickets/purge/(completed|all)
----------------------------------------
AdminPurgeTicketsAPI"

/api/admin/tickets
------------------
AdminTicketsAPI"

/blobs/([a-f0-9]{8})
--------------------
DirectDownloadAPI

/blobs/([a-f0-9]{32})
---------------------
DirectDownloadAPI

/static/(.*)
------------
StaticFileAPI: serves the server's bundled CSS/JS/image assets (used by the HTML pages above). No authentication required.


Command-Line Administration
============================
The middleware server also exposes a small set of administrative commands through the ``itksnap-dss-server`` console script, for tasks that can't go through the web UI.

``itksnap-dss-server set-sysadmin <email>``
--------------------------------------------
Grants sysadmin privileges to an existing user, identified by the email address they logged in with. Sysadmin status is otherwise only grantable by an *existing* sysadmin through the ``/admin`` web pages, which makes bootstrapping the very first sysadmin on a new deployment impossible through the UI alone -- this command is that bootstrap path. The user must have logged in at least once (so their row exists in the database) before this command can find them; if not, it exits with an error rather than silently doing nothing.

This command operates on the same SQLite database the running server uses, resolved the same way as the server itself (``--sqlite-path`` / ``ALFABIS_SQLITE_PATH``), so it's safe to run directly against a live deployment.

``itksnap-dss-server unset-sysadmin <email>``
-----------------------------------------------
Revokes sysadmin privileges from a user.

