"""
Yuno Sentinel - FastAPI Ingestor
High-throughput transaction ingestion service
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import redis.asyncio as redis
import logging
import json
from typing import Dict, List
from pydantic import BaseModel, Field

from schemas import PaymentEvent, convert_to_usd, AlertRuleCreate, AlertRuleResponse
from database import get_db, check_db_connection
from config import settings

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Yuno Sentinel Ingestor",
    description="Real-time payment transaction ingestion service",
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

# Redis connection pool
redis_client: redis.Redis | None = None


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global redis_client

    # Check database connection
    db_ok = await check_db_connection()
    if not db_ok:
        logger.error("Database connection failed!")

    # Initialize Redis
    try:
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis_pool_max_connections
        )
        await redis_client.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")

    logger.info("Ingestor service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if redis_client:
        await redis_client.close()
    logger.info("Ingestor service shut down")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_ok = False
    try:
        if redis_client:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        pass

    db_ok = await check_db_connection()

    return {
        "status": "healthy" if (redis_ok and db_ok) else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "database": "connected" if db_ok else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_transaction(
    payment: PaymentEvent,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    try:
        amount_usd = convert_to_usd(payment.amount.value, payment.amount.currency)

        event_data = {
            "merchant_id": payment.merchant_id,
            "provider_id": payment.provider_data.id,
            "status": payment.status,
            "amount_usd": float(amount_usd),
            "raw_payload": json.dumps(payment.model_dump(mode='json'))
        }

        insert_query = text("""
            INSERT INTO events_log (merchant_id, provider_id, status, amount_usd, raw_payload)
            VALUES (:merchant_id, :provider_id, :status, :amount_usd, :raw_payload)
            RETURNING event_id
        """)

        result = await db.execute(insert_query, event_data)
        await db.commit()
        event_id = result.scalar_one()

        if redis_client:
            await update_redis_metrics(payment)

        logger.debug(f"Ingested transaction {event_id} from {payment.provider_data.id}")

        return {
            "status": "accepted",
            "event_id": str(event_id),
            "message": "Transaction ingested successfully"
        }

    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest transaction: {str(e)}"
        )


async def update_redis_metrics(payment: PaymentEvent):
    """
    Update Redis sliding window counters
    New Pattern: stats:{merchant_id}:{country}:{provider}:{status}:{minute_window}
    """
    try:
        timestamp = payment.created_at
        minute_window = timestamp.strftime("%Y%m%d%H%M")

        redis_key = f"stats:{payment.merchant_id}:{payment.country}:{payment.provider_data.id}:{payment.status}:{minute_window}"

        async with redis_client.pipeline() as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, settings.redis_key_ttl_seconds)
            await pipe.execute()

    except Exception as e:
        logger.warning(f"Redis update failed (non-fatal): {e}")


@app.get("/metrics/recent")
async def get_recent_metrics(minutes: int = 30):
    """
    Get time-series metrics from Redis for the chart
    Updated to handle the new key pattern with merchant_id
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    try:
        pattern = "stats:*"
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key)

        time_series = {}

        for key in keys:
            count = await redis_client.get(key)
            parts = key.split(":")
            
            # FIX: Handle new key format (6 parts)
            # stats:{merchant_id}:{country}:{provider}:{status}:{minute}
            if len(parts) >= 6:
                status = parts[4]       # Index 4 is status
                minute_str = parts[5]   # Index 5 is minute timestamp
            # Fallback for old keys (5 parts) just in case
            elif len(parts) == 5:
                status = parts[3]
                minute_str = parts[4]
            else:
                continue

            if minute_str not in time_series:
                time_series[minute_str] = {"total": 0, "errors": 0, "success": 0}
            
            val = int(count or 0)
            time_series[minute_str]["total"] += val
            
            if status == "ERROR" or status == "DECLINED":
                time_series[minute_str]["errors"] += val
            elif status == "SUCCEEDED":
                time_series[minute_str]["success"] += val

        chart_data = []
        for minute, data in sorted(time_series.items()):
            try:
                dt = datetime.strptime(minute, "%Y%m%d%H%M")
                approval_rate = (data["success"] / data["total"] * 100) if data["total"] > 0 else 0
                
                chart_data.append({
                    "timestamp": dt.isoformat(),
                    "approval_rate": round(approval_rate, 2),
                    "error_rate": round(100 - approval_rate, 2),
                    "total_count": data["total"]
                })
            except ValueError:
                continue

        return chart_data[-minutes:]

    except Exception as e:
        logger.error(f"Metrics query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch metrics")


