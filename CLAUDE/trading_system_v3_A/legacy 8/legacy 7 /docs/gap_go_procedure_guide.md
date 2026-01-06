# Gap & Go Trading System - Procedimiento Diario Completo

## 📋 Resumen Ejecutivo

Este sistema combina un **ProScreener de ProRealTime** para detectar gaps ideales con un **sistema algorítmico en Streamlit** que ejecuta la estrategia Gap & Go automáticamente. El procedimiento debe ejecutarse cada día de trading entre 8:30-9:30 AM EST.

---

## 🛠️ Herramientas Necesarias

### Software Requerido
- [ ] **ProRealTime** (con datos premarket US)
- [ ] **Streamlit Trading System** (plataforma de trading algorítmico)
- [ ] Conexión a internet estable
- [ ] Broker con acceso a smallcaps US

### Configuraciones Previas
- [ ] ProRealTime configurado con datos US extended hours
- [ ] Estrategia Gap & Go cargada en Streamlit
- [ ] Universo de trading: NASDAQ SmallCaps

---

## ⏰ Timeline Diario de Ejecución

| Hora (EST) | Actividad | Duración | Crítico |
|------------|-----------|----------|---------|
| 8:30 AM | Ejecutar ProScreener | 2 min | ⭐⭐⭐ |
| 8:35 AM | Análisis y selección | 10 min | ⭐⭐⭐ |
| 8:50 AM | Copiar a Streamlit | 5 min | ⭐⭐⭐ |
| 9:00 AM | Verificación sistema | 5 min | ⭐⭐ |
| 9:25 AM | Activar trading | 2 min | ⭐⭐⭐ |
| 9:30 AM | Monitoreo inicial | 30 min | ⭐⭐ |

---

## 📊 PASO 1: Configurar ProScreener (SETUP INICIAL)

### 1.1 Abrir ProRealTime
1. Iniciar ProRealTime
2. Ir a **ProScreener**
3. Crear **Nuevo Screener**
4. Nombrar: "Gap_&_Go_V2"

### 1.2 Configurar Parámetros
```
Temporalidad: DIARIA (Daily/1D) ⚠️ CRÍTICO
Universe: NASDAQ SmallCaps
Market: US Stocks
Extended Hours: HABILITADO
```

### 1.3 Código del Screener
**Copiar y pegar el código completo del ProScreener** (proporcionado anteriormente)

### 1.4 Verificación
- [ ] Screener "Gap_&_Go_V2" guarda correctamente
- [ ] Test execution funciona
- [ ] Columnas aparecen: Gap %, Vol Ratio, Score, PM High, Price, Breakout

---

## 🔍 PASO 2: Ejecución Matutina del Screener

### 2.1 Primera Ejecución (8:30 AM EST)

1. **Abrir ProRealTime** a las 8:30 AM
2. **Ejecutar** "Gap_&_Go_V2"
3. **Esperar** resultados (30-60 segundos)
4. **Verificar** que hay datos:
   - Al menos 10-20 resultados
   - Gap % entre -20% y +20%
   - Vol Ratio > 2.0

### 2.2 Interpretación de Resultados

| Columna | Descripción | Ejemplo | Interpretación |
|---------|-------------|---------|----------------|
| **Gap %** | Porcentaje de gap | 6.2 | Gap up 6.2% |
| **Vol Ratio** | Multiplicador volumen | 4.5 | Volumen 4.5x normal |
| **Score** | Calidad del setup | 8 | Excelente calidad |
| **PM High** | High premarket | 12.50 | Resistencia a romper |
| **Price** | Precio actual | 13.20 | Precio por acción |
| **Breakout** | Breakout confirmado | 1 | 1=Sí, 0=No |

### 2.3 Ordenar Resultados
1. **Click** en columna "Score"
2. **Ordenar** descendente (mayor a menor)
3. **Focus** en Score >= 7

---

## 🎯 PASO 3: Selección de Plays

### 3.1 Criterios de Selección (8:35 AM)

**TOMAR PLAYS QUE CUMPLAN:**
- [ ] **Score >= 7** (obligatorio)
- [ ] **Gap %** entre 3% y 12% (positivo o negativo)
- [ ] **Vol Ratio >= 3.0** (volumen fuerte)
- [ ] **Price** entre $2.00 y $15.00
- [ ] **NO considerar** columna Breakout para selección

### 3.2 Proceso de Selección

```
1. Crear lista de candidatos:
   - Filtrar por Score >= 7
   - Revisar top 15 resultados
   
2. Aplicar filtros de calidad:
   - Gap % en rango 3-12%
   - Vol Ratio >= 3.0
   - Precio $2-$15
   
3. Verificación manual rápida:
   - Check news si disponible
   - Evitar gaps > 15% (muy extremos)
   - Preferir gaps 4-8% (sweet spot)
   
4. Seleccionar top 5-8 plays finales
```

### 3.3 Formato de Lista Final

**Ejemplo de selección:**
```
ABCD - Gap: 6.2%, Vol: 4.5x, Score: 8, Price: $13.20
EFGH - Gap: -4.1%, Vol: 3.2x, Score: 7, Price: $8.20
IJKL - Gap: 5.8%, Vol: 5.1x, Score: 9, Price: $7.45
MNOP - Gap: 3.9%, Vol: 3.8x, Score: 7, Price: $12.10
QRST - Gap: 8.1%, Vol: 4.2x, Score: 8, Price: $9.75
```

