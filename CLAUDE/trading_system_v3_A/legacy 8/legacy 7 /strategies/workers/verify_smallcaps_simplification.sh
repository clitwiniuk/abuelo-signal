#!/bin/bash

# Verificar que la simplificación del worker smallcaps_long se implementó correctamente

echo "🔍 VERIFICANDO SIMPLIFICACIÓN DE SMALLCAPS_LONG WORKER"
echo "======================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

check_code() {
    local file=$1
    local pattern=$2
    local description=$3

    if grep -q "$pattern" "$file"; then
        echo -e "${GREEN}✅ $description${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ $description${NC}"
        echo -e "${YELLOW}   Patrón no encontrado: $pattern${NC}"
        ((FAILED++))
    fi
}

WORKER_FILE="/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/strategies/workers/smallcaps_long_worker_logic.py"

echo "📁 Verificando smallcaps_long_worker_logic.py..."

# Verificación 1: Volume threshold corregido
check_code "$WORKER_FILE" \
    "self.min_volume_ratio = 2.0.*# Ratio mínimo de volumen (>2.0x EXACT match to validated rule)" \
    "Volume threshold = 2.0 (no 1.5)"

# Verificación 2: Nueva función _calculate_daily_return
check_code "$WORKER_FILE" \
    "def _calculate_daily_return(self, opportunity: Dict\[str, Any\]) -> float:" \
    "Función _calculate_daily_return() existe"

# Verificación 3: Cálculo correcto de daily_return (vs open)
check_code "$WORKER_FILE" \
    "open_price = bars\[0\].open" \
    "Usa day's open (no previous close)"

# Verificación 4: Daily return calculation
check_code "$WORKER_FILE" \
    "daily_return_pct = ((current_price - open_price) / open_price) \* 100" \
    "Cálculo correcto de daily_return"

# Verificación 5: Función simplificada
check_code "$WORKER_FILE" \
    "Detect bullish volume signal - EXACT match to validated rule" \
    "Función marcada como EXACT match"

# Verificación 6: Criterio 1 - Volume > 2.0
check_code "$WORKER_FILE" \
    "if volume_ratio <= 2.0:" \
    "Criterio volume_ratio > 2.0 (threshold correcto)"

# Verificación 7: Criterio 2 - Daily return > 0
check_code "$WORKER_FILE" \
    "if daily_return_pct <= 0:" \
    "Criterio daily_return_pct > 0"

# Verificación 8: Sin secondary signals
if grep -q "secondary_signals" "$WORKER_FILE"; then
    echo -e "${RED}❌ Secondary signals eliminados${NC}"
    echo -e "${YELLOW}   Aún contiene referencias a secondary_signals${NC}"
    ((FAILED++))
else
    echo -e "${GREEN}✅ Secondary signals eliminados${NC}"
    ((PASSED++))
fi

# Verificación 9: Sin fallback gap
if grep -q "elif gap_pct >= 0.3:.*# Fallback" "$WORKER_FILE"; then
    echo -e "${RED}❌ Fallback gap eliminado${NC}"
    echo -e "${YELLOW}   Aún contiene fallback con gap_pct${NC}"
    ((FAILED++))
else
    echo -e "${GREEN}✅ Fallback gap eliminado${NC}"
    ((PASSED++))
fi

# Verificación 10: Edge esperado documentado
check_code "$WORKER_FILE" \
    "Edge esperado: \+17.64%" \
    "Edge esperado documentado (+17.64%)"

# Verificación 11: Sample size documentado
check_code "$WORKER_FILE" \
    "Sample size: 163 eventos" \
    "Sample size documentado (163 eventos)"

# Verificación 12: Log message actualizado
check_code "$WORKER_FILE" \
    "Expected Edge: \+17.64% (validated on 163 events)" \
    "Log message incluye edge esperado"

# Verificación 13: Documentación actualizada
check_code "$WORKER_FILE" \
    "Última actualización: 2025-11-06 - Simplificado para coincidir con regla validada" \
    "Documentación actualizada con fecha"

echo ""
echo "======================================================"
echo "📊 RESUMEN DE VERIFICACIÓN"
echo "======================================================"
echo -e "${GREEN}✅ Verificaciones pasadas: $PASSED${NC}"
echo -e "${RED}❌ Verificaciones fallidas: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 TODAS LAS MODIFICACIONES IMPLEMENTADAS CORRECTAMENTE${NC}"
    echo ""
    echo "✅ Worker simplificado para coincidir con regla validada"
    echo "✅ Volume threshold: > 2.0 (era >= 1.5)"
    echo "✅ Daily return: vs day's open (era vs previous close)"
    echo "✅ Secondary signals eliminados"
    echo "✅ Fallbacks eliminados"
    echo "✅ Edge esperado: +17.64% (validado en 163 eventos)"
    echo ""
    echo "📊 Comparación:"
    echo "   ANTES: vol>=1.5x + múltiples criterios → edge ~10-12% (estimado)"
    echo "   DESPUÉS: vol>2.0x + daily_return>0 → edge +17.64% (validado)"
    echo ""
    echo "🚀 Próximos pasos:"
    echo "1. Monitorear logs: tail -f logs/worker_smallcaps_long.log | grep 'VALIDATED_RULE'"
    echo "2. Verificar entries: Deberían ser ~35% menos pero con mejor edge"
    echo "3. Después de 20-30 trades, comparar edge real vs +17.64% esperado"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  ALGUNAS VERIFICACIONES FALLARON${NC}"
    echo ""
    echo "Por favor revisa el código manualmente."
    echo "Consulta SMALLCAPS_LONG_SIMPLIFICATION.md para detalles."
    echo ""
    exit 1
fi
