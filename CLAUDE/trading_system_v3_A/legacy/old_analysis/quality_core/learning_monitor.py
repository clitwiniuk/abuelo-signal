#!/usr/bin/env python3
"""
Learning System Monitor
======================

Herramienta para monitorear el rendimiento del sistema de aprendizaje
y actualizar resultados de predicciones.
"""

import argparse
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import os

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from learning_system import AutoLearningSystem, PredictionTracker, WeightLearningSystem

def display_learning_stats(db_path: str):
    """Mostrar estadísticas del sistema de aprendizaje"""
    print("\n🎯 LEARNING SYSTEM STATISTICS")
    print("=" * 50)
    
    try:
        auto_system = AutoLearningSystem(db_path)
        stats = auto_system.get_system_stats()
        
        print(f"📊 Total Predictions: {stats['total_predictions']}")
        print(f"🎯 Learning Enabled: {'✅ Yes' if stats['learning_enabled'] else '❌ No (need more data)'}")
        
        # Accuracy metrics
        if 'accuracy_metrics' in stats:
            metrics = stats['accuracy_metrics']
            print(f"📈 Overall Win Rate: {metrics['win_rate']:.1%}")
            print(f"🎯 High Grade Accuracy: {metrics['accuracy']:.1%}")
            
            if 'precision_by_grade' in metrics:
                print("\n📊 Precision by Grade:")
                for grade, precision in metrics['precision_by_grade'].items():
                    print(f"   {grade}: {precision:.1%}")
        
        # Current weights
        print(f"\n⚖️ Current Factor Weights:")
        weights = stats['current_weights']
        for factor, weight in weights.items():
            print(f"   {factor.title()}: {weight:.1%}")
        
        # Factor importance (if available)
        if 'factor_importance' in stats and not stats['factor_importance'].get('insufficient_data'):
            importance = stats['factor_importance']
            if 'correlations' in importance:
                print(f"\n🔗 Factor Correlations with Success:")
                for factor, corr in importance['correlations'].items():
                    direction = "📈" if corr > 0 else "📉" if corr < 0 else "➡️"
                    print(f"   {direction} {factor.title()}: {corr:.3f}")
        
    except Exception as e:
        print(f"❌ Error displaying stats: {e}")

def update_pending_results(db_path: str, dry_run: bool = False):
    """Actualizar resultados pendientes"""
    print(f"\n🔄 {'SIMULATING' if dry_run else 'UPDATING'} PENDING RESULTS")
    print("=" * 50)
    
    try:
        auto_system = AutoLearningSystem(db_path)
        
        # Get untracked predictions first to show what we're working with
        tracker = PredictionTracker(db_path)
        untracked = tracker.get_untracked_predictions()
        
        if not untracked:
            print("✅ No pending predictions to update")
            return
        
        print(f"📋 Found {len(untracked)} predictions to update:")
        for pred in untracked[:5]:  # Show first 5
            print(f"   • {pred['ticker']} - {pred['prediction_time']}")
        if len(untracked) > 5:
            print(f"   ... and {len(untracked) - 5} more")
        
        if dry_run:
            print("\n🧪 DRY RUN - No actual updates performed")
            return
        
        # Perform actual updates
        print(f"\n🔄 Updating results...")
        results = auto_system.update_results_and_learn()
        
        print(f"✅ Updated Results: {results['updated_results']}")
        print(f"❌ Failed Updates: {results['failed_updates']}")
        
        # Learning update results
        if results['learning_update']:
            learning = results['learning_update']
            if learning['updated']:
                print(f"\n🧠 Learning System Updated:")
                print(f"   📊 Samples Used: {learning['samples']}")
                if 'accuracy_metrics' in learning:
                    print(f"   🎯 Current Win Rate: {learning['accuracy_metrics']['win_rate']:.1%}")
            else:
                reason = learning.get('reason', 'unknown')
                print(f"\n🤔 Learning Not Updated: {reason}")
        
    except Exception as e:
        print(f"❌ Error updating results: {e}")

