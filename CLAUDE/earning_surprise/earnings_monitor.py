"""
Monitor de Earnings Surprises - Herramienta de análisis y backtesting
Ejecutar este script para monitorear oportunidades de earnings en tiempo real
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Dict
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EarningsMonitor:
    """Monitor en tiempo real de oportunidades de earnings"""
    
    def __init__(self):
        from strategies.earnings_surprise import EarningsSurpriseStrategy, EarningsDataProvider
        
        self.strategy = EarningsSurpriseStrategy()
        self.data_provider = EarningsDataProvider()
        
    def scan_current_opportunities(self) -> pd.DataFrame:
        """Escanea oportunidades actuales de earnings"""
        logger.info("Escaneando oportunidades de earnings...")
        
        # Obtener earnings recientes
        recent_earnings = self.data_provider.get_recent_earnings(days_back=7)
        
        opportunities = []
        
        for earning in recent_earnings:
            try:
                # Aquí necesitarías obtener datos de precio histórico para cada ticker
                # Por simplicidad, simularemos el análisis
                
                days_since = (datetime.now() - earning.earnings_date).days
                
                opportunity = {
                    'ticker': earning.ticker,
                    'earnings_date': earning.earnings_date,
                    'days_since_earnings': days_since,
                    'surprise_pct': earning.surprise_pct,
                    'actual_eps': earning.actual_eps,
                    'estimated_eps': earning.estimated_eps,
                    'market_cap': earning.market_cap,
                    'market_cap_category': self._categorize_market_cap(earning.market_cap),
                    'surprise_strength': self._categorize_surprise(earning.surprise_pct)
                }
                
                opportunities.append(opportunity)
                
            except Exception as e:
                logger.warning(f"Error procesando {earning.ticker}: {e}")
                continue
        
        df = pd.DataFrame(opportunities)
        
        if not df.empty:
            # Ordenar por surprise más fuerte y más reciente
            df['score'] = abs(df['surprise_pct']) * (8 - df['days_since_earnings'])
            df = df.sort_values('score', ascending=False)
        
        logger.info(f"Encontradas {len(df)} oportunidades de earnings")
        return df
    
    def _categorize_market_cap(self, market_cap: float) -> str:
        """Categoriza por tamaño de market cap"""
        if market_cap < 300_000_000:
            return "Micro Cap"
        elif market_cap < 2_000_000_000:
            return "Small Cap"
        elif market_cap < 10_000_000_000:
            return "Mid Cap"
        else:
            return "Large Cap"
    
    def _categorize_surprise(self, surprise_pct: float) -> str:
        """Categoriza la fuerza del surprise"""
        abs_surprise = abs(surprise_pct)
        if abs_surprise > 20:
            return "Muy Fuerte"
        elif abs_surprise > 10:
            return "Fuerte"
        elif abs_surprise > 5:
            return "Moderado"
        else:
            return "Débil"
    
    def analyze_historical_performance(self, days_back: int = 90) -> Dict:
        """Analiza el rendimiento histórico de la estrategia"""
        logger.info(f"Analizando rendimiento histórico ({days_back} días)...")
        
        # Obtener earnings históricos
        historical_earnings = self.data_provider.get_recent_earnings(days_back=days_back)
        
        results = {
            'total_opportunities': len(historical_earnings),
            'by_surprise_strength': {},
            'by_market_cap': {},
            'by_days_momentum': {},
            'success_rate': 0,
            'avg_return': 0
        }
        
        # Análisis por fuerza de surprise
        for earning in historical_earnings:
            strength = self._categorize_surprise(earning.surprise_pct)
            if strength not in results['by_surprise_strength']:
                results['by_surprise_strength'][strength] = []
            results['by_surprise_strength'][strength].append(earning.surprise_pct)
        
        # Análisis por market cap
        for earning in historical_earnings:
            category = self._categorize_market_cap(earning.market_cap)
            if category not in results['by_market_cap']:
                results['by_market_cap'][category] = []
            results['by_market_cap'][category].append(earning.surprise_pct)
        
        return results
    
    def generate_report(self) -> str:
        """Genera reporte completo de oportunidades"""
        logger.info("Generando reporte de earnings...")
        
        # Obtener datos actuales
        current_opps = self.scan_current_opportunities()
        historical_analysis = self.analyze_historical_performance()
        
        report = []
        report.append("=" * 80)
        report.append("REPORTE DE EARNINGS SURPRISES - SMALL CAPS")
        report.append("=" * 80)
        report.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Resumen ejecutivo
        report.append("RESUMEN EJECUTIVO:")
        report.append("-" * 40)
        if not current_opps.empty:
            top_opportunities = current_opps.head(5)
            report.append(f"• {len(current_opps)} oportunidades activas")
            report.append(f"• Top 5 por score:")
            
            for _, opp in top_opportunities.iterrows():
                report.append(f"  {opp['ticker']}: Surprise {opp['surprise_pct']:+.1f}% "
                            f"({opp['days_since_earnings']} días) - {opp['surprise_strength']}")
        else:
            report.append("• No hay oportunidades activas actualmente")
        
        report.append("")
        
        # Oportunidades por categoría
        if not current_opps.empty:
            report.append("OPORTUNIDADES POR CATEGORÍA:")
            report.append("-" * 40)
            
            # Por fuerza de surprise
            surprise_counts = current_opps['surprise_strength'].value_counts()
            report.append("Por fuerza de surprise:")
            for strength, count in surprise_counts.items():
                report.append(f"  • {strength}: {count} oportunidades")
            
            report.append("")
            
            # Por tamaño de empresa
            cap_counts = current_opps['market_cap_category'].value_counts()
            report.append("Por tamaño de empresa:")
            for category, count in cap_counts.items():
                report.append(f"  • {category}: {count} oportunidades")
            
            report.append("")
        
        # Análisis histórico
        report.append("ANÁLISIS HISTÓRICO:")
        report.append("-" * 40)
        report.append(f"• Total oportunidades últimos 90 días: {historical_analysis['total_opportunities']}")
        
        if historical_analysis['by_surprise_strength']:
            report.append("• Distribución por fuerza:")
            for strength, surprises in historical_analysis['by_surprise_strength'].items():
                avg_surprise = np.mean([abs(s) for s in surprises])
                report.append(f"  {strength}: {len(surprises)} casos (avg: {avg_surprise:.1f}%)")
        
        report.append("")
        
        # Recomendaciones
        report.append("RECOMENDACIONES DE TRADING:")
        report.append("-" * 40)
        if not current_opps.empty:
            # Filtrar las mejores oportunidades
            best_opps = current_opps[
                (current_opps['days_since_earnings'] <= 3) &
                (abs(current_opps['surprise_pct']) >= 7) &
                (current_opps['market_cap_category'].isin(['Small Cap', 'Micro Cap']))
            ]
            
            if not best_opps.empty:
                report.append("🎯 OPORTUNIDADES PRIORITARIAS:")
                for _, opp in best_opps.head(3).iterrows():
                    direction = "LONG" if opp['surprise_pct'] > 0 else "SHORT"
                    report.append(f"  • {opp['ticker']} ({direction}): "
                                f"Surprise {opp['surprise_pct']:+.1f}%, "
                                f"{opp['days_since_earnings']} días desde earnings")
                report.append("")
            
            # Alertas de riesgo
            old_opps = current_opps[current_opps['days_since_earnings'] > 4]
            if not old_opps.empty:
                report.append("⚠️  ALERTAS - Oportunidades perdiendo fuerza:")
                for _, opp in old_opps.head(3).iterrows():
                    report.append(f"  • {opp['ticker']}: {opp['days_since_earnings']} días desde earnings")
                report.append("")
        
        report.append("CONFIGURACIÓN RECOMENDADA:")
        report.append("-" * 40)
        report.append("• Surprise mínimo: 5-7% para entrar")
        report.append("• Máximo 3-5 días desde earnings")
        report.append("• Stop loss: 4% | Take profit: 8%")
        report.append("• Máximo 3 posiciones simultáneas")
        report.append("• Verificar volumen >2x promedio")
        report.append("")
        
        report.append("APIs GRATUITAS UTILIZADAS:")
        report.append("-" * 40)
        report.append("• Financial Modeling Prep: 250 calls/día")
        report.append("• Alpha Vantage: 500 calls/día")  
        report.append("• Polygon.io: 5 calls/minuto")
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def create_visualization(self, save_path: str = "earnings_analysis.png"):
        """Crea visualización del análisis"""
        try:
            current_opps = self.scan_current_opportunities()
            
            if current_opps.empty:
                print("No hay datos para visualizar")
                return
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle('Análisis de Earnings Surprises - Small Caps', fontsize=16, fontweight='bold')
            
            # 1. Distribución de surprises
            axes[0, 0].hist(current_opps['surprise_pct'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            axes[0, 0].axvline(0, color='red', linestyle='--', alpha=0.7)
            axes[0, 0].set_title('Distribución de Earnings Surprises')
            axes[0, 0].set_xlabel('Surprise (%)')
            axes[0, 0].set_ylabel('Frecuencia')
            
            # 2. Surprise por días transcurridos
            scatter = axes[0, 1].scatter(current_opps['days_since_earnings'], 
                                       current_opps['surprise_pct'],
                                       c=current_opps['score'], 
                                       cmap='viridis', 
                                       alpha=0.7,
                                       s=60)
            axes[0, 1].set_title('Surprise vs Días Transcurridos')
            axes[0, 1].set_xlabel('Días desde Earnings')
            axes[0, 1].set_ylabel('Surprise (%)')
            plt.colorbar(scatter, ax=axes[0, 1], label='Score')
            
            # 3. Por categoría de market cap
            cap_data = current_opps['market_cap_category'].value_counts()
            axes[1, 0].pie(cap_data.values, labels=cap_data.index, autopct='%1.1f%%')
            axes[1, 0].set_title('Distribución por Market Cap')
            
            # 4. Fuerza de surprises
            strength_data = current_opps['surprise_strength'].value_counts()
            axes[1, 1].bar(strength_data.index, strength_data.values, color=['red', 'orange', 'yellow', 'green'])
            axes[1, 1].set_title('Distribución por Fuerza del Surprise')
            axes[1, 1].set_ylabel('Cantidad')
            axes[1, 1].tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            
            print(f"Visualización guardada en: {save_path}")
            
        except Exception as e:
            logger.error(f"Error creando visualización: {e}")

def main():
    """Función principal del monitor"""
    print("Iniciando Monitor de Earnings Surprises...")
    
    try:
        monitor = EarningsMonitor()
        
        # Generar y mostrar reporte
        report = monitor.generate_report()
        print(report)
        
        # Guardar reporte en archivo
        with open(f"earnings_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt", 'w') as f:
            f.write(report)
        
        # Crear visualización
        monitor.create_visualization()
        
    except Exception as e:
        logger.error(f"Error en monitor principal: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()