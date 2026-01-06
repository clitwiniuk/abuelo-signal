# Reorganización de Directorios - Backtesting

Fecha: 2025-12-17

## 🎯 Objetivo

Organizar los sistemas de backtesting en el directorio, separando:
- Sistema científico nuevo (activo)
- Sistemas antiguos (legacy)
- Logs y archivos temporales (archive)

## 📁 Estructura Resultante

```
trading_system_v3/
├── scientific_backtest/              ← NUEVO: Sistema científico activo
│   ├── README.md
│   ├── backtest_worker_scientific.py
│   ├── backtest_all_workers.py
│   └── validate_replay_fidelity.py
│
├── replay_testing/                   ← YA EXISTÍA: Sistema de replay activo
│   └── [sin cambios]
│
├── legacy/
│   ├── old_backtesting_system/      ← MOVIDO: Sistema antiguo
│   │   └── backtesting_system/
│   │       ├── menu_principal.py
│   │       ├── core/
│   │       ├── strategies/
│   │       └── [otros archivos]
│   │
│   ├── old_backtesting_engine/      ← MOVIDO: Motor antiguo
│   │   └── backtesting_engine/
│   │       ├── data_feed/
│   │       ├── strategy/
│   │       └── tests/
│   │
│   ├── old_backtesting/             ← YA EXISTÍA
│   └── backtesting_backtrader/      ← YA EXISTÍA
│
└── logs/
    └── archive/                      ← MOVIDO: Logs antiguos de replay
        ├── replay.log
        ├── replay_artv.log
        ├── replay_debug.log
        ├── replay_debug_2.log
        ├── replay_debug_3.log
        └── replay_market_data.db
```

## 📦 Archivos Movidos

### 1. Creado: `scientific_backtest/`
Nuevo directorio para el sistema científico de backtesting.

**Archivos movidos desde raíz:**
- `backtest_worker_scientific.py` → `scientific_backtest/backtest_worker_scientific.py`
- `backtest_all_workers.py` → `scientific_backtest/backtest_all_workers.py`
- `validate_replay_fidelity.py` → `scientific_backtest/validate_replay_fidelity.py`

**Archivo creado:**
- `README.md` - Documentación del sistema científico

### 2. Movido a Legacy: `backtesting_system/`
Sistema antiguo ya no utilizado activamente.

**Desde:** `backtesting_system/`
**Hacia:** `legacy/old_backtesting_system/backtesting_system/`

**Nota:** Solo `menu_principal.py` tenía referencia a este sistema, ya actualizado.

### 3. Movido a Legacy: `backtesting_engine/`
Motor de backtesting antiguo, no utilizado.

**Desde:** `backtesting_engine/`
**Hacia:** `legacy/old_backtesting_engine/backtesting_engine/`

### 4. Archivado: Logs de Replay Antiguos
Logs generados durante desarrollo del sistema de replay.

**Archivos movidos a `logs/archive/`:**
- `replay.log` (1.6 MB)
- `replay_artv.log` (578 KB)
- `replay_debug.log` (524 KB)
- `replay_debug_2.log` (70 KB)
- `replay_debug_3.log` (70 KB)
- `replay_market_data.db` (77 KB) - DB antiguo, no usado

## ✅ Verificación de Referencias

### Referencias Actualizadas
- `menu_principal.py`: Ya movido a legacy, sin necesidad de actualizar

### Referencias NO Afectadas
- `analysis_bridge.py`: No importa backtesting_system
- Sistema principal (`trader_main.py`): No afectado
- Dashboard: No afectado

## 🚀 Próximos Pasos

### Para Usar el Sistema Científico:
```bash
# Navegar al nuevo directorio
cd scientific_backtest/

# Validar fidelidad del replay (hacer MAÑANA cuando sistema no se toque)
python validate_replay_fidelity.py --worker vcp_smallcap --days 7

# Ejecutar backtest de todos los workers
python backtest_all_workers.py

# Ver resultados
open backtest_comparison.html
```

### Documentación Completa:
- Sistema científico: `scientific_backtest/README.md`
- Instrucciones de uso: `INSTRUCCIONES_BACKTEST.md`
- Plan de validación: `PLAN_VALIDACION_BACKTEST.md`

## 📝 Notas

1. **Sistema de Replay Activo**
   - `replay_testing/` se mantiene sin cambios
   - Es el sistema activo para replay de trades
   - No afectado por esta reorganización

2. **Sistemas Legacy**
   - Conservados en `legacy/` por si se necesitan en el futuro
   - No se eliminaron para mantener historial
   - Pueden eliminarse manualmente si se confirma que no se necesitan

3. **Logs Archivados**
   - Logs antiguos movidos a `logs/archive/`
   - Pueden eliminarse si se necesita espacio
   - No afectan funcionamiento del sistema

## 🔍 Cambios en Git

Esta reorganización afecta múltiples directorios. Para commitear:

```bash
# Ver cambios
git status

# Agregar reorganización
git add scientific_backtest/
git add legacy/old_backtesting_system/
git add legacy/old_backtesting_engine/
git add logs/archive/
git add REORGANIZACION_DIRECTORIOS.md

# Commit
git commit -m "chore: Reorganize backtest systems into scientific_backtest and legacy

- Create scientific_backtest/ for new scientific backtest system
- Move old backtesting_system to legacy/old_backtesting_system
- Move old backtesting_engine to legacy/old_backtesting_engine
- Archive old replay logs to logs/archive/
- Add comprehensive README for scientific_backtest system"
```

## ✨ Beneficios

1. **Claridad**: Sistema científico separado y documentado
2. **Organización**: Legacy systems en su propio directorio
3. **Limpieza**: Logs antiguos archivados
4. **Mantenibilidad**: Estructura clara para futuros desarrollos
5. **Documentación**: README completo para el sistema científico

---

**Reorganización completada:** 2025-12-17 22:46
**Sistema listo para usar mañana cuando se valide replay fidelity**
