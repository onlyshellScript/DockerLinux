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

## SQL Server en Docker (producción)

En el despliegue con `infra/docker/docker-compose.prod.yaml` los respaldos se hacen con los scripts de
[`infra/docker/backup/`](../infra/docker/backup/README.md):

- `backup.sh`: `BACKUP DATABASE` con `CHECKSUM` + `RESTORE VERIFYONLY`, copia del `.bak` al host y tar.gz del
  volumen de evidencias (`api-uploads`), con retención (`BACKUP_RETENTION_DAYS`, 14 días por defecto).
  En SQL Server Express no hay `COMPRESSION`; el script la activa solo en ediciones que la soportan.
- `restore.sh`: detiene `api` y `worker`, restaura con `REPLACE` y vuelve a arrancarlos.

Programación (cron/systemd) y prueba de restauración: ver el README de esa carpeta.
Los respaldos deben copiarse fuera del servidor (rsync/rclone); los scripts no lo hacen.
