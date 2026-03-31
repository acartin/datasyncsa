import json
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, Iterable, Optional
from uuid import UUID
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("inference-core-v3.repositories")


class VerticalRuntimeRepository:
    """Minimal repository for tenant runtime data used by v3 dispatcher."""

    _DEFAULT_LEAD_SOURCE_ID = 14

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_client_vertical_context(self, client_id: UUID) -> Optional[Dict[str, Any]]:
        stmt = text(
            """
            SELECT
                c.id AS client_id,
                c.vertical_id AS vertical_id,
                c.scoring_model_id AS scoring_model_id,
                v.slug AS vertical_slug,
                v.name AS vertical_name
            FROM lead_clients c
            LEFT JOIN lead_client_verticals v ON v.id = c.vertical_id
            WHERE c.id = :client_id
            """
        )
        result = await self.session.execute(stmt, {"client_id": str(client_id)})
        row = result.mappings().first()
        if not row:
            return {
                "client_exists": False,
                "vertical_id": None,
                "scoring_model_id": None,
                "vertical_slug": None,
                "vertical_name": None,
            }
        return {
            "client_exists": True,
            "vertical_id": row["vertical_id"],
            "scoring_model_id": row["scoring_model_id"],
            "vertical_slug": row["vertical_slug"],
            "vertical_name": row["vertical_name"],
        }

    async def get_client_system_prompt(self, client_id: UUID, slug: str = "primary_chat") -> Optional[str]:
        query = text(
            """
            SELECT prompt_text
            FROM lead_ai_prompts
            WHERE client_id = :client_id
              AND slug = :slug
              AND is_active = true
            LIMIT 1
            """
        )
        result = await self.session.execute(query, {"client_id": str(client_id), "slug": slug})
        row = result.mappings().first()
        if row:
            return row["prompt_text"]

        query = text(
            """
            SELECT prompt_text
            FROM lead_ai_prompts
            WHERE client_id IS NULL
              AND slug = :slug
              AND is_active = true
            LIMIT 1
            """
        )
        result = await self.session.execute(query, {"slug": slug})
        row = result.mappings().first()
        if row:
            return row["prompt_text"]

        return None

    async def get_client_prompt_bundle(
        self,
        client_id: UUID,
        slugs: Iterable[str],
    ) -> Dict[str, Optional[str]]:
        bundle: Dict[str, Optional[str]] = {}
        for slug in slugs:
            bundle[str(slug)] = await self.get_client_system_prompt(client_id=client_id, slug=str(slug))
        return bundle

    async def get_active_ai_system_prompt(
        self,
        node_slug: str,
        vertical_slug: Optional[str] = None,
    ) -> Optional[str]:
        scoped_query = text(
            """
            SELECT prompt_text
            FROM ai_system_prompts
            WHERE node_slug = :node_slug
              AND vertical_slug = :vertical_slug
              AND is_active = true
            ORDER BY version DESC, updated_at DESC
            LIMIT 1
            """
        )
        if vertical_slug:
            result = await self.session.execute(
                scoped_query,
                {
                    "node_slug": str(node_slug),
                    "vertical_slug": str(vertical_slug),
                },
            )
            row = result.mappings().first()
            if row:
                return row["prompt_text"]

        fallback_query = text(
            """
            SELECT prompt_text
            FROM ai_system_prompts
            WHERE node_slug = :node_slug
              AND vertical_slug IS NULL
              AND is_active = true
            ORDER BY version DESC, updated_at DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            fallback_query,
            {
                "node_slug": str(node_slug),
            },
        )
        row = result.mappings().first()
        if row:
            return row["prompt_text"]

        return None

    async def get_active_ai_system_prompt_bundle(
        self,
        *,
        node_slugs: Iterable[str],
        vertical_slug: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        bundle: Dict[str, Optional[str]] = {}
        for node_slug in node_slugs:
            bundle[str(node_slug)] = await self.get_active_ai_system_prompt(
                node_slug=str(node_slug),
                vertical_slug=vertical_slug,
            )
        return bundle

    async def get_or_create_lead(
        self,
        client_id: UUID,
        user_metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> UUID:
        metadata = user_metadata or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}

        if conversation_id:
            existing_by_conversation = await self.get_lead_by_conversation_id(
                conversation_id=str(conversation_id),
                client_id=client_id,
            )
            if existing_by_conversation:
                return existing_by_conversation

        existing_lead_id = metadata.get("lead_id") or metadata.get("leadId")
        if existing_lead_id:
            try:
                normalized_lead_id = UUID(str(existing_lead_id))
            except (TypeError, ValueError):
                normalized_lead_id = None
            if normalized_lead_id:
                stmt = text(
                    """
                    SELECT id
                    FROM lead_leads
                    WHERE id = :lead_id
                      AND client_id = :client_id
                    LIMIT 1
                    """
                )
                result = await self.session.execute(
                    stmt,
                    {"lead_id": str(normalized_lead_id), "client_id": str(client_id)},
                )
                row = result.fetchone()
                if row:
                    return UUID(str(row[0]))

        metadata = self._normalize_extraction_data(metadata)
        full_name = (
            metadata.get("full_name")
            or metadata.get("extracted_name")
            or metadata.get("name")
            or f"Lead {str(client_id)[:8]}"
        )
        email = metadata.get("email") or metadata.get("extracted_email")
        phone = metadata.get("phone") or metadata.get("extracted_phone")
        source_id = metadata.get("source_id", self._DEFAULT_LEAD_SOURCE_ID)

        try:
            source_id_int = int(source_id)
        except (TypeError, ValueError):
            source_id_int = self._DEFAULT_LEAD_SOURCE_ID

        insert_stmt = text(
            """
            INSERT INTO lead_leads (
                id,
                client_id,
                source_id,
                full_name,
                email,
                phone,
                business_domain,
                created_at
            )
            VALUES (
                gen_random_uuid(),
                :client_id,
                :source_id,
                :full_name,
                :email,
                :phone,
                :business_domain,
                NOW()
            )
            RETURNING id
            """
        )
        result = await self.session.execute(
            insert_stmt,
            {
                "client_id": str(client_id),
                "source_id": source_id_int,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "business_domain": metadata.get("business_domain"),
            },
        )
        lead_id = UUID(str(result.scalar_one()))

        await self._ensure_conversation_exists(
            lead_id=lead_id,
            conversation_id=conversation_id,
            platform="webchat",
        )
        return lead_id

    async def get_lead_by_conversation_id(
        self,
        conversation_id: str,
        client_id: UUID,
    ) -> Optional[UUID]:
        query = text(
            """
            SELECT lc.lead_id
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE lc.conversation_id = :conversation_id
              AND ll.client_id = :client_id
            ORDER BY lc.updated_at DESC NULLS LAST, lc.last_message_at DESC NULLS LAST, lc.id DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            query,
            {"conversation_id": str(conversation_id), "client_id": str(client_id)},
        )
        row = result.fetchone()
        if not row:
            return None

        try:
            return UUID(str(row[0]))
        except (TypeError, ValueError):
            return None

    async def get_conversation_record(
        self,
        lead_id: UUID,
        conversation_id: str,
    ) -> Optional[Dict[str, Any]]:
        query = text(
            """
            SELECT id, lead_id, platform, conversation_id, messages,
                   total_messages, bot_messages, lead_messages, context_snapshot
            FROM lead_conversations
            WHERE lead_id = :lead_id
              AND conversation_id = :conversation_id
            ORDER BY updated_at DESC NULLS LAST, last_message_at DESC NULLS LAST, id DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            query,
            {
                "lead_id": str(lead_id),
                "conversation_id": str(conversation_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        return dict(row)

    async def get_conversation_messages(
        self,
        conversation_id: str,
        client_id: UUID,
        max_messages: int = 20,
    ) -> list[Dict[str, Any]]:
        query = text(
            """
            SELECT lc.messages
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE lc.conversation_id = :conversation_id
              AND ll.client_id = :client_id
            ORDER BY lc.updated_at DESC NULLS LAST, lc.last_message_at DESC NULLS LAST, lc.id DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            query,
            {"conversation_id": str(conversation_id), "client_id": str(client_id)},
        )
        row = result.mappings().first()
        if not row:
            return []

        messages = row.get("messages") or []
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except Exception:
                logger.warning(
                    "Invalid JSON in lead_conversations.messages for %s",
                    conversation_id,
                )
                return []
        if not isinstance(messages, list):
            return []

        if max_messages <= 0:
            return []

        return messages[-max_messages:]

    async def get_conversation_context_snapshot(self, conversation_id: UUID, client_id: UUID) -> Optional[Dict[str, Any]]:
        query = text(
            """
            SELECT lc.context_snapshot
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE lc.conversation_id = :conversation_id
              AND ll.client_id = :client_id
            ORDER BY lc.updated_at DESC NULLS LAST, lc.last_message_at DESC NULLS LAST, lc.id DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            query,
            {"conversation_id": str(conversation_id), "client_id": str(client_id)},
        )
        row = result.mappings().first()
        if not row:
            return None

        snapshot = row.get("context_snapshot")
        if snapshot is None:
            return {}
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                return {}
        return snapshot if isinstance(snapshot, dict) else None

    async def get_conversation_context_snapshot_by_ids(
        self,
        conversation_id: str,
        lead_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        query = text(
            """
            SELECT lc.context_snapshot
            FROM lead_conversations lc
            WHERE lc.conversation_id = :conversation_id
              AND lc.lead_id = :lead_id
            ORDER BY lc.updated_at DESC NULLS LAST, lc.last_message_at DESC NULLS LAST, lc.id DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            query,
            {"conversation_id": str(conversation_id), "lead_id": str(lead_id)},
        )
        row = result.mappings().first()
        if not row:
            return None

        snapshot = row.get("context_snapshot")
        if snapshot is None:
            return {}
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                logger.warning(
                    "Invalid JSON in lead_conversations.context_snapshot for %s",
                    conversation_id,
                )
                return {}
        return snapshot if isinstance(snapshot, dict) else {}

    async def get_lead_snapshot(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        query = text(
            """
            SELECT id, full_name, email, phone, source_id, status_id, current_scorecard_id, created_at
            FROM lead_leads
            WHERE id = :lead_id
            LIMIT 1
            """
        )
        result = await self.session.execute(query, {"lead_id": str(lead_id)})
        row = result.mappings().first()
        if not row:
            return None
        return {
            "id": str(row.get("id")) if row.get("id") else None,
            "full_name": row.get("full_name"),
            "email": row.get("email"),
            "phone": row.get("phone"),
            "source_id": row.get("source_id"),
            "status_id": str(row.get("status_id")) if row.get("status_id") else None,
            "current_scorecard_id": str(row.get("current_scorecard_id"))
            if row.get("current_scorecard_id")
            else None,
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        }

    async def get_conversation_metrics(
        self,
        conversation_id: UUID,
        client_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        query = text(
            """
            SELECT
                lc.lead_id,
                lc.total_messages,
                lc.bot_messages,
                lc.lead_messages,
                lc.last_message_at
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE lc.conversation_id = :conversation_id
              AND ll.client_id = :client_id
            ORDER BY lc.updated_at DESC NULLS LAST, lc.last_message_at DESC NULLS LAST, lc.id DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            query,
            {
                "conversation_id": str(conversation_id),
                "client_id": str(client_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "lead_id": str(row.get("lead_id")) if row.get("lead_id") else None,
            "total_messages": row.get("total_messages", 0),
            "bot_messages": row.get("bot_messages", 0),
            "lead_messages": row.get("lead_messages", 0),
            "last_message_at": row.get("last_message_at").isoformat() if row.get("last_message_at") else None,
        }

    async def get_active_scoring_model(
        self,
        vertical_id: int,
        scoring_model_id: Optional[UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        if not vertical_id:
            return None

        if scoring_model_id:
            query = text(
                """
                SELECT id, vertical_id, name, version, prompt_version, normalization_strategy
                FROM lead_scoring_models
                WHERE id = :model_id
                  AND vertical_id = :vertical_id
                  AND is_active = true
                LIMIT 1
                """
            )
            params = {
                "model_id": str(scoring_model_id),
                "vertical_id": vertical_id,
            }
        else:
            query = text(
                """
                SELECT id, vertical_id, name, version, prompt_version, normalization_strategy
                FROM lead_scoring_models
                WHERE vertical_id = :vertical_id
                  AND is_active = true
                ORDER BY version DESC
                LIMIT 1
                """
            )
            params = {"vertical_id": vertical_id}

        result = await self.session.execute(query, params)
        row = result.mappings().first()
        if not row:
            return None

        model = dict(row)
        model["id"] = str(model["id"])
        return model

    async def get_active_scoring_prompt(self, model_id: UUID) -> Optional[Dict[str, Any]]:
        query = text(
            """
            SELECT id, model_id, version, prompt_template, extraction_schema, is_active
            FROM lead_scoring_prompts
            WHERE model_id = :model_id
              AND is_active = true
            ORDER BY version DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(query, {"model_id": str(model_id)})
        row = result.mappings().first()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "model_id": str(row["model_id"]),
            "version": row["version"],
            "prompt_template": row["prompt_template"],
            "extraction_schema": row.get("extraction_schema"),
            "is_active": row["is_active"],
        }

    async def upsert_scoring_job(
        self,
        *,
        lead_id: UUID,
        conversation_id: UUID,
        client_id: UUID,
        expected_lead_messages: Optional[int],
        model_id: Optional[UUID],
        prompt_id: Optional[UUID],
        max_attempts: int,
        debounce_secs: float,
    ) -> Dict[str, Any]:
        scheduled_for = datetime.now(timezone.utc) + timedelta(seconds=max(0.0, debounce_secs))
        stmt = text(
            """
            INSERT INTO lead_scoring_jobs (
                lead_id,
                conversation_id,
                client_id,
                model_id,
                prompt_id,
                generation,
                running_generation,
                expected_lead_messages,
                status,
                attempts,
                max_attempts,
                scheduled_for,
                last_error_code,
                last_error_message,
                fallback_used,
                json_valid,
                latency_ms,
                response_chars,
                started_at,
                finished_at
            )
            VALUES (
                CAST(:lead_id AS uuid),
                CAST(:conversation_id AS uuid),
                CAST(:client_id AS uuid),
                CAST(:model_id AS uuid),
                CAST(:prompt_id AS uuid),
                1,
                NULL,
                :expected_lead_messages,
                'queued',
                0,
                :max_attempts,
                :scheduled_for,
                NULL,
                NULL,
                FALSE,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL
            )
            ON CONFLICT (conversation_id)
            DO UPDATE SET
                lead_id = EXCLUDED.lead_id,
                client_id = EXCLUDED.client_id,
                model_id = EXCLUDED.model_id,
                prompt_id = EXCLUDED.prompt_id,
                generation = lead_scoring_jobs.generation + 1,
                running_generation = NULL,
                expected_lead_messages = EXCLUDED.expected_lead_messages,
                status = 'queued',
                attempts = 0,
                max_attempts = EXCLUDED.max_attempts,
                scheduled_for = EXCLUDED.scheduled_for,
                last_error_code = NULL,
                last_error_message = NULL,
                fallback_used = FALSE,
                json_valid = NULL,
                latency_ms = NULL,
                response_chars = NULL,
                started_at = NULL,
                finished_at = NULL,
                updated_at = NOW()
            RETURNING *
            """
        )
        result = await self.session.execute(
            stmt,
            {
                "lead_id": str(lead_id),
                "conversation_id": str(conversation_id),
                "client_id": str(client_id),
                "model_id": str(model_id) if model_id else None,
                "prompt_id": str(prompt_id) if prompt_id else None,
                "expected_lead_messages": expected_lead_messages,
                "max_attempts": max_attempts,
                "scheduled_for": scheduled_for,
            },
        )
        await self.session.commit()
        row = result.mappings().first()
        return self._serialize_scoring_job_row(dict(row)) if row else {}

    async def delete_conversations_by_client(self, client_id: UUID) -> int:
        stmt = text(
            """
            DELETE FROM lead_conversations lc
            USING lead_leads ll
            WHERE lc.lead_id = ll.id
              AND ll.client_id = :client_id
            """
        )
        result = await self.session.execute(stmt, {"client_id": str(client_id)})
        await self.session.commit()
        return int(result.rowcount or 0)

    async def upsert_conversation_context_snapshot(
        self,
        conversation_id: UUID,
        lead_id: UUID,
        snapshot: Dict[str, Any],
    ) -> None:
        query = text(
            """
            UPDATE lead_conversations
            SET context_snapshot = CAST(:context_snapshot AS jsonb),
                updated_at = NOW()
            WHERE conversation_id = :conversation_id
              AND lead_id = :lead_id
            """
        )
        await self.session.execute(
            query,
            {
                "context_snapshot": json.dumps(snapshot, default=str),
                "conversation_id": str(conversation_id),
                "lead_id": str(lead_id),
            },
        )
        await self.session.commit()

    async def append_conversation_turn(
        self,
        conversation_id: str,
        lead_id: UUID,
        user_message: str,
        bot_message: str,
    ) -> Dict[str, int]:
        query = text(
            """
            SELECT messages, total_messages, bot_messages, lead_messages
            FROM lead_conversations
            WHERE conversation_id = :conversation_id
              AND lead_id = :lead_id
            ORDER BY updated_at DESC NULLS LAST, last_message_at DESC NULLS LAST, id DESC
            LIMIT 1
            """
        )
        result = await self.session.execute(
            query,
            {"conversation_id": str(conversation_id), "lead_id": str(lead_id)},
        )
        row = result.mappings().first()
        if not row:
            return {
                "total_messages": 0,
                "bot_messages": 0,
                "lead_messages": 0,
            }

        messages = row.get("messages") or []
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except Exception:
                logger.warning("Invalid JSON in lead_conversations.messages for %s", conversation_id)
                messages = []
        if not isinstance(messages, list):
            messages = []

        now = datetime.now(timezone.utc).isoformat()
        messages.extend(
            [
                {
                    "role": "user",
                    "content": user_message,
                    "timestamp": now,
                },
                {
                    "role": "assistant",
                    "content": bot_message,
                    "timestamp": now,
                },
            ]
        )

        total = int(row.get("total_messages") or 0) + 2
        bot_count = int(row.get("bot_messages") or 0) + 1
        user_count = int(row.get("lead_messages") or 0) + 1

        update_query = text(
            """
            UPDATE lead_conversations
            SET messages = :messages,
                total_messages = :total_messages,
                bot_messages = :bot_messages,
                lead_messages = :lead_messages,
                last_message_at = :last_message_at,
                updated_at = NOW()
            WHERE conversation_id = :conversation_id
              AND lead_id = :lead_id
            """
        )
        await self.session.execute(
            update_query,
            {
                "messages": json.dumps(messages),
                "total_messages": total,
                "bot_messages": bot_count,
                "lead_messages": user_count,
                "last_message_at": datetime.now(timezone.utc),
                "conversation_id": str(conversation_id),
                "lead_id": str(lead_id),
            },
        )
        await self.session.commit()

        return {
            "total_messages": total,
            "bot_messages": bot_count,
            "lead_messages": user_count,
        }

    async def _ensure_conversation_exists(
        self,
        lead_id: UUID,
        conversation_id: Optional[str],
        platform: str = "webchat",
    ) -> None:
        if not conversation_id:
            return

        existing = await self.get_conversation_record(lead_id, conversation_id)
        if existing:
            return

        query = text(
            """
            INSERT INTO lead_conversations (
                id,
                lead_id,
                platform,
                conversation_id,
                messages,
                total_messages,
                bot_messages,
                lead_messages,
                context_snapshot
            )
            VALUES (:id, :lead_id, :platform, :conversation_id, '[]'::jsonb, 0, 0, 0, '{}'::jsonb)
            """
        )
        await self.session.execute(
            query,
            {
                "id": str(uuid.uuid4()),
                "lead_id": str(lead_id),
                "platform": platform,
                "conversation_id": str(conversation_id),
            },
        )
        await self.session.commit()

    @staticmethod
    def _normalize_extraction_data(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Drop null-ish values before persisting extracted context."""
        if not isinstance(data, dict):
            return {}

        normalized: Dict[str, Any] = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, str):
                cleaned = value.strip()
                if not cleaned:
                    continue
                if cleaned.lower() in {"null", "none", "n/a", "na", "unknown", "desconocido"}:
                    continue
                normalized[key] = cleaned
                continue
            normalized[key] = value

        return normalized

    @staticmethod
    def _serialize_scoring_job_row(row: Dict[str, Any]) -> Dict[str, Any]:
        if not row:
            return {}
        return {
            "id": str(row.get("id")) if row.get("id") else None,
            "lead_id": str(row.get("lead_id")) if row.get("lead_id") else None,
            "conversation_id": str(row.get("conversation_id")) if row.get("conversation_id") else None,
            "client_id": str(row.get("client_id")) if row.get("client_id") else None,
            "model_id": str(row.get("model_id")) if row.get("model_id") else None,
            "prompt_id": str(row.get("prompt_id")) if row.get("prompt_id") else None,
            "generation": row.get("generation"),
            "running_generation": row.get("running_generation"),
            "expected_lead_messages": row.get("expected_lead_messages"),
            "status": row.get("status"),
            "attempts": row.get("attempts"),
            "max_attempts": row.get("max_attempts"),
            "scheduled_for": row.get("scheduled_for").isoformat() if row.get("scheduled_for") else None,
            "started_at": row.get("started_at").isoformat() if row.get("started_at") else None,
            "finished_at": row.get("finished_at").isoformat() if row.get("finished_at") else None,
            "last_error_code": row.get("last_error_code"),
            "last_error_message": row.get("last_error_message"),
            "fallback_used": row.get("fallback_used"),
            "json_valid": row.get("json_valid"),
            "latency_ms": row.get("latency_ms"),
            "response_chars": row.get("response_chars"),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
        }
