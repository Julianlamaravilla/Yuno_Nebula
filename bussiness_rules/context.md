# YUNO SENTINEL - PROJECT CONTEXT & SPECIFICATIONS

## 1. Goal
Build "Yuno Sentinel", a Real-time Financial Observability & Self-Healing system.
It monitors payment transactions, detects anomalies (technical vs business), calculates financial impact ($), and suggests actionable fixes.

## 2. Architecture (Monorepo)
* **Infrastructure:** Docker Compose (5 services).
* **Services:**
    * `db`: PostgreSQL 15.
    * `redis`: Redis 7 (Alpine).
    * `ingestor`: Python FastAPI (Port 8000).
    * `worker`: Python script (The Brain).
    * `dashboard`: Streamlit (Port 8501).
    * `simulator`: Python script with Faker.

## 3. Data Contracts (STRICT)

### A. Input Transaction JSON (From Simulator to Ingestor)
*Based on Yuno Official Docs "The Payment Object".*
```json
{
  "id": "uuid-v4",
  "created_at": "ISO8601_TIMESTAMP",
  "merchant_id": "merchant_shopito",
  "country": "MX",
  "status": "ERROR",  // Options: CREATED, SUCCEEDED, DECLINED, ERROR, REJECTED
  "sub_status": "TIMEOUT", // Options: TIMEOUT, INSUFFICIENT_FUNDS, FRAUD, DO_NOT_HONOR
  "amount": { 
      "value": 1500.00, 
      "currency": "MXN" 
  },
  "payment_method": {
    "type": "CARD",
    "detail": {
      "card": {
        "brand": "VISA",
        "issuer_name": "BBVA",      // CRITICAL for granular analysis
        "bin": "415231"
      }
    }
  },
  "provider_data": {
    "id": "STRIPE",
    "merchant_advice_code": "TRY_AGAIN_LATER", // Use for recommendations
    "response_code": "504"
  },
  "latency_ms": 5200 // Calculated field
}



B. Alert Object JSON (Output from Worker to Dashboard)

{
  "alert_id": "uuid",
  "timestamp": "ISO8601",
  "severity": "CRITICAL", // CRITICAL, WARNING
  "confidence_score": 0.95, // 0.0 to 1.0
  "title": "Stripe MX Outage - BBVA Impact",
  "description_llm": "Generated text explaining the issue...",
  "impact": {
    "revenue_at_risk_usd": 4500.00,
    "affected_transactions": 150,
    "sla_breach_countdown_seconds": 240 // Time until SLA fine
  },
  "root_cause": {
    "provider": "Stripe",
    "issue": "High Latency & Timeouts",
    "scope": "BBVA Issuers only"
  },
  "suggested_action": {
    "label": "Reroute to dLocal",
    "action_type": "FAILOVER_PROVIDER"
  }
}


4. Database Schema (PostgreSQL)
Table: events_log

event_id (UUID, PK)

created_at (TIMESTAMP, Indexed)

merchant_id (VARCHAR, Indexed)

provider_id (VARCHAR, Indexed)

status (VARCHAR, Indexed)

amount_usd (DECIMAL)

raw_payload (JSONB, GIN Indexed) -> Stores the full Input Transaction JSON.

Table: merchant_rules

merchant_id (PK)

sla_minutes (INT) -> e.g., 5 minutes allowed downtime.

avg_approval_rate (DECIMAL) -> e.g., 0.70.

5. Logic & Business Rules
Real-time Detection: Worker checks Redis sliding windows every 10 seconds.

Red Alert: Any status=ERROR or sub_status=TIMEOUT is an infrastructure failure.

Yellow Alert: If status=DECLINED rate exceeds avg_approval_rate by 20%.

Granularity: If an alert triggers, query Postgres JSONB to check if it's specific to an issuer_name (Bank).

Self-Healing: If merchant_advice_code is TRY_AGAIN_LATER, suggest "Pause Traffic".



---

### 🚀 Paso 2: El Prompt Maestro (Actualizado)

Copia y pega esto en Claude **después de adjuntar el archivo**.

 **Role:** You are a Senior Payment Systems Architect participating in a Hackathon.

 **Task:** Generate the complete project scaffolding for "Yuno Sentinel".

 **Instructions:**
 1.  **Read the attached `CONTEXT.md` file carefully.** It contains the strict Source of Truth for JSON schemas, Database models, and Business Logic. Do not deviate from these definitions.
 2.  **Generate the Project Structure:** Create a Monorepo structure (`/backend`, `/frontend`, `/simulator`, `/database`).
 3.  **Generate `docker-compose.yml`:** Orchestrate the 5 services defined in the Context.
 4.  **Generate `database/init.sql`:** Write the SQL to create the tables `events_log` (with Hybrid JSONB pattern) and `merchant_rules` as specified in the Context.
 5.  **Generate `backend/schemas.py`:** Create Pydantic models that exactly match the "Input Transaction JSON" and "Alert Object JSON" from the Context.
 6.  **Generate `simulator/main.py`:** Create a Python script using `Faker` that generates realistic transactions matching the "Input Transaction JSON". Include a function `inject_chaos(scenario)` to simulate a "Stripe Timeout" (status=ERROR).

 **Focus:** Ensuring the Data Contract between Simulator -> Backend -> Database -> Frontend is consistent with `CONTEXT.md`.

---

### ¿Qué ganas con esto?
1.  **Frontend y Backend alineados:** Ambos usarán los mismos nombres de variables (`revenue_at_risk_usd`) desde el minuto 1.
2.  **Simulador Realista:** El script de caos generará los datos exactos que tu base de datos espera.
3.  **Cero Retrabajo:** No tendrás que corregir nombres de tablas o campos a la mitad de la noche.
