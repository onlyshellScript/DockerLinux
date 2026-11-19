#!/usr/bin/env bash
# shellcheck disable=SC2034  # variables usadas por los scripts que cargan esta libreria
# Funciones compartidas de los scripts de SIGOS para Linux (no se ejecuta solo).
# Rutas de instalacion: programa en /opt/sigos, configuracion en /etc/sigos, datos/estado en /var/lib/sigos.
# Los datos de la aplicacion (BD, archivos subidos, certificados) viven en volumenes Docker del proyecto "sigos".

SIGOS_HOME="${SIGOS_HOME:-/opt/sigos}"
SIGOS_ETC="${SIGOS_ETC:-/etc/sigos}"
SIGOS_VAR="${SIGOS_VAR:-/var/lib/sigos}"
SIGOS_LOG_DIR="${SIGOS_LOG_DIR:-/var/log/sigos}"
SIGOS_PROJECT="sigos"
SIGOS_ENV_FILE="$SIGOS_ETC/sigos.env"
SIGOS_CONF="$SIGOS_ETC/install.conf"
SIGOS_COMPOSE="$SIGOS_HOME/compose/docker-compose.prod.yaml"
SIGOS_UNIT="sigos.service"
SIGOS_UNIT_FILE="/etc/systemd/system/$SIGOS_UNIT"
SIGOS_DEFAULT_IMAGE="ghcr.io/onlyshellscript/dockerlinux/sigos-api"
SIGOS_RELEASES_URL="https://github.com/onlyshellScript/DockerLinux/releases"

# Codigos de salida comunes
EXIT_OK=0; EXIT_USAGE=1; EXIT_ROOT=2; EXIT_PREREQ=3; EXIT_DOCKER=4; EXIT_START=5; EXIT_HEALTH=6
EXIT_NOT_INSTALLED=7; EXIT_ADMIN=8; EXIT_UPDATE=9; EXIT_CANCEL=10

