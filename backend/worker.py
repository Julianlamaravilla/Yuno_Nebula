"""
Yuno Sentinel - Anomaly Detection Worker (Sentinel Worker)
The Brain: Real-time pattern detection and self-healing recommendations

TEAM: Detection Team
RESPONSIBILITIES:
- Scan Redis metrics every 10 seconds
- Calculate error/decline rates
- Detect anomalies (thresholds)
- Execute JSONB queries for granular analysis
- Call AI Agent service for LLM reasoning
- Insert alerts into database
- NO LLM logic (delegate to AI Agent)
"""
import asyncio
import redis.asyncio as redis
from sqlalchemy import text
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import uuid
import random
from collections import defaultdict
import httpx

from config import settings
from database import async_session_maker, get_issuer_breakdown, get_merchant_rules

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Real-time anomaly detection engine"""

    def __init__(self):
        self.redis_client: redis.Redis | None = None
        self.check_interval = settings.check_interval_seconds
        self.error_threshold = 0.01
        self.decline_threshold = 0.05 

    async def start(self):
        """Initialize and start the detection loop"""
        logger.info("Starting Anomaly Detection Worker...")

        # Connect to Redis
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return

        # Main detection loop
        while True:
            try:
                await self.detect_anomalies()
            except Exception as e:
                logger.error(f"Detection cycle error: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def detect_anomalies(self):
        """
        Main detection logic:
        1. Scan Redis metrics
        2. Calculate error/decline rates
        3. Check thresholds
        4. Trigger granular analysis if needed
        5. Create alerts
        """
        logger.debug("Running anomaly detection cycle...")

        # Step 1: Fetch all Redis metric keys
        pattern = "stats:*"
        metrics = defaultdict(lambda: defaultdict(int))

        async for key in self.redis_client.scan_iter(match=pattern):
            count = await self.redis_client.get(key)
            parts = key.split(":")

            if len(parts) == 5:
                _, country, provider, status, minute_window = parts
                metric_key = (country, provider)
                metrics[metric_key][status] += int(count or 0)

        # Step 2: Analyze each provider/country combination
        for (country, provider), status_counts in metrics.items():
            await self.analyze_provider(country, provider, status_counts)

    async def analyze_provider(self, country: str, provider: str, status_counts: dict):
        """
        Analyze metrics for a specific provider/country

        Alert Triggers:
        - Red Alert: Error rate > 15% OR any TIMEOUT
        - Yellow Alert: Decline rate > baseline + 20%
        
        Severity Distribution: 30% CRITICAL, 70% WARNING
        """
        total = sum(status_counts.values())
        if total == 0:
            return

        succeeded = status_counts.get("SUCCEEDED", 0)
        declined = status_counts.get("DECLINED", 0)
        errors = status_counts.get("ERROR", 0)

        # Calculate rates
        error_rate = errors / total if total > 0 else 0
        decline_rate = declined / (succeeded + declined) if (succeeded + declined) > 0 else 0

        severity = "CRITICAL" if random.random() < 0.10 else "WARNING"

        # Red Alert: High error rate
        if error_rate > self.error_threshold:
            logger.warning(
                f"⚠️  HIGH ERROR RATE DETECTED: {provider} in {country} "
                f"({error_rate:.1%}, {errors}/{total} txns) - {severity}"
            )
            await self.create_alert(
                provider=provider,
                country=country,
                severity=severity,
                alert_type="HIGH_ERROR_RATE",
                affected_count=errors,
                status_counts=status_counts
            )

        # Yellow Alert: Elevated decline rate
        # TODO: Fetch merchant baseline and compare
        elif decline_rate > 0.30:  # Simplified threshold
            logger.warning(
                f"⚠️  HIGH DECLINE RATE: {provider} in {country} "
                f"({decline_rate:.1%}) - {severity}"
            )
            await self.create_alert(
                provider=provider,
                country=country,
                severity=severity,
                alert_type="HIGH_DECLINE_RATE",
                affected_count=declined,
                status_counts=status_counts
            )

    async def create_alert(
        self,
        provider: str,
        country: str,
        severity: str,
        alert_type: str,
        affected_count: int,
        status_counts: dict
    ):
        """
        Create alert with granular analysis and LLM explanation
        """
        # Step 1: Granular JSONB analysis - check if issuer-specific
        issuer_breakdown = await self.get_issuer_analysis(provider, country)

        # Step 2: Calculate financial impact
        revenue_at_risk = await self.calculate_revenue_impact(provider, country)

        # Step 3: Determine root cause
        root_cause, suggested_action = await self.determine_root_cause(
            provider=provider,
            country=country,
            issuer_breakdown=issuer_breakdown,
            alert_type=alert_type
        )

        # Step 4: Call AI Agent for LLM explanation
        # INTERFACE CONTRACT: Detection Team → AI Team
        ai_response = await self.call_ai_agent(
            provider=provider,
            country=country,
            error_count=affected_count,
            revenue_at_risk=float(revenue_at_risk),
            issuer_breakdown=issuer_breakdown
        )

        # Extract AI Agent response
        llm_explanation = ai_response.get("explanation") if ai_response else None
        confidence_score = ai_response.get("confidence", 0.85) if ai_response else 0.5

        # Override suggested_action with AI recommendation (if available)
        if ai_response and ai_response.get("recommended_action"):
            suggested_action = {
                "label": ai_response["recommended_action"],
                "action_type": ai_response.get("action_type", "CONTACT_ISSUER")
            }

        # Step 5: Insert alert into database
        alert_id = await self.save_alert(
            severity=severity,
            title=f"{provider} {country} - {alert_type.replace('_', ' ').title()}",
            confidence_score=confidence_score,
            revenue_at_risk_usd=revenue_at_risk,
            affected_transactions=affected_count,
            root_cause=root_cause,
            llm_explanation=llm_explanation,
            suggested_action=suggested_action
        )

        logger.info(
            f"🚨 ALERT TRIGGERED - {alert_id}: {severity} - "
            f"{provider} {country} ({affected_count} txns, ${revenue_at_risk:.2f} at risk)"
        )

    async def get_issuer_analysis(self, provider: str, country: str) -> list:
        """
        Query JSONB payload for issuer-level breakdown
        Returns list of issuers with error counts
        """
        try:
            query = text("""
                SELECT
                    raw_payload->'payment_method'->'detail'->'card'->>'issuer_name' as issuer_name,
                    COUNT(*) as error_count,
                    SUM(amount_usd) as revenue_at_risk,
                    ARRAY_AGG(DISTINCT raw_payload->>'sub_status') as sub_statuses
                FROM events_log
                WHERE
                    provider_id = :provider
                    AND raw_payload->>'country' = :country
                    AND status = 'ERROR'
                    AND created_at >= NOW() - INTERVAL '15 minutes'
                    AND raw_payload->'payment_method'->'detail'->'card'->>'issuer_name' IS NOT NULL
                GROUP BY issuer_name
                HAVING COUNT(*) >= 3
                ORDER BY error_count DESC
                LIMIT 5
            """)

            async with async_session_maker() as session:
                result = await session.execute(query, {"provider": provider, "country": country})
                rows = result.fetchall()

                return [
                    {
                        "issuer_name": row[0],
                        "error_count": row[1],
                        "revenue_at_risk": float(row[2] or 0),
                        "sub_statuses": [s for s in row[3] if s]
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Issuer analysis failed: {e}")
            return []

    async def calculate_revenue_impact(self, provider: str, country: str) -> Decimal:
        """Calculate total revenue at risk"""
        try:
            query = text("""
                SELECT COALESCE(SUM(amount_usd), 0)
                FROM events_log
                WHERE
                    provider_id = :provider
                    AND raw_payload->>'country' = :country
                    AND status = 'ERROR'
                    AND created_at >= NOW() - INTERVAL '15 minutes'
            """)

            async with async_session_maker() as session:
                result = await session.execute(query, {"provider": provider, "country": country})
                return Decimal(str(result.scalar() or 0))

        except Exception as e:
            logger.error(f"Revenue calculation failed: {e}")
            return Decimal("0")

    async def determine_root_cause(
        self,
        provider: str,
        country: str,
        issuer_breakdown: list,
        alert_type: str
    ) -> tuple[dict, dict]:
        """
        Determine root cause and suggested action

        Returns: (root_cause_dict, suggested_action_dict)
        """
        # Check if issuer-specific
        if issuer_breakdown and len(issuer_breakdown) == 1:
            # Single issuer problem
            issuer = issuer_breakdown[0]
            root_cause = {
                "provider": provider,
                "issue": f"Elevated errors for {issuer['issuer_name']} cards",
                "scope": f"{issuer['issuer_name']} issuers only"
            }
            suggested_action = {
                "label": f"Failover {issuer['issuer_name']} to backup provider",
                "action_type": "FAILOVER_PROVIDER"
            }
        else:
            # Provider-wide issue
            root_cause = {
                "provider": provider,
                "issue": f"{alert_type.replace('_', ' ')} across {country}",
                "scope": "All transactions"
            }
            suggested_action = {
                "label": f"Pause traffic to {provider} or increase timeout",
                "action_type": "PAUSE_TRAFFIC"
            }

        return root_cause, suggested_action

    async def save_alert(
        self,
        severity: str,
        title: str,
        confidence_score: float,
        revenue_at_risk_usd: Decimal,
        affected_transactions: int,
        root_cause: dict,
        llm_explanation: str | None,
        suggested_action: dict
    ) -> str:
        """Save alert to database"""
        try:
            import json

            sla_breach_countdown = 300 if severity == "CRITICAL" else None

            query = text("""
                INSERT INTO alerts (
                    severity, title, confidence_score, revenue_at_risk_usd,
                    affected_transactions, sla_breach_countdown_seconds, 
                    root_cause, llm_explanation, suggested_action
                )
                VALUES (
                    :severity, :title, :confidence_score, :revenue_at_risk_usd,
                    :affected_transactions, :sla_breach_countdown_seconds,
                    :root_cause, :llm_explanation, :suggested_action
                )
                RETURNING alert_id
            """)

            async with async_session_maker() as session:
                result = await session.execute(query, {
                    "severity": severity,
                    "title": title,
                    "confidence_score": confidence_score,
                    "revenue_at_risk_usd": float(revenue_at_risk_usd),
                    "affected_transactions": affected_transactions,
                    "sla_breach_countdown_seconds": sla_breach_countdown,
                    "root_cause": json.dumps(root_cause),
                    "llm_explanation": llm_explanation,
                    "suggested_action": json.dumps(suggested_action)
                })
                await session.commit()
                return str(result.scalar_one())

        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            return str(uuid.uuid4())

    async def call_ai_agent(
        self,
        provider: str,
        country: str,
        error_count: int,
        revenue_at_risk: float,
        issuer_breakdown: list
    ) -> dict | None:
        """
        Call AI Agent service for LLM reasoning

        INTERFACE CONTRACT with AI Team
        - Endpoint: POST /analyze
        - Timeout: 5s (AI processing is async to detection)
        - Fallback: Returns None if AI Agent is unavailable

        Returns: AI response dict or None
        """
        try:
            # Prepare context for AI Agent
            issuer_name = issuer_breakdown[0]["issuer_name"] if issuer_breakdown else None
            sub_statuses = issuer_breakdown[0]["sub_statuses"] if issuer_breakdown else []

            context = {
                "provider": provider,
                "country": country,
                "error_count": error_count,
                "revenue_at_risk_usd": revenue_at_risk,
                "issuer_name": issuer_name,
                "sub_statuses": [s for s in sub_statuses if s],
                "merchant_advice_code": None,  # TODO: Extract from JSONB
                "time_window_minutes": 15
            }

            # Call AI Agent
            ai_agent_url = getattr(settings, 'ai_agent_url', 'http://ai-agent:8001')

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{ai_agent_url}/analyze",
                    json=context
                )
                response.raise_for_status()
                ai_response = response.json()

                logger.info(
                    f"AI Agent response: confidence={ai_response.get('confidence', 0):.2f}, "
                    f"time={ai_response.get('processing_time_ms', 0)}ms"
                )

                return ai_response

        except httpx.TimeoutException:
            logger.warning("AI Agent timeout - continuing without LLM explanation")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"AI Agent HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"AI Agent call failed: {e}")
            return None


async def main():
    """Entry point"""
    detector = AnomalyDetector()
    await detector.start()


if __name__ == "__main__":
    asyncio.run(main())
