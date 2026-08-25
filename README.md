ITK-SNAP Distributed Segmentation Service (DSS) Middleware Layer
==================================================================

This is the source code of the middleware layer for the ITK-SNAP distributed segmentation service (DSS). [ITK-SNAP](https://itksnap.org) is an interactive tool for segmentation of volumetric medical imaging datasets, like CT and MRI. DSS is a web-based application that allows scientists to make their advanced image processing algorithms available as services to ITK-SNAP users. The main "production" DSS service is running at [https://dss.itksnap.org](https://dss.itksnap.org).

**Full documentation, including quick-start guides for users and for service developers, is at [https://alfabis-server.readthedocs.io](https://alfabis-server.readthedocs.io).**

## What's in this repository

The middleware is a Python 3 web application (installable as the package **`itksnap-dss-server`**), using [web.py](https://webpy.org) and a local SQLite database — no separate database server needs to be installed or run.

A separate, standalone Python package, [**`itksnap-dss`**](https://github.com/pyushkevich/itksnap-dss-python), provides a client library for service-provider scripts that interact with a running DSS server (`DSSClient`) and a helper for editing ITK-SNAP workspace files (`WorkspaceWrapper`). See that repository if you're writing a service provider in Python rather than Bash/`itksnap-wt`.

## Running your own instance

**With pip**, from a checkout of this repo (not yet published to PyPI):

```bash
pip install .
```

then:

```bash
itksnap-dss-server --server
```

By default this creates and initializes a SQLite database under `./datastore/` on first run. See `itksnap-dss-server --help` for the available configuration flags (each has an `ALFABIS_*` environment variable equivalent, for container/systemd deployments).

**With Docker**, this repository includes a `docker-compose.yml` that runs the middleware alongside an example DSS service:

```bash
docker compose up
```

This is intended for testing services locally before submitting them for production — see the [service developer's quick-start guide](https://alfabis-server.readthedocs.io/en/latest/service_quick_start.html) for a full walkthrough.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
