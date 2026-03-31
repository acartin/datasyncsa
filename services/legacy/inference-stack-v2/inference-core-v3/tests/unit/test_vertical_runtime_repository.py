from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.repositories.vertical_runtime_repository import VerticalRuntimeRepository


@pytest.mark.asyncio
async def test_get_or_create_lead_reuses_existing_conversation_lead():
    session = AsyncMock()
    repo = VerticalRuntimeRepository(session)
    existing_lead = UUID("11111111-1111-1111-1111-111111111111")
    repo.get_lead_by_conversation_id = AsyncMock(return_value=existing_lead)

    lead_id = await repo.get_or_create_lead(
        client_id=UUID("64f357a0-98eb-44f1-9f41-6e615ed26180"),
        user_metadata={},
        conversation_id="22222222-2222-2222-2222-222222222222",
    )

    assert lead_id == existing_lead
    session.execute.assert_not_called()
