/**
 * Test ConfigReader to verify capital calculations
 */

const configReader = require('../tradetally/backend/src/utils/configReader');

console.log('=== Testing ConfigReader ===\n');

console.log('📁 Config path:', configReader.configPath);
console.log('');

const portfolioCapital = configReader.getPortfolioCapital();
console.log('💰 Portfolio Capital:', portfolioCapital);

const metricsPercentage = configReader.getMetricsCalculationPercentage();
console.log('📊 Metrics Calculation Percentage:', metricsPercentage + '%');

const effectiveCapital = configReader.getEffectiveCapitalForMetrics();
console.log('✨ Effective Capital:', effectiveCapital);
console.log('');

console.log('=== Calculation Check ===');
console.log('Formula: effectiveCapital = portfolioCapital * (percentage / 100)');
console.log(`${effectiveCapital} = ${portfolioCapital} * (${metricsPercentage} / 100)`);
console.log(`${effectiveCapital} = ${portfolioCapital} * ${metricsPercentage / 100}`);
console.log(`${effectiveCapital} = ${portfolioCapital * (metricsPercentage / 100)}`);
console.log('');

if (effectiveCapital === 2000) {
  console.log('✅ CORRECTO: effectiveCapital = $2000');
} else if (effectiveCapital === 20000) {
  console.log('❌ ERROR: effectiveCapital = $20,000 (debería ser $2,000)');
  console.log('');
  console.log('Posibles causas:');
  console.log('1. metrics_calculation_percentage = 1000 en lugar de 100');
  console.log('2. portfolio_capital = 20000 en lugar de 2000');
} else {
  console.log(`⚠️  VALOR INESPERADO: effectiveCapital = $${effectiveCapital}`);
}

console.log('');
console.log('=== P&L Percentage Test ===');
const testPnL = 666.52;
const correctPercentage = (testPnL / 2000) * 100;
const wrongPercentage = (testPnL / 20000) * 100;

console.log(`P&L: $${testPnL}`);
console.log(`Con capital correcto ($2,000): ${correctPercentage.toFixed(2)}%`);
console.log(`Con capital incorrecto ($20,000): ${wrongPercentage.toFixed(2)}%`);
console.log('');

if (effectiveCapital === 20000) {
  console.log('🔴 El dashboard mostrará: ' + wrongPercentage.toFixed(2) + '%');
} else {
  console.log('🟢 El dashboard mostrará: ' + correctPercentage.toFixed(2) + '%');
}
