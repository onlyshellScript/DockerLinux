#!/usr/bin/env bash
# Actualizacion de SIGOS a la ultima imagen publicada (o a --version TAG).
#   1. Consulta/descarga la imagen nueva y la compara con la instalada (si es la misma, termina).
#   2. Respaldo de la BD y archivos (backup.sh) salvo --no-backup.
#   3. Recrea los servicios: "migrate" aplica las migraciones pendientes (alembic upgrade, nunca destructivo).
#   4. Verifica healthchecks y la API. Si falla, vuelve a la imagen anterior y lo informa
#      (las migraciones son aditivas; si hiciera falta, el respaldo del paso 2 se restaura con "sigos restore").
# Nunca elimina volumenes ni bases de datos.
#
#   sudo sigos update [--version TAG] [--no-backup] [--no-pull] [--force] [--yes]
#   --no-pull: usar una imagen ya cargada localmente (p. ej. "docker load" sin conexion)
# Codigos: 0 actualizado o ya al dia | 9 fallo y se revirtio | 5 fallo sin poder revertir.
set -Eeuo pipefail
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
# shellcheck source=lib/common.sh
source "$(dirname "$SELF")/../lib/common.sh"

NEW_VERSION=""; NO_BACKUP=0; NO_PULL=0; FORCE=0; YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) NEW_VERSION="${2:?}"; shift ;;
    --no-backup) NO_BACKUP=1 ;;
    --no-pull) NO_PULL=1 ;;
    --force) FORCE=1 ;;
    --yes|-y) YES=1 ;;
    -h|--help) sed -n '2,13p' "$SELF" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "$EXIT_USAGE" "Opcion desconocida: $1" ;;
  esac; shift
done
require_root; require_installed
mkdir -p "$SIGOS_LOG_DIR"; LOG_FILE="$SIGOS_LOG_DIR/update-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

repo="$(env_get "$SIGOS_ENV_FILE" SIGOS_IMAGE)"; old_tag="$(env_get "$SIGOS_ENV_FILE" SIGOS_VERSION)"
tag="${NEW_VERSION:-$old_tag}"
step "Consultando $repo:$tag"
old_id="$(docker image inspect --format '{{.Id}}' "$repo:$old_tag" 2>/dev/null || true)"
# Imagen anterior conservada con una etiqueta local para poder revertir aunque la etiqueta remota se mueva.
if [[ -n "$old_id" ]]; then docker tag "$old_id" "$repo:sigos-rollback"; fi
if [[ $NO_PULL -eq 0 ]]; then
  docker pull --quiet "$repo:$tag" >/dev/null || die "$EXIT_UPDATE" "No se pudo descargar $repo:$tag (red, etiqueta o permisos de GHCR)."
fi
docker image inspect "$repo:$tag" >/dev/null 2>&1 || die "$EXIT_UPDATE" "La imagen $repo:$tag no existe localmente."
new_id="$(docker image inspect --format '{{.Id}}' "$repo:$tag")"
if [[ "$new_id" == "$old_id" && $FORCE -eq 0 ]]; then ok "Ya esta en la ultima version ($tag, ${new_id:7:12})."; exit 0; fi
info "Instalada: ${old_id:7:12}  ->  Nueva: ${new_id:7:12}"
if [[ $YES -eq 0 && -t 0 ]]; then read -r -p "    ¿Actualizar ahora? Habra una breve interrupcion del servicio [S/n] " a; [[ "${a:-s}" =~ ^[sSyY] ]] || exit "$EXIT_CANCEL"; fi

if [[ $NO_BACKUP -eq 0 ]]; then
  step "Respaldo previo"
  "$SIGOS_HOME/backup/backup.sh" -p "$SIGOS_PROJECT" -f "$SIGOS_COMPOSE" -e "$SIGOS_ENV_FILE" -o "$SIGOS_VAR/backups" \
    || die "$EXIT_UPDATE" "El respaldo fallo: no se actualiza. Use --no-backup para omitirlo bajo su responsabilidad."
  ok "Respaldo en $SIGOS_VAR/backups"
fi

[[ "$tag" != "$old_tag" ]] && env_set "$SIGOS_ENV_FILE" SIGOS_VERSION "$tag"
step "Aplicando (migraciones + recreacion de servicios)"
if dc up -d --wait --wait-timeout "${SIGOS_WAIT_TIMEOUT:-900}" --remove-orphans && wait_health 180; then
  systemctl start "$SIGOS_UNIT" >/dev/null 2>&1 || true
  printf '%s %s %s\n' "$(date -Is)" "$repo:$tag" "$new_id" >> "$SIGOS_VAR/state/update-history"
  ok "SIGOS actualizado a $repo:$tag (${new_id:7:12}). Registro: $LOG_FILE"
  exit 0
fi

diagnose
warn "La version nueva no quedo sana. Revirtiendo a la imagen anterior..."
if [[ -z "$old_id" ]]; then die "$EXIT_START" "No hay imagen anterior para revertir. Restaure con: sudo sigos restore <respaldo>.bak"; fi
docker tag "$repo:sigos-rollback" "$repo:$old_tag"
[[ "$tag" != "$old_tag" ]] && env_set "$SIGOS_ENV_FILE" SIGOS_VERSION "$old_tag"
if dc up -d --wait --wait-timeout "${SIGOS_WAIT_TIMEOUT:-900}" && wait_health 180; then
  warn "Revertido a la imagen anterior (${old_id:7:12}). Si la BD quedo inconsistente: sudo sigos restore $SIGOS_VAR/backups/<ultimo>.bak"
  exit "$EXIT_UPDATE"
fi
die "$EXIT_START" "No se pudo revertir automaticamente. Revise 'sudo sigos logs' y restaure el respaldo previo."
