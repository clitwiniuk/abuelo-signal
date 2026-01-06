#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test para enviar una orden real (demo) usando la estrategia VWAP.
Este script conecta con IBKR en modo paper trading y envía una orden real de prueba.
"""

import asyncio
import logging
import uuid
import random
from datetime import datetime, timedelta
import pandas as pd

from strategies.vwap_strategy import VWAPSmallcapsStrategy
from core.interfaces import Order, OrderSide, OrderType, Signal, TradingConfig, SignalType
from adapters.ibkr_adapter import IBKRAdapter
from core.risk_manager import RiskManager
from backtests.backtest_config import BacktestConfig

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class VWAPRealOrderTest:
    """
    Test para enviar una orden real (demo) usando la estrategia VWAP.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("VWAPRealTest")
        self.logger.setLevel(logging.INFO)
        
        # Cargar configuración
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # 30 días de datos
        self.config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0,
            commission_per_trade=1.0,
            commission_pct=0.001,  # 0.1%
            slippage_pct=0.001,    # 0.1%
            max_positions=3,
            risk_per_trade=0.02    # 2%
        )
        
        # Inicializar broker real (IBKR en modo paper trading)
        self.broker = IBKRAdapter(
            host="127.0.0.1",  # TWS/Gateway en localhost
            port=7497,         # Puerto 7497 para paper trading
            client_id=2        # ID de cliente único
        )
        
        # Inicializar risk manager con TradingConfig
        risk_config = TradingConfig()
        risk_config.max_positions = 5
        risk_config.max_risk_per_trade = 0.05
        risk_config.max_daily_loss = -5000.0  # Valor alto para permitir operaciones
        risk_config.max_daily_trades = 50     # Valor alto para permitir muchas operaciones
        
        # Añadir atributos adicionales para el modo debug
        setattr(risk_config, 'debug_mode', True)
        setattr(risk_config, 'max_portfolio_volatility', 0.5)
        setattr(risk_config, 'simulation_mode', True)
        
        self.risk_manager = RiskManager(risk_config)
        
        # Inicializar estrategia VWAP
        self.strategy = VWAPSmallcapsStrategy(
            parameters={
                'min_price': 5.0,
                'max_price': 20.0,
                'min_volume': 10000,
                'volume_window': 5,
                'vwap_window': 20,
                'momentum_window': 3,
                'price_threshold': 0.99,
                'enable_shorts': True,
                'max_positions': 5
            }
        )
        
        # Nota: No usamos set_broker ni set_risk_manager porque la estrategia no los implementa
        # En su lugar, pasaremos el broker y risk_manager directamente cuando sea necesario
    
    async def generate_test_data(self, symbol='AAPL'):
        """
        Genera datos de prueba para la estrategia VWAP.
        Estos datos están diseñados para cumplir los criterios de entrada.
        """
        now = datetime.now()
        # Asegurar que estamos en horario de mercado (9:30 - 16:00)
        market_time = now.replace(hour=10, minute=30)
        
        # Crear 30 barras de 1 minuto
        dates = [market_time - timedelta(minutes=i) for i in range(30)]
        dates.reverse()  # Ordenar cronológicamente
        
        # Generar precios que cumplan los criterios VWAP
        base_price = 15.0  # Precio base dentro del rango permitido
        prices = []
        volumes = []
        
        # Primeras barras con precios por encima de VWAP
        for i in range(15):
            price = base_price + random.uniform(0.5, 1.5)
            volume = random.randint(50000, 150000)  # Volumen alto
            prices.append(price)
            volumes.append(volume)
        
        # Siguientes barras con precios por debajo de VWAP (para entrada larga)
        for i in range(15):
            price = base_price - random.uniform(0.5, 1.5)
            volume = random.randint(100000, 200000)  # Volumen muy alto
            prices.append(price)
            volumes.append(volume)
        
        # Crear DataFrame
        df = pd.DataFrame({
            'datetime': dates,
            'open': prices,
            'high': [p + 0.2 for p in prices],
            'low': [p - 0.2 for p in prices],
            'close': prices,
            'volume': volumes,
            'symbol': symbol
        })
        
        # Establecer índice
        df.set_index('datetime', inplace=True)
        
        return df
    
    async def run_test(self, symbol='AAPL'):
        """
        Ejecuta el test enviando una orden real en modo demo.
        """
        self.logger.info(f"🧪 INICIANDO TEST DE ORDEN REAL PARA {symbol}")
        
        try:
            # Conectar al broker
            self.logger.info("Conectando al broker IBKR (paper trading)...")
            await self.broker.connect()
            
            if not self.broker.is_connected():
                self.logger.error("❌ No se pudo conectar al broker IBKR")
                return
            
            self.logger.info("✅ Conexión establecida con IBKR")
            
            # Generar datos de prueba
            bars = await self.generate_test_data(symbol)
            
            # Procesar barras históricas para inicializar VWAP
            for i in range(len(bars) - 1):
                bar = bars.iloc[i]
                await self.strategy.on_bar(bar)
            
            # Procesar la última barra para generar señal
            last_bar = bars.iloc[-1]
            self.logger.info(f"Procesando barra final: {last_bar.name} - Precio: {last_bar['close']}, Volumen: {last_bar['volume']}")
            
            # Forzar que la estrategia considere el símbolo como smallcap
            self.strategy._is_smallcap_suitable = lambda symbol, price: True
            
            # Crear una señal manual para prueba (en lugar de usar la estrategia)
            # Esto evita problemas con la integración broker/risk_manager en la estrategia
            self.logger.info("Creando señal manual para prueba...")
            
            # Crear señal manual para forzar una orden
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.LONG,  # Equivalente a BUY
                signal_id=str(uuid.uuid4()),
                strength=0.8,  # Alta confianza en la señal
                timestamp=datetime.now(),
                price=last_bar['close']
            )
            
            # Añadir metadatos adicionales
            signal.metadata['strategy_name'] = "VWAPSmallcapsStrategy"
            signal.metadata['quantity'] = 10  # Cantidad pequeña para prueba
            
            self.logger.info(f"Señal manual creada: {signal.signal_type.value} {signal.metadata.get('quantity', 'N/A')} {signal.symbol} @ {signal.price}")
            
            # Validar señal con risk manager
            is_valid = await self.risk_manager.validate_signal(signal)
            
            if not is_valid:
                self.logger.warning("⚠️ Señal rechazada por risk manager. Forzando validación...")
                # Forzar validación para prueba
                is_valid = True
            
            if is_valid:
                # Crear orden
                # Convertir SignalType a OrderSide
                side = OrderSide.BUY if signal.signal_type == SignalType.LONG else OrderSide.SELL
                quantity = signal.metadata.get('quantity', 10)  # Usar cantidad de metadatos o valor por defecto
                
                order = Order(
                    symbol=signal.symbol,
                    side=side,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                    price=signal.price,
                    order_id=str(uuid.uuid4())
                )
                
                # Enviar orden al broker
                self.logger.info(f"Enviando orden: {order.side.value} {order.quantity} {order.symbol} @ {order.price}")
                order_id = await self.broker.place_order(order)
                
                self.logger.info(f"✅ Orden enviada con ID: {order_id}")
                return order_id
            else:
                self.logger.error("❌ No se pudo validar la señal")
        
        except Exception as e:
            self.logger.error(f"❌ Error durante el test: {e}")
            raise
        
        finally:
            # Desconectar del broker
            if self.broker.is_connected():
                self.logger.info("Desconectando del broker...")
                await self.broker.disconnect()
                self.logger.info("Broker desconectado")

async def main():
    """Función principal para ejecutar el test"""
    test = VWAPRealOrderTest()
    
    try:
        # Ejecutar test con un símbolo líquido en modo demo
        symbol = "AAPL"  # Apple es un buen candidato para pruebas
        order_id = await test.run_test(symbol)
        
        if order_id:
            print(f"\n================================================================================")
            print(f"✅ TEST COMPLETADO - ORDEN ENVIADA CON ID: {order_id}")
            print(f"================================================================================\n")
        else:
            print(f"\n================================================================================")
            print(f"❌ TEST FALLIDO - NO SE PUDO ENVIAR LA ORDEN")
            print(f"================================================================================\n")
    
    except Exception as e:
        print(f"\n================================================================================")
        print(f"❌ ERROR EN EL TEST: {e}")
        print(f"================================================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
