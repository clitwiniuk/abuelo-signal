#!/bin/bash
# Script para programar la descarga EOD de OHLC usando crontab
# Ejecuta download_eod_ohlc.py automáticamente a las 22:00 hora española

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo "📅 Configurando descarga automática EOD de OHLC"
echo "================================================"
echo ""
echo "⏰ Programación: 22:00 hora española (diario)"
echo "📂 Proyecto: $PROJECT_ROOT"
echo ""

# Crear el cron job
CRON_JOB="0 22 * * * cd $PROJECT_ROOT && /usr/bin/python3 scripts/maintenance/download_eod_ohlc.py >> logs/ohlc_downloader.log 2>&1"

# Verificar si ya existe el cron job
if crontab -l 2>/dev/null | grep -q "download_eod_ohlc.py"; then
    echo "⚠️  El cron job ya existe:"
    crontab -l | grep "download_eod_ohlc.py"
    echo ""
    read -p "¿Deseas reemplazarlo? (s/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        echo "❌ Cancelado"
        exit 1
    fi
    # Eliminar cron job existente
    crontab -l | grep -v "download_eod_ohlc.py" | crontab -
fi

# Agregar nuevo cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job agregado correctamente"
echo ""
echo "📋 Cron jobs actuales:"
crontab -l | grep "download_eod_ohlc.py"
echo ""
echo "💡 Para ver todos los cron jobs: crontab -l"
echo "💡 Para editar manualmente: crontab -e"
echo "💡 Para eliminar: crontab -l | grep -v 'download_eod_ohlc.py' | crontab -"
echo ""
echo "✅ Configuración completada"
