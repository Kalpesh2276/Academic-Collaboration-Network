"""Shared fixtures.

Integration tests (marked `integration`) need a running Neo4j and WIPE + RESEED the project
labels in the configured database. They only run when ACN_ALLOW_RESET=true is set, so a
plain `pytest` never touches your data:

    # Windows PowerShell                     # bash
    $env:ACN_ALLOW_RESET="true"; pytest      ACN_ALLOW_RESET=true pytest
"""
from __future__ import annotations

import pytest

from app.config import settings


def pytest_collection_modifyitems(config, items):
    if settings.allow_reset and not settings.is_production:
        return
    skip = pytest.mark.skip(reason="integration test: set ACN_ALLOW_RESET=true (wipes and reseeds the project data)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def seeded_db():
    from app.db import get_driver
    from database.reset import wipe_project_data
    from database.init_db import init_schema
    from database.seed import load_dataset

    get_driver().verify_connectivity()
    wipe_project_data()
    init_schema()
    load_dataset()
    yield
    # Leave a clean seeded database behind for the demo.
    wipe_project_data()
    load_dataset()


@pytest.fixture(scope="session")
def client(seeded_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
