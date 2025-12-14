-- Yuno Sentinel - Database Initialization Script
-- Hybrid Relational + JSONB Pattern for Granular Analysis

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLE: kams (Key Account Managers)
-- Stores KAM information for merchant assignment
-- ============================================
CREATE TABLE kams (
    kam_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for email lookups
CREATE INDEX idx_kams_email ON kams(email);

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
-- NOW WITH KAM ASSIGNMENT (1:N relationship)
-- ============================================
CREATE TABLE merchant_rules (
    merchant_id VARCHAR(100) PRIMARY KEY,
    kam_id UUID NOT NULL REFERENCES kams(kam_id) ON DELETE RESTRICT,
    sla_minutes INTEGER NOT NULL DEFAULT 5,
    avg_approval_rate DECIMAL(4,3) NOT NULL DEFAULT 0.70,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for KAM lookups
CREATE INDEX idx_merchant_rules_kam ON merchant_rules(kam_id);

-- ============================================
-- TABLE: alert_rules
-- Dynamic alert rules with scope-based thresholds
-- ============================================
CREATE TABLE alert_rules (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id VARCHAR(100),  -- NULL = global rule
    rule_name VARCHAR(255),

    -- Filters (NULL = applies to all)
    filter_country CHAR(2),
    filter_provider VARCHAR(50),
    filter_issuer VARCHAR(100),  -- For issuer-specific rules (e.g., "BBVA")

    -- Metric configuration
    metric_type VARCHAR(50) NOT NULL,  -- 'APPROVAL_RATE', 'ERROR_RATE', 'DECLINE_RATE', 'TOTAL_VOLUME'
    operator VARCHAR(10) NOT NULL,     -- '<', '>', '>=', '<='
    threshold_value DECIMAL(5,2) NOT NULL,
    min_transactions INT DEFAULT 10,   -- Minimum sample size

    -- Time-based rules (for peak hours, business hours, etc.)
    is_time_based BOOLEAN NOT NULL DEFAULT FALSE,
    start_hour INTEGER CHECK (start_hour >= 0 AND start_hour < 24),
    end_hour INTEGER CHECK (end_hour >= 0 AND end_hour < 24),

    -- Alert action
    severity VARCHAR(20) DEFAULT 'WARNING' CHECK (severity IN ('CRITICAL', 'WARNING')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_alert_rules_merchant ON alert_rules(merchant_id);
CREATE INDEX idx_alert_rules_active ON alert_rules(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_alert_rules_lookup ON alert_rules(merchant_id, filter_country, filter_provider) WHERE is_active = TRUE;

-- ============================================
-- SEED DATA: KAMs and Merchants
-- ============================================

-- Insert KAM
INSERT INTO kams (name, email) VALUES
    ('Julián Admin', 'julian.admin@yunosentinel.com');

-- Get KAM ID for merchant assignment
DO $$
DECLARE
    julian_kam_id UUID;
BEGIN
    SELECT kam_id INTO julian_kam_id FROM kams WHERE email = 'julian.admin@yunosentinel.com';

    -- Insert merchants assigned to Julián
    INSERT INTO merchant_rules (merchant_id, kam_id, sla_minutes, avg_approval_rate) VALUES
        ('merchant_shopito', julian_kam_id, 5, 0.72),
        ('merchant_rappi', julian_kam_id, 3, 0.75),
        ('merchant_uber', julian_kam_id, 4, 0.78),
        ('merchant_techstore', julian_kam_id, 3, 0.68),
        ('merchant_fashionhub', julian_kam_id, 5, 0.75);
END $$;

-- ============================================
-- SEED DATA: Alert Rules
-- ============================================

-- Limpiar reglas viejas
TRUNCATE alert_rules;

-- ESCENARIO 1: "Hora Pico" (Alta Exigencia)
-- "Si son entre las 9 AM y 6 PM, exijo 95% de aprobación. Si baja, ALERTA CRÍTICA."
INSERT INTO alert_rules (merchant_id, rule_name, is_time_based, start_hour, end_hour, metric_type, operator, threshold_value, severity)
VALUES ('merchant_shopito', 'SLA Hora Pico (Strict)', TRUE, 9, 18, 'APPROVAL_RATE', '<', 0.95, 'CRITICAL');

-- ESCENARIO 2: "Hora Valle" (Baja Exigencia)
-- "Si son las 3 AM (00-05), relájate. Solo avisa si la aprobación cae al 50%."
INSERT INTO alert_rules (merchant_id, rule_name, is_time_based, start_hour, end_hour, metric_type, operator, threshold_value, severity)
VALUES ('merchant_shopito', 'Monitoreo Hora Valle', TRUE, 0, 5, 'APPROVAL_RATE', '<', 0.50, 'WARNING');

-- ESCENARIO 3: "Transacciones Aprobadas por Merchant"
-- "Para Shopito en Colombia, avisa si hay CERO transacciones (Caída Total)."
INSERT INTO alert_rules (merchant_id, rule_name, filter_country, metric_type, operator, threshold_value, severity)
VALUES ('merchant_shopito', 'Blackout Colombia', 'CO', 'TOTAL_VOLUME', '<', 1, 'CRITICAL');

-- ESCENARIO 4: "Granularidad (Issuer/Cuenta)"
-- "Si falla BBVA específicamente en Stripe, avisa rápido (5% error)."
INSERT INTO alert_rules (merchant_id, rule_name, filter_provider, filter_issuer, metric_type, operator, threshold_value, severity)
VALUES ('merchant_shopito', 'Fallo Específico BBVA', 'STRIPE', 'BBVA', 'ERROR_RATE', '>', 0.05, 'WARNING');

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

-- View: KAM Dashboard - Merchants and their metrics
CREATE OR REPLACE VIEW v_kam_merchants AS
SELECT
    k.kam_id,
    k.name as kam_name,
    k.email as kam_email,
    mr.merchant_id,
    mr.sla_minutes,
    mr.avg_approval_rate,
    COUNT(DISTINCT e.event_id) as total_transactions_today
FROM kams k
INNER JOIN merchant_rules mr ON k.kam_id = mr.kam_id
LEFT JOIN events_log e ON mr.merchant_id = e.merchant_id
    AND e.created_at >= CURRENT_DATE
GROUP BY k.kam_id, k.name, k.email, mr.merchant_id, mr.sla_minutes, mr.avg_approval_rate
ORDER BY k.name, mr.merchant_id;

-- ============================================
-- COMMENTS
-- ============================================
COMMENT ON TABLE kams IS 'Key Account Managers - manage multiple merchant accounts';
COMMENT ON TABLE events_log IS 'Stores all payment transaction events with full JSONB payload for granular analysis';
COMMENT ON TABLE alerts IS 'Stores anomaly detection alerts with LLM-generated explanations';
COMMENT ON TABLE merchant_rules IS 'Merchant-specific SLA thresholds and approval rate baselines with KAM assignment';
COMMENT ON COLUMN merchant_rules.kam_id IS 'Foreign key to kams table - each merchant has one KAM';
COMMENT ON COLUMN events_log.raw_payload IS 'Full Yuno payment object in JSONB format - enables issuer/BIN level queries';
COMMENT ON INDEX idx_events_raw_payload IS 'GIN index for fast JSONB queries on payment_method, issuer_name, etc.';
