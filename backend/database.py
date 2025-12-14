"""
Yuno Sentinel - Database Setup
Async SQLAlchemy engine and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from config import settings
import logging

logger = logging.getLogger(__name__)

# Create async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.env == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency for FastAPI endpoints
    Yields database session and ensures proper cleanup
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Check if database is reachable"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def execute_raw_query(query: str, params: dict = None):
    """
    Execute raw SQL query (useful for JSONB queries)

    Example:
        result = await execute_raw_query(
            "SELECT * FROM events_log WHERE raw_payload->>'country' = :country",
            {"country": "MX"}
        )
    """
    async with async_session_maker() as session:
        result = await session.execute(text(query), params or {})
        return result.fetchall()


async def get_issuer_breakdown(provider_id: str, minutes: int = 15):
    """
    Get error breakdown by issuer for a specific provider
    Uses JSONB operators for granular analysis
    """
    query = """
    SELECT
        raw_payload->'payment_method'->'detail'->'card'->>'issuer_name' as issuer_name,
        raw_payload->>'country' as country,
        COUNT(*) as error_count,
        SUM(amount_usd) as revenue_at_risk_usd,
        ARRAY_AGG(DISTINCT raw_payload->>'sub_status') as sub_statuses
    FROM events_log
    WHERE
        provider_id = :provider_id
        AND status = 'ERROR'
        AND created_at >= NOW() - INTERVAL ':minutes minutes'
        AND raw_payload->'payment_method'->'detail'->'card'->>'issuer_name' IS NOT NULL
    GROUP BY issuer_name, country
    HAVING COUNT(*) >= 3
    ORDER BY error_count DESC
    """

    return await execute_raw_query(query, {"provider_id": provider_id, "minutes": minutes})


async def get_alert_rules(merchant_id: str, country: str = None, provider: str = None):
    """
    Fetch active alert rules for a merchant with optional scope filtering

    Args:
        merchant_id: Merchant identifier
        country: Optional country filter
        provider: Optional provider filter

    Returns:
        List of applicable alert rules
    """
    query = """
    SELECT
        rule_id,
        rule_name,
        scope_country,
        scope_provider,
        scope_method,
        metric_type,
        operator,
        threshold_value,
        min_transactions,
        severity
    FROM alert_rules
    WHERE merchant_id = :merchant_id
      AND is_active = TRUE
      AND (scope_country IS NULL OR scope_country = :country)
      AND (scope_provider IS NULL OR scope_provider = :provider)
    ORDER BY severity DESC, threshold_value ASC
    """

    result = await execute_raw_query(query, {
        "merchant_id": merchant_id,
        "country": country,
        "provider": provider
    })

    rules = []
    for row in result:
        rules.append({
            "rule_id": str(row[0]),
            "rule_name": row[1],
            "scope_country": row[2],
            "scope_provider": row[3],
            "scope_method": row[4],
            "metric_type": row[5],
            "operator": row[6],
            "threshold_value": float(row[7]),
            "min_transactions": row[8],
            "severity": row[9]
        })

    return rules
