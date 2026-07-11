# Objetivo

Añadir a `twitter_studio` un módulo de investigación de Stocktwits, análogo a `twikit_client/` (que ya existe para X), que permita consultar el histórico de mensajes de cualquier ticker, almacenarlo localmente y buscarlo por fecha, usuario, sentimiento y palabra clave.

Es una **extensión del proyecto existente**, no un proyecto nuevo. Debe seguir las convenciones ya establecidas en `twitter_studio/` (estructura de `models/`, `services/`, `database/`, `auth/`, `config/`) en vez de introducir una arquitectura paralela.

Contexto técnico verificado: la API pública de Stocktwits (`api.stocktwits.com/api/2/streams/symbol/{ticker}.json`) está detrás de Cloudflare (challenge JS, 403 a peticiones directas). No es viable con `requests`/`httpx` simple. Sí es viable con Playwright: la página web de Stocktwits llama a esa misma API internamente vía `fetch`, así que en vez de parsear el DOM/HTML, hay que **interceptar las respuestas JSON de red** con `page.on("response")` mientras se hace scroll. Esto da datos ya estructurados (sentiment, likes, timestamps, user) sin fragilidad de parsing de HTML.

---

# Tecnologías

* Python 3.12+ (mismo entorno que `twitter_studio`)
* Playwright (headless), usado solo como "navegador para pasar Cloudflare + disparar la API interna", no para parsear HTML
* SQLite, reusando/extendiendo el esquema de `database/` si aplica
* Pydantic para validar las respuestas JSON de la API interna
* Typer para CLI (si `twitter_studio` ya tiene una CLI, añadir subcomandos ahí en vez de crear una nueva)
* pytest
* Logging estructurado consistente con el resto del proyecto

Se deja fuera del alcance inicial (evaluar solo si hace falta más adelante): FastAPI, Docker, PostgreSQL, exportación a Parquet/Markdown, nube de palabras, rotación de user-agent, migraciones a otras webs, LLM hooks explícitos. No forman parte del objetivo mínimo y no deben condicionar la arquitectura de la Fase 1.

---

# Arquitectura

Ubicar el nuevo código en `twitter_studio/stocktwits_client/`, con la misma responsabilidad única por módulo que ya usa `twikit_client/`:

```
stocktwits_client/
    client.py          # arranque de Playwright, login/sesión, navegación
    api_interceptor.py # captura y valida las respuestas JSON de red
    models/             # o reusar/extender models/ existente (tweet.py -> post.py, etc.)
    ...
```

Antes de escribir código, inspecciona `twikit_client/client.py`, `models/tweet.py`, `models/user.py` y `services/tweet_service.py` para replicar el mismo estilo (naming, manejo de sesión, forma de exponer datos a `services/`).

---

# Funcionalidades

## 1. Descarga histórica

* `download TSLA`
* `download NVDA --from 2024-01-01`
* `download RKLB --from 2024-01-01 --to 2024-06-01`

## 2. Navegación e interceptación

* Abrir la página del ticker en Playwright, esperar a pasar el challenge de Cloudflare
* Interceptar vía `page.on("response")` las llamadas a `api.stocktwits.com/api/2/streams/symbol/*.json` y parsear el JSON directamente (no el HTML)
* Hacer scroll para disparar la paginación (Stocktwits pagina por `max`/cursor id en la propia respuesta JSON — usar ese cursor para pedir directamente vía `page.evaluate(fetch(...))` cuando sea posible, en vez de depender solo del scroll)
* Deduplicar por `id` de mensaje
* Reintentos con backoff si Cloudflare vuelve a interponerse; esperas dinámicas (esperar a que aparezca la respuesta de red, no `sleep` fijo)
* Checkpoint de progreso para poder reanudar una descarga larga tras fallo

## 3. Parser / normalización

Del JSON de la API (no de HTML) extraer y normalizar:
id, ticker(s), usuario, fecha, texto, likes, replies, sentimiento (Bullish/Bearish/None), enlaces, imágenes, cashtags, menciones.

## 4. Base de datos

Evaluar primero si el esquema de `database/` existente puede extenderse (tabla `messages` estilo `tweets` con `source='stocktwits'`) antes de crear tablas nuevas paralelas. Índices por ticker, fecha, usuario. Upsert sin duplicados por `id`.

## 5. CLI

Subcomandos en la CLI existente si la hay: `stock download NVDA`, `stock sync TSLA`, `stock search NVDA earnings`, `stock stats RKLB`.

## 6. Antibloqueo (solo lo necesario para Cloudflare, no full stealth suite)

* Persistencia de sesión/cookies tras pasar el challenge una vez (reusar patrón de `auth/`/`cookies/` que ya existe en el proyecto para X)
* Esperas aleatorias entre requests para no gatillar rate-limit
* Nada de rotación de user-agent ni fingerprinting avanzado salvo que el challenge lo exija en la práctica

---

# Desarrollo por fases (con tu validación entre cada una)

1. Inspección del código existente (`twikit_client`, `models`, `services`, `database`) y propuesta concreta de dónde encaja cada pieza nueva
2. Cliente Playwright: abrir ticker, pasar Cloudflare, capturar una respuesta de red de ejemplo
3. Parser/validación Pydantic del JSON capturado
4. Persistencia (reusar o extender esquema existente)
5. Scroll + paginación + dedupe + checkpoint/reanudación
6. CLI (`download`, `sync`, `search`, `stats`)
7. Tests (mockeando las respuestas de red, no la web real)
8. (Opcional, solo si se necesita) exportación, API HTTP, análisis estadístico

---

# Estado (implementado 2026-07-11)

Fases 2–7 completas. Módulo funcional: `stocktwits_client/`, `models/stocktwits_post.py`,
`services/stocktwits_service.py`, `pages/stocktwits.py`, tabla `DBStocktwitsPost` (PK compuesta
`id+ticker`, porque un mismo mensaje puede llevar varios cashtags y aparecer en el stream de
más de un ticker), 14 tests en `tests/`.

**Hallazgos técnicos que cambiaron el plan original:**
- Playwright estándar no pasa el challenge de Cloudflare (fingerprint de automatización). Se usa
  `patchright` (drop-in) lanzando el canal `chrome` real, no el Chromium de testing.
- **Solo funciona con `headless=False`** (ventana visible). En todas las pruebas, `headless=True`
  se quedó bloqueado indefinidamente en el challenge.
- El `fetch()` cross-origin manual (`page.evaluate`) a `api.stocktwits.com` está bloqueado a nivel
  de red aunque las cookies sean válidas. La paginación solo funciona interceptando las respuestas
  reales que dispara la propia web al hacer scroll (`page.mouse.wheel` + cursor `max` de la respuesta).

**Pendiente para despliegue desatendido (servidor sin pantalla):**
Necesitaría `Xvfb` — pero eso solo aplica a Linux (framebuffer X11); no sirve en este Mac de
desarrollo, donde Chrome es una app nativa Cocoa. No se ha probado todavía porque no hay un
servidor Linux ni Docker disponible en este entorno. Antes de automatizar la descarga en
background/cron, verificar en un contenedor/VM Linux real que Chrome bajo Xvfb supera el
challenge igual que con ventana visible en macOS — no está garantizado, ya que Cloudflare puede
usar otras señales además de la presencia de ventana.

En cada fase entrega solo el código de esa fase, explicación técnica breve y sus tests. No avances de fase sin validación.
