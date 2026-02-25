"""
Generic Bridge V2
Adapts generic chat requests to inference-core-v2 API
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
INFERENCE_V2_URL = os.getenv("INFERENCE_V2_URL", "http://localhost:8000")
INFERENCE_V2_API_PREFIX = os.getenv("INFERENCE_V2_API_PREFIX", "/api/v2")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generic-bridge-v2")

# FastAPI app
app = FastAPI(
    title="Generic Bridge V2",
    description="Adapts generic chat requests to inference-core-v2",
    version="2.0.0"
)


class GenericChatRequest(BaseModel):
    """Generic chat request contract"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
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
    business_domain: Optional[str] = Field(None, description="Optional business domain")
    conversation_id: Optional[UUID] = Field(None, description="Existing conversation ID")
    user_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GenericChatResponse(BaseModel):
    """Generic chat response contract"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    answer: str
    conversation_id: UUID
    lead_id: Optional[UUID] = None
    scorecard_id: Optional[UUID] = None
    scoring_status: Optional[str] = None
    scoring_job_id: Optional[UUID] = None
    scoring_eta: Optional[str] = None
    score_total: Optional[float] = None
    priority_label: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    inference_v2_status: str


class AsyncHTTPClient:
    """Async HTTP client with retry logic"""
    
    def __init__(self):
        self.client = None
        self.base_url = f"{INFERENCE_V2_URL}{INFERENCE_V2_API_PREFIX}"
    
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
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        
        raise httpx.RequestError("Max retries exceeded")


def _pick(payload: Dict[str, Any], *keys: str):
    for key in keys:
        if key in payload:
            return payload[key]
    return None


@app.post("/chat", response_model=GenericChatResponse)
async def chat_endpoint(request: GenericChatRequest):
    """
    Generic chat endpoint that forwards to inference-core-v2
    
    Required:
    - query_text: User's question/message
    - client_id: Tenant/client identifier
    
    Optional:
    - business_domain: Additional granularity for model resolution
    - conversation_id: Continue existing conversation
    """
    start_time = time.time()
    
    try:
        # Build v2 request payload
        v2_payload = {
            "queryText": request.query_text,
            "clientId": str(request.client_id),
            "businessDomain": request.business_domain,
            "conversationId": str(request.conversation_id) if request.conversation_id else None,
            "userMetadata": request.user_metadata,
            "filters": request.filters
        }
        
        # Forward to inference-core-v2
        async with AsyncHTTPClient() as http_client:
            response = await http_client.post_with_retry("/chat", v2_payload)
            
            if response.status_code == 400:
                error_data = response.json()
                raise HTTPException(status_code=400, detail=error_data.get("detail", "Bad request"))
            
            if response.status_code == 404:
                error_data = response.json()
                raise HTTPException(status_code=404, detail=error_data.get("detail", "Not found"))
            
            if response.status_code >= 500:
                logger.error(f"Inference v2 error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=503,
                    detail="Scoring service temporarily unavailable"
                )
            
            if response.status_code != 200:
                logger.error(f"Unexpected response: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Bad gateway: {response.status_code}"
                )
            
            # Parse v2 response
            v2_response = response.json()
            
            # Build generic response
            generic_response = GenericChatResponse(
                answer=v2_response["answer"],
                conversation_id=UUID(_pick(v2_response, "conversationId", "conversation_id")),
                metadata={
                    "source": "inference-core-v2",
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            )

            generic_response.scoring_status = _pick(v2_response, "scoringStatus", "scoring_status")
            generic_response.scoring_eta = _pick(v2_response, "scoringEta", "scoring_eta")
            scoring_job_id = _pick(v2_response, "scoringJobId", "scoring_job_id")
            if scoring_job_id:
                try:
                    generic_response.scoring_job_id = UUID(str(scoring_job_id))
                except ValueError:
                    logger.warning("Invalid scoring_job_id in v2 response: %s", scoring_job_id)
            
            # Add scoring data if available
            if v2_response.get("scorecard"):
                scorecard = v2_response["scorecard"]
                scorecard_id = _pick(v2_response, "scorecardId", "scorecard_id")
                generic_response.scorecard_id = UUID(scorecard_id) if scorecard_id else None
                generic_response.score_total = _pick(scorecard, "scoreTotal", "score_total")
                generic_response.priority_label = _pick(scorecard, "priorityLabel", "priority_label")
                generic_response.metadata["scoring_model_version"] = _pick(scorecard, "modelVersion", "model_version")
                generic_response.metadata["scoring_prompt_version"] = _pick(scorecard, "promptVersion", "prompt_version")
            
            lead_id = _pick(v2_response, "leadId", "lead_id")
            if lead_id:
                generic_response.lead_id = UUID(lead_id)
            
            logger.info(
                f"Chat processed: client={request.client_id}, "
                f"conversation={generic_response.conversation_id}, "
                f"scoring_status={generic_response.scoring_status}"
            )
            
            return generic_response
    
    except HTTPException:
        raise
    except httpx.RequestError as e:
        logger.error(f"Connection error to inference-core-v2: {e}")
        raise HTTPException(status_code=503, detail="Scoring service unavailable")
    except Exception as e:
        logger.exception(f"Unexpected error in /chat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check inference-core-v2 health
        inference_status = "unknown"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{INFERENCE_V2_URL}{INFERENCE_V2_API_PREFIX}/health")
                if response.status_code == 200:
                    data = response.json()
                    inference_status = data.get("status", "unknown")
                else:
                    inference_status = f"error_{response.status_code}"
            except Exception as e:
                logger.warning(f"Health check failed for inference-core-v2: {e}")
                inference_status = "unreachable"
        
        return HealthResponse(
            status="healthy",
            service="generic-bridge-v2",
            inference_v2_status=inference_status
        )
    
    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "generic-bridge-v2",
        "version": "2.0.0",
        "description": "Adapts generic chat requests to inference-core-v2",
        "endpoints": {
            "POST /chat": "Forward chat to inference-core-v2 with scoring",
            "GET /health": "Health check with dependency status"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info"
    )
