"""Conversation history and persistence repository.

Schema: lead_conversations (id, lead_id, platform, conversation_id varchar,
messages jsonb, total_messages, bot_messages, lead_messages, context_snapshot,
last_message_at, created_at, updated_at).

lead_conversations.conversation_id has a non-unique btree index.
Use SELECT-then-INSERT pattern; no ON CONFLICT available.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("data.conversation_repository")


class ConversationRepository:
    """Stores and retrieves chat history with mandatory tenant filters."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    # ------------------------------------------------------------------
    # Load history (used by analyze_turn_node for ANAPHORIC_HISTORY)
    # ------------------------------------------------------------------

    async def load_history(
        self,
        *,
        client_id: str,
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return last N messages from the most recent conversation for this tenant."""
        query = text("""
            SELECT lc.messages
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE ll.client_id = :client_id
            ORDER BY lc.updated_at DESC NULLS LAST, lc.created_at DESC
            LIMIT 1
        """)
        async with self.engine.begin() as conn:
            result = await conn.execute(query, {"client_id": client_id})
            row = result.mappings().first()
        if not row:
            return []
        messages = row.get("messages") or []
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except Exception:
                return []
        if not isinstance(messages, list):
            return []
        if limit <= 0:
            return []
        return messages[-limit:]

    # ------------------------------------------------------------------
    # Lead resolution helpers
    # ------------------------------------------------------------------

    async def _find_lead_by_conversation(
        self,
        conn: Any,
        *,
        client_id: str,
        conversation_id: str,
    ) -> str | None:
        """Return lead_id if a conversation row already exists for this tenant."""
        row = (
            await conn.execute(
                text("""
                    SELECT lc.lead_id::text
                    FROM lead_conversations lc
                    JOIN lead_leads ll ON ll.id = lc.lead_id
                    WHERE lc.conversation_id = :conversation_id
                      AND ll.client_id = :client_id
                    LIMIT 1
                """),
                {"conversation_id": conversation_id, "client_id": client_id},
            )
        ).fetchone()
        return str(row[0]) if row else None

    async def _find_lead_by_hint(
        self,
        conn: Any,
        *,
        client_id: str,
        lead_id_hint: str,
    ) -> str | None:
        """Validate and return lead_id from metadata hint if it belongs to tenant."""
        row = (
            await conn.execute(
                text("""
                    SELECT id::text FROM lead_leads
                    WHERE id = :lead_id AND client_id = :client_id
                    LIMIT 1
                """),
                {"lead_id": lead_id_hint, "client_id": client_id},
            )
        ).fetchone()
        return str(row[0]) if row else None

    async def _create_lead(
        self,
        conn: Any,
        *,
        client_id: str,
        metadata: dict[str, Any],
    ) -> str:
        """Create a new lead_leads row and return its id."""
        full_name = (
            str(metadata.get("full_name") or "").strip()
            or str(metadata.get("extracted_name") or "").strip()
            or f"Lead {client_id[:8]}"
        )
        email = metadata.get("email") or metadata.get("extracted_email") or None
        phone = metadata.get("phone") or metadata.get("extracted_phone") or None
        row = (
            await conn.execute(
                text("""
                    INSERT INTO lead_leads (
                        id, client_id, source_id, full_name, email, phone, created_at
                    )
                    VALUES (gen_random_uuid(), :client_id, 14, :full_name, :email, :phone, NOW())
                    RETURNING id::text
                """),
                {
                    "client_id": client_id,
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                },
            )
        ).fetchone()
        return str(row[0])

    async def _resolve_lead_id(
        self,
        conn: Any,
        *,
        client_id: str,
        conversation_id: str,
        metadata: dict[str, Any],
    ) -> str:
        """Resolve lead_id for this conversation (find existing or create new)."""
        # 1. Already have a conversation row for this conversation_id
        lead_id = await self._find_lead_by_conversation(
            conn, client_id=client_id, conversation_id=conversation_id
        )
        if lead_id:
            return lead_id

        # 2. Caller passed a lead_id hint via metadata
        lead_id_hint = str(metadata.get("lead_id") or "").strip()
        if lead_id_hint:
            lead_id = await self._find_lead_by_hint(
                conn, client_id=client_id, lead_id_hint=lead_id_hint
            )
            if lead_id:
                return lead_id

        # 3. Create new lead
        return await self._create_lead(conn, client_id=client_id, metadata=metadata)

    # ------------------------------------------------------------------
    # Upsert turn
    # ------------------------------------------------------------------

    async def upsert_turn(
        self,
        *,
        client_id: str,
        conversation_id: str,
        user_message: str,
        bot_message: str,
        platform: str = "webchat",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a completed turn to lead_conversations.

        Returns dict with lead_id and message counters.
        Raises on DB error — caller should wrap in try/except for best-effort behavior.
        """
        meta = metadata or {}
        now = datetime.now(timezone.utc)

        async with self.engine.begin() as conn:
            lead_id = await self._resolve_lead_id(
                conn,
                client_id=client_id,
                conversation_id=conversation_id,
                metadata=meta,
            )

            # Get or create conversation row (non-unique index, use SELECT+INSERT)
            row = (
                await conn.execute(
                    text("""
                        SELECT id, messages, total_messages, bot_messages, lead_messages
                        FROM lead_conversations
                        WHERE conversation_id = :conversation_id
                          AND lead_id = :lead_id
                        LIMIT 1
                    """),
                    {"conversation_id": conversation_id, "lead_id": lead_id},
                )
            ).mappings().first()

            if not row:
                await conn.execute(
                    text("""
                        INSERT INTO lead_conversations (
                            lead_id, platform, conversation_id, messages,
                            total_messages, bot_messages, lead_messages, context_snapshot
                        )
                        VALUES (
                            :lead_id, :platform, :conversation_id, '[]'::jsonb,
                            0, 0, 0, '{}'::jsonb
                        )
                    """),
                    {
                        "lead_id": lead_id,
                        "platform": platform,
                        "conversation_id": conversation_id,
                    },
                )
                row = (
                    await conn.execute(
                        text("""
                            SELECT id, messages, total_messages, bot_messages, lead_messages
                            FROM lead_conversations
                            WHERE conversation_id = :conversation_id
                              AND lead_id = :lead_id
                            LIMIT 1
                        """),
                        {"conversation_id": conversation_id, "lead_id": lead_id},
                    )
                ).mappings().first()

            if not row:
                logger.warning(
                    "upsert_turn: could not get/create conversation conversation_id=%s",
                    conversation_id,
                )
                return {
                    "lead_id": lead_id,
                    "total_messages": 0,
                    "bot_messages": 0,
                    "lead_messages": 0,
                }

            messages = row.get("messages") or []
            if isinstance(messages, str):
                try:
                    messages = json.loads(messages)
                except Exception:
                    messages = []
            if not isinstance(messages, list):
                messages = []

            messages.append(
                {"role": "user", "content": user_message, "timestamp": now.isoformat()}
            )
            messages.append(
                {"role": "assistant", "content": bot_message, "timestamp": now.isoformat()}
            )

            total = int(row.get("total_messages") or 0) + 2
            bots = int(row.get("bot_messages") or 0) + 1
            leads = int(row.get("lead_messages") or 0) + 1

            await conn.execute(
                text("""
                    UPDATE lead_conversations
                    SET messages          = CAST(:messages AS jsonb),
                        total_messages    = :total,
                        bot_messages      = :bots,
                        lead_messages     = :leads,
                        last_message_at   = :now
                    WHERE conversation_id = :conversation_id
                      AND lead_id         = :lead_id
                """),
                {
                    "messages": json.dumps(messages, default=str),
                    "total": total,
                    "bots": bots,
                    "leads": leads,
                    "now": now,
                    "conversation_id": conversation_id,
                    "lead_id": lead_id,
                },
            )

        return {
            "lead_id": lead_id,
            "total_messages": total,
            "bot_messages": bots,
            "lead_messages": leads,
        }
