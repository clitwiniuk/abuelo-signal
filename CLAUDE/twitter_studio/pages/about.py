"""About page."""

import streamlit as st


def render() -> None:
    st.markdown("## ℹ️ Acerca de Twitter Studio")
    st.markdown("---")

    st.markdown(
        """
        **Twitter Studio** es una plataforma de inteligencia para X (Twitter),
        orientada al análisis, monitorización y exportación de datos públicos.

        ---

        ### Funcionalidades
        - Login con cookies persistentes via Twikit
        - Búsqueda avanzada con filtros (idioma, fechas, media, verificados...)
        - Análisis de perfiles: métricas, estadísticas, palabras frecuentes
        - Monitor de palabras clave con histórico en SQLite
        - Exportación CSV / Excel
        - Gráficas interactivas (Plotly)
        - Análisis de sentimiento (TextBlob)
        - Viewer de logs en tiempo real

        ---

        ### Tecnologías
        | Componente | Tecnología |
        |------------|-----------|
        | Frontend | Streamlit |
        | Cliente X | Twikit |
        | Base de datos | SQLite + SQLAlchemy |
        | Modelos | Pydantic v2 |
        | Visualización | Plotly |
        | Logging | Loguru |
        | Sentimiento | TextBlob |

        ---

        ### Aviso legal
        Esta herramienta es exclusivamente de **consulta y análisis**.
        No publica, responde ni modifica contenido en X.
        Úsala respetando los [Términos de servicio de X](https://x.com/en/tos).

        ---

        **Versión:** 1.0.0
        """
    )