def show_recent_predictions(db_path: str, limit: int = 10):
    """Mostrar predicciones recientes"""
    print(f"\n📋 RECENT PREDICTIONS (Last {limit})")
    print("=" * 70)
    
    try:
        conn = sqlite3.connect(db_path)
        
        query = """
        SELECT 
            p.ticker,
            p.prediction_time,
            p.predicted_grade,
            p.predicted_score,
            p.current_price,
            p.result_tracked,
            r.return_eod,
            r.final_result
        FROM predictions p
        LEFT JOIN prediction_results r ON p.id = r.prediction_id
        ORDER BY p.timestamp DESC
        LIMIT ?
        """
        
        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        
        if df.empty:
            print("📝 No predictions found")
            return
        
        # Format display
        for _, row in df.iterrows():
            ticker = row['ticker']
            grade = row['predicted_grade']
            score = row['predicted_score']
            tracked = "✅" if row['result_tracked'] else "⏳"
            
            result_text = ""
            if row['result_tracked']:
                return_eod = row['return_eod']
                final_result = row['final_result']
                if final_result == 'win':
                    result_text = f"🟢 +{return_eod:.1f}%"
                elif final_result == 'loss':
                    result_text = f"🔴 {return_eod:.1f}%"
                else:
                    result_text = f"🟡 {return_eod:.1f}%"
            else:
                result_text = "⏳ Pending"
            
            prediction_time = row['prediction_time']
            print(f"{tracked} {ticker:<6} {grade:<3} ({score:>3}) | {prediction_time} | {result_text}")
        
    except Exception as e:
        print(f"❌ Error showing predictions: {e}")

def reset_learning_system(db_path: str, confirm: bool = False):
    """Reset del sistema de aprendizaje"""
    if not confirm:
        print("⚠️  This will delete ALL learning data. Use --confirm to proceed.")
        return
    
    print("\n🗑️  RESETTING LEARNING SYSTEM")
    print("=" * 50)
    
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"✅ Deleted learning database: {db_path}")
        else:
            print(f"ℹ️  Database doesn't exist: {db_path}")
        
        # Recreate database with fresh schema
        auto_system = AutoLearningSystem(db_path)
        print("✅ Recreated fresh learning database")
        
    except Exception as e:
        print(f"❌ Error resetting system: {e}")

def export_learning_data(db_path: str, output_file: str):
    """Exportar datos de aprendizaje"""
    print(f"\n📤 EXPORTING LEARNING DATA")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Export predictions
        predictions_df = pd.read_sql_query("""
            SELECT * FROM predictions ORDER BY timestamp DESC
        """, conn)
        
        # Export results
        results_df = pd.read_sql_query("""
            SELECT * FROM prediction_results ORDER BY result_timestamp DESC
        """, conn)
        
        conn.close()
        
        # Create export data
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'predictions_count': len(predictions_df),
            'results_count': len(results_df),
            'predictions': predictions_df.to_dict('records'),
            'results': results_df.to_dict('records')
        }
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"✅ Exported {len(predictions_df)} predictions and {len(results_df)} results")
        print(f"📁 File: {output_file}")
        
    except Exception as e:
        print(f"❌ Error exporting data: {e}")

def main():
    parser = argparse.ArgumentParser(description="Learning System Monitor")
    parser.add_argument('--db', default='learning_system.db', 
                       help='Path to learning database')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show learning statistics')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update pending results')
    update_parser.add_argument('--dry-run', action='store_true',
                              help='Simulate update without making changes')
    
    # Predictions command
    pred_parser = subparsers.add_parser('predictions', help='Show recent predictions')
    pred_parser.add_argument('--limit', type=int, default=10,
                            help='Number of predictions to show')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset learning system')
    reset_parser.add_argument('--confirm', action='store_true',
                             help='Confirm reset operation')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export learning data')
    export_parser.add_argument('output', help='Output file path')
    
    args = parser.parse_args()
    
    # Convert relative path to absolute
    db_path = str(Path(args.db).resolve())
    
    print(f"🗄️  Database: {db_path}")
    
    if args.command == 'stats':
        display_learning_stats(db_path)
    elif args.command == 'update':
        update_pending_results(db_path, args.dry_run)
    elif args.command == 'predictions':
        show_recent_predictions(db_path, args.limit)
    elif args.command == 'reset':
        reset_learning_system(db_path, args.confirm)
    elif args.command == 'export':
        export_learning_data(db_path, args.output)
    else:
        # Default: show stats
        display_learning_stats(db_path)
        print(f"\n💡 Use --help to see available commands")

if __name__ == "__main__":
    main()