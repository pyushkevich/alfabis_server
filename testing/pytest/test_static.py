"""
Static asset serving (itksnap_dss.app.StaticFileAPI). Templates reference
CSS/JS/images under /static/... . web.py's built-in dev server has its own
automatic /static/ file serving, but it's CWD-based and gets disabled in
favor of this route -- see the comment on StaticMiddleware in
itksnap_dss/app.py's main_server() for why.
"""
import requests


def test_static_css_served(server):
    r = requests.get(server.base_url + "/static/alfabis.css")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/css"
    assert len(r.content) > 0


def test_static_nested_path_served(server):
    r = requests.get(server.base_url + "/static/pure/pure-min.css")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/css"


def test_static_unknown_file_404s(server):
    r = requests.get(server.base_url + "/static/does-not-exist.css")
    assert r.status_code == 404


def test_static_path_traversal_blocked(server):
    r = requests.get(server.base_url + "/static/../../pyproject.toml")
    assert r.status_code in (400, 404)
