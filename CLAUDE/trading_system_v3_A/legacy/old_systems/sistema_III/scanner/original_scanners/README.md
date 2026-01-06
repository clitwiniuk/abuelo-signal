# Daily Plays Filter Scanner

Sistema de filtrado para identificar plays del día con datos de ProRealTime ProScreener.

## Características

- ✅ **Filtro de Volumen**: Premarket >500K (filtrado en ProRealTime)
- ✅ **Gap Filter**: Gap positivo >10% (filtrado en ProRealTime) 
- ✅ **Float Filter**: Limita a acciones con float <100M shares
- ✅ **Catalyst Filter**: Escanea noticias por palabras clave relevantes

## Instalación

```bash
cd scanner
pip install -r requirements.txt
```

## Uso

### 1. Línea de Comandos

```bash
python daily_plays_filter.py
```

Sigue las instrucciones para pegar los datos de ProRealTime.

### 2. Interfaz Web (Recomendado)

```bash
streamlit run web_interface.py
```

Abre automáticamente la interfaz web en tu navegador.

## Flujo de Trabajo

### En ProRealTime ProScreener:

1. Configura estos filtros:
   - Volumen premarket >500,000 acciones
   - Gap positivo >10% vs cierre anterior
   - Precio en rango smallcap ($0.10 - $15.00)

2. Ejecuta el screener y copia los resultados

### En el Scanner:

1. Pega los datos en la interfaz
2. Ajusta el float máximo si necesario (default: 100M)
3. Ejecuta el filtro
4. Obtén la lista final de tickers: `XXXX, YYYY, ZZZZ`

## Formato de Datos Esperado

```
"Ticker"    "Nombre"    "Criterio"    "%Var"    "Var"    "Inserción"    "Último"    "Volumen"
"TLRY"    "TILRAY BRANDS INC."    "6"    "+0,34%"    "+0,0031"    "20:03:57"    "0,9231"    "289M"
"PRPH"    "PROPHASE LABS INC."    "2"    "+24,25%"    "+0,0683"    "22:30:13"    "0,3500"    "272M"
```

## Palabras Clave de Catalizadores

### FDA/Regulatory
- FDA, approval, drug, clinical, trial, phase, breakthrough, orphan, designation, patent

### Earnings/Financial  
- earnings, revenue, profit, guidance, beat, miss, outlook, forecast

### M&A/Corporate
- acquisition, merger, buyout, takeover, deal, partnership, collaboration

### Contracts/Business
- contract, order, award, win, selected, agreement, license

### Technology/Innovation
- breakthrough, innovation, launch, product, technology, AI, blockchain, EV, battery

### Energy/Commodities
- oil, gas, gold, lithium, rare earth, drilling, discovery, reserve

### Crypto/Fintech
- bitcoin, crypto, blockchain, NFT, DeFi, digital asset, fintech

## Ejemplo de Uso

### Input (ProRealTime):
```
"GEVO"    "GEVO INC."    "2"    "+56,00%"    "+0,70"    "22:30:04"    "1,95"    "81,7M"
"CGTX"    "COGNITION THERAPEUTICS INC."    "2"    "+56,05%"    "+0,4813"    "22:25:37"    "1,34"    "14,3M"
```

### Output (Filtrado):
```
GEVO, CGTX
```

Solo si ambos cumplen:
- Float <100M shares ✓
- Noticias con catalizadores en últimos 7 días ✓

## Integración con Trading System

Los tickers filtrados pueden usarse directamente en:

1. **config.ini** - Sección `[TRADING]`
2. **Estrategias específicas** - Como lista de símbolos objetivo
3. **DailyPlaysStrategy** - Estrategia especializada para estos plays

## Notas Técnicas

- **APIs utilizadas**: Yahoo Finance (yahooquery) para float y noticias - más eficiente que yfinance
- **Batch processing**: Procesa múltiples tickers en una sola llamada API
- **Rate limiting**: Implementado para evitar bloqueos con delays optimizados
- **Async processing**: Para procesamiento eficiente de múltiples tickers
- **Error handling**: Robusto manejo de errores de API y parsing

## Limitaciones

- Yahoo Finance puede no tener datos de float para todos los tickers
- Las noticias pueden no estar actualizadas en tiempo real
- Algunos tickers muy pequeños pueden no tener suficiente cobertura

## Próximas Mejoras

- [ ] Integración con APIs premium (Benzinga, Polygon)
- [ ] Filtros adicionales (insider trading, short interest)
- [ ] Alertas automáticas por Telegram
- [ ] Integración directa con el trading system