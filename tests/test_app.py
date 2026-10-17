"""Local-workspace boundaries and explicit import/activation, without fitting."""
from contextlib import contextmanager
import http.client
import json
import threading

import pytest

from priorityx.app import WorkspaceServer, build_html
from priorityx.results import ResultBundle, ResultValidationError, strict_json_loads
from test_views import bundle


@contextmanager
def server():
    workspace = WorkspaceServer()
    thread = threading.Thread(target=workspace.serve_forever, daemon=True)
    thread.start()
    try:
        yield workspace
    finally:
        workspace.shutdown()
        workspace.server_close()
        thread.join(timeout=2)


def request(workspace, method, path, payload=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", workspace.server_port, timeout=10)
    body = json.dumps(payload) if payload is not None else None
    conn.request(method, path, body=body, headers={"Content-Type": "application/json", **(headers or {})})
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    conn.close()
    return result


def test_strict_json_rejects_duplicate_keys_and_nonfinite_values():
    for raw in ('{"datasets":[],"datasets":[]}', '{"x":NaN}', '{"x":Infinity}'):
        with pytest.raises(ResultValidationError):
            strict_json_loads(raw)


def test_offline_html_has_safe_embedded_source_and_no_template_tokens():
    source = bundle()
    source.datasets[0].type_label = "</script><script>alert(1)</script>"
    html = build_html(source)
    assert "__LIBRARY__" not in html and "__DATA__" not in html
    assert "\\u003c/script>\\u003cscript>alert(1)\\u003c/script>" in html
    assert 'id="workspace-data"' in html
    assert "plotly" in html.lower()


def test_workspace_activation_reload_and_cross_origin_boundaries():
    source = bundle()
    with server() as workspace:
        code, _, body = request(workspace, "GET", "/api/bootstrap")
        assert code == 200 and json.loads(body)["bundle"]["datasets"] == []
        code, _, body = request(workspace, "POST", "/api/prepare", {"bundle": source.to_dict(), "activate": True})
        assert code == 200 and json.loads(body)["prepared"]["datasets"][0]["typeLabel"] == "Work units"
        assert json.loads(request(workspace, "GET", "/api/bootstrap")[2])["bundle"] == source.to_dict()
        code, _, _ = request(workspace, "POST", "/api/prepare", {"bundle": ResultBundle().to_dict()}, {"Origin": "https://example.invalid"})
        assert code == 403
        assert request(workspace, "GET", "/api/bootstrap", headers={"Host": "example.invalid"})[0] == 403
        assert request(workspace, "GET", "/../pyproject.toml")[0] == 404
        assert request(workspace, "POST", "/api/prepare", {"bundle_json": '{"datasets":[],"datasets":[]}'})[0] == 400


def test_csv_import_requires_explicit_roles_and_validates_exact_data():
    source = bundle().datasets[0]
    payload = {"entity_type": "item", "type_label": "Work units", "cadence": "quarterly", "source_id": "source",
               "coverage_start": source.coverage_start, "as_of": source.as_of,
               "files": {role: {"name": f"{role}.csv", "text": getattr(source, role).to_csv(index=False)}
                         for role in ("matrix", "movement", "transitions")}}
    with server() as workspace:
        status, _, body = request(workspace, "POST", "/api/import", payload)
        assert status == 200
        imported = json.loads(body)
        assert imported["prepared"]["datasets"][0]["matrix"][0]["entity"] == "001"
        assert imported["bundle"]["datasets"][0]["source_files"]["matrix"] == "matrix.csv"
        payload["files"]["unknown"] = payload["files"]["matrix"]
        assert request(workspace, "POST", "/api/import", payload)[0] == 400
        del payload["files"]["unknown"]
        payload["files"]["matrix"]["text"] = "entity,x_score,x_score,y_score,count,quadrant\n001,1,2,3,3,Q1\n"
        assert request(workspace, "POST", "/api/import", payload)[0] == 400
        payload["files"]["matrix"]["text"] = source.matrix.to_csv(index=False).replace("1.0", "Infinity")
        assert request(workspace, "POST", "/api/import", payload)[0] == 400


def test_static_endpoint_rejects_stale_settings_and_returns_source_bound_report():
    from priorityx.views import prepare_bundle, resolve_settings
    source = bundle()
    settings = resolve_settings(None, prepare_bundle(source)).to_dict()
    payload = {"bundle": source.to_dict(), "settings": settings, "family": "matrix", "format": "png"}
    with server() as workspace:
        status, headers, image = request(workspace, "POST", "/api/static", payload)
        assert status == 200 and image.startswith(b"\x89PNG")
        report = json.loads(headers["X-PriorityX-Layout"])
        assert report["bundle_id"] == settings["bundle_id"]
        assert report["renderer"] == "matplotlib"
        import io
        from PIL import Image
        with Image.open(io.BytesIO(image)) as saved:
            assert json.loads(saved.info["Description"]) == report
        payload["settings"] = {**settings, "bundle_id": "stale"}
        assert request(workspace, "POST", "/api/static", payload)[0] == 400
