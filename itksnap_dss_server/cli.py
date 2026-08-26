"""
Command-line entry point for the itksnap-dss-server (console script
`itksnap-dss-server`, and `python -m itksnap_dss_server`).
"""
import argparse
import sys


_ADMIN_COMMANDS = ("set-sysadmin", "unset-sysadmin")


def _build_admin_parser():
  parser = argparse.ArgumentParser(prog="itksnap-dss-server")
  subparsers = parser.add_subparsers(dest="command", required=True)

  set_sysadmin = subparsers.add_parser(
    "set-sysadmin", help="Grant sysadmin privileges to an existing user, by email")
  set_sysadmin.add_argument("email")

  unset_sysadmin = subparsers.add_parser(
    "unset-sysadmin", help="Revoke sysadmin privileges from an existing user, by email")
  unset_sysadmin.add_argument("email")

  return parser


def main():
  argv = sys.argv[1:]

  # sys.argv[1] alone decides whether this is an admin subcommand. The rest
  # of argv is only handed to _build_admin_parser() once that's settled --
  # itksnap_dss_server.app has its own independent argparse parser over this
  # same sys.argv (parse_known_args(), so it can coexist with uWSGI's own
  # flags), and two argparse parsers scanning the same argv independently
  # isn't safe: parse_known_args() here would see e.g. `--port 8080` as an
  # unrecognized flag, not know it takes a value, and misparse the bare
  # "8080" as this parser's positional subcommand instead.
  if argv and argv[0] in _ADMIN_COMMANDS:
    admin_pargs = _build_admin_parser().parse_args(argv)
    return _admin_command(admin_pargs.command, admin_pargs.email)

  # Importing itksnap_dss_server.app runs its module-level setup (its own
  # argparse parsing, DB connect/auto-init, route table, session setup) --
  # this is also exactly what a WSGI server relies on via
  # `itksnap_dss_server.app:application`, so this wrapper must not
  # duplicate or shadow that parsing, only trigger it.
  from itksnap_dss_server import app as dss_app
  dss_app.main_server()


def _admin_command(command, email):
  # Sysadmin status can otherwise only be granted by an existing sysadmin
  # through the web UI, which is a bootstrapping problem for the very first
  # admin on a new deployment -- hence this CLI escape hatch. Importing
  # itksnap_dss_server.app connects to the database using the same
  # --sqlite-path/ALFABIS_SQLITE_PATH resolution the server itself uses, so
  # this always operates on whichever database the running server is using.
  from itksnap_dss_server import app as dss_app

  flag = command == "set-sysadmin"
  n = dss_app.db.update("users", where="email=$email", sysadmin=flag, vars={"email": email})
  if not n:
    sys.exit("itksnap-dss-server: no user with email '%s' (they must log in at least "
              "once before their account can be made a sysadmin)" % email)
  print("%s: sysadmin=%s" % (email, flag))
