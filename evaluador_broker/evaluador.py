import pandas as pd
import numpy as np
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from collections import defaultdict

class DataQualityTester(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = defaultdict(list)
        self.ready = False
        self.req_id_map = {}
        self.error_messages = []
        
    def error(self, reqId, errorCode, errorString):
        msg = f"Error: {reqId} {errorCode} {errorString}"
        print(msg)
        self.error_messages.append(msg)
        
    def historicalData(self, reqId, bar):
        symbol = self.req_id_map.get(reqId, "UNKNOWN")
        bar_dict = {
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "count": bar.barCount
        }
        # Solo añade 'wap' si existe
        if hasattr(bar, "wap"):
            bar_dict["wap"] = bar.wap
        self.data[symbol].append(bar_dict)

        
    def historicalDataEnd(self, reqId, start, end):
        print(f"Historical data received for reqId: {reqId} ({self.req_id_map.get(reqId)})")
        self.ready = True
        
def create_contract(symbol, sec_type="STK", exchange="SMART", currency="USD", primary_exchange=""):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.exchange = exchange
    contract.currency = currency
    if primary_exchange:
        contract.primaryExchange = primary_exchange
    return contract

def calculate_metrics(df, symbol):
    # Basic metrics
    metrics = {
        "symbol": symbol,
        "total_bars": len(df),
        "expected_bars": len(pd.date_range(start=df.index.min(), end=df.index.max(), freq='1min')),
        "zero_volume_bars": len(df[df['volume'] == 0]),
        "avg_daily_bars": len(df) / df.index.normalize().nunique(),
        "avg_spread_pct": (df['high'] - df['low']).mean() / df['close'].mean() * 100,
        "price_jumps": len(df[(df['high'] - df['low']) > (4 * (df['high'].shift(1) - df['low'].shift(1)).abs())]),
        "volume_consistency": df['volume'].std() / df['volume'].mean(),
    }
    
    # Time gaps analysis
    time_diffs = df.index.to_series().diff().dt.total_seconds() / 60
    time_gaps = time_diffs[time_diffs > 1.5]  # More than 1.5 minutes gap
    metrics.update({
        "time_gaps_count": len(time_gaps),
        "max_time_gap": time_gaps.max() if not time_gaps.empty else 0,
        "avg_time_gap": time_gaps.mean() if not time_gaps.empty else 0,
    })
    
    # Price stability metrics (important for penny stocks)
    metrics.update({
        "zero_move_bars": len(df[df['high'] == df['low']]),
        "wick_ratio": ((df['high'] - df['close']) + (df['close'] - df['low'])).mean() / (df['high'] - df['low']).mean(),
        "overnight_gaps_pct": (df['open'] - df['close'].shift(1)).abs().mean() / df['close'].mean() * 100,
    })
    
    # Liquidity metrics
    metrics.update({
        "avg_volume": df['volume'].mean(),
        "median_volume": df['volume'].median(),
        "volume_imbalance": (df['volume'].max() - df['volume'].min()) / df['volume'].max(),
    })
    
    # Calculate missing bars ratio based on actual trading hours
    trading_hours = 6.5  # Typical US equity trading hours (9:30-16:00)
    expected_daily_bars = int(trading_hours * 60)
    actual_days = df.index.normalize().nunique()
    metrics["missing_bars_ratio"] = 1 - (len(df) / (expected_daily_bars * actual_days))
    
    return metrics

from datetime import timezone

def test_data_quality(app, contract, days=3, timeout=30):
    symbol = contract.symbol
    print(f"\nRequesting data for {symbol}...")

    # Fecha de fin en UTC con formato correcto y zona horaria explícita
    end_date = datetime.now(timezone.utc).strftime('%Y%m%d %H:%M:%S') + " UTC"
    
    req_id = hash(symbol) % 100000
    app.req_id_map[req_id] = symbol
    app.ready = False
    app.data[symbol] = []  # Limpiar datos previos para este símbolo

    # Solicitar datos históricos
    app.reqHistoricalData(
        reqId=req_id,
        contract=contract,
        endDateTime=end_date,
        durationStr=f"{days} D",
        barSizeSetting="1 min",
        whatToShow="TRADES",
        useRTH=0,  # Todos los datos, incluyendo fuera del horario regular
        formatDate=1,
        keepUpToDate=False,
        chartOptions=[]
    )
    
    # Esperar activamente procesando mensajes
    start_time = time.time()
    while not app.ready and (time.time() - start_time) < timeout:
        app.run()  # Procesar mensajes entrantes
        time.sleep(0.1)  # Pequeña pausa para no consumir demasiada CPU
    
    if not app.ready:
        print(f"Timeout waiting for data for {symbol}")
        return None, None
    
    # Procesar los datos recibidos
    df = pd.DataFrame(app.data[symbol])
    if df.empty:
        print(f"No data received for {symbol}")
        return None, None
    
    # Convertir y ordenar los datos
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)
    
    # Calcular métricas
    metrics = calculate_metrics(df, symbol)
    
    # Resetear para la próxima solicitud
    app.ready = False
    
    return df, metrics

