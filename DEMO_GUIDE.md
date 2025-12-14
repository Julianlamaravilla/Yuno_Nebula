# 🎯 CHEATSHEET COMPLETO - YUNO SENTINEL DEMO

## 1️⃣ PUSH CAMBIOS
```bash
git push origin main
```

## 2️⃣ LEVANTAR SISTEMA
```bash
# Desde raíz del proyecto
docker-compose down -v  # Limpiar todo
docker-compose up --build
```

**Espera a ver estos logs:**
- ✅ `db_1       | database system is ready to accept connections`
- ✅ `redis_1    | Ready to accept connections`
- ✅ `ingestor_1 | Uvicorn running on http://0.0.0.0:8000`
- ✅ `worker_1   | Worker started - checking every 10s`
- ✅ `simulator_1| Simulator started - generating traffic`

## 3️⃣ VERIFICAR SALUD
```bash
# Health check
curl http://localhost:8000/health

# Ver reglas seed (deben existir 4)
curl http://localhost:8000/rules | jq
```

## 4️⃣ ABRIR FRONTEND
```
http://localhost:3000
```

## 5️⃣ CREAR REGLA DE PRUEBA

**Click en "Rule Settings" → "Create New Rule"**

```yaml
Rule Name: "Demo - High Error Rate"
Merchant: merchant_shopito
Country: (vacío - All Countries)
Provider: STRIPE
Issuer: (vacío)
Metric Type: ERROR_RATE
Operator: >
Threshold: 0.05
Min Transactions: 10
Time-Based: ❌ OFF
Severity: CRITICAL
```

**Click "Create Rule"**

⏳ **ESPERAR 15 SEGUNDOS** (worker recarga)

## 6️⃣ LANZAR CHAOS (Simulator)

```bash
# Inyectar errores de Stripe
docker-compose exec simulator python -c "
from main import TransactionSimulator
import asyncio

async def chaos():
    sim = TransactionSimulator()
    sim.inject_chaos('STRIPE_TIMEOUT', {'provider': 'STRIPE', 'country': 'MX'})
    await sim.start(duration_seconds=60, tps=5)

asyncio.run(chaos())
"
```

O más simple, modifica `simulator/main.py` línea 180:
```python
# Descomentar esta línea
simulator.inject_chaos("STRIPE_TIMEOUT", {"provider": "STRIPE", "country": "MX"})
```

## 7️⃣ VERIFICAR RESULTADOS

**En Frontend (cada 5s auto-refresh):**
- Revenue at Risk > $0
- Active Alerts > 0
- Alert Feed muestra tarjeta CRITICAL

**En API:**
```bash
curl http://localhost:8000/alerts | jq
```

## 8️⃣ TROUBLESHOOTING

**No aparecen alertas:**
```bash
# Ver logs del worker
docker-compose logs worker -f

# Verificar que la regla existe
curl http://localhost:8000/rules | jq '.[] | select(.rule_name | contains("Demo"))'

# Ver métricas en Redis
docker-compose exec redis redis-cli KEYS "stats:*"
```

**Simulator no envía datos:**
```bash
docker-compose logs simulator -f
# Debe mostrar: "Sent 5 transactions..."
```

**Frontend no carga:**
```bash
docker-compose logs frontend -f
# Verificar puerto 3000 libre
```

## 9️⃣ DEMO SCRIPT (PRESENTACIÓN)

1. **Mostrar dashboard limpio** (sin alertas)
2. **Abrir Settings** → Mostrar reglas pre-configuradas
3. **Crear regla nueva** → Explicar filtros granulares
4. **Esperar 10s** → Mencionar "worker reload"
5. **Inyectar caos** → "Simulamos error de Stripe"
6. **Watch the magic** → Alerta aparece automáticamente
7. **Mostrar LLM explanation** → "Gemini generó esto"
8. **Highlight revenue at risk** → "$X perdidos"

## 🔟 RESETEAR PARA NUEVA DEMO
```bash
# Limpiar alertas
docker-compose exec db_1 psql -U yuno_admin -d yuno_sentinel -c "DELETE FROM alerts;"

# Reiniciar Redis (métricas)
docker-compose exec redis redis-cli FLUSHALL

# Parar chaos
docker-compose restart simulator
```

---

**🎯 REGLA DE ORO:** Siempre esperar 10-15s después de crear regla antes de chaos.

**⚠️ TIMEZONE:** Dejar time-based OFF o verificar hora UTC: `date -u`
