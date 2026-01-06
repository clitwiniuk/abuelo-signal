# Volume Absorption Worker - DESACTIVADO

**Fecha**: 2025-12-04
**Estado**: DISABLED
**Razón**: Worker no robusto para smallcaps en baja temporalidad

---

## 📊 Problemas Identificados

### 1. **Overtrading Masivo**
- **Regression Test**: 67 trades simulados vs 11 trades reales en 2025-12-03
- **Causa**: Bug en ReplayEngine que resetea cooldowns entre eventos
- **Impacto**: Sistema entra/sale múltiples veces en el mismo símbolo (QCLS: 10 trades en un día)

### 2. **Stops Demasiado Ajustados**
- **Configuración actual**: 5% Take Profit / 2% Stop Loss
- **Problema**: Causa whipsaw en volatilidad de smallcaps (2-5x mayor que largecaps)
- **Resultado**: Enter-exit-enter-exit constante (scalping involuntario)

### 3. **Inadecuado para Baja Temporalidad**
- **Timeframe**: 1 minuto
- **Problema**: Ruido excesivo en 1min bars para smallcaps
- **Spreads**: 1-3% en smallcaps vs 0.1% en largecaps
- **Resultado**: Stops se disparan por ruido, no por movimientos reales

### 4. **Performance Negativa**
- **Win Rate**: 41.7% (necesita >50% con R:R 1:1)
- **P&L 2025-12-04**: -22.36% (14 trades, 5W/7L)
- **Trades <50% confianza**: 5 trades perdieron -19.24%

---

## 🔍 Análisis de Resultados

### **2025-12-04 (día problemático)**
```
Total Trades:     14
Closed:           12 (5W/7L)
Win Rate:         41.7%
Total P&L:        -22.36%
Avg P&L:          -1.60%
Avg Confidence:   66.1%
Low Conf Trades:  5 (<50% conf) → lost -1.78%
```

**Peores trades** (baja confianza):
- SLS: 28.28% conf → -3.69%
- CGC: 27.70% conf → -3.27%
- KALA: 29.46% conf → -12.28%

### **2025-12-03 (día positivo pero sospechoso)**
```
Total Trades:     11
Win Rate:         60.0%
Total P&L:        +83.85%
```

**Pero en regression test**:
- Simulación generó **67 trades** (6x más)
- Indica overtrading por bug de cooldown

---

## 🐛 Bugs Técnicos Encontrados

### **Bug #1: Cooldown Reset en ReplayEngine**
**Ubicación**: [replay_engine.py:483-484](replay_testing/core/replay_engine.py#L483-L484)

```python
# BUG CRÍTICO - Resetea cooldowns entre eventos
self.locked_symbols = {}
self.cooldown_symbols = {}
```

**Impacto**:
1. Worker entra en QCLS a las 10:00, sale con TP a las 10:05 (cooldown 5min)
2. ReplayEngine termina evento QCLS y **borra el cooldown**
3. Cuando vuelve a QCLS, no hay cooldown → entra de nuevo
4. Se repite 10 veces en el mismo día

### **Bug #2: Filtro de Confianza Mínima No Aplicado**
**Ubicación**: [volume_absorption_worker_logic.py:269-278](strategies/workers/volume_absorption_worker_logic.py#L269-L278)

Se agregó filtro de 50% mínimo pero los resultados del regression test muestran que no se aplicó correctamente.

---

## 💡 Lecciones Aprendidas

### **1. Timeframe Importa**
- 1min bars son **demasiado ruidosos** para smallcaps
- Considerar **5min o 15min** para reducir ruido
- Filtrar falsos breakouts y mejorar R:R

### **2. Stops para Smallcaps**
- 5% TP / 2% SL es **scalping**, no swing
- Para smallcaps volátiles: **10-15% TP / 3-4% SL**
- Permite que los ganadores corran, evita whipsaw

### **3. Volume Absorption ≠ Smallcaps**
- Estrategia diseñada para **largecaps institucionales**
- Smallcaps tienen comportamiento **retail-driven**
- No hay "absorción institucional" en penny stocks

### **4. Regression Testing Funcionó**
- **NO fallamos** con replay/regression
- Los tests **revelaron problemas reales**
- Esto es exactamente lo que deben hacer

---

## ✅ Cambios Aplicados

1. **Desactivado en config.ini**
   ```ini
   [VOLUME_ABSORPTION_WORKER]
   enabled = false
   ```

2. **Agregado filtro de confianza mínima (50%)**
   - Líneas 269-278 en `volume_absorption_worker_logic.py`
   - Rechaza setups con <50% pattern completion

3. **Documentación de problemas**
   - Este archivo documenta razones para desactivación
   - Facilita futura revisión o eliminación

---

## 🎯 Recomendaciones Futuras

### **Opción 1: Rediseño Completo**
Si se quiere mantener este worker:
1. Cambiar a **5min o 15min timeframe**
2. Ajustar stops: **10% TP / 3% SL**
3. **Arreglar bug de cooldown** en ReplayEngine
4. Testear con 10-15 fechas antes de activar
5. Considerar solo **largecaps** (>$10, >1M volume)

### **Opción 2: Fusionar con Daily Plays**
- Daily Plays tiene mejor rendimiento
- Absorber lógica útil (VWAP, volumen)
- Eliminar duplicación de código

### **Opción 3: Eliminar Completamente**
- Si no se usa en 30 días, eliminar
- Reducir complejidad del sistema
- Enfocarse en workers que funcionan

---

## 📝 Referencias

- **Regression Test**: [test_volume_absorption_regression.py](replay_testing/test_volume_absorption_regression.py)
- **Worker Logic**: [volume_absorption_worker_logic.py](strategies/workers/volume_absorption_worker_logic.py)
- **Config**: [config.ini:1771-1848](config.ini#L1771-L1848)
- **Bug Cooldown**: [replay_engine.py:483-484](replay_testing/core/replay_engine.py#L483-L484)

---

**Conclusión**: El worker `volume_absorption` no es adecuado para el perfil de trading actual (smallcaps, alta volatilidad, baja temporalidad). Requiere rediseño completo o eliminación.
