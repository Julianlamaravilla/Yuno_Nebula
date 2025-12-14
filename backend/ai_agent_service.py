"""
Yuno Sentinel - AI Agent Service
Separate microservice for LLM-powered reasoning and alert generation

TEAM: AI/Reasoning Team
RESPONSIBILITIES:
- Receive incident context from Sentinel Worker
- Generate human-readable explanations using LLM
- Return structured recommendations
- NO database access (stateless)
- NO detection logic (pure reasoning)
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from llm_service import llm_service
from config import settings

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Yuno Sentinel - AI Agent",
    description="LLM-powered reasoning and alert generation service",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# API CONTRACTS (DO NOT MODIFY WITHOUT TEAM AGREEMENT)
# ============================================

class IncidentContext(BaseModel):
    """
    Input from Sentinel Worker
    CONTRACT: Detection Team sends this payload
    """
    provider: str = Field(..., description="Payment provider ID (STRIPE, DLOCAL, etc.)")
    country: str = Field(..., description="Country code (MX, CO, BR)")
    error_count: int = Field(..., ge=0, description="Number of errors detected")
    revenue_at_risk_usd: float = Field(..., ge=0, description="Revenue at risk in USD")
    issuer_name: Optional[str] = Field(None, description="Specific issuer if granular (e.g., BBVA)")
    sub_statuses: List[str] = Field(default_factory=list, description="List of error sub-statuses")
    merchant_advice_code: Optional[str] = Field(None, description="Provider's advice code")
    time_window_minutes: int = Field(15, description="Time window for the analysis")


class AIResponse(BaseModel):
    """
    Output to Sentinel Worker
    CONTRACT: AI Team returns this structure
    """
    explanation: str = Field(..., description="Human-readable incident explanation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    recommended_action: str = Field(..., description="Suggested action label")
    action_type: str = Field(..., description="Action type (FAILOVER_PROVIDER, PAUSE_TRAFFIC, etc.)")
    scope: str = Field(..., description="Scope of impact (e.g., 'BBVA issuers only')")
    processing_time_ms: int = Field(..., description="LLM processing time")


# ============================================
# ENDPOINTS
# ============================================

@app.post("/analyze", response_model=AIResponse, status_code=status.HTTP_200_OK)
async def analyze_incident(context: IncidentContext) -> AIResponse:
    """
    Analyze incident and generate LLM explanation

    WORKFLOW:
    1. Receive incident context from Sentinel Worker
    2. Generate LLM prompt with business context
    3. Call Gemini/OpenAI API
    4. Parse response and structure recommendation
    5. Return to Worker

    Performance Target: < 2s p99 (LLM API dependent)
    """
    start_time = datetime.now()

    try:
        logger.info(f"Analyzing incident: {context.provider} {context.country} ({context.error_count} errors)")

        # Step 1: Generate LLM explanation
        if llm_service:
            explanation = llm_service.generate_alert_explanation(
                provider=context.provider,
                country=context.country,
                error_count=context.error_count,
                revenue_at_risk=context.revenue_at_risk_usd,
                issuer_name=context.issuer_name,
                sub_statuses=context.sub_statuses,
                merchant_advice_code=context.merchant_advice_code
            )
        else:
            explanation = _fallback_explanation(context)

        # Step 2: Determine recommended action
        action, action_type = _determine_action(context)

        # Step 3: Determine scope
        scope = _determine_scope(context)

        # Step 4: Calculate confidence
        confidence = _calculate_confidence(context)

        # Calculate processing time
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        response = AIResponse(
            explanation=explanation,
            confidence=confidence,
            recommended_action=action,
            action_type=action_type,
            scope=scope,
            processing_time_ms=processing_time
        )

        logger.info(f"Analysis complete ({processing_time}ms, confidence={confidence:.2f})")
        return response

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Agent analysis failed: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    llm_status = "operational" if llm_service else "degraded"

    return {
        "status": "healthy",
        "llm_provider": settings.llm_provider,
        "llm_status": llm_status,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Yuno Sentinel - AI Agent",
        "status": "operational",
        "version": "1.0.0",
        "team": "AI/Reasoning Team",
        "endpoints": {
            "analyze": "POST /analyze",
            "health": "/health"
        }
    }


# ============================================
# PRIVATE HELPER FUNCTIONS (AI TEAM ONLY)
# ============================================

def _determine_action(context: IncidentContext) -> tuple[str, str]:
    """
    Determine recommended action based on context

    Returns: (action_label, action_type)
    """
    # Issuer-specific failure
    if context.issuer_name:
        action = f"Reroute {context.issuer_name} transactions to backup provider"
        action_type = "FAILOVER_PROVIDER"

    # Provider advice code
    elif context.merchant_advice_code == "TRY_AGAIN_LATER":
        action = f"Pause traffic to {context.provider} temporarily"
        action_type = "PAUSE_TRAFFIC"

    # High error rate
    elif context.error_count > 100:
        action = f"Increase timeout and retry for {context.provider}"
        action_type = "INCREASE_TIMEOUT"

    # Default
    else:
        action = f"Contact {context.provider} support immediately"
        action_type = "CONTACT_ISSUER"

    return action, action_type


def _determine_scope(context: IncidentContext) -> str:
    """Determine impact scope"""
    if context.issuer_name:
        return f"{context.issuer_name} issuers only"
    else:
        return f"All {context.country} transactions"


def _calculate_confidence(context: IncidentContext) -> float:
    """
    Calculate confidence score based on data quality

    High confidence: Granular issuer data + many samples
    Low confidence: Limited data
    """
    confidence = 0.5  # Base

    # More errors = higher confidence
    if context.error_count >= 10:
        confidence += 0.2
    if context.error_count >= 50:
        confidence += 0.1

    # Granular issuer data = higher confidence
    if context.issuer_name:
        confidence += 0.15

    # Sub-status data available
    if context.sub_statuses and len(context.sub_statuses) > 0:
        confidence += 0.05

    return min(confidence, 1.0)


def _fallback_explanation(context: IncidentContext) -> str:
    """Fallback if LLM service is unavailable"""
    issuer_text = f" affecting {context.issuer_name}" if context.issuer_name else ""

    return (
        f"⚠️ {context.provider} in {context.country} is experiencing elevated error rates{issuer_text}. "
        f"{context.error_count} transactions failed in the last {context.time_window_minutes} minutes, "
        f"putting ${context.revenue_at_risk_usd:,.2f} at risk. "
        f"Immediate action recommended."
    )


# ============================================
# STARTUP
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("=" * 60)
    logger.info("AI Agent Service Starting...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Team: AI/Reasoning Team")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
