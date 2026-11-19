# shellcheck shell=bash
# Funciones compartidas por backup.sh y restore.sh. No ejecutar directamente.
set -Eeuo pipefail
# Los respaldos contienen datos personales y hashes: nada legible por otros usuarios.
umask 077
# Git Bash (MSYS) reescribe rutas tipo /var/opt/...; desactivarlo es inocuo en Linux.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && { pwd -W 2>/dev/null || pwd; })"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-sigos}"
COMPOSE_FILE_PATH="${COMPOSE_FILE_PATH:-$REPO_ROOT/infra/docker/docker-compose.prod.yaml}"
ENV_FILE="${ENV_FILE:-}"
DB_NAME="${DB_NAME:-sigos}"
SQL_SERVICE="${SQL_SERVICE:-sqlserver}"
CONTAINER_BACKUP_DIR="/var/opt/mssql/backup"
SQLCMD="/opt/mssql-tools18/bin/sqlcmd"

log()  { printf '%s [%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$1" "${*:2}" >&2; }
info() { log INFO "$@"; }
warn() { log WARN "$@"; }
die()  { local code="$1"; shift; log ERROR "$@"; exit "$code"; }

dc() {
  local args=(-p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE_PATH")
  if [[ -n "$ENV_FILE" ]]; then args+=(--env-file "$ENV_FILE"); fi
  docker compose "${args[@]}" "$@"
}

SIGOS_UID="${SIGOS_UID:-1000}"   # UID del usuario sigos de la imagen de la API
SAFE_NAME_RE='^[A-Za-z0-9._-]+$'

# Ejecuta T-SQL dentro del contenedor; la contrasena SA se lee del entorno del propio
# contenedor, asi el host no necesita conocerla.
sql() {
  # SQLCMDPASSWORD en lugar de -P: la contrasena no aparece en la linea de comandos (ps).
  dc exec -T "$SQL_SERVICE" bash -c \
    'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" exec "$2" -S localhost -U sa -C -b -h -1 -W -Q "$1"' _ "$1" "$SQLCMD"
}

volume_name() { # $1 = nombre logico del volumen en el compose
  docker volume ls -q \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    --filter "label=com.docker.compose.volume=$1" | head -n1
}

require_sqlserver() {
  command -v docker >/dev/null || die 2 "docker no esta instalado"
  [[ -f "$COMPOSE_FILE_PATH" ]] || die 2 "No existe el compose: $COMPOSE_FILE_PATH"
  [[ "$DB_NAME" =~ ^[A-Za-z0-9_]+$ ]] || die 2 "DB_NAME invalido: $DB_NAME"
  sql "SELECT 1" >/dev/null || die 3 "SQL Server ($SQL_SERVICE) no responde en el proyecto $COMPOSE_PROJECT"
}
