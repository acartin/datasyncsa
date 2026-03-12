"""
Property Bridge V2
Adapts property-specific chat requests to the active inference-core API
Maintains compatibility with existing property integrations
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict, AliasChoices
from pydantic.alias_generators import to_camel
import httpx
import os


# Configuration
INFERENCE_API_URL = os.getenv("INFERENCE_API_URL", os.getenv("INFERENCE_V2_URL", "http://localhost:8000"))
INFERENCE_API_PREFIX = os.getenv("INFERENCE_API_PREFIX", os.getenv("INFERENCE_V2_API_PREFIX", "/api/v3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("property-bridge-v2")

# FastAPI app
app = FastAPI(
    title="Property Bridge V2",
    description="Adapts property chat requests to the active inference core",
    version="2.0.0"
)


class PropertyChatRequest(BaseModel):
    """Property chat request (compatible with existing contract)"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore"
    )
    
    query_text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("query_text", "queryText", "text"),
    )
    client_id: UUID = Field(
        ...,
        description="Tenant/client identifier",
        validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId"),
    )
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    conversation_id: Optional[UUID] = Field(None)
    user_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SourceDocument(BaseModel):
    """Source document for backward compatibility"""
    content_id: str
    title: Optional[str] = None
    body_content: str
    score: float
    metadata: Dict[str, Any]


class LeadScoringResult(BaseModel):
    """Legacy scoring result for backward compatibility"""
    score_engagement: int = Field(0)
    score_finance: int = Field(0)
    score_timeline: int = Field(0)
    score_match: int = Field(0)
    score_info: int = Field(0)
    reasoning: str = Field("")
    
    # Extracted fields
    extracted_name: Optional[str] = None
    extracted_email: Optional[str] = None
    extracted_phone: Optional[str] = None
    extracted_income: Optional[float] = None
    extracted_debts: Optional[float] = None
    extracted_currency_id: Optional[str] = None
    extracted_contact_pref_id: Optional[str] = None


class PropertyChatResponse(BaseModel):
    """Property chat response (compatible with existing contract)"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    answer: str
    sources: list[SourceDocument] = Field(default_factory=list)
    conversation_id: UUID
    lead_scoring: Optional[LeadScoringResult] = None
    scoring_status: Optional[str] = None
    scoring_job_id: Optional[UUID] = None
    scoring_eta: Optional[str] = None


class AsyncHTTPClient:
    """Async HTTP client for the active inference core"""
    
    def __init__(self):
        self.client = None
        self.base_url = f"{INFERENCE_API_URL}{INFERENCE_API_PREFIX}"
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def post_with_retry(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        retries: int = MAX_RETRIES
    ) -> httpx.Response:
        """POST request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{retries}: POST {url}")
                response = await self.client.post(url, json=payload)
                
                if response.status_code < 500 or attempt == retries - 1:
                    return response
                
                logger.warning(f"Attempt {attempt + 1} failed: {response.status_code}")
                await asyncio.sleep(2 ** attempt)
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        
        raise httpx.RequestError("Max retries exceeded")
    
def map_v2_scorecard_to_legacy(scorecard: Dict[str, Any]) -> LeadScoringResult:
    """
    Map v2 scorecard to legacy scoring format
    
    This is a simplified mapping for backward compatibility.
    In production, would need business logic to map criteria to legacy pillars.
    """
    if not scorecard:
        return LeadScoringResult(
            score_engagement=0,
            score_finance=0,
            score_timeline=0,
            score_match=0,
            score_info=0,
            reasoning="No scoring available",
        )
    
    # Extract scores from v2 score items
    engagement_score = 0
    finance_score = 0
    timeline_score = 0
    match_score = 0
    info_score = 0
    
    score_items = scorecard.get("score_items") or scorecard.get("scoreItems") or []
    for item in score_items:
        criterion = item.get("criterion_key", "")
        score = item.get("score", 0)
        
        # Map v2 criteria to legacy pillars (simplified)
        if "intent" in criterion or "urgency" in criterion:
            engagement_score = int(score * 3)  # Scale to legacy range
        elif "finance" in criterion or "budget" in criterion:
            finance_score = int(score * 3)
        elif "timeline" in criterion or "timeframe" in criterion:
            timeline_score = int(score * 2)
        elif "match" in criterion or "fit" in criterion:
            match_score = int(score * 1.5)
        elif "data" in criterion or "quality" in criterion:
            info_score = int(score * 0.5)
    
    # Ensure scores are within legacy ranges
    engagement_score = max(-20, min(30, engagement_score))
    finance_score = max(-10, min(30, finance_score))
    timeline_score = max(0, min(20, timeline_score))
    match_score = max(0, min(15, match_score))
    info_score = max(-3, min(5, info_score))
    
    return LeadScoringResult(
        score_engagement=engagement_score,
        score_finance=finance_score,
        score_timeline=timeline_score,
        score_match=match_score,
        score_info=info_score,
        reasoning=scorecard.get("reasoning", "Scoring calculated with v2 model"),
        # Note: Extracted fields would come from score_items extracted_data
    )


