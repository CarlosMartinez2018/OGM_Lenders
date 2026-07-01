"""
Smoke test: the FastAPI app imports cleanly and wires the new routes.

Guards against import-time regressions in routes.py (e.g. a bad import or a
mis-declared endpoint) that unit tests on individual modules would not catch.
Skipped if FastAPI isn't installed (it is installed in CI via requirements).
"""
import pytest

pytest.importorskip("fastapi")


def test_app_imports_and_registers_waiver_pack_route():
    from app.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/v1/classifications/{classification_id}/waiver-pack" in paths
