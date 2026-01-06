# tests/quick_validation.py
import asyncio
from bull_flag_pattern_generator import BullFlagPatternGenerator
from workers.bull_flag_worker import BullFlagWorker

async def quick_validation():
    """Validación rápida del worker con datos sintéticos"""
    
    print("🚀 Quick Validation of Bull Flag Worker")
    print("=" * 50)
    
    # Generar patrón de ejemplo
    generator = BullFlagPatternGenerator()
    pattern = generator.generate_bull_flag_pattern(0.75)
    
    # Mostrar información del patrón
    info = pattern['pattern_info']
    print(f"📊 Pattern Characteristics:")
    print(f"   Strength: {info['pattern_strength']:.2f}")
    print(f"   Pole Height: {info['pole_height_percent']:.1f}%")
    print(f"   Flag Duration: {info['flag_duration']} periods")
    
    # Testear worker
    worker = BullFlagWorker()
    
    # Crear opportunity simulado
    opportunity = {
        'symbol': 'AAPL_TEST',
        'opportunity_type': 'BULL_FLAG', 
        'current_price': pattern['data']['close'].iloc[-1],
        'volume': pattern['data']['volume'].iloc[-1],
        'gap_percentage': info['pole_height_percent'],
        'volume_ratio': 2.5,
        'quality_score': 85.0
    }
    
    # Simular enhancement
    enhanced_opportunity = opportunity.copy()
    enhanced_opportunity.update({
        'previous_close': pattern['data']['close'].iloc[0],
        'market_cap': 2_000_000_000,
        'enhanced': True
    })
    
    # Ejecutar análisis
    analysis = await worker._analyze_flag_setup(enhanced_opportunity)
    
    print(f"\n🔍 Worker Analysis:")
    print(f"   Should Trade: {analysis['should_trade']}")
    print(f"   Action: {analysis['action']}")
    print(f"   Quantity: {analysis['quantity']}")
    print(f"   Entry: ${analysis['entry_price']:.2f}")
    print(f"   Stop: ${analysis['stop_loss']:.2f}")
    print(f"   Target: ${analysis['take_profit']:.2f}")
    print(f"   Reason: {analysis['reason']}")
    
    # Mostrar gráfico
    generator.plot_pattern(pattern, "Test Pattern for Worker Validation")

if __name__ == "__main__":
    asyncio.run(quick_validation())