@app.post("/chat", response_model=PropertyChatResponse)
async def chat_endpoint(request: PropertyChatRequest):
    """
    Property chat endpoint with backward compatibility
    
    Forwards to the active inference core
    Maps scorecards to legacy format for frontend compatibility
    """
    start_time = time.time()
    
    try:
        request_payload = {
            "queryText": request.query_text,
            "clientId": str(request.client_id),
            "businessDomain": None,  # Optional for future use
            "conversationId": str(request.conversation_id) if request.conversation_id else None,
            "userMetadata": request.user_metadata,
            "filters": request.filters
        }
        
        # Forward to inference core
        async with AsyncHTTPClient() as http_client:
            response = await http_client.post_with_retry("/chat", request_payload)
            
            if response.status_code >= 400:
                logger.error(f"Inference core error: {response.status_code} - {response.text}")
                
                if response.status_code == 400:
                    error_data = response.json()
                    raise HTTPException(status_code=400, detail=error_data.get("detail", "Bad request"))
                elif response.status_code == 404:
                    error_data = response.json()
                    raise HTTPException(status_code=404, detail=error_data.get("detail", "Not found"))
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Bad gateway: {response.status_code}"
                    )
            
            # Parse core response
            core_response = response.json()

            def pick(payload: Dict[str, Any], *keys: str):
                for key in keys:
                    if key in payload:
                        return payload[key]
                return None
            
            # Get legacy scoring if available
            legacy_scoring = None
            scorecard_payload = core_response.get("scorecard")
            if scorecard_payload:
                legacy_scoring = map_v2_scorecard_to_legacy(scorecard_payload)

            scoring_status = pick(core_response, "scoringStatus", "scoring_status")
            scoring_eta = pick(core_response, "scoringEta", "scoring_eta")
            scoring_job_id = None
            raw_scoring_job_id = pick(core_response, "scoringJobId", "scoring_job_id")
            if raw_scoring_job_id:
                try:
                    scoring_job_id = UUID(str(raw_scoring_job_id))
                except ValueError:
                    logger.warning("Invalid scoring_job_id in core response: %s", raw_scoring_job_id)
            
            # Build property response
            property_response = PropertyChatResponse(
                answer=core_response["answer"],
                conversation_id=UUID(pick(core_response, "conversationId", "conversation_id")),
                lead_scoring=legacy_scoring,
                scoring_status=scoring_status,
                scoring_job_id=scoring_job_id,
                scoring_eta=scoring_eta,
            )
            
            # Note: Sources would need to be populated from v2_response if available
            # This is a placeholder - actual implementation would map sources
            
            logger.info(
                f"Property chat processed: client={request.client_id}, "
                f"conversation={property_response.conversation_id}, "
                f"scoring_status={property_response.scoring_status}, "
                f"processing_time={int((time.time() - start_time) * 1000)}ms"
            )
            
            return property_response
    
    except HTTPException:
        raise
    except httpx.RequestError as e:
        logger.error(f"Connection error to inference core: {e}")
        raise HTTPException(status_code=503, detail="Scoring service unavailable")
    except Exception as e:
        logger.exception(f"Unexpected error in /chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check inference-core health
        inference_status = "unknown"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{INFERENCE_API_URL}{INFERENCE_API_PREFIX}/health")
                if response.status_code == 200:
                    data = response.json()
                    inference_status = data.get("status", "unknown")
                else:
                    inference_status = f"error_{response.status_code}"
            except Exception as e:
                logger.warning(f"Health check failed for inference core: {e}")
                inference_status = "unreachable"
        
        return {
            "status": "healthy",
            "service": "property-bridge-v2",
            "inference_status": inference_status,
            "vertical": "real-estate"
        }
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "property-bridge-v2",
        "version": "2.0.0",
        "description": "Adapts property chat requests to the active inference core",
        "vertical": "real-estate",
        "endpoints": {
            "POST /chat": "Property chat with backward-compatible scoring",
            "GET /health": "Health check with dependency status"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info"
    )
