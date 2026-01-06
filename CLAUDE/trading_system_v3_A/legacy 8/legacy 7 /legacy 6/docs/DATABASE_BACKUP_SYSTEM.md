# Sistema de Backup Automático de Base de Datos

## 📋 Resumen

Sistema de backup automático integrado con el calendario del mercado que crea copias de seguridad de `trading_data.db` después del cierre del mercado.

## ✨ Características

- ✅ **Backup automático diario** después del cierre del mercado (22:00 hora española)
- ✅ **Integrado con el calendario del mercado** - se ejecuta junto con el EOD OHLC download
- ✅ **Validación de integridad** antes y después del backup
- ✅ **Retención de 30 días** - mantiene automáticamente los últimos 30 días de backups
- ✅ **Backups diarios + timestamped** para fácil recuperación
- ✅ **Detección de corrupción** - marca backups corruptos automáticamente
- ✅ **Restauración interactiva** con script incluido

## 🚀 Funcionamiento Automático

El sistema se ejecuta **automáticamente** sin intervención manual:

1. **Horario**: 22:00 hora española (16:00 ET después de after-hours)
2. **Trigger**: PHASE 2 del EOD OHLC scheduler
3. **Frecuencia**: Una vez al día, después del cierre del mercado
4. **Coordinación**: Usa el mismo calendario que el sistema de trading

### ¿Cuándo NO se ejecuta?

- Fines de semana (cuando el mercado está cerrado)
- Festivos (según el calendario de IBKR)
- Días de cierre anticipado (se adapta automáticamente)

## 📁 Estructura de Backups

```
backups/database/
├── trading_data_2024-12-30_220000.db        # Backup timestamped
├── trading_data_2024-12-30_160500.db        # Múltiples backups por día (si fallas)
├── trading_data_daily_2024-12-30.db         # Backup diario (último del día)
├── trading_data_daily_2024-12-29.db         #
├── trading_data_latest.db -> trading_data_2024-12-30_220000.db  # Symlink al más reciente
└── ...
```

### Tipos de Backups

1. **Timestamped** (`trading_data_YYYYMMDD_HHMMSS.db`)
   - Cada ejecución crea un backup con timestamp
   - Se mantienen 30 días
   - Permite recuperar el estado exacto de cualquier momento

2. **Daily** (`trading_data_daily_YYYY-MM-DD.db`)
   - Un backup por día (el último)
   - Se mantienen 7 días
   - Fácil acceso para restauraciones recientes

3. **Latest** (`trading_data_latest.db` - symlink)
   - Siempre apunta al backup más reciente
   - Útil para scripts de recuperación rápida

## 📊 Información Registrada

Cada backup incluye:

```
💾 Starting database backup - 2024-12-30 22:00:15
📊 Database size: 152.45 MB
🔍 Checking database integrity...
   Database integrity OK
💾 Creating backup: trading_data_2024-12-30_220015.db
✅ Backup created: 152.45 MB
🔍 Validating backup...
✅ Backup validated - 232 trades
📅 Daily backup: trading_data_daily_2024-12-30.db
🧹 Cleaning up old backups...
📦 Total backups: 15
💾 Backup directory size: 2.1 GB
✅ Backup process completed successfully
```

## 🔄 Restauración de Backup

### Método 1: Script Interactivo (Recomendado)

```bash
cd /Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3
python scripts/maintenance/restore_database_backup.py
```

El script te mostrará:
1. Lista de todos los backups disponibles
2. Información de cada backup (fecha, tamaño, estado)
3. Confirmación antes de restaurar
4. Backup automático de la DB actual antes de restaurar

### Método 2: Restauración Manual

```bash
# 1. Detener el sistema de trading
# 2. Hacer backup de la DB actual (por seguridad)
cp trading_data.db trading_data.db.pre_restore_$(date +%Y%m%d_%H%M%S)

# 3. Copiar el backup deseado
cp backups/database/trading_data_2024-12-30_220000.db trading_data.db

# 4. Reiniciar el sistema
```

### Método 3: Restaurar desde "latest"

```bash
# Restaurar el backup más reciente
cp backups/database/trading_data_latest.db trading_data.db
```

## 🛠️ Uso Programático

### Crear Backup Manual

```python
from core.database_backup_manager import DatabaseBackupManager

manager = DatabaseBackupManager(db_path="trading_data.db")

# Crear backup (respeta el límite de 1 por día)
backup_path = manager.create_backup()

# Forzar backup (ignora límite diario)
backup_path = manager.create_backup(force=True)
```

