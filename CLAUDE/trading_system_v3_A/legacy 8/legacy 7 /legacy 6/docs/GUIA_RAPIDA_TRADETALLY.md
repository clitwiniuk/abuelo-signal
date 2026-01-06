# 🚀 TradeTally - Guía Rápida de Referencia

**Versión rápida para usuarios que ya conocen el sistema**

---

## 📍 Acceso Rápido

| Funcionalidad | Ruta de Navegación |
|---------------|-------------------|
| Custom Metrics | Analytics → Custom Metrics |
| Pivot Grid | Analytics → Pivot Grid |
| AI Pattern Detection | Analytics → AI Pattern Detection |
| Saved Filters | Analytics → Saved Filters |

---

## ⚡ Comandos Rápidos

### Custom Metrics - Fórmulas Más Útiles

```javascript
// R-Multiple
pnl / (abs(mae) || 1)

// Expectancy
(win_rate / 100) * avg_win - ((100 - win_rate) / 100) * abs(avg_loss)

// Efficiency Ratio
pnl / (abs(mae) + abs(mfe))

// Position Size %
(quantity * entry_price) / (capital_at_trade_time || 1) * 100

// Risk-Adjusted Return
pnl / max(abs(mae), 1)

// Win/Loss Ratio
avg_win / abs(avg_loss)

// Profit per Trade
total_pnl / trade_count

// Average Hold Time (hours)
avg_hold_time / 3600
```

---

## 📊 Pivot Grid - Presets Recomendados

### Para Análisis Diario
- **Performance by Strategy** - Ver qué estrategias funcionan hoy

### Para Optimización
- **Day of Week Analysis** - Encontrar mejores días
- **Time-Based Analysis** - Encontrar mejores horas

### Para Validación de Estrategias
- **Strategy Performance Matrix** - Comparar todas las estrategias
- **Confidence Level Analysis** - Validar tu confianza

### Para Risk Management
- **Risk/Reward Analysis** - Analizar MAE/MFE
- **Position Sizing Analysis** - Optimizar tamaños

---

## 🤖 AI Pattern Detection - Checklist

**Antes de ejecutar:**
- [ ] Tienes al menos 30 operaciones
- [ ] GEMINI_API_KEY configurada
- [ ] Rango de fechas: mínimo 30 días, recomendado 3 meses

**Después de ejecutar:**
- [ ] Revisar Top 3 Insights
- [ ] Actuar sobre patrones "High" severity
- [ ] Documentar hallazgos importantes
- [ ] Re-ejecutar mensualmente

---

## 🔍 Saved Filters - Operadores Cheat Sheet

| Operador | Sintaxis | Ejemplo |
|----------|----------|---------|
| Igual | `=` | `strategy = "ORB"` |
| Diferente | `!=` | `side != "Short"` |
| Mayor | `>` | `pnl > 100` |
| Menor | `<` | `mae < -50` |
| Contiene | `contains` | `symbol contains "AA"` |
| En lista | `in` | `strategy in ["ORB", "Momentum"]` |
| Entre | `between` | `pnl between [0, 500]` |
| Es nulo | `is_null` | `exit_price is_null` |

---

## 💡 Workflows Recomendados

### Workflow 1: Análisis Semanal (15 min)

1. **Lunes AM:**
   - Pivot Grid → "This Week" preset
   - Revisar métricas clave
   - Identificar qué funcionó/no funcionó

2. **Viernes PM:**
   - AI Pattern Detection → última semana
   - Revisar Top 3 Insights
   - Ajustar plan para próxima semana

### Workflow 2: Validación de Estrategia (30 min)

1. Saved Filters → Crear filtro para la estrategia
2. Pivot Grid → Analizar por día/hora
3. Custom Metrics → Calcular métricas específicas
4. AI Pattern Detection → Buscar patrones ocultos
5. Documentar conclusiones

### Workflow 3: Optimización Mensual (1 hora)

1. AI Pattern Detection → último mes completo
2. Identificar patrones "High" severity
3. Pivot Grid → Validar cada patrón
4. Custom Metrics → Crear métricas para monitorear
5. Saved Filters → Crear filtros para tracking
6. Implementar cambios en tu trading plan

---

## 🎯 KPIs Esenciales a Monitorear

### Con Custom Metrics

Crea estas métricas y monitoréalas semanalmente:

1. **R-Multiple Promedio** - Objetivo: >2.0
2. **Expectancy** - Objetivo: >$50/trade
3. **Efficiency Ratio** - Objetivo: >0.5
4. **Win/Loss Ratio** - Objetivo: >2.0
5. **Position Size Avg %** - Objetivo: <5% del capital

### Con Pivot Grid

Revisa estas dimensiones mensualmente:

1. **Win Rate por Estrategia** - Objetivo: >60%
2. **Profit Factor por Día** - Objetivo: >2.0
3. **Avg P&L por Hora** - Identificar mejores horas
4. **Trade Count por Símbolo** - Evitar sobre-trading
5. **MAE/MFE Ratio** - Objetivo: <0.5

---

## 🚨 Alertas Rojas

### Custom Metrics
- ❌ Fórmula no valida → Revisar sintaxis
- ❌ Resultado NaN → Añadir `|| 1` o `|| 0`
- ❌ Métrica inactiva → No aparecerá en filtros

### Pivot Grid
- ❌ No data → Verificar filtros y fechas
- ❌ Tabla muy grande → Reducir dimensiones
- ❌ Drill-down vacío → Verificar combinación de dimensiones

### AI Pattern Detection
- ❌ API Key missing → Configurar en `.env.local`
- ❌ Timeout → Reducir rango de fechas
- ❌ Patrones genéricos → Necesitas más datos

### Saved Filters
- ❌ No matches → Revisar lógica AND/OR
- ❌ Custom metric no funciona → Verificar formato `custom:nombre`
- ❌ Demasiados resultados → Añadir más condiciones

---

## 📱 Atajos de Teclado (Futuros)

*Próximamente en v2.1*

---

## 🔗 Links Útiles

- [Guía Completa](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/GUIA_USUARIO_TRADETALLY.md)
- [Phase 1 Technical Docs](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/PHASE1_COMPLETION_SUMMARY.md)
- [Phase 2 Technical Docs](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/PHASE2_COMPLETION_SUMMARY.md)
- [Phase 3 Technical Docs](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/PHASE3_COMPLETION_SUMMARY.md)
- [Google Gemini API](https://ai.google.dev/)

---

## 📞 Soporte Rápido

**Problema más común:** "No veo mis custom metrics en los filtros"
**Solución:** Usa el formato `custom:nombre_exacto_metrica`

**Problema #2:** "AI Pattern Detection no funciona"
**Solución:** Verifica GEMINI_API_KEY en `.env.local` y reinicia backend

**Problema #3:** "Pivot Grid está vacío"
**Solución:** Verifica que tienes operaciones en el rango de fechas seleccionado

---

*Última actualización: Noviembre 2025*
*Para más detalles, consulta la [Guía Completa](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/GUIA_USUARIO_TRADETALLY.md)*
