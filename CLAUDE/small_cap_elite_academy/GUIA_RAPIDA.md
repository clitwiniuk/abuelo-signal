# 🚀 Guía Rápida - Small Cap Elite Academy

## Instalación en 3 Pasos

### Paso 1: Instalar Dependencias
```bash
pip install -r requirements.txt
```

### Paso 2: Inicializar Base de Datos
```bash
python -c "from database.db_manager import init_database; init_database()"
```

### Paso 3: Iniciar Aplicación
```bash
streamlit run app.py
```

O usa los scripts incluidos:
- **Linux/Mac**: `./start.sh`
- **Windows**: `start.bat`

---

## 🎮 Primeros Pasos

### 1. Crear Cuenta
- Abre `http://localhost:8501`
- Haz clic en "Registrarse"
- Completa tus datos

### 2. Completa tu Daily Report Card
- Es **OBLIGATORIO** antes de operar
- Evalúa tu estado emocional
- Define tu plan para el día
- Gana +15 XP

### 3. Explora los Setups
- Ve a la pestaña "Setups"
- Lee sobre cada estrategia
- Identifica cuál resuena contigo

### 4. Crea tu Watchlist
- Agrega 3-5 small caps
- Asigna un setup a cada uno
- Monitorea antes del mercado

### 5. Empieza a Operar
- Ve a "Trading"
- Selecciona un setup
- Define entrada, stop y target
- Ejecuta con disciplina

---

## 📊 Sistema de Niveles

| Nivel | Nombre | Capital | Max Trades/Día | Riesgo Máx/Trade |
|-------|--------|---------|----------------|------------------|
| 1 | Cadete | $25,000 | 3 | $100 |
| 2 | Analista | $50,000 | 5 | $200 |
| 3 | Estratega | $100,000 | ∞ | $500 |
| 4 | Psychology Master | $250,000 | ∞ | $1,000 |
| 5 | Elite Trader | $1,000,000 | ∞ | $2,500 |

### Requisitos para Subir de Nivel
- **Nivel 2**: 500 XP + 60% WR + 20 trades
- **Nivel 3**: 1,500 XP + 3 setups dominados + PF > 1.2
- **Nivel 4**: 3,500 XP + EV positivo + Max DD < 10%
- **Nivel 5**: 7,000 XP + 30 días sin violar reglas

---

## 💎 Cómo Ganar XP

| Acción | XP | Bonus |
|--------|-----|-------|
| Daily Report | +15 | +50 por racha 7 días |
| Trade según plan | +10 | +5 si winner |
| Trade con R:R > 1:3 | +10 | - |
| Identificar setup | +5 | +15 ejecución perfecta |
| Semana sin violar reglas | +50 | +200 racha 4 semanas |
| Backtest 20 setups | +30 | +100 edge >60% |

---

## 🎯 Los 4 Setups

### 1. Morning Panic Dip (Kyle Williams)
**Cuándo**: Caída >20% en primeros 15 min  
**Entrada**: Break del high de vela de rechazo  
**Stop**: Bajo del día  
**Target**: 1:3 a 1:5 R:R

### 2. VWAP Bounce (Alex Temiz)
**Cuándo**: Precio toca VWAP y rebota  
**Entrada**: Break del high de confirmación  
**Stop**: Bajo de consolidación  
**Target**: 1:2 a 1:4 R:R

### 3. First Red Day (Short)
**Cuándo**: Después de 3+ días verdes  
**Entrada**: Break del low previo  
**Stop**: Alto del día anterior  
**Target**: 1:3 a 1:5 R:R  
⚠️ **Solo Nivel 3+**

### 4. Opening Range Breakout (Lance Breitstein)
**Cuándo**: Break de rango 5-30 min  
**Entrada**: Pullback al breakout  
**Stop**: Bajo del rango  
**Target**: 1:2 a 1:4 R:R

---

## 🛡️ Reglas de Protección

### Límites Automáticos
- ❌ Bloqueo si pierdes >5% en un día
- ❌ Máximo trades según nivel
- ❌ Slippage realista (0.2-1% en small caps)
- ❌ Comisiones: $0.005 por acción

### Checklist Pre-Trade
- [ ] ¿Tengo setup válido?
- [ ] ¿R:R mínimo 2:1?
- [ ] ¿Stop loss definido?
- [ ] ¿Riesgo dentro de límites?
- [ ] ¿Estoy siguiendo mi plan?

---

## 📈 Métricas Clave

### Win Rate Objetivo
- **Nivel 1-2**: 40-50%
- **Nivel 3-4**: 50-55%
- **Nivel 5**: 55%+

### Profit Factor Objetivo
- **Mínimo aceptable**: 1.2
- **Bueno**: 1.5+
- **Excelente**: 2.0+

### R-Multiple Objetivo
- **Mínimo**: 1.5R promedio
- **Bueno**: 2.0R promedio
- **Excelente**: 2.5R+ promedio

---

## 🔥 Modos de Entrenamiento

### Pattern Recognition
- Identifica setups en charts históricos
- 10-50 ejercicios por sesión
- +5 XP por respuesta correcta

### Replay Histórico
- Opera días históricos reales
- Incluye épocas volátiles (Ene 2021, Mar 2020)
- Velocidad ajustable (1x, 2x, 5x, 10x)

### Drill Intensivo
- Repetición deliberada de un setup
- 10-30 repeticiones
- Enfoque en timing y ejecución

---

## 💡 Consejos Pro

1. **Menos es más**: Máximo 5 stocks en watchlist
2. **Quality over quantity**: Mejor 1 trade A+ que 5 trades B
3. **El mercado siempre tiene razón**: No luches contra la tendencia
4. **Tu edge es la disciplina**: Sigue tu plan al 100%
5. **El trading es un maratón**: Consistencia > Home runs

---

## 🆘 Solución de Problemas

### Error: "No module named 'streamlit'"
```bash
pip install streamlit
```

### Error: "No se pueden cargar datos"
- Verifica conexión a internet
- Yahoo Finance puede estar temporalmente down
- Intenta con otro símbolo

### Error: "Database locked"
- Cierra otras instancias de la app
- Elimina `database/elite_academy.db` y reinicia

---

## 📚 Recursos Adicionales

### Libros Recomendados
- "Trading in the Zone" - Mark Douglas
- "One Good Trade" - Mike Bellafiore
- "The PlayBook" - Mike Bellafiore

### Traders a Seguir
- Steven Dux (@Steven1Dux)
- Kyle Williams (@kylewskye)
- Alex Temiz (@AlexTemiz)
- Lance Breitstein (@LanceBrei)

---

## ❓ FAQ

**¿Puedo perder dinero real?**  
No, esta es una plataforma de simulación con capital virtual.

**¿Los datos son en tiempo real?**  
Los datos vienen de Yahoo Finance con ligero retraso (15 min).

**¿Puedo resetear mi progreso?**  
Sí, elimina la base de datos y reinicia.

**¿Cómo subo de nivel rápido?**  
Completa Daily Reports diariamente y opera con disciplina.

---

**¡Empieza tu viaje hacia la maestría en trading! 🚀**