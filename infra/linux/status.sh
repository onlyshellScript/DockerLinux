#!/usr/bin/env bash
# Estado de SIGOS: servicio systemd, contenedores, salud de la API y espacio en disco.
# Sin sudo muestra un resumen (servicio + health); con sudo, tambien el detalle de contenedores.
# Codigo de salida: 0 todo sano | 6 API no responde | 7 no instalado | 5 servicio no activo.
set -Euo pipefail
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
# shellcheck source=lib/common.sh
source "$(dirname "$SELF")/../lib/common.sh"

[[ -f "$SIGOS_COMPOSE" ]] || { echo "SIGOS no esta instalado."; exit "$EXIT_NOT_INSTALLED"; }
rc=0
state="$(systemctl is-active "$SIGOS_UNIT" 2>/dev/null || true)"; enabled="$(systemctl is-enabled "$SIGOS_UNIT" 2>/dev/null || true)"
printf 'Servicio sigos:   %s (arranque automatico: %s)\n' "${state:-desconocido}" "${enabled:-no}"
[[ "$state" == "active" ]] || rc=$EXIT_START
url="http://127.0.0.1"
if [[ -r "$SIGOS_ENV_FILE" ]]; then url="$(local_url)"; else
  url="$(sed -n 's/.*"apiBaseUrl": *"\([^"]*\)".*/\1/p' "$SIGOS_ETC/desktop.json" 2>/dev/null || true)"; url="${url:-http://127.0.0.1}"; fi
body="$(curl -fsS --max-time 5 "$url/api/v1/health" 2>/dev/null || true)"
if [[ "$body" == *'"status":"UP"'* || "$body" == *'"status": "UP"'* ]]; then
  printf 'API (%s):  UP  %s\n' "$url" "$body"
else
  printf 'API (%s):  NO RESPONDE %s\n' "$url" "${body}"; rc=$EXIT_HEALTH
fi
if [[ -r "$SIGOS_ENV_FILE" ]] && docker info >/dev/null 2>&1; then
  echo; echo "Contenedores:"
  dc ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Status}}' 2>/dev/null | sed 's/^/  /'
  for s in api worker proxy sqlserver; do
    h="$(dc ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk -v s="$s" '$1==s {print $2}')"
    [[ "$h" == "healthy" ]] || { [[ $rc -eq 0 ]] && rc=$EXIT_HEALTH; }
  done
  echo; echo "Imagen: $(env_get "$SIGOS_ENV_FILE" SIGOS_IMAGE):$(env_get "$SIGOS_ENV_FILE" SIGOS_VERSION)"
  echo "Volumenes de datos:"; docker volume ls --filter "label=com.docker.compose.project=$SIGOS_PROJECT" --format '  {{.Name}}'
else
  echo "(Ejecute 'sudo sigos status' para ver el detalle de contenedores)"
fi
echo; df -h "$SIGOS_VAR" /var/lib/docker 2>/dev/null | sed 's/^/  /' || true
exit $rc
