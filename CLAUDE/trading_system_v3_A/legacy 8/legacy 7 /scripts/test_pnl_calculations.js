/**
 * Test P&L Display Calculations
 * Verifica que los cálculos de % y R sean correctos
 */

// Simular datos reales
const initialAccountBalance = 2000; // Capital inicial
const riskPercentage = 2; // 2% de riesgo por trade

// Ejemplo: Total P&L = $666.52
const totalPnL = 666.52;

// CÁLCULO PORCENTAJE
// Fórmula: (P&L / Capital Inicial) * 100
const percentageCalculation = (totalPnL / initialAccountBalance) * 100;
console.log('=== CÁLCULO PORCENTAJE ===');
console.log('Total P&L: $' + totalPnL);
console.log('Capital Inicial: $' + initialAccountBalance);
console.log('Fórmula: (' + totalPnL + ' / ' + initialAccountBalance + ') * 100');
console.log('Resultado: ' + percentageCalculation.toFixed(2) + '%');
console.log('Esperado: 33.33%');
console.log('¿Es correcto?: ' + (Math.abs(percentageCalculation - 33.326) < 0.01 ? '✅ SÍ' : '❌ NO'));
console.log('');

// CÁLCULO R (usando método del código actual)
// Para Total P&L, no hay trade específico, así que usa el account balance como fallback
const positionValue = initialAccountBalance;
const riskPerTrade = (positionValue * riskPercentage) / 100;
const riskUnits = totalPnL / riskPerTrade;

console.log('=== CÁLCULO R (método actual - FALLBACK) ===');
console.log('Total P&L: $' + totalPnL);
console.log('Position Value (fallback = account balance): $' + positionValue);
console.log('Risk %: ' + riskPercentage + '%');
console.log('Riesgo por trade: $' + riskPerTrade.toFixed(2));
console.log('Fórmula: ' + totalPnL + ' / ' + riskPerTrade.toFixed(2));
console.log('Resultado: ' + riskUnits.toFixed(2) + 'R');
console.log('');

// CÁLCULO R MEJORADO (debería usar P&L total sobre capital de riesgo total)
// Si hiciste 50 trades con 2% de riesgo cada uno, el capital de riesgo total es diferente
// Para Total P&L acumulado, deberíamos calcular R de forma diferente:

// Opción 1: R basado en capital inicial y risk%
const totalCapitalRisk = (initialAccountBalance * riskPercentage) / 100;
const rUnitsOption1 = totalPnL / totalCapitalRisk;
console.log('=== CÁLCULO R - OPCIÓN 1 (sobre capital inicial) ===');
console.log('Total P&L: $' + totalPnL);
console.log('Capital de riesgo (2% de $2000): $' + totalCapitalRisk);
console.log('Resultado: ' + rUnitsOption1.toFixed(2) + 'R');
console.log('');

// Opción 2: R basado en retorno sobre capital (ROI * R)
// Si ganaste 33.33%, eso equivale a 16.67R (con 2% de riesgo)
const roiPercentage = percentageCalculation;
const rUnitsOption2 = roiPercentage / riskPercentage;
console.log('=== CÁLCULO R - OPCIÓN 2 (ROI / Risk%) ===');
console.log('ROI: ' + roiPercentage.toFixed(2) + '%');
console.log('Risk por trade: ' + riskPercentage + '%');
console.log('Fórmula: ' + roiPercentage.toFixed(2) + ' / ' + riskPercentage);
console.log('Resultado: ' + rUnitsOption2.toFixed(2) + 'R');
console.log('Interpretación: Has ganado ' + rUnitsOption2.toFixed(2) + 'R sobre tu capital');
console.log('');

console.log('=== RESUMEN ===');
console.log('Para un P&L total de $' + totalPnL + ' con capital de $' + initialAccountBalance + ':');
console.log('- Porcentaje: ' + percentageCalculation.toFixed(2) + '% ✅ (correcto)');
console.log('- R (método actual): ' + riskUnits.toFixed(2) + 'R');
console.log('- R (opción 1 - sobre 1R): ' + rUnitsOption1.toFixed(2) + 'R');
console.log('- R (opción 2 - ROI/Risk%): ' + rUnitsOption2.toFixed(2) + 'R ⭐ (más significativo para totales)');
console.log('');
console.log('El método más apropiado para Total P&L es la Opción 2,');
console.log('porque representa cuántos "riesgos" has ganado sobre tu capital.');
