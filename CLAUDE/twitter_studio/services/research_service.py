"""Research service — lista de X filtrada por palabras clave con anti-ban."""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.logger import logger

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "research_config.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class ResearchConfig:
    listas: list[dict]
    palabras_valor: list[str]
    palabras_ruido: list[str]
    pausa_min_tweets: float
    pausa_max_tweets: float
    pausa_min_ciclos: float
    pausa_max_ciclos: float


def cargar_config() -> ResearchConfig:
    """Lee research_config.json. Lanza excepción si el archivo no existe."""
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    ab = raw.get("anti_ban", {})
    return ResearchConfig(
        listas=raw.get("listas", []),
        palabras_valor=[p.lower() for p in raw.get("palabras_valor", [])],
        palabras_ruido=[p.lower() for p in raw.get("palabras_ruido", [])],
        pausa_min_tweets=ab.get("pausa_min_entre_tweets", 2),
        pausa_max_tweets=ab.get("pausa_max_entre_tweets", 5),
        pausa_min_ciclos=ab.get("pausa_min_entre_ciclos", 60),
        pausa_max_ciclos=ab.get("pausa_max_entre_ciclos", 180),
    )


def guardar_config(cfg: ResearchConfig) -> None:
    """Persiste cambios en palabras_valor / palabras_ruido / listas."""
    raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["palabras_valor"] = cfg.palabras_valor
    raw["palabras_ruido"] = cfg.palabras_ruido
    raw["listas"] = cfg.listas
    _CONFIG_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=4), encoding="utf-8")


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class TweetResearch:
    id: str
    autor: str
    autor_username: str
    texto: str
    fecha: Optional[datetime]
    url: str
    likes: int
    retweets: int
    replies: int
    palabras_encontradas: list[str]


# ---------------------------------------------------------------------------
# Anti-ban
# ---------------------------------------------------------------------------

async def espera_humana(modo: str = "tweet", cfg: Optional[ResearchConfig] = None) -> None:
    """
    Pausa asíncrona con jitter para simular comportamiento humano.

    modo='tweet'  → pausa corta entre lecturas individuales (2–5 s por defecto)
    modo='ciclo'  → pausa larga al terminar un ciclo completo (60–180 s por defecto)
    """
    if cfg is None:
        cfg = cargar_config()

    if modo == "ciclo":
        segundos = random.uniform(cfg.pausa_min_ciclos, cfg.pausa_max_ciclos)
        logger.info(f"[anti-ban] Pausa de ciclo: {segundos:.0f}s")
    else:
        segundos = random.uniform(cfg.pausa_min_tweets, cfg.pausa_max_tweets)
        # Ocasionalmente añade una pausa extra larga (simula distracción)
        if random.random() < 0.1:
            segundos += random.uniform(5, 15)

    await asyncio.sleep(segundos)


# ---------------------------------------------------------------------------
# Filtrado
# ---------------------------------------------------------------------------

def _contiene_valor(texto: str, palabras_valor: list[str]) -> list[str]:
    """Devuelve las palabras de valor encontradas en el texto."""
    texto_lower = texto.lower()
    return [p for p in palabras_valor if p in texto_lower]


def _contiene_ruido(texto: str, palabras_ruido: list[str]) -> bool:
    texto_lower = texto.lower()
    return any(p in texto_lower for p in palabras_ruido)


def filtrar_tweet(texto: str, cfg: ResearchConfig) -> list[str]:
    """
    Aplica el filtro cruzado.
    Devuelve lista de palabras de valor encontradas, o [] si el tweet no pasa.
    """
    if _contiene_ruido(texto, cfg.palabras_ruido):
        return []
    return _contiene_valor(texto, cfg.palabras_valor)


# ---------------------------------------------------------------------------
# Research principal
# ---------------------------------------------------------------------------

async def ejecutar_research(client, list_id: str, max_tweets: int = 100) -> list[TweetResearch]:
    """
    Descarga tweets de una Twitter List y aplica el filtro cruzado.

    Parámetros
    ----------
    client   : instancia de twikit.Client ya autenticada
    list_id  : ID de la lista de X (string numérico)
    max_tweets: máximo de tweets a descargar antes de filtrar

    Retorna
    -------
    Lista de TweetResearch que superan el filtro.

    Uso
    ---
        from services.research_service import ejecutar_research
        resultados = asyncio.run(ejecutar_research(twitter_client._client, "123456789"))
    """
    cfg = cargar_config()
    resultados: list[TweetResearch] = []

    logger.info(f"[research] Iniciando research en lista {list_id} (max {max_tweets} tweets)")

    try:
        tweets = await client.get_list_tweets(list_id=list_id, count=min(max_tweets, 100))
    except Exception as e:
        logger.error(f"[research] Error descargando tweets de lista {list_id}: {e}")
        return []

    collected = list(tweets)

    # Paginar si hace falta
    while len(collected) < max_tweets:
        await espera_humana("tweet", cfg)
        try:
            tweets = await tweets.next()
            if not tweets:
                break
            collected.extend(list(tweets))
        except Exception:
            break

    logger.info(f"[research] {len(collected)} tweets descargados, filtrando...")

    for raw in collected:
        await espera_humana("tweet", cfg)

        texto = getattr(raw, "text", "") or ""
        palabras = filtrar_tweet(texto, cfg)
        if not palabras:
            continue

        author = getattr(raw, "user", None)
        username = str(getattr(author, "screen_name", "")) if author else ""
        tweet_id = str(getattr(raw, "id", ""))

        from email.utils import parsedate_to_datetime
        raw_date = getattr(raw, "created_at", None)
        try:
            fecha = parsedate_to_datetime(str(raw_date)) if raw_date else None
        except Exception:
            fecha = None

        resultados.append(TweetResearch(
            id=tweet_id,
            autor=str(getattr(author, "name", "")) if author else "",
            autor_username=username,
            texto=texto,
            fecha=fecha,
            url=f"https://x.com/{username}/status/{tweet_id}" if username else "",
            likes=int(getattr(raw, "favorite_count", 0) or 0),
            retweets=int(getattr(raw, "retweet_count", 0) or 0),
            replies=int(getattr(raw, "reply_count", 0) or 0),
            palabras_encontradas=palabras,
        ))

    logger.info(f"[research] {len(resultados)} tweets pasaron el filtro")
    return resultados
