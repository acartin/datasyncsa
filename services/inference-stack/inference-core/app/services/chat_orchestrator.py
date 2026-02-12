import httpx
import logging
import asyncio
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime
from google import genai
from google.genai import types

from app.core.config import settings
from app.models.chat import ChatMessageRequest, ChatMessageResponse, SourceDocument
from app.repositories.conversation_repo import ConversationRepository
from app.services.lead_analyzer import LeadAnalyzer

logger = logging.getLogger("inference-core.orchestrator")

class ChatOrchestrator:
    def __init__(self):
        self.repo = ConversationRepository()
        self.analyzer = LeadAnalyzer()
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.model_id = settings.LLM_MODEL
        self.semantic_url = f"{settings.SEMANTIC_ADAPTER_URL}/api/v1/search"

    async def chat(self, request: ChatMessageRequest) -> ChatMessageResponse:
        # 1. Get/Create conversation history
        conversation = self.repo.get_or_create_conversation(request.client_id, request.conversation_id)
        conv_id = conversation['id']
        history = conversation.get('messages', [])

        # 2. Retrieve Context from Semantic Adapter
        category = request.filters.get('category') if request.filters else None
        context_docs = await self._get_semantic_context(request.query_text, request.client_id, request.filters)
        
        # 3. Retrieve Dynamic System Prompt
        system_prompt_template = self.repo.get_system_prompt(request.client_id)
        
        # 4. Build Prompt Context
        context_text = "\n\n".join([f"Source {i+1}: {doc['body_content']}" for i, doc in enumerate(context_docs)])
        
        # Replace variable in system prompt
        # The original code expected {context_text} in the prompt template
        final_system_instruction = system_prompt_template.replace("{context_text}", context_text)

        # Convert history format for google-genai SDK
        # SDK expects a list of types.Content
        contents = []
        for msg in history[-10:]: # Last 10 messages for context
            role = 'user' if msg['role'] == 'user' else 'model'
            contents.append(types.Content(role=role, parts=[types.Part(text=msg.get('content', ''))]))

        # Add current message
        contents.append(types.Content(role='user', parts=[types.Part(text=request.query_text)]))

        # 5. Generate Answer
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=final_system_instruction,
                    temperature=0.2,
                )
            )
            answer = response.text
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            answer = "Lo siento, tuve un problema procesando tu solicitud."

        # Update History
        new_history = history + [
            {"role": "user", "content": request.query_text, "timestamp": str(datetime.now())},
            {"role": "assistant", "content": answer, "timestamp": str(datetime.now())}
        ]
        self.repo.update_conversation(UUID(conv_id), new_history)

        # 6. Background Task: Analyze Lead Scoring
        lead_id = conversation.get('lead_id')
        if lead_id:
            catalogs = self.repo.get_catalogs()
            asyncio.create_task(self._run_lead_analysis(lead_id, new_history, catalogs))

        # 7. Format Response
        sources = [
            SourceDocument(
                content_id=doc['content_id'],
                title=doc['title'],
                body_content=doc['body_content'],
                score=doc['score'],
                metadata=doc['metadata']
            ) for doc in context_docs
        ]

        return ChatMessageResponse(
            answer=answer,
            sources=sources,
            conversation_id=UUID(conv_id)
        )

    async def _get_semantic_context(self, query: str, client_id: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "query_text": query,
                    "client_id": client_id,
                    "top_k": 3,
                    "filters": filters or {}
                }

                response = await client.post(
                    self.semantic_url,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("results", [])
            except Exception as e:
                logger.error(f"Error calling semantic adapter: {e}")
                return []

    async def _run_lead_analysis(self, lead_id: str, history: List[Dict[str, Any]], catalogs: Dict[str, Any]):
        """
        Helper para ejecutar el análisis de lead en background.
        """
        try:
            scoring_result = await self.analyzer.analyze_conversation(history, catalogs)
            self.repo.update_lead_scores(lead_id, scoring_result.dict())
            logger.info(f"Lead {lead_id} scored: {scoring_result.reasoning}")
        except Exception as e:
            logger.error(f"Error in background lead analysis: {e}")

    def get_conversation_history(self, conversation_id: UUID) -> List[Dict[str, Any]]:
        conversation = self.repo.get_conversation(conversation_id)
        if not conversation:
            return []
        # Return the raw messages list
        return conversation.get('messages', [])
