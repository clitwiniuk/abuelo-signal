import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import datetime

def create_lightweight_chart(data, symbol="STOCK", height=600, show_volume=True):
    """
    Crear un gráfico interactivo usando Lightweight Charts de TradingView
    
    Args:
        data: DataFrame con columnas OHLCV
        symbol: Símbolo del stock
        height: Altura del gráfico en píxeles
        show_volume: Mostrar volumen
    
    Returns:
        HTML del gráfico
    """
    
    # Convertir datos a formato JavaScript
    if data is None or data.empty:
        return "<div>No hay datos disponibles</div>"
    
    # Preparar datos para el gráfico
    chart_data = []
    volume_data = []
    
    for idx, row in data.iterrows():
        timestamp = int(idx.timestamp() * 1000) if hasattr(idx, 'timestamp') else idx
        
        chart_data.append({
            'time': timestamp,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close'])
        })
        
        if show_volume and 'volume' in row:
            volume_data.append({
                'time': timestamp,
                'value': float(row['volume']),
                'color': '#26a69a' if row['close'] >= row['open'] else '#ef5350'
            })
    
    # HTML con Lightweight Charts
    html_code = f"""
    <div id="tradingview_chart_{symbol}" style="height: {height}px; background-color: #1a1a1a; border-radius: 8px;"></div>
    
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        // Datos del gráfico
        const chartData = {chart_data};
        const volumeData = {volume_data};
        
        // Crear gráfico
        const chart = LightweightCharts.createChart(
            document.getElementById('tradingview_chart_{symbol}'),
            {{
                width: document.getElementById('tradingview_chart_{symbol}').parentElement.offsetWidth - 32,
                height: {height},
                layout: {{
                    backgroundColor: '#1a1a1a',
                    textColor: '#d1d4dc',
                    fontSize: 12,
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                }},
                grid: {{
                    vertLines: {{
                        color: '#2a2a2a',
                    }},
                    horzLines: {{
                        color: '#2a2a2a',
                    }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                }},
                rightPriceScale: {{
                    borderColor: '#2a2a2a',
                    textColor: '#d1d4dc',
                }},
                timeScale: {{
                    borderColor: '#2a2a2a',
                    textColor: '#d1d4dc',
                    timeVisible: true,
                    secondsVisible: false,
                }},
                overlayPriceScales: {{
                    ticksVisible: false,
                    borderVisible: false,
                }},
                localization: {{
                    priceFormatter: (price) => {{
                        return '$' + price.toFixed(2);
                    }},
                }},
            }}
        );
        
        // Añadir serie de velas
        const candlestickSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderDownColor: '#ef5350',
            borderUpColor: '#26a69a',
            wickDownColor: '#ef5350',
            wickUpColor: '#26a69a',
        }});
        
        candlestickSeries.setData(chartData);
        
        // Añadir volumen si está habilitado
        {f'''
        const volumeSeries = chart.addHistogramSeries({{
            color: '#26a69a',
            priceFormat: {{
                type: 'volume',
            }},
            priceScaleId: 'volume',
            scaleMargins: {{
                top: 0.8,
                bottom: 0,
            }},
        }});
        
        volumeSeries.setData(volumeData);
        ''' if show_volume else ''}
        
        // Añadir línea de VWAP si existe
        {f'''
        const vwapData = chartData.map(item => ({{
            time: item.time,
            value: (item.open + item.high + item.low + item.close) / 4
        }}));
        
        const vwapSeries = chart.addLineSeries({{
            color: '#2196f3',
            lineWidth: 2,
            title: 'VWAP',
            priceScaleId: 'right',
        }});
        
        vwapSeries.setData(vwapData);
        ''' if 'vwap' in data.columns else ''}
        
        // Añadir título
        chart.applyOptions({{
            watermark: {{
                color: 'rgba(255, 255, 255, 0.1)',
                visible: true,
                text: '{symbol}',
                fontSize: 48,
                fontFamily: 'Arial, sans-serif',
                fontStyle: 'bold',
            }},
        }});
        
        // Auto-ajustar contenido
        chart.timeScale().fitContent();
        
        // Hacer el gráfico responsive
        window.addEventListener('resize', () => {{
            chart.applyOptions({{
                width: document.getElementById('tradingview_chart_{symbol}').parentElement.offsetWidth - 32,
            }});
        }});
        
        // Habilitar zoom y pan con mouse wheel
        chart.subscribeCrosshairMove((param) => {{
            if (!param.time) return;
            
            const price = param.seriesPrices.get(candlestickSeries);
            if (price) {{
                const tooltip = document.createElement('div');
                tooltip.style.position = 'absolute';
                tooltip.style.left = param.point.x + 'px';
                tooltip.style.top = param.point.y + 'px';
                tooltip.style.padding = '8px';
                tooltip.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
                tooltip.style.color = 'white';
                tooltip.style.borderRadius = '4px';
                tooltip.style.fontSize = '12px';
                tooltip.style.pointerEvents = 'none';
                tooltip.style.zIndex = '1000';
                
                const date = new Date(param.time * 1000);
                tooltip.innerHTML = `
                    <div style="font-weight: bold; margin-bottom: 4px;">{symbol}</div>
                    <div>${{date.toLocaleDateString()}} ${{date.toLocaleTimeString()}}</div>
                    <div>O: ${{price.open.toFixed(2)}}</div>
                    <div>H: ${{price.high.toFixed(2)}}</div>
                    <div>L: ${{price.low.toFixed(2)}}</div>
                    <div>C: ${{price.close.toFixed(2)}}</div>
                `;
                
                // Remover tooltip anterior si existe
                const oldTooltip = document.getElementById('chart-tooltip');
                if (oldTooltip) oldTooltip.remove();
                
                tooltip.id = 'chart-tooltip';
                document.body.appendChild(tooltip);
            }}
        }});
        
        // Limpiar tooltip cuando el mouse sale del gráfico
        chart.subscribeCrosshairMove((param) => {{
            if (!param.time) {{
                const tooltip = document.getElementById('chart-tooltip');
                if (tooltip) tooltip.remove();
            }}
        }});
    </script>
    """
    
    return html_code

def render_lightweight_chart(data, symbol="STOCK", height=600, show_volume=True, use_container_width=True):
    """
    Renderizar el gráfico en Streamlit
    
    Args:
        data: DataFrame con datos OHLCV
        symbol: Símbolo del stock
        height: Altura del gráfico
        show_volume: Mostrar volumen
        use_container_width: Usar ancho completo del contenedor
    """
    html_code = create_lightweight_chart(data, symbol, height, show_volume)
    components.html(html_code, height=height + 50, use_container_width=use_container_width)