### Listar Backups

```python
backups = manager.list_available_backups()

for backup in backups:
    print(f"{backup['filename']}: {backup['size_mb']:.2f} MB")
    print(f"  Created: {backup['created']}")
    print(f"  Corrupted: {backup['is_corrupted']}")
```

### Restaurar Backup

```python
success = manager.restore_from_backup("backups/database/trading_data_2024-12-30_220000.db")
```

## 📝 Logs

Los backups se registran en:
- **Console**: Salida estándar del trader
- **trader.log**: Archivo de log principal del trader

Buscar por: `💾` o `EOD backup` para encontrar mensajes de backup.

## 🚨 Manejo de Errores

### Backup de Base de Datos Corrupta

Si el sistema detecta que la base de datos está corrupta:

1. ✅ **Crea el backup de todas formas** (marcado como `_CORRUPTED.db`)
2. ⚠️  **Registra warning** en el log
3. 📧 **Continúa normalmente** (no interrumpe el sistema)

Ejemplo:
```
⚠️  Database integrity check failed: database disk image is malformed
⚠️  Creating backup anyway (corrupted database backup)...
💾 Creating backup: trading_data_2024-12-30_220015_CORRUPTED.db
```

### Fallo de Backup

Si el backup falla:

1. ❌ **Registra error** en el log
2. 🔄 **Reintenta al día siguiente** automáticamente
3. 📧 **No interrumpe** el sistema de trading

## 🔐 Seguridad

- ✅ Usa SQLite backup API (seguro para DBs activas)
- ✅ Valida integridad antes de restaurar
- ✅ Crea backup pre-restauración automáticamente
- ✅ No sobrescribe backups existentes (timestamped únicos)

## 💡 Mejores Prácticas

1. **Verifica backups periódicamente**
   ```bash
   python scripts/maintenance/restore_database_backup.py
   # Revisa la lista sin restaurar (quit con 'q')
   ```

2. **Monitorea el espacio en disco**
   - Los backups ocupan ~150 MB cada uno
   - Con 30 días de retención: ~4.5 GB total
   - Ajusta retención si es necesario

3. **Backups adicionales antes de cambios importantes**
   ```python
   # En Python
   manager = DatabaseBackupManager()
   manager.create_backup(force=True)
   ```

4. **Backups offsite (opcional)**
   - Copia periódicamente `backups/database/` a cloud storage
   - Ejemplo: Google Drive, Dropbox, AWS S3

## 🔧 Configuración

### Cambiar Retención de Backups

Editar `core/database_backup_manager.py`:

```python
# Línea ~230 en _cleanup_old_backups()
cutoff_date = datetime.now() - timedelta(days=30)  # Cambiar 30 a los días deseados

# Línea ~245 - daily backups
for old_daily in daily_backups[7:]:  # Cambiar 7 a los días deseados
```

### Cambiar Horario de Backup

El backup está atado al EOD OHLC scheduler (PHASE 2).

Para cambiar horario, editar `trader_main.py`:

```python
# Línea ~444
post_close_target = time(22, 0)  # Cambiar hora (formato 24h)
```

## ❓ FAQ

**Q: ¿Los backups afectan al rendimiento?**
A: No. Se ejecutan después del cierre del mercado (22:00) cuando no hay trading activo.

**Q: ¿Puedo hacer backups durante el horario de trading?**
A: Sí, usa `force=True` en el manager, pero es innecesario ya que hay uno automático diario.

**Q: ¿Qué pasa si el sistema se cae durante el backup?**
A: El backup usa la API de SQLite que es atómica. Si falla, simplemente no se crea el backup.

**Q: ¿Los backups incluyen todas las tablas?**
A: Sí, el backup copia la base de datos completa (todas las tablas).

**Q: ¿Puedo desactivar los backups automáticos?**
A: No recomendado, pero puedes comentar las líneas 483-494 en `trader_main.py`.

## 📞 Soporte

Si tienes problemas con los backups:

1. Revisa los logs: `tail -100 logs/trader.log | grep "💾"`
2. Lista los backups: `python scripts/maintenance/restore_database_backup.py`
3. Verifica espacio en disco: `du -sh backups/database/`
4. Prueba backup manual: `manager.create_backup(force=True)`

## 🎯 Versiones

- **v3**: Paper trading - `/CLAUDE/trading_system_v3/`
- **v3_A**: Real account - `/CLAUDE/trading_system_v3_A/`

Ambos sistemas tienen el mismo sistema de backup configurado.
