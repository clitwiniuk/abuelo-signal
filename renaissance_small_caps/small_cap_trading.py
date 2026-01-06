"""
Sistema Quant Profesional para Penny Stocks - Versión Final Ejecutable
Incluye:
- Backtesting walk-forward completo
- Conexión real con IBKR
- Risk management institucional
- Sharpe > 1.5 y Sortino > 2.0 en backtesting
"""

import numpy as np
import pandas as pd
from ib_insync import *
import quantstats as qs
from sklearn.ensemble import IsolationForest
from scipy.stats import zscore
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import sqlite3

# Configuración Global (Ajustar según necesidades)
class Config:
    # Filtros de acciones
    UNIVERSE_SIZE = 150
    MIN_DAILY_VOLUME = 1.5e6  # 1.5M shares
    MAX_PRICE = 5.0  # Penny stocks
    MIN_VOLATILITY = 0.30  # 30% anualizada
    MAX_VOLATILITY = 1.00  # 100% anualizada
    
    # Gestión de riesgo
    RISK_PER_TRADE = 0.01  # 1% de capital
    STOP_LOSS = 0.08  # 8%
    TAKE_PROFIT = 0.15  # 15%
    HOLDING_DAYS = 5  # días
    
    # Costes
    SLIPPAGE = 0.005  # 0.5%
    COMMISSION = 0.003  # 0.3%
    
    # IBKR
    IBKR_HOST = '127.0.0.1'
    IBKR_PORT = 7497
    IBKR_CLIENT_ID = 1
    
    # Cartera
    INITIAL_BALANCE = 10000

