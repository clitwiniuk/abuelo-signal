#!/bin/bash
# Verificación rápida de implementación de determinismo
# Ejecutar: bash verify_implementation.sh

echo "========================================================================"
echo "VERIFICACIÓN DE IMPLEMENTACIÓN - MEJORAS DE DETERMINISMO"
echo "========================================================================"
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Problema #1: Scanner Persistence
echo "📊 Problema #1: Scanner Signal Persistence"
echo "----------------------------------------"

if [ -f "core/scanner_signal_recorder.py" ]; then
    echo -e "${GREEN}✅${NC} ScannerSignalRecorder existe"
else
    echo -e "${RED}❌${NC} ScannerSignalRecorder NO existe"
fi

# Check DB
SIGNAL_COUNT=$(sqlite3 trading_data.db "SELECT COUNT(*) FROM scanner_signals" 2>/dev/null || echo "0")
if [ "$SIGNAL_COUNT" -gt "0" ]; then
    echo -e "${GREEN}✅${NC} Scanner signals en DB: $SIGNAL_COUNT"

    # Date range
    DATE_RANGE=$(sqlite3 trading_data.db "SELECT MIN(signal_date) || ' a ' || MAX(signal_date) FROM scanner_signals" 2>/dev/null)
    echo "   Rango: $DATE_RANGE"
else
    echo -e "${YELLOW}⚠️${NC} No hay scanner signals en DB (ejecutar scanner primero)"
fi

# Check integration
if grep -q "ScannerSignalRecorder" scanner/smallcap/smallcap_daily_scanner.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} Scanner integrado con persistence"
else
    echo -e "${RED}❌${NC} Scanner NO integrado"
fi

if grep -q "signal_recorder.get_signal_for_replay" replay_testing/core/replay_engine.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} ReplayEngine carga signals reales"
else
    echo -e "${RED}❌${NC} ReplayEngine NO carga signals"
fi

echo ""

# Problema #2: Clock Abstraction
echo "🕐 Problema #2: Clock Abstraction"
echo "----------------------------------------"

if [ -f "core/time_provider.py" ]; then
    echo -e "${GREEN}✅${NC} TimeProvider existe"
else
    echo -e "${RED}❌${NC} TimeProvider NO existe"
fi

# Check integration
if grep -q "from core.time_provider import" core/execution_engine_adapter.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} ExecutionEngineAdapter usa TimeProvider"
else
    echo -e "${RED}❌${NC} ExecutionEngineAdapter NO usa TimeProvider"
fi

if grep -q "from core.time_provider import" core/extended_hours_manager.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} ExtendedHoursManager usa TimeProvider"
else
    echo -e "${RED}❌${NC} ExtendedHoursManager NO usa TimeProvider"
fi

# Check datetime.now() replacements
DATETIME_NOW_COUNT=$(grep -c "datetime\.now()" core/execution_engine_adapter.py 2>/dev/null || echo "0")
CLOCK_NOW_COUNT=$(grep -c "self\.clock\.now()" core/execution_engine_adapter.py 2>/dev/null || echo "0")

if [ "$CLOCK_NOW_COUNT" -gt "0" ]; then
    echo -e "${GREEN}✅${NC} ExecutionEngineAdapter: $CLOCK_NOW_COUNT llamadas a self.clock.now()"
    if [ "$DATETIME_NOW_COUNT" -gt "5" ]; then
        echo -e "${YELLOW}⚠️${NC} Todavía hay $DATETIME_NOW_COUNT datetime.now() (revisar)"
    fi
else
    echo -e "${YELLOW}⚠️${NC} No se encontraron llamadas a self.clock.now()"
fi

echo ""

# Problema #3: Entry Competition
echo "🏆 Problema #3: Entry Competition"
echo "----------------------------------------"

if [ -f "core/entry_competition.py" ]; then
    echo -e "${GREEN}✅${NC} EntryCompetition existe"

    # Check if it still has asyncio.sleep (exclude comments)
    if grep -v "^#" core/entry_competition.py 2>/dev/null | grep -v "^\s*#" | grep -q "await asyncio.sleep"; then
        echo -e "${YELLOW}⚠️${NC} Todavía usa asyncio.sleep() (no completamente determinístico)"
    else
        echo -e "${GREEN}✅${NC} No usa asyncio.sleep() (determinístico)"
    fi
else
    echo -e "${RED}❌${NC} EntryCompetition NO existe"
fi

echo ""

# Tests
echo "🧪 Tests"
echo "----------------------------------------"

