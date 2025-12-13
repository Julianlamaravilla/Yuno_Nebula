-- Yuno Sentinel - Database Initialization Script
-- Hybrid Relational + JSONB Pattern for Granular Analysis

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLE: events_log
-- Stores all payment transaction events
-- ============================================
CREATE TABLE events_log (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    merchant_id VARCHAR(100) NOT NULL,
    provider_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    amount_usd DECIMAL(12,2) NOT NULL,
    raw_payload JSONB NOT NULL
);

-- Indexes for fast queries
CREATE INDEX idx_events_created_at ON events_log(created_at DESC);
CREATE INDEX idx_events_merchant ON events_log(merchant_id);
CREATE INDEX idx_events_provider ON events_log(provider_id);
CREATE INDEX idx_events_status ON events_log(status);

-- GIN index for JSONB queries (enables issuer-level analysis)
CREATE INDEX idx_events_raw_payload ON events_log USING GIN(raw_payload);

-- Composite index for common queries
CREATE INDEX idx_events_provider_status_time ON events_log(provider_id, status, created_at DESC);

-- ============================================
-- TABLE: alerts
-- Stores detected anomalies and incidents
-- ============================================
CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('CRITICAL', 'WARNING')),
    confidence_score FLOAT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    title VARCHAR(255) NOT NULL,
    revenue_at_risk_usd DECIMAL(12,2) NOT NULL,
    affected_transactions INTEGER NOT NULL,
    sla_breach_countdown_seconds INTEGER,
    root_cause JSONB NOT NULL,
    llm_explanation TEXT,
    suggested_action JSONB NOT NULL
);

-- Indexes for alert queries
CREATE INDEX idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_root_cause ON alerts USING GIN(root_cause);

-- ============================================
-- TABLE: merchant_rules
-- Stores merchant-specific SLA and baselines
-- ============================================
CREATE TABLE merchant_rules (
    merchant_id VARCHAR(100) PRIMARY KEY,
    sla_minutes INTEGER NOT NULL DEFAULT 5,
    avg_approval_rate DECIMAL(4,3) NOT NULL DEFAULT 0.70,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- SEED DATA: Insert sample merchant rules
-- ============================================
INSERT INTO merchant_rules (merchant_id, sla_minutes, avg_approval_rate) VALUES
    ('merchant_shopito', 5, 0.72),
    ('merchant_techstore', 3, 0.68),
    ('merchant_fashionhub', 5, 0.75);

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to extract issuer name from JSONB payload
CREATE OR REPLACE FUNCTION get_issuer_name(payload JSONB)
RETURNS TEXT AS $$
BEGIN
    RETURN payload->'payment_method'->'detail'->'card'->>'issuer_name';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to extract card brand from JSONB payload
CREATE OR REPLACE FUNCTION get_card_brand(payload JSONB)
RETURNS TEXT AS $$
BEGIN
    RETURN payload->'payment_method'->'detail'->'card'->>'brand';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to extract country from JSONB payload
CREATE OR REPLACE FUNCTION get_country(payload JSONB)
RETURNS TEXT AS $$
BEGIN
    RETURN payload->>'country';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================
-- VIEWS: Useful aggregations
-- ============================================

-- View: Recent transactions with issuer breakdown
CREATE OR REPLACE VIEW v_recent_transactions AS
SELECT
    event_id,
    created_at,
    merchant_id,
    provider_id,
    status,
    amount_usd,
    get_issuer_name(raw_payload) as issuer_name,
    get_card_brand(raw_payload) as card_brand,
    get_country(raw_payload) as country,
    raw_payload->>'sub_status' as sub_status,
    (raw_payload->>'latency_ms')::INTEGER as latency_ms
FROM events_log
ORDER BY created_at DESC
LIMIT 1000;

-- View: Provider performance summary (last hour)
CREATE OR REPLACE VIEW v_provider_performance AS
SELECT
    provider_id,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN status = 'SUCCEEDED' THEN 1 ELSE 0 END) as succeeded,
    SUM(CASE WHEN status = 'DECLINED' THEN 1 ELSE 0 END) as declined,
    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as errors,
    ROUND(AVG(amount_usd), 2) as avg_amount_usd,
    ROUND(
        SUM(CASE WHEN status = 'SUCCEEDED' THEN 1 ELSE 0 END)::DECIMAL /
        NULLIF(COUNT(*), 0), 3
    ) as approval_rate
FROM events_log
WHERE created_at >= NOW() - INTERVAL '1 hour'
GROUP BY provider_id;

-- View: Issuer-specific error analysis
CREATE OR REPLACE VIEW v_issuer_errors AS
SELECT
    provider_id,
    get_issuer_name(raw_payload) as issuer_name,
    get_country(raw_payload) as country,
    COUNT(*) as error_count,
    SUM(amount_usd) as revenue_at_risk_usd,
    ARRAY_AGG(DISTINCT raw_payload->>'sub_status') as sub_statuses
FROM events_log
WHERE status = 'ERROR'
  AND created_at >= NOW() - INTERVAL '15 minutes'
  AND get_issuer_name(raw_payload) IS NOT NULL
GROUP BY provider_id, get_issuer_name(raw_payload), get_country(raw_payload)
HAVING COUNT(*) >= 3
ORDER BY error_count DESC;

-- ============================================
-- COMMENTS
-- ============================================
COMMENT ON TABLE events_log IS 'Stores all payment transaction events with full JSONB payload for granular analysis';
COMMENT ON TABLE alerts IS 'Stores anomaly detection alerts with LLM-generated explanations';
COMMENT ON TABLE merchant_rules IS 'Merchant-specific SLA thresholds and approval rate baselines';
COMMENT ON COLUMN events_log.raw_payload IS 'Full Yuno payment object in JSONB format - enables issuer/BIN level queries';
COMMENT ON INDEX idx_events_raw_payload IS 'GIN index for fast JSONB queries on payment_method, issuer_name, etc.';
