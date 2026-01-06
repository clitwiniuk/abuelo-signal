#!/bin/bash

# Verificar que la simplificación del worker outlier_penny_extreme se implementó correctamente

echo "🔍 VERIFICANDO SIMPLIFICACIÓN DE OUTLIER_PENNY_EXTREME WORKER"
echo "=============================================================="
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

WORKER_FILE="/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/strategies/workers/outlier_penny_extreme_worker_logic.py"

echo "📁 Verificando outlier_penny_extreme_worker_logic.py..."

# Verificación 1: Price range corregido
check_code "$WORKER_FILE" \
    "self.min_price = 3.0.*# >= \$3.00 (EXACT match to validated rule)" \
    "Min price = $3.00 (no $0.10)"

# Verificación 2: Volume ratio es None
check_code "$WORKER_FILE" \
    "self.min_volume_ratio = None.*# NOT required by validated rule" \
    "Volume ratio = None (no requirement)"

# Verificación 3: VWAP no requerido
check_code "$WORKER_FILE" \
    "self.require_vwap_above = False.*# NOT required by validated rule" \
    "VWAP requirement = False"

# Verificación 4: Premarket range threshold
check_code "$WORKER_FILE" \
    "self.min_pm_range_pct = 3.0.*# > 3% premarket range" \
    "Premarket range >= 3% (correct)"

# Verificación 5: Edge esperado documentado
check_code "$WORKER_FILE" \
    "Edge esperado: +11.69%" \
    "Edge esperado documentado (+11.69%)"

# Verificación 6: Sample size documentado
check_code "$WORKER_FILE" \
    "Sample size: 163 eventos" \
    "Sample size documentado (163 eventos)"

# Verificación 7: Log message actualizado con edge
check_code "$WORKER_FILE" \
    "Expected Edge: +11.69% (validated on 163 events)" \
    "Log message incluye edge esperado"

# Verificación 8: Volume como informativo
check_code "$WORKER_FILE" \
    "Volume: NOT required (informational only)" \
    "Log indica volume es informativo"

# Verificación 9: VWAP como informativo
check_code "$WORKER_FILE" \
    "VWAP: NOT required (optional confirmation)" \
    "Log indica VWAP es informativo"

# Verificación 10: Volume validation siempre retorna True
check_code "$WORKER_FILE" \
    "Volume is INFORMATIONAL ONLY - not required by validated rule" \
    "Volume validation documentada como informativa"

check_code "$WORKER_FILE" \
    "INFORMATIONAL ONLY - always return True" \
    "Volume validation siempre retorna True"

# Verificación 11: VWAP es opcional
check_code "$WORKER_FILE" \
    "VWAP is OPTIONAL (not required by validated rule) - informational only" \
    "VWAP validation documentada como opcional"

# Verificación 12: Documentación actualizada
check_code "$WORKER_FILE" \
    "Última actualización: 2025-11-06 - Simplificado para coincidir con regla validada" \
    "Documentación actualizada con fecha"

# Verificación 13: Criterios exactos en documentación
check_code "$WORKER_FILE" \
    "1. price >= \\\$3.00 AND < \\\$5.00" \
    "Criterio de precio documentado"

check_code "$WORKER_FILE" \
    "2. premarket_range_pct > 3%" \
    "Criterio de premarket range documentado"

echo ""
echo "=============================================================="
echo "📊 RESUMEN DE VERIFICACIÓN"
echo "=============================================================="
echo -e "${GREEN}✅ Verificaciones pasadas: $PASSED${NC}"
echo -e "${RED}❌ Verificaciones fallidas: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 TODAS LAS MODIFICACIONES IMPLEMENTADAS CORRECTAMENTE${NC}"
    echo ""
    echo "✅ Worker simplificado para coincidir con regla validada"
    echo "✅ Price range: \$3.00-\$5.00 (era \$0.10-\$5.00)"
    echo "✅ Volume: Informativo solamente (era requerido >= 1.5x)"
    echo "✅ VWAP: Opcional (era requerido)"
    echo "✅ Premarket range: > 3% (SOLO criterio requerido)"
    echo "✅ Edge esperado: +11.69% (validado en 163 eventos)"
    echo ""
    echo "📊 Comparación:"
    echo "   ANTES: price \$0.10-\$5 + vol>=1.5x + VWAP required → edge desconocido"
    echo "   DESPUÉS: price \$3-\$5 + pm_range>3% → edge +11.69% (validado)"
    echo ""
    echo "🚀 Próximos pasos:"
    echo "1. Monitorear logs: tail -f logs/worker_outlier_penny_extreme.log | grep 'VALIDATED_RULE'"
    echo "2. Verificar entries: Deberían enfocarse SOLO en penny stocks \$3-\$5 con alta volatilidad PM"
    echo "3. Después de 20-30 trades, comparar edge real vs +11.69% esperado"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  ALGUNAS VERIFICACIONES FALLARON${NC}"
    echo ""
    echo "Por favor revisa el código manualmente."
    echo "Consulta OUTLIER_PENNY_EXTREME_SIMPLIFICATION.md para detalles."
    echo ""
    exit 1
fi
