#!/bin/bash
# Script para automatizar el testeo de la API de trading
export PYTHONPATH="$(pwd)"
echo "[test_api.sh] PYTHONPATH=$PYTHONPATH"

# Usar broker dummy para tests de API
export USE_DUMMY_BROKER=true
# Lanzar backend en background y guardar PID
python algoplatform/main.py > backend.log 2>&1 &
BACKEND_PID=$!
echo "[test_api.sh] Backend lanzado con PID $BACKEND_PID (logs en backend.log)"

# Esperar a que el backend esté listo
sleep 5

# Ejecutar los tests de API
PYTHONPATH=. pytest -v algoplatform/tests/test_api_worker.py
TEST_RESULT=$?

# Matar el backend al terminar los tests
kill $BACKEND_PID

# Mostrar resultado
echo "[test_api.sh] Tests finalizados. Código de salida: $TEST_RESULT"
exit $TEST_RESULT
