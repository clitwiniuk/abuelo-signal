# IBKR Streamlit Trading App (Unificado)

Este proyecto integra una app de trading en Streamlit con la lógica robusta de la librería Interactive-Brokers-Trading-Bot-master, todo en un solo directorio para facilitar el desarrollo y la gestión de dependencias.

---

## Estructura del Proyecto

```
/conexion_IBKR
├── app.py               # Interfaz principal en Streamlit
├── ib_client.py         # Wrapper para conexión y órdenes usando IBTB
├── ibw/                 # Lógica de conexión y API Client Portal
├── robot/               # Portfolio, Trader, lógica de órdenes, etc.
├── config/
│   └── config.ini       # Tus credenciales IBKR
├── write_config.py      # Script para generar config.ini
└── README.md            # (Este archivo)
```

---

## 1. Requisitos
- Python 3.7+
- Java instalado (para Client Portal Gateway de IBKR)
- Cuenta de Interactive Brokers

---

## 2. Configuración Inicial

1. **Crea tu archivo de configuración:**
   
   Ejecuta:
   ```sh
   python write_config.py
   ```
   Luego edita `config/config.ini` con tus credenciales reales.

2. **(Opcional) Crea un entorno virtual:**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt  # Si lo tienes, o instala streamlit y pandas
   ```

---

## 3. Ejecutar la App

Desde la carpeta `/conexion_IBKR`:

```sh
streamlit run app.py
```

- Ingresa tu usuario y cuenta IBKR en la barra lateral.
- Pulsa "Conectar IBKR".
- Consulta datos de cuenta, precios y lanza órdenes desde la interfaz.

---

## 4. Personalización y Desarrollo
- Puedes modificar la lógica de conexión y trading en `ib_client.py`.
- Puedes extender la interfaz visual en `app.py`.
- Si necesitas más funcionalidades, revisa y usa las clases en `ibw/` y `robot/`.

---

## 5. Notas y Consejos
- **No necesitas TWS**: El sistema usa Client Portal Gateway, que se lanza automáticamente.
- Si tienes problemas de conexión, revisa tu archivo `config.ini` y asegúrate de que Java esté instalado.
- Para desarrollo, tener todo en un solo directorio facilita la gestión y pruebas.

---

## 6. Créditos
- Basado en [Interactive-Brokers-Trading-Bot-master](https://github.com/Vincentho711/Interactive-Brokers-Trading-Bot)
- Adaptado e integrado para uso en Streamlit por [Tu Nombre]
