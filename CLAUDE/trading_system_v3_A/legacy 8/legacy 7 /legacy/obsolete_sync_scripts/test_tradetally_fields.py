#!/usr/bin/env python3
"""
Script para probar qué campos acepta la API de TradeTally
y verificar el formato correcto de los payloads
"""

import requests
import json
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradeTallyFieldTester:
    """Clase para probar campos de TradeTally API"""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'X-API-Key': api_key,
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'TradingSystemV3-FieldTest/1.0'
        }

    def test_connection(self):
        """Probar conexión básica"""
        try:
            url = f"{self.base_url}/trades?limit=1"
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code == 200:
                logger.info("✅ Conexión exitosa con TradeTally API")
                return True
            else:
                logger.error(f"❌ Error de conexión: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Error de red: {e}")
            return False

    def test_payload_fields(self):
        """Probar diferentes combinaciones de campos"""

        # Payload base
        base_payload = {
            'symbol': 'TEST',
            'side': 'long',
            'entryTime': datetime.now(timezone.utc).isoformat(),
            'entryPrice': 100.0,
            'quantity': 10,
            'commission': 1.0,
            'strategy': 'test_strategy',
            'broker': 'TEST'
        }

        # Campos a probar
        test_fields = {
            'confidence': 75,
            'context': 'BULLISH',
            'session': 'midday',
            'notes': 'Test trade with all fields'
        }

        logger.info("🔍 Probando campos individuales...")

        for field_name, field_value in test_fields.items():
            test_payload = base_payload.copy()
            test_payload[field_name] = field_value

            logger.info(f"📤 Probando campo: {field_name} = {field_value}")

            try:
                response = requests.post(
                    f"{self.base_url}/trades",
                    headers=self.headers,
                    json=test_payload,
                    timeout=30
                )

                if response.status_code in [200, 201]:
                    logger.info(f"  ✅ Campo '{field_name}' aceptado")
                elif response.status_code == 400:
                    error_data = response.json() if response.text else {}
                    logger.warning(f"  ⚠️ Campo '{field_name}' rechazado: {error_data.get('details', response.text)}")
                else:
                    logger.error(f"  ❌ Error inesperado para '{field_name}': {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"  ❌ Error de red probando '{field_name}': {e}")

    def test_full_payload(self):
        """Probar payload completo con todos los campos"""

        full_payload = {
            'symbol': 'FULL_TEST',
            'side': 'long',
            'entryTime': datetime.now(timezone.utc).isoformat(),
            'entryPrice': 150.0,
            'quantity': 5,
            'commission': 0.5,
            'strategy': 'full_test_strategy',
            'broker': 'TEST_BROKER',
            'confidence': 85,
            'context': 'BEARISH',
            'session': 'power_hour',
            'notes': 'Full test trade with all enhanced fields | Confidence: 85% | Session: power_hour'
        }

        logger.info("🚀 Probando payload completo...")

        try:
            response = requests.post(
                f"{self.base_url}/trades",
                headers=self.headers,
                json=full_payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                logger.info("✅ Payload completo aceptado exitosamente")
                logger.info(f"📊 Respuesta: {response.json() if response.text else 'OK'}")
            elif response.status_code == 400:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ Payload completo rechazado: {error_data}")
                logger.info("🔍 Campos que pueden estar causando problemas:")
                for field in ['confidence', 'context', 'session']:
                    if field in full_payload:
                        logger.info(f"  - {field}: {full_payload[field]}")
            else:
                logger.error(f"❌ Error de servidor: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"❌ Error de red: {e}")

def main():
    """Función principal"""
    import os

    # Configuración
    API_KEY = os.getenv('TRADETALLY_API_KEY')
    BASE_URL = os.getenv('TRADETALLY_BASE_URL')

    if not API_KEY or not BASE_URL:
        print("❌ Variables de entorno requeridas:")
        print("   export TRADETALLY_API_KEY='tu_api_key'")
        print("   export TRADETALLY_BASE_URL='tu_dominio'")
        return

    print("🧪 TRADETALLY FIELD TESTER")
    print("=" * 40)
    print()

    tester = TradeTallyFieldTester(API_KEY, BASE_URL)

    if not tester.test_connection():
        print("❌ No se pudo conectar. Verifica credenciales.")
        return

    print()
    tester.test_payload_fields()

    print()
    tester.test_full_payload()

    print()
    print("📋 RESUMEN:")
    print("   - Si algunos campos son rechazados, pueden no estar soportados por tu versión de TradeTally")
    print("   - Contacta con soporte de TradeTally para confirmar campos disponibles")
    print("   - Los campos aceptados se usarán en futuras sincronizaciones")

if __name__ == "__main__":
    main()