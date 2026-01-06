#!/bin/bash
# Script generado automáticamente para limpiar archivos legacy
echo 'Limpiando archivos legacy de tests...'

echo 'Moviendo test_optimized_gap_go_strategy.py a advanced/'
mv test_optimized_gap_go_strategy.py advanced/
echo 'Moviendo test_volume_momentum_backtest.py a simulation/'
mv test_volume_momentum_backtest.py simulation/
mkdir -p misc
echo 'Moviendo conftest.py a misc/'
mv conftest.py misc/
echo 'Moviendo test_market_close.py a advanced/'
mv test_market_close.py advanced/
echo 'Moviendo test_risk_manager.py a advanced/'
mv test_risk_manager.py advanced/
echo 'Moviendo test_strategy_exits.py a advanced/'
mv test_strategy_exits.py advanced/
echo 'Moviendo test_gap_go_strategy.py a simulation/'
mv test_gap_go_strategy.py simulation/
echo 'Moviendo test_ibkr_duration.py a advanced/'
mv test_ibkr_duration.py advanced/
mkdir -p misc
echo 'Moviendo monkey_tester.py a misc/'
mv monkey_tester.py misc/
echo 'Moviendo test_position_value_validation.py a advanced/'
mv test_position_value_validation.py advanced/
echo 'Moviendo test_stop_loss.py a advanced/'
mv test_stop_loss.py advanced/
echo 'Moviendo test_vwap_real_order.py a advanced/'
mv test_vwap_real_order.py advanced/
echo 'Moviendo test_volume_momentum_strategy.py a simulation/'
mv test_volume_momentum_strategy.py simulation/
echo 'Moviendo test_vwap_orders.py a advanced/'
mv test_vwap_orders.py advanced/
echo 'Moviendo backtest_volume_momentum.py a simulation/'
mv backtest_volume_momentum.py simulation/
echo 'Moviendo test_risk_manager_strategies.py a advanced/'
mv test_risk_manager_strategies.py advanced/
echo 'Moviendo test_position_sizing.py a advanced/'
mv test_position_sizing.py advanced/

echo 'Limpieza completada!'
