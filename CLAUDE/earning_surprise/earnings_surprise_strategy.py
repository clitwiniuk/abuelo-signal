"""
Estrategia de Momentum por Earnings Surprises en Small Caps
Detecta y capitaliza el momentum post-earnings usando APIs gratuitas
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
import configparser
import os
import requests
import time
import json
from dataclasses import dataclass

from .base_strategy import BaseStrategy, BarData

# Configuración de logging
logger = logging.getLogger(__name__)

# Cargar configuración global
CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini'))

# Registrar la estrategia
from . import register_strategy

@dataclass
class EarningsData:
    """Estructura para datos de earnings"""
    ticker: str
    earnings_date: datetime
    actual_eps: float
    estimated_eps: float
    surprise_pct: float
    market_cap: float
    volume_spike: float
    pre_post_market: str  # 'pre' o 'post'

class EarningsDataProvider:
    """
    Proveedor de datos de earnings usando APIs gratuitas
    """
    
    def __init__(self):
        # APIs gratuitas que podemos usar
        self.apis = {
            'alpha_vantage': {
                'base_url': 'https://www.alphavantage.co/query',
                'key': CONFIG.get('APIs', 'alpha_vantage_key', fallback='demo'),  # Necesitarás registrarte (gratis)
                'calls_per_minute': 5
            },
            'financialmodelingprep': {
                'base_url': 'https://financialmodelingprep.com/api/v3',
                'key': CONFIG.get('APIs', 'fmp_key', fallback='demo'),  # 250 calls gratis/día
                'calls_per_minute': 10
            },
            'polygon': {
                'base_url': 'https://api.polygon.io',
                'key': CONFIG.get('APIs', 'polygon_key', fallback='demo'),  # Tier gratis disponible
                'calls_per_minute': 5
            }
        }
        
        self.last_call_times = {}
        self.call_counts = {}
    
    def _rate_limit(self, api_name: str):
        """Control de rate limiting"""
        current_time = time.time()
        
        if api_name not in self.last_call_times:
            self.last_call_times[api_name] = []
        
        # Limpiar llamadas antiguas (más de 1 minuto)
        self.last_call_times[api_name] = [
            t for t in self.last_call_times[api_name] 
            if current_time - t < 60
        ]
        
        # Verificar límite
        max_calls = self.apis[api_name]['calls_per_minute']
        if len(self.last_call_times[api_name]) >= max_calls:
            sleep_time = 60 - (current_time - self.last_call_times[api_name][0])
            if sleep_time > 0:
                logger.info(f"Rate limit {api_name}: esperando {sleep_time:.1f}s")
                time.sleep(sleep_time)
        
        self.last_call_times[api_name].append(current_time)
    
    def get_recent_earnings(self, days_back: int = 7) -> List[EarningsData]:
        """
        Obtiene earnings recientes usando múltiples APIs gratuitas
        """
        earnings_data = []
        
        try:
            # Intentar con Financial Modeling Prep (gratis hasta 250 calls/día)
            earnings_data.extend(self._get_fmp_earnings(days_back))
        except Exception as e:
            logger.warning(f"Error con FMP: {e}")
        
        try:
            # Complementar con Alpha Vantage si es necesario
            if len(earnings_data) < 20:  # Si no tenemos suficientes datos
                earnings_data.extend(self._get_alpha_vantage_earnings(days_back))
        except Exception as e:
            logger.warning(f"Error con Alpha Vantage: {e}")
        
        return self._filter_small_caps(earnings_data)
    
    def _get_fmp_earnings(self, days_back: int) -> List[EarningsData]:
        """Obtener earnings de Financial Modeling Prep"""
        self._rate_limit('financialmodelingprep')
        
        # Endpoint para earnings calendar
        from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.apis['financialmodelingprep']['base_url']}/earning_calendar"
        params = {
            'from': from_date,
            'to': to_date,
            'apikey': self.apis['financialmodelingprep']['key']
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        earnings_list = []
        
        for item in data:
            try:
                if not item.get('eps') or not item.get('epsEstimated'):
                    continue
                    
                actual_eps = float(item['eps'])
                estimated_eps = float(item['epsEstimated'])
                
                if estimated_eps == 0:
                    continue
                
                surprise_pct = ((actual_eps - estimated_eps) / abs(estimated_eps)) * 100
                
                earnings_list.append(EarningsData(
                    ticker=item['symbol'],
                    earnings_date=datetime.strptime(item['date'], '%Y-%m-%d'),
                    actual_eps=actual_eps,
                    estimated_eps=estimated_eps,
                    surprise_pct=surprise_pct,
                    market_cap=self._get_market_cap(item['symbol']),
                    volume_spike=0,  # Se calculará después
                    pre_post_market=item.get('time', 'post').lower()
                ))
            except (ValueError, KeyError) as e:
                continue
        
        return earnings_list
    
    def _get_alpha_vantage_earnings(self, days_back: int) -> List[EarningsData]:
        """Obtener earnings de Alpha Vantage (backup)"""
        self._rate_limit('alpha_vantage')
        
        # Alpha Vantage tiene endpoint de earnings calendar
        url = self.apis['alpha_vantage']['base_url']
        params = {
            'function': 'EARNINGS_CALENDAR',
            'horizon': '3month',
            'apikey': self.apis['alpha_vantage']['key']
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Alpha Vantage devuelve CSV para earnings calendar
            df = pd.read_csv(response.text)
            earnings_list = []
            
            # Filtrar por fechas recientes
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            for _, row in df.iterrows():
                try:
                    report_date = pd.to_datetime(row['reportDate'])
                    if report_date < cutoff_date:
                        continue
                    
                    if pd.isna(row['estimate']) or pd.isna(row['actual']):
                        continue
                    
                    actual = float(row['actual'])
                    estimate = float(row['estimate'])
                    
                    if estimate == 0:
                        continue
                    
                    surprise_pct = ((actual - estimate) / abs(estimate)) * 100
                    
                    earnings_list.append(EarningsData(
                        ticker=row['symbol'],
                        earnings_date=report_date,
                        actual_eps=actual,
                        estimated_eps=estimate,
                        surprise_pct=surprise_pct,
                        market_cap=self._get_market_cap(row['symbol']),
                        volume_spike=0,
                        pre_post_market='post'
                    ))
                except Exception as e:
                    continue
            
            return earnings_list
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de Alpha Vantage: {e}")
            return []
    
    def _get_market_cap(self, ticker: str) -> float:
        """Obtener market cap para filtrar small caps"""
        try:
            # Usar FMP para obtener market cap
            self._rate_limit('financialmodelingprep')
            
            url = f"{self.apis['financialmodelingprep']['base_url']}/market-capitalization/{ticker}"
            params = {'apikey': self.apis['financialmodelingprep']['key']}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                return data[0].get('marketCap', 0)
            
        except Exception:
            pass
        
        return 0  # Si no podemos obtener el market cap, asumimos que no es small cap
    
    def _filter_small_caps(self, earnings_data: List[EarningsData]) -> List[EarningsData]:
        """Filtrar solo small caps (market cap < $2B)"""
        small_cap_threshold = CONFIG.getfloat('STRATEGY_EARNINGS', 'small_cap_max_mcap', fallback=2_000_000_000)
        
        filtered = []
        for earning in earnings_data:
            if 0 < earning.market_cap < small_cap_threshold:
                filtered.append(earning)
        
        logger.info(f"Filtrados {len(filtered)} small caps de {len(earnings_data)} earnings totales")
        return filtered

@register_strategy('earnings_surprise')
class EarningsSurpriseStrategy(BaseStrategy):
    """
    Estrategia de momentum basada en sorpresas de earnings en small caps
    """
    
    def __init__(self, config_section: str = None):
        """Inicializa la estrategia de earnings surprise"""
        super().__init__(config_section or 'STRATEGY_EARNINGS')
        
        # Parámetros de la estrategia
        self.min_surprise_pct = CONFIG.getfloat(self.config_section, 'min_surprise_pct', fallback=5.0)
        self.max_days_since_earnings = CONFIG.getint(self.config_section, 'max_days_since_earnings', fallback=5)
        self.min_volume_spike = CONFIG.getfloat(self.config_section, 'min_volume_spike', fallback=2.0)
        self.momentum_window = CONFIG.getint(self.config_section, 'momentum_window', fallback=3)
        self.rsi_period = CONFIG.getint(self.config_section, 'rsi_period', fallback=14)
        self.max_rsi_overbought = CONFIG.getfloat(self.config_section, 'max_rsi_overbought', fallback=75)
        self.min_rsi_oversold = CONFIG.getfloat(self.config_section, 'min_rsi_oversold', fallback=25)
        
        # Proveedor de datos de earnings
        self.earnings_provider = EarningsDataProvider()
        
        # Cache de earnings recientes
        self.earnings_cache = {}
        self.last_earnings_update = None
    
    def _update_earnings_cache(self):
        """Actualizar cache de earnings si es necesario"""
        now = datetime.now()
        
        # Actualizar cada 4 horas
        if (self.last_earnings_update is None or 
            (now - self.last_earnings_update).total_seconds() > 14400):
            
            logger.info("Actualizando cache de earnings...")
            recent_earnings = self.earnings_provider.get_recent_earnings(
                days_back=self.max_days_since_earnings + 2
            )
            
            # Organizar por ticker
            self.earnings_cache = {}
            for earning in recent_earnings:
                self.earnings_cache[earning.ticker] = earning
            
            self.last_earnings_update = now
            logger.info(f"Cache actualizado con {len(self.earnings_cache)} earnings")
    
    def should_enter_position(self, ticker: str, bars: List[BarData]) -> Tuple[bool, str]:
        """
        Determina si entrar en posición basado en earnings surprise momentum
        """
        if len(bars) < 50:
            return False, "Historial insuficiente"
        
        try:
            # Actualizar cache de earnings
            self._update_earnings_cache()
            
            # Verificar si el ticker tuvo earnings recientes
            if ticker not in self.earnings_cache:
                return False, "Sin earnings recientes"
            
            earning_data = self.earnings_cache[ticker]
            
            # Verificar que los earnings sean suficientemente recientes
            days_since_earnings = (datetime.now() - earning_data.earnings_date).days
            if days_since_earnings > self.max_days_since_earnings:
                return False, "Earnings muy antiguos"
            
            # Verificar surprise mínimo
            if abs(earning_data.surprise_pct) < self.min_surprise_pct:
                return False, f"Surprise insuficiente: {earning_data.surprise_pct:.1f}%"
            
            # Convertir bars a DataFrame
            df = pd.DataFrame([{
                'date': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars])
            
            # Calcular indicadores
            df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
            df['volume_ma'] = df['volume'].rolling(20).mean()
            df['price_change'] = df['close'].pct_change()
            
            # Calcular momentum post-earnings
            earnings_bar_idx = self._find_earnings_bar_index(df, earning_data.earnings_date)
            if earnings_bar_idx is None:
                return False, "No se encontró barra de earnings"
            
            # Analizar momentum desde earnings
            post_earnings_data = df.iloc[earnings_bar_idx:].copy()
            if len(post_earnings_data) < 2:
                return False, "Datos post-earnings insuficientes"
            
            # Calcular métricas de momentum
            momentum_metrics = self._calculate_momentum_metrics(post_earnings_data, earning_data)
            
            # Obtener valores actuales
            current = df.iloc[-1]
            
            # Determinar dirección de la estrategia
            signal_type = self._determine_signal_type(earning_data, momentum_metrics, current)
            
            if signal_type:
                logger.info(
                    f"{ticker}: Señal {signal_type} - "
                    f"Surprise: {earning_data.surprise_pct:.1f}%, "
                    f"Momentum: {momentum_metrics['price_momentum']:.1f}%, "
                    f"RSI: {current['rsi']:.1f}"
                )
                return True, signal_type
            
            return False, ""
            
        except Exception as e:
            logger.error(f"Error en earnings surprise para {ticker}: {e}")
            return False, ""
    
    def _find_earnings_bar_index(self, df: pd.DataFrame, earnings_date: datetime) -> Optional[int]:
        """Encuentra el índice de la barra más cercana a la fecha de earnings"""
        df['time_diff'] = abs((df['date'] - earnings_date).dt.total_seconds())
        min_diff_idx = df['time_diff'].idxmin()
        
        # Solo si está dentro de 24 horas
        if df.loc[min_diff_idx, 'time_diff'] < 86400:
            return min_diff_idx
        return None
    
    def _calculate_momentum_metrics(self, post_earnings_df: pd.DataFrame, earning_data: EarningsData) -> Dict:
        """Calcula métricas de momentum post-earnings"""
        if len(post_earnings_df) < 2:
            return {}
        
        # Momentum de precio desde earnings
        price_start = post_earnings_df['close'].iloc[0]
        price_current = post_earnings_df['close'].iloc[-1]
        price_momentum = ((price_current - price_start) / price_start) * 100
        
        # Momentum de volumen
        volume_current = post_earnings_df['volume'].iloc[-3:].mean()  # Promedio últimas 3 barras
        volume_baseline = post_earnings_df['volume_ma'].iloc[-1]
        volume_spike = volume_current / volume_baseline if volume_baseline > 0 else 1
        
        # Consistencia del momentum (% de días con movimiento en misma dirección)
        daily_changes = post_earnings_df['price_change'].iloc[1:]  # Excluir primer día
        if earning_data.surprise_pct > 0:  # Surprise positivo
            consistency = (daily_changes > 0).mean() * 100
        else:  # Surprise negativo
            consistency = (daily_changes < 0).mean() * 100
        
        # Volatilidad ajustada
        volatility = daily_changes.std() * 100
        
        return {
            'price_momentum': price_momentum,
            'volume_spike': volume_spike,
            'consistency': consistency,
            'volatility': volatility,
            'days_tracked': len(daily_changes)
        }
    
    def _determine_signal_type(self, earning_data: EarningsData, momentum_metrics: Dict, current_bar: pd.Series) -> Optional[str]:
        """Determina el tipo de señal basado en todos los factores"""
        if not momentum_metrics:
            return None
        
        surprise_pct = earning_data.surprise_pct
        price_momentum = momentum_metrics.get('price_momentum', 0)
        volume_spike = momentum_metrics.get('volume_spike', 1)
        consistency = momentum_metrics.get('consistency', 50)
        current_rsi = current_bar['rsi']
        
        # Condiciones base
        volume_ok = volume_spike >= self.min_volume_spike
        momentum_strong = abs(price_momentum) >= 2.0  # Al menos 2% de momentum
        consistency_ok = consistency >= 60  # Al menos 60% de consistencia
        
        # Señales LONG (surprise positivo con momentum alcista)
        if (surprise_pct > self.min_surprise_pct and 
            price_momentum > 0 and 
            momentum_strong and 
            volume_ok and 
            consistency_ok and 
            current_rsi < self.max_rsi_overbought):
            return "LONG"
        
        # Señales SHORT (surprise negativo con momentum bajista)
        elif (surprise_pct < -self.min_surprise_pct and 
              price_momentum < 0 and 
              momentum_strong and 
              volume_ok and 
              consistency_ok and 
              current_rsi > self.min_rsi_oversold):
            return "SHORT"
        
        # Señales de reversión (contrarian)
        # Solo si el momentum inicial se está agotando
        elif (abs(surprise_pct) > self.min_surprise_pct * 1.5 and  # Surprise muy fuerte
              momentum_metrics.get('days_tracked', 0) >= 3 and     # Al menos 3 días de tracking
              consistency < 40):  # Momentum perdiendo consistencia
            
            if surprise_pct > 0 and current_rsi > self.max_rsi_overbought:
                return "SHORT"  # Reversión bajista tras surprise positivo
            elif surprise_pct < 0 and current_rsi < self.min_rsi_oversold:
                return "LONG"   # Reversión alcista tras surprise negativo
        
        return None
    
    def get_position_size(self, ticker: str, signal_type: str, account_value: float) -> float:
        """
        Calcula el tamaño de posición basado en la fuerza del earnings surprise
        """
        base_size = super().get_position_size(ticker, signal_type, account_value)
        
        if ticker not in self.earnings_cache:
            return base_size
        
        earning_data = self.earnings_cache[ticker]
        surprise_strength = abs(earning_data.surprise_pct)
        
        # Ajustar tamaño basado en fuerza del surprise
        if surprise_strength > 15:  # Surprise muy fuerte
            multiplier = 1.5
        elif surprise_strength > 10:  # Surprise fuerte
            multiplier = 1.3
        elif surprise_strength > 7:   # Surprise moderado
            multiplier = 1.1
        else:
            multiplier = 1.0
        
        return min(base_size * multiplier, base_size * 2)  # Máximo 2x el tamaño base
    
    def should_exit_position(self, ticker: str, bars: List[BarData], entry_bar: BarData, position_type: str) -> Tuple[bool, str]:
        """
        Determina cuándo salir de la posición (earnings momentum se agota rápido)
        """
        if len(bars) < 5:
            return False, ""
        
        try:
            # Convertir a DataFrame
            df = pd.DataFrame([{
                'date': bar.date,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars])
            
            current = df.iloc[-1]
            entry_price = entry_bar.close
            
            # Calcular P&L
            if position_type == "LONG":
                pnl_pct = ((current['close'] - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - current['close']) / entry_price) * 100
            
            # Salidas por tiempo (earnings momentum se agota en 3-5 días)
            days_in_position = len(df)
            if days_in_position >= 5:
                return True, "Máximo tiempo en posición"
            
            # Salidas por profit target agresivo
            if pnl_pct > 8:  # 8% profit target
                return True, f"Profit target alcanzado: {pnl_pct:.1f}%"
            
            # Stop loss ajustado
            if pnl_pct < -4:  # 4% stop loss
                return True, f"Stop loss: {pnl_pct:.1f}%"
            
            # Salida por pérdida de momentum
            if days_in_position >= 3:
                recent_momentum = df['close'].pct_change().iloc[-2:].mean() * 100
                
                if position_type == "LONG" and recent_momentum < -1:
                    return True, "Pérdida de momentum alcista"
                elif position_type == "SHORT" and recent_momentum > 1:
                    return True, "Pérdida de momentum bajista"
            
            return False, ""
            
        except Exception as e:
            logger.error(f"Error en should_exit_position para {ticker}: {e}")
            return True, "Error en evaluación de salida"