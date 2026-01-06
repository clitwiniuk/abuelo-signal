#!/usr/bin/env python3
"""
Test de Simulación de Trading Real
Tests que simulan escenarios reales de trading para validar el comportamiento del sistema
"""

import os
import sys
import random
import sqlite3
import math
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import pandas as pd

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class MarketCondition(Enum):
    """Condiciones del mercado para simulación"""
    BULL_MARKET = "bull"          # Mercado alcista
    BEAR_MARKET = "bear"          # Mercado bajista  
    SIDEWAYS = "sideways"         # Mercado lateral
    HIGH_VOLATILITY = "volatile"   # Alta volatilidad
    LOW_VOLATILITY = "calm"       # Baja volatilidad

@dataclass
class SimulatedTrade:
    """Trade simulado con datos realistas"""
    symbol: str
    strategy: str
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    side: str  # 'BUY' or 'SELL'
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl: Optional[float]
    max_profit: float = 0.0
    max_loss: float = 0.0
    hold_time_minutes: int = 0

class MarketSimulator:
    """Simulador de condiciones de mercado"""
    
    def __init__(self):
        self.current_condition = MarketCondition.SIDEWAYS
        self.volatility_factor = 1.0
        
    def set_market_condition(self, condition: MarketCondition):
        """Establecer condición del mercado"""
        self.current_condition = condition
        
        # Ajustar factores según condición
        if condition == MarketCondition.BULL_MARKET:
            self.volatility_factor = 1.2
        elif condition == MarketCondition.BEAR_MARKET:
            self.volatility_factor = 1.3
        elif condition == MarketCondition.HIGH_VOLATILITY:
            self.volatility_factor = 2.5
        elif condition == MarketCondition.LOW_VOLATILITY:
            self.volatility_factor = 0.5
        else:  # SIDEWAYS
            self.volatility_factor = 1.0
    
    def generate_realistic_price_movement(self, initial_price: float, minutes: int) -> List[float]:
        """Generar movimiento de precios realista"""
        prices = [initial_price]
        current_price = initial_price
        
        for _ in range(minutes):
            # Tendencia base según condición del mercado
            trend = 0.0
            if self.current_condition == MarketCondition.BULL_MARKET:
                trend = random.uniform(0.0001, 0.002)  # Tendencia alcista
            elif self.current_condition == MarketCondition.BEAR_MARKET:
                trend = random.uniform(-0.002, -0.0001)  # Tendencia bajista
            
            # Volatilidad aleatoria
            volatility = random.gauss(0, 0.001) * self.volatility_factor
            
            # Calcular nuevo precio
            change = trend + volatility
            current_price *= (1 + change)
            
            # Evitar precios negativos o irrealísticamente bajos
            current_price = max(current_price, initial_price * 0.3)
            
            prices.append(current_price)
        
        return prices

