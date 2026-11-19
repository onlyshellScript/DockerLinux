#!/usr/bin/env bash
# Restauracion de SIGOS desde un .bak (y opcionalmente un tar.gz de uploads).
# Uso: restore.sh [-p proyecto] [-f compose.yaml] [-e env-file] [-u uploads.tar.gz] [--yes] archivo.bak
# Detiene api/worker, ejecuta RESTORE ... WITH REPLACE y vuelve a arrancar los que corrian.
# Codigos: 0 ok | 1 uso | 2 entorno | 3 SQL Server caido | 4 copia fallo | 5 RESTORE fallo | 6 uploads fallo | 10 cancelado
# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

YES=0; UPLOADS_TGZ=""; BAK_FILE=""
APP_SERVICES=(api worker)
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p) COMPOSE_PROJECT="$2"; shift 2;;
    -f) COMPOSE_FILE_PATH="$2"; shift 2;;
    -e) ENV_FILE="$2"; shift 2;;
    -u) UPLOADS_TGZ="$2"; shift 2;;
    -y|--yes) YES=1; shift;;
    -h|--help) sed -n '2,5p' "$0"; exit 0;;
    -*) die 1 "Argumento desconocido: $1";;
    *) BAK_FILE="$1"; shift;;
  esac
done
[[ -n "$BAK_FILE" && -s "$BAK_FILE" ]] || die 1 "Indica un .bak existente"
[[ -z "$UPLOADS_TGZ" || -s "$UPLOADS_TGZ" ]] || die 1 "No existe $UPLOADS_TGZ"
[[ "$(basename "$BAK_FILE")" =~ $SAFE_NAME_RE ]] || die 1 "Nombre de .bak no permitido (solo A-Z a-z 0-9 . _ -): $(basename "$BAK_FILE")"
if [[ -n "$UPLOADS_TGZ" && ! "$(basename "$UPLOADS_TGZ")" =~ $SAFE_NAME_RE ]]; then
  die 1 "Nombre de uploads no permitido (solo A-Z a-z 0-9 . _ -): $(basename "$UPLOADS_TGZ")"
fi
BAK_FILE="$(cd "$(dirname "$BAK_FILE")" && { pwd -W 2>/dev/null || pwd; })/$(basename "$BAK_FILE")"

require_sqlserver
warn "Se SOBRESCRIBIRA la BD [$DB_NAME] del proyecto $COMPOSE_PROJECT con $BAK_FILE"
if [[ -n "$UPLOADS_TGZ" ]]; then warn "y se REEMPLAZARA el volumen api-uploads con $UPLOADS_TGZ"; fi
if [[ $YES -ne 1 ]]; then
  read -r -p "Escribe si para continuar: " ans
  [[ "$ans" == "si" ]] || die 10 "Cancelado por el usuario"
fi

RUNNING="$(dc ps --status running --services 2>/dev/null || true)"
restart_apps() {
  local s
  for s in "${APP_SERVICES[@]}"; do
    if grep -qx "$s" <<<"$RUNNING"; then
      info "Arrancando $s"
      dc up -d --no-deps "$s" >&2 || warn "No se pudo arrancar $s"
    fi
  done
}
trap restart_apps EXIT
info "Deteniendo ${APP_SERVICES[*]}"
dc stop "${APP_SERVICES[@]}" >&2 || warn "No se pudieron detener todos los servicios"

CBAK="$CONTAINER_BACKUP_DIR/restore_$(basename "$BAK_FILE")"
dc exec -T "$SQL_SERVICE" mkdir -p "$CONTAINER_BACKUP_DIR"
dc cp "$BAK_FILE" "$SQL_SERVICE:$CBAK" || die 4 "No se pudo copiar el .bak al contenedor"
# docker cp deja el archivo como root; sqlservr corre como mssql.
dc exec -T -u 0 "$SQL_SERVICE" chown mssql "$CBAK" >/dev/null 2>&1 || true

info "RESTORE DATABASE [$DB_NAME] WITH REPLACE"
sql "SET NOCOUNT ON;
DECLARE @data nvarchar(260) = CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS nvarchar(260));
DECLARE @log  nvarchar(260) = CAST(SERVERPROPERTY('InstanceDefaultLogPath') AS nvarchar(260));
DECLARE @f TABLE (LogicalName nvarchar(128), PhysicalName nvarchar(260), [Type] char(1), FileGroupName nvarchar(128),
  Size numeric(20,0), MaxSize numeric(20,0), FileId bigint, CreateLSN numeric(25,0), DropLSN numeric(25,0),
  UniqueId uniqueidentifier, ReadOnlyLSN numeric(25,0), ReadWriteLSN numeric(25,0), BackupSizeInBytes bigint,
  SourceBlockSize int, FileGroupId int, LogGroupGUID uniqueidentifier, DifferentialBaseLSN numeric(25,0),
  DifferentialBaseGUID uniqueidentifier, IsReadOnly bit, IsPresent bit, TDEThumbprint varbinary(32), SnapshotUrl nvarchar(360));
INSERT @f EXEC (N'RESTORE FILELISTONLY FROM DISK = N''$CBAK''');
DECLARE @move nvarchar(max) = N'';
SELECT @move += N', MOVE N''' + LogicalName + N''' TO N''' + CASE WHEN [Type] = 'L' THEN @log ELSE @data END
  + N'$DB_NAME' + CASE WHEN [Type] = 'L' THEN N'_log.ldf' WHEN FileId = 1 THEN N'.mdf'
  ELSE N'_' + LogicalName + N'.ndf' END + N'''' FROM @f;
IF DB_ID(N'$DB_NAME') IS NOT NULL EXEC (N'ALTER DATABASE [$DB_NAME] SET SINGLE_USER WITH ROLLBACK IMMEDIATE');
DECLARE @s nvarchar(max) = N'RESTORE DATABASE [$DB_NAME] FROM DISK = N''$CBAK'' WITH REPLACE, CHECKSUM, RECOVERY, STATS = 25' + @move;
EXEC (@s);
EXEC (N'ALTER DATABASE [$DB_NAME] SET MULTI_USER');" >&2 || {
  sql "IF DB_ID(N'$DB_NAME') IS NOT NULL ALTER DATABASE [$DB_NAME] SET MULTI_USER" >/dev/null 2>&1 || true
  die 5 "RESTORE fallo"
}
dc exec -T "$SQL_SERVICE" rm -f "$CBAK" || true
info "OK BD restaurada: $(sql "SET NOCOUNT ON; SELECT COUNT(*) FROM [$DB_NAME].sys.tables" | tr -d '\r') tablas"

if [[ -n "$UPLOADS_TGZ" ]]; then
  VOL="$(volume_name api-uploads)"
  [[ -n "$VOL" ]] || die 6 "El volumen api-uploads no existe en el proyecto $COMPOSE_PROJECT"
  TDIR="$(cd "$(dirname "$UPLOADS_TGZ")" && { pwd -W 2>/dev/null || pwd; })"
  info "Restaurando uploads en $VOL"
  # Nombre como argumento posicional (sin interpolar en el script); --no-same-owner y chown al
  # usuario sigos de la imagen para que api/worker puedan escribir.
  docker run --rm -v "$VOL:/data" -v "$TDIR:/backup:ro" alpine:3 sh -c \
    'find /data -mindepth 1 -delete && tar -xzf "/backup/$1" --no-same-owner -C /data && chown -R "$2:$2" /data' \
    _ "$(basename "$UPLOADS_TGZ")" "$SIGOS_UID" \
    || die 6 "Restauracion de uploads fallo"
fi
info "Restauracion completada"
