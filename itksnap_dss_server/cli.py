"""
Command-line entry point for the itksnap-dss-server (console script
`itksnap-dss-server`, and `python -m itksnap_dss_server`).
"""


def main():
  # Importing itksnap_dss_server.app runs its module-level setup (its own
  # argparse parsing, DB connect/auto-init, route table, session setup) --
  # this is also exactly what a WSGI server relies on via
  # `itksnap_dss_server.app:application`, so this wrapper must not
  # duplicate or shadow that parsing, only trigger it.
  from itksnap_dss_server import app as dss_app
  dss_app.main_server()
