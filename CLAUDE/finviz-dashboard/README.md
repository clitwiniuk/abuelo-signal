# Finviz Dashboard — macOS App

Dashboard de escritorio para macOS que captura automáticamente datos de Finviz
(Top Gainers, New High, Unusual Volume) cada 15 minutos en horario de mercado.

## Arquitectura

```
Electron (ventana macOS)
    └── React UI (dashboard con tablas en vivo)
            └── API HTTP local :5050
                    └── Python (FastAPI + finvizfinance + SQLite)
```

---

## Requisitos previos

- **Node.js** >= 18  →  https://nodejs.org
- **Python** >= 3.10  →  https://python.org
- **Xcode Command Line Tools**  →  `xcode-select --install`

---

## Instalación

### 1. Dependencias Python

```bash
pip3 install finvizfinance fastapi uvicorn pytz pandas
```

### 2. Dependencias Node

```bash
cd finviz-dashboard
npm install
```

---

## Desarrollo (modo live)

Abre **dos terminales**:

**Terminal 1 — Backend Python:**
```bash
cd finviz-dashboard/python
python3 server.py
```

**Terminal 2 — App Electron + React:**
```bash
cd finviz-dashboard
npm run electron-dev
```

---

## Compilar app .app para macOS

```bash
npm run dist
```

Genera `dist/Finviz Dashboard.dmg`. Arrástralo a `/Applications`.

> ⚠️ Al distribuir la app, asegúrate de que Python3 y las librerías
> estén instaladas en el sistema destino, o considera empaquetar
> un intérprete Python con PyInstaller (ver sección avanzada abajo).

---

## Uso de la app

| Botón | Acción |
|---|---|
| **START SCHEDULER** | Inicia capturas automáticas cada 15 min |
| **STOP SCHEDULER** | Para el scheduler |
| **MANUAL SNAPSHOT** | Captura inmediata (útil para probar) |

- Los datos se guardan en `python/finviz_snapshots.db` (SQLite)
- El log de actividad muestra el estado en tiempo real
- El badge **MARKET OPEN/CLOSED** indica si el mercado está activo

---

## Consultar datos históricos

```python
import sqlite3, pandas as pd

conn = sqlite3.connect("python/finviz_snapshots.db")

# Ver todos los snapshots de Top Gainers
df = pd.read_sql("SELECT * FROM snapshots WHERE category='top_gainers'", conn)
print(df)

# Ver timestamps disponibles
ts = pd.read_sql("SELECT DISTINCT timestamp FROM snapshots ORDER BY timestamp DESC", conn)
print(ts)
```

También puedes usar **DB Browser for SQLite** (app gratuita) para explorar los datos visualmente.

---

## Estructura del proyecto

```
finviz-dashboard/
├── electron/
│   ├── main.js          # Proceso principal Electron
│   └── preload.js       # Puente seguro renderer ↔ main
├── python/
│   └── server.py        # API FastAPI + scraping + SQLite
├── src/
│   ├── App.js           # Dashboard React
│   ├── App.css          # Estilos terminal finance
│   ├── index.js
│   └── index.css
├── public/
│   └── index.html
├── package.json
└── README.md
```

---

## Avanzado: empaquetar Python con la app

Si quieres distribuir la app sin depender de Python instalado:

```bash
pip3 install pyinstaller
cd python
pyinstaller --onefile server.py
```

Luego en `electron/main.js` apunta a `dist/server` en vez de `server.py`.
