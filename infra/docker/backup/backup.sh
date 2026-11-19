#!/usr/bin/env bash
# Respaldo de SIGOS: BD SQL Server (.bak verificado) + volumen api-uploads (tar.gz).
# Uso: backup.sh [-p proyecto] [-f compose.yaml] [-e env-file] [-o dir] [-r dias] [--no-uploads]
# Codigos: 0 ok | 1 uso | 2 entorno | 3 SQL Server caido | 4 BACKUP fallo
#          5 VERIFYONLY fallo | 6 copia al host fallo | 7 tar de uploads fallo
# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
WITH_UPLOADS=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p) COMPOSE_PROJECT="$2"; shift 2;;
    -f) COMPOSE_FILE_PATH="$2"; shift 2;;
    -e) ENV_FILE="$2"; shift 2;;
    -o) BACKUP_DIR="$2"; shift 2;;
    -r) BACKUP_RETENTION_DAYS="$2"; shift 2;;
    --no-uploads) WITH_UPLOADS=0; shift;;
    -h|--help) sed -n '2,5p' "$0"; exit 0;;
    *) die 1 "Argumento desconocido: $1";;
  esac
done
[[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]] || die 1 "BACKUP_RETENTION_DAYS debe ser entero"

mkdir -p "$BACKUP_DIR" || die 2 "No se puede crear $BACKUP_DIR"
# pwd -W da ruta Windows en Git Bash (docker.exe no entiende /tmp); en Linux se usa pwd
chmod 700 "$BACKUP_DIR" || warn "No se pudo aplicar chmod 700 a $BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && { pwd -W 2>/dev/null || pwd; })"
TS="$(date +%Y%m%d_%H%M%S)"
BAK="${DB_NAME}_${TS}.bak"
CBAK="$CONTAINER_BACKUP_DIR/$BAK"

info "Proyecto=$COMPOSE_PROJECT BD=$DB_NAME destino=$BACKUP_DIR retencion=${BACKUP_RETENTION_DAYS}d"
require_sqlserver
dc exec -T "$SQL_SERVICE" mkdir -p "$CONTAINER_BACKUP_DIR" || die 4 "No se pudo crear $CONTAINER_BACKUP_DIR"

# COMPRESSION no existe en Express (EngineEdition=4): se decide en el servidor.
info "BACKUP DATABASE [$DB_NAME] -> $CBAK"
sql "SET NOCOUNT ON;
DECLARE @opt nvarchar(200) = N'INIT, FORMAT, CHECKSUM, STATS = 25';
IF CAST(SERVERPROPERTY('EngineEdition') AS int) <> 4 SET @opt = @opt + N', COMPRESSION';
PRINT 'Edicion: ' + CAST(SERVERPROPERTY('Edition') AS nvarchar(128)) + ' | opciones: ' + @opt;
DECLARE @s nvarchar(max) = N'BACKUP DATABASE [$DB_NAME] TO DISK = N''$CBAK'' WITH ' + @opt;
EXEC (@s);" >&2 || die 4 "BACKUP DATABASE fallo"

info "RESTORE VERIFYONLY"
sql "RESTORE VERIFYONLY FROM DISK = N'$CBAK' WITH CHECKSUM" >&2 || die 5 "RESTORE VERIFYONLY fallo: $CBAK"

info "Copiando $BAK al host"
dc cp "$SQL_SERVICE:$CBAK" "$BACKUP_DIR/$BAK" || die 6 "docker compose cp fallo"
[[ -s "$BACKUP_DIR/$BAK" ]] || die 6 "El .bak copiado esta vacio"
chmod 600 "$BACKUP_DIR/$BAK" || warn "No se pudo aplicar chmod 600 a $BAK"
dc exec -T "$SQL_SERVICE" rm -f "$CBAK" || warn "No se pudo borrar $CBAK del contenedor"
info "OK BD: $BACKUP_DIR/$BAK ($(du -h "$BACKUP_DIR/$BAK" | cut -f1))"

if [[ $WITH_UPLOADS -eq 1 ]]; then
  VOL="$(volume_name api-uploads)"
  if [[ -z "$VOL" ]]; then
    warn "El volumen api-uploads no existe en el proyecto $COMPOSE_PROJECT; se omite"
  else
    TGZ="uploads_${TS}.tar.gz"
    info "Empaquetando volumen $VOL -> $TGZ"
    # El tar corre con el UID/GID del host para que el archivo sea suyo. En Git Bash id puede dar
    # valores no validos para el contenedor: si falla, se crea como root y se corrige despues.
    HOST_UG="$(id -u 2>/dev/null):$(id -g 2>/dev/null)"
    if ! docker run --rm --user "$HOST_UG" -v "$VOL:/data:ro" -v "$BACKUP_DIR:/backup" alpine:3 \
        sh -c 'umask 077 && tar -czf "/backup/$1" -C /data .' _ "$TGZ"; then
      warn "tar con --user $HOST_UG fallo; reintentando como root con chown posterior"
      docker run --rm -v "$VOL:/data:ro" -v "$BACKUP_DIR:/backup" alpine:3 \
        sh -c 'umask 077 && tar -czf "/backup/$1" -C /data . && chown "$2" "/backup/$1"' _ "$TGZ" "$HOST_UG" \
        || die 7 "tar de uploads fallo"
    fi
    chmod 600 "$BACKUP_DIR/$TGZ" || warn "No se pudo aplicar chmod 600 a $TGZ"
    info "OK uploads: $BACKUP_DIR/$TGZ ($(du -h "$BACKUP_DIR/$TGZ" | cut -f1))"
  fi
fi

if [[ "$BACKUP_RETENTION_DAYS" -gt 0 ]]; then
  info "Retencion: borrando respaldos con mas de $BACKUP_RETENTION_DAYS dias"
  find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "${DB_NAME}_*.bak" -o -name 'uploads_*.tar.gz' \) \
    -mtime +"$BACKUP_RETENTION_DAYS" -print -delete >&2 || warn "Fallo aplicando la retencion"
fi
info "Respaldo completado"
