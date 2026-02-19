import logging
import asyncio
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_v2 import ChatV2Request, ChatV2Response, ScoreItemV2, ScorecardV2
from app.repositories.scoring_repository import ScoringRepository
from app.services.cache_service import cache_service
from app.core.config import settings

logger = logging.getLogger("inference-core-v2.orchestrator")


class ScoringOrchestrator:
    """Orchestrator for v2 chat and scoring"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repo = ScoringRepository(db_session)
        self._scoring_engine = None
    
    @property
    def scoring_engine(self):
        """Lazy initialization of scoring engine"""
        if self._scoring_engine is None and settings.google_api_key:
            try:
                from app.services.scoring_engine import scoring_engine
                self._scoring_engine = scoring_engine
            except ImportError:
                logger.warning("ScoringEngine not available - google-genai not installed")
        return self._scoring_engine
    
    async def get_active_scoring_model(
        self,
        vertical_id: int,
        business_domain: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get active scoring model with caching"""
        cached = await cache_service.get_active_model(vertical_id, business_domain)
        if cached:
            logger.debug(f"Cache hit for active model: vertical={vertical_id}")
            return cached
        
        model_data = await self.repo.get_active_scoring_model(vertical_id, business_domain)
        if not model_data:
            logger.warning(f"No active model found: vertical={vertical_id}, domain={business_domain}")
            return None
        
        await cache_service.set_active_model(vertical_id, business_domain, model_data)
        return model_data

    async def resolve_vertical_for_client(self, client_id: UUID) -> Dict[str, Any]:
        """Resolve vertical context from tenant configuration."""
        vertical_ctx = await self.repo.get_client_vertical_context(client_id)
        if not vertical_ctx or not vertical_ctx.get("client_exists"):
            raise ValueError("CLIENT_NOT_FOUND")
        if vertical_ctx.get("vertical_id") is None:
            raise ValueError("TENANT_VERTICAL_NOT_CONFIGURED")
        return vertical_ctx

    @staticmethod
    def derive_lead_type_from_vertical(vertical_ctx: Dict[str, Any]) -> str:
        """Derive a lead_type string for lead_leads from vertical metadata."""
        slug = (vertical_ctx.get("vertical_slug") or "").strip().lower()
        if slug:
            return slug[:32]
        name = (vertical_ctx.get("vertical_name") or "generic").strip().lower()
        normalized = name.replace(" ", "_").replace("-", "_")
        return normalized[:32] if normalized else "generic"
    
    async def get_or_create_prompt(
        self,
        model_data: Dict[str, Any],
        vertical_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get active prompt - must be configured in database"""
        model_id = UUID(model_data["id"])
        
        prompt_config = await self.repo.get_active_prompt(model_id)
        
        if not prompt_config:
            raise ValueError(f"No active prompt found for model {model_id} - please configure prompt in database")
        
        return prompt_config
    
    async def process_chat(self, request: ChatV2Request) -> ChatV2Response:
        """
        Process chat request with v2 scoring.
        
        Scoring runs in background and does not block the response.
        """
        try:
            vertical_ctx = await self.resolve_vertical_for_client(request.client_id)
            vertical_id = int(vertical_ctx["vertical_id"])
            lead_type = self.derive_lead_type_from_vertical(vertical_ctx)

            model_data = await self.get_active_scoring_model(
                vertical_id=vertical_id,
                business_domain=request.business_domain
            )
            
            if not model_data:
                raise ValueError(
                    f"NO_ACTIVE_VERTICAL_SCORING_MODEL: vertical_id={vertical_id}, business_domain={request.business_domain}"
                )
            
            answer = "This is a placeholder response from v2 inference engine."
            
            conversation_id = request.conversation_id or uuid4()
            
            existing_lead_id = None
            if request.conversation_id:
                existing_lead_id = await self.repo.get_lead_by_conversation_id(
                    conversation_id=str(request.conversation_id),
                    client_id=request.client_id
                )
            
            if existing_lead_id:
                lead_id = existing_lead_id
                logger.info(f"Reusing existing lead {lead_id} for conversation {request.conversation_id}")
            else:
                lead_id = await self.repo.get_or_create_lead(
                    client_id=request.client_id,
                    lead_type=lead_type,
                    business_domain=request.business_domain,
                    user_metadata=request.user_metadata or {},
                    conversation_id=str(conversation_id),
                )
            
            await self.db_session.commit()
            
            if not self.scoring_engine:
                raise ValueError("LLM_ENGINE_NOT_AVAILABLE: Scoring engine requires GOOGLE_API_KEY to be configured")
            
            asyncio.create_task(
                self._run_scoring_background(
                    lead_id=lead_id,
                    model_data=model_data,
                    vertical_ctx=vertical_ctx,
                    conversation_id=conversation_id,
                    query_text=request.query_text,
                    business_domain=request.business_domain,
                    lead_type=lead_type
                )
            )
            scorecard_id = None
            scorecard = None

            return ChatV2Response(
                answer=answer,
                conversation_id=conversation_id,
                lead_id=lead_id,
                scorecard_id=scorecard_id,
                scorecard=scorecard
            )
            
        except Exception as e:
            logger.error(f"Error processing chat request: {e}")
            raise
    
    async def _run_scoring_background(
        self,
        lead_id: UUID,
        model_data: Dict[str, Any],
        vertical_ctx: Dict[str, Any],
        conversation_id: UUID,
        query_text: str,
        business_domain: Optional[str] = None,
        lead_type: Optional[str] = None
    ):
        """Run scoring in background with retries"""
        from app.dependencies.database import AsyncSessionLocal
        
        max_retries = settings.scoring_max_retries
        retry_delay = settings.scoring_retry_delay_secs
        
        async with AsyncSessionLocal() as db_session:
            self.db_session = db_session
            self.repo = ScoringRepository(db_session)
            
            for attempt in range(1, max_retries + 1):
                try:
                    prompt_config = await self.get_or_create_prompt(model_data, vertical_ctx)
                    
                    conversation_text = f"Usuario: {query_text}\n"
                    
                    result = await self.scoring_engine.analyze_conversation(
                        conversation_text=conversation_text,
                        model_config={
                            **model_data,
                            "vertical_name": vertical_ctx.get("vertical_name", "leads"),
                            "vertical_slug": vertical_ctx.get("vertical_slug", ""),
                            "business_domain": business_domain,
                            "lead_type": lead_type,
                        },
                        prompt_config=prompt_config
                    )
                    
                    scorecard_data = self._build_scorecard_from_result(
                        model_data=model_data,
                        result=result
                    )
                    
                    await self._create_scorecard_with_engine(
                        lead_id=lead_id,
                        model_data=model_data,
                        scorecard_data=scorecard_data,
                        prompt_config=prompt_config,
                        result=result,
                        conversation_id=conversation_id
                    )
                    
                    logger.info(f"Background scoring completed for lead {lead_id}")
                    return
                    
                except Exception as e:
                    logger.error(f"Background scoring attempt {attempt}/{max_retries} failed: {e}")
                    
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay * attempt)
                    else:
                        logger.error(f"All background scoring attempts failed for lead {lead_id}")
    
    def _build_scorecard_from_result(
        self,
        model_data: Dict[str, Any],
        result: Dict[str, Any]
    ) -> ScorecardV2:
        """Build ScorecardV2 from engine result"""
        scores = result.get("scores", {})
        explanations = result.get("explanations", {})
        
        score_items = []
        total_score = 0.0
        total_weight = 0.0
        
        for criterion in model_data.get("criteria", []):
            criterion_key = criterion.get("criterion_key")
            score = scores.get(criterion_key, 5.0)
            
            min_score = float(criterion.get("min_score", 0))
            max_score = float(criterion.get("max_score", 10))
            score = min(max(float(score), min_score), max_score)
            
            band_key = None
            for band in criterion.get("bands", []):
                if float(band.get("min_score", 0)) <= score < float(band.get("max_score", 10)):
                    band_key = band.get("band_key")
                    break
            
            explanation = explanations.get(criterion_key, f"Score for {criterion_key}")
            
            score_items.append(ScoreItemV2(
                criterion_key=criterion_key,
                score=score,
                band_key=band_key,
                explanation=explanation,
                extracted_data=None
            ))
            
            weight = float(criterion.get("weight", 1.0))
            total_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            normalized_total = total_score / total_weight
        else:
            normalized_total = 0.0
        
        priority_label = "medium"
        if normalized_total >= 8.0:
            priority_label = "high"
        elif normalized_total <= 3.0:
            priority_label = "low"
        
        return ScorecardV2(
            score_total=normalized_total,
            priority_label=priority_label,
            reasoning=result.get("reasoning", ""),
            model_version=model_data.get("version", 1),
            prompt_version=1,
            score_items=score_items
        )
    
    async def _create_scorecard_with_engine(
        self,
        lead_id: UUID,
        model_data: Dict[str, Any],
        scorecard_data: ScorecardV2,
        prompt_config: Dict[str, Any],
        result: Dict[str, Any],
        conversation_id: UUID
    ) -> UUID:
        """Create scorecard with prompt snapshot"""
        try:
            model_id_raw = model_data.get("id")
            model_id = UUID(str(model_id_raw)) if model_id_raw else None
            
            prompt_id_raw = prompt_config.get("id")
            prompt_id = UUID(str(prompt_id_raw)) if prompt_id_raw else None
            prompt_version = int(prompt_config.get("version", scorecard_data.prompt_version))
            
            prompt_snapshot = result.get("prompt_snapshot", "")
            extraction_result = result.get("extraction_result", {})
            
            scorecard_id = await self.repo.upsert_scorecard(
                lead_id=lead_id,
                model_id=model_id,
                model_version=scorecard_data.model_version,
                prompt_version=prompt_version,
                prompt_id=prompt_id,
                prompt_snapshot=prompt_snapshot,
                score_total=scorecard_data.score_total,
                priority_label=scorecard_data.priority_label,
                reasoning=scorecard_data.reasoning,
                conversation_id=conversation_id,
                new_extraction_result=extraction_result,
                raw_payload={
                    "scoring_metadata": {
                        "normalization_strategy": model_data.get("normalization_strategy"),
                        "criteria_count": len(scorecard_data.score_items),
                        "engine": "gemini"
                    }
                }
            )
            
            score_items_data = []
            for item in scorecard_data.score_items:
                item_data = {
                    "criterion_key": item.criterion_key,
                    "score": item.score,
                    "explanation": item.explanation,
                    "extracted_data": item.extracted_data
                }
                
                if item.band_key:
                    for criterion in model_data.get("criteria", []):
                        if criterion.get("criterion_key") == item.criterion_key:
                            for band in criterion.get("bands", []):
                                if band.get("band_key") == item.band_key:
                                    item_data["band_id"] = UUID(band["id"])
                                    break
                            break
                
                score_items_data.append(item_data)
            
            await self.repo.create_score_items(scorecard_id, score_items_data)
            await self.repo.update_lead_current_scorecard(lead_id, scorecard_id)
            await self.repo.update_lead_from_extraction(lead_id, extraction_result)
            await self.db_session.commit()
            
            return scorecard_id
            
        except Exception as e:
            logger.error(f"Error creating scorecard with engine: {e}")
            await self.db_session.rollback()
            raise
    
    async def _create_scorecard_sync(
        self,
        lead_id: UUID,
        model_data: Dict[str, Any],
        scorecard_data: ScorecardV2,
        conversation_id: UUID
    ) -> UUID:
        """Create scorecard synchronously (fallback)"""
        try:
            scorecard_id = await self.repo.create_scorecard(
                lead_id=lead_id,
                model_id=UUID(model_data["id"]),
                model_version=scorecard_data.model_version,
                prompt_version=scorecard_data.prompt_version,
                score_total=scorecard_data.score_total,
                priority_label=scorecard_data.priority_label,
                reasoning=scorecard_data.reasoning,
                conversation_id=conversation_id,
                raw_payload={
                    "scoring_metadata": {
                        "normalization_strategy": model_data.get("normalization_strategy"),
                        "criteria_count": len(scorecard_data.score_items),
                        "engine": "placeholder"
                    }
                }
            )
            
            score_items_data = []
            for item in scorecard_data.score_items:
                item_data = {
                    "criterion_key": item.criterion_key,
                    "score": item.score,
                    "explanation": item.explanation,
                    "extracted_data": item.extracted_data
                }
                
                if item.band_key:
                    for criterion in model_data["criteria"]:
                        if criterion["criterion_key"] == item.criterion_key:
                            for band in criterion["bands"]:
                                if band["band_key"] == item.band_key:
                                    item_data["band_id"] = UUID(band["id"])
                                    break
                            break
                
                score_items_data.append(item_data)
            
            await self.repo.create_score_items(scorecard_id, score_items_data)
            await self.repo.update_lead_current_scorecard(lead_id, scorecard_id)
            await self.db_session.commit()
            
            return scorecard_id
            
        except Exception as e:
            logger.error(f"Error creating scorecard: {e}")
            await self.db_session.rollback()
            raise
    
    async def get_latest_scorecard_response(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get latest scorecard for a lead"""
        scorecard = await self.repo.get_latest_scorecard(lead_id)
        if not scorecard:
            return None
        return self._build_scorecard_response(scorecard)
    
    async def get_scorecard_response(self, scorecard_id: UUID) -> Optional[Dict[str, Any]]:
        """Get specific scorecard"""
        scorecard = await self.repo.get_scorecard_with_items(scorecard_id)
        if not scorecard:
            return None
        return self._build_scorecard_response(scorecard)
    
    def _build_scorecard_response(self, scorecard: Dict[str, Any]) -> Dict[str, Any]:
        """Build scorecard response dictionary from repo dict"""
        extraction_result = scorecard.get("extraction_result")
        if extraction_result is None:
            extraction_result = {}

        score_items = []
        for item in scorecard.get("score_items", []):
            score_items.append({
                "criterion_key": item.get("criterion_key"),
                "score": item.get("score"),
                "band_id": str(item.get("band_id")) if item.get("band_id") else None,
                "explanation": item.get("explanation"),
                "extracted_data": item.get("extracted_data"),
                "created_at": item.get("created_at").isoformat() if item.get("created_at") else None
            })
        
        return {
            "id": str(scorecard.get("id")),
            "lead_id": str(scorecard.get("lead_id")),
            "conversation_id": str(scorecard.get("conversation_id")) if scorecard.get("conversation_id") else None,
            "model_id": str(scorecard.get("model_id")),
            "model_version": scorecard.get("model_version"),
            "prompt_version": scorecard.get("prompt_version"),
            "prompt_id": str(scorecard.get("prompt_id")) if scorecard.get("prompt_id") else None,
            "score_total": scorecard.get("score_total"),
            "priority_label": scorecard.get("priority_label"),
            "reasoning": scorecard.get("reasoning"),
            "extraction_result": extraction_result,
            "created_at": scorecard.get("created_at").isoformat() if scorecard.get("created_at") else None,
            "score_items": score_items
        }
