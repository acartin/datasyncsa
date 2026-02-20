import logging
import json
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("inference-core-v2.repositories")


class ScoringRepository:
    """Repository for scoring v2 database operations - uses raw SQL"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        client_id: UUID,
        max_messages: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Returns tenant-scoped conversation messages for LLM context.
        """
        query = text("""
            SELECT lc.messages
            FROM lead_conversations lc
            JOIN lead_leads ll ON ll.id = lc.lead_id
            WHERE lc.conversation_id = :conversation_id
              AND ll.client_id = :client_id
            LIMIT 1
        """)
        result = await self.session.execute(
            query,
            {
                "conversation_id": str(conversation_id),
                "client_id": str(client_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return []

        messages = row.get("messages") or []
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except Exception:
                logger.warning("Invalid JSON in lead_conversations.messages for %s", conversation_id)
                return []

        if not isinstance(messages, list):
            return []

        if max_messages <= 0:
            return []
        return messages[-max_messages:]

    async def get_conversation_metrics(
        self,
        conversation_id: UUID,
        client_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns tenant-scoped metrics for a conversation.
        """
        query = text("""
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
            LIMIT 1
        """)
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

    async def get_lead_snapshot(
        self,
        lead_id: UUID,
        client_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns tenant-scoped lead snapshot for structured RAG context.
        """
        query = text("""
            SELECT
                id,
                full_name,
                email,
                phone,
                lead_type,
                business_domain,
                source_id,
                current_scorecard_id,
                created_at
            FROM lead_leads
            WHERE id = :lead_id
              AND client_id = :client_id
            LIMIT 1
        """)
        result = await self.session.execute(
            query,
            {
                "lead_id": str(lead_id),
                "client_id": str(client_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "id": str(row.get("id")),
            "full_name": row.get("full_name"),
            "email": row.get("email"),
            "phone": row.get("phone"),
            "lead_type": row.get("lead_type"),
            "business_domain": row.get("business_domain"),
            "source_id": row.get("source_id"),
            "current_scorecard_id": str(row.get("current_scorecard_id")) if row.get("current_scorecard_id") else None,
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        }

    async def delete_conversations_by_client(self, client_id: UUID) -> int:
        """
        Deletes conversation rows for a tenant and returns deleted count.
        """
        stmt = text("""
            DELETE FROM lead_conversations lc
            USING lead_leads ll
            WHERE lc.lead_id = ll.id
              AND ll.client_id = :client_id
        """)
        result = await self.session.execute(stmt, {"client_id": str(client_id)})
        await self.session.commit()
        return result.rowcount or 0

    async def get_or_create_conversation(
        self,
        lead_id: UUID,
        conversation_id: UUID,
        platform: str = "webchat"
    ) -> Dict[str, Any]:
        """Get or create a conversation"""
        # Try to find existing conversation
        query = text("""
            SELECT id, lead_id, platform, conversation_id, messages, total_messages
            FROM lead_conversations 
            WHERE lead_id = :lead_id 
              AND conversation_id = :conversation_id
            LIMIT 1
        """)
        result = await self.session.execute(query, {
            "lead_id": str(lead_id),
            "conversation_id": str(conversation_id)
        })
        row = result.mappings().first()
        
        if row:
            return dict(row)
        
        # Create new conversation
        insert_query = text("""
            INSERT INTO lead_conversations (lead_id, platform, conversation_id, messages, total_messages, bot_messages, lead_messages)
            VALUES (:lead_id, :platform, :conversation_id, '[]'::jsonb, 0, 0, 0)
            RETURNING id, lead_id, platform, conversation_id, messages, total_messages
        """)
        result = await self.session.execute(insert_query, {
            "lead_id": str(lead_id),
            "platform": platform,
            "conversation_id": str(conversation_id)
        })
        row = result.mappings().first()
        await self.session.commit()
        return dict(row)

    async def update_conversation(
        self,
        conversation_id: UUID,
        lead_id: UUID,
        user_message: str,
        bot_message: str
    ) -> None:
        """Update conversation with new messages"""
        # Get current messages - search by conversation_id field
        query = text("""
            SELECT id, messages, total_messages, bot_messages, lead_messages
            FROM lead_conversations 
            WHERE conversation_id = :conversation_id
        """)
        result = await self.session.execute(query, {"conversation_id": str(conversation_id)})
        row = result.mappings().first()
        
        if not row:
            logger.warning(f"Conversation {conversation_id} not found")
            return
        
        messages = row.get("messages", [])
        if isinstance(messages, str):
            messages = json.loads(messages)
        
        from datetime import datetime
        # Add user message
        messages.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Add bot message
        messages.append({
            "role": "assistant", 
            "content": bot_message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        total = row.get("total_messages", 0) + 2
        bot_count = row.get("bot_messages", 0) + 1
        lead_count = row.get("lead_messages", 0) + 1
        
        update_query = text("""
            UPDATE lead_conversations 
            SET messages = :messages,
                total_messages = :total_messages,
                bot_messages = :bot_messages,
                lead_messages = :lead_messages,
                last_message_at = :last_message_at
            WHERE conversation_id = :conversation_id
        """)
        await self.session.execute(update_query, {
            "messages": json.dumps(messages),
            "total_messages": total,
            "bot_messages": bot_count,
            "lead_messages": lead_count,
            "last_message_at": datetime.utcnow(),
            "conversation_id": str(conversation_id)
        })
        await self.session.commit()
    
    @staticmethod
    def _normalize_extraction_result(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Drop null/empty placeholder values so accumulation is monotonic."""
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
    
    async def get_active_scoring_model(
        self,
        vertical_id: int,
        business_domain: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get active scoring model for given scope using raw SQL
        """
        try:
            if not vertical_id:
                logger.warning("Model resolution requires vertical_id")
                return None

            # Query model
            if business_domain:
                model_query = text("""
                    SELECT id, vertical_id, business_domain, name, version, prompt_version, normalization_strategy
                    FROM lead_scoring_models
                    WHERE vertical_id = :vertical_id
                      AND business_domain = :business_domain
                      AND is_active = true
                    ORDER BY version DESC
                    LIMIT 1
                """)
                result = await self.session.execute(model_query, {
                    "vertical_id": vertical_id,
                    "business_domain": business_domain
                })
            else:
                model_query = text("""
                    SELECT id, vertical_id, business_domain, name, version, prompt_version, normalization_strategy
                    FROM lead_scoring_models
                    WHERE vertical_id = :vertical_id
                      AND business_domain IS NULL
                      AND is_active = true
                    ORDER BY version DESC
                    LIMIT 1
                """)
                result = await self.session.execute(model_query, {"vertical_id": vertical_id})
            
            row = result.mappings().first()
            if not row:
                logger.warning(f"No active model found for vertical={vertical_id}, domain={business_domain}")
                return None
            
            model = dict(row)
            
            # Query criteria
            criteria_query = text("""
                SELECT id, criterion_key, label, weight, min_score, max_score, display_order
                FROM lead_scoring_criteria
                WHERE model_id = :model_id AND is_active = true
                ORDER BY display_order
            """)
            criteria_result = await self.session.execute(criteria_query, {"model_id": model["id"]})
            criteria = [dict(r) for r in criteria_result.mappings().all()]
            
            # Query bands for each criterion
            for criterion in criteria:
                bands_query = text("""
                    SELECT id, band_key, label, min_score, max_score, icon, color
                    FROM lead_scoring_bands
                    WHERE criterion_id = :criterion_id
                    ORDER BY min_score
                """)
                bands_result = await self.session.execute(bands_query, {"criterion_id": criterion["id"]})
                criterion["bands"] = [dict(b) for b in bands_result.mappings().all()]
            
            model["criteria"] = criteria
            
            # Convert UUIDs to strings for JSON serialization
            model["id"] = str(model["id"])
            for c in model["criteria"]:
                c["id"] = str(c["id"])
                for b in c["bands"]:
                    b["id"] = str(b["id"])
            
            logger.debug(f"Found active model for vertical={vertical_id}, domain={business_domain}")
            return model
            
        except Exception as e:
            logger.error(f"Error getting active scoring model: {e}")
            raise

    async def get_client_vertical_context(self, client_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Resolve tenant vertical context from lead_clients.vertical_id -> lead_client_verticals.
        """
        try:
            stmt = text("""
                SELECT
                    c.id AS client_id,
                    c.vertical_id AS vertical_id,
                    v.slug AS vertical_slug,
                    v.name AS vertical_name
                FROM lead_clients c
                LEFT JOIN lead_client_verticals v ON v.id = c.vertical_id
                WHERE c.id = :client_id
            """)
            result = await self.session.execute(stmt, {"client_id": str(client_id)})
            row = result.mappings().first()
            if not row:
                return {"client_exists": False, "vertical_id": None, "vertical_slug": None, "vertical_name": None}

            return {
                "client_exists": True,
                "vertical_id": row["vertical_id"],
                "vertical_slug": row["vertical_slug"],
                "vertical_name": row["vertical_name"],
            }
        except Exception as e:
            logger.error(f"Error resolving client vertical context: {e}")
            raise
    
    async def create_scorecard(
        self,
        lead_id: UUID,
        model_id: UUID,
        model_version: int,
        prompt_version: int,
        score_total: float,
        priority_label: Optional[str] = None,
        reasoning: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
        raw_payload: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Create a new scorecard using raw SQL"""
        try:
            import json
            
            raw_json = json.dumps(raw_payload) if raw_payload else None
            
            stmt = text("""
                INSERT INTO lead_scorecards 
                    (lead_id, conversation_id, model_id, model_version, prompt_version, score_total, priority_label, reasoning, raw_payload)
                VALUES 
                    (CAST(:lead_id AS uuid), CAST(:conversation_id AS uuid), CAST(:model_id AS uuid), :model_version, :prompt_version, :score_total, :priority_label, :reasoning, CAST(:raw_payload AS jsonb))
                RETURNING id
            """)
            result = await self.session.execute(stmt, {
                "lead_id": str(lead_id),
                "conversation_id": str(conversation_id) if conversation_id else None,
                "model_id": str(model_id),
                "model_version": model_version,
                "prompt_version": prompt_version,
                "score_total": score_total,
                "priority_label": priority_label,
                "reasoning": reasoning,
                "raw_payload": raw_json
            })
            scorecard_id = result.scalar_one()
            logger.debug(f"Created scorecard {scorecard_id} for lead {lead_id}")
            return UUID(str(scorecard_id))
            
        except Exception as e:
            logger.error(f"Error creating scorecard: {e}")
            raise
    
    async def create_score_items(
        self,
        scorecard_id: UUID,
        score_items: List[Dict[str, Any]]
    ) -> int:
        """Replace score items for a scorecard using raw SQL"""
        try:
            delete_stmt = text("""
                DELETE FROM lead_score_items
                WHERE scorecard_id = CAST(:scorecard_id AS uuid)
            """)
            await self.session.execute(delete_stmt, {"scorecard_id": str(scorecard_id)})

            count = 0
            for item_data in score_items:
                extracted_json = json.dumps(item_data.get("extracted_data")) if item_data.get("extracted_data") else None
                stmt = text("""
                    INSERT INTO lead_score_items 
                        (scorecard_id, criterion_key, score, band_id, explanation, extracted_data)
                    VALUES 
                        (CAST(:scorecard_id AS uuid), :criterion_key, :score, CAST(:band_id AS uuid), :explanation, CAST(:extracted_data AS jsonb))
                """)
                await self.session.execute(stmt, {
                    "scorecard_id": str(scorecard_id),
                    "criterion_key": item_data["criterion_key"],
                    "score": item_data["score"],
                    "band_id": str(item_data["band_id"]) if item_data.get("band_id") else None,
                    "explanation": item_data.get("explanation"),
                    "extracted_data": extracted_json
                })
                count += 1
            
            logger.debug(f"Created {count} score items for scorecard {scorecard_id}")
            return count
            
        except Exception as e:
            logger.error(f"Error creating score items: {e}")
            raise
    
    async def update_lead_current_scorecard(self, lead_id: UUID, scorecard_id: UUID) -> bool:
        """Update lead's current_scorecard_id reference"""
        try:
            stmt = text("""
                UPDATE lead_leads
                SET current_scorecard_id = :scorecard_id
                WHERE id = :lead_id
            """)
            await self.session.execute(stmt, {
                "scorecard_id": str(scorecard_id),
                "lead_id": str(lead_id)
            })
            logger.debug(f"Updated lead {lead_id} with current_scorecard_id {scorecard_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating lead current scorecard: {e}")
            raise
    
    async def update_lead_from_extraction(
        self,
        lead_id: UUID,
        extracted_data: Dict[str, Any]
    ) -> bool:
        """Update lead with extracted data from scoring"""
        try:
            updates = {}
            if extracted_data.get("extracted_name"):
                updates["full_name"] = extracted_data["extracted_name"]
            if extracted_data.get("extracted_email"):
                updates["email"] = extracted_data["extracted_email"]
            if extracted_data.get("extracted_phone"):
                updates["phone"] = extracted_data["extracted_phone"]
            
            if not updates:
                return False
            
            set_clauses = []
            params = {"lead_id": str(lead_id)}
            for key, value in updates.items():
                set_clauses.append(f"{key} = :{key}")
                params[key] = value
            
            stmt = text(f"""
                UPDATE lead_leads
                SET {', '.join(set_clauses)}
                WHERE id = :lead_id
            """)
            await self.session.execute(stmt, params)
            logger.debug(f"Updated lead {lead_id} with extracted data: {updates}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating lead from extraction: {e}")
            raise
    
    async def get_lead_by_conversation_id(
        self,
        conversation_id: str,
        client_id: UUID
    ) -> Optional[UUID]:
        """
        Find lead by conversation_id from lead_conversations table.
        Returns lead_id if found, None otherwise.
        """
        try:
            stmt = text("""
                SELECT lc.lead_id
                FROM lead_conversations lc
                JOIN lead_leads ll ON ll.id = lc.lead_id
                WHERE lc.conversation_id = :conversation_id
                  AND ll.client_id = :client_id
                LIMIT 1
            """)
            res = await self.session.execute(stmt, {
                "conversation_id": conversation_id,
                "client_id": str(client_id)
            })
            row = res.fetchone()
            if row:
                return UUID(str(row[0]))
            return None
        except Exception as e:
            logger.warning(f"Error looking up lead by conversation_id: {e}")
            return None
    
    async def get_or_create_lead(
        self,
        client_id: UUID,
        lead_type: str,
        business_domain: Optional[str] = None,
        user_metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> UUID:
        """
        Returns an existing tenant-scoped lead when provided via metadata, otherwise creates one.
        Optionally creates a lead_conversations record if conversation_id is provided.
        """
        metadata = user_metadata or {}
        existing_lead_id = metadata.get("lead_id")
        if existing_lead_id:
            try:
                stmt = text("""
                    SELECT id FROM lead_leads
                    WHERE id = :lead_id AND client_id = :client_id
                """)
                res = await self.session.execute(stmt, {
                    "lead_id": str(existing_lead_id),
                    "client_id": str(client_id)
                })
                row = res.fetchone()
                if row:
                    return UUID(str(row[0]))
            except Exception:
                logger.warning("Ignoring invalid lead_id from metadata: %s", existing_lead_id)

        full_name = (
            metadata.get("full_name")
            or metadata.get("extracted_name")
            or f"Lead {str(client_id)[:8]}"
        )
        source_id = metadata.get("source_id", 14)

        insert_stmt = text("""
            INSERT INTO lead_leads (id, client_id, source_id, full_name, lead_type, business_domain, created_at)
            VALUES (gen_random_uuid(), :client_id, :source_id, :full_name, :lead_type, :business_domain, NOW())
            RETURNING id
        """)
        result = await self.session.execute(insert_stmt, {
            "client_id": str(client_id),
            "source_id": source_id,
            "full_name": full_name,
            "lead_type": lead_type,
            "business_domain": business_domain,
        })
        new_lead_id = result.scalar_one()
        
        if conversation_id:
            try:
                conv_stmt = text("""
                    INSERT INTO lead_conversations (id, lead_id, platform, conversation_id, messages)
                    VALUES (gen_random_uuid(), :lead_id, 'webchat', :conversation_id, '[]'::jsonb)
                """)
                await self.session.execute(conv_stmt, {
                    "lead_id": str(new_lead_id),
                    "conversation_id": conversation_id
                })
            except Exception as e:
                logger.warning(f"Error creating lead_conversation record: {e}")
        
        return UUID(str(new_lead_id))
    
    async def get_latest_scorecard(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get current scorecard for a lead, fallback to latest by created_at"""
        try:
            current_stmt = text("""
                SELECT l.current_scorecard_id
                FROM lead_leads l
                WHERE l.id = :lead_id
            """)
            current_result = await self.session.execute(current_stmt, {"lead_id": str(lead_id)})
            current_row = current_result.fetchone()
            current_scorecard_id = current_row[0] if current_row else None

            if current_scorecard_id:
                stmt = text("""
                    SELECT id, lead_id, conversation_id, model_id, model_version, prompt_version,
                           prompt_id, prompt_snapshot, score_total, priority_label, reasoning,
                           extraction_result, raw_payload, created_at
                    FROM lead_scorecards
                    WHERE id = :scorecard_id
                    LIMIT 1
                """)
                result = await self.session.execute(stmt, {"scorecard_id": str(current_scorecard_id)})
                row = result.mappings().first()
            else:
                stmt = text("""
                    SELECT id, lead_id, conversation_id, model_id, model_version, prompt_version,
                           prompt_id, prompt_snapshot, score_total, priority_label, reasoning,
                           extraction_result, raw_payload, created_at
                    FROM lead_scorecards
                    WHERE lead_id = :lead_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = await self.session.execute(stmt, {"lead_id": str(lead_id)})
                row = result.mappings().first()

            if not row:
                return None
            
            scorecard = dict(row)
            
            # Get score items
            items_stmt = text("""
                SELECT id, criterion_key, score, band_id, explanation, extracted_data, created_at
                FROM lead_score_items
                WHERE scorecard_id = :scorecard_id
            """)
            items_result = await self.session.execute(items_stmt, {"scorecard_id": scorecard["id"]})
            scorecard["score_items"] = [dict(r) for r in items_result.mappings().all()]
            
            return scorecard
            
        except Exception as e:
            logger.error(f"Error getting latest scorecard: {e}")
            raise
    
    async def get_scorecard_with_items(self, scorecard_id: UUID) -> Optional[Dict[str, Any]]:
        """Get scorecard with all items"""
        try:
            stmt = text("""
                SELECT id, lead_id, conversation_id, model_id, model_version, prompt_version,
                       prompt_id, prompt_snapshot, score_total, priority_label, reasoning,
                       extraction_result, raw_payload, created_at
                FROM lead_scorecards
                WHERE id = :scorecard_id
            """)
            result = await self.session.execute(stmt, {"scorecard_id": str(scorecard_id)})
            row = result.mappings().first()
            if not row:
                return None
            
            scorecard = dict(row)
            
            # Get score items
            items_stmt = text("""
                SELECT id, criterion_key, score, band_id, explanation, extracted_data, created_at
                FROM lead_score_items
                WHERE scorecard_id = :scorecard_id
            """)
            items_result = await self.session.execute(items_stmt, {"scorecard_id": str(scorecard_id)})
            scorecard["score_items"] = [dict(r) for r in items_result.mappings().all()]
            
            return scorecard
            
        except Exception as e:
            logger.error(f"Error getting scorecard with items: {e}")
            raise
    
    async def get_scorecards_for_lead(self, lead_id: UUID, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scorecards for a lead"""
        try:
            stmt = text("""
                SELECT id, lead_id, conversation_id, model_id, model_version, prompt_version,
                       prompt_id, prompt_snapshot, score_total, priority_label, reasoning,
                       extraction_result, raw_payload, created_at
                FROM lead_scorecards
                WHERE lead_id = :lead_id
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await self.session.execute(stmt, {
                "lead_id": str(lead_id),
                "limit": limit
            })
            scorecards = [dict(r) for r in result.mappings().all()]
            
            # Get items for each scorecard
            for sc in scorecards:
                items_stmt = text("""
                    SELECT id, criterion_key, score, band_id, explanation, extracted_data, created_at
                    FROM lead_score_items
                    WHERE scorecard_id = :scorecard_id
                """)
                items_result = await self.session.execute(items_stmt, {"scorecard_id": sc["id"]})
                sc["score_items"] = [dict(r) for r in items_result.mappings().all()]
            
            return scorecards
            
        except Exception as e:
            logger.error(f"Error getting scorecards for lead: {e}")
            raise
    
    async def get_active_prompt(self, model_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get active prompt for scoring model using raw SQL
        """
        query = text("""
            SELECT id, model_id, version, prompt_template, extraction_schema, is_active
            FROM lead_scoring_prompts
            WHERE model_id = :model_id
              AND is_active = true
            ORDER BY version DESC
            LIMIT 1
        """)
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
            "is_active": row["is_active"]
        }

    async def get_client_system_prompt(self, client_id: UUID, slug: str = "primary_chat") -> Optional[str]:
        """
        Get system prompt for chat (from lead_ai_prompts)
        """
        # Try client-specific prompt first
        query = text("""
            SELECT prompt_text FROM lead_ai_prompts
            WHERE client_id = :client_id
              AND slug = :slug
              AND is_active = true
            LIMIT 1
        """)
        result = await self.session.execute(query, {"client_id": str(client_id), "slug": slug})
        row = result.mappings().first()
        if row:
            return row["prompt_text"]
        
        # Fallback to global prompt (client_id IS NULL)
        query = text("""
            SELECT prompt_text FROM lead_ai_prompts
            WHERE client_id IS NULL
              AND slug = :slug
              AND is_active = true
            LIMIT 1
        """)
        result = await self.session.execute(query, {"slug": slug})
        row = result.mappings().first()
        if row:
            return row["prompt_text"]
        
        return None
    
    async def upsert_scorecard(
        self,
        lead_id: UUID,
        model_id: UUID,
        model_version: int,
        prompt_version: int,
        prompt_id: Optional[UUID],
        prompt_snapshot: str,
        score_total: float,
        priority_label: Optional[str] = None,
        reasoning: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
        new_extraction_result: Optional[Dict[str, Any]] = None,
        raw_payload: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Insert or update single scorecard for a lead (concurrency-safe)"""
        lead_lock_stmt = text("""
            SELECT current_scorecard_id
            FROM lead_leads
            WHERE id = :lead_id
            FOR UPDATE
        """)
        lock_result = await self.session.execute(lead_lock_stmt, {"lead_id": str(lead_id)})
        lead_row = lock_result.fetchone()
        if not lead_row:
            raise ValueError(f"Lead not found: {lead_id}")

        existing_scorecard_id = lead_row[0]
        if not existing_scorecard_id:
            latest_stmt = text("""
                SELECT id
                FROM lead_scorecards
                WHERE lead_id = :lead_id
                ORDER BY created_at DESC
                LIMIT 1
                FOR UPDATE
            """)
            latest_res = await self.session.execute(latest_stmt, {"lead_id": str(lead_id)})
            latest_row = latest_res.fetchone()
            if latest_row:
                existing_scorecard_id = latest_row[0]

        merged_extraction = {}

        if existing_scorecard_id:
            existing_stmt = text("""
                SELECT extraction_result
                FROM lead_scorecards
                WHERE id = :scorecard_id
                FOR UPDATE
            """)
            existing_res = await self.session.execute(
                existing_stmt,
                {"scorecard_id": str(existing_scorecard_id)}
            )
            existing_row = existing_res.fetchone()
            existing_extraction = existing_row[0] if existing_row else None

            try:
                if isinstance(existing_extraction, str):
                    merged_extraction = json.loads(existing_extraction)
                else:
                    merged_extraction = existing_extraction or {}
            except Exception:
                merged_extraction = {}

        merged_extraction = self._normalize_extraction_result(merged_extraction)
        cleaned_new_extraction = self._normalize_extraction_result(new_extraction_result)
        if cleaned_new_extraction:
            merged_extraction.update(cleaned_new_extraction)
        
        extraction_json = json.dumps(merged_extraction) if merged_extraction else None
        raw_json = json.dumps(raw_payload) if raw_payload else None
        
        if existing_scorecard_id:
            stmt = text("""
                UPDATE lead_scorecards
                SET conversation_id = CAST(:conversation_id AS uuid),
                    model_id = CAST(:model_id AS uuid),
                    model_version = :model_version,
                    prompt_version = :prompt_version,
                    prompt_id = CAST(:prompt_id AS uuid),
                    prompt_snapshot = :prompt_snapshot,
                    score_total = :score_total,
                    priority_label = :priority_label,
                    reasoning = :reasoning,
                    extraction_result = CAST(:extraction_result AS jsonb),
                    raw_payload = CAST(:raw_payload AS jsonb)
                WHERE id = :scorecard_id
                RETURNING id
            """)
            result = await self.session.execute(stmt, {
                "conversation_id": str(conversation_id) if conversation_id else None,
                "model_id": str(model_id),
                "model_version": model_version,
                "prompt_version": prompt_version,
                "prompt_id": str(prompt_id) if prompt_id else None,
                "prompt_snapshot": prompt_snapshot,
                "score_total": score_total,
                "priority_label": priority_label,
                "reasoning": reasoning,
                "extraction_result": extraction_json,
                "raw_payload": raw_json,
                "scorecard_id": str(existing_scorecard_id)
            })
            scorecard_id = result.scalar_one()
        else:
            stmt = text("""
                INSERT INTO lead_scorecards 
                    (lead_id, conversation_id, model_id, model_version, prompt_version, 
                     prompt_id, prompt_snapshot, score_total, priority_label, reasoning, 
                     extraction_result, raw_payload)
                VALUES 
                    (CAST(:lead_id AS uuid), CAST(:conversation_id AS uuid), CAST(:model_id AS uuid), 
                     :model_version, :prompt_version, CAST(:prompt_id AS uuid), :prompt_snapshot, 
                     :score_total, :priority_label, :reasoning, 
                     CAST(:extraction_result AS jsonb), CAST(:raw_payload AS jsonb))
                RETURNING id
            """)
            result = await self.session.execute(stmt, {
                "lead_id": str(lead_id),
                "conversation_id": str(conversation_id) if conversation_id else None,
                "model_id": str(model_id),
                "model_version": model_version,
                "prompt_version": prompt_version,
                "prompt_id": str(prompt_id) if prompt_id else None,
                "prompt_snapshot": prompt_snapshot,
                "score_total": score_total,
                "priority_label": priority_label,
                "reasoning": reasoning,
                "extraction_result": extraction_json,
                "raw_payload": raw_json
            })
            scorecard_id = result.scalar_one()

        await self.session.execute(text("""
            UPDATE lead_leads
            SET current_scorecard_id = :scorecard_id
            WHERE id = :lead_id
        """), {
            "scorecard_id": str(scorecard_id),
            "lead_id": str(lead_id),
        })
        
        return UUID(str(scorecard_id))
