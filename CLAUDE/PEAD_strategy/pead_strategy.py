import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import requests
import warnings
import time
from textblob import TextBlob
import re
from ib_insync import *
warnings.filterwarnings('ignore')

class EnhancedPEADStrategy:
    def __init__(self, alpha_vantage_key, min_market_cap=300e6, max_market_cap=2e9, min_avg_volume=500000):
        self.av_key = alpha_vantage_key
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.min_avg_volume = min_avg_volume
        self.positions = []
        self.trades = []
        self.ib = None
        self.earnings_cache = {}
        
    def connect_ibkr(self, host='127.0.0.1', port=7497):
        """Conecta a Interactive Brokers TWS/Gateway"""
        try:
            self.ib = IB()
            self.ib.connect(host, port, clientId=1)
            print("✅ Conectado a IBKR exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error conectando a IBKR: {e}")
            print("💡 Asegúrate de tener TWS/Gateway corriendo y API habilitada")
            return False
    
    def get_earnings_calendar_av(self, horizon='3month'):
        """Obtiene calendario de earnings de Alpha Vantage"""
        try:
            url = f'https://www.alphavantage.co/query'
            params = {
                'function': 'EARNINGS_CALENDAR',
                'horizon': horizon,
                'apikey': self.av_key
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                # Alpha Vantage devuelve CSV
                from io import StringIO
                df = pd.read_csv(StringIO(response.text))
                
                # Limpiar y procesar datos
                df['reportDate'] = pd.to_datetime(df['reportDate'])
                df = df[df['reportDate'] >= datetime.now().date()]
                
                # Filtrar por market cap si disponible
                if 'marketCapitalization' in df.columns:
                    df['marketCap'] = pd.to_numeric(df['marketCapitalization'], errors='coerce')
                    df = df[(df['marketCap'] >= self.min_market_cap) & 
                           (df['marketCap'] <= self.max_market_cap)]
                
                print(f"📅 Obtenidos {len(df)} earnings próximos de Alpha Vantage")
                return df
                
        except Exception as e:
            print(f"❌ Error obteniendo earnings de AV: {e}")
        
        return pd.DataFrame()
    
    def get_realtime_liquidity_ibkr(self, symbol):
        """Obtiene liquidez en tiempo real desde IBKR"""
        if not self.ib:
            print("⚠️ IBKR no conectado, usando datos históricos")
            return self.get_liquidity_fallback(symbol)
        
        try:
            # Crear contrato
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Obtener datos de mercado
            ticker = self.ib.reqMktData(contract, '', False, False)
            self.ib.sleep(2)  # Esperar datos
            
            # Obtener book de órdenes (Nivel II)
            dom = self.ib.reqMktDepth(contract)
            self.ib.sleep(1)
            
            liquidity_metrics = {
                'bid_size': ticker.bidSize if ticker.bidSize else 0,
                'ask_size': ticker.askSize if ticker.askSize else 0,
                'bid': ticker.bid if ticker.bid else 0,
                'ask': ticker.ask if ticker.ask else 0,
                'volume': ticker.volume if ticker.volume else 0,
                'avg_volume': ticker.avgVolume if ticker.avgVolume else 0
            }
            
            # Calcular spread y liquidez
            if liquidity_metrics['bid'] > 0 and liquidity_metrics['ask'] > 0:
                spread = (liquidity_metrics['ask'] - liquidity_metrics['bid']) / liquidity_metrics['bid']
                liquidity_score = (liquidity_metrics['bid_size'] + liquidity_metrics['ask_size']) * (1 - spread)
            else:
                spread = 0
                liquidity_score = 0
            
            liquidity_metrics.update({
                'spread_pct': spread * 100,
                'liquidity_score': liquidity_score,
                'is_liquid': liquidity_score > 10000 and spread < 0.02  # Spread < 2%
            })
            
            # Limpiar suscripciones
            self.ib.cancelMktData(contract)
            self.ib.cancelMktDepth(contract)
            
            return liquidity_metrics
            
        except Exception as e:
            print(f"❌ Error obteniendo liquidez IBKR para {symbol}: {e}")
            return self.get_liquidity_fallback(symbol)
    
    def get_liquidity_fallback(self, symbol):
        """Fallback para liquidez usando yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d')
            
            if len(hist) > 0:
                avg_volume = hist['Volume'].mean()
                latest_close = hist['Close'].iloc[-1]
                
                return {
                    'avg_volume': avg_volume,
                    'latest_close': latest_close,
                    'is_liquid': avg_volume > self.min_avg_volume,
                    'spread_pct': 1.0,  # Estimación conservadora
                    'liquidity_score': avg_volume / 1000
                }
        except:
            pass
        
        return {'is_liquid': False, 'avg_volume': 0}
    
    def get_earnings_transcript_sentiment(self, symbol, earnings_date):
        """Análisis de sentiment de transcripts de earnings"""
        try:
            # En producción usarías APIs como Sentieo, FactSet o scraping de Seeking Alpha
            # Aquí simulo con análisis de noticias financieras
            
            # Buscar noticias relacionadas con earnings
            end_date = earnings_date + timedelta(days=1)
            start_date = earnings_date - timedelta(days=1)
            
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            relevant_texts = []
            
            # Filtrar noticias del período de earnings
            for item in news[:5]:  # Top 5 noticias recientes
                try:
                    news_date = datetime.fromtimestamp(item['providerPublishTime'])
                    if start_date <= news_date <= end_date:
                        title = item.get('title', '')
                        summary = item.get('summary', '')
                        relevant_texts.append(f"{title}. {summary}")
                except:
                    continue
            
            if not relevant_texts:
                return {'sentiment_score': 0, 'confidence': 0, 'analysis': 'No transcript data'}
            
            # Análisis de sentiment combinado
            combined_text = ' '.join(relevant_texts)
            
            # Sentiment básico con TextBlob
            blob = TextBlob(combined_text)
            polarity = blob.sentiment.polarity  # -1 (negativo) a 1 (positivo)
            
            # Análisis específico de earnings usando keywords
            earnings_keywords = {
                'positive': ['beat', 'exceed', 'strong', 'growth', 'optimistic', 'bullish', 
                           'outperform', 'robust', 'solid', 'momentum'],
                'negative': ['miss', 'disappoint', 'weak', 'decline', 'concern', 'bearish',
                           'underperform', 'struggle', 'challenge', 'headwind']
            }
            
            text_lower = combined_text.lower()
            pos_count = sum(text_lower.count(word) for word in earnings_keywords['positive'])
            neg_count = sum(text_lower.count(word) for word in earnings_keywords['negative'])
            
            # Combinar sentiment general con keywords específicos
            keyword_sentiment = (pos_count - neg_count) / max(pos_count + neg_count, 1)
            final_sentiment = (polarity + keyword_sentiment) / 2
            
            # Calcular confianza basada en cantidad de texto
            confidence = min(len(combined_text) / 500, 1.0)  # Máx 1.0
            
            return {
                'sentiment_score': final_sentiment,  # -1 a 1
                'confidence': confidence,  # 0 a 1
                'positive_keywords': pos_count,
                'negative_keywords': neg_count,
                'analysis': f"Sentiment: {final_sentiment:.2f}, Keywords: +{pos_count}/-{neg_count}"
            }
            
        except Exception as e:
            print(f"❌ Error en análisis de sentiment para {symbol}: {e}")
            return {'sentiment_score': 0, 'confidence': 0, 'analysis': 'Error en análisis'}
    
    def enhanced_screening(self, target_date):
        """Screening mejorado con datos de AV, IBKR y sentiment"""
        print(f"🔍 Screening mejorado para {target_date.strftime('%Y-%m-%d')}")
        
        # 1. Obtener earnings del calendario
        earnings_df = self.get_earnings_calendar_av()
        if earnings_df.empty:
            print("❌ No se pudieron obtener datos de earnings")
            return []
        
        # Filtrar earnings en el rango de fechas (últimos 3 días)
        date_range = [target_date - timedelta(days=i) for i in range(4)]
        recent_earnings = earnings_df[earnings_df['reportDate'].dt.date.isin([d.date() for d in date_range])]
        
        candidates = []
        
        for _, earning in recent_earnings.iterrows():
            symbol = earning['symbol']
            earnings_date = earning['reportDate']
            
            print(f"📊 Analizando {symbol} (earnings: {earnings_date.strftime('%Y-%m-%d')})")
            
            try:
                # 2. Verificar liquidez en tiempo real
                liquidity = self.get_realtime_liquidity_ibkr(symbol)
                
                if not liquidity['is_liquid']:
                    print(f"   ❌ {symbol}: Liquidez insuficiente")
                    continue
                
                # 3. Obtener datos de precio y calcular earnings surprise
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=earnings_date - timedelta(days=5), 
                                    end=target_date + timedelta(days=1))
                
                if len(hist) < 3:
                    continue
                
                # Encontrar día de earnings
                earnings_day = hist.loc[hist.index.date == earnings_date.date()]
                if earnings_day.empty:
                    # Buscar día más cercano con volumen alto
                    hist['volume_spike'] = hist['Volume'] / hist['Volume'].rolling(3).mean()
                    earnings_day = hist.loc[hist['volume_spike'].idxmax():hist['volume_spike'].idxmax()]
                
                if earnings_day.empty:
                    continue
                
                # Calcular earnings surprise
                pre_earnings_close = hist['Close'].iloc[0]
                earnings_close = earnings_day['Close'].iloc[0]
                earnings_return = (earnings_close - pre_earnings_close) / pre_earnings_close
                
                # 4. Análisis de sentiment
                sentiment = self.get_earnings_transcript_sentiment(symbol, earnings_date)
                
                # 5. Generar señal mejorada
                current_price = hist['Close'].iloc[-1] if len(hist) > 0 else earnings_close
                
                # Lógica de señal mejorada con sentiment
                signal_strength = abs(earnings_return)
                sentiment_score = sentiment['sentiment_score']
                sentiment_confidence = sentiment['confidence']
                
                # Ajustar señal con sentiment
                if earnings_return > 0.05:  # Earnings beat
                    if sentiment_score > 0.2 and sentiment_confidence > 0.3:
                        # Sentiment confirma el beat - señal fuerte
                        signal_type = 'STRONG_BUY'
                        expected_return = 0.15
                    elif sentiment_score < -0.2:
                        # Sentiment contradice - posible reversión
                        continue  # Skip esta señal
                    else:
                        signal_type = 'BUY'
                        expected_return = 0.10
                        
                elif earnings_return < -0.05:  # Earnings miss
                    if sentiment_score < -0.2 and sentiment_confidence > 0.3:
                        # Sentiment confirma el miss - señal fuerte bajista
                        signal_type = 'STRONG_SELL'
                        expected_return = -0.15
                    elif sentiment_score > 0.2:
                        # Sentiment contradice - posible reversión alcista
                        signal_type = 'CONTRARIAN_BUY'
                        expected_return = 0.08
                    else:
                        signal_type = 'SELL'
                        expected_return = -0.10
                else:
                    continue  # Earnings neutros
                
                candidate = {
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'current_price': current_price,
                    'earnings_return': earnings_return,
                    'sentiment_score': sentiment_score,
                    'sentiment_confidence': sentiment_confidence,
                    'liquidity_score': liquidity['liquidity_score'],
                    'spread_pct': liquidity.get('spread_pct', 1.0),
                    'avg_volume': liquidity['avg_volume'],
                    'expected_return': expected_return,
                    'signal_date': target_date,
                    'earnings_date': earnings_date,
                    'analysis': sentiment['analysis']
                }
                
                candidates.append(candidate)
                print(f"   ✅ {symbol}: {signal_type} - Sentiment: {sentiment_score:.2f}")
                
            except Exception as e:
                print(f"   ❌ Error procesando {symbol}: {e}")
                continue
        
        # Ordenar por fuerza de señal
        candidates.sort(key=lambda x: abs(x['expected_return']), reverse=True)
        
        return candidates[:10]  # Top 10 señales
    
    def generate_enhanced_signals(self, date):
        """Genera señales mejoradas con todos los filtros"""
        candidates = self.enhanced_screening(date)
        signals = []
        
        for candidate in candidates:
            if candidate['signal_type'] in ['STRONG_BUY', 'BUY', 'CONTRARIAN_BUY']:
                action = 'BUY'
                stop_multiplier = 0.92
                profit_multiplier = 1 + abs(candidate['expected_return'])
            else:
                action = 'SELL_SHORT'
                stop_multiplier = 1.08
                profit_multiplier = 1 - abs(candidate['expected_return'])
            
            signal = {
                'symbol': candidate['symbol'],
                'action': action,
                'signal_strength': candidate['signal_type'],
                'price': candidate['current_price'],
                'date': date,
                'stop_loss': candidate['current_price'] * stop_multiplier,
                'take_profit': candidate['current_price'] * profit_multiplier,
                'expected_hold_days': 7 if 'STRONG' in candidate['signal_type'] else 5,
                'earnings_return': candidate['earnings_return'],
                'sentiment_score': candidate['sentiment_score'],
                'sentiment_confidence': candidate['sentiment_confidence'],
                'liquidity_score': candidate['liquidity_score'],
                'spread_pct': candidate['spread_pct'],
                'reason': f"Earnings: {candidate['earnings_return']:.2%}, "
                         f"Sentiment: {candidate['sentiment_score']:.2f}, "
                         f"Type: {candidate['signal_type']}"
            }
            
            signals.append(signal)
        
        return signals
    
    def enhanced_backtest(self, start_date, end_date):
        """Backtest mejorado con todas las funcionalidades"""
        print("🚀 ENHANCED PEAD STRATEGY BACKTEST")
        print("=" * 60)
        print(f"📅 Período: {start_date} a {end_date}")
        print(f"🔗 Alpha Vantage: {'✅' if self.av_key else '❌'}")
        print(f"🔗 IBKR: {'✅' if self.ib else '❌'}")
        print("=" * 60)
        
        # Conectar a IBKR si no está conectado
        if not self.ib:
            self.connect_ibkr()
        
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        all_trades = []
        active_positions = []
        
        while current_date <= end_dt:
            if current_date.weekday() < 5:  # Solo días laborables
                
                # Generar señales mejoradas
                signals = self.generate_enhanced_signals(current_date)
                
                for signal in signals:
                    print(f"\n📊 {signal['date'].strftime('%Y-%m-%d')} | "
                          f"{signal['action']} {signal['symbol']} @ ${signal['price']:.2f}")
                    print(f"   🎯 Strength: {signal['signal_strength']}")
                    print(f"   📈 TP: ${signal['take_profit']:.2f} | 🛑 SL: ${signal['stop_loss']:.2f}")
                    print(f"   💭 {signal['reason']}")
                    print(f"   💧 Liquidity: {signal['liquidity_score']:.0f} | Spread: {signal['spread_pct']:.2f}%")
                    
                    active_positions.append(signal)
                
                # Gestión de posiciones activas (igual que antes pero con métricas mejoradas)
                positions_to_close = []
                for i, position in enumerate(active_positions):
                    days_held = (current_date - position['date']).days
                    
                    try:
                        ticker = yf.Ticker(position['symbol'])
                        hist = ticker.history(start=current_date, end=current_date + timedelta(days=1))
                        
                        if not hist.empty:
                            current_price = hist['Close'].iloc[-1]
                            
                            should_close = False
                            close_reason = ""
                            
                            if position['action'] == 'BUY':
                                if current_price >= position['take_profit']:
                                    should_close, close_reason = True, "Take Profit"
                                elif current_price <= position['stop_loss']:
                                    should_close, close_reason = True, "Stop Loss"
                                elif days_held >= position['expected_hold_days']:
                                    should_close, close_reason = True, "Max Hold"
                                    
                            else:  # SELL_SHORT
                                if current_price <= position['take_profit']:
                                    should_close, close_reason = True, "Take Profit"
                                elif current_price >= position['stop_loss']:
                                    should_close, close_reason = True, "Stop Loss"
                                elif days_held >= position['expected_hold_days']:
                                    should_close, close_reason = True, "Max Hold"
                            
                            if should_close:
                                pnl_pct = ((current_price - position['price']) / position['price'] 
                                          if position['action'] == 'BUY' 
                                          else (position['price'] - current_price) / position['price'])
                                
                                trade_result = {
                                    'symbol': position['symbol'],
                                    'action': position['action'],
                                    'signal_strength': position['signal_strength'],
                                    'entry_date': position['date'],
                                    'exit_date': current_date,
                                    'entry_price': position['price'],
                                    'exit_price': current_price,
                                    'days_held': days_held,
                                    'pnl_pct': pnl_pct,
                                    'close_reason': close_reason,
                                    'earnings_return': position['earnings_return'],
                                    'sentiment_score': position['sentiment_score'],
                                    'sentiment_confidence': position['sentiment_confidence']
                                }
                                
                                all_trades.append(trade_result)
                                positions_to_close.append(i)
                                
                                print(f"🔄 {position['symbol']}: {pnl_pct:.2%} ({close_reason})")
                                
                    except Exception as e:
                        print(f"❌ Error procesando {position['symbol']}: {e}")
                        continue
                
                for i in sorted(positions_to_close, reverse=True):
                    active_positions.pop(i)
            
            current_date += timedelta(days=1)
        
        # Análisis mejorado de resultados
        if all_trades:
            df_trades = pd.DataFrame(all_trades)
            self.enhanced_analysis(df_trades)
        else:
            print("❌ No se generaron trades en el período")
    
    def enhanced_analysis(self, df_trades):
        """Análisis mejorado de resultados"""
        print("\n" + "=" * 60)
        print("📈 ANÁLISIS AVANZADO DE RESULTADOS")
        print("=" * 60)
        
        # Métricas básicas
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['pnl_pct'] > 0])
        win_rate = winning_trades / total_trades * 100
        
        avg_return = df_trades['pnl_pct'].mean() * 100
        total_return = df_trades['pnl_pct'].sum() * 100
        
        print(f"📊 MÉTRICAS GENERALES:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Retorno Promedio: {avg_return:.2f}%")
        print(f"   Retorno Acumulado: {total_return:.2f}%")
        
        # Análisis por tipo de señal
        print(f"\n🎯 POR TIPO DE SEÑAL:")
        signal_analysis = df_trades.groupby('signal_strength').agg({
            'pnl_pct': ['count', 'mean', 'std'],
        }).round(4)
        
        for signal_type in df_trades['signal_strength'].unique():
            subset = df_trades[df_trades['signal_strength'] == signal_type]
            win_rate_signal = (subset['pnl_pct'] > 0).mean() * 100
            avg_return_signal = subset['pnl_pct'].mean() * 100
            
            print(f"   {signal_type}: {len(subset)} trades, "
                  f"WR: {win_rate_signal:.1f}%, "
                  f"Avg: {avg_return_signal:.2f}%")
        
        # Análisis de sentiment
        print(f"\n💭 ANÁLISIS DE SENTIMENT:")
        high_confidence = df_trades[df_trades['sentiment_confidence'] > 0.5]
        if len(high_confidence) > 0:
            print(f"   High Confidence Sentiment: {len(high_confidence)} trades, "
                  f"Avg Return: {high_confidence['pnl_pct'].mean()*100:.2f}%")
        
        positive_sentiment = df_trades[df_trades['sentiment_score'] > 0.2]
        negative_sentiment = df_trades[df_trades['sentiment_score'] < -0.2]
        
        if len(positive_sentiment) > 0:
            print(f"   Positive Sentiment: {len(positive_sentiment)} trades, "
                  f"Avg Return: {positive_sentiment['pnl_pct'].mean()*100:.2f}%")
        
        if len(negative_sentiment) > 0:
            print(f"   Negative Sentiment: {len(negative_sentiment)} trades, "
                  f"Avg Return: {negative_sentiment['pnl_pct'].mean()*100:.2f}%")

# Configuración y uso
if __name__ == "__main__":
    # ⚠️ REEMPLAZA CON TU API KEY DE ALPHA VANTAGE
    AV_API_KEY = "TU_ALPHA_VANTAGE_API_KEY"
    
    # Inicializar estrategia mejorada
    strategy = EnhancedPEADStrategy(AV_API_KEY)
    
    print("🚀 CONFIGURACIÓN:")
    print(f"✅ Alpha Vantage API configurada")
    print(f"🔗 Intentando conexión IBKR...")
    
    # Intentar conectar IBKR
    ibkr_connected = strategy.connect_ibkr()
    
    if not ibkr_connected:
        print("⚠️ Continuando sin IBKR (usando datos históricos)")
    
    # Ejecutar backtest mejorado
    print("\n" + "="*50)
    strategy.enhanced_backtest('2024-01-01', '2024-03-31')
    
    # Señales actuales
    print("\n" + "="*50)
    print("🔴 SEÑALES ACTUALES MEJORADAS")
    print("="*50)
    
    today = datetime.now()
    current_signals = strategy.generate_enhanced_signals(today)
    
    if current_signals:
        for signal in current_signals:
            print(f"\n🎯 {signal['action']} {signal['symbol']} @ ${signal['price']:.2f}")
            print(f"   🏆 Strength: {signal['signal_strength']}")
            print(f"   📈 Take Profit: ${signal['take_profit']:.2f}")
            print(f"   🛑 Stop Loss: ${signal['stop_loss']:.2f}")
            print(f"   💭 Sentiment: {signal['sentiment_score']:.2f} "
                  f"(Conf: {signal['sentiment_confidence']:.2f})")
            print(f"   💧 Liquidity Score: {signal['liquidity_score']:.0f}")
            print(f"   📊 {signal['reason']}")
    else:
        print("Sin señales mejoradas para hoy")
        print("💡 Verifica conexiones API y que haya earnings recientes")
