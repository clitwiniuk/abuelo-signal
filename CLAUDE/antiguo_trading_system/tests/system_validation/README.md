# System Validation Tests

Tests progresivos para verificar que el sistema unificado funciona correctamente.

## 📋 Tests Disponibles

### 1. `test_unified_components.py`
**Test básico de componentes**
- Verifica que todos los servicios se inicializan correctamente
- Comprueba Service Locator, IBKR Adapter, Telegram Client, Scanner
- No requiere conexiones reales - solo verificación de inicialización

```bash
python tests/system_validation/test_unified_components.py
```

### 2. `test_scanner_mock.py` 
**Test del scanner con datos simulados**
- Prueba funcionalidad completa del SmallcapDailyScanner
- Usa datos mock pero procesos reales (news fetching, ML analysis)
- Verifica filtros de calidad, catalyst analysis, FinBERT integration

```bash
python tests/system_validation/test_scanner_mock.py
```

### 3. `test_notifications.py`
**Test del sistema de notificaciones inteligentes**
- Prueba filtros anti-spam y cooldown
- Verifica detección de cambios significativos
- Testea formato de mensajes de Telegram

```bash
python tests/system_validation/test_notifications.py
```

### 4. `test_integration_final.py`
**Test de integración end-to-end**
- Simula múltiples ciclos de scanning completos
- Prueba el flujo completo: Scanner → Filtros → Notificaciones
- Verifica manejo de errores y robustez del sistema

```bash
python tests/system_validation/test_integration_final.py
```

### 5. `test_sistema_final.py` ⭐
**Test final de validación del sistema**
- Verificación completa de que el sistema está listo para producción
- Comprueba todas las interfaces críticas
- Valida configuración y architecture

```bash
python tests/system_validation/test_sistema_final.py
```

## 🚀 Ejecutar Todos los Tests

Para ejecutar toda la suite de validación:

```bash
cd tests/system_validation
python test_unified_components.py && python test_scanner_mock.py && python test_notifications.py && python test_sistema_final.py
```

## ✅ Resultados Esperados

Todos los tests deben completarse exitosamente con:
- ✅ Componentes inicializados correctamente
- ✅ Scanner funcional con datos mock
- ✅ Sistema de notificaciones operativo
- ✅ Integración end-to-end funcionando
- ✅ Sistema validado para producción

## 📝 Notas

- Estos tests **no requieren IBKR real** conectado
- Usan mocks y datos simulados para testing seguro
- Validan la arquitectura y lógica sin riesgos de trading
- Son tests de **pre-producción** - ejecutar antes de `python main.py`

## 🔧 Troubleshooting

Si algún test falla:
1. Verificar que todas las dependencias estén instaladas
2. Comprobar config.ini está correctamente configurado
3. Asegurar que no hay conflictos de imports
4. Revisar logs para detalles específicos del error