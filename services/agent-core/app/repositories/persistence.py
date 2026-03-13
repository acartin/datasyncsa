from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from app.core.config import settings

logger = logging.getLogger("agent-core.runtime-repository")


def _to_asyncpg_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url[len("postgresql://") :]
    if database_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + database_url[len("postgres://") :]
    return database_url


def _as_uuid(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(str(value).strip()))
    except Exception:
        return None


class RuntimeRepository:
    def __init__(self) -> None:
        self._base = Path(settings.runtime_trace_path)
        self._base.mkdir(parents=True, exist_ok=True)
        self._engine = create_async_engine(
            _to_asyncpg_url(settings.database_url),
            pool_pre_ping=True,
        )

    async def resolve_lead_id(
        self,
        *,
        conversation_id: str,
        payload: dict[str, Any],
        tenant_id: str | None = None,
        explicit_lead_id: str | None = None,
    ) -> str | None:
        serialized = self._serialize(payload)
        tenant_uuid = _as_uuid(tenant_id or self._extract_tenant_id(serialized))
        conversation_uuid = _as_uuid(conversation_id)
        fallback_lead_id = _as_uuid(explicit_lead_id)

        if not tenant_uuid or not conversation_uuid:
            return fallback_lead_id

        try:
            async with self._engine.begin() as conn:
                return await self._resolve_or_create_lead(
                    conn=conn,
                    tenant_id=tenant_uuid,
                    conversation_id=conversation_uuid,
                    explicit_lead_id=fallback_lead_id,
                    user_metadata=self._extract_user_metadata(serialized),
                )
        except Exception as exc:
            logger.warning(
                "runtime_repo_resolve_lead_failed tenant=%s conversation=%s: %s",
                tenant_uuid,
                conversation_uuid,
                exc,
            )
            return fallback_lead_id

    async def persist_turn(
        self,
        *,
        conversation_id: str,
        payload: dict[str, Any],
        metrics: dict[str, float] | None = None,
        lead_id: str | None = None,
    ) -> str | None:
        serialized_payload = self._serialize(payload)
        data = {
            "conversation_id": conversation_id,
            "timestamp": time.time(),
            "payload": serialized_payload,
            "metrics": metrics or {},
        }
        path = self._base / f"{conversation_id}.jsonl"
        await asyncio.to_thread(
            self._append_line,
            path,
            json.dumps(data, ensure_ascii=False),
        )

        tenant_uuid = _as_uuid(self._extract_tenant_id(serialized_payload))
        conversation_uuid = _as_uuid(conversation_id)
        resolved_lead_id = _as_uuid(lead_id)
        if not tenant_uuid or not conversation_uuid:
            return resolved_lead_id

        try:
            async with self._engine.begin() as conn:
                if not resolved_lead_id:
                    resolved_lead_id = await self._resolve_or_create_lead(
                        conn=conn,
                        tenant_id=tenant_uuid,
                        conversation_id=conversation_uuid,
                        explicit_lead_id=None,
                        user_metadata=self._extract_user_metadata(serialized_payload),
                    )
                if not resolved_lead_id:
                    return None

                await self._ensure_conversation_exists(
                    conn=conn,
                    lead_id=resolved_lead_id,
                    conversation_id=conversation_uuid,
                    platform=self._extract_platform(serialized_payload),
                )
                await self._append_turn_and_snapshot(
                    conn=conn,
                    lead_id=resolved_lead_id,
                    conversation_id=conversation_uuid,
                    user_message=self._extract_user_message(serialized_payload),
                    bot_message=self._extract_bot_message(serialized_payload),
                    snapshot=self._build_context_snapshot(serialized_payload),
                )
        except Exception as exc:
            logger.warning(
                "runtime_repo_persist_db_failed tenant=%s conversation=%s: %s",
                tenant_uuid,
                conversation_uuid,
                exc,
            )

        return resolved_lead_id

    async def reset_client_memory(self, client_id: str) -> int:
        normalized_client = str(client_id).strip()
        if not normalized_client:
            return 0
        traces_deleted = await asyncio.to_thread(self._reset_client_memory_sync, normalized_client)
        db_deleted = await self._delete_conversations_by_client(normalized_client)
        return int(traces_deleted) + int(db_deleted)

    @staticmethod
    def _append_line(path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")

    @staticmethod
    def _serialize(payload: Any) -> Any:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(mode="json")
        if isinstance(payload, dict):
            output = {}
            for key, value in payload.items():
                if hasattr(value, "model_dump"):
                    output[key] = value.model_dump(mode="json")
                elif isinstance(value, list):
                    output[key] = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
                else:
                    output[key] = value
            return output
        return payload

    @staticmethod
    def _extract_tenant_id(payload: dict[str, Any]) -> str | None:
        raw_input = payload.get("raw_input") or {}
        if not isinstance(raw_input, dict):
            raw_input = {}
        for key in ("tenant_id", "client_id", "clientId"):
            value = raw_input.get(key)
            if value:
                return str(value)
        for key in ("tenant_id", "client_id", "clientId"):
            value = payload.get(key)
            if value:
                return str(value)
        return None

    @staticmethod
    def _extract_user_metadata(payload: dict[str, Any]) -> dict[str, Any]:
        raw_input = payload.get("raw_input") or {}
        if not isinstance(raw_input, dict):
            return {}
        metadata = raw_input.get("userMetadata") or raw_input.get("user_metadata") or {}
        return metadata if isinstance(metadata, dict) else {}

    @staticmethod
    def _extract_platform(payload: dict[str, Any]) -> str:
        raw_input = payload.get("raw_input") or {}
        if not isinstance(raw_input, dict):
            raw_input = {}
        channel = str(raw_input.get("channel") or "").strip().lower()
        if channel in {"web_html", "api", "web", "webchat"}:
            return "webchat"
        if channel in {"meta_whatsapp", "whatsapp"}:
            return "whatsapp"
        if channel in {"meta_ig", "instagram"}:
            return "instagram"
        if channel in {"messenger", "meta_messenger"}:
            return "messenger"
        if channel in {"telegram", "meta_telegram"}:
            return "telegram"
        return "webchat"

    @staticmethod
    def _extract_user_message(payload: dict[str, Any]) -> str:
        raw_input = payload.get("raw_input") or {}
        if not isinstance(raw_input, dict):
            return ""
        return str(raw_input.get("queryText") or raw_input.get("text") or "").strip()

    @staticmethod
    def _extract_bot_message(payload: dict[str, Any]) -> str:
        envelope = payload.get("answer_envelope") or {}
        if isinstance(envelope, dict):
            text = str(envelope.get("text") or "").strip()
            if text:
                return text
        synth = payload.get("synthesizer_output") or {}
        if isinstance(synth, dict):
            return str(synth.get("text") or "").strip()
        return ""

    def _build_context_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_input = payload.get("raw_input") or {}
        if not isinstance(raw_input, dict):
            raw_input = {}
        normalized = payload.get("normalized_input") or {}
        if not isinstance(normalized, dict):
            normalized = {}

        conversation_state = raw_input.get("conversation_state")
        if not isinstance(conversation_state, dict):
            conversation_state = {}

        return {
            "conversation_summary": str(
                normalized.get("conversation_summary")
                or raw_input.get("queryText")
                or raw_input.get("text")
                or ""
            ).strip(),
            "vertical": str(normalized.get("vertical") or "").strip(),
            "last_user_turn": self._extract_user_message(payload),
            "conversation_state": conversation_state,
            "last_router_decision": payload.get("router_decision") or {},
            "last_tool_results": payload.get("tool_results") or [],
            "last_answer_envelope": payload.get("answer_envelope") or {},
            "error_code": payload.get("error_code"),
            "scoring_status": payload.get("scoring_status"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _delete_conversations_by_client(self, client_id: str) -> int:
        client_uuid = _as_uuid(client_id)
        if not client_uuid:
            return 0

        stmt = text(
            """
            DELETE FROM lead_conversations lc
            USING lead_leads ll
            WHERE lc.lead_id = ll.id
              AND ll.client_id = :client_id
            """
        )
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(stmt, {"client_id": client_uuid})
            return int(result.rowcount or 0)
        except Exception as exc:
            logger.warning("runtime_repo_reset_db_failed client=%s: %s", client_uuid, exc)
            return 0

    async def _resolve_or_create_lead(
        self,
        *,
        conn: AsyncConnection,
        tenant_id: str,
        conversation_id: str,
        explicit_lead_id: str | None,
        user_metadata: dict[str, Any],
    ) -> str | None:
        if explicit_lead_id and await self._lead_belongs_to_tenant(
            conn=conn,
            lead_id=explicit_lead_id,
            tenant_id=tenant_id,
        ):
            return explicit_lead_id

        lead_id = await self._get_lead_by_conversation_id(
            conn=conn,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
        )
        if lead_id:
            return lead_id

        return await self._create_lead(
            conn=conn,
            tenant_id=tenant_id,
            user_metadata=user_metadata,
        )

    async def _lead_belongs_to_tenant(
        self,
        *,
        conn: AsyncConnection,
        lead_id: str,
        tenant_id: str,
    ) -> bool:
        query = text(
            """
            SELECT id
            FROM lead_leads
            WHERE id = :lead_id
              AND client_id = :client_id
            LIMIT 1
            """
        )
        row = (await conn.execute(query, {"lead_id": lead_id, "client_id": tenant_id})).mappings().first()
        return bool(row)

    async def _get_lead_by_conversation_id(
        self,
        *,
        conn: AsyncConnection,
        conversation_id: str,
        tenant_id: str,
    ) -> str | None:
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
        row = (
            await conn.execute(
                query,
                {
                    "conversation_id": conversation_id,
                    "client_id": tenant_id,
                },
            )
        ).mappings().first()
        if not row or not row.get("lead_id"):
            return None
        return _as_uuid(str(row["lead_id"]))

    async def _create_lead(
        self,
        *,
        conn: AsyncConnection,
        tenant_id: str,
        user_metadata: dict[str, Any],
    ) -> str | None:
        metadata = user_metadata if isinstance(user_metadata, dict) else {}
        full_name = str(
            metadata.get("full_name")
            or metadata.get("name")
            or metadata.get("extracted_name")
            or f"Lead {tenant_id[:8]}"
        ).strip()
        email = str(metadata.get("email") or metadata.get("extracted_email") or "").strip() or None
        phone = str(metadata.get("phone") or metadata.get("extracted_phone") or "").strip() or None
        business_domain = str(metadata.get("business_domain") or "").strip() or None
        source_id = self._coerce_source_id(metadata.get("source_id"))
        lead_id = str(uuid4())

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
                :id,
                :client_id,
                :source_id,
                :full_name,
                :email,
                :phone,
                :business_domain,
                NOW()
            )
            """
        )
        await conn.execute(
            insert_stmt,
            {
                "id": lead_id,
                "client_id": tenant_id,
                "source_id": source_id,
                "full_name": full_name[:255] or f"Lead {tenant_id[:8]}",
                "email": email,
                "phone": phone,
                "business_domain": business_domain,
            },
        )
        return lead_id

    @staticmethod
    def _coerce_source_id(value: Any) -> int:
        try:
            parsed = int(value)
            if parsed > 0:
                return parsed
        except Exception:
            pass
        return 14

    async def _ensure_conversation_exists(
        self,
        *,
        conn: AsyncConnection,
        lead_id: str,
        conversation_id: str,
        platform: str,
    ) -> None:
        query = text(
            """
            SELECT id
            FROM lead_conversations
            WHERE lead_id = :lead_id
              AND conversation_id = :conversation_id
            ORDER BY updated_at DESC NULLS LAST, last_message_at DESC NULLS LAST, id DESC
            LIMIT 1
            """
        )
        existing = await conn.execute(
            query,
            {"lead_id": lead_id, "conversation_id": conversation_id},
        )
        if existing.mappings().first():
            return

        insert_stmt = text(
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
                context_snapshot,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :lead_id,
                :platform,
                :conversation_id,
                '[]'::jsonb,
                0,
                0,
                0,
                '{}'::jsonb,
                NOW(),
                NOW()
            )
            """
        )
        await conn.execute(
            insert_stmt,
            {
                "id": str(uuid4()),
                "lead_id": lead_id,
                "platform": platform or "webchat",
                "conversation_id": conversation_id,
            },
        )

    async def _append_turn_and_snapshot(
        self,
        *,
        conn: AsyncConnection,
        lead_id: str,
        conversation_id: str,
        user_message: str,
        bot_message: str,
        snapshot: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        messages_to_append: list[dict[str, Any]] = []
        lead_increment = 0
        bot_increment = 0

        if user_message:
            messages_to_append.append(
                {
                    "role": "user",
                    "content": user_message,
                    "timestamp": now_iso,
                }
            )
            lead_increment = 1

        if bot_message:
            messages_to_append.append(
                {
                    "role": "assistant",
                    "content": bot_message,
                    "timestamp": now_iso,
                }
            )
            bot_increment = 1

        total_increment = lead_increment + bot_increment
        update_stmt = text(
            """
            UPDATE lead_conversations
            SET messages = COALESCE(messages, '[]'::jsonb) || CAST(:messages AS jsonb),
                total_messages = COALESCE(total_messages, 0) + :total_increment,
                bot_messages = COALESCE(bot_messages, 0) + :bot_increment,
                lead_messages = COALESCE(lead_messages, 0) + :lead_increment,
                context_snapshot = CAST(:context_snapshot AS jsonb),
                last_message_at = CASE
                    WHEN :total_increment > 0 THEN :last_message_at
                    ELSE last_message_at
                END,
                updated_at = NOW()
            WHERE conversation_id = :conversation_id
              AND lead_id = :lead_id
            """
        )
        await conn.execute(
            update_stmt,
            {
                "messages": json.dumps(messages_to_append, ensure_ascii=False),
                "total_increment": total_increment,
                "bot_increment": bot_increment,
                "lead_increment": lead_increment,
                "context_snapshot": json.dumps(snapshot or {}, ensure_ascii=False, default=str),
                "last_message_at": now,
                "conversation_id": conversation_id,
                "lead_id": lead_id,
            },
        )

    def _reset_client_memory_sync(self, client_id: str) -> int:
        conversations_deleted = 0
        for path in self._base.glob("*.jsonl"):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            kept_lines: list[str] = []
            removed_any = False
            for line in lines:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    kept_lines.append(line)
                    continue
                raw_input = ((payload.get("payload") or {}).get("raw_input") or {})
                event_client = str(
                    raw_input.get("tenant_id")
                    or raw_input.get("client_id")
                    or raw_input.get("clientId")
                    or ""
                ).strip()
                if event_client == client_id:
                    removed_any = True
                    continue
                kept_lines.append(line)

            if not removed_any:
                continue

            conversations_deleted += 1
            if kept_lines:
                path.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")
            else:
                path.unlink(missing_ok=True)

        return conversations_deleted


runtime_repository = RuntimeRepository()
