# Respaldos (RNF-13 / RNF-14)

## SQLite (desarrollo/pruebas)
Script: `scripts/backup_sqlite.py`
Variables de entorno:
- SIGOS_DB_PATH (default sigos.db)
- SIGOS_BACKUP_DIR (default backups)
- SIGOS_BACKUP_RETENTION (default 7)

Ejecucion manual:
```
python scripts/backup_sqlite.py
```

Programacion diaria:
- Linux (cron): `0 2 * * * /usr/bin/python3 /opt/sigos/scripts/backup_sqlite.py`
- systemd: timer diario que ejecute el script.
- Windows (Task Scheduler): tarea diaria ejecutando `python scripts\backup_sqlite.py`.

Retencion: conserva los ultimos N respaldos (configurable). Restauracion: copiar el archivo de respaldo sobre la BD y verificar conteos.

Prueba automatizada: `tests/test_rnf13_backup.py` restaura el ultimo respaldo en una BD temporal y compara conteos.

## SQL Server (produccion)
Equivalente con BACKUP/RESTORE:
```
BACKUP DATABASE sigos TO DISK = 'C:\backups\sigos_YYYYMMDD.bak' WITH INIT, COMPRESSION;
```
Restauracion:
```
RESTORE DATABASE sigos FROM DISK = 'C:\backups\sigos_YYYYMMDD.bak' WITH REPLACE;
```
Programar con SQL Server Agent (job diario) o Task Scheduler invocando sqlcmd. Retencion: eliminar archivos mas antiguos a N dias (script PowerShell).