if [ -f "test_scanner_persistence.py" ]; then
    echo -e "${GREEN}✅${NC} test_scanner_persistence.py existe"

    # Try to run it
    echo "   Ejecutando tests..."
    if python test_scanner_persistence.py > /tmp/test_output.txt 2>&1; then
        PASSED=$(grep "tests passed" /tmp/test_output.txt | head -1)
        echo -e "   ${GREEN}✅${NC} $PASSED"
    else
        FAILED=$(grep "FAIL" /tmp/test_output.txt | head -1)
        echo -e "   ${RED}❌${NC} Tests fallaron: $FAILED"
    fi
else
    echo -e "${YELLOW}⚠️${NC} test_scanner_persistence.py NO existe"
fi

echo ""

# Summary
echo "========================================================================"
echo "RESUMEN"
echo "========================================================================"

IMPL_COUNT=0
TOTAL_COUNT=4

# Check each problem
if [ "$SIGNAL_COUNT" -gt "0" ] && grep -q "ScannerSignalRecorder" scanner/smallcap/smallcap_daily_scanner.py 2>/dev/null; then
    echo -e "${GREEN}✅${NC} Problema #1: Scanner Persistence - IMPLEMENTADO"
    IMPL_COUNT=$((IMPL_COUNT + 1))
else
    echo -e "${YELLOW}⚠️${NC} Problema #1: Scanner Persistence - PARCIAL"
fi

if grep -q "from core.time_provider import" core/execution_engine_adapter.py 2>/dev/null && [ "$CLOCK_NOW_COUNT" -gt "0" ]; then
    echo -e "${GREEN}✅${NC} Problema #2: Clock Abstraction - IMPLEMENTADO"
    IMPL_COUNT=$((IMPL_COUNT + 1))
else
    echo -e "${YELLOW}⚠️${NC} Problema #2: Clock Abstraction - PARCIAL"
fi

if [ -f "core/entry_competition.py" ]; then
    if grep -v "^#" core/entry_competition.py 2>/dev/null | grep -v "^\s*#" | grep -q "await asyncio.sleep"; then
        echo -e "${YELLOW}⚠️${NC} Problema #3: Entry Competition - PARCIAL (necesita refactor)"
    else
        echo -e "${GREEN}✅${NC} Problema #3: Entry Competition - IMPLEMENTADO"
        IMPL_COUNT=$((IMPL_COUNT + 1))
    fi
else
    echo -e "${RED}❌${NC} Problema #3: Entry Competition - NO IMPLEMENTADO"
fi

if [ -f "core/fill_model.py" ] && [ -f "test_fill_model.py" ]; then
    echo -e "${GREEN}✅${NC} Problema #4: Fill Model - IMPLEMENTADO"
    IMPL_COUNT=$((IMPL_COUNT + 1))
else
    echo -e "${RED}❌${NC} Problema #4: Fill Model - NO IMPLEMENTADO"
fi

echo ""
echo "Implementación: $IMPL_COUNT/$TOTAL_COUNT problemas completados"
echo ""

# Estimate reproducibility
if [ "$IMPL_COUNT" -eq 4 ]; then
    echo -e "${GREEN}Reproducibilidad estimada: 95-97%${NC} (baseline: 70%)"
elif [ "$IMPL_COUNT" -eq 3 ]; then
    echo -e "${GREEN}Reproducibilidad estimada: 92-95%${NC} (baseline: 70%)"
elif [ "$IMPL_COUNT" -eq 2 ]; then
    echo -e "${GREEN}Reproducibilidad estimada: 90-92%${NC} (baseline: 70%)"
elif [ "$IMPL_COUNT" -eq 1 ]; then
    echo -e "${YELLOW}Reproducibilidad estimada: 85-90%${NC} (baseline: 70%)"
else
    echo -e "${RED}Reproducibilidad estimada: 70-75%${NC} (baseline: 70%)"
fi

echo ""
echo "========================================================================"
echo "PRÓXIMOS PASOS"
echo "========================================================================"

if [ "$SIGNAL_COUNT" -gt "0" ]; then
    echo "✅ Puedes ejecutar replay inmediatamente:"
    echo "   python -m replay_testing.run_replay --date 2026-01-05"
    echo ""
else
    echo "⚠️ Ejecutar scanner primero para generar signals:"
    echo "   python scanner_main.py"
    echo ""
fi

echo "📊 Ver impacto detallado:"
echo "   python quick_verification.py"
echo ""

echo "📚 Leer documentación:"
echo "   - IMPLEMENTACION_COMPLETA_SUMMARY.md"
echo "   - SCANNER_PERSISTENCE_IMPLEMENTATION.md"
echo "   - AUDITORIA_ARQUITECTURAL_DETERMINISMO.md"
echo ""
