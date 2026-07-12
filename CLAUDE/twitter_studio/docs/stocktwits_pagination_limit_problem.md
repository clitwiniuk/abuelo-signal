# Problema: techo de paginación histórica en Stocktwits para tickers activos

## Contexto

Tenemos un scraper funcional de Stocktwits (`stocktwits_client/client.py` en este
repo) que usa Playwright/patchright con sesión logueada real para superar el
challenge de Cloudflare, e intercepta las respuestas JSON del endpoint interno
`api.stocktwits.com/api/2/streams/symbol/{TICKER}.json?filter=top&limit=22&max={cursor}`.

La paginación hacia atrás en el tiempo se dispara haciendo scroll real de la
página (`window.scrollTo(0, document.body.scrollHeight)`), no llamando a la API
directamente (un `fetch()` manual cross-origin desde la página está bloqueado a
nivel de red aunque las cookies sean válidas).

## El problema

Para **tickers de alto volumen de mensajes** (ej. `NVDA`, `ZCMD`), el scroll
hacia atrás se detiene siempre alrededor de las **mismas ~150-160 mensajes /
~5-6 días de antigüedad**, sin importar la técnica usada. Lo detectamos porque
el `cursor.max` de la respuesta (el cursor de paginación hacia páginas más
antiguas) empieza a **repetirse exactamente** — el feed se reinicia a la
página 1 en vez de seguir avanzando hacia atrás.

Para **tickers de bajo volumen** (ej. `CMD`) esto casi no se nota, porque cada
página de 22 mensajes cubre semanas o meses de calendario en vez de horas, así
que aunque exista el mismo techo de páginas, en la práctica ya se cubre todo
el histórico relevante antes de toparse con él.

## Lo que ya hemos descartado como causa

1. **Publicidad/trackers ralentizando la carga** — cierto, y lo arreglamos
   (bloqueo de dominios + patrones de URL de un vendor de session-replay que
   rota de dominio para evadir blocklists). Bajó la latencia por página de
   ~30-45s a ~4s. Pero **no** es la causa del reinicio — el reinicio ocurre
   igual con la red rápida.

2. **Sesión no autenticada** — cierto que limita a 2 páginas (~44 mensajes)
   para usuarios anónimos, pero **ya estamos autenticados** con cookies
   reales de sesión (login manual + export vía Cookie-Editor), y el techo de
   ~150 mensajes persiste igualmente.

3. **Bug de nuestro propio código: `scroll_into_view_if_needed()` es un
   no-op de Playwright** cuando el elemento ya es visible en el viewport
   (cierto en cualquier feed corto). Esto SÍ era un bug real que arreglamos
   (cambiado a `window.scrollTo` forzado), pero solucionarlo no eliminó el
   techo de ~150 mensajes — solo hizo que llegáramos a él de forma fiable en
   vez de quedarnos atascados en la página 1 sin darnos cuenta.

4. **Rate-limiting por velocidad de scroll** — probado bajando la cadencia de
   scroll de 0.5s a 5s entre páginas. Mismo resultado: se reinicia
   exactamente en el mismo punto (~150 mensajes), solo que tardando más en
   llegar ahí (82.7s en vez de 36.7s). Esto descarta que sea un simple
   rate-limit temporal que ceder velocidad evitaría.

5. **Reintentar tras el reinicio** — implementamos backoff de 4.5s y hasta 6
   reintentos consecutivos tras detectar `cursor.max` repetido. No consigue
   superarlo nunca; siempre se reinicia otra vez.

6. **Filtro alternativo en la UI (tab "Todos" en vez de "Top")** — inspeccionado
   el DOM del feed de mensajes: no existe ningún selector de filtro
   cronológico distinto a `filter=top` en la interfaz. El único botón "All"
   visible en la página pertenece a otro widget (contador de seguidores), no
   al stream de mensajes.

7. **Fingerprint de comportamiento "no humano" en el patrón de scroll** —
   probado con scroll incremental en pasos pequeños (300-700px), pausas
   aleatorias entre 0.4-3.5s, y movimientos de ratón aleatorios antes de cada
   scroll, simulando lectura humana. Resultado: **peor**, no mejor — con este
   patrón ni siquiera llegó a cargar la página 2 en 118 segundos (se quedó
   todo el rato repitiendo la página 1). Esto descarta que el reinicio sea
   una defensa anti-bot basada en fingerprinting de comportamiento de scroll;
   más bien parece que `window.scrollTo` al fondo total del documento es la
   única señal que el frontend realmente escucha para paginar, y los
   micro-scrolls simplemente no la disparan en absoluto.

## Hipótesis pendientes de investigar (no probadas aún)

- **¿Es un límite de páginas por sesión de navegador**, no de tiempo/velocidad?
  Si es así, cerrar y reabrir la página (nueva navegación completa, no solo
  scroll) tras cada N páginas podría "resetear el contador" del lado del
  servidor/cliente y permitir seguir. No lo hemos probado — cada intento hasta
  ahora ha sido dentro de la misma navegación de página sin recargar.
- **¿El propio "live-update" polling del cliente (que refresca cada ~4s la
  página 1) es lo que pisa nuestro avance**, no un límite de páginas en sí?
  Es decir: quizá si consiguiéramos **desactivar o pausar** ese polling de
  actualizaciones en vivo (quizá vinculado a la pestaña estar en foco/visible,
  vía la Page Visibility API — probar `document.visibilityState` oculto o
  poner la pestaña en background), el scroll hacia atrás podría seguir sin
  ser interrumpido por el refresco automático de la parte superior del feed.
- **¿Hay un endpoint de búsqueda/histórico distinto** (no el stream en vivo)
  que permita filtrar por rango de fechas directamente vía parámetros de
  query, en vez de depender de paginación por scroll? No hemos buscado a
  fondo en el código JS del bundle de la SPA de Stocktwits en busca de rutas
  de API alternativas (ej. un endpoint de "archive" o "search" con parámetros
  `since`/`until`).

## Pregunta a resolver

¿Cómo conseguir bajar más de ~150 mensajes / ~5-6 días de histórico en
tickers de alto volumen de Stocktwits, dado que ya descartamos publicidad,
autenticación, velocidad de scroll, reintentos, y patrón de comportamiento de
scroll como causas solucionables desde nuestro lado?
