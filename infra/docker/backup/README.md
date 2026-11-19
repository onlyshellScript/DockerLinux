# Respaldos del stack de producción (SQL Server + uploads)

Scripts:

- `backup.sh`: `BACKUP DATABASE` con `CHECKSUM` (y `COMPRESSION` si la edición no es Express)
  dentro del contenedor `sqlserver`, `RESTORE VERIFYONLY`, copia del `.bak` al host con
  `docker compose cp`, `tar.gz` del volumen `api-uploads` y retención por días.
- `restore.sh`: detiene `api`/`worker`, restaura con `WITH REPLACE` (reubica los archivos con
  `MOVE`), restaura uploads opcionalmente y vuelve a arrancar los servicios que estaban corriendo.
- `common.sh`: funciones compartidas (no se ejecuta solo).

La contraseña SA **no** se pasa a los scripts: se lee del entorno del contenedor `sqlserver`.

## Parámetros

| Variable / opción | Default | Uso |
|---|---|---|
| `COMPOSE_PROJECT` / `-p` | `sigos` | nombre del proyecto compose (`docker compose -p`) |
| `COMPOSE_FILE_PATH` / `-f` | `infra/docker/docker-compose.prod.yaml` | archivo compose |
| `ENV_FILE` / `-e` | (ninguno) | `--env-file` para la interpolación del compose |
| `DB_NAME` | `sigos` | base a respaldar o restaurar |
| `BACKUP_DIR` / `-o` | `./backups` | destino en el host |
| `BACKUP_RETENTION_DAYS` / `-r` | `14` | borra `.bak`/`tar.gz` más antiguos (0 = no borrar) |
| `--no-uploads` | | omite el tar del volumen |

Códigos de salida de `backup.sh`: 0 ok, 1 uso, 2 entorno, 3 SQL Server caído, 4 BACKUP,
5 VERIFYONLY, 6 copia al host, 7 tar de uploads. Los de `restore.sh`: 0 ok, 1 uso, 2 entorno,
3 SQL Server caído, 4 copia, 5 RESTORE, 6 uploads, 10 cancelado. Los logs van a stderr con fecha y nivel.

## Uso manual

```bash
cd /opt/sigos
infra/docker/backup/backup.sh -p sigos -e infra/docker/.env.prod -o /var/backups/sigos
infra/docker/backup/restore.sh -p sigos -e infra/docker/.env.prod \
  -u /var/backups/sigos/uploads_20261118_020000.tar.gz /var/backups/sigos/sigos_20261118_020000.bak
```

`restore.sh` pide escribir `si`; usa `--yes` en automatizaciones.

## Programación diaria (02:00)

### cron

```cron
0 2 * * * cd /opt/sigos && BACKUP_DIR=/var/backups/sigos infra/docker/backup/backup.sh -p sigos -e infra/docker/.env.prod >> /var/log/sigos-backup.log 2>&1
```

### systemd timer

`/etc/systemd/system/sigos-backup.service`:

```ini
[Unit]
Description=Respaldo SIGOS
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/sigos
Environment=BACKUP_DIR=/var/backups/sigos BACKUP_RETENTION_DAYS=14
ExecStart=/opt/sigos/infra/docker/backup/backup.sh -p sigos -e /opt/sigos/infra/docker/.env.prod
```

`/etc/systemd/system/sigos-backup.timer`:

```ini
[Unit]
Description=Respaldo diario SIGOS

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload && systemctl enable --now sigos-backup.timer
journalctl -u sigos-backup.service   # ver logs
```

Copia los respaldos fuera del servidor (rsync/rclone a otro host u objeto) y monitoriza el código de salida.

## Probar la restauración (recomendado mensualmente)

Hazlo en un proyecto aislado, nunca sobre producción:

```bash
P=sigosrestoretest
docker compose -p $P -f infra/docker/docker-compose.prod.yaml --env-file /ruta/env-de-prueba up -d sqlserver
infra/docker/backup/restore.sh -p $P -e /ruta/env-de-prueba --yes /var/backups/sigos/sigos_AAAAMMDD_HHMMSS.bak
docker compose -p $P -f infra/docker/docker-compose.prod.yaml --env-file /ruta/env-de-prueba \
  exec sqlserver bash -c '/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C \
  -Q "SELECT COUNT(*) FROM sigos.sys.tables"'
docker compose -p $P -f infra/docker/docker-compose.prod.yaml --env-file /ruta/env-de-prueba down -v
```

En Windows con Git Bash los scripts exportan `MSYS_NO_PATHCONV=1` para que no se reescriban las rutas del contenedor.
