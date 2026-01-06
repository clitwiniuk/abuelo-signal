import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.widgets import Button, RadioButtons
import os
from koncorde import calculate_koncorde

class KoncordeVisualizer:
    """
    Visualizador interactivo para precios y indicador Koncorde
    """
    
    def __init__(self, data_folder='./data'):
        self.data_folder = data_folder
        self.current_data = None
        self.current_koncorde = None
        self.current_symbol = None
        self.fig = None
        self.ax_price = None
        self.ax_koncorde = None
        
    def load_csv_files(self):
        """Cargar todos los archivos CSV disponibles"""
        csv_files = []
        for file in os.listdir(self.data_folder):
            if file.endswith('_1_min.csv'):
                symbol = file.replace('_1_min.csv', '')
                csv_files.append((symbol, file))
        return csv_files
    
    def load_data(self, symbol, file_name):
        """Cargar datos de un archivo CSV específico"""
        file_path = os.path.join(self.data_folder, file_name)
        
        # Leer CSV
        df = pd.read_csv(file_path)
        
        # Convertir timestamp a datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Renombrar columnas para que coincidan con el formato esperado
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        # Limpiar datos NaN
        df = df.dropna()
        
        print(f"Cargados {len(df)} registros para {symbol}")
        print(f"Período: {df.index[0]} a {df.index[-1]}")
        
        return df
    
    def calculate_indicators(self, df):
        """Calcular indicador Koncorde"""
        try:
            # Hacer una copia para no modificar el original
            df_copy = df.copy()
            koncorde_data = calculate_koncorde(df_copy)
            return koncorde_data
        except Exception as e:
            print(f"Error calculando Koncorde: {e}")
            return None
    
    def create_plot_with_date(self, symbol, df, koncorde_data, time_range, selected_date):
        """Crear gráfico con precio y Koncorde para una fecha específica"""
        # Filtrar datos según el rango de tiempo
        if time_range == '1M':
            # 1M = Todo el día a resolución de 1 minuto
            df_plot = df  # Todo el día
            koncorde_plot = koncorde_data
        elif time_range == '5M':
            df_plot = df.tail(5)  # Últimos 5 minutos
            koncorde_plot = koncorde_data.tail(5)
        elif time_range == '15M':
            df_plot = df.tail(15)  # Últimos 15 minutos
            koncorde_plot = koncorde_data.tail(15)
        elif time_range == '30M':
            df_plot = df.tail(30)  # Últimos 30 minutos
            koncorde_plot = koncorde_data.tail(30)
        elif time_range == '1H':
            df_plot = df.tail(60)  # Última hora
            koncorde_plot = koncorde_data.tail(60)
        elif time_range == '4H':
            df_plot = df.tail(240)  # Últimas 4 horas
            koncorde_plot = koncorde_data.tail(240)
        elif time_range == 'FULL_DAY':
            df_plot = df  # Todo el día
            koncorde_plot = koncorde_data
        else:
            df_plot = df
            koncorde_plot = koncorde_data
        
        # Crear figura con subplots
        self.fig, (self.ax_price, self.ax_koncorde) = plt.subplots(2, 1, figsize=(15, 12), 
                                                                   gridspec_kw={'height_ratios': [2, 1]})
        
        # Debug: verificar datos
        print(f"Debug - df_plot shape: {df_plot.shape}")
        print(f"Debug - koncorde_plot shape: {koncorde_plot.shape}")
        print(f"Debug - df_plot range: {df_plot.index[0] if len(df_plot) > 0 else 'empty'} to {df_plot.index[-1] if len(df_plot) > 0 else 'empty'}")
        
        # Gráfico de precio
        self.plot_price(df_plot, symbol)
        
        # Gráfico de Koncorde
        self.plot_koncorde(koncorde_plot)
        
        # Configurar formato de fechas para datos intraday
        self.setup_intraday_date_formatting(time_range)
        
        # Título principal con fecha
        self.fig.suptitle(f'{symbol} - {selected_date} - Precio y Koncorde ({time_range})', fontsize=16)
        
        plt.tight_layout()
        return self.fig
    
    def setup_intraday_date_formatting(self, time_range):
        """Configurar formato de fechas para datos intraday"""
        from matplotlib.ticker import MaxNLocator
        import matplotlib.dates as mdates
        
        # Configuración específica por rango de tiempo
        for ax in [self.ax_price, self.ax_koncorde]:
            if time_range == '1M':
                # Para 1M, mostrar hora:minuto:segundo
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                ax.xaxis.set_major_locator(mdates.SecondLocator(bysecond=[0, 15, 30, 45]))
            elif time_range in ['5M', '15M', '30M']:
                # Para rangos de minutos, mostrar hora:minuto
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 5)))
            elif time_range == '1H':
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 10)))
            elif time_range == '4H':
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 30)))
            elif time_range == 'FULL_DAY':
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 2)))
            
            # Aplicar limitador de ticks como respaldo
            current_locator = ax.xaxis.get_major_locator()
            ax.xaxis.set_major_locator(MaxNLocator(nbins=20, prune='both'))
            
            # Rotar etiquetas
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            # Configurar formato menor
            ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=range(0, 60, 1)))
            ax.xaxis.set_minor_formatter(mdates.DateFormatter(''))
    
    def plot_price(self, df, symbol):
        """Dibujar gráfico de precios"""
        print(f"Debug plot_price - df shape: {df.shape}")
        print(f"Debug plot_price - columns: {df.columns.tolist()}")
        
        if len(df) == 0:
            print("Warning: df está vacío")
            return
            
        self.ax_price.clear()
        
        # Si solo hay un punto, usar scatter en lugar de plot
        if len(df) == 1:
            self.ax_price.scatter(df.index, df['Close'], color='black', s=50, label='Close', zorder=5)
            # Añadir línea horizontal para referencia
            self.ax_price.axhline(y=df['Close'].iloc[0], color='black', linestyle='--', alpha=0.3)
        else:
            # Gráfico de línea del precio de cierre
            self.ax_price.plot(df.index, df['Close'], color='black', linewidth=2, label='Close', marker='o', markersize=3)
        
        # Añadir volumen como barras en segundo eje
        ax_vol = self.ax_price.twinx()
        if len(df) == 1:
            # Para un solo punto, hacer la barra más visible
            ax_vol.bar(df.index, df['Volume'], alpha=0.5, color='gray', width=pd.Timedelta(minutes=5))
        else:
            ax_vol.bar(df.index, df['Volume'], alpha=0.3, color='gray', width=pd.Timedelta(minutes=1))
        ax_vol.set_ylabel('Volume', color='gray')
        
        self.ax_price.set_ylabel('Precio')
        self.ax_price.legend()
        self.ax_price.grid(True, alpha=0.3)
        self.ax_price.set_title(f'{symbol} - Precio')
        
        print(f"Debug plot_price - price range: {df['Close'].min():.2f} to {df['Close'].max():.2f}")
    
    def plot_koncorde(self, koncorde_data):
        """Dibujar indicador Koncorde"""
        print(f"Debug plot_koncorde - shape: {koncorde_data.shape}")
        print(f"Debug plot_koncorde - columns: {koncorde_data.columns.tolist()}")
        
        if len(koncorde_data) == 0:
            print("Warning: koncorde_data está vacío")
            return
            
        self.ax_koncorde.clear()
        
        # Verificar que las columnas existen
        required_cols = ['verde', 'marron', 'azul', 'media']
        missing_cols = [col for col in required_cols if col not in koncorde_data.columns]
        if missing_cols:
            print(f"Warning: columnas faltantes en Koncorde: {missing_cols}")
            return
        
        if len(koncorde_data) == 1:
            # Para un solo punto, usar scatter
            self.ax_koncorde.scatter(koncorde_data.index, koncorde_data['verde'], 
                                   color='#006600', s=100, label='Verde', marker='s', zorder=5)
            self.ax_koncorde.scatter(koncorde_data.index, koncorde_data['marron'], 
                                   color='#330000', s=100, label='Marrón', marker='o', zorder=5)
            self.ax_koncorde.scatter(koncorde_data.index, koncorde_data['azul'], 
                                   color='#000066', s=100, label='Azul', marker='^', zorder=5)
            self.ax_koncorde.scatter(koncorde_data.index, koncorde_data['media'], 
                                   color='red', s=100, label='Media', marker='d', zorder=5)
            
            # Líneas horizontales para referencia
            for col, color in [('verde', '#66FF66'), ('marron', '#FFCC99'), 
                             ('azul', '#00FFFF'), ('media', 'red')]:
                self.ax_koncorde.axhline(y=koncorde_data[col].iloc[0], color=color, 
                                       linestyle='--', alpha=0.3)
        else:
            # Líneas del indicador para múltiples puntos
            self.ax_koncorde.fill_between(koncorde_data.index, 0, koncorde_data['verde'], 
                                         color='#66FF66', alpha=0.7, label='Verde')
            self.ax_koncorde.fill_between(koncorde_data.index, 0, koncorde_data['marron'], 
                                         color='#FFCC99', alpha=0.7, label='Marrón')
            self.ax_koncorde.fill_between(koncorde_data.index, 0, koncorde_data['azul'], 
                                         color='#00FFFF', alpha=0.7, label='Azul')
            
            # Líneas más marcadas
            self.ax_koncorde.plot(koncorde_data.index, koncorde_data['marron'], 
                                 color='#330000', linewidth=2, label='Marrón Line', marker='o', markersize=3)
            self.ax_koncorde.plot(koncorde_data.index, koncorde_data['verde'], 
                                 color='#006600', linewidth=2, label='Verde Line', marker='s', markersize=3)
            self.ax_koncorde.plot(koncorde_data.index, koncorde_data['azul'], 
                                 color='#000066', linewidth=1, label='Azul Line', marker='^', markersize=3)
            self.ax_koncorde.plot(koncorde_data.index, koncorde_data['media'], 
                                 color='red', linewidth=2, label='Media', marker='d', markersize=3)
        
        # Línea de cero
        self.ax_koncorde.axhline(y=0, color='black', linewidth=1, alpha=0.5)
        
        self.ax_koncorde.set_ylabel('Koncorde')
        self.ax_koncorde.legend(loc='upper left')
        self.ax_koncorde.grid(True, alpha=0.3)
        self.ax_koncorde.set_title('Indicador Koncorde')
        
        print(f"Debug plot_koncorde - verde range: {koncorde_data['verde'].min():.2f} to {koncorde_data['verde'].max():.2f}")
        print(f"Debug plot_koncorde - marron range: {koncorde_data['marron'].min():.2f} to {koncorde_data['marron'].max():.2f}")
    
    def setup_date_formatting(self):
        """Configurar formato de fechas en los ejes"""
        # Formato de fechas
        for ax in [self.ax_price, self.ax_koncorde]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    def run_interactive(self):
        """Ejecutar visualizador interactivo"""
        # Cargar archivos disponibles
        csv_files = self.load_csv_files()
        
        if not csv_files:
            print("No se encontraron archivos CSV en la carpeta data/")
            return
        
        print("Archivos disponibles:")
        for i, (symbol, file) in enumerate(csv_files):
            print(f"{i+1}. {symbol}")
        
        # Seleccionar archivo
        while True:
            try:
                choice = int(input(f"Selecciona un archivo (1-{len(csv_files)}): ")) - 1
                if 0 <= choice < len(csv_files):
                    symbol, file_name = csv_files[choice]
                    break
                else:
                    print("Opción no válida")
            except ValueError:
                print("Introduce un número válido")
        
        # Cargar datos
        print(f"Cargando datos de {symbol}...")
        df = self.load_data(symbol, file_name)
        
        # Calcular Koncorde
        print("Calculando indicador Koncorde...")
        koncorde_data = self.calculate_indicators(df)
        
        if koncorde_data is None:
            print("Error calculando Koncorde")
            return
        
        # Mostrar fechas disponibles
        dates_available = df.index.date
        unique_dates = sorted(set(dates_available))
        
        print(f"\nFechas disponibles ({len(unique_dates)} días):")
        for i, date in enumerate(unique_dates[-10:]):  # Mostrar últimos 10 días
            print(f"{len(unique_dates)-10+i+1}. {date}")
        if len(unique_dates) > 10:
            print(f"... y {len(unique_dates)-10} días más")
        
        # Seleccionar fecha específica
        while True:
            date_input = input(f"Selecciona fecha (YYYY-MM-DD) o 'latest' para la más reciente: ").strip()
            if date_input.lower() == 'latest':
                selected_date = unique_dates[-1]
                break
            else:
                try:
                    from datetime import datetime
                    selected_date = datetime.strptime(date_input, '%Y-%m-%d').date()
                    if selected_date in unique_dates:
                        break
                    else:
                        print(f"Fecha no disponible. Fechas disponibles: {unique_dates[0]} a {unique_dates[-1]}")
                except ValueError:
                    print("Formato incorrecto. Usa YYYY-MM-DD o 'latest'")
        
        # Filtrar datos por fecha seleccionada
        df_date = df[df.index.date == selected_date]
        koncorde_date = koncorde_data[koncorde_data.index.date == selected_date]
        
        # Filtrar solo horas de trading (10:00 - 23:00)
        trading_hours_mask = (df_date.index.time >= pd.Timestamp('10:00:00').time()) & \
                           (df_date.index.time <= pd.Timestamp('23:00:00').time())
        
        df_date_trading = df_date[trading_hours_mask]
        koncorde_date_trading = koncorde_date[trading_hours_mask]
        
        print(f"\nDatos para {selected_date}: {len(df_date)} registros totales")
        print(f"Datos en horario de trading (10:00-23:00): {len(df_date_trading)} registros")
        
        # Usar datos filtrados por horario de trading
        df_date = df_date_trading
        koncorde_date = koncorde_date_trading
        
        # Seleccionar rango de tiempo
        time_ranges = ['1M', '5M', '15M', '30M', '1H', '4H', 'FULL_DAY']
        print("\nRangos de tiempo disponibles:")
        for i, tr in enumerate(time_ranges):
            print(f"{i+1}. {tr}")
        
        while True:
            try:
                time_choice = int(input(f"Selecciona rango (1-{len(time_ranges)}): ")) - 1
                if 0 <= time_choice < len(time_ranges):
                    time_range = time_ranges[time_choice]
                    break
                else:
                    print("Opción no válida")
            except ValueError:
                print("Introduce un número válido")
        
        # Crear y mostrar gráfico con datos filtrados por fecha
        print(f"Creando gráfico para {symbol} - {selected_date} ({time_range})...")
        self.create_plot_with_date(symbol, df_date, koncorde_date, time_range, selected_date)
        plt.show()

def main():
    """Función principal"""
    print("=== Visualizador Koncorde ===")
    
    visualizer = KoncordeVisualizer()
    visualizer.run_interactive()

if __name__ == "__main__":
    main()