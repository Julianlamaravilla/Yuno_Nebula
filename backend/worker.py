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
from database import async_session_maker, get_issuer_breakdown, get_alert_rules

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Real-time anomaly detection engine with smart trend detection"""

    def __init__(self):
        self.redis_client: redis.Redis | None = None
        self.check_interval = settings.check_interval_seconds
        self.error_threshold = settings.alert_threshold_error_rate
        self.decline_threshold = settings.alert_threshold_decline_rate
        
        # Track alert history to prevent duplicates and false positives
        self.active_alerts = {}  # {(provider, country, type): timestamp}
        self.recent_errors = defaultdict(list)  # Track error patterns 

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
        Analyze metrics for a specific provider/country with smart trend detection
        
        NEW LOGIC:
        1. Detect error trends (not isolated incidents)
        2. Check response codes for specific HTTP errors
        3. Verify errors are persistent before alerting
        4. Auto-resolve if recovered
        """
        total = sum(status_counts.values())
        if total < settings.min_transactions_for_alert:
            return

        succeeded = status_counts.get("SUCCEEDED", 0)
        declined = status_counts.get("DECLINED", 0)
        errors = status_counts.get("ERROR", 0)

        # Calculate rates
        error_rate = errors / total if total > 0 else 0
        decline_rate = declined / (succeeded + declined) if (succeeded + declined) > 0 else 0

        # Check if error trend is persistent (anti-false positive)
        is_persistent_error = await self.check_error_trend(provider, country, errors, total)
        
        # Check for recovery (if previously alerted, verify issue persists)
        is_recovered = await self.check_recovery(provider, country, succeeded)
        alert_key = (provider, country, "HIGH_ERROR_RATE")
        
        if is_recovered and alert_key in self.active_alerts:
            logger.info(f"✅ RECOVERY: {provider} in {country} has recovered")
            del self.active_alerts[alert_key]
            return

        # Red Alert: High error rate WITH persistent trend
        if error_rate > self.error_threshold and is_persistent_error:
            # Check if already alerted recently
            if self.should_alert(provider, country, "HIGH_ERROR_RATE"):
                # Get detailed error breakdown (response codes)
                error_details = await self.get_error_code_breakdown(provider, country)
                
                severity = "CRITICAL" if error_rate > 0.30 else "WARNING"
                
                logger.warning(
                    f"🚨 PERSISTENT ERROR DETECTED: {provider} in {country} "
                    f"({error_rate:.1%}, {errors}/{total} txns) - {severity}"
                    f"\n   Response codes: {error_details.get('response_codes', {})}"
                )
                
                await self.create_alert(
                    provider=provider,
                    country=country,
                    severity=severity,
                    alert_type="HIGH_ERROR_RATE",
                    affected_count=errors,
                    status_counts=status_counts,
                    error_details=error_details
                )
                
                self.active_alerts[alert_key] = datetime.now()

        # Yellow Alert: Elevated decline rate
        elif decline_rate > self.decline_threshold:
            alert_key_decline = (provider, country, "HIGH_DECLINE_RATE")
            
            if self.should_alert(provider, country, "HIGH_DECLINE_RATE"):
                severity = "WARNING"
                
                logger.warning(
                    f"⚠️  HIGH DECLINE RATE: {provider} in {country} "
                    f"({decline_rate:.1%}, {declined} declined) - {severity}"
                )
                
                await self.create_alert(
                    provider=provider,
                    country=country,
                    severity=severity,
                    alert_type="HIGH_DECLINE_RATE",
                    affected_count=declined,
                    status_counts=status_counts
                )
                
                self.active_alerts[alert_key_decline] = datetime.now()

    async def create_alert(
        self,
        provider: str,
        country: str,
        severity: str,
        alert_type: str,
        affected_count: int,
        status_counts: dict,
        error_details: dict = None
    ):
        """
        Create alert with granular analysis and LLM explanation
        """
        # Step 1: Granular JSONB analysis - check if issuer-specific
        issuer_breakdown = await self.get_issuer_analysis(provider, country)

        # Step 2: Calculate financial impact
        revenue_at_risk = await self.calculate_revenue_impact(provider, country)

        # Step 3: Determine root cause (include error code details)
        root_cause, suggested_action = await self.determine_root_cause(
            provider=provider,
            country=country,
            issuer_breakdown=issuer_breakdown,
            alert_type=alert_type,
            error_details=error_details
        )

        # Step 4: Call AI Agent for LLM explanation
        # INTERFACE CONTRACT: Detection Team → AI Team
        ai_response = await self.call_ai_agent(
            provider=provider,
            country=country,
            error_count=affected_count,
            revenue_at_risk=float(revenue_at_risk),
            issuer_breakdown=issuer_breakdown,
            error_details=error_details
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

    def should_alert(self, provider: str, country: str, alert_type: str) -> bool:
        """
        Check if we should alert based on cooldown period
        Prevents alert spam for same issue
        """
        alert_key = (provider, country, alert_type)
        
        if alert_key not in self.active_alerts:
            return True
        
        last_alert = self.active_alerts[alert_key]
        cooldown = timedelta(seconds=settings.alert_cooldown_seconds)
        
        return (datetime.now() - last_alert) > cooldown

    async def check_error_trend(self, provider: str, country: str, current_errors: int, total: int) -> bool:
        """
        Check if errors are part of a persistent trend (not isolated)
        
        Returns True if:
        - We have minimum consecutive errors in time window
        - Error pattern is consistent (not random spikes)
        """
        if current_errors < settings.min_consecutive_errors:
            return False
        
        try:
            # Query recent error history
            query = text("""
                SELECT
                    DATE_TRUNC('minute', created_at) as minute,
                    COUNT(*) FILTER (WHERE status = 'ERROR') as errors,
                    COUNT(*) as total
                FROM events_log
                WHERE
                    provider_id = :provider
                    AND raw_payload->>'country' = :country
                    AND created_at >= NOW() - make_interval(mins => :window)
                GROUP BY minute
                ORDER BY minute DESC
                LIMIT 10
            """)
            
            async with async_session_maker() as session:
                result = await session.execute(query, {
                    "provider": provider,
                    "country": country,
                    "window": settings.error_trend_window_minutes
                })
                rows = result.fetchall()
                
                if len(rows) < 3:  # Need at least 3 data points
                    return False
                
                # Check if majority of recent windows have errors
                windows_with_errors = sum(1 for row in rows if row[1] > 0)
                return windows_with_errors >= (len(rows) * 0.6)  # 60% of windows
                
        except Exception as e:
            logger.error(f"Error trend check failed: {e}")
            return True  # If check fails, allow alert (fail-safe)

    async def check_recovery(self, provider: str, country: str, recent_success: int) -> bool:
        """
        Check if system has recovered from previous error state
        
        Returns True if we have enough consecutive successful transactions
        """
        if recent_success < settings.recovery_check_threshold:
            return False
        
        try:
            # Check recent success rate
            query = text("""
                SELECT COUNT(*) FILTER (WHERE status = 'SUCCEEDED') as success_count
                FROM events_log
                WHERE 
                    provider_id = :provider
                    AND raw_payload->>'country' = :country
                    AND created_at >= NOW() - INTERVAL '2 minutes'
            """)
            
            async with async_session_maker() as session:
                result = await session.execute(query, {"provider": provider, "country": country})
                success_count = result.scalar() or 0
                
                return success_count >= settings.recovery_check_threshold
                
        except Exception as e:
            logger.error(f"Recovery check failed: {e}")
            return False

    async def get_error_code_breakdown(self, provider: str, country: str) -> dict:
        """
        Get detailed breakdown of response codes (500, 501, 502, 503, 504)
        Shows frequency of each HTTP error type
        """
        try:
            query = text("""
                SELECT 
                    raw_payload->'provider_data'->>'response_code' as response_code,
                    COUNT(*) as count,
                    ARRAY_AGG(DISTINCT raw_payload->>'sub_status') as sub_statuses
                FROM events_log
                WHERE 
                    provider_id = :provider
                    AND raw_payload->>'country' = :country
                    AND status = 'ERROR'
                    AND created_at >= NOW() - INTERVAL '15 minutes'
                GROUP BY response_code
                ORDER BY count DESC
            """)
            
            async with async_session_maker() as session:
                result = await session.execute(query, {"provider": provider, "country": country})
                rows = result.fetchall()
                
                response_codes = {}
                all_sub_statuses = set()
                
                for row in rows:
                    code = row[0] or "UNKNOWN"
                    response_codes[code] = row[1]
                    if row[2]:
                        all_sub_statuses.update([s for s in row[2] if s])
                
                return {
                    "response_codes": response_codes,
                    "sub_statuses": list(all_sub_statuses),
                    "most_common_code": max(response_codes.items(), key=lambda x: x[1])[0] if response_codes else None
                }
                
        except Exception as e:
            logger.error(f"Error code breakdown failed: {e}")
            return {"response_codes": {}, "sub_statuses": []}

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
        alert_type: str,
        error_details: dict = None
    ) -> tuple[dict, dict]:
        """
        Determine root cause and suggested action
        Includes HTTP response code analysis with enhanced detection:
        - 401: Merchant configuration / Invalid API keys
        - 57: Regulatory/regional blocks
        - 500/504: Infrastructure failures

        Returns: (root_cause_dict, suggested_action_dict)
        """
        # Extract most common error code
        most_common_code = None
        if error_details and error_details.get("most_common_code"):
            most_common_code = error_details["most_common_code"]

        # Priority 1: Check for merchant configuration errors (401)
        if most_common_code == "401":
            root_cause = {
                "provider": provider,
                "issue": "Merchant Configuration Error - Invalid API Credentials",
                "scope": f"All {provider} transactions",
                "response_code": "401"
            }
            suggested_action = {
                "label": f"Update API Keys for {provider}",
                "action_type": "UPDATE_CREDENTIALS"
            }
            return root_cause, suggested_action

        # Priority 2: Check for regulatory blocks (57)
        if most_common_code == "57":
            root_cause = {
                "provider": provider,
                "issue": f"Regulatory/Regional Block in {country}",
                "scope": f"Transactions not permitted in {country}",
                "response_code": "57"
            }
            suggested_action = {
                "label": f"Review Country Rules for {country}",
                "action_type": "REVIEW_COMPLIANCE"
            }
            return root_cause, suggested_action

        # Priority 3: Check if issuer-specific (infrastructure)
        if issuer_breakdown and len(issuer_breakdown) == 1:
            # Single issuer problem
            issuer = issuer_breakdown[0]
            issue_desc = f"Elevated errors for {issuer['issuer_name']} cards"
            if most_common_code:
                issue_desc += f" (HTTP {most_common_code})"

            root_cause = {
                "provider": provider,
                "issue": issue_desc,
                "scope": f"{issuer['issuer_name']} issuers only",
                "response_code": most_common_code
            }
            suggested_action = {
                "label": f"Failover {issuer['issuer_name']} to backup provider",
                "action_type": "FAILOVER_PROVIDER"
            }
        else:
            # Provider-wide issue
            issue_desc = f"{alert_type.replace('_', ' ')} across {country}"
            if most_common_code:
                issue_desc += f" (HTTP {most_common_code})"

            root_cause = {
                "provider": provider,
                "issue": issue_desc,
                "scope": "All transactions",
                "response_code": most_common_code
            }

            # Determine action based on error code
            if most_common_code in ["504", "503", "502"]:
                action_label = f"Increase timeout or failover {provider}"
                action_type = "INCREASE_TIMEOUT"
            elif most_common_code == "500":
                action_label = f"Contact {provider} - Internal server error"
                action_type = "CONTACT_ISSUER"
            else:
                action_label = f"Pause traffic to {provider}"
                action_type = "PAUSE_TRAFFIC"

            suggested_action = {
                "label": action_label,
                "action_type": action_type
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
        issuer_breakdown: list,
        error_details: dict = None
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
            
            # Include error code details
            response_codes = error_details.get("response_codes", {}) if error_details else {}
            most_common_code = error_details.get("most_common_code") if error_details else None

            # Include error code details
            response_codes = error_details.get("response_codes", {}) if error_details else {}
            most_common_code = error_details.get("most_common_code") if error_details else None

            context = {
                "provider": provider,
                "country": country,
                "error_count": error_count,
                "revenue_at_risk_usd": revenue_at_risk,
                "issuer_name": issuer_name,
                "sub_statuses": [s for s in sub_statuses if s],
                "response_codes": response_codes,
                "most_common_code": most_common_code,
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
