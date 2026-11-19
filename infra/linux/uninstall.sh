#!/usr/bin/env bash
# Desinstalacion de SIGOS.
#   sudo sigos uninstall               quita el programa, el servicio systemd y SIGOS Desktop.
#                                      CONSERVA la base de datos, los archivos subidos (volumenes Docker),
#                                      /etc/sigos (secretos) y /var/lib/sigos (respaldos). Reinstalar los reutiliza.
#   sudo sigos uninstall --purge-data  ademas BORRA DEFINITIVAMENTE datos, configuracion y respaldos.
#                                      Pide escribir BORRAR (o --yes-delete-data en modo no interactivo).
# No desinstala Docker.
set -Eeuo pipefail
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
LIB="$(dirname "$SELF")/../lib/common.sh"
# Copia de la libreria: este script borra /opt/sigos mientras se ejecuta.
TMP_LIB="$(mktemp)"; cp "$LIB" "$TMP_LIB"
# shellcheck source=lib/common.sh
source "$TMP_LIB"; rm -f "$TMP_LIB"

PURGE=0; CONFIRMED=0
for a in "$@"; do
  case "$a" in
    --purge-data) PURGE=1 ;;
    --yes-delete-data) CONFIRMED=1 ;;
    -h|--help) sed -n '2,9p' "$SELF" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "$EXIT_USAGE" "Opcion desconocida: $a" ;;
  esac
done
require_root

if [[ $PURGE -eq 1 && $CONFIRMED -eq 0 ]]; then
  [[ -t 0 ]] || die "$EXIT_CANCEL" "--purge-data sin terminal requiere --yes-delete-data."
  printf '%sATENCION:%s se borraran DEFINITIVAMENTE la base de datos, los archivos subidos, la configuracion\n' "$C_R" "$C_0"
  printf 'y los respaldos de %s. Esto no se puede deshacer.\n' "$SIGOS_VAR/backups"
  read -r -p "Escriba BORRAR para confirmar: " answer
  [[ "$answer" == "BORRAR" ]] || die "$EXIT_CANCEL" "Cancelado: no se borro nada."
fi

step "Deteniendo servicios"
systemctl disable --now "$SIGOS_UNIT" >/dev/null 2>&1 || true
if [[ -f "$SIGOS_COMPOSE" && -f "$SIGOS_ENV_FILE" ]] && command -v docker >/dev/null; then
  if [[ $PURGE -eq 1 ]]; then dc down --volumes --remove-orphans || true
  else dc down --remove-orphans || true; fi
fi
rm -f "$SIGOS_UNIT_FILE"; systemctl daemon-reload || true
ok "Servicio sigos eliminado"

step "Quitando el programa"
rm -f /usr/local/bin/sigos /usr/share/applications/sigos-desktop.desktop /usr/share/icons/hicolor/512x512/apps/sigos-desktop.png
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
for home in /home/* /root; do rm -f "$home/.config/autostart/sigos-desktop.desktop" 2>/dev/null || true; done
rm -rf "$SIGOS_HOME"
ok "Eliminado $SIGOS_HOME, comando sigos y acceso del menu"

if [[ $PURGE -eq 1 ]]; then
  rm -rf "$SIGOS_ETC" "$SIGOS_VAR"
  ok "Datos, configuracion y respaldos eliminados"
else
  info "Conservados: volumenes Docker (BD y archivos):"
  docker volume ls --filter "label=com.docker.compose.project=$SIGOS_PROJECT" --format '      {{.Name}}' 2>/dev/null || true
  info "Conservados: $SIGOS_ETC (secretos) y $SIGOS_VAR (respaldos). Reinstalar con install.sh los reutiliza."
  info "Para borrarlos tambien: vuelva a instalar y ejecute 'sudo sigos uninstall --purge-data'."
fi
ok "SIGOS desinstalado"