def visualize_comparison(metrics_list):
    metrics_df = pd.DataFrame(metrics_list)
    
    # Group by market cap category for comparison
    categories = {
        'Penny Stocks': ['GORV', 'IMNN', 'MMAT'],
        'Small Caps': ['SNDL', 'FCEL', 'ATER'],
        'Middle Caps': ['PLTR', 'RKT', 'FUBO'],
        'Large Caps': ['AAPL', 'MSFT', 'AMZN']
    }
    
    # Add category column
    metrics_df['category'] = ''
    for category, symbols in categories.items():
        metrics_df.loc[metrics_df['symbol'].isin(symbols), 'category'] = category
    
    # Plot comparison metrics
    fig, axes = plt.subplots(3, 2, figsize=(15, 15))
    
    # Missing bars ratio
    metrics_df.groupby('category')['missing_bars_ratio'].mean().plot.bar(
        ax=axes[0, 0], title='Missing Bars Ratio', ylabel='Ratio')
    
    # Zero volume bars
    metrics_df.groupby('category')['zero_volume_bars'].mean().plot.bar(
        ax=axes[0, 1], title='Avg Zero Volume Bars', ylabel='Count')
    
    # Average spread
    metrics_df.groupby('category')['avg_spread_pct'].mean().plot.bar(
        ax=axes[1, 0], title='Average Spread %', ylabel='Percentage')
    
    # Price jumps
    metrics_df.groupby('category')['price_jumps'].mean().plot.bar(
        ax=axes[1, 1], title='Price Jumps Count', ylabel='Count')
    
    # Volume consistency
    metrics_df.groupby('category')['volume_consistency'].mean().plot.bar(
        ax=axes[2, 0], title='Volume Consistency (Std/Mean)', ylabel='Ratio')
    
    # Overnight gaps
    metrics_df.groupby('category')['overnight_gaps_pct'].mean().plot.bar(
        ax=axes[2, 1], title='Avg Overnight Gap %', ylabel='Percentage')
    
    plt.tight_layout()
    plt.show()
    
    return metrics_df

def main():
    # Initialize IBKR connection
    app = DataQualityTester()
    
    print("Conectando a TWS/IB Gateway...")
    app.connect("127.0.0.1", 7497, clientId=0)
    
    # Espera activa por conexión con timeout
    print("Esperando conexión...")
    start_time = time.time()
    while not app.isConnected() and (time.time() - start_time) < 10:  # 10 segundos timeout
        app.run()  # Procesa mensajes entrantes
        time.sleep(0.1)
    
    if not app.isConnected():
        print("\nError: No se pudo conectar a TWS/IB Gateway. Verifica:")
        print("1. Que TWS o IB Gateway estén ejecutándose")
        print("2. Que la API esté habilitada en Configuración -> API")
        print("3. Que el puerto (7497) y dirección IP (127.0.0.1) sean correctos")
        print("4. Que no haya otro programa usando el mismo clientId (0)")
        print("\nMensajes de error recibidos:")
        for error in app.error_messages:
            print(f"- {error}")
        return
    
    print("\nConexión establecida correctamente con TWS/IB Gateway")
    
    # Define test universe
    test_universe = [
        create_contract("AAPL", primary_exchange="NASDAQ"),
        create_contract("MSFT", primary_exchange="NASDAQ"),
        create_contract("AMZN", primary_exchange="NASDAQ")
    ]
    
    all_metrics = []
    successful_dfs = {}
    
    for contract in test_universe:
        try:
            print(f"\nSolicitando datos para {contract.symbol}...")
            df, metrics = test_data_quality(app, contract, days=3)
            
            if df is not None and metrics is not None:
                all_metrics.append(metrics)
                successful_dfs[contract.symbol] = df
                
                print(f"\nMétricas para {contract.symbol}:")
                for k, v in metrics.items():
                    print(f"{k:>25}: {v}")
            else:
                print(f"No se recibieron datos para {contract.symbol}")
                
        except Exception as e:
            print(f"Error probando {contract.symbol}: {str(e)}")
    
    # Visual comparison if we got data
    if all_metrics:
        metrics_df = visualize_comparison(all_metrics)
        print("\nResumen comparativo de métricas:")
        print(metrics_df.groupby('category').mean()[
            ['missing_bars_ratio', 'zero_volume_bars', 'avg_spread_pct', 
             'price_jumps', 'volume_consistency', 'overnight_gaps_pct']
        ].round(3))
    else:
        print("\nNo se obtuvieron datos para generar comparaciones")
    
    # Disconnect
    app.disconnect()
    print("\nDesconectado de TWS/IB Gateway")

if __name__ == "__main__":
    main()
    