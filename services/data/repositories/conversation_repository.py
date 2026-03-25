"""Conversation history and persistence repository."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class ConversationRepository:
    """Stores and retrieves chat history with mandatory client filters."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def load_history(
        self,
        *,
        client_id: str,
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        query = text(
            """
            SELECT
                conversation_id::text AS conversation_id,
                summary,
                message_payload,
                created_at
            FROM lead_conversations
            WHERE client_id = :client_id
              AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        async with self.engine.begin() as connection:
            result = await connection.execute(
                query,
                {
                    "client_id": client_id,
                    "user_id": user_id,
                    "limit": limit,
                },
            )
            return [dict(row) for row in result.mappings().all()]

    async def persist_turn(self, payload: dict[str, object]) -> None:
        query = text(
            """
            INSERT INTO lead_conversations (
                client_id,
                user_id,
                conversation_id,
                session_id,
                summary,
                message_payload
            ) VALUES (
                :client_id,
                :user_id,
                :conversation_id,
                :session_id,
                :summary,
                CAST(:message_payload AS jsonb)
            )
            """
        )
        async with self.engine.begin() as connection:
            await connection.execute(query, payload)

