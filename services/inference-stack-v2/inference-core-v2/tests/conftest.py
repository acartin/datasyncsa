import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_cache_service(mocker):
    """Mock cache service for tests."""
    mock = mocker.MagicMock()
    mock.is_enabled.return_value = False
    mock.get_active_model.return_value = None
    mock.set_active_model.return_value = True
    return mock
