# 📚 DOCUMENTACIÓN DEL SISTEMA DE TRADING

Esta carpeta contiene toda la documentación del sistema de trading automatizado, incluyendo la nueva **documentación del sistema híbrido de producción para smallcaps intraday**.

---

## 🚀 DOCUMENTACIÓN DE PRODUCCIÓN (NUEVA)

### Sistema Híbrido Smallcaps Intraday
- **[QUICK_START_PRODUCTION.md](QUICK_START_PRODUCTION.md)** - 🚀 Inicio rápido en 5 minutos
- **[OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md)** - 📋 Manual completo de operaciones
- **[HYBRID_PRODUCTION_ARCHITECTURE.md](HYBRID_PRODUCTION_ARCHITECTURE.md)** - 🏗️ Arquitectura del sistema híbrido

**Características del Sistema Híbrido:**
- ✅ **Aprovecha tu config.ini existente al 100%** - Sin duplicar configuración
- ✅ **Solo agrega extensiones necesarias** para producción (Tiingo, alertas, monitoreo)
- ✅ **Integra todos los componentes existentes** (IBKRAdapter, SmallcapMayordomo, ML Engine)
- ✅ **Optimizado para smallcaps intraday** ($1-$15, gaps >10%, volumen >500K)

---

## 📖 DOCUMENTACIÓN EXISTENTE

### Configuración y Setup
- **[README_DOCS.md](README_DOCS.md)** - Documentación general del sistema
- **[CONFIGURAR_SIMBOLOS.md](CONFIGURAR_SIMBOLOS.md)** - Configuración de símbolos para trading
- **[COMO_EJECUTAR_MOCK.md](COMO_EJECUTAR_MOCK.md)** - Guía para ejecutar el modo mock/simulación

### Arquitectura y Desarrollo
- **[HYBRID_ARCHITECTURE_GUIDE.md](HYBRID_ARCHITECTURE_GUIDE.md)** - Guía de arquitectura híbrida (legacy)
- **[ENHANCED_DATA_MANAGEMENT_INTEGRATION.md](ENHANCED_DATA_MANAGEMENT_INTEGRATION.md)** - Integración de gestión de datos mejorada
- **[ESTRUCTURA_ORGANIZADA.md](ESTRUCTURA_ORGANIZADA.md)** - Estructura organizada del proyecto
- **[REORGANIZACION_COMPLETADA.md](REORGANIZACION_COMPLETADA.md)** - Información sobre reorganización
- **[THREAD_SAFE_ADAPTER_README.md](THREAD_SAFE_ADAPTER_README.md)** - Adaptador thread-safe para IBKR

### Trading y Estrategias
- **[README_MULTI_STRATEGY.md](README_MULTI_STRATEGY.md)** - Sistema de estrategias múltiples
- **[strategy_selection.md](strategy_selection.md)** - Selección automática de estrategias
- **[gap_go_procedure_guide.md](gap_go_procedure_guide.md)** - Procedimientos para estrategia Gap Go
- **[SIMULATION_GUIDE.md](SIMULATION_GUIDE.md)** - Guía completa de simulación

### APIs e Integraciones
- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - Documentación de APIs del sistema
- **[TRADETALLY_INTEGRATION_GUIDE.md](TRADETALLY_INTEGRATION_GUIDE.md)** - Integración con TradeTally
- **[propuesta_mejoras.txt](propuesta_mejoras.txt)** - Propuestas de mejoras del sistema

---

## 📁 SUBDIRECTORIOS ESPECIALIZADOS

### integrations/
Documentación específica de integraciones externas:
- **[TRADETALLY_EQUITY_AUTOMATION.md](integrations/TRADETALLY_EQUITY_AUTOMATION.md)** - Automatización de equity tracking
- **[TRADETALLY_ORGANIZATION.md](integrations/TRADETALLY_ORGANIZATION.md)** - Organización del sistema TradeTally

### learning_system/
Documentación del sistema de aprendizaje ML:
- **[README.md](learning_system/README.md)** - Introducción al sistema de aprendizaje
- **[ARCHITECTURE.md](learning_system/ARCHITECTURE.md)** - Arquitectura del sistema ML
- **[QUICK_REFERENCE.md](learning_system/QUICK_REFERENCE.md)** - Referencia rápida
- **[STREAMLIT_SETUP.md](learning_system/STREAMLIT_SETUP.md)** - Setup de interfaces Streamlit
- **[TIMING_GUIDE.md](learning_system/TIMING_GUIDE.md)** - Guía de timing para ML

---

## 🎯 GUÍAS RECOMENDADAS POR USO

### Para Nuevos Usuarios:
1. **[QUICK_START_PRODUCTION.md](QUICK_START_PRODUCTION.md)** - Comenzar aquí
2. **[README_DOCS.md](README_DOCS.md)** - Entender el sistema general
3. **[CONFIGURAR_SIMBOLOS.md](CONFIGURAR_SIMBOLOS.md)** - Configurar símbolos

### Para Deployment en Producción:
1. **[QUICK_START_PRODUCTION.md](QUICK_START_PRODUCTION.md)** - Setup rápido
2. **[OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md)** - Manual operativo completo
3. **[HYBRID_PRODUCTION_ARCHITECTURE.md](HYBRID_PRODUCTION_ARCHITECTURE.md)** - Entender la arquitectura

### Para Desarrollo:
1. **[HYBRID_PRODUCTION_ARCHITECTURE.md](HYBRID_PRODUCTION_ARCHITECTURE.md)** - Arquitectura del sistema
2. **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - APIs disponibles
3. **[learning_system/ARCHITECTURE.md](learning_system/ARCHITECTURE.md)** - Sistema ML

### Para Trading Específico:
1. **[README_MULTI_STRATEGY.md](README_MULTI_STRATEGY.md)** - Estrategias disponibles
2. **[strategy_selection.md](strategy_selection.md)** - Selección automática
3. **[gap_go_procedure_guide.md](gap_go_procedure_guide.md)** - Gap Go específico

---

## 🔄 ESTADO DE LA DOCUMENTACIÓN

### ✅ Actualizada y Vigente:
- Sistema híbrido de producción
- Manual de operaciones
- Arquitectura de producción
- Quick start guides

### 📋 Legacy (Referencia):
- Guías de arquitectura antiguas
- Documentación de componentes específicos
- Procedimientos de desarrollo históricos

---

**📈 Para trading smallcaps intraday en producción, comienza con [QUICK_START_PRODUCTION.md](QUICK_START_PRODUCTION.md)**
