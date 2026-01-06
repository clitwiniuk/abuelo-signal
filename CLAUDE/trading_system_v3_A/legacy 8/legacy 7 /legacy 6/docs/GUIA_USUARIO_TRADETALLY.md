# 📘 Guía de Usuario TradeTally - Nuevas Funcionalidades

**Versión:** 2.0 - Tier 1 Features Complete  
**Fecha:** Noviembre 2025  
**Estado:** ✅ 4 Fases Completadas

---

## 📑 Índice

1. [Introducción](#introducción)
2. [Fase 1: Custom Metrics (Métricas Personalizadas)](#fase-1-custom-metrics)
3. [Fase 2: Pivot Grid (Análisis Dinámico)](#fase-2-pivot-grid)
4. [Fase 3: AI Pattern Detection (Detección de Patrones con IA)](#fase-3-ai-pattern-detection)
5. [Fase 4: Advanced Filters UI (Interfaz de Filtros Avanzados)](#fase-4-advanced-filters-ui)
6. [Casos de Uso Prácticos](#casos-de-uso-prácticos)
7. [Consejos y Mejores Prácticas](#consejos-y-mejores-prácticas)
8. [Solución de Problemas](#solución-de-problemas)

---

## Introducción

TradeTally ha sido mejorado con **4 nuevas funcionalidades de nivel profesional** que te permiten analizar tus operaciones de trading de formas que antes eran imposibles. Estas mejoras te colocan al nivel (o por encima) de las mejores plataformas de journaling del mercado como Tradervue, Tradezella y TraderSync.

### ¿Qué puedes hacer ahora?

- ✅ **Crear métricas personalizadas** con fórmulas matemáticas
- ✅ **Analizar datos multidimensionales** con tablas dinámicas
- ✅ **Descubrir patrones ocultos** usando inteligencia artificial
- ✅ **Guardar filtros complejos** para análisis recurrentes

---

## Fase 1: Custom Metrics

### ¿Qué son las Custom Metrics?

Las métricas personalizadas te permiten crear **campos calculados** usando fórmulas matemáticas sobre tus datos de trading. Es como tener Excel dentro de TradeTally.

### ¿Cómo acceder?

1. Navega al menú principal
2. Haz clic en **"Analytics"** → **"Custom Metrics"**

### Crear tu Primera Métrica Personalizada

#### Paso 1: Abrir el Constructor

Haz clic en el botón **"New Custom Metric"** (esquina superior izquierda).

#### Paso 2: Completar el Formulario

**Campos obligatorios:**

- **Name** (Nombre): Un nombre descriptivo, ej: "R-Multiple"
- **Formula** (Fórmula): La expresión matemática
- **Category** (Categoría): Risk, Performance, Statistical, o Time
- **Data Type** (Tipo de dato): number, percentage, currency, ratio

**Campos opcionales:**

- **Description** (Descripción): Explica qué mide esta métrica

#### Paso 3: Escribir la Fórmula

**Campos disponibles para usar en fórmulas:**

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `pnl` | Ganancia/Pérdida | `pnl > 0` |
| `mae` | Maximum Adverse Excursion | `abs(mae)` |
| `mfe` | Maximum Favorable Excursion | `abs(mfe)` |
| `entry_price` | Precio de entrada | `entry_price * quantity` |
| `exit_price` | Precio de salida | `exit_price - entry_price` |
| `quantity` | Cantidad de acciones | `quantity * 100` |
| `win_rate` | Tasa de ganancia (%) | `win_rate / 100` |
| `avg_win` | Ganancia promedio | `avg_win * 2` |
| `avg_loss` | Pérdida promedio | `abs(avg_loss)` |
| `profit_factor` | Factor de beneficio | `profit_factor > 2` |

**Funciones matemáticas disponibles:**

- `abs()` - Valor absoluto
- `round()` - Redondear
- `sqrt()` - Raíz cuadrada
- `max()` - Máximo entre valores
- `min()` - Mínimo entre valores
- `pow()` - Potencia

### Ejemplos de Métricas Útiles

#### 1. R-Multiple (Relación Riesgo/Beneficio)

```javascript
pnl / (abs(mae) || 1)
```

**Qué mide:** Cuántas veces tu riesgo inicial ganaste o perdiste.  
**Categoría:** Performance  
**Tipo:** ratio

#### 2. Expectancy (Expectativa Matemática)

```javascript
(win_rate / 100) * avg_win - ((100 - win_rate) / 100) * abs(avg_loss)
```

**Qué mide:** Cuánto esperas ganar por operación en promedio.  
**Categoría:** Statistical  
**Tipo:** currency

#### 3. Efficiency Ratio (Ratio de Eficiencia)

```javascript
pnl / (abs(mae) + abs(mfe))
```

**Qué mide:** Qué tan bien capturaste el movimiento disponible.  
**Categoría:** Performance  
**Tipo:** ratio

#### 4. Position Size % (Tamaño de Posición)

```javascript
(quantity * entry_price) / (capital_at_trade_time || 1) * 100
```

**Qué mide:** Qué porcentaje de tu capital usaste.  
**Categoría:** Risk  
**Tipo:** percentage

#### 5. Risk-Adjusted Return

```javascript
pnl / max(abs(mae), 1)
```

**Qué mide:** Retorno ajustado por el riesgo máximo.  
**Categoría:** Risk  
**Tipo:** ratio

### Validar tu Fórmula

Antes de guardar, el sistema **valida automáticamente** tu fórmula:

- ✅ Sintaxis correcta
- ✅ Variables reconocidas
- ✅ Funciones permitidas
- ✅ Protección contra errores

Si hay un error, verás un mensaje explicando qué está mal.

### Ver Ejemplos Predefinidos

Haz clic en **"View Examples"** para ver una biblioteca de métricas pre-configuradas que puedes copiar y adaptar.

### Usar tus Métricas

Una vez creada, tu métrica personalizada estará disponible en:

- Filtros avanzados (como `custom:nombre_metrica`)
- Exportaciones CSV
- Análisis futuros

---

## Fase 2: Pivot Grid

### ¿Qué es el Pivot Grid?

Es una **tabla dinámica** (como en Excel) que te permite cruzar cualquier dimensión con cualquier métrica para descubrir patrones en tus datos.

### ¿Cómo acceder?

1. Navega al menú principal
2. Haz clic en **"Analytics"** → **"Pivot Grid"**

### Conceptos Clave

#### Dimensiones (Dimensions)

Son las **categorías** por las que quieres agrupar tus datos:

**Dimensiones Temporales:**
- `day_of_week` - Día de la semana (Lunes, Martes, etc.)
- `hour_of_day` - Hora del día (0-23)
- `month` - Mes
- `year` - Año
- `session_type` - Tipo de sesión (Pre-market, Market Hours, After Hours)

**Dimensiones de Operación:**
- `strategy` - Estrategia (ORB, Momentum, etc.)
- `symbol` - Símbolo (AAPL, TSLA, etc.)
- `side` - Lado (Long, Short)
- `catalyst_type` - Tipo de catalizador

**Dimensiones de Clasificación:**
- `entry_price_range` - Rango de precio de entrada
- `quantity_range` - Rango de cantidad
- `hold_time_range` - Rango de tiempo de retención
- `confidence_bucket` - Nivel de confianza (Low, Medium, High)
- `tag` - Etiquetas individuales

#### Métricas (Metrics)

Son los **valores** que quieres calcular:

**Volumen:**
- `trade_count` - Número de operaciones

**P&L:**
- `total_pnl` - P&L total
- `avg_pnl` - P&L promedio
- `avg_win` - Ganancia promedio
- `avg_loss` - Pérdida promedio
- `best_trade` - Mejor operación
- `worst_trade` - Peor operación

**Performance:**
- `win_rate` - Tasa de ganancia (%)
- `profit_factor` - Factor de beneficio
- `sharpe_ratio` - Ratio de Sharpe
- `expectancy` - Expectativa matemática

**Riesgo:**
- `avg_mae` - MAE promedio
- `avg_mfe` - MFE promedio
- `mae_mfe_ratio` - Ratio MAE/MFE

**Tiempo:**
- `avg_hold_time` - Tiempo promedio de retención

### Crear tu Primer Análisis Pivot

#### Opción 1: Usar un Preset (Recomendado para empezar)

1. Haz clic en el dropdown **"Select Preset"**
2. Elige uno de los 12 presets disponibles:
   - **Performance by Strategy** - Rendimiento por estrategia
   - **Day of Week Analysis** - Análisis por día de la semana
   - **Symbol Performance Matrix** - Matriz de rendimiento por símbolo
   - **Time-Based Analysis** - Análisis basado en tiempo
   - Y 8 más...
3. Haz clic en **"Generate Pivot"**

#### Opción 2: Configuración Manual

**Paso 1: Seleccionar Dimensiones de Fila**

Haz clic en **"Add Row Dimension"** y selecciona, por ejemplo:
- `strategy` (para ver cada estrategia en una fila)

**Paso 2: Seleccionar Dimensiones de Columna (Opcional)**

Si quieres una tabla cruzada, añade dimensiones de columna:
- `day_of_week` (para ver cada día en una columna)

**Paso 3: Seleccionar Métricas**

Marca las casillas de las métricas que quieres ver:
- ✅ `trade_count`
- ✅ `win_rate`
- ✅ `avg_pnl`
- ✅ `profit_factor`

**Paso 4: Aplicar Filtros (Opcional)**

Puedes filtrar por:
- **Date Range** - Rango de fechas
- **Symbol** - Símbolo específico
- **Strategy** - Estrategia específica
- **Side** - Long o Short

**Paso 5: Generar**

Haz clic en **"Generate Pivot"** y espera unos segundos.

### Interpretar los Resultados

#### Tabla Simple (Sin columnas)

Si solo usaste dimensiones de fila, verás una tabla estándar:

| Strategy | Trade Count | Win Rate | Avg P&L | Profit Factor |
|----------|-------------|----------|---------|---------------|
| ORB | 150 | 65.3% | $125.50 | 2.1 |
| Momentum | 200 | 58.0% | $98.75 | 1.8 |
| Daily Plays | 100 | 72.0% | $210.30 | 3.2 |

#### Tabla Cruzada (Con columnas)

Si usaste dimensiones de columna, verás una tabla pivotada:

**Ejemplo: Strategy × Day of Week (Win Rate)**

| Strategy | Monday | Tuesday | Wednesday | Thursday | Friday |
|----------|--------|---------|-----------|----------|--------|
| ORB | 62% | 68% | 70% | 65% | 55% |
| Momentum | 55% | 60% | 58% | 62% | 50% |

### Drill-Down (Profundizar)

**¿Qué es?** Ver las operaciones individuales detrás de cada celda.

**Cómo usarlo:**

1. Haz clic en **cualquier celda** de la tabla
2. Se abrirá un modal mostrando:
   - Las dimensiones activas (ej: "Strategy: ORB, Day: Monday")
   - Lista de todas las operaciones que cumplen esos criterios
   - Estadísticas resumidas (Total Trades, Total P&L, Win Rate, Avg P&L)
3. Haz clic en cualquier operación para ver su detalle completo

### Exportar a CSV

1. Genera tu pivot
2. Haz clic en **"Export to CSV"**
3. El archivo se descargará automáticamente

---

## Fase 3: AI Pattern Detection

### ¿Qué es AI Pattern Detection?

Es un **sistema de inteligencia artificial** (Google Gemini Pro) que analiza automáticamente tus operaciones y descubre **patrones ocultos**, **debilidades** y **oportunidades** que serían imposibles de encontrar manualmente.

### ¿Cómo acceder?

1. Navega al menú principal
2. Haz clic en **"Analytics"** → **"AI Pattern Detection"**

### Configuración Inicial (Solo primera vez)

**Requisito:** Necesitas una API Key de Google Gemini.

#### Obtener tu API Key:

1. Visita https://ai.google.dev/
2. Regístrate o inicia sesión
3. Ve a "Get API Key"
4. Copia tu API key

#### Configurar en TradeTally:

1. Abre el archivo `.env.local` en la carpeta `tradetally/backend/`
2. Añade esta línea:
   ```
   GEMINI_API_KEY=tu_api_key_aqui
   ```
3. Reinicia el servidor backend

### Ejecutar tu Primer Análisis de IA

#### Paso 1: Seleccionar Período

Elige el rango de fechas a analizar:
- **Recomendado:** Últimos 3 meses (suficientes datos, resultados relevantes)
- **Mínimo:** 30 días
- **Máximo:** Todo tu historial

#### Paso 2: Aplicar Filtros (Opcional)

Puedes limitar el análisis a:
- **Strategy:** Analizar solo una estrategia específica
- **Symbol:** Analizar solo un símbolo específico

#### Paso 3: Analizar

1. Haz clic en **"Analyze with AI"**
2. Espera 30-60 segundos (la IA está trabajando)
3. Los resultados se mostrarán automáticamente

> **💡 Tip:** Los resultados se cachean por 1 hora. Si ejecutas el mismo análisis de nuevo, será instantáneo.

### Interpretar los Resultados

La IA organiza los patrones en **4 categorías**:

#### 1. 🕐 Time-Based Patterns (Patrones Temporales)

**Qué descubre:** Cuándo tienes ventaja y cuándo no.

**Ejemplos de insights:**

- ✅ "Tus operaciones antes de las 10:00 AM tienen 72% win rate vs 45% después de las 11:00 AM"
- ⚠️ "Los lunes tienes -$450 de P&L promedio vs +$280 los jueves"
- 💡 "Pre-market trades superan por $200/trade vs market hours"

**Qué hacer:** Ajusta tus horarios de trading para operar solo en tus ventanas de ventaja.

#### 2. 🎯 Entry Condition Patterns (Patrones de Entrada)

**Qué descubre:** Qué setups realmente funcionan.

**Ejemplos de insights:**

- ✅ "Operaciones con confianza 'High' tienen solo 55% win rate (esperabas 75%)"
- ⚠️ "Acciones entre $50-$100 tienen 68% win rate vs $100+: 42%"
- 💡 "Catalizadores de earnings producen +$350 avg vs news: -$120"

**Qué hacer:** Refina tus criterios de entrada basándote en datos reales, no intuición.

#### 3. 📊 Strategy Interactions (Interacciones de Estrategias)

**Qué descubre:** Correlaciones y conflictos ocultos.

**Ejemplos de insights:**

- ✅ "ORB en símbolos de baja volatilidad: 72% win rate vs alta volatilidad: 45%"
- ⚠️ "Ejecutar múltiples estrategias el mismo día reduce performance 70%"
- 💡 "Posiciones >200 acciones tienen 48% win rate vs <100: 65%"

**Qué hacer:** Optimiza la combinación de estrategias y tamaños de posición.

#### 4. 🛡️ Risk Management Patterns (Patrones de Gestión de Riesgo)

**Qué descubre:** Dónde estás dejando dinero en la mesa.

**Ejemplos de insights:**

- ✅ "Stops muy ajustados - MAE avg -$85 pero trades recuperan a +$30"
- ⚠️ "Salidas tempranas - MFE avg +$450 pero sales en +$180"
- 💡 "Revenge trading después de 2+ pérdidas: -$250 avg vs normal +$80"

**Qué hacer:** Ajusta tus stops, targets y reglas psicológicas.

### Top 3 Insights

Arriba de todo verás los **3 hallazgos más importantes** destacados con estrellas ⭐.

Estos son los patrones con mayor impacto en tu P&L.

### Severidad de Patrones

Cada patrón tiene un nivel de severidad:

- 🔴 **High** (Alto) - Impacto significativo, actuar inmediatamente
- 🟡 **Medium** (Medio) - Impacto moderado, considerar ajustes
- 🔵 **Low** (Bajo) - Impacto menor, monitorear

### Impacto Cuantificado

Cada patrón muestra:
- **Impact:** Impacto en dólares (ej: -$450, +$280)
- **Affected Trades:** Número de operaciones afectadas
- **Recommendation:** Acción específica recomendada

### Ver Ejemplos

Haz clic en **"View Examples"** para ver ejemplos de patrones antes de ejecutar tu análisis.

---

## Fase 4: Advanced Filters UI

### ¿Qué son los Saved Filters?

Son **filtros complejos** que puedes guardar y reutilizar. Piensa en ellos como "búsquedas guardadas" con lógica avanzada (AND/OR).

### ¿Cómo acceder?

1. Navega al menú principal
2. Haz clic en **"Analytics"** → **"Saved Filters"**

### Quick Filters (Filtros Rápidos)

TradeTally incluye **12 filtros predefinidos** listos para usar:

1. **Winning Trades** - Solo operaciones ganadoras
2. **Losing Trades** - Solo operaciones perdedoras
3. **Today** - Operaciones de hoy
4. **This Week** - Operaciones de esta semana
5. **This Month** - Operaciones de este mes
6. **Large Positions** - Posiciones grandes (>$10,000)
7. **High Conviction** - Alta confianza (>70%)
8. **After Hours** - Operaciones fuera de horario
9. **Long Positions** - Solo posiciones long
10. **Short Positions** - Solo posiciones short
11. **Big Winners** - Grandes ganadores (>$500)
12. **Big Losers** - Grandes perdedores (<-$500)

#### Cargar Quick Filters:

1. Haz clic en **"Load Quick Filters"**
2. Los 12 filtros aparecerán en tu lista
3. Úsalos como punto de partida

### Crear un Filtro Personalizado

#### Paso 1: Abrir el Constructor

Haz clic en **"New Filter"**.

#### Paso 2: Configurar el Filtro

**Campos básicos:**

- **Name:** Nombre descriptivo (ej: "Operaciones ORB Ganadoras en AAPL")
- **Description:** Explicación opcional
- **Is Favorite:** Marcar como favorito (aparece con ★)

#### Paso 3: Construir la Lógica

Los filtros usan una estructura de **árbol lógico**:

```
AND
├── pnl > 0
├── strategy = "ORB"
└── symbol = "AAPL"
```

**Operadores disponibles:**

| Operador | Descripción | Ejemplo |
|----------|-------------|---------|
| `=` | Igual a | `strategy = "ORB"` |
| `!=` | Diferente de | `side != "Short"` |
| `>` | Mayor que | `pnl > 100` |
| `>=` | Mayor o igual | `win_rate >= 60` |
| `<` | Menor que | `mae < -50` |
| `<=` | Menor o igual | `quantity <= 100` |
| `contains` | Contiene texto | `symbol contains "AA"` |
| `not_contains` | No contiene | `tags not_contains "mistake"` |
| `starts_with` | Empieza con | `symbol starts_with "A"` |
| `ends_with` | Termina con | `symbol ends_with "L"` |
| `in` | En lista | `strategy in ["ORB", "Momentum"]` |
| `not_in` | No en lista | `side not_in ["Short"]` |
| `between` | Entre valores | `pnl between [0, 500]` |
| `is_null` | Es nulo | `exit_price is_null` |
| `is_not_null` | No es nulo | `exit_price is_not_null` |

**Campos filtrables:**

- Básicos: `symbol`, `strategy`, `setup`, `side`, `broker`, `tags`
- Performance: `pnl`, `pnl_percent`, `mae`, `mfe`
- Precios: `entry_price`, `exit_price`, `quantity`
- ML: `strategy_confidence`, `ml_signal_quality`, `market_context_score`
- Tiempo: `trade_date`, `entry_time`, `exit_time`, `trade_session`
- Sector: `sector`, `company_name`
- Custom: `custom:nombre_metrica` (tus métricas personalizadas)

#### Paso 4: Lógica AND/OR

Puedes anidar condiciones:

**Ejemplo: Operaciones ganadoras de ORB o Momentum en tech stocks**

```
AND
├── pnl > 0
├── OR
│   ├── strategy = "ORB"
│   └── strategy = "Momentum"
└── sector = "Technology"
```

### Usar tus Filtros

Una vez guardado, tu filtro estará disponible para:

- Aplicar en la vista de Trades
- Usar en análisis futuros
- Combinar con otros filtros

### Gestión de Filtros

- **Editar:** Haz clic en el icono de lápiz
- **Eliminar:** Haz clic en el icono de papelera
- **Favorito:** Marca la estrella para acceso rápido
- **Estadísticas:** Ve cuántas veces has usado cada filtro

---

## Casos de Uso Prácticos

### Caso 1: Optimizar Horarios de Trading

**Objetivo:** Descubrir a qué horas operas mejor.

**Pasos:**

1. Ve a **Pivot Grid**
2. Selecciona preset **"Day of Week Analysis"**
3. Genera el pivot
4. Observa qué días/horas tienen mejor win rate
5. Ve a **AI Pattern Detection**
6. Ejecuta análisis completo
7. Revisa la sección **Time-Based Patterns**
8. Ajusta tu horario de trading basándote en los datos

**Resultado esperado:** Identificar tus "golden hours" y evitar tus "dead zones".

---

### Caso 2: Validar una Estrategia Nueva

**Objetivo:** Analizar si tu estrategia ORB realmente funciona.

**Pasos:**

1. Ve a **Saved Filters**
2. Crea un filtro: `strategy = "ORB"`
3. Ve a **Pivot Grid**
4. Configura:
   - Row: `day_of_week`, `hour_of_day`
   - Metrics: `trade_count`, `win_rate`, `avg_pnl`, `profit_factor`
   - Filter: Aplica tu filtro de ORB
5. Genera el pivot
6. Haz drill-down en las celdas con mejor performance
7. Ve a **AI Pattern Detection**
8. Filtra por strategy: "ORB"
9. Analiza los patrones específicos de ORB

**Resultado esperado:** Entender en qué condiciones ORB funciona mejor.

---

### Caso 3: Crear un Dashboard Personalizado

**Objetivo:** Métricas personalizadas para tu estilo de trading.

**Pasos:**

1. Ve a **Custom Metrics**
2. Crea estas métricas:
   - **R-Multiple:** `pnl / (abs(mae) || 1)`
   - **Win/Loss Ratio:** `avg_win / abs(avg_loss)`
   - **Risk %:** `(quantity * entry_price) / capital * 100`
3. Ve a **Pivot Grid**
4. Configura:
   - Row: `strategy`
   - Metrics: Tus custom metrics + `trade_count`, `win_rate`
5. Guarda esta configuración como preset personalizado

**Resultado esperado:** Dashboard con métricas que realmente importan para ti.

---

### Caso 4: Detectar Revenge Trading

**Objetivo:** Identificar si operas emocionalmente después de pérdidas.

**Pasos:**

1. Ve a **AI Pattern Detection**
2. Ejecuta análisis de últimos 3 meses
3. Revisa **Risk Management Patterns**
4. Busca patrones como "trading after losses"
5. Si la IA detecta revenge trading:
   - Ve a **Saved Filters**
   - Crea filtro: Operaciones después de 2+ pérdidas consecutivas
   - Analiza esas operaciones específicamente

**Resultado esperado:** Cuantificar el impacto del revenge trading y crear reglas para evitarlo.

---

### Caso 5: Optimizar Tamaño de Posición

**Objetivo:** Encontrar el tamaño óptimo de posición para cada estrategia.

**Pasos:**

1. Ve a **Custom Metrics**
2. Crea: **Position Size %:** `(quantity * entry_price) / capital * 100`
3. Ve a **Pivot Grid**
4. Configura:
   - Row: `strategy`, `quantity_range`
   - Metrics: `trade_count`, `win_rate`, `avg_pnl`, tu custom metric
5. Genera el pivot
6. Identifica qué rangos de tamaño tienen mejor performance por estrategia

**Resultado esperado:** Reglas de position sizing basadas en datos reales.

---

## Consejos y Mejores Prácticas

### Custom Metrics

✅ **DO:**
- Empieza con ejemplos predefinidos y modifícalos
- Usa nombres descriptivos
- Añade descripciones para recordar qué mide cada métrica
- Valida siempre antes de guardar
- Usa `|| 1` para evitar división por cero: `pnl / (mae || 1)`

❌ **DON'T:**
- No uses variables que no existen
- No olvides los paréntesis en operaciones complejas
- No uses métricas sin probarlas primero

### Pivot Grid

✅ **DO:**
- Empieza con presets para familiarizarte
- Usa drill-down para validar los números
- Exporta a CSV para análisis más profundos
- Combina dimensiones temporales con dimensiones de estrategia
- Limita a 2-3 dimensiones de fila para claridad

❌ **DON'T:**
- No uses demasiadas dimensiones a la vez (se vuelve confuso)
- No olvides aplicar filtros de fecha relevantes
- No asumas que correlación = causación

### AI Pattern Detection

✅ **DO:**
- Usa al menos 30 días de datos (preferible 3 meses)
- Ejecuta análisis después de cambios importantes en tu trading
- Presta atención a los Top 3 Insights
- Actúa sobre patrones de severidad "High"
- Re-ejecuta mensualmente para ver evolución

❌ **DON'T:**
- No analices períodos muy cortos (<30 días)
- No ignores patrones de severidad "High"
- No ejecutes análisis sin suficientes operaciones (mínimo 20-30)
- No olvides que el cache dura 1 hora

### Saved Filters

✅ **DO:**
- Usa nombres descriptivos
- Empieza con Quick Filters y modifícalos
- Marca como favoritos los que uses frecuentemente
- Combina filtros con custom metrics
- Documenta filtros complejos en la descripción

❌ **DON'T:**
- No crees filtros demasiado específicos (úsalos una vez y olvidas)
- No uses lógica excesivamente compleja
- No olvides validar que el filtro funciona correctamente

---

## Solución de Problemas

### Custom Metrics

**Problema:** "Formula validation failed"

**Solución:**
- Verifica que todas las variables existen (usa el botón "Available Fields")
- Revisa la sintaxis (paréntesis, operadores)
- Usa `|| 1` para evitar división por cero
- Prueba con fórmulas más simples primero

**Problema:** "Metric returns NaN or undefined"

**Solución:**
- Asegúrate de que los campos tienen datos
- Usa valores por defecto: `(campo || 0)`
- Verifica que el tipo de dato sea correcto

---

### Pivot Grid

**Problema:** "No data returned"

**Solución:**
- Verifica que tienes operaciones en el rango de fechas
- Revisa que los filtros no sean demasiado restrictivos
- Asegúrate de haber seleccionado al menos una métrica
- Comprueba que las dimensiones tienen datos

**Problema:** "Table is too large/confusing"

**Solución:**
- Reduce el número de dimensiones
- Usa filtros para limitar el alcance
- Exporta a CSV y analiza en Excel
- Usa drill-down en lugar de ver todo a la vez

---

### AI Pattern Detection

**Problema:** "GEMINI_API_KEY not configured"

**Solución:**
1. Obtén una API key de https://ai.google.dev/
2. Añádela a `.env.local` en `tradetally/backend/`
3. Reinicia el servidor backend
4. Recarga la página

**Problema:** "Analysis takes too long (>2 minutes)"

**Solución:**
- Reduce el rango de fechas
- Aplica filtros para limitar operaciones
- Verifica tu conexión a internet
- Comprueba que no hay límites de rate en tu API key

**Problema:** "AI returns generic/unhelpful patterns"

**Solución:**
- Necesitas más datos (mínimo 30 operaciones)
- Aumenta el rango de fechas
- Asegúrate de tener variedad en tus operaciones
- Verifica que tus datos están completos (no faltan campos)

---

### Saved Filters

**Problema:** "Filter doesn't match expected trades"

**Solución:**
- Revisa la lógica AND/OR
- Verifica los operadores (=, >, <, etc.)
- Comprueba que los valores son correctos (case-sensitive)
- Usa el botón "Validate" antes de guardar

**Problema:** "Can't use custom metrics in filters"

**Solución:**
- Usa el formato: `custom:nombre_metrica`
- Asegúrate de que la métrica existe y está activa
- Verifica que el nombre es exacto (case-sensitive)

---

## Recursos Adicionales

### Documentación Técnica

- [PHASE1_COMPLETION_SUMMARY.md](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/PHASE1_COMPLETION_SUMMARY.md) - Detalles técnicos Fase 1
- [PHASE2_COMPLETION_SUMMARY.md](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/PHASE2_COMPLETION_SUMMARY.md) - Detalles técnicos Fase 2
- [PHASE3_COMPLETION_SUMMARY.md](file:///Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/PHASE3_COMPLETION_SUMMARY.md) - Detalles técnicos Fase 3

### API Endpoints

Si quieres integrar estas funcionalidades programáticamente:

**Custom Metrics:**
- `GET /api/custom-metrics` - Listar métricas
- `POST /api/custom-metrics` - Crear métrica
- `GET /api/custom-metrics/examples` - Ver ejemplos

**Pivot Grid:**
- `POST /api/analytics/pivot` - Generar pivot
- `GET /api/analytics/pivot/presets` - Listar presets
- `POST /api/analytics/pivot/drilldown` - Drill-down

**AI Patterns:**
- `POST /api/analytics/ai-patterns/detect` - Ejecutar análisis
- `GET /api/analytics/ai-patterns/status` - Estado de IA

**Saved Filters:**
- `GET /api/saved-filters` - Listar filtros
- `POST /api/saved-filters` - Crear filtro
- `GET /api/saved-filters/quick` - Quick filters

---

## Próximos Pasos

Ahora que conoces todas las funcionalidades, te recomendamos:

1. **Semana 1:** Familiarízate con Custom Metrics
   - Crea 3-5 métricas relevantes para ti
   - Úsalas en tus análisis diarios

2. **Semana 2:** Domina el Pivot Grid
   - Prueba todos los presets
   - Crea 2-3 configuraciones personalizadas
   - Exporta y analiza en Excel

3. **Semana 3:** Ejecuta AI Pattern Detection
   - Configura tu GEMINI_API_KEY
   - Ejecuta análisis mensual completo
   - Implementa las recomendaciones de severidad "High"

4. **Semana 4:** Optimiza con Saved Filters
   - Crea filtros para tus análisis recurrentes
   - Combina filtros con custom metrics
   - Automatiza tu workflow de análisis

---

## Feedback y Soporte

Si encuentras bugs, tienes sugerencias o necesitas ayuda:

1. Revisa esta guía primero
2. Consulta los archivos de documentación técnica
3. Contacta al equipo de desarrollo

---

**¡Disfruta de tus nuevas superpotencias de análisis! 🚀**

*Última actualización: Noviembre 2025*
