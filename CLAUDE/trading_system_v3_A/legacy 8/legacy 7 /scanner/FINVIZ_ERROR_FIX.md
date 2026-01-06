# Fix: FINVIZ AttributeError para símbolos no soportados

## Problema Original

Telegram mostraba este error:
```
🚨 FINVIZ ERROR

📊 Symbol: CRCG
❌ Error: AttributeError
🔄 Fallback: Using Yahoo/NewsAPI
```

## Causa Raíz

El error `AttributeError: 'NoneType' object has no attribute 'find_all'` ocurre dentro de la librería **finvizfinance** cuando:

1. El símbolo no existe en Finviz
2. La página tiene una estructura HTML diferente a la esperada
3. Es un tipo de instrumento que Finviz no soporta (ETFs, ciertos OTC, etc.)

### Ejemplo: CRCG

- **Símbolo**: CRCG
- **Tipo**: ETF (Leverage Shares 2X Long CRCL Daily ETF)
- **Exchange**: NasdaqGM
- **Problema**: Finviz no tiene página o la estructura HTML es diferente
- **Resultado Yahoo**: Datos disponibles pero sin noticias

## Solución Implementada

### 1. Manejo Robusto de Errores en `_fetch_finviz_news()`

```python
def sync_fetch():
    try:
        stock = finvizfinance(symbol)
        return stock.ticker_news()
    except AttributeError as e:
        # Detectar error de parsing HTML
        if "'NoneType' object has no attribute" in str(e):
            logger.warning(f"Finviz HTML parsing failed for {symbol}")
        return None  # Retornar None en lugar de lanzar excepción
```

**Beneficios**:
- No rompe el flujo del scanner
- Permite que el sistema continúe con fuentes alternativas
- Logging apropiado para debugging

### 2. Validación Mejorada del DataFrame

```python
# Validaciones múltiples antes de procesar
if news_data is None:
    return {'headlines': [], 'error': 'No data returned'}

is_dataframe = hasattr(news_data, 'empty') and hasattr(news_data, 'iterrows')
if not is_dataframe:
    return {'headlines': [], 'error': f'Unexpected data type: {type(news_data)}'}

if news_data.empty:
    return {'headlines': [], 'error': 'Empty DataFrame'}
```

### 3. Mensajes de Telegram Mejorados

```python
# Mensaje específico para símbolos no encontrados
if "'NoneType' object has no attribute" in str(e):
    telegram_alert = f"""⚠️ **FINVIZ SYMBOL NOT FOUND**

📊 Symbol: {symbol}
❌ Finviz page not available or invalid symbol
🔄 Switching to: Yahoo Finance + NewsAPI

💡 This is normal for OTC/unlisted stocks"""
```

## Comportamiento Esperado

### Antes del Fix
```
🚨 FINVIZ ERROR
📊 Symbol: CRCG
❌ Error: AttributeError
🔄 Fallback: Using Yahoo/NewsAPI
```

### Después del Fix
```
⚠️ FINVIZ SYMBOL NOT FOUND

📊 Symbol: CRCG
❌ Finviz page not available or invalid symbol
🔄 Switching to: Yahoo Finance + NewsAPI

💡 This is normal for OTC/unlisted stocks
```

## Sistema de Fallback

El sistema usa una jerarquía de fuentes:

1. **Finviz** (primaria) - Mejor calidad pero no cubre todos los símbolos
2. **Finnhub** (secundaria) - Buena cobertura, free tier
3. **Yahoo Finance** (terciaria) - Amplia cobertura, siempre disponible
4. **Polygon** (cuaternaria) - Alternativa confiable
5. **NewsAPI** (quinaria) - Requiere API key

**Si Finviz falla**, el sistema automáticamente:
- ✅ Continúa con las otras fuentes
- ✅ Registra el error en logs
- ✅ Notifica vía Telegram (una vez)
- ✅ **NO interrumpe el escaneo**

## Testing

### Test 1: Símbolo que funciona (AAPL)
```bash
python test_finviz_crcg.py
# ✅ Retorna DataFrame con ~100 noticias
```

### Test 2: Símbolo problemático (CRCG)
```bash
python test_finviz_crcg.py
# ⚠️  AttributeError capturado
# ✅ Sistema continúa con Yahoo Finance
```

### Test 3: Yahoo Finance para CRCG
```bash
python test_crcg_yahoo.py
# ✅ Datos del ETF disponibles
# ⚠️  Sin noticias disponibles
```

## Archivos Modificados

1. **multi_source_news.py**:
   - Línea 446-464: Manejo robusto en `_fetch_finviz_news()`
   - Línea 465-541: Validación mejorada del DataFrame
   - Línea 426-450: Mensajes de Telegram descriptivos

## Tipos de Símbolos Afectados

Este error puede ocurrir con:
- ETFs de bajo volumen
- Acciones OTC
- Símbolos recién listados
- Instrumentos exóticos (warrants, rights, etc.)
- Símbolos delistados

## Recomendaciones

1. **No es necesario fijar nada más** - El sistema ahora maneja estos casos correctamente
2. **El error es esperado** - Algunos símbolos simplemente no están en Finviz
3. **El fallback funciona** - Yahoo Finance y otras fuentes cubren estos casos
4. **Monitorear logs** - Si muchos símbolos fallan, puede indicar un problema con Finviz

## Logs Útiles

```python
# Éxito con múltiples fuentes
INFO: News sources successful for CRCG: yahoo(3), finnhub(2)

# Fallo de Finviz con fallback exitoso
INFO: News sources failed for CRCG: finviz - using fallback sources
INFO: News sources successful for CRCG: yahoo(3)
```

## Conclusión

✅ Error identificado y corregido
✅ Sistema más robusto
✅ Mejor feedback al usuario
✅ No interrumpe el flujo de escaneo
✅ Mensajes de Telegram más informativos
