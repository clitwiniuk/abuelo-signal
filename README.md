# Algoplatform - Guía de Ejecución y Uso

Este documento explica cómo ejecutar el backend (FastAPI) y la interfaz gráfica (Streamlit) de la plataforma, así como ejemplos de uso de la API REST.

---

## Ejecución recomendada

### 1. Ejecutar todo con el script `run_streamlit.sh`

Este script lanza **el backend (FastAPI)** y **la GUI (Streamlit)** en paralelo, asegurando que el `PYTHONPATH` sea correcto para los imports del proyecto.

```bash
cd algoplatform
./run_streamlit.sh
```
- El backend FastAPI se ejecuta en segundo plano (logs en `backend.log`).
- La GUI de Streamlit se lanza en primer plano.
- Al cerrar la GUI, el backend se detiene automáticamente.

### 2. Ejecución manual (solo backend)
Si solo quieres lanzar el backend para pruebas API o tests:

```bash
cd algoplatform
PYTHONPATH=. USE_DUMMY_BROKER=true python main.py
```
- El backend FastAPI estará disponible en http://localhost:8000
- El modo dummy permite pruebas sin broker real.

### 3. Ejecución manual (solo Streamlit GUI)

Asegúrate de que el backend ya está corriendo, luego:
```bash
cd algoplatform
streamlit run gui/app.py
```

---

## ¿Qué hace cada archivo?
- `main.py`: Lanza el backend FastAPI (importando todos los endpoints de `core/backend_api.py`).
- `run_streamlit.sh`: Lanza backend y GUI en paralelo y gestiona el ciclo de vida de ambos.
- `core/backend_api.py`: Define los endpoints de la API REST.
- `gui/app.py`: Interfaz gráfica de usuario (Streamlit).

---

## Ejemplo de uso de la API REST

### Lanzar un worker de trading
```bash
curl -X POST http://localhost:8000/api/worker/start \
  -H 'Content-Type: application/json' \
  -d '{"ticker": "AAPL", "config": {}, "strategy": "always_enter_strategy", "params": {}}'
```

### Ver estado de los workers
```bash
curl http://localhost:8000/api/worker/status
```

### Consultar posiciones abiertas
```bash
curl http://localhost:8000/api/position/AAPL
```

### Detener un worker
```bash
curl -X POST http://localhost:8000/api/worker/stop \
  -H 'Content-Type: application/json' \
  -d '{"ticker": "AAPL"}'
```

---

## Notas importantes
- **No modifiques `main.py` para lanzar el backend si usas `run_streamlit.sh`:** El script ya lo gestiona correctamente.
- El backend debe ser lanzado desde la raíz del proyecto o desde la carpeta `algoplatform` con el `PYTHONPATH` adecuado.
- Usa la variable de entorno `USE_DUMMY_BROKER=true` para pruebas y desarrollo sin broker real.

---

## Tests
Para ejecutar los tests automatizados:
```bash
USE_DUMMY_BROKER=true pytest -v algoplatform/tests/
```

---

## Contacto y soporte
Consulta el archivo `ARCHITECTURE.md` para entender la arquitectura y cómo contribuir.
