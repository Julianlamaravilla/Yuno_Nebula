# 🚨 Sistema de Alertas Mejorado - Yuno Sentinel

## 📋 Problema Identificado

El sistema generaba **demasiadas alertas** (tanto WARNING como CRITICAL) por:
- Umbrales muy bajos (1% error rate)
- No diferenciaba entre errores transitorios vs persistentes
- No rastreaba códigos HTTP específicos (500, 501, 502, 503, 504)
- Alertaba por errores que se auto-resolvían rápidamente

## ✅ Soluciones Implementadas

### 1. **Detección de Tendencias Persistentes** (Anti-Falsos Positivos)

**Antes:**
- Alertaba con 1 solo error de cada 100 transacciones

**Ahora:**
- Requiere **8 errores consecutivos** en ventana de 10 minutos
- Verifica que el 60% de las ventanas de tiempo tengan errores
- Solo alerta si es un patrón **persistente**

```python
# Configuración en config.py
min_consecutive_errors: 8
error_trend_window_minutes: 10
```

### 2. **Detección de Recuperación Automática**

**Nueva funcionalidad:**
- Detecta cuando un proveedor se recupera después de errores
- Requiere 5 transacciones exitosas consecutivas
- Cancela alertas activas automáticamente

```python
recovery_check_threshold: 5  # txns exitosas para marcar como recuperado
```

### 3. **Análisis de Códigos HTTP**

**Antes:**
- Solo reportaba "ERROR" sin detalles

**Ahora:**
- Desglose por código de respuesta (500, 502, 503, 504)
- Identifica el código más frecuente
- Recomienda acciones específicas por tipo de error

```python
# Ejemplo de output
Response codes: {'504': 45, '502': 12, '500': 3}
Most common: 504 (Gateway Timeout)
Action: "Increase timeout or failover"
```

### 4. **Acciones Recomendadas Inteligentes**

| Código HTTP | Acción Recomendada |
|-------------|-------------------|
| 504, 503, 502 | Aumentar timeout o failover |
| 500 | Contactar proveedor (error interno) |
| Otros | Pausar tráfico temporalmente |

### 5. **Umbrales Ajustados**

| Métrica | Antes | Ahora | Razón |
|---------|-------|-------|-------|
| Error Rate Alert | 1% | 10% | Más sensible pero realista |
| Min Transactions | 20 | 30 | Muestra estadísticamente significativa |
| Alert Cooldown | 5 min | 10 min | Evita spam de alertas |
| CRITICAL Severity | Random 10% | Error > 30% | Basado en impacto real |

## 🎯 Ejemplo de Flujo

### Escenario: 6 errores 500 que se auto-resuelven

**Antes:**
```
1. Error 1 → ❌ Alerta inmediata
2. Error 2 → ❌ Otra alerta (sin cooldown suficiente)
3. Error 3-6 → ❌ Más alertas
7. Se recupera → ⚠️ Sigue mostrando alerta activa
```

**Ahora:**
```
1-7. Errores 1-7 → ✅ No alerta (< 8 consecutivos)
8. Error 8 → ⚠️ Verifica tendencia
   - Chequea ventana de 10min
   - Verifica si es patrón persistente
   - ❌ NO alerta (solo 8 errores, no es persistente)
9. Se recupera → ✅ Detecta recuperación automática
```

### Escenario: Problema real persistente con Stripe

**Antes:**
```
Status ERROR - rate 15%
→ Alerta genérica sin detalles
```

**Ahora:**
```
🔍 Análisis profundo:
- Error rate: 25% (75/300 txns)
- Tendencia: Persistente (10 min)
- Response codes: {'504': 60, '503': 15}
- Proveedor: STRIPE
- País: MX
- Issuer: BBVA (50/75 errores)

🚨 ALERTA:
Severity: CRITICAL
Title: "STRIPE MX - Persistent Timeouts (HTTP 504)"
Root Cause: "BBVA issuer específico"
Action: "Failover BBVA a dLocal"
```

## 📊 Métricas de Reducción de Alertas

**Estimado de reducción:**
- **Falsos positivos**: -80%
- **Alertas duplicadas**: -60%
- **Alertas sin acción**: -70%

**Alertas que SÍ se mantienen:**
- Problemas persistentes reales
- Impacto financiero significativo
- Patrones anómalos confirmados

## 🔧 Archivos Modificados

1. **backend/config.py**
   - Nuevos parámetros de tendencias
   - Umbrales ajustados

2. **backend/worker.py**
   - `check_error_trend()` - Detecta patrones persistentes
   - `check_recovery()` - Detecta recuperación automática
   - `get_error_code_breakdown()` - Analiza códigos HTTP
   - `should_alert()` - Cooldown inteligente
   - `determine_root_cause()` - Incluye códigos de error

## 🚀 Próximos Pasos Sugeridos

1. **Machine Learning** (futuro):
   - Aprender baseline por merchant
   - Detección de anomalías con Z-score

2. **Alert Grouping**:
   - Agrupar alertas relacionadas
   - "3 proveedores afectados en MX"

3. **Notification Routing**:
   - CRITICAL → PagerDuty
   - WARNING → Slack