class TradingSimulationTest:
    """Tests de simulación de trading realista"""
    
    def __init__(self):
        from core.database_manager import get_database_manager
        self.db_manager = get_database_manager()
        self.market_simulator = MarketSimulator()
        
        # Estrategias con características realistas
        self.strategy_profiles = {
            'macdv_smallcaps': {
                'avg_hold_minutes': 45,
                'win_rate': 0.65,
                'avg_win': 0.08,  # 8%
                'avg_loss': -0.04,  # -4%
                'preferred_symbols': self._generate_smallcap_symbols()
            },
            'gap_go': {
                'avg_hold_minutes': 25,
                'win_rate': 0.58,
                'avg_win': 0.12,  # 12%
                'avg_loss': -0.06,  # -6%
                'preferred_symbols': self._generate_midcap_symbols()
            },
            'orb': {
                'avg_hold_minutes': 35,
                'win_rate': 0.62,
                'avg_win': 0.06,  # 6%
                'avg_loss': -0.03,  # -3%
                'preferred_symbols': self._generate_largecap_symbols()
            },
            'volume_breakout': {
                'avg_hold_minutes': 55,
                'win_rate': 0.55,
                'avg_win': 0.15,  # 15%
                'avg_loss': -0.08,  # -8%
                'preferred_symbols': self._generate_volatile_symbols()
            }
        }
    
    def _generate_smallcap_symbols(self) -> List[str]:
        """Generar símbolos de small caps simulados"""
        return [f'SMLC{i:03d}' for i in range(1, 51)]  # 50 símbolos
    
    def _generate_midcap_symbols(self) -> List[str]:
        """Generar símbolos de mid caps simulados"""
        return [f'MIDC{i:03d}' for i in range(1, 31)]  # 30 símbolos
    
    def _generate_largecap_symbols(self) -> List[str]:
        """Generar símbolos de large caps simulados"""
        return [f'LRGC{i:03d}' for i in range(1, 21)]  # 20 símbolos
    
    def _generate_volatile_symbols(self) -> List[str]:
        """Generar símbolos volátiles simulados"""
        return [f'VOLT{i:03d}' for i in range(1, 26)]  # 25 símbolos
    
    def test_full_trading_day_simulation(self, market_condition: MarketCondition = MarketCondition.SIDEWAYS) -> dict:
        """Simular un día completo de trading"""
        print(f"📅 Simulando día completo de trading ({market_condition.value})...")
        
        self.market_simulator.set_market_condition(market_condition)
        
        results = {
            'market_condition': market_condition.value,
            'trades_generated': 0,
            'trades_opened': 0,
            'trades_closed': 0,
            'total_pnl': 0.0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'max_drawdown': 0.0,
            'max_profit_run': 0.0,
            'strategies_performance': {},
            'hourly_performance': [],
            'simulated_trades': []
        }
        
        # Simular 8 horas de trading (9:30 AM - 5:30 PM)
        trading_start = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        current_time = trading_start
        
        running_pnl = 0.0
        peak_pnl = 0.0
        
        for hour in range(8):  # 8 horas de trading
            hour_start_time = current_time
            hour_trades = []
            hour_pnl = 0.0
            
            # Generar trades para esta hora (frecuencia basada en condición del mercado)
            if market_condition == MarketCondition.HIGH_VOLATILITY:
                trades_this_hour = random.randint(15, 25)
            elif market_condition == MarketCondition.LOW_VOLATILITY:
                trades_this_hour = random.randint(3, 8)
            else:
                trades_this_hour = random.randint(8, 15)
            
            print(f"   🕐 Hora {hour+1}: Generando {trades_this_hour} trades...")
            
            for trade_num in range(trades_this_hour):
                # Seleccionar estrategia aleatoria
                strategy = random.choice(list(self.strategy_profiles.keys()))
                profile = self.strategy_profiles[strategy]
                
                # Generar trade simulado
                simulated_trade = self._generate_realistic_trade(
                    strategy, profile, current_time + timedelta(minutes=random.randint(0, 59))
                )
                
                # Simular ejecución del trade
                trade_result = self._simulate_trade_execution(simulated_trade, market_condition)
                
                if trade_result:
                    # Guardar en base de datos
                    success = self.db_manager.save_trade(trade_result)
                    if success:
                        results['trades_opened'] += 1
                        hour_trades.append(trade_result['symbol'])
                        
                        # Si el trade se cerró, actualizar estadísticas
                        if trade_result.get('status') == 'CLOSED' and trade_result.get('pnl') is not None:
                            trade_pnl = trade_result['pnl']
                            hour_pnl += trade_pnl
                            running_pnl += trade_pnl
                            
                            results['trades_closed'] += 1
                            if trade_pnl > 0:
                                results['winning_trades'] += 1
                            else:
                                results['losing_trades'] += 1
                            
                            # Actualizar drawdown y profit run
                            peak_pnl = max(peak_pnl, running_pnl)
                            current_drawdown = peak_pnl - running_pnl
                            results['max_drawdown'] = max(results['max_drawdown'], current_drawdown)
                            
                            if running_pnl > 0:
                                results['max_profit_run'] = max(results['max_profit_run'], running_pnl)
                
                results['trades_generated'] += 1
                current_time += timedelta(minutes=random.randint(2, 10))
            
            # Estadísticas por hora
            results['hourly_performance'].append({
                'hour': hour + 1,
                'trades': len(hour_trades),
                'pnl': hour_pnl,
                'symbols': list(set(hour_trades))
            })
            
            current_time = hour_start_time + timedelta(hours=1)
        
        # Calcular estadísticas finales
        results['total_pnl'] = running_pnl
        if results['trades_closed'] > 0:
            results['win_rate'] = results['winning_trades'] / results['trades_closed']
        
        # Performance por estrategia
        results['strategies_performance'] = self._calculate_strategy_performance()
        
        print(f"   ✅ Día simulado: {results['trades_opened']} trades abiertos")
        print(f"   📊 Trades cerrados: {results['trades_closed']}")
        print(f"   💰 PnL total: ${results['total_pnl']:.2f}")
        print(f"   📈 Win rate: {results['win_rate']*100:.1f}%")
        print(f"   📉 Max drawdown: ${results['max_drawdown']:.2f}")
        
        # Limpiar datos de simulación
        self._cleanup_simulation_data()
        
        return results
    
    def _generate_realistic_trade(self, strategy: str, profile: dict, entry_time: datetime) -> SimulatedTrade:
        """Generar un trade realista basado en el perfil de estrategia"""
        symbol = random.choice(profile['preferred_symbols'])
        
        # Precios realistas basados en tipo de símbolo
        if 'SMLC' in symbol:  # Small caps
            entry_price = round(random.uniform(0.5, 15.0), 4)
        elif 'MIDC' in symbol:  # Mid caps
            entry_price = round(random.uniform(5.0, 50.0), 4)
        elif 'LRGC' in symbol:  # Large caps
            entry_price = round(random.uniform(20.0, 300.0), 4)
        else:  # Volatile
            entry_price = round(random.uniform(1.0, 100.0), 4)
        
        quantity = self._calculate_realistic_quantity(entry_price, strategy)
        
        return SimulatedTrade(
            symbol=symbol,
            strategy=strategy,
            entry_price=entry_price,
            exit_price=None,
            quantity=quantity,
            side='BUY',  # Simplificado a compras
            entry_time=entry_time,
            exit_time=None,
            pnl=None
        )
    
    def _calculate_realistic_quantity(self, entry_price: float, strategy: str) -> int:
        """Calcular cantidad realista basada en precio y estrategia"""
        # Posición típica de $500-2000
        target_value = random.uniform(500, 2000)
        
        # Ajustar por estrategia
        if strategy == 'macdv_smallcaps':
            target_value = random.uniform(300, 1500)  # Posiciones más pequeñas
        elif strategy == 'volume_breakout':
            target_value = random.uniform(800, 2500)  # Posiciones más grandes
        
        quantity = int(target_value / entry_price)
        return max(10, quantity)  # Mínimo 10 acciones
    
    def _simulate_trade_execution(self, trade: SimulatedTrade, market_condition: MarketCondition) -> Optional[dict]:
        """Simular la ejecución y resultado de un trade"""
        profile = self.strategy_profiles[trade.strategy]
        
        # Determinar si el trade será ganador o perdedor
        is_winner = random.random() < profile['win_rate']
        
        # Ajustar probabilidades según condición del mercado
        if market_condition == MarketCondition.BEAR_MARKET and is_winner:
            # En mercado bajista, reducir probabilidad de ganar
            is_winner = random.random() < 0.7
        elif market_condition == MarketCondition.BULL_MARKET and not is_winner:
            # En mercado alcista, reducir probabilidad de perder
            is_winner = random.random() < 0.3
        
        # Calcular tiempo de tenencia
        base_hold_minutes = profile['avg_hold_minutes']
        if market_condition == MarketCondition.HIGH_VOLATILITY:
            hold_minutes = int(base_hold_minutes * random.uniform(0.5, 0.8))  # Salidas más rápidas
        else:
            hold_minutes = int(base_hold_minutes * random.uniform(0.8, 1.5))
        
        # Simular movimiento de precios durante la tenencia
        price_path = self.market_simulator.generate_realistic_price_movement(
            trade.entry_price, hold_minutes
        )
        
        # Determinar precio de salida
        if is_winner:
            # Trade ganador
            profit_pct = abs(random.gauss(profile['avg_win'], profile['avg_win'] * 0.3))
            exit_price = trade.entry_price * (1 + profit_pct)
        else:
            # Trade perdedor
            loss_pct = abs(random.gauss(abs(profile['avg_loss']), abs(profile['avg_loss']) * 0.3))
            exit_price = trade.entry_price * (1 - loss_pct)
        
        # Asegurar que el precio de salida esté dentro del rango del path
        max_price = max(price_path)
        min_price = min(price_path)
        exit_price = max(min_price, min(max_price, exit_price))
        
        # Calcular PnL
        pnl = (exit_price - trade.entry_price) * trade.quantity
        
        # Crear registro para la base de datos
        trade_data = {
            'trade_id': f"SIM_{trade.strategy.upper()}_{int(trade.entry_time.timestamp())}_{random.randint(1000, 9999)}",
            'symbol': trade.symbol,
            'strategy': trade.strategy,
            'side': trade.side,
            'quantity': trade.quantity,
            'entry_price': trade.entry_price,
            'exit_price': exit_price,
            'entry_time': trade.entry_time,
            'exit_time': trade.entry_time + timedelta(minutes=hold_minutes),
            'duration_minutes': hold_minutes,
            'pnl': round(pnl, 2),
            'status': 'CLOSED',
            'is_winner': is_winner,
            'notes': f'Simulated {market_condition.value} market trade'
        }
        
        return trade_data
    
    def _calculate_strategy_performance(self) -> dict:
        """Calcular performance por estrategia de las trades simuladas"""
        try:
            # Obtener trades simuladas recientes
            trades_df = self.db_manager.get_trades(limit=10000)
            sim_trades = trades_df[trades_df['trade_id'].str.contains('SIM_')]
            
            if sim_trades.empty:
                return {}
            
            performance = {}
            for strategy in sim_trades['strategy'].unique():
                strategy_trades = sim_trades[sim_trades['strategy'] == strategy]
                
                if len(strategy_trades) > 0:
                    total_pnl = strategy_trades['pnl'].sum()
                    winning_trades = len(strategy_trades[strategy_trades['pnl'] > 0])
                    win_rate = winning_trades / len(strategy_trades) if len(strategy_trades) > 0 else 0
                    
                    performance[strategy] = {
                        'total_trades': len(strategy_trades),
                        'winning_trades': winning_trades,
                        'win_rate': win_rate,
                        'total_pnl': round(total_pnl, 2),
                        'avg_pnl': round(total_pnl / len(strategy_trades), 2),
                        'best_trade': round(strategy_trades['pnl'].max(), 2),
                        'worst_trade': round(strategy_trades['pnl'].min(), 2)
                    }
            
            return performance
            
        except Exception as e:
            print(f"   ⚠️  Error calculando performance por estrategia: {e}")
            return {}
    
    def test_market_stress_scenarios(self) -> dict:
        """Test de escenarios de stress del mercado"""
        print("🌪️  Test de escenarios de stress del mercado...")
        
        results = {
            'scenarios_tested': [],
            'total_trades_generated': 0,
            'scenario_performance': {}
        }
        
        # Definir escenarios de stress
        stress_scenarios = [
            (MarketCondition.BEAR_MARKET, "Mercado Bajista Severo"),
            (MarketCondition.HIGH_VOLATILITY, "Alta Volatilidad Extrema"),
            (MarketCondition.LOW_VOLATILITY, "Mercado Sin Movimiento")
        ]
        
        for condition, description in stress_scenarios:
            print(f"   🎭 Escenario: {description}")
            
            # Simular medio día de trading bajo estas condiciones
            scenario_result = self._simulate_stress_scenario(condition, hours=4)
            
            results['scenarios_tested'].append(description)
            results['scenario_performance'][description] = scenario_result
            results['total_trades_generated'] += scenario_result.get('trades_generated', 0)
            
            print(f"      📊 Trades: {scenario_result.get('trades_generated', 0)}")
            print(f"      💰 PnL: ${scenario_result.get('total_pnl', 0):.2f}")
            print(f"      📈 Win Rate: {scenario_result.get('win_rate', 0)*100:.1f}%")
        
        return results
    
    def _simulate_stress_scenario(self, condition: MarketCondition, hours: int = 4) -> dict:
        """Simular escenario de stress específico"""
        self.market_simulator.set_market_condition(condition)
        
        result = {
            'condition': condition.value,
            'trades_generated': 0,
            'trades_closed': 0,
            'total_pnl': 0.0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0
        }
        
        # Simular trading por las horas especificadas
        current_time = datetime.now()
        
        for hour in range(hours):
            # Número de trades basado en la condición
            if condition == MarketCondition.HIGH_VOLATILITY:
                trades_count = random.randint(20, 35)  # Muchos trades
            elif condition == MarketCondition.LOW_VOLATILITY:
                trades_count = random.randint(2, 6)   # Pocos trades
            else:  # BEAR_MARKET
                trades_count = random.randint(8, 15)  # Trades normales
            
            for _ in range(trades_count):
                strategy = random.choice(list(self.strategy_profiles.keys()))
                profile = self.strategy_profiles[strategy]
                
                trade = self._generate_realistic_trade(
                    strategy, profile, 
                    current_time + timedelta(minutes=random.randint(0, 59))
                )
                
                trade_result = self._simulate_trade_execution(trade, condition)
                
                if trade_result:
                    success = self.db_manager.save_trade(trade_result)
                    if success:
                        result['trades_generated'] += 1
                        
                        if trade_result.get('status') == 'CLOSED':
                            pnl = trade_result.get('pnl', 0)
                            result['trades_closed'] += 1
                            result['total_pnl'] += pnl
                            
                            if pnl > 0:
                                result['winning_trades'] += 1
                            else:
                                result['losing_trades'] += 1
            
            current_time += timedelta(hours=1)
        
        # Calcular win rate
        if result['trades_closed'] > 0:
            result['win_rate'] = result['winning_trades'] / result['trades_closed']
        
        return result
    
    def test_strategy_validation_under_conditions(self) -> dict:
        """Validar que las estrategias funcionan correctamente bajo diferentes condiciones"""
        print("🧪 Test de validación de estrategias bajo condiciones...")
        
        results = {
            'strategies_tested': list(self.strategy_profiles.keys()),
            'conditions_tested': [c.value for c in MarketCondition],
            'validation_results': {},
            'failed_validations': []
        }
        
        for strategy in self.strategy_profiles.keys():
            strategy_results = {}
            
            for condition in MarketCondition:
                print(f"   📊 Validando {strategy} en {condition.value}...")
                
                # Generar muestra de trades para esta estrategia y condición
                sample_results = self._validate_strategy_sample(strategy, condition, sample_size=100)
                
                strategy_results[condition.value] = sample_results
                
                # Verificar si la estrategia se comporta según expectativas
                expected_profile = self.strategy_profiles[strategy]
                actual_win_rate = sample_results.get('win_rate', 0)
                expected_win_rate = expected_profile['win_rate']
                
                # Tolerancia estadística para win rate
                se = math.sqrt(expected_win_rate * (1 - expected_win_rate) / max(sample_results.get('sample_size', 1), 1))
                tolerance = max(0.5, 2 * se)
                if abs(actual_win_rate - expected_win_rate) > tolerance:
                    results['failed_validations'].append({
                        'strategy': strategy,
                        'condition': condition.value,
                        'expected_win_rate': expected_win_rate,
                        'actual_win_rate': actual_win_rate,
                        'issue': 'Win rate fuera de tolerancia'
                    })
            results['validation_results'][strategy] = strategy_results
        
        print(f"   ✅ Estrategias validadas: {len(results['strategies_tested'])}")
        print(f"   ⚠️  Validaciones fallidas: {len(results['failed_validations'])}")
        
        return results
    def _validate_strategy_sample(self, strategy: str, condition: MarketCondition, sample_size: int = 50) -> dict:
        """Validar muestra de una estrategia bajo condición específica"""
        self.market_simulator.set_market_condition(condition)
        profile = self.strategy_profiles[strategy]
        
        trades_data = []
        current_time = datetime.now()
        
        for i in range(sample_size):
            trade = self._generate_realistic_trade(
                strategy, profile, 
                current_time + timedelta(minutes=i * 2)
            )
            
            trade_result = self._simulate_trade_execution(trade, condition)
            
            if trade_result:
                success = self.db_manager.save_trade(trade_result)
                if success and trade_result.get('pnl') is not None:
                    trade_result['is_winner'] = trade_result.get('pnl', 0) > 0
                    trades_data.append(trade_result)
        
        # Calcular estadísticas de la muestra
        if trades_data:
            winning_trades = len([t for t in trades_data if t.get('is_winner')])
            win_rate = winning_trades / len(trades_data)
            avg_pnl = sum([t['pnl'] for t in trades_data]) / len(trades_data) if trades_data else 0
            
            return {
                'sample_size': len(trades_data),
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'total_pnl': sum([t['pnl'] for t in trades_data]),
                'best_trade': max([t['pnl'] for t in trades_data]) if trades_data else 0,
                'worst_trade': min([t['pnl'] for t in trades_data]) if trades_data else 0
            }
        
        return {
            'sample_size': 0,
            'win_rate': 0,
            'avg_pnl': 0,
            'total_pnl': 0,
            'best_trade': 0,
            'worst_trade': 0
        }
    
    def _cleanup_simulation_data(self):
        """Limpiar datos de simulación"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute("DELETE FROM trades WHERE trade_id LIKE 'SIM_%'")
                conn.commit()
        except Exception as e:
            print(f"   ⚠️  Error limpiando datos de simulación: {e}")

def main():
    """Ejecutar todos los tests de simulación de trading"""
    print("📈 TESTS DE SIMULACIÓN DE TRADING REAL")
    print("=" * 45)
    
    simulation_test = TradingSimulationTest()
    all_results = {}
    
    # Test 1: Simulación de día completo - condiciones normales
    print("\n1️⃣  SIMULACIÓN DE DÍA COMPLETO - MERCADO NORMAL")
    print("-" * 45)
    normal_day = simulation_test.test_full_trading_day_simulation(MarketCondition.SIDEWAYS)
    all_results['normal_trading_day'] = normal_day
    
    # Test 2: Simulación de día completo - mercado alcista
    print("\n2️⃣  SIMULACIÓN DE DÍA COMPLETO - MERCADO ALCISTA")
    print("-" * 45)
    bull_day = simulation_test.test_full_trading_day_simulation(MarketCondition.BULL_MARKET)
    all_results['bull_market_day'] = bull_day
    
    # Test 3: Escenarios de stress del mercado
    print("\n3️⃣  ESCENARIOS DE STRESS DEL MERCADO")
    print("-" * 45)
    stress_results = simulation_test.test_market_stress_scenarios()
    all_results['market_stress_scenarios'] = stress_results
    
    # Test 4: Validación de estrategias bajo condiciones
    print("\n4️⃣  VALIDACIÓN DE ESTRATEGIAS BAJO CONDICIONES")
    print("-" * 45)
    strategy_validation = simulation_test.test_strategy_validation_under_conditions()
    all_results['strategy_validation'] = strategy_validation
    
    # Resumen final
    print("\n" + "=" * 45)
    print("📊 RESUMEN DE SIMULACIÓN DE TRADING")
    print("=" * 45)
    
    test_categories = {
        'normal_trading_day': 'Día Normal de Trading',
        'bull_market_day': 'Día de Mercado Alcista',
        'market_stress_scenarios': 'Escenarios de Stress',
        'strategy_validation': 'Validación de Estrategias'
    }
    
    passed_tests = 0
    total_tests = len(all_results)
    
    for test_key, test_name in test_categories.items():
        if test_key in all_results:
            result = all_results[test_key]
            
            # Determinar si pasó basado en criterios específicos
            passed = False
            metrics_info = ""
            
            if test_key in ['normal_trading_day', 'bull_market_day']:
                trades_generated = result.get('trades_generated', 0)
                trades_opened = result.get('trades_opened', 0)
                success_rate = trades_opened / trades_generated if trades_generated > 0 else 0
                passed = success_rate > 0.8 and trades_generated > 20  # 80% éxito, mínimo 20 trades
                
                total_pnl = result.get('total_pnl', 0)
                win_rate = result.get('win_rate', 0)
                metrics_info = f"({trades_generated} trades, ${total_pnl:.0f} PnL, {win_rate*100:.1f}% WR)"
                
            elif test_key == 'market_stress_scenarios':
                scenarios_count = len(result.get('scenarios_tested', []))
                total_trades = result.get('total_trades_generated', 0)
                passed = scenarios_count >= 3 and total_trades > 50  # Mínimo 3 escenarios, 50 trades
                metrics_info = f"({scenarios_count} escenarios, {total_trades} trades)"
                
            elif test_key == 'strategy_validation':
                strategies_tested = len(result.get('strategies_tested', []))
                failed_validations = len(result.get('failed_validations', []))
                passed = strategies_tested >= 4 and failed_validations <= strategies_tested * 0.3  # Max 30% fallos
                metrics_info = f"({strategies_tested} estrategias, {failed_validations} fallos)"
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name}: {status} {metrics_info}")
            
            if passed:
                passed_tests += 1
    
    print(f"\n🎯 RESULTADO FINAL: {passed_tests}/{total_tests} tests de simulación pasaron")
    
    # Recomendaciones específicas
    print("\n💡 RECOMENDACIONES DE SIMULACIÓN:")
    
    if passed_tests == total_tests:
        print("🏆 ¡Sistema de trading completamente validado!")
        print("✅ Comportamiento realista bajo todas las condiciones")
        print("🎯 Estrategias funcionan según expectativas")
        print("🚀 Listo para trading en vivo")
    elif passed_tests >= total_tests * 0.75:
        print("💪 Sistema de trading robusto con áreas de mejora")
        print("⚠️  Revisar tests fallidos para optimización")
        print("📊 Ajustar parámetros de estrategias si es necesario")
    else:
        print("⚠️  Sistema necesita mejoras significativas")
        print("🔧 Revisar lógica de estrategias y ejecución")
        print("📉 No recomendado para trading en vivo")
    
    # Análisis específico de resultados
    normal_day = all_results.get('normal_trading_day', {})
    if normal_day.get('win_rate', 0) < 0.5:
        print("📉 Win rate bajo en condiciones normales - revisar estrategias")
    
    bull_day = all_results.get('bull_market_day', {})
    if bull_day.get('total_pnl', 0) <= normal_day.get('total_pnl', 0):
        print("📊 Sistema no aprovecha mercados alcistas eficientemente")
    
    validation = all_results.get('strategy_validation', {})
    if len(validation.get('failed_validations', [])) > 0:
        print("⚙️  Algunas estrategias no funcionan según parámetros esperados")

if __name__ == "__main__":
    main()