# === ENDPOINT RESTAURADO PARA EL FRONTEND ===
class ResolveAlertRequest(BaseModel):
    alert_id: str
    action_type: str | None = None

@app.post("/simulation/resolve")
async def resolve_alert_simulation(request: ResolveAlertRequest):
    """
    Dummy endpoint to handle 'Resolve' clicks from Frontend.
    In a real scenario, this would trigger a playbook.
    """
    logger.info(f"Resolving alert {request.alert_id} with action {request.action_type}")
    return {"status": "resolved", "message": "Action executed successfully"}
# ============================================


@app.get("/alerts")
async def get_alerts(limit: int = 10, db: AsyncSession = Depends(get_db)):
    try:
        query = text("""
            SELECT
                alert_id,
                created_at,
                severity,
                title,
                confidence_score,
                revenue_at_risk_usd,
                affected_transactions,
                sla_breach_countdown_seconds,
                root_cause,
                llm_explanation,
                suggested_action
            FROM alerts
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        result = await db.execute(query, {"limit": limit})
        rows = result.fetchall()

        alerts = []
        for row in rows:
            root_cause = row[8]
            if isinstance(root_cause, str):
                root_cause = json.loads(root_cause)

            suggested_action = row[10]
            if isinstance(suggested_action, str):
                suggested_action = json.loads(suggested_action)

            alerts.append({
                "alert_id": str(row[0]),
                "created_at": row[1].isoformat() if row[1] else None,
                "severity": row[2],
                "title": row[3],
                "confidence_score": float(row[4]) if row[4] else 0.0,
                "revenue_at_risk_usd": float(row[5]) if row[5] else 0.0,
                "affected_transactions": row[6] if row[6] else 0,
                "sla_breach_countdown_seconds": row[7],
                "root_cause": root_cause or {},
                "llm_explanation": row[9],
                "suggested_action": suggested_action or {}
            })

        return {"alerts": alerts, "total": len(alerts)}

    except Exception as e:
        logger.error(f"Alerts query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alerts")


@app.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule: AlertRuleCreate,
    db: AsyncSession = Depends(get_db)
) -> AlertRuleResponse:
    try:
        query = text("""
            INSERT INTO alert_rules (
                merchant_id,
                rule_name,
                filter_country,
                filter_provider,
                filter_issuer,
                metric_type,
                operator,
                threshold_value,
                min_transactions,
                is_time_based,
                start_hour,
                end_hour,
                severity
            ) VALUES (
                :merchant_id,
                :rule_name,
                :filter_country,
                :filter_provider,
                :filter_issuer,
                :metric_type,
                :operator,
                :threshold_value,
                :min_transactions,
                :is_time_based,
                :start_hour,
                :end_hour,
                :severity
            )
            RETURNING *
        """)

        result = await db.execute(query, {
            "merchant_id": rule.merchant_id,
            "rule_name": rule.rule_name,
            "filter_country": rule.filter_country,
            "filter_provider": rule.filter_provider,
            "filter_issuer": rule.filter_issuer,
            "metric_type": rule.metric_type,
            "operator": rule.operator,
            "threshold_value": float(rule.threshold_value),
            "min_transactions": rule.min_transactions,
            "is_time_based": rule.is_time_based,
            "start_hour": rule.start_hour,
            "end_hour": rule.end_hour,
            "severity": rule.severity
        })
        await db.commit()
        row = result.fetchone()
        
        # Mapping row directly to response (SQLAlchemy row to Pydantic)
        return AlertRuleResponse(
            rule_id=row[0],
            merchant_id=row[1],
            rule_name=row[2],
            filter_country=row[3],
            filter_provider=row[4],
            filter_issuer=row[5],
            metric_type=row[6],
            operator=row[7],
            threshold_value=row[8],
            min_transactions=row[9],
            is_time_based=row[10],
            start_hour=row[11],
            end_hour=row[12],
            severity=row[13],
            is_active=row[14],
            created_at=row[15]
        )

    except Exception as e:
        logger.error(f"Alert rule creation failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create alert rule: {str(e)}")


@app.get("/rules")
async def get_alert_rules(
    merchant_id: str | None = None,
    is_active: bool | None = True,
    db: AsyncSession = Depends(get_db)
) -> List[AlertRuleResponse]:
    try:
        where_clauses = []
        params = {}

        if merchant_id is not None:
            where_clauses.append("merchant_id = :merchant_id")
            params["merchant_id"] = merchant_id

        if is_active is not None:
            where_clauses.append("is_active = :is_active")
            params["is_active"] = is_active

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = text(f"SELECT * FROM alert_rules {where_sql} ORDER BY created_at DESC")
        result = await db.execute(query, params)
        rows = result.fetchall()

        rules = []
        for row in rows:
            rules.append(AlertRuleResponse(
                rule_id=row[0],
                merchant_id=row[1],
                rule_name=row[2],
                filter_country=row[3],
                filter_provider=row[4],
                filter_issuer=row[5],
                metric_type=row[6],
                operator=row[7],
                threshold_value=row[8],
                min_transactions=row[9],
                is_time_based=row[10],
                start_hour=row[11],
                end_hour=row[12],
                severity=row[13],
                is_active=row[14],
                created_at=row[15]
            ))
        return rules

    except Exception as e:
        logger.error(f"Alert rules query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch alert rules: {str(e)}")


@app.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("UPDATE alert_rules SET is_active = FALSE WHERE rule_id = :rule_id RETURNING rule_id")
        result = await db.execute(query, {"rule_id": rule_id})
        await db.commit()
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Alert rule not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Alert rule deletion failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# KAM MANAGEMENT - PYDANTIC MODELS
# ============================================

class KamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

class KamResponse(BaseModel):
    kam_id: str
    name: str
    email: str
    created_at: str

class MerchantAssign(BaseModel):
    merchant_id: str = Field(..., min_length=1, max_length=100)
    kam_id: str


# ============================================
# KAM MANAGEMENT - ENDPOINTS
# ============================================

@app.get("/kams")
async def get_kams(db: AsyncSession = Depends(get_db)):
    """Get all registered KAMs"""
    try:
        query = text("""
            SELECT kam_id, name, email, created_at
            FROM kams
            ORDER BY name ASC
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        kams = []
        for row in rows:
            kams.append({
                "kam_id": str(row[0]),
                "name": row[1],
                "email": row[2],
                "created_at": row[3].isoformat() if row[3] else None
            })

        return kams

    except Exception as e:
        logger.error(f"KAMs query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch KAMs: {str(e)}")


@app.post("/kams", status_code=status.HTTP_201_CREATED)
async def create_kam(kam: KamCreate, db: AsyncSession = Depends(get_db)) -> KamResponse:
    """Register a new KAM"""
    try:
        query = text("""
            INSERT INTO kams (name, email)
            VALUES (:name, :email)
            RETURNING kam_id, name, email, created_at
        """)

        result = await db.execute(query, {
            "name": kam.name,
            "email": kam.email
        })
        await db.commit()
        row = result.fetchone()

        return KamResponse(
            kam_id=str(row[0]),
            name=row[1],
            email=row[2],
            created_at=row[3].isoformat()
        )

    except Exception as e:
        logger.error(f"KAM creation failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create KAM: {str(e)}"
        )


@app.post("/merchants/assign")
async def assign_merchant_to_kam(assignment: MerchantAssign, db: AsyncSession = Depends(get_db)):
    """Assign a merchant to a KAM (updates merchant_rules table)"""
    try:
        query = text("""
            UPDATE merchant_rules
            SET kam_id = :kam_id
            WHERE merchant_id = :merchant_id
            RETURNING merchant_id
        """)

        result = await db.execute(query, {
            "kam_id": assignment.kam_id,
            "merchant_id": assignment.merchant_id
        })
        await db.commit()

        if not result.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Merchant '{assignment.merchant_id}' not found in merchant_rules"
            )

        return {
            "status": "success",
            "message": f"Merchant {assignment.merchant_id} assigned to KAM successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merchant assignment failed: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign merchant: {str(e)}"
        )


@app.get("/")
async def root():
    return {
        "service": "Yuno Sentinel Ingestor",
        "status": "operational",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)