#!/bin/bash

# Script para sincronizar trades de SQLite a PostgreSQL
# Este script inserta todos los trade_ids de SQLite en trade_metadata de PostgreSQL

USER_ID="7ab22590-ebff-4cc0-b2c3-43170dda53d2"
SQLITE_DB="trading_data.db"
PG_DB="carlos"

echo "🚀 Iniciando sincronización de trades..."
echo "📊 Obteniendo trade_ids de SQLite..."

# Get all closed trade_ids from SQLite
trade_ids=$(sqlite3 $SQLITE_DB "SELECT trade_id FROM trades WHERE status='CLOSED' ORDER BY entry_time DESC")

# Count total trades
total=$(echo "$trade_ids" | wc -l | tr -d ' ')
echo "📊 Total trades cerrados: $total"

# Create SQL insert statements
synced=0
skipped=0

echo "💾 Insertando en PostgreSQL..."

for trade_id in $trade_ids; do
    # Insert into PostgreSQL (ignore if already exists)
    result=$(psql -d $PG_DB -t -c "
        INSERT INTO trade_metadata (trade_id, user_id, is_public, notes, tags)
        VALUES ('$trade_id', '$USER_ID', false, NULL, ARRAY[]::TEXT[])
        ON CONFLICT (trade_id) DO NOTHING
        RETURNING id;
    " 2>&1)

    if [[ $result == *"INSERT"* ]] || [[ $result =~ [0-9]+ ]]; then
        ((synced++))
        if [ $((synced % 50)) -eq 0 ]; then
            echo "   ✅ Sincronizados: $synced/$total"
        fi
    else
        ((skipped++))
    fi
done

echo ""
echo "✅ Sincronización completada!"
echo "   Total: $total"
echo "   Sincronizados: $synced"
echo "   Omitidos (ya existían): $skipped"

# Verify
final_count=$(psql -d $PG_DB -t -c "SELECT COUNT(*) FROM trade_metadata WHERE user_id='$USER_ID'" | tr -d ' ')
echo ""
echo "📊 Verificación final: $final_count registros en trade_metadata"
