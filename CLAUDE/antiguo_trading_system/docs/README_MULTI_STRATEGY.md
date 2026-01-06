# Sistema de Trading Multi-Estrategia

## Descripción
Este sistema permite ejecutar múltiples estrategias de trading simultáneamente, cada una con sus propios símbolos asignados. El sistema está diseñado para minimizar los cambios en el código existente y mantener un rendimiento óptimo.

## Características principales
- Soporte para múltiples estrategias ejecutándose en paralelo
- Asignación independiente de símbolos a cada estrategia
- Resolución automática de conflictos entre órdenes de diferentes estrategias
- Interfaz gráfica con Streamlit para gestionar estrategias y símbolos
- Monitoreo de posiciones y estadísticas por estrategia

## Arquitectura
El sistema se basa en tres componentes principales:

1. **MultiStrategyManager**: Actúa como una fachada que implementa la interfaz `IStrategy` y gestiona múltiples estrategias internamente.
   - Distribuye barras de datos y actualizaciones de posición a las estrategias correspondientes
   - Recopila señales de trading de todas las estrategias
   - Resuelve conflictos entre señales contradictorias
   - Etiqueta cada señal con metadatos de la estrategia que la generó

2. **MultiStrategySystemManager**: Reemplaza al `TradingSystemManager` original para soportar múltiples estrategias.
   - Inicializa y gestiona el `MultiStrategyManager`
   - Administra la adición/eliminación de estrategias y símbolos
   - Controla el ciclo de vida del sistema (inicio/parada)
   - Proporciona métodos para integración con Streamlit

3. **Interfaz Streamlit**: Proporciona una interfaz gráfica para gestionar el sistema.
   - Añadir/eliminar estrategias
   - Asignar/eliminar símbolos por estrategia
   - Monitorear posiciones y estadísticas
   - Controlar el estado del sistema

## Resolución de conflictos
El sistema implementa un mecanismo para resolver conflictos entre señales de diferentes estrategias:

1. Si todas las señales son del mismo lado (compra o venta), se procesan en orden cronológico.
2. Si hay señales contradictorias (compra y venta):
   - Se priorizan las señales de venta (salida) sobre las de compra (entrada).
   - Entre señales del mismo tipo, se elige la más reciente.
   - Se registra la decisión tomada en los logs.

## Uso
### Iniciar el sistema
```bash
cd /ruta/al/proyecto
streamlit run streamlit_app_multi.py
```

### Añadir una estrategia
1. En la pestaña "Estrategias", expande "Añadir Nueva Estrategia"
2. Selecciona una estrategia de la lista desplegable
3. Haz clic en "Añadir Estrategia"

### Asignar símbolos a una estrategia
1. En la tarjeta de la estrategia, introduce el símbolo en el campo "Nuevo símbolo"
2. Haz clic en "Añadir Símbolo"

### Iniciar el trading
1. En la barra lateral, haz clic en "Iniciar Sistema"
2. El sistema comenzará a monitorear los símbolos asignados a cada estrategia

## Consideraciones de rendimiento
- El sistema está diseñado para minimizar la duplicación de datos y procesamiento.
- Cada símbolo se procesa una sola vez, independientemente de cuántas estrategias lo utilicen.
- El uso de memoria aumenta linealmente con el número de estrategias y símbolos.
- Se recomienda monitorear el rendimiento al ejecutar más de 5 estrategias simultáneamente.

## Limitaciones
- Las estrategias no pueden comunicarse entre sí directamente.
- La resolución de conflictos prioriza la seguridad (salidas) sobre las oportunidades (entradas).
- El sistema no implementa actualmente un mecanismo de prioridad personalizable por estrategia.
