import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime
from app.core.config import settings

class ConversationRepository:
    def __init__(self):
        self.dsn = settings.agentic_db_url

    def _get_connection(self):
        return psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)

    def get_or_create_conversation(self, client_id: str, conversation_id: Optional[UUID] = None) -> Dict[str, Any]:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                if conversation_id:
                    cur.execute("SELECT * FROM lead_conversations WHERE id = %s", (str(conversation_id),))
                    conv = cur.fetchone()
                    if conv:
                        return dict(conv)
                
                # Logic strict: A new conversation ALWAYS implies a new Lead interaction flow
                # (or at least capturing a new lead session).
                # User Requirement: "when a new conversation enters, it must necessarily create a new lead"
                
                new_lead_id = str(uuid4())
                cur.execute(
                    "INSERT INTO lead_leads (id, client_id, source_id, full_name) VALUES (%s, %s, %s, %s)",
                    (new_lead_id, client_id, 14, f"User {client_id[:8]}")
                )
                lead_id = new_lead_id

                new_conv_id = str(conversation_id or uuid4())
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

    def get_system_prompt(self, client_id: str, slug: str = 'primary_chat') -> str:
        """
        Recupera el prompt de sistema para un cliente específico o el global por defecto.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Intentar obtener prompt específico del cliente
                cur.execute(
                    "SELECT prompt_text FROM lead_ai_prompts WHERE client_id = %s AND slug = %s AND is_active = true",
                    (client_id, slug)
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