---

## 💻 PASO 4: Configurar Sistema Streamlit

### 4.1 Acceder a Streamlit (8:50 AM)

1. **Abrir** navegador
2. **Ir** a plataforma Streamlit
3. **Login** con credenciales
4. **Verificar** que estrategia Gap & Go está disponible

### 4.2 Añadir Tickers Seleccionados

**Para cada ticker seleccionado:**

1. **Localizar** sección "Add Scanner Gap" o similar
2. **Introducir datos:**
   ```
   Symbol: ABCD
   Gap Percentage: 6.2
   Volume Ratio: 4.5
   Scanner Score: 8
   Current Price: 13.20
   ```
3. **Click** "Add to System"
4. **Repetir** para todos los tickers

### 4.3 Verificación en Streamlit

**Confirmar que se han añadido:**
- [ ] Todos los tickers aparecen en lista
- [ ] Gap percentages correctos
- [ ] Status = "Ready" o "Pending"
- [ ] No errores en log

---

## ⚙️ PASO 5: Activación del Sistema

### 5.1 Verificación Pre-Activación (9:00 AM)

**Checklist antes de activar:**
- [ ] Todos los tickers añadidos correctamente
- [ ] Estrategia Gap & Go seleccionada
- [ ] Capital disponible suficiente
- [ ] Conexión broker estable
- [ ] Risk management configurado

### 5.2 Configuración Final

**Parámetros recomendados:**
```
Max Risk per Trade: 1.5%
Position Size: $1000 máximo por posición
Stop Loss: 5%
Profit Target: 12%
Max Hold Time: 90 minutos
```

### 5.3 Activación (9:25 AM)

1. **Ir** a sección "Strategy Control"
2. **Seleccionar** "Optimized Gap & Go"
3. **Click** "Activate Strategy"
4. **Confirmar** status = "ACTIVE"
5. **Verificar** que dice "Ready for Market Open"

---

## 📈 PASO 6: Monitoreo Post-Apertura

### 6.1 Monitoreo Inicial (9:30-10:00 AM)

**Qué observar:**
- [ ] Entradas automáticas ejecutándose
- [ ] Precios rompiendo resistance levels
- [ ] Volumen manteniéndose fuerte
- [ ] Stop losses funcionando

### 6.2 Señales de Alerta

**🚨 INTERVENIR SI:**
- Múltiples stops activados simultaneamente
- Errores de conexión broker
- Gaps llenándose rápidamente
- Volumen desapareciendo

### 6.3 Registro de Performance

**Anotar diariamente:**
```
Fecha: ___________
Plays seleccionados: ___
Plays con entrada: ___
Ganadores: ___
Perdedores: ___
P&L total: $______
Notas: ____________
```

---

## ⚠️ Puntos Críticos y Errores Comunes

### ❌ Errores Frecuentes

1. **Ejecutar screener tarde** (después 9:00 AM)
   - ✅ Solución: Alarma 8:25 AM

2. **Usar timeframe incorrecto** (5min en lugar de diario)
   - ✅ Solución: Verificar siempre "Daily"

3. **Esperar Breakout = 1** para seleccionar
   - ✅ Solución: Seleccionar por Score, no Breakout

4. **Añadir demasiados plays** (>8)
   - ✅ Solución: Máximo 8 plays, preferir calidad

5. **No activar antes de 9:30 AM**
   - ✅ Solución: Activar a 9:25 AM siempre

### 🔧 Troubleshooting

**Si ProScreener no muestra resultados:**
- Verificar temporalidad = Daily
- Check extended hours habilitado
- Verificar NASDAQ SmallCaps seleccionado

**Si Streamlit no acepta tickers:**
- Verificar formato ticker (sin espacios)
- Check conexión internet
- Restart browser si necesario

**Si no hay entradas post-9:30 AM:**
- Verificar que estrategia está active
- Check que tickers tienen gaps válidos
- Revisar logs para errores

---

## 📝 Template Diario de Ejecución

### Checklist Rápido Matutino

```
⏰ 8:30 AM
□ ProRealTime abierto
□ Screener ejecutado
□ Resultados obtenidos

⏰ 8:35 AM  
□ Resultados ordenados por Score
□ Top 15 revisados
□ 5-8 plays seleccionados

⏰ 8:50 AM
□ Streamlit abierto
□ Tickers añadidos
□ Datos verificados

⏰ 9:00 AM
□ Sistema verificado
□ Parámetros correctos
□ Capital disponible

⏰ 9:25 AM
□ Estrategia activada
□ Status = ACTIVE
□ Ready for market open

⏰ 9:30 AM
□ Market abierto
□ Monitoreo iniciado
□ Primeras entradas ejecutándose
```

### Notas Importantes

- **Consistencia es clave**: Ejecutar mismo proceso diariamente
- **No improvisar**: Seguir timeline estrictamente
- **Quality over quantity**: Mejor 5 plays excelentes que 10 mediocres
- **Monitor but don't micromanage**: Dejar que sistema ejecute
- **Learn and adapt**: Revisar performance semanalmente

---

## 📞 Contacto y Soporte

**Para dudas sobre este procedimiento:**
- Revisar troubleshooting section
- Verificar logs de Streamlit
- Documentar errores para mejora del proceso

**Actualizaciones del sistema:**
- Review parámetros mensualmente
- Ajustar según performance
- Backup configuraciones importantes