if [[ -t 1 ]]; then C_B=$'\e[1m'; C_G=$'\e[32m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_0=$'\e[0m'; else C_B=; C_G=; C_Y=; C_R=; C_0=; fi

step() { printf '\n%s==> %s%s\n' "$C_B" "$*" "$C_0"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '    %s[OK]%s %s\n' "$C_G" "$C_0" "$*"; }
warn() { printf '    %s[AVISO]%s %s\n' "$C_Y" "$C_0" "$*" >&2; }
die()  { local code="$1"; shift; printf '\n%s[ERROR]%s %s\n' "$C_R" "$C_0" "$*" >&2; exit "$code"; }

require_root() {
  [[ ${EUID:-$(id -u)} -eq 0 ]] || die "$EXIT_ROOT" "Ejecute como root: sudo $0 $*"
}

is_installed() { [[ -f "$SIGOS_COMPOSE" && -f "$SIGOS_ENV_FILE" ]]; }

require_installed() {
  is_installed || die "$EXIT_NOT_INSTALLED" "SIGOS no esta instalado (falta $SIGOS_COMPOSE o $SIGOS_ENV_FILE). Ejecute install.sh."
}

# docker compose del stack instalado. El .env solo lo lee root (0600): por eso los comandos que lo usan exigen root.
dc() { docker compose -p "$SIGOS_PROJECT" --env-file "$SIGOS_ENV_FILE" -f "$SIGOS_COMPOSE" "$@"; }

# Lee una clave de un archivo KEY=VALUE sin ejecutarlo (no se hace "source" de archivos de configuracion).
env_get() {
  local file="$1" key="$2"
  [[ -f "$file" ]] || return 1
  awk -v k="$key" 'BEGIN{FS="="} $0 !~ /^[[:space:]]*#/ && $1==k { sub(/^[^=]*=/, ""); sub(/[[:space:]]+#.*$/, ""); print; found=1; exit } END{ exit !found }' "$file"
}

# Anade KEY=VALUE solo si la clave no existe (nunca sobrescribe valores del usuario).
env_add_missing() {
  local file="$1" key="$2" value="$3"
  if ! grep -qE "^[[:space:]]*${key}=" "$file" 2>/dev/null; then
    printf '%s=%s\n' "$key" "$value" >> "$file"
    return 0
  fi
  return 1
}

# Cambia (o anade) KEY=VALUE. Solo para claves de gestion del instalador (version de imagen), nunca secretos.
env_set() {
  local file="$1" key="$2" value="$3" tmp
  tmp="$(mktemp "$file.XXXXXX")"
  if grep -qE "^[[:space:]]*${key}=" "$file"; then
    awk -v k="$key" -v v="$value" 'BEGIN{FS="="} $1==k { print k "=" v; next } { print }' "$file" > "$tmp"
  else
    cat "$file" > "$tmp"; printf '%s=%s\n' "$key" "$value" >> "$tmp"
  fi
  chmod --reference="$file" "$tmp" 2>/dev/null || chmod 600 "$tmp"
  mv -f "$tmp" "$file"
}

# Secreto aleatorio (CSPRNG del kernel), sin caracteres que el compose o las URLs interpreten ($ / + = @ : %),
# y con mayuscula, minuscula, digito y simbolo para cumplir la politica de contrasenas de SQL Server.
new_secret() {
  local len="${1:-32}" s=""
  while [[ ${#s} -lt $len ]]; do
    s+="$(head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')"
  done
  printf '%s-Aa1' "${s:0:$len}"
}

# Contrasena inicial del admin: cumple la politica de la API (>=10, mayuscula, minuscula, numero).
new_admin_password() {
  local s=""
  while [[ ${#s} -lt 14 ]]; do s+="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-HJ-NP-Za-km-z2-9')"; done
  printf '%s-%s7Q' "${s:0:7}" "${s:7:7}"
}

check_password_policy() {
  local p="$1"
  [[ ${#p} -ge 10 && "$p" =~ [A-Z] && "$p" =~ [a-z] && "$p" =~ [0-9] && "${p,,}" != "admin" ]]
}

http_port() { local p; p="$(env_get "$SIGOS_ENV_FILE" HTTP_PORT 2>/dev/null || true)"; printf '%s' "${p:-80}"; }

local_url() { local p; p="$(http_port)"; if [[ "$p" == "80" ]]; then printf 'http://127.0.0.1'; else printf 'http://127.0.0.1:%s' "$p"; fi; }

# GET /api/v1/health a traves del proxy local. Devuelve 0 si status=UP.
health_up() {
  local body
  body="$(curl -fsS --max-time 5 "$(local_url)/api/v1/health" 2>/dev/null)" || return 1
  [[ "$body" == *'"status":"UP"'* || "$body" == *'"status": "UP"'* ]]
}

wait_health() {
  local timeout="${1:-180}" t=0
  until health_up; do
    (( t >= timeout )) && return 1
    sleep 5; t=$((t + 5))
  done
}

diagnose() {
  warn "Diagnostico:"
  dc ps -a 2>&1 | sed 's/^/      /' >&2 || true
  local s
  for s in migrate api worker proxy sqlserver; do
    printf '      --- %s (ultimas 25 lineas) ---\n' "$s" >&2
    dc logs --no-color --tail 25 "$s" 2>&1 | sed 's/^/      /' >&2 || true
  done
}

# Version de Docker Compose v2 >= 2.20 (necesaria para "up --wait" con servicios one-shot).
compose_ok() {
  local v
  v="$(docker compose version --short 2>/dev/null)" || return 1
  v="${v#v}"
  local major="${v%%.*}" rest="${v#*.}"; local minor="${rest%%.*}"
  [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] || return 1
  (( major > 2 || (major == 2 && minor >= 20) ))
}

conf_get() { env_get "$SIGOS_CONF" "$1" 2>/dev/null || true; }