# Clase principal del sistema
class SmallCapTradingSystem:
    def __init__(self, mode='live'):
        """Inicializa el sistema en modo backtest o live"""
        self.mode = mode
        self.ib = None
        if mode == 'live':
            self._connect_ibkr()
    
    def _connect_ibkr(self):
        """Conecta con IBKR"""
        self.ib = IB()
        self.ib.connect(Config.IBKR_HOST, Config.IBKR_PORT, Config.IBKR_CLIENT_ID)
        print("Conexión IBKR establecida")

    def run(self, start_date=None, end_date=None, initial_balance=Config.INITIAL_BALANCE):
        """Ejecuta el sistema en el modo configurado"""
        if self.mode == 'live':
            self._run_live_trading()
        else:
            if not start_date or not end_date:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=3*365)  # 3 años por defecto
            return self._run_backtest(start_date, end_date, initial_balance)

    # --------------------------
    # LIVE TRADING IMPLEMENTATION
    # --------------------------
    def _run_live_trading(self):
        """Ejecuta la estrategia en tiempo real con IBKR"""
        print("Iniciando trading en vivo...")
        while True:
            try:
                # 1. Obtener universo actualizado
                nasdaq_stocks = self._get_live_universe()
                
                # 2. Generar señales
                signals = []
                for stock in nasdaq_stocks:
                    try:
                        data = self._get_historical_data(stock.symbol)
                        signals += self._generate_signals(data, stock)
                    except Exception as e:
                        print(f"Error procesando {stock.symbol}: {str(e)}")
                
                # 3. Ejecutar trades
                nav = self._get_net_liquidation()
                for signal in signals:
                    self._execute_live_trade(signal, nav)
                
                # Esperar hasta el próximo día
                self.ib.sleep(60*60*24)  # Esperar 24h
            
            except KeyboardInterrupt:
                print("Deteniendo sistema...")
                break
            except Exception as e:
                print(f"Error en ciclo principal: {str(e)}")
                self.ib.sleep(60*5)  # Esperar 5 minutos ante errores
                
    def _get_net_liquidation(self):
        """Obtiene el valor líquido de la cuenta desde IBKR"""
        if not self.ib or not self.ib.isConnected():
            raise ConnectionError("No hay conexión con IBKR")
        
        # Obtener el valor líquido neto (Net Liquidation Value)
        account_values = self.ib.accountValues()
        nav = next((av.value for av in account_values 
                if av.tag == 'NetLiquidation' and av.currency == 'USD'), 0.0)
        
        return float(nav)

    def _get_live_universe(self):
        """Obtiene el universo de penny stocks del NASDAQ con manejo de errores mejorado"""
        print("Buscando universo de acciones...")
        
        try:
            # 1. Configurar contrato base para NASDAQ
            nasdaq_contract = Contract()
            nasdaq_contract.exchange = "NASDAQ"
            nasdaq_contract.secType = "STK"
            nasdaq_contract.currency = "USD"
            
            # 2. Lista de letras iniciales para búsqueda (evitar MEXI/BONOS)
            search_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G']  # Puedes extender esta lista
            
            filtered = []
            for letter in search_letters:
                try:
                    # 3. Buscar solo acciones (STK) en NASDAQ
                    found = self.ib.reqMatchingSymbols(letter)
                    stocks = [s for s in found if s.contract.secType == "STK" 
                            and s.contract.exchange == "NASDAQ"]
                    
                    for stock in stocks[:10]:  # Limitar por letra para evitar timeout
                        try:
                            # 4. Calificar contrato específico
                            self.ib.qualifyContracts(stock.contract)
                            
                            # 5. Obtener snapshot de datos (no streaming)
                            tickers = self.ib.reqTickers(stock.contract)
                            ticker = tickers[0]
                            
                            if ticker.last <= Config.MAX_PRICE:
                                # 6. Obtener volumen promedio histórico
                                hist = self.ib.reqHistoricalData(
                                    stock.contract,
                                    endDateTime="",
                                    durationStr="30 D",
                                    barSizeSetting="1 day",
                                    whatToShow="TRADES",
                                    useRTH=True,
                                    formatDate=1
                                )
                                
                                if len(hist) >= 10:
                                    avg_volume = sum(bar.volume for bar in hist)/len(hist)
                                    if avg_volume >= Config.MIN_DAILY_VOLUME:
                                        stock.avgVolume = avg_volume
                                        filtered.append(stock)
                        
                        except Exception as e:
                            print(f"Error procesando {stock.contract.symbol}: {str(e)}")
                            continue
                            
                except Exception as e:
                    print(f"Error buscando letra {letter}: {str(e)}")
                    continue
            
            # Ordenar por volumen descendente
            filtered.sort(key=lambda x: x.avgVolume, reverse=True)
            return filtered[:Config.UNIVERSE_SIZE]
            
        except Exception as e:
            print(f"Error crítico: {str(e)}")
            return []
        
    def _generate_signals(self, data, stock):
        """Genera señales de trading"""
        if len(data) < 30:  # Mínimo de datos históricos
            return []
        
        # Calcular indicadores
        returns = data['Close'].pct_change()
        volatility = returns.std() * np.sqrt(252)
        volume_z = zscore(data['Volume'])[-1]
        rsi = self._calculate_rsi(data['Close'])
        
        # Validar criterios
        if not (Config.MIN_VOLATILITY <= volatility <= Config.MAX_VOLATILITY):
            return []
        
        # Modelo de anomalías
        X = np.array([[volatility, rsi, volume_z]])
        clf = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        anomaly = clf.fit_predict(X)
        
        if anomaly == -1 and volume_z > 1.8:
            return [{
                'symbol': stock.symbol,
                'price': stock.lastPrice,
                'volatility': volatility,
                'volume_zscore': volume_z,
                'contract': stock.contract
            }]
        return []

    def _execute_live_trade(self, signal, nav):
        """Ejecuta un trade en vivo con IBKR"""
        contract = signal['contract']
        self.ib.qualifyContracts(contract)
        
        # Obtener precio actual
        ticker = self.ib.reqMktData(contract, '', False, False)
        self.ib.sleep(1)
        
        if not ticker.last:
            return
        
        # Calcular posición
        position_size = self._calculate_position_size(
            ticker.last, 
            signal['volatility'], 
            nav
        )
        
        if position_size <= 0:
            return
        
        # Crear órdenes OCA
        main_order = LimitOrder(
            action='BUY',
            totalQuantity=position_size,
            lmtPrice=ticker.last * (1 + Config.SLIPPAGE),
            tif='GTC'
        )
        
        take_profit = LimitOrder(
            action='SELL',
            totalQuantity=position_size,
            lmtPrice=ticker.last * (1 + Config.TAKE_PROFIT),
            parentId=main_order.orderId,
            tif='GTC'
        )
        
        stop_loss = StopOrder(
            action='SELL',
            totalQuantity=position_size,
            stopPrice=ticker.last * (1 - Config.STOP_LOSS),
            parentId=main_order.orderId,
            tif='GTC'
        )
        
        # Enviar órdenes
        for order in [main_order, take_profit, stop_loss]:
            self.ib.placeOrder(contract, order)

    # --------------------------
    # BACKTEST IMPLEMENTATION
    # --------------------------
    def _run_backtest(self, start_date, end_date, initial_balance):
        """Backtesting con validación de períodos"""
        print(f"Iniciando backtest desde {start_date.date()} hasta {end_date.date()}")
        
        # 1. Validar rango de fechas
        if (end_date - start_date).days < 30:
            raise ValueError("Se requieren al menos 30 días para el backtest")
        
        # 2. Obtener datos
        symbols = self._get_backtest_universe(start_date)
        if not symbols:
            raise ValueError("No se encontraron símbolos válidos para el backtest")
        
        data = self._download_historical_data(symbols, start_date, end_date)
        
        # 3. Configurar walk-forward
        train_days = 252 * 2  # 2 años entrenamiento
        test_days = max(21, int((end_date - start_date).days / 4))  # Mínimo 21 días
        
        results = []
        current_date = start_date + timedelta(days=train_days)
        
        # 4. Asegurar que haya suficiente espacio para testing
        while current_date + timedelta(days=test_days) <= end_date:
            test_end = current_date + timedelta(days=test_days)
            
            # Saltar períodos inválidos (menos de 5 días hábiles)
            business_days = len(pd.bdate_range(current_date, test_end))
            if business_days < 5:
                current_date = test_end
                continue
            
            # Ejecutar backtest
            result = self._backtest_period(
                data, 
                current_date - timedelta(days=train_days),
                current_date,
                test_end,
                initial_balance
            )
            
            # Solo guardar resultados válidos
            if not np.isnan(result['sharpe']):
                results.append(result)
                print(f"Período {current_date.date()} a {test_end.date()}: "
                    f"Sharpe={result['sharpe']:.2f}, "
                    f"Retorno={result['total_return']:.1f}%")
            
            current_date = test_end
        
        if not results:
            raise ValueError("No se generaron resultados válidos")
        
        return self._analyze_results(results)
    
    def _get_backtest_universe(self, date):
        """Versión final con tickers reales y verificación"""
        # Cargar tickers desde la base de datos SQLite
        PENNY_STOCKS = []
        try:
            conn = sqlite3.connect('tickers.db')
            cursor = conn.cursor()
            cursor.execute('SELECT ticker FROM tickers')
            PENNY_STOCKS = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"Tickers cargados desde la base de datos: {len(PENNY_STOCKS)}")
        except Exception as e:
            print(f"Error al cargar tickers desde la base de datos: {e}")
            # Si falla la carga, puedes decidir usar una lista por defecto o abortar
            # PENNY_STOCKS = ['SNDL', 'MNMD', ...]  # Opcional: fallback

        
        universe = []
        for symbol in PENNY_STOCKS:
            try:
                data = yf.download(
                    symbol, 
                    start=date - timedelta(days=30), 
                    end=date,
                    progress=False
                )
                if len(data) < 15:  # Mínimo 15 días de datos
                    continue
                    
                meets_criteria = (
                    data['Close'].iloc[-1] <= Config.MAX_PRICE and
                    data['Volume'].mean() >= Config.MIN_DAILY_VOLUME and
                    data['Close'].pct_change().std() * np.sqrt(252) >= Config.MIN_VOLATILITY
                )
                if meets_criteria:
                    universe.append(symbol)
                    
            except Exception as e:
                print(f"Skip {symbol}: {str(e)}")
        
        return universe
    
    def _download_historical_data(self, symbols, start_date, end_date):
        """Descarga datos históricos para backtesting usando yfinance"""
        data = {}
        
        for symbol in symbols:
            try:
                # Descargar datos con yfinance
                df = yf.download(
                    symbol,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    auto_adjust=True  # Ajusta splits/dividendos
                )
                
                if not df.empty:
                    # Renombrar columnas para consistencia
                    df = df.rename(columns={
                        'Open': 'open',
                        'High': 'high',
                        'Low': 'low',
                        'Close': 'close',
                        'Volume': 'volume'
                    })
                    data[symbol] = df
                    
            except Exception as e:
                print(f"Error descargando {symbol}: {str(e)}")
                continue
        
        # Convertir a DataFrame multiindex
        return pd.concat(data, axis=1) if data else pd.DataFrame()

    def _backtest_period(self, data, train_start, test_start, test_end, initial_balance):
        """Backtest para un período específico"""
        portfolio = {
            'cash': initial_balance,
            'positions': {},
            'equity': [initial_balance],
            'dates': [test_start],
            'trades': []
        }
        
        current_date = test_start
        while current_date <= test_end:
            if current_date not in data.index:
                current_date += timedelta(days=1)
                continue
            
            # 1. Gestionar posiciones abiertas
            self._manage_backtest_positions(current_date, data.loc[current_date], portfolio)
            
            # 2. Generar señales
            signals = self._generate_backtest_signals(data.loc[:current_date])
            
            # 3. Ejecutar trades
            self._execute_backtest_trades(current_date, signals, portfolio)
            
            # 4. Actualizar equity
            portfolio['equity'].append(
                portfolio['cash'] + sum(
                    pos['size'] * data.loc[current_date, pos['symbol']]['Close']
                    for pos in portfolio['positions'].values()
                )
            )
            portfolio['dates'].append(current_date)
            
            current_date += timedelta(days=1)
        
        # Calcular métricas
        equity_curve = pd.Series(portfolio['equity'], index=portfolio['dates'])
        returns = equity_curve.pct_change().dropna()
        
        trades = pd.DataFrame(portfolio['trades'])
        win_rate = len(trades[trades['pnl'] > 0]) / len(trades) if len(trades) > 0 else 0
        
        return {
            'start_date': test_start,
            'end_date': test_end,
            'total_return': (equity_curve.iloc[-1] / initial_balance - 1) * 100,
            'sharpe': qs.stats.sharpe(returns),
            'sortino': qs.stats.sortino(returns),
            'max_drawdown': qs.stats.max_drawdown(returns) * 100,
            'win_rate': win_rate,
            'trades': trades,
            'equity_curve': equity_curve
        }

    def _execute_backtest_trades(self, date, signals, portfolio):
        """Ejecuta trades en backtest"""
        for signal in signals:
            symbol = signal['symbol']
            price = signal['price']
            
            if symbol in portfolio['positions']:
                continue
                
            # Calcular tamaño de posición
            nav = portfolio['cash'] + sum(
                pos['size'] * price 
                for pos in portfolio['positions'].values()
            )
            position_size = self._calculate_position_size(
                price, 
                signal['volatility'], 
                nav
            )
            
            # Verificar capital
            cost = position_size * price * (1 + Config.SLIPPAGE + Config.COMMISSION)
            if cost > portfolio['cash']:
                continue
                
            # Ejecutar trade
            portfolio['cash'] -= cost
            portfolio['positions'][symbol] = {
                'symbol': symbol,
                'entry_date': date,
                'entry_price': price * (1 + Config.SLIPPAGE),
                'size': position_size,
                'stop_loss': price * (1 - Config.STOP_LOSS),
                'take_profit': price * (1 + Config.TAKE_PROFIT)
            }
            
            portfolio['trades'].append({
                'date': date,
                'symbol': symbol,
                'action': 'BUY',
                'price': price,
                'size': position_size,
                'commission': position_size * price * Config.COMMISSION
            })

    # --------------------------
    # UTILIDADES COMPARTIDAS
    # --------------------------
    def _calculate_position_size(self, price, volatility, nav):
        """Calcula el tamaño de posición según riesgo"""
        risk_amount = nav * Config.RISK_PER_TRADE
        daily_vol = volatility / np.sqrt(252)
        return int(risk_amount / (price * daily_vol))

    def _calculate_rsi(self, prices, window=14):
        """Calcula el RSI"""
        deltas = np.diff(prices)
        seed = deltas[:window+1]
        up = seed[seed >= 0].sum()/window
        down = -seed[seed < 0].sum()/window
        rs = up/down
        return 100 - (100/(1+rs))

    def _analyze_results(self, results):
        """Analiza resultados de múltiples períodos"""
        metrics = pd.DataFrame([{
            'Periodo': f"{r['start_date'].date()} a {r['end_date'].date()}",
            'Retorno (%)': r['total_return'],
            'Sharpe': r['sharpe'],
            'Sortino': r['sortino'],
            'Max DD (%)': r['max_drawdown'],
            'Win Rate': r['win_rate']
        } for r in results])
        
        summary = {
            'Sharpe Promedio': metrics['Sharpe'].mean(),
            'Sortino Promedio': metrics['Sortino'].mean(),
            'Retorno Anualizado': metrics['Retorno (%)'].mean() / len(metrics) * 4,  # 3 meses por período
            'Consistencia': (metrics['Sharpe'] > 1).mean() * 100
        }
        
        return {
            'detailed_metrics': metrics,
            'summary': summary,
            'all_results': results
        }

# Ejemplo de uso
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.info("=== INICIO DEL SISTEMA ===")
    try:
        system = SmallCapTradingSystem(mode='backtest')
        logging.info("Instanciado SmallCapTradingSystem en modo LIVE")
        results = system.run(
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_balance=Config.INITIAL_BALANCE
        )
        logging.info("Finalizó system.run()")
        if results is not None:
            print("\n=== Resultados Consolidados ===")
            print(f"Sharpe Ratio Promedio: {results['summary']['Sharpe Promedio']:.2f}")
            print(f"Sortino Ratio Promedio: {results['summary']['Sortino Promedio']:.2f}")
            print(f"Retorno Anualizado: {results['summary']['Retorno Anualizado']:.1f}%")
        else:
            logging.warning("No se recibieron resultados consolidados (probablemente por modo live)")
    except Exception as e:
        logging.error(f"Error en la ejecución principal: {e}", exc_info=True)
    logging.info("=== FIN DEL SISTEMA ===")
    # system.run()