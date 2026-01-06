# tests/bull_flag_pattern_generator.py
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

class BullFlagPatternGenerator:
    """Genera datos sintéticos con patrones Bull Flag para testing"""
    
    def __init__(self):
        self.base_price = 100.0
        self.volatility = 0.02  # 2% de volatilidad diaria
        
    def generate_bull_flag_pattern(self, pattern_strength=0.7):
        """
        Genera un patrón Bull Flag completo:
        - Pole: Movimiento alcista rápido
        - Flag: Consolidación/descenso suave
        - Breakout: Ruptura alcista
        """
        # Parámetros del patrón
        pole_height = pattern_strength * 0.15 + 0.05  # 5-20% de altura
        flag_retracement = pattern_strength * 0.4 + 0.2  # 20-60% de retroceso
        flag_duration = int(pattern_strength * 30 + 10)  # 10-40 periodos
        
        # 1. POLE - Movimiento alcista fuerte
        pole_periods = 5
        pole_data = self._generate_pole(self.base_price, pole_height, pole_periods)
        
        # 2. FLAG - Consolidación/descenso
        flag_start_price = pole_data['close'].iloc[-1]
        flag_data = self._generate_flag(flag_start_price, flag_retracement, flag_duration)
        
        # 3. BREAKOUT - Ruptura alcista
        breakout_data = self._generate_breakout(flag_data['close'].iloc[-1], pattern_strength)
        
        # Combinar todos los datos
        full_data = pd.concat([pole_data, flag_data, breakout_data], ignore_index=True)
        
        return {
            'data': full_data,
            'pattern_info': {
                'pole_height_percent': pole_height * 100,
                'flag_retracement_percent': flag_retracement * 100,
                'flag_duration': flag_duration,
                'pattern_strength': pattern_strength,
                'pole_end_idx': len(pole_data) - 1,
                'flag_end_idx': len(pole_data) + len(flag_data) - 1
            }
        }
    
    def _generate_pole(self, start_price, height, periods):
        """Genera el mástil/palo del patrón"""
        data = []
        current_price = start_price
        
        for i in range(periods):
            # Movimiento alcista fuerte
            move = height / periods + np.random.normal(0, self.volatility/3)
            current_price *= (1 + move)
            
            # Generar OHLC
            open_price = current_price * (1 + np.random.normal(0, 0.001))
            high = max(open_price, current_price) * (1 + abs(np.random.normal(0, 0.005)))
            low = min(open_price, current_price) * (1 - abs(np.random.normal(0, 0.005)))
            close = current_price
            
            # Volumen alto durante el pole
            volume = np.random.normal(1000000, 100000)
            
            data.append({
                'datetime': datetime.now() + timedelta(minutes=i*5),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': max(volume, 1000),
                'phase': 'pole'
            })
            
        return pd.DataFrame(data)
    
    def _generate_flag(self, start_price, retracement, periods):
        """Genera la bandera (consolidación)"""
        data = []
        current_price = start_price
        
        for i in range(periods):
            # Movimiento lateral con ligero retroceso
            move = np.random.normal(-retracement/(periods*2), self.volatility/2)
            current_price *= (1 + move)
            
            # Rango estrecho típico de flags
            open_price = current_price * (1 + np.random.normal(0, 0.002))
            high = max(open_price, current_price) * (1 + abs(np.random.normal(0, 0.003)))
            low = min(open_price, current_price) * (1 - abs(np.random.normal(0, 0.003)))
            close = current_price
            
            # Volumen decreciente durante la bandera
            volume = np.random.normal(500000, 50000) * (1 - i/periods)
            
            data.append({
                'datetime': datetime.now() + timedelta(minutes=(5 + i)*5),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': max(volume, 1000),
                'phase': 'flag'
            })
            
        return pd.DataFrame(data)
    
    def _generate_breakout(self, start_price, strength):
        """Genera el breakout de la bandera"""
        data = []
        current_price = start_price
        breakout_strength = strength * 0.1 + 0.02  # 2-12% de breakout
        
        for i in range(10):  # 10 periodos de breakout
            # Movimiento alcista fuerte
            if i == 0:
                move = breakout_strength * 0.5  # Gran movimiento inicial
            else:
                move = np.random.normal(breakout_strength/10, self.volatility/4)
            
            current_price *= (1 + move)
            
            open_price = current_price * (1 + np.random.normal(0, 0.001))
            high = max(open_price, current_price) * (1 + abs(np.random.normal(0, 0.004)))
            low = min(open_price, current_price) * (1 - abs(np.random.normal(0, 0.002)))
            close = current_price
            
            # Volumen alto en breakout
            volume = np.random.normal(1500000, 200000)
            
            data.append({
                'datetime': datetime.now() + timedelta(minutes=(15 + i)*5),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': max(volume, 1000),
                'phase': 'breakout'
            })
            
        return pd.DataFrame(data)
    
    def generate_random_patterns(self, num_patterns=100):
        """Genera múltiples patrones para testing exhaustivo"""
        patterns = []
        for i in range(num_patterns):
            strength = np.random.uniform(0.3, 1.0)  # Fuerza variable del patrón
            pattern_data = self.generate_bull_flag_pattern(strength)
            patterns.append(pattern_data)
        return patterns

    def plot_pattern(self, pattern_data, title="Bull Flag Pattern"):
        """Visualiza el patrón generado"""
        data = pattern_data['data']
        info = pattern_data['pattern_info']
        
        plt.figure(figsize=(12, 8))
        
        # Precio
        plt.subplot(2, 1, 1)
        plt.plot(data['close'], label='Close Price', linewidth=2)
        
        # Marcar fases
        pole_end = info['pole_end_idx']
        flag_end = info['flag_end_idx']
        
        plt.axvline(x=pole_end, color='green', linestyle='--', alpha=0.7, label='Pole End')
        plt.axvline(x=flag_end, color='orange', linestyle='--', alpha=0.7, label='Flag End')
        
        plt.title(f"{title} - Strength: {info['pattern_strength']:.2f}")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Volumen
        plt.subplot(2, 1, 2)
        plt.bar(range(len(data)), data['volume'], alpha=0.7, color='blue')
        plt.axvline(x=pole_end, color='green', linestyle='--', alpha=0.7)
        plt.axvline(x=flag_end, color='orange', linestyle='--', alpha=0.7)
        plt.title('Volume')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()