# 📈 CONFIGURACIÓN DEL SISTEMA PRINCIPAL

## 🔧 Modos de Operación

### 🎮 MODO TESTING (Simulación)
- **Configuración**: `active_profile = TESTING` 
- **Dependencias**: Solo requiere Python básico
- **Datos**: Archivos CSV incluidos
- **Uso**: Desarrollo, pruebas, mercado cerrado

### 📈 MODO PRODUCTION (Demo/Real)
- **Configuración**: `active_profile = PRODUCTION`
- **Dependencias**: Requiere `pip install ib_insync`
- **Datos**: Interactive Brokers en tiempo real
- **Uso**: Trading demo o real con broker

### 🔄 Fallback Automático
Si configuras `PRODUCTION` pero no tienes `ib_insync`, el sistema automáticamente:
- ✅ Detecta la falta de dependencias
- ✅ Cambia a modo TESTING automáticamente  
- ✅ Funciona con datos CSV sin interrumpir

## 📈 CÓMO CONFIGURAR SÍMBOLOS

## 🎯 Configuración en config.ini

Para cambiar los símbolos que usa main.py (opción 6 del menú), edita el archivo `config.ini`:

```ini
[TRADING]
# Default symbols for main.py (comma-separated)
# TESTING: Use symbols we have CSV data for
# PRODUCTION: Use any symbols you want to trade
default_symbols = XXII,SOFI,SNDL,MVIS,PLTR
```

## 📊 Símbolos Disponibles por Modo

### 🎮 MODO TESTING (Simulación)
Símbolos con datos CSV disponibles:
- AAPL, BB, BLNK, CAN, CLOV, COIN, FCEL, GME, HOOD, LAZR
- LOBO, MARA, MVIS, NIO, PATH, PLTR, PLUG, RBLX, RIOT, SNDL
- SOFI, SOS, SPCE, WKHS, XPEV, XXII

### 📈 MODO PRODUCTION (Demo/Real)
Cualquier símbolo disponible en Interactive Brokers.

## 🔧 Comandos Durante la Ejecución

Una vez que el sistema está corriendo, puedes:

```bash
> add AAPL        # Agregar Apple a la monitorización
> add TSLA        # Agregar Tesla
> remove XXII     # Quitar XXII de la monitorización
> status          # Ver estado actual
> positions       # Ver posiciones abiertas
> stop            # Detener el sistema
```

## 💡 Recomendaciones

### Para TESTING:
- Usa símbolos con datos CSV disponibles
- Máximo 5-8 símbolos para mejor rendimiento
- Símbolos recomendados: `XXII,SOFI,SNDL,MVIS,PLTR`

### Para PRODUCTION:
- Usa símbolos líquidos con buen volumen
- Considera spreads bid-ask
- Máximo 10-12 símbolos inicialmente

## 🚀 Flujo de Trabajo Recomendado

1. **Configurar símbolos** en config.ini
2. **Ejecutar** opción 6 del menú principal
3. **Monitorizar** la ejecución
4. **Agregar/quitar** símbolos dinámicamente según necesidad
5. **Revisar posiciones** y ajustar si es necesario

## 🔄 Cambios Rápidos

Para cambiar rápidamente los símbolos sin reiniciar:

```bash
# Durante la ejecución del sistema:
> remove XXII
> remove SOFI  
> add AAPL
> add TSLA
> status          # Verificar cambios
```

## 📋 Ejemplo Completo

```ini
# Para trading de smallcaps en simulación
default_symbols = XXII,SOFI,SNDL,MVIS,RIOT

# Para trading de largecaps en production  
default_symbols = AAPL,TSLA,GOOGL,MSFT,NVDA
```

El sistema mostrará automáticamente los símbolos configurados al iniciar.