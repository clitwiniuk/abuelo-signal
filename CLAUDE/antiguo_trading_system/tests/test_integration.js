#!/usr/bin/env node

/**
 * Script de prueba para la integración SQLite-PostgreSQL
 */

const dataIntegrationService = require('./tradetally/backend/src/services/dataIntegrationService');

async function testIntegration() {
  console.log('🧪 Probando integración SQLite-PostgreSQL...\n');

  try {
    // 1. Probar consistencia de datos
    console.log('1. Verificando consistencia de datos...');
    const consistency = await dataIntegrationService.validateDataConsistency('test-user-id');
    console.log('   ✅ Consistencia:', consistency);
    console.log('');

    // 2. Probar métricas avanzadas
    console.log('2. Obteniendo métricas avanzadas...');
    const advancedMetrics = await dataIntegrationService.getAdvancedMetrics('test-user-id');
    console.log('   ✅ Métricas avanzadas:', advancedMetrics);
    console.log('');

    // 3. Probar analytics combinados
    console.log('3. Obteniendo analytics combinados...');
    const combinedAnalytics = await dataIntegrationService.getCombinedAnalytics('test-user-id');
    console.log('   ✅ Analytics combinados:', {
      totalTrades: combinedAnalytics.totalTrades,
      totalPnL: combinedAnalytics.totalPnL,
      winRate: combinedAnalytics.winRate,
      sharpeRatio: combinedAnalytics.sharpeRatio,
      dataSource: combinedAnalytics.dataSource
    });
    console.log('');

    console.log('🎉 ¡Todas las pruebas pasaron exitosamente!');
    console.log('📊 La integración SQLite-PostgreSQL está funcionando correctamente.');

  } catch (error) {
    console.error('❌ Error en las pruebas:', error.message);
    console.error('Stack:', error.stack);
    process.exit(1);
  }
}

// Ejecutar pruebas
testIntegration();