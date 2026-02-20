import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import List, Dict, Any, Optional, Union
from uuid import UUID, uuid4
from datetime import datetime
from app.core.config import settings

class ConversationRepository:
    def __init__(self):
        self.dsn = settings.agentic_db_url

    def _get_connection(self):
        return psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)

    def _extract_click_id(self, user_metadata: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Returns normalized click_id + click_id_type.
        Priority: explicit click_id > known platform-specific IDs.
        """
        click_id = user_metadata.get("click_id")
        click_id_type = user_metadata.get("click_id_type")

        if click_id:
            return {"click_id": str(click_id), "click_id_type": str(click_id_type or "unknown")}

        platform_click_keys = [
            "gclid",
            "gbraid",
            "wbraid",
            "fbclid",
            "ttclid",
            "msclkid",
            "li_fat_id",
        ]
        for key in platform_click_keys:
            value = user_metadata.get(key)
            if value:
                return {"click_id": str(value), "click_id_type": key}

        return {"click_id": None, "click_id_type": None}

    def _normalize_lead_metadata(self, user_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        metadata = user_metadata or {}
        click_data = self._extract_click_id(metadata)
        return {
            "brand_project": metadata.get("brand_project") or metadata.get("project"),
            "utm_source": metadata.get("utm_source"),
            "utm_medium": metadata.get("utm_medium"),
            "utm_campaign": metadata.get("utm_campaign"),
            "utm_content": metadata.get("utm_content"),
            "utm_term": metadata.get("utm_term"),
            "click_id": click_data["click_id"],
            "click_id_type": click_data["click_id_type"],
            "source_property_ref": metadata.get("source_property_ref"),
            "source_property_url": metadata.get("source_property_url"),
            "landing_page_url": metadata.get("landing_page_url"),
            "referrer_url": metadata.get("referrer_url"),
            "user_agent": metadata.get("user_agent"),
            "ip_address": metadata.get("ip_address"),
        }

    def get_or_create_conversation(
        self,
        client_id: Union[str, UUID],
        conversation_id: Optional[UUID] = None,
        user_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        client_id_str = str(client_id)
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if conversation_id:
                    # Strict tenant isolation: only reuse a conversation if it belongs to the same client.
                    cur.execute(
                        """
                        SELECT lc.*
                        FROM lead_conversations lc
                        JOIN lead_leads ll ON ll.id = lc.lead_id
                        WHERE lc.id = %s
                          AND ll.client_id = %s
                        """,
                        (str(conversation_id), client_id_str),
                    )
                    conv = cur.fetchone()
                    if conv:
                        return dict(conv)
                
                # Logic strict: A new conversation ALWAYS implies a new Lead interaction flow
                # (or at least capturing a new lead session).
                # User Requirement: "when a new conversation enters, it must necessarily create a new lead"
                
                new_lead_id = str(uuid4())
                lead_metadata = self._normalize_lead_metadata(user_metadata)
                base_fields = {
                    "id": new_lead_id,
                    "client_id": client_id_str,
                    "source_id": 14,
                    "full_name": f"User {client_id_str[:8]}",
                }
                insert_data = {
                    **base_fields,
                    **{k: v for k, v in lead_metadata.items() if v not in (None, "")},
                }
                columns = ", ".join(insert_data.keys())
                placeholders = ", ".join(["%s"] * len(insert_data))
                cur.execute(
                    f"INSERT INTO lead_leads ({columns}) VALUES ({placeholders})",
                    tuple(insert_data.values())
                )
                lead_id = new_lead_id

                # If a conversation_id was provided but was not found for this tenant,
                # force a fresh ID to avoid collisions and cross-tenant reuse.
                new_conv_id = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO lead_conversations (id, lead_id, platform, messages)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (new_conv_id, lead_id, 'webchat', Json([]))
                )
                result = dict(cur.fetchone())
                conn.commit()
                return result

    def get_conversation(self, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM lead_conversations WHERE id = %s", (str(conversation_id),))
                conv = cur.fetchone()
                return dict(conv) if conv else None

    def delete_conversations_by_client(self, client_id: Union[str, UUID]) -> int:
        """
        Deletes all conversations associated to leads of a specific client.
        Returns number of deleted conversation rows.
        """
        client_id_str = str(client_id)
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM lead_conversations lc
                    USING lead_leads ll
                    WHERE lc.lead_id = ll.id
                      AND ll.client_id = %s
                    """,
                    (client_id_str,),
                )
                deleted = cur.rowcount or 0
                conn.commit()
                return deleted

    def update_conversation(self, conversation_id: UUID, new_messages: List[Dict[str, Any]], summary: Optional[str] = None):
        # Calcular contadores
        total = len(new_messages)
        lead_msgs = len([m for m in new_messages if m.get('role') == 'user'])
        bot_msgs = len([m for m in new_messages if m.get('role') == 'assistant'])
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE lead_conversations 
                    SET 
                        messages = %s, 
                        summary = %s, 
                        updated_at = %s,
                        last_message_at = %s,
                        total_messages = %s,
                        lead_messages = %s,
                        bot_messages = %s
                    WHERE id = %s
                    """,
                    (
                        Json(new_messages), 
                        summary, 
                        datetime.now(), 
                        datetime.now(),
                        total,
                        lead_msgs,
                        bot_msgs,
                        str(conversation_id)
                    )
                )
                conn.commit()

    def get_system_prompt(self, client_id: Union[str, UUID], slug: str = 'primary_chat') -> str:
        """
        Recupera el prompt de sistema para un cliente específico o el global por defecto.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                client_id_str = str(client_id)
                # 1. Intentar obtener prompt específico del cliente
                cur.execute(
                    "SELECT prompt_text FROM lead_ai_prompts WHERE client_id = %s AND slug = %s AND is_active = true",
                    (client_id_str, slug)
                )
                row = cur.fetchone()
                if row:
                    return row['prompt_text']
                
                # 2. Intentar obtener prompt global (client_id es NULL)
                cur.execute(
                    "SELECT prompt_text FROM lead_ai_prompts WHERE client_id IS NULL AND slug = %s AND is_active = true",
                    (slug,)
                )
                row = cur.fetchone()
                if row:
                    return row['prompt_text']
                
                # 3. Fallback de seguridad en código
                return "Eres un asistente técnico. Responde basándote exclusivamente en el contexto:\n\n{context_text}"

    def get_catalogs(self) -> Dict[str, Any]:
        """
        Retrieves valid currencies and contact preferences for the LLM context.
        """
        params = {}
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM lead_currencies")
                params['currencies'] = [r['id'] for r in cur.fetchall()]
                
                cur.execute("SELECT id, name FROM lead_contact_preferences WHERE active = true")
                params['preferences'] = [{str(r['id']): r['name']} for r in cur.fetchall()]
        return params

    def update_lead_scores(self, lead_id: str, scores: Dict[str, Any]):
        """
        Updates lead scores and extracted fields if present.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Base Score Update
                cur.execute(
                    """
                    UPDATE lead_leads 
                    SET 
                        score_engagement = %s,
                        score_finance = %s,
                        score_timeline = %s,
                        score_match = %s,
                        score_info = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        scores['score_engagement'],
                        scores['score_finance'],
                        scores['score_timeline'],
                        scores['score_match'],
                        scores['score_info'],
                        datetime.now(),
                        lead_id
                    )
                )

                # 2. Conditional Field Updates (only if extracted value is not None)
                # We do this individually or build a dynamic query to avoid overwriting existig data with NULL
                # if the LLM didn't find it this turn.
                
                updates = []
                params = []
                
                if scores.get('extracted_name'):
                    updates.append("full_name = %s")
                    params.append(scores['extracted_name'])
                
                if scores.get('extracted_email'):
                    updates.append("email = %s")
                    params.append(scores['extracted_email'])
                    
                if scores.get('extracted_phone'):
                    updates.append("phone = %s")
                    params.append(scores['extracted_phone'])

                if scores.get('extracted_income') is not None:
                    updates.append("declared_income = %s")
                    params.append(scores['extracted_income'])
                    
                if scores.get('extracted_debts') is not None:
                    updates.append("current_debts = %s")
                    params.append(scores['extracted_debts'])
                    
                if scores.get('extracted_currency_id'):
                    updates.append("financial_currency_id = %s")
                    params.append(scores['extracted_currency_id'])

                if scores.get('extracted_contact_pref_id'):
                    updates.append("contact_preference_id = %s")
                    params.append(scores['extracted_contact_pref_id'])

                if updates:
                    sql = f"UPDATE lead_leads SET {', '.join(updates)} WHERE id = %s"
                    params.append(lead_id)
                    cur.execute(sql, tuple(params))
                
                conn.commit()
