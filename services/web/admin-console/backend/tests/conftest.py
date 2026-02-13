import uuid
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "/app")

from app.main import app
from app.modules.auth.config import current_active_user


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_override():
    overrides = []

    def _set(user):
        app.dependency_overrides[current_active_user] = lambda: user
        overrides.append(current_active_user)

    yield _set

    for dep in overrides:
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
def make_user():
    def _factory(
        *,
        is_superuser: bool = False,
        tenant_ids: list[uuid.UUID] | None = None,
    ):
        tenants = [SimpleNamespace(client_id=tenant_id) for tenant_id in (tenant_ids or [])]
        return SimpleNamespace(
            id=uuid.uuid4(),
            email="test@example.com",
            name="Test User",
            is_superuser=is_superuser,
            tenants=tenants,
        )

    return _factory
