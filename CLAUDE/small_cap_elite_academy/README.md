# 📈 Small Cap Elite Academy

Plataforma de entrenamiento gamificado para traders de small caps. Desarrolla tus habilidades desde nivel principiante hasta trader élite con un sistema de progresión estructurado.

## 🎯 Características Principales

### Sistema de Niveles (5 Niveles)
- **Nivel 1 - CADETE**: $25,000 capital virtual, horario limitado, máximo 3 trades/día
- **Nivel 2 - ANALISTA TÉCNICO**: $50,000 capital, acceso extendido
- **Nivel 3 - ESTRATEGA CUANTITATIVO**: $100,000 capital, backtesting manual
- **Nivel 4 - PSYCHOLOGY MASTER**: $250,000 capital, focus en control emocional
- **Nivel 5 - ELITE TRADER**: $1,000,000 capital, prop firm challenges simulados

### Setups Profesionales
1. **Morning Panic Dip** (Kyle Williams) - Caídas matutinas con rebote
2. **VWAP Bounce** (Alex Temiz) - Rebotes en línea VWAP
3. **First Red Day** (Short Selling) - Primer día rojo después de racha alcista
4. **Opening Range Breakout** (Lance Breitstein) - Breakout de rango de apertura

### Módulos Funcionales
- 📊 **Simulador de Mercado**: Datos reales de Yahoo Finance con slippage realista
- 📈 **Tracking Estadístico**: Win rate, Profit Factor, Expected Value, R-Multiple
- 📓 **Daily Report Card**: Journal psicológico obligatorio pre-trading
- 🏆 **Sistema XP y Logros**: Gamificación con badges desbloqueables
- 📚 **Modos de Entrenamiento**: Pattern Recognition, Replay Histórico, Drills
- ⭐ **Watchlist y Scanner**: Monitoreo de small caps en tiempo real

## 🚀 Instalación

### Requisitos
- Python 3.8+
- pip

### Pasos

1. Clonar o descargar el proyecto:
```bash
cd small_cap_elite_academy
```

2. Crear entorno virtual (recomendado):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate      # Windows
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Inicializar la base de datos:
```bash
python -c "from database.db_manager import init_database; init_database()"
```

5. Ejecutar la aplicación:
```bash
streamlit run app.py
```

La aplicación estará disponible en `http://localhost:8501`

## 📁 Estructura del Proyecto

```
small_cap_elite_academy/
├── app.py                    # Aplicación principal Streamlit
├── requirements.txt          # Dependencias
├── README.md                 # Documentación
├── database/
│   ├── __init__.py
│   └── db_manager.py         # Gestión de base de datos SQLite
├── utils/
│   ├── __init__.py
│   ├── market_data.py        # Datos de mercado (Yahoo Finance)
│   ├── calculations.py       # Cálculos de trading
│   └── achievements.py       # Sistema de logros
├── pages/
│   ├── __init__.py
│   ├── trading.py            # Página de trading
│   ├── daily_report.py       # Daily Report Card
│   ├── estadisticas.py       # Dashboard estadístico
│   ├── setups.py             # Biblioteca de setups
│   ├── logros.py             # Página de logros
│   ├── entrenamiento.py      # Modos de entrenamiento
│   └── watchlist.py          # Watchlist personal
└── data/                     # Datos locales (si aplica)
```

## 🎮 Uso

### Primeros Pasos
1. Registra una nueva cuenta o inicia sesión
2. Completa tu **Daily Report Card** (obligatorio antes de operar)
3. Explora la biblioteca de setups
4. Agrega stocks a tu watchlist
5. Empieza a operar en el simulador

### Sistema de XP
Gana XP por:
- ✅ Completar Daily Report: +15 XP
- ✅ Trade según plan: +10 XP
- ✅ Trade ganador: +5 XP bonus
- ✅ Trade con R:R > 1:3: +10 XP bonus
- ✅ Semana sin violar reglas: +50 XP
- ✅ Dominar un setup: +100 XP

### Protección del Trader
- Bloqueo automático si pierdes >5% del capital en un día
- Límite de trades según nivel
- Validación obligatoria de setup antes de entrar
- Slippage realista en small caps

## 📊 Métricas Trackeadas

### Métricas Principales
- **Win Rate**: Porcentaje de trades ganadores
- **Profit Factor**: Gross Profit / Gross Loss
- **Expected Value**: (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
- **R-Multiple**: Ganancia en términos de riesgo inicial
- **Max Drawdown**: Máximo retroceso del equity curve

### Métricas por Setup
- Win rate individual por setup
- P&L total y promedio por setup
- Dominio del setup (20+ trades, 60%+ WR)

## 🏆 Logros Disponibles

| Logro | Descripción | Dificultad |
|-------|-------------|------------|
| 🥉 First Blood | Primer trade ejecutado | Fácil |
| 👑 Consistency King | 10 trades siguiendo plan | Media |
| 📊 VWAP Master | 20 trades ganadores VWAP | Media |
| 🌅 Morning Panic Pro | 20 trades ganadores Panic | Media |
| 🛡️ Risk Manager | 30 días sin violar riesgo | Difícil |
| 🎓 Setup Collector | Dominar los 4 setups | Difícil |
| 💰 Profit Factor Pro | PF > 1.5 con 30+ trades | Difícil |
| 🏆 Elite Status | Alcanzar Nivel 5 | Muy Difícil |

## 🎨 Paleta de Colores

- **Fondo**: #0A0A0A (Negro trading)
- **Velas Alcistas**: #00C805 (Verde)
- **Velas Bajistas**: #FF5000 (Rojo)
- **Acentos**: #00D4FF (Cyan), #FFD700 (Dorado)
- **Niveles**: Bronce → Plata → Oro → Platino → Diamante

## ⚙️ Configuración

### Variables de Entorno (opcional)
```bash
export DB_PATH="/ruta/a/tu/base/de/datos"
export DEFAULT_SLIPPAGE=0.002
export COMMISSION_PER_SHARE=0.005
```

### Personalización
Edita `utils/calculations.py` para ajustar:
- Slippage por defecto
- Comisiones
- Límites de riesgo
- Fórmulas de cálculo

## 🔒 Seguridad

- Contraseñas hasheadas con SHA-256
- Validación de entradas de usuario
- Protección contra overtrading
- Límites de riesgo configurables

## 🚧 Roadmap

### Fase 1 (Actual)
- ✅ Sistema de niveles y XP
- ✅ Simulador de trading básico
- ✅ Tracking estadístico
- ✅ Daily Report Card
- ✅ Sistema de logros

### Fase 2 (Próxima)
- 🔄 Paper Trading con datos reales (Alpaca API)
- 🔄 AI Coach (análisis de trades con GPT)
- 🔄 Comunidad y leaderboards
- 🔄 Retos semanales
- 🔄 Exportación de reportes PDF

### Fase 3 (Futuro)
- 📋 WebSocket para datos en tiempo real
- 📋 App móvil
- 📋 Integración con brokers reales
- 📋 Mentoría virtual avanzada

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el repositorio
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de código abierto bajo licencia MIT.

## 🙏 Agradecimientos

Inspirado por los métodos de traders profesionales:
- **Steven Dux** - Estadísticas y tracking riguroso
- **Kyle Williams** - Morning Panic Dip
- **Alex Temiz** - VWAP Bounce
- **Lance Breitstein** - Opening Range Breakout

## 📧 Contacto

Para preguntas o sugerencias, abre un issue en el repositorio.

---

**Disclaimer**: Esta plataforma es para fines educativos. El trading involucra riesgo significativo de pérdida. Practica con capital virtual antes de operar con dinero real.