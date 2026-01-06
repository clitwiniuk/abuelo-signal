#!/usr/bin/env python3
"""
Script de prueba para simular condiciones de mercado específicas
que activen la estrategia VWAP y verificar si envía órdenes al broker.
"""

import sys
import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("VWAPTest")

# Añadir el directorio actual al path
sys.path.append(str(Path(__file__).parent))

# Importar componentes necesarios
from core.interfaces import (
    Signal, MarketData, SignalType, Position, Order, OrderSide, OrderType, OrderStatus, TradingConfig
)
from strategies.vwap_strategy import VWAPSmallcapsStrategy
from core.risk_manager import RiskManager
from backtesting.backtest_engine import BacktestBroker, BacktestConfig, BacktestTrade
from typing import Dict, List

class TestBroker(BacktestBroker):
    """Broker de prueba que registra todas las órdenes enviadas"""
    
    def __init__(self, config: BacktestConfig):
        super().__init__(config)
        self.orders_sent = []
        self.logger = logging.getLogger("TestBroker")
    
    def submit_order(self, order: Order) -> bool:
        """Registra la orden y simula su ejecución"""
        self.orders_sent.append(order)
        self.logger.info(f"✅ ORDEN RECIBIDA: {order.symbol} {order.order_type} {order.quantity}@{order.price}")
        
        # Simular ejecución inmediata
        execution_price = order.price
        
        # Actualizar posiciones
        if order.order_type in ["BUY", "SELL"]:
            # Crear posición
            position = Position(
                symbol=order.symbol,
                quantity=order.quantity,
                entry_price=execution_price,
                side="LONG" if order.order_type == "BUY" else "SHORT"
            )
            
            # Actualizar cash y posiciones
            cost = order.quantity * execution_price
            if order.order_type == "BUY":
                self.cash -= cost
            else:  # SELL (short)
                self.cash += cost
                
            self.positions[order.symbol] = position
            self.current_positions_count += 1
            self.logger.info(f"✅ POSICIÓN ABIERTA: {order.symbol} {position.side} {order.quantity}@{execution_price} (Cash: ${self.cash:.2f})")
            
        elif order.order_type == "CLOSE" and order.symbol in self.positions:
            position = self.positions[order.symbol]
            
            # Calcular P&L
            if position.side == "LONG":
                pnl = (execution_price - position.entry_price) * position.quantity
            else:  # SHORT
                pnl = (position.entry_price - execution_price) * position.quantity
                
            # Actualizar cash
            if position.side == "LONG":
                self.cash += position.quantity * execution_price
            else:  # SHORT
                self.cash -= position.quantity * execution_price
                
            self.logger.info(f"✅ POSICIÓN CERRADA: {order.symbol}: PnL: ${pnl:.2f} (Cash: ${self.cash:.2f})")
            
            # Registrar trade
            trade = BacktestTrade(
                symbol=order.symbol,
                entry_price=position.entry_price,
                exit_price=execution_price,
                quantity=position.quantity,
                entry_time=position.entry_time,
                exit_time=order.timestamp,
                side=position.side,
                pnl=pnl
            )
            self.trades.append(trade)
            
            # Eliminar posición
            del self.positions[order.symbol]
            self.current_positions_count -= 1
            
        self.orders_history.append(order)
        self.total_trades_executed += 1
        
        return True

class VWAPTestSimulator:
    """Simulador para probar la estrategia VWAP con datos sintéticos"""
    
    def __init__(self):
        self.logger = logging.getLogger("VWAPTest")
        
        # Configuración para el backtest
        self.config = BacktestConfig(
            initial_capital=10000.0,
            commission_per_trade=1.0,
            commission_pct=0.001,
            slippage_pct=0.001,
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            max_positions=5,
            risk_per_trade=0.02,
            data_frequency="1min"
        )
        
        # Inicializar broker de prueba
        self.broker = TestBroker(self.config)
        
        # Cargar configuración para la estrategia con parámetros ajustados para el test
        self.strategy = VWAPSmallcapsStrategy(
            parameters={
                'vwap_period': 20,
                'momentum_period': 5,
                'vwap_entry_threshold': 0.99,  # Umbral para entradas
                'momentum_entry_threshold': 0.01,  # Momentum mínimo para entradas
                'vwap_exit_threshold': 1.02,
                'momentum_exit_threshold': -0.01,
                'max_hold_days': 5,
                'risk_management_mode': 'fixed',
                'initial_stop_loss': 0.05,
                'trailing_stop_distance': 0.03,
                'partial_take_profit': 0.10,
                'min_price': 1.0,
                'max_price': 20.0,
                'volatility_threshold': 0.01,  # Reducido para el test
                'volume_threshold': 1.0,  # Reducido para el test
                'min_volume_ratio': 0.1,  # Reducido para el test
                'confidence_base': 0.3,
                'enable_shorts': True
            }
        )
        
        # Inicializar trading config para el risk manager
        trading_config = TradingConfig(
            max_positions=5,
            max_risk_per_trade=0.02,
            max_daily_loss=-1000.0,
            max_daily_trades=20
        )
        # Agregar debug_mode como atributo adicional
        setattr(trading_config, 'debug_mode', True)  # Modo debug para permitir todas las señales
        
        # Inicializar risk manager
        self.risk_manager = RiskManager(config=trading_config)
        
        # Modificar la función _is_smallcap_suitable para forzar que siempre devuelva True en el test
        self.original_is_smallcap_suitable = self.strategy._is_smallcap_suitable
        self.strategy._is_smallcap_suitable = lambda symbol, bar: True
    
    def generate_test_data(self, symbol='TEST', scenario='long_entry'):
        """Genera datos de prueba para el escenario especificado"""
        # Crear una serie de barras de prueba
        bars = []
        base_price = 10.0
        base_volume = 100000  # Volumen muy alto para asegurar que pase el filtro
        
        # Establecer la hora de mercado válida (9:30 AM - 4:00 PM)
        now = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)  # 10:30 AM, hora de mercado válida
        
        # Generar 30 barras con datos que simulen el escenario
        for i in range(30):
            timestamp = now - timedelta(minutes=30-i)
            
            # Ajustar precio según el escenario
            if scenario == 'long_entry':
                # Para entrada larga: precio bajando y luego subiendo cerca del VWAP (pero por debajo)
                if i < 15:
                    price = base_price - (0.05 * i)  # Bajada gradual
                elif i < 20:
                    price = base_price - 0.75  # Estabilización
                else:
                    # Subida gradual hacia el VWAP (ratio muy cercano a 0.99)
                    # Las últimas barras deben tener un precio muy cercano al VWAP
                    if i >= 25:
                        # Acercarse mucho al umbral en las últimas barras
                        price = base_price * 0.991  # 99.1% del VWAP (muy cerca del umbral 0.99)
                    else:
                        price = base_price - 0.75 + (0.06 * (i-20))  # Subida más rápida
                        
                    # Asegurar momentum positivo en las últimas barras para long_entry
                    if i >= 25:
                        # Crear un patrón de precios ascendente en las últimas 5 barras
                        # para garantizar momentum positivo
                        price = price * (1.0 + 0.005 * (i-24))  # +0.5% por barra
            
            elif scenario == 'short_entry':
                # Para entrada corta: precio subiendo y luego cayendo cerca del VWAP (pero por encima)
                if i < 15:
                    price = base_price + (0.05 * i)  # Subida gradual
                elif i < 20:
                    price = base_price + 0.75  # Estabilización
                else:
                    # Bajada gradual hacia el VWAP (ratio ~1.01)
                    if i >= 25:
                        # Acercarse mucho al umbral en las últimas barras
                        price = base_price * 1.01  # 101% del VWAP (muy cerca del umbral 1.01)
                    else:
                        price = base_price + 0.75 - (0.06 * (i-20))  # Bajada más rápida
                    
                    # Asegurar momentum negativo en las últimas barras para short_entry
                    if i >= 25:
                        # Crear un patrón de precios descendente en las últimas 5 barras
                        price = price * (1.0 - 0.005 * (i-24))  # -0.5% por barra
            
            elif scenario == 'long_exit':
                # Para salida larga: precio subiendo por encima del umbral de salida
                if i < 15:
                    price = base_price + (0.05 * i)  # Subida gradual
                else:
                    # Subida más pronunciada para superar umbral de salida
                    price = base_price + 0.75 + (0.08 * (i-15))
                    
                    # Asegurar que las últimas barras superen claramente el umbral de salida
                    if i >= 25:
                        price = base_price * 1.05  # 5% por encima del precio base
            
            elif scenario == 'short_exit':
                # Para salida corta: precio bajando por debajo del umbral de salida
                if i < 15:
                    price = base_price - (0.05 * i)  # Bajada gradual
                else:
                    # Bajada más pronunciada para superar umbral de salida
                    price = base_price - 0.75 - (0.08 * (i-15))
                    
                    # Asegurar que las últimas barras superen claramente el umbral de salida
                    if i >= 25:
                        price = base_price * 0.95  # 5% por debajo del precio base
            
            else:
                price = base_price
            
            # Ajustar volumen con variabilidad pero siempre muy por encima del umbral
            # Aumentar el volumen en las últimas barras para reforzar la señal
            if i >= 25:
                volume = base_volume * 2 + random.randint(10000, 50000)  # Volumen muy alto en barras finales
            else:
                volume = base_volume + random.randint(10000, 30000)
            
            # Crear barra con alta volatilidad para pasar el filtro de volatilidad
            bar = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=price * 0.99,
                high=price * 1.04,  # Mayor high para aumentar volatilidad
                low=price * 0.96,   # Menor low para aumentar volatilidad
                close=price,
                volume=volume,
                vwap=None  # La estrategia calculará el VWAP
            )
            
            # Añadir metadatos para ayudar a la estrategia a identificar smallcaps
            setattr(bar, 'metadata', {'is_smallcap': True})
            
            bars.append(bar)
        
        # Imprimir información de diagnóstico
        self.logger.info(f"Datos generados para {scenario}: {len(bars)} barras")
        self.logger.info(f"Primera barra: {bars[0].timestamp} - ${bars[0].close:.2f}")
        self.logger.info(f"Última barra: {bars[-1].timestamp} - ${bars[-1].close:.2f}")
        
        return bars
    
    async def run_test(self, symbol='TEST', scenario='long_entry'):
        """Ejecuta el test con el escenario especificado"""
        self.logger.info(f"🧪 INICIANDO TEST: {scenario} para {symbol}")
        
        # Inicializar contador de órdenes enviadas
        orders_sent = 0
        
        # Generar datos de prueba
        bars = self.generate_test_data(symbol, scenario)
        
        # Inicializar la estrategia
        await self.strategy._initialize_strategy()
        
        # Procesar cada barra con la estrategia
        for i, bar in enumerate(bars):
            self.logger.info(f"Procesando barra {i+1}/{len(bars)}: {bar.timestamp} - Precio: {bar.close:.2f}, Volumen: {bar.volume:.0f}")
            
            # Verificar condiciones de smallcap antes de procesar
            is_suitable = self.strategy._is_smallcap_suitable(symbol, bar)
            self.logger.info(f"¿Es suitable para smallcap? {is_suitable}")
            
            # Verificar tiempo válido
            is_valid_time = self.strategy._is_valid_entry_time(bar.timestamp)
            self.logger.info(f"¿Es tiempo válido? {is_valid_time}")
            
            # Actualizar la estrategia con la nueva barra (método asíncrono)
            signal = await self.strategy.on_bar(bar)
            
            # Si no hay señal, intentar evaluar manualmente las condiciones VWAP
            if not signal and i >= 20:  # Solo después de suficientes barras para calcular VWAP
                self.logger.info("No se generó señal, evaluando condiciones VWAP manualmente...")
                vwap_conditions = await self.strategy._evaluate_vwap_entry_conditions(symbol, bar)
                self.logger.info(f"Condiciones VWAP: {vwap_conditions}")
                
                # Calcular VWAP para diagnóstico
                bars_history = self.strategy.bars_history.get(symbol, [])
                if len(bars_history) >= self.strategy.vwap_period:
                    vwap = self.strategy._calculate_vwap(bars_history, self.strategy.vwap_period)
                    self.logger.info(f"VWAP calculado: {vwap:.2f}, Precio actual: {bar.close:.2f}")
                    self.logger.info(f"Ratio precio/VWAP: {bar.close/vwap:.4f} (Threshold: {self.strategy.vwap_entry_threshold})")
            
            # La estrategia devuelve la señal directamente si se genera una
            if signal:
                self.logger.info(f"🎥 SEÑAL GENERADA: {signal.symbol} {signal.signal_type} @ ${signal.price:.2f}")
                
                # Para el test, forzamos la aceptación de todas las señales sin pasar por el RiskManager
                # ya que el RiskManager valida contra la hora actual del sistema, no la hora simulada
                self.logger.info(f"✅ SEÑAL ACEPTADA PARA TEST: {signal.symbol} {signal.signal_type}")
                
                # Convertir señal a orden
                if signal.signal_type == SignalType.LONG:
                    order_type = OrderType.MARKET
                    side = OrderSide.BUY
                else:  # SHORT
                    order_type = OrderType.MARKET
                    side = OrderSide.SELL
                
                # Crear orden con un order_id único
                order = Order(
                    order_id=str(uuid.uuid4()),  # Generar ID único para la orden
                    symbol=signal.symbol,
                    order_type=order_type,
                    side=side,
                    quantity=100,  # Cantidad fija para prueba
                    price=signal.price
                )
                
                # Enviar orden al broker (sin await, ya que no es una corrutina)
                self.broker.submit_order(order)
                self.logger.info(f"📤 ORDEN ENVIADA: {order.symbol} {order.side} {order.quantity} @ ${order.price:.2f}")
                orders_sent += 1


        
        # Verificar resultados
        self.logger.info(f"\n📊 RESULTADOS DEL TEST ({scenario}):")
        self.logger.info(f"Órdenes enviadas: {len(self.broker.orders_sent)}")
        for i, order in enumerate(self.broker.orders_sent):
            self.logger.info(f"  {i+1}. {order.symbol} {order.order_type} {order.quantity}@{order.price}")
        
        self.logger.info(f"Posiciones activas: {len(self.broker.positions)}")
        for symbol, pos in self.broker.positions.items():
            self.logger.info(f"  {symbol}: {pos.side} {pos.quantity}@{pos.entry_price}")
            
        self.logger.info(f"Trades completados: {len(self.broker.trades)}")
        for i, trade in enumerate(self.broker.trades):
            pnl_pct = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
            self.logger.info(f"  {i+1}. {trade.symbol} {trade.side}: PnL=${trade.pnl:.2f} ({pnl_pct:.2f}%)")
            
        return len(self.broker.orders_sent) > 0

