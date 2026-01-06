# tests/bull_flag_backtest.py
import asyncio
import pandas as pd
from datetime import datetime
import backtrader as bt
from workers.bull_flag_worker import BullFlagWorker

class BullFlagBacktest:
    """Framework de backtesting especializado para patrones Bull Flag"""
    
    def __init__(self):
        self.pattern_generator = BullFlagPatternGenerator()
        self.results = []
        
    async def test_worker_detection(self, num_tests=50):
        """Testea la capacidad del worker para detectar patrones Bull Flag"""
        print(f"🧪 Testing Bull Flag Worker with {num_tests} patterns...")
        
        # Generar patrones de prueba
        patterns = self.pattern_generator.generate_random_patterns(num_tests)
        
        # Inicializar worker (modo test)
        worker = BullFlagWorker()
        
        detection_stats = {
            'true_positives': 0,
            'false_positives': 0,
            'false_negatives': 0,
            'pattern_strength_threshold': 0.6
        }
        
        for i, pattern_data in enumerate(patterns):
            pattern_strength = pattern_data['pattern_info']['pattern_strength']
            data = pattern_data['data']
            
            # Simular opportunity basado en el patrón
            opportunity = self._create_opportunity_from_pattern(data, pattern_data['pattern_info'])
            
            # Testear análisis del worker
            enhanced_opportunity = await self._simulate_enhancement(opportunity, data)
            analysis = await worker._analyze_flag_setup(enhanced_opportunity)
            
            # Evaluar detección
            is_strong_pattern = pattern_strength > detection_stats['pattern_strength_threshold']
            was_detected = analysis['should_trade']
            
            if is_strong_pattern and was_detected:
                detection_stats['true_positives'] += 1
            elif is_strong_pattern and not was_detected:
                detection_stats['false_negatives'] += 1
            elif not is_strong_pattern and was_detected:
                detection_stats['false_positives'] += 1
                
            print(f"Pattern {i+1}: strength={pattern_strength:.2f}, detected={was_detected}")
            
        # Calcular métricas
        total_strong = detection_stats['true_positives'] + detection_stats['false_negatives']
        total_detected = detection_stats['true_positives'] + detection_stats['false_positives']
        
        precision = (detection_stats['true_positives'] / total_detected) if total_detected > 0 else 0
        recall = (detection_stats['true_positives'] / total_strong) if total_strong > 0 else 0
        
        print(f"\n📊 Detection Results:")
        print(f"True Positives: {detection_stats['true_positives']}")
        print(f"False Positives: {detection_stats['false_positives']}")
        print(f"False Negatives: {detection_stats['false_negatives']}")
        print(f"Precision: {precision:.2%}")
        print(f"Recall: {recall:.2%}")
        
        return detection_stats
    
    def _create_opportunity_from_pattern(self, data, pattern_info):
        """Crea un opportunity a partir de datos de patrón"""
        current_price = data['close'].iloc[-1]
        volume = data['volume'].iloc[-1]
        pole_height = pattern_info['pole_height_percent']
        
        return {
            'symbol': 'TEST',
            'opportunity_type': 'BULL_FLAG',
            'current_price': current_price,
            'volume': volume,
            'gap_percentage': pole_height,  # Usar pole height como gap aproximado
            'volume_ratio': 1.5,  # Ratio de volumen típico
            'quality_score': pattern_info['pattern_strength'] * 100,
            'pattern_data': pattern_info
        }
    
    async def _simulate_enhancement(self, opportunity, data):
        """Simula el enhancement service para testing"""
        enhanced = opportunity.copy()
        enhanced.update({
            'current_price': data['close'].iloc[-1],
            'previous_close': data['close'].iloc[0],
            'volume': data['volume'].iloc[-1],
            'market_cap': 1_000_000_000,
            'enhanced': True
        })
        return enhanced

class BullFlagBacktraderStrategy(bt.Strategy):
    """Estrategia Backtrader para testing de Bull Flag"""
    
    def __init__(self, bull_flag_worker):
        self.worker = bull_flag_worker
        self.dataclose = self.datas[0].close
        self.datavolume = self.datas[0].volume
        
    def next(self):
        # Solo evaluar cada 5 velas para simular procesamiento en tiempo real
        if len(self) % 5 == 0:
            # Crear opportunity simulado
            opportunity = {
                'symbol': 'TEST',
                'opportunity_type': 'BULL_FLAG',
                'current_price': self.dataclose[0],
                'volume': self.datavolume[0],
                'gap_percentage': 0.0,
                'volume_ratio': 1.0,
                'quality_score': 50.0
            }
            
            # Ejecutar análisis (simulado)
            # En una implementación real, esto sería async
            pass

async def run_comprehensive_test():
    """Ejecuta tests comprehensivos del Bull Flag Worker"""
    
    # 1. Test de detección de patrones
    backtester = BullFlagBacktest()
    detection_results = await backtester.test_worker_detection(30)
    
    # 2. Generar ejemplos visuales
    generator = BullFlagPatternGenerator()
    
    print("\n🎯 Generating example patterns...")
    
    # Patrón fuerte
    strong_pattern = generator.generate_bull_flag_pattern(0.8)
    generator.plot_pattern(strong_pattern, "Strong Bull Flag Pattern")
    
    # Patrón débil
    weak_pattern = generator.generate_bull_flag_pattern(0.4)
    generator.plot_pattern(weak_pattern, "Weak Bull Flag Pattern")
    
    # 3. Test de parámetros
    await test_parameter_sensitivity()

async def test_parameter_sensitivity():
    """Testea la sensibilidad a diferentes parámetros del patrón"""
    print("\n🔧 Testing parameter sensitivity...")
    
    worker = BullFlagWorker()
    generator = BullFlagPatternGenerator()
    
    # Test diferentes alturas de pole
    pole_heights = [3, 8, 15, 25]  # porcentajes
    for height in pole_heights:
        # Modificar parámetro temporalmente
        original_min = worker.min_pole_height
        worker.min_pole_height = height - 2
        worker.max_pole_height = height + 5
        
        pattern = generator.generate_bull_flag_pattern(0.7)
        opportunity = {
            'symbol': 'TEST',
            'opportunity_type': 'BULL_FLAG',
            'current_price': pattern['data']['close'].iloc[-1],
            'volume': pattern['data']['volume'].iloc[-1],
            'gap_percentage': height,
            'volume_ratio': 2.0,
            'quality_score': 70.0
        }
        
        enhanced = await backtester._simulate_enhancement(opportunity, pattern['data'])
        analysis = await worker._analyze_flag_setup(enhanced)
        
        print(f"Pole height {height}%: Trade={analysis['should_trade']}, Reason={analysis['reason']}")
        
        # Restaurar parámetros
        worker.min_pole_height = original_min

if __name__ == "__main__":
    # Ejecutar tests
    asyncio.run(run_comprehensive_test())