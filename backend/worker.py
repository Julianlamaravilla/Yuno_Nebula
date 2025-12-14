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
from database import async_session_maker, get_issuer_breakdown, get_alert_rules_for_context, get_merchant_rules

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
        # New format: stats:{merchant_id}:{country}:{provider}:{status}:{minute_window}
        pattern = "stats:*"
        metrics = defaultdict(lambda: defaultdict(int))

        async for key in self.redis_client.scan_iter(match=pattern):
            count = await self.redis_client.get(key)
            parts = key.split(":")

            if len(parts) == 6:
                _, merchant_id, country, provider, status, minute_window = parts
                metric_key = (merchant_id, country, provider)
                metrics[metric_key][status] += int(count or 0)

        # Step 2: Analyze each merchant/provider/country combination
        for (merchant_id, country, provider), status_counts in metrics.items():
            await self.analyze_provider(merchant_id, country, provider, status_counts)

    async def analyze_provider(self, merchant_id: str, country: str, provider: str, status_counts: dict):
        """
        RULE-BASED DETECTION SYSTEM

        Evaluates all applicable alert_rules for the merchant/provider/country context.
        Supports: APPROVAL_RATE, ERROR_RATE, DECLINE_RATE, TOTAL_VOLUME metrics
        Time-based rules (peak hours, business hours)
        """
        # Load ALL applicable rules for this context
        rules = await get_alert_rules_for_context(merchant_id, country, provider)

        # Calculate metrics
        total = sum(status_counts.values())
        succeeded = status_counts.get("SUCCEEDED", 0)
        declined = status_counts.get("DECLINED", 0)
        errors = status_counts.get("ERROR", 0)

        # Calculate rates
        error_rate = errors / total if total > 0 else 0
        approval_rate = succeeded / total if total > 0 else 0
        decline_rate = declined / (succeeded + declined) if (succeeded + declined) > 0 else 0

        current_hour = datetime.now().hour

        # === EVALUATE EACH RULE ===
        for rule in rules:
            # === TIME-BASED VALIDATION ===
            if rule.get("is_time_based"):
                start_hour = rule.get("start_hour")
                end_hour = rule.get("end_hour")

                if start_hour is not None and end_hour is not None:
                    if not (start_hour <= current_hour < end_hour):
                        logger.debug(
                            f"⏰ Rule '{rule.get('rule_name')}' INACTIVE "
                            f"(current={current_hour}h, active={start_hour}-{end_hour}h)"
                        )
                        continue  # Skip this rule

            # === LAYER 1: MIN TRANSACTIONS FILTER ===
            min_txns = rule.get("min_transactions", 10)
            if total < min_txns:
                logger.debug(f"Rule '{rule.get('rule_name')}': volume too low ({total} < {min_txns})")
                continue

            # === EVALUATE METRIC ===
            metric_type = rule.get("metric_type")
            operator = rule.get("operator")
            threshold = rule.get("threshold_value")

            # Get current metric value
            if metric_type == "APPROVAL_RATE":
                current_value = approval_rate
            elif metric_type == "ERROR_RATE":
                current_value = error_rate
            elif metric_type == "DECLINE_RATE":
                current_value = decline_rate
            elif metric_type == "TOTAL_VOLUME":
                current_value = total
            else:
                logger.warning(f"Unknown metric_type: {metric_type}")
                continue

            # Apply operator
            condition_met = False
            if operator == "<":
                condition_met = current_value < threshold
            elif operator == ">":
                condition_met = current_value > threshold
            elif operator == "<=":
                condition_met = current_value <= threshold
            elif operator == ">=":
                condition_met = current_value >= threshold
            else:
                logger.warning(f"Unknown operator: {operator}")
                continue

            # === TRIGGER ALERT IF CONDITION MET ===
            if condition_met:
                rule_key = (provider, country, rule.get("rule_id"))

                if self.should_alert(provider, country, rule.get("rule_id")):
                    logger.warning(
                        f"🚨 RULE TRIGGERED: {rule.get('rule_name')} "
                        f"| {metric_type} {operator} {threshold} "
                        f"| Current: {current_value:.2f} "
                        f"| Severity: {rule.get('severity')}"
                    )

                    # Get error details if applicable
                    error_details = None
                    if metric_type in ["ERROR_RATE", "DECLINE_RATE"]:
                        error_details = await self.get_error_code_breakdown(provider, country)

                    await self.create_alert(
                        provider=provider,
                        country=country,
                        merchant_id=merchant_id,
                        severity=rule.get("severity", "WARNING"),
                        alert_type=rule.get("rule_name", metric_type),
                        affected_count=errors if metric_type == "ERROR_RATE" else declined,
                        status_counts=status_counts,
                        error_details=error_details or {"metric": metric_type, "value": current_value}
                    )

                    self.active_alerts[rule_key] = datetime.now()

    async def create_alert(
        self,
        provider: str,
        country: str,
        merchant_id: str,
        severity: str,
        alert_type: str,
        affected_count: int,
        status_counts: dict,
        error_details: dict = None
    ):
        """
        Create alert with granular analysis and LLM explanation

        CRITICAL: All analysis functions use merchant_id for strict data isolation
        """
        # Step 1: Granular JSONB analysis - check if issuer-specific (merchant-isolated)
        issuer_breakdown = await self.get_issuer_analysis(merchant_id, provider, country)

        # Step 2: Calculate financial impact (merchant-isolated)
        revenue_at_risk = await self.calculate_revenue_impact(merchant_id, provider, country)

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
        # Custom title for probabilistic anomalies
        if alert_type == "PROBABILISTIC_ANOMALY":
            title = f"{provider} {country} - Anomalía de Comportamiento (Probabilística)"
        else:
            title = f"{provider} {country} - {alert_type.replace('_', ' ').title()}"

        alert_id = await self.save_alert(
            severity=severity,
            title=title,
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

        # === EMAIL NOTIFICATION TO KAM ===
        try:
            kam_info = await self.get_kam_email(merchant_id)
            if kam_info:
                await self.send_kam_alert_email(
                    kam_info=kam_info,
                    alert_details={
                        "alert_id": str(alert_id),
                        "severity": severity,
                        "title": title,
                        "revenue_at_risk": float(revenue_at_risk),
                        "affected_transactions": affected_count,
                        "llm_explanation": llm_explanation,
                        "suggested_action": suggested_action
                    }
                )
            else:
                logger.warning(f"No KAM found for merchant {merchant_id}, email notification skipped")
        except Exception as e:
            logger.error(f"Email notification failed (non-fatal): {e}")

    async def get_merchant_from_context(self, provider: str, country: str) -> str:
        """
        Get merchant_id from recent transactions for this provider/country context
        Used to apply merchant-specific alert rules
        
        Returns: merchant_id or 'unknown'
        """
        try:
            query = text("""
                SELECT merchant_id, COUNT(*) as txn_count
                FROM events_log
                WHERE 
                    provider_id = :provider
                    AND raw_payload->>'country' = :country
                    AND created_at >= NOW() - INTERVAL '5 minutes'
                GROUP BY merchant_id
                ORDER BY txn_count DESC
                LIMIT 1
            """)
            
            async with async_session_maker() as session:
                result = await session.execute(query, {"provider": provider, "country": country})
                row = result.fetchone()
                
                return row[0] if row else "unknown"
                
        except Exception as e:
            logger.error(f"Failed to get merchant context: {e}")
            return "unknown"

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

    async def check_error_trend(self, provider: str, country: str, error_rate: float, threshold: float) -> bool:
        """
        LAYER 2: Trend Detection with Redis Counters

        Tracks consecutive cycles with high error rates.
        Only triggers alert after 3 consecutive cycles (30 seconds) of errors.
        Resets counter if error rate drops below threshold.

        Returns:
            True if error trend is persistent (3+ consecutive cycles)
            False otherwise
        """
        trend_key = f"trend:{country}:{provider}:error_streak"

        try:
            if error_rate > threshold:
                # Increment streak counter
                streak = await self.redis_client.incr(trend_key)
                await self.redis_client.expire(trend_key, 60)  # Expire after 1 minute

                logger.debug(f"Error streak for {provider} in {country}: {streak} cycles")

                # Require 3 consecutive cycles (30 seconds) before alerting
                if streak >= 3:
                    logger.info(f"🔥 PERSISTENT TREND DETECTED: {provider} in {country} (streak={streak})")
                    return True
                else:
                    logger.debug(f"Error trend building: {streak}/3 cycles")
                    return False
            else:
                # Error rate is normal, reset streak
                await self.redis_client.delete(trend_key)
                return False

        except Exception as e:
            logger.error(f"Error trend check failed: {e}")
            # Fail-safe: allow alert if Redis fails
            return error_rate > threshold

    async def check_probabilistic_anomaly(self, approval_rate: float) -> tuple[bool, float]:
        """
        LAYER 3: Probabilistic Model (Z-Score Detection)

        Uses statistical deviation to detect anomalies when no custom rule exists.
        Baseline: 85% approval rate
        Std Deviation: 5%

        Returns:
            (is_anomaly, z_score)
        """
        BASELINE = 0.85  # Theoretical baseline (85% approval)
        STD_DEV = 0.05   # Standard deviation (5%)

        # Calculate Z-Score: (Baseline - Current) / StdDev
        z_score = (BASELINE - approval_rate) / STD_DEV

        # Z-Score > 3 means extreme deviation (approval_rate < 70%)
        is_anomaly = z_score > 3

        if is_anomaly:
            logger.info(
                f"📊 PROBABILISTIC ANOMALY DETECTED: "
                f"Z-Score={z_score:.2f}, Approval Rate={approval_rate:.1%} (Baseline={BASELINE:.1%})"
            )

        return is_anomaly, z_score

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

    async def get_issuer_analysis(self, merchant_id: str, provider: str, country: str) -> list:
        """
        Query JSONB payload for issuer-level breakdown
        Returns list of issuers with error counts

        CRITICAL: Filters by merchant_id to ensure strict data isolation
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
                    merchant_id = :merchant_id
                    AND provider_id = :provider
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
                result = await session.execute(query, {
                    "merchant_id": merchant_id,
                    "provider": provider,
                    "country": country
                })
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
            logger.error(f"Issuer analysis failed for merchant {merchant_id}: {e}")
            return []

    async def calculate_revenue_impact(self, merchant_id: str, provider: str, country: str) -> Decimal:
        """
        Calculate total revenue at risk for a specific merchant

        CRITICAL: Filters by merchant_id to ensure accurate per-merchant financial impact
        """
        try:
            query = text("""
                SELECT COALESCE(SUM(amount_usd), 0)
                FROM events_log
                WHERE
                    merchant_id = :merchant_id
                    AND provider_id = :provider
                    AND raw_payload->>'country' = :country
                    AND status = 'ERROR'
                    AND created_at >= NOW() - INTERVAL '15 minutes'
            """)

            async with async_session_maker() as session:
                result = await session.execute(query, {
                    "merchant_id": merchant_id,
                    "provider": provider,
                    "country": country
                })
                return Decimal(str(result.scalar() or 0))

        except Exception as e:
            logger.error(f"Revenue calculation failed for merchant {merchant_id}: {e}")
            return Decimal("0")

    async def get_kam_email(self, merchant_id: str) -> dict | None:
        """
        Get KAM information for a merchant

        Returns:
            {
                "kam_name": str,
                "kam_email": str,
                "merchant_id": str
            } or None
        """
        try:
            query = text("""
                SELECT
                    k.name,
                    k.email,
                    mr.merchant_id
                FROM merchant_rules mr
                INNER JOIN kams k ON mr.kam_id = k.kam_id
                WHERE mr.merchant_id = :merchant_id
            """)

            async with async_session_maker() as session:
                result = await session.execute(query, {"merchant_id": merchant_id})
                row = result.fetchone()

                if row:
                    return {
                        "kam_name": row[0],
                        "kam_email": row[1],
                        "merchant_id": row[2]
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get KAM for merchant {merchant_id}: {e}")
            return None

    async def send_kam_alert_email(
        self,
        kam_info: dict,
        alert_details: dict
    ):
        """
        Send email notification to KAM about critical alert

        Args:
            kam_info: {kam_name, kam_email, merchant_id}
            alert_details: {alert_id, severity, title, revenue_at_risk, affected_transactions, llm_explanation, suggested_action}
        """
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Check if email credentials are configured
            if not settings.email_sender or not settings.email_password:
                logger.warning("Email credentials not configured, skipping notification")
                return

            # Email subject
            severity_emoji = "🔴" if alert_details['severity'] == 'CRITICAL' else "⚠️"
            subject = f"{severity_emoji} [{alert_details['severity']}] {alert_details['title']}"

            # Email body (HTML)
            severity_color = "#dc2626" if alert_details['severity'] == 'CRITICAL' else "#f59e0b"
            severity_bg = "#fee2e2" if alert_details['severity'] == 'CRITICAL' else "#fef3c7"

            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: {severity_color}; border-left: 4px solid {severity_color}; padding-left: 15px;">
                        {severity_emoji} Alert Notification
                    </h2>

                    <p>Hi <strong>{kam_info['kam_name']}</strong>,</p>

                    <p>A <strong style="color: {severity_color};">{alert_details['severity']}</strong> alert has been detected for your merchant
                    <strong>{kam_info['merchant_id']}</strong>.</p>

                    <div style="background: {severity_bg}; padding: 20px; border-left: 4px solid {severity_color}; margin: 20px 0; border-radius: 4px;">
                        <h3 style="margin-top: 0; color: {severity_color};">{alert_details['title']}</h3>
                        <p style="margin: 10px 0;">
                            <strong>💰 Revenue at Risk:</strong>
                            <span style="font-size: 18px; color: {severity_color};">${alert_details['revenue_at_risk']:,.2f} USD</span>
                        </p>
                        <p style="margin: 10px 0;">
                            <strong>📊 Affected Transactions:</strong> {alert_details['affected_transactions']}
                        </p>
                    </div>

                    <h4 style="color: #374151; margin-top: 25px;">🤖 AI Analysis:</h4>
                    <div style="background: #f3f4f6; padding: 15px; border-radius: 4px; font-style: italic;">
                        {alert_details.get('llm_explanation', 'AI analysis not available')}
                    </div>

                    <h4 style="color: #374151; margin-top: 25px;">💡 Recommended Action:</h4>
                    <div style="background: #dbeafe; padding: 15px; border-radius: 4px; border-left: 3px solid #3b82f6;">
                        <strong>{alert_details['suggested_action'].get('label', 'No action specified')}</strong>
                        <p style="margin: 5px 0 0 0; font-size: 14px; color: #6b7280;">
                            Type: {alert_details['suggested_action'].get('action_type', 'N/A')}
                        </p>
                    </div>

                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">

                    <div style="font-size: 13px; color: #6b7280;">
                        <p><strong>Alert ID:</strong> {alert_details['alert_id']}</p>
                        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                        <p><a href="http://localhost:3000" style="color: #3b82f6; text-decoration: none;">📊 View Dashboard →</a></p>
                    </div>

                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; text-align: center;">
                        <p>This is an automated notification from <strong>Yuno Sentinel</strong>.</p>
                        <p>Powered by Gemini AI | Real-time Financial Observability</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = settings.email_sender
            msg['To'] = kam_info['kam_email']
            msg.attach(MIMEText(body, 'html'))

            # Send email using Gmail SMTP
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(settings.email_sender, settings.email_password)
                server.send_message(msg)

            logger.info(
                f"✅ Email sent to KAM {kam_info['kam_name']} ({kam_info['kam_email']}) "
                f"for merchant {kam_info['merchant_id']}"
            )

        except Exception as e:
            logger.error(f"Failed to send email to KAM: {e}", exc_info=True)

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