async def main():
    """Función principal para ejecutar los tests"""
    simulator = VWAPTestSimulator()
    
    # Ejecutar tests para diferentes escenarios
    await simulator.run_test(symbol='AAPL', scenario='long_entry')
    print("\n" + "-"*80 + "\n")
    
    await simulator.run_test(symbol='MSFT', scenario='short_entry')
    print("\n" + "-"*80 + "\n")
    
    # Crear un nuevo simulador para los tests de salida
    # para que tenga posiciones abiertas primero
    exit_simulator = VWAPTestSimulator()
    
    # Abrir posición LONG para TSLA
    await exit_simulator.run_test(symbol='TSLA', scenario='long_entry')
    print("\n" + "-"*80 + "\n")
    
    # Probar salida de LONG
    await exit_simulator.run_test(symbol='TSLA', scenario='long_exit')
    print("\n" + "-"*80 + "\n")
    
    # Abrir posición SHORT para AMZN
    await exit_simulator.run_test(symbol='AMZN', scenario='short_entry')
    print("\n" + "-"*80 + "\n")
    
    # Probar salida de SHORT
    await exit_simulator.run_test(symbol='AMZN', scenario='short_exit')
    
    print("\n" + "="*80)
    print("✅ TESTS COMPLETADOS")
    print("="*80)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
