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


async def get_merchant_rules(merchant_id: str):
    """Fetch merchant-specific rules"""
    query = """
    SELECT sla_minutes, avg_approval_rate
    FROM merchant_rules
    WHERE merchant_id = :merchant_id
    """

    result = await execute_raw_query(query, {"merchant_id": merchant_id})
    if result:
        row = result[0]
        return {"sla_minutes": row[0], "avg_approval_rate": float(row[1])}
    return {"sla_minutes": 5, "avg_approval_rate": 0.70}  # Defaults
