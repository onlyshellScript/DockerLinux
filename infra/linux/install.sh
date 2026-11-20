#!/usr/bin/env bash
# Instalador de SIGOS para Linux (openSUSE Leap/Tumbleweed, SLES, Fedora/RHEL, Ubuntu/Debian).
#
#   sudo ./install.sh                  instalacion interactiva (pregunta lo necesario)
#   sudo ./install.sh --yes            sin preguntas: valores por defecto y contrasena de admin generada
#
# Que hace (idempotente: repetirlo no borra datos, no regenera secretos ni duplica el admin):
#   1. Comprueba sistema, arquitectura (x86_64), memoria y disco.
#   2. Instala Docker Engine + Compose v2 si faltan (zypper/dnf/apt) y los habilita con systemd.
#   3. Copia el programa a /opt/sigos y crea /etc/sigos (config, 0700) y /var/lib/sigos (respaldos/estado).
#   4. Crea /etc/sigos/sigos.env con secretos aleatorios (0600 root). Si ya existe solo anade claves que falten.
#   5. Descarga las imagenes de GHCR, levanta el stack (migraciones incluidas) y espera a que este sano.
#   6. Crea el usuario administrador inicial (solo si la base no tiene usuarios) y muestra su contrasena UNA vez.
#   7. Instala y habilita sigos.service (arranque automatico) y el comando "sigos".
#   8. Instala SIGOS Desktop (menu de aplicaciones) y, si se pide, su inicio automatico al iniciar sesion.
#
# Opciones:
#   --yes                    no preguntar (usa valores por defecto)
#   --image REPO             imagen de la API (por defecto ghcr.io/onlyshellscript/dockerlinux/sigos-api)
#   --version TAG            etiqueta de la imagen (por defecto latest)
#   --http-port N            puerto HTTP del proxy (por defecto 80)
#   --domain DOMINIO         HTTPS automatico con Let's Encrypt para DOMINIO (requiere DNS y puertos 80/443)
#   --admin-password-stdin   lee la contrasena del admin inicial de la entrada estandar (una linea)
#   --no-docker-install      no instalar Docker (falla si no esta)
#   --no-pull                no descargar imagenes (deben existir localmente; p. ej. pruebas/CI)
#   --skip-desktop           no instalar la aplicacion de escritorio
#   --desktop-appimage RUTA  usar este AppImage en lugar de descargarlo de las releases
#   --desktop-user USUARIO   usuario de escritorio para el inicio automatico (por defecto $SUDO_USER)
#   --autostart / --no-autostart   abrir SIGOS al iniciar sesion (por defecto: si, para el usuario que ejecuta sudo)
#
# Acceso a un registro privado: exporte GHCR_USER y GHCR_TOKEN (token con read:packages) antes de ejecutar;
# el token se pasa a "docker login" por la entrada estandar, nunca por argumentos.
set -Eeuo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SRC_DIR/../.." && pwd)"
# shellcheck source=lib/common.sh
source "$SRC_DIR/lib/common.sh"

ASSUME_YES=0; IMAGE=""; VERSION=""; HTTP_PORT_OPT=""; DOMAIN=""; ADMIN_STDIN=0; NO_DOCKER_INSTALL=0
NO_PULL=0; SKIP_DESKTOP=0; DESKTOP_APPIMAGE=""; DESKTOP_USER="${SUDO_USER:-}"; AUTOSTART=""

usage() { sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-$EXIT_USAGE}"; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) ASSUME_YES=1 ;;
    --image) IMAGE="${2:?}"; shift ;;
    --version) VERSION="${2:?}"; shift ;;
    --http-port) HTTP_PORT_OPT="${2:?}"; shift ;;
    --domain) DOMAIN="${2:?}"; shift ;;
    --admin-password-stdin) ADMIN_STDIN=1 ;;
    --no-docker-install) NO_DOCKER_INSTALL=1 ;;
    --no-pull) NO_PULL=1 ;;
    --skip-desktop) SKIP_DESKTOP=1 ;;
    --desktop-appimage) DESKTOP_APPIMAGE="${2:?}"; shift ;;
    --desktop-user) DESKTOP_USER="${2:?}"; shift ;;
    --autostart) AUTOSTART=1 ;;
    --no-autostart) AUTOSTART=0 ;;
    -h|--help) usage 0 ;;
    *) printf 'Opcion desconocida: %s\n' "$1" >&2; usage ;;
  esac
  shift
done

require_root "$@"
[[ -z "$HTTP_PORT_OPT" || "$HTTP_PORT_OPT" =~ ^[0-9]{1,5}$ ]] || die "$EXIT_USAGE" "--http-port invalido: $HTTP_PORT_OPT"

INTERACTIVE=0
if [[ $ASSUME_YES -eq 0 && -t 0 && -r /dev/tty ]]; then INTERACTIVE=1; fi
ask_yes_no() { # pregunta [default s|n]
  local q="$1" def="${2:-n}" a
  [[ $INTERACTIVE -eq 1 ]] || { [[ "$def" == "s" ]]; return; }
  read -r -p "    $q [$( [[ $def == s ]] && echo 'S/n' || echo 's/N')] " a </dev/tty || a=""
  a="${a:-$def}"; [[ "${a,,}" == s* || "${a,,}" == y* ]]
}

# Registro de la instalacion (sin secretos: la contrasena del admin se escribe directamente en la terminal).
mkdir -p "$SIGOS_LOG_DIR"; chmod 750 "$SIGOS_LOG_DIR"
LOG_FILE="$SIGOS_LOG_DIR/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1
# shellcheck disable=SC2154
trap 'rc=$?; [[ $rc -ne 0 ]] && printf "\nInstalacion interrumpida (codigo %s). Registro: %s\n" "$rc" "$LOG_FILE" >&2' EXIT

printf '%sSIGOS · instalador para Linux%s  (registro: %s)\n' "$C_B" "$C_0" "$LOG_FILE"

# ---------------------------------------------------------------------------------------------------------
step "1/8 Sistema"
OS_ID="unknown"; OS_LIKE=""; OS_NAME="desconocido"
if [[ -r /etc/os-release ]]; then
  OS_ID="$(. /etc/os-release; printf '%s' "${ID:-unknown}")"
  OS_LIKE="$(. /etc/os-release; printf '%s' "${ID_LIKE:-}")"
  OS_NAME="$(. /etc/os-release; printf '%s' "${PRETTY_NAME:-$ID}")"
fi
info "Distribucion: $OS_NAME"
family="other"
case " $OS_ID $OS_LIKE " in
  *" opensuse"*|*" suse "*|*" sles "*|*" sled "*) family="suse" ;;
  *" fedora "*|*" rhel "*|*" centos "*|*" rocky "*|*" almalinux "*) family="rhel" ;;
  *" debian "*|*" ubuntu "*) family="debian" ;;
esac
info "Familia: $family"
ARCH="$(uname -m)"
[[ "$ARCH" == "x86_64" ]] || die "$EXIT_PREREQ" "Arquitectura $ARCH no soportada: la imagen de SQL Server solo existe para x86_64 (amd64)."
ok "Arquitectura x86_64"
mem_mb=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 ))
if (( mem_mb < 2500 )); then die "$EXIT_PREREQ" "Memoria insuficiente (${mem_mb} MB). SQL Server necesita al menos 2 GB libres; se recomiendan 6 GB."; fi
(( mem_mb < 5500 )) && warn "Memoria ${mem_mb} MB: funciona, pero se recomiendan 6 GB o mas." || ok "Memoria ${mem_mb} MB"
command -v systemctl >/dev/null && [[ -d /run/systemd/system ]] || die "$EXIT_PREREQ" "Se requiere systemd (no detectado)."
selinux="no"
if command -v getenforce >/dev/null 2>&1; then selinux="$(getenforce 2>/dev/null || echo no)"; fi
info "SELinux: $selinux (no se desactiva; los montajes usan etiquetas :z)"

# ---------------------------------------------------------------------------------------------------------
step "2/8 Docker Engine y Compose"
pkg_install() {
  case "$family" in
    suse)   zypper --non-interactive --quiet refresh && zypper --non-interactive install --no-recommends "$@" ;;
    rhel)   dnf -y install "$@" ;;
    debian) DEBIAN_FRONTEND=noninteractive apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@" ;;
    *)      return 1 ;;
  esac
}
if ! command -v curl >/dev/null; then pkg_install curl || die "$EXIT_PREREQ" "Falta curl y no se pudo instalar."; fi
if ! command -v docker >/dev/null 2>&1; then
  [[ $NO_DOCKER_INSTALL -eq 0 ]] || die "$EXIT_DOCKER" "Docker no esta instalado (--no-docker-install)."
  info "Instalando Docker..."
  case "$family" in
    suse)   pkg_install docker docker-compose ;;
    rhel)   pkg_install moby-engine docker-compose || pkg_install docker docker-compose-plugin ;;
    debian) pkg_install docker.io docker-compose-v2 || pkg_install docker.io docker-compose-plugin ;;
    *)      die "$EXIT_DOCKER" "Distribucion no reconocida: instale Docker Engine y Compose v2 manualmente y repita." ;;
  esac || die "$EXIT_DOCKER" "No se pudo instalar Docker con el gestor de paquetes ($family)."
  ok "Docker instalado"
else
  ok "Docker ya instalado: $(docker --version 2>/dev/null)"
fi
if ! compose_ok; then
  if [[ $NO_DOCKER_INSTALL -eq 0 ]]; then
    info "Instalando/actualizando Docker Compose v2..."
    case "$family" in
      suse) pkg_install docker-compose || true ;;
      rhel) pkg_install docker-compose-plugin || pkg_install docker-compose || true ;;
      debian) pkg_install docker-compose-v2 || pkg_install docker-compose-plugin || true ;;
    esac
  fi
  compose_ok || die "$EXIT_DOCKER" "Se requiere Docker Compose v2 >= 2.20 ('docker compose version'). Detectado: $(docker compose version --short 2>/dev/null || echo ninguno)."
fi
ok "Docker Compose $(docker compose version --short)"
systemctl enable --now docker >/dev/null 2>&1 || systemctl enable --now docker.service
for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
docker info >/dev/null 2>&1 || die "$EXIT_DOCKER" "El servicio Docker no responde ('systemctl status docker')."
ok "Servicio docker habilitado y activo"

# ---------------------------------------------------------------------------------------------------------
step "3/8 Archivos del programa"
install -d -m 755 "$SIGOS_HOME" "$SIGOS_HOME/compose" "$SIGOS_HOME/bin" "$SIGOS_HOME/lib" "$SIGOS_HOME/backup"
install -d -m 700 "$SIGOS_ETC"
install -d -m 700 "$SIGOS_VAR" "$SIGOS_VAR/backups" "$SIGOS_VAR/state"
install -m 644 "$REPO_ROOT/infra/docker/docker-compose.prod.yaml" "$SIGOS_COMPOSE"
install -m 644 "$REPO_ROOT/infra/docker/Caddyfile" "$SIGOS_HOME/compose/Caddyfile"
install -m 644 "$REPO_ROOT/infra/docker/.env.prod.example" "$SIGOS_HOME/compose/env.prod.example"
for f in backup.sh restore.sh common.sh; do install -m 755 "$REPO_ROOT/infra/docker/backup/$f" "$SIGOS_HOME/backup/$f"; done
install -m 644 "$SRC_DIR/lib/common.sh" "$SIGOS_HOME/lib/common.sh"
for f in sigos install.sh update.sh status.sh uninstall.sh; do install -m 755 "$SRC_DIR/$f" "$SIGOS_HOME/bin/$f"; done
install -m 644 "$SRC_DIR/README.md" "$SIGOS_HOME/README.md"
# El instalador copiado (para reinstalar/reparar) necesita el arbol de fuentes: se guarda una copia minima.
rm -rf "$SIGOS_HOME/src.new"; install -d "$SIGOS_HOME/src.new/infra"
cp -a "$REPO_ROOT/infra/linux" "$REPO_ROOT/infra/docker" "$SIGOS_HOME/src.new/infra/"
rm -rf "$SIGOS_HOME/src" && mv "$SIGOS_HOME/src.new" "$SIGOS_HOME/src"
ln -sf "$SIGOS_HOME/bin/sigos" /usr/local/bin/sigos
ok "Programa en $SIGOS_HOME; comando: sigos"
if [[ "$selinux" == "Enforcing" ]] && command -v restorecon >/dev/null; then restorecon -R "$SIGOS_HOME" "$SIGOS_ETC" >/dev/null 2>&1 || true; fi

# ---------------------------------------------------------------------------------------------------------
step "4/8 Configuracion y secretos"
umask 077
new_env=0
if [[ ! -f "$SIGOS_ENV_FILE" ]]; then
  # SQL Server fija la contrasena de sa al crear su volumen: con un sigos.env nuevo (secretos nuevos) y un
  # volumen de una instalacion anterior, la BD rechazaria las credenciales. No se borra nada: se pide decidir.
  if docker volume inspect "${SIGOS_PROJECT}_sqlserver-data" >/dev/null 2>&1; then
    die "$EXIT_PREREQ" "Existe el volumen ${SIGOS_PROJECT}_sqlserver-data de una instalacion anterior, pero falta $SIGOS_ENV_FILE con sus contrasenas.
    - Si tiene datos que quiere conservar: restaure el $SIGOS_ENV_FILE original (o una copia) y repita.
    - Si es una instalacion de prueba sin datos: borre los volumenes viejos y repita:
        sudo docker compose -p $SIGOS_PROJECT -f $REPO_ROOT/infra/docker/docker-compose.prod.yaml down -v
      (si se queja de variables obligatorias: sudo docker volume rm \$(sudo docker volume ls -q --filter label=com.docker.compose.project=$SIGOS_PROJECT))"
  fi
  new_env=1
  {
    printf '# SIGOS: configuracion de produccion. Generado por install.sh el %s.\n' "$(date -Is)"
    printf '# Contiene secretos: solo root puede leerlo (0600). No lo copie a repositorios ni lo envie por chat.\n'
  } > "$SIGOS_ENV_FILE"
fi
chown root:root "$SIGOS_ENV_FILE"; chmod 600 "$SIGOS_ENV_FILE"
added=()
add() { if env_add_missing "$SIGOS_ENV_FILE" "$1" "$2"; then added+=("$1"); fi; }
add MSSQL_SA_PASSWORD "$(new_secret 32)"
add MSSQL_PID Express
add DB_NAME sigos
add DB_MIGRATOR_USER sigos_migrator
add DB_MIGRATOR_PASSWORD "$(new_secret 32)"
add DB_APP_USER sigos_app
add DB_APP_PASSWORD "$(new_secret 32)"
add JWT_SECRET_KEY "$(new_secret 64)"
add SIGOS_IMAGE "${IMAGE:-$SIGOS_DEFAULT_IMAGE}"
add SIGOS_VERSION "${VERSION:-latest}"
add HTTP_PORT "${HTTP_PORT_OPT:-80}"
add HTTPS_PORT 443
add SIGOS_DOMAIN "${DOMAIN:-:80}"
add TZ "$(timedatectl show -p Timezone --value 2>/dev/null || echo America/Bogota)"
add GUNICORN_WORKERS 4
add NOTIFICATION_WORKER_INTERVAL 30
# Opciones explicitas en una reinstalacion: solo claves de gestion (nunca secretos).
[[ -n "$IMAGE" ]] && env_set "$SIGOS_ENV_FILE" SIGOS_IMAGE "$IMAGE"
[[ -n "$VERSION" ]] && env_set "$SIGOS_ENV_FILE" SIGOS_VERSION "$VERSION"
[[ -n "$HTTP_PORT_OPT" ]] && env_set "$SIGOS_ENV_FILE" HTTP_PORT "$HTTP_PORT_OPT"
[[ -n "$DOMAIN" ]] && env_set "$SIGOS_ENV_FILE" SIGOS_DOMAIN "$DOMAIN"
umask 022
if [[ $new_env -eq 1 ]]; then ok "Creado $SIGOS_ENV_FILE (0600) con secretos nuevos"
elif [[ ${#added[@]} -gt 0 ]]; then ok "Conservado $SIGOS_ENV_FILE; claves anadidas: ${added[*]}"
else ok "Conservado $SIGOS_ENV_FILE sin cambios de secretos"; fi
API_URL="$(local_url)"
printf '{\n  "apiBaseUrl": "%s"\n}\n' "$API_URL" > "$SIGOS_ETC/desktop.json"
chmod 644 "$SIGOS_ETC/desktop.json"; chmod 711 "$SIGOS_ETC"
installed_at="$(conf_get INSTALLED_AT)"
printf 'INSTALLED_AT=%s\nUPDATED_AT=%s\nSOURCE=%s\n' "${installed_at:-$(date -Is)}" "$(date -Is)" "$REPO_ROOT" > "$SIGOS_CONF"
chmod 644 "$SIGOS_CONF"

# ---------------------------------------------------------------------------------------------------------
step "5/8 Imagenes y servicios"
img="$(env_get "$SIGOS_ENV_FILE" SIGOS_IMAGE):$(env_get "$SIGOS_ENV_FILE" SIGOS_VERSION)"
info "Imagen de la API: $img"
if [[ -n "${GHCR_TOKEN:-}" ]]; then
  printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-token}" --password-stdin >/dev/null \
    || die "$EXIT_DOCKER" "docker login ghcr.io fallo (revise GHCR_USER/GHCR_TOKEN)."
  ok "Sesion iniciada en ghcr.io"
fi
if [[ $NO_PULL -eq 0 ]]; then
  if ! dc pull --quiet; then
    die "$EXIT_DOCKER" "No se pudieron descargar las imagenes. Si el paquete de GHCR es privado, exporte GHCR_USER y GHCR_TOKEN (read:packages) y repita, o hagalo publico en GitHub (Packages > sigos-api > Package settings)."
  fi
  ok "Imagenes descargadas"
else
  docker image inspect "$img" >/dev/null 2>&1 || die "$EXIT_DOCKER" "--no-pull: la imagen $img no existe localmente."
  ok "Usando imagenes locales (--no-pull)"
fi
info "Levantando el stack (la primera vez SQL Server y las migraciones tardan 1-3 minutos)..."
if ! dc up -d --wait --wait-timeout 900 --remove-orphans; then
  diagnose
  die "$EXIT_START" "El stack no quedo sano. Revise el diagnostico de arriba y el registro $LOG_FILE."
fi
ok "Contenedores sanos: $(dc ps --format '{{.Service}}' --status running | tr '\n' ' ')"
wait_health 180 || { diagnose; die "$EXIT_HEALTH" "La API no responde UP en $API_URL/api/v1/health."; }
ok "API UP en $API_URL"

# ---------------------------------------------------------------------------------------------------------
step "6/8 Administrador inicial"
ADMIN_MARK="$SIGOS_VAR/state/admin-initialized"
admin_pwd=""
if [[ -f "$ADMIN_MARK" ]]; then
  info "Ya inicializado el $(cat "$ADMIN_MARK"); no se modifica ningun usuario."
fi
if [[ $ADMIN_STDIN -eq 1 && ! -f "$ADMIN_MARK" ]]; then
  IFS= read -r admin_pwd || true
  check_password_policy "$admin_pwd" || die "$EXIT_ADMIN" "La contrasena del admin no cumple la politica (minimo 10, mayuscula, minuscula y numero)."
elif [[ $INTERACTIVE -eq 1 && ! -f "$ADMIN_MARK" ]] && ask_yes_no "¿Desea elegir usted la contrasena inicial del usuario admin? (si no, se genera una)" n; then
  while :; do
    read -r -s -p "    Contrasena (min. 10, mayuscula, minuscula y numero): " admin_pwd </dev/tty; printf '\n' >/dev/tty
    read -r -s -p "    Repitala: " p2 </dev/tty; printf '\n' >/dev/tty
    [[ "$admin_pwd" == "$p2" ]] || { warn "No coinciden."; continue; }
    check_password_policy "$admin_pwd" && break || warn "No cumple la politica."
  done
  unset p2
fi
generated=0
if [[ -z "$admin_pwd" ]]; then admin_pwd="$(new_admin_password)"; generated=1; fi
# La contrasena viaja por el entorno del proceso docker (no por argumentos: "-e ADMIN_PASSWORD" sin valor).
seed_out="$(ADMIN_PASSWORD="$admin_pwd" dc run --rm --no-deps -T -e SIGOS_ENV=production -e ADMIN_PASSWORD api python seed.py --catalogs 2>&1)" \
  || { printf '%s\n' "$seed_out" | grep -v -F "$admin_pwd" >&2; die "$EXIT_ADMIN" "Fallo la inicializacion de datos (seed.py)."; }
printf '%s\n' "$seed_out" | grep -v -F "$admin_pwd" | sed 's/^/    /'
if grep -q 'Usuario admin creado' <<<"$seed_out"; then
  date -Is > "$ADMIN_MARK"; chmod 600 "$ADMIN_MARK"
  if { : > /dev/tty; } 2>/dev/null; then
    {
      printf '\n    ┌──────────────────────────────────────────────────────────────┐\n'
      printf '    │  Usuario: admin                                              │\n'
      if [[ $generated -eq 1 ]]; then printf '    │  Contrasena temporal: %-39s│\n' "$admin_pwd"
      else printf '    │  Contrasena: la que acaba de escribir                        │\n'; fi
      printf '    │  Se mostrara SOLO ESTA VEZ. SIGOS pedira cambiarla al entrar.  │\n'
      printf '    └──────────────────────────────────────────────────────────────┘\n\n'
    } > /dev/tty
  elif [[ $generated -eq 1 ]]; then
    (umask 077; printf 'usuario=admin\ncontrasena_temporal=%s\n' "$admin_pwd" > "$SIGOS_ETC/initial-admin.txt")
    warn "Sin terminal: contrasena temporal guardada en $SIGOS_ETC/initial-admin.txt (0600 root). Borrela tras el primer acceso."
  fi
  ok "Administrador 'admin' creado (debe cambiar la contrasena en el primer acceso)"
else
  [[ -f "$ADMIN_MARK" ]] || date -Is > "$ADMIN_MARK"
  ok "La base ya tenia usuarios: no se creo ni modifico ninguno"
fi
admin_pwd=""; unset admin_pwd seed_out

# ---------------------------------------------------------------------------------------------------------
step "7/8 Arranque automatico (systemd)"
DOCKER_BIN="$(command -v docker)"
sed -e "s#{{DOCKER}}#$DOCKER_BIN#g" -e "s#{{COMPOSE}}#$SIGOS_COMPOSE#g" -e "s#{{ENV}}#$SIGOS_ENV_FILE#g" \
  "$SRC_DIR/systemd/sigos.service" > "$SIGOS_UNIT_FILE.new"
chmod 644 "$SIGOS_UNIT_FILE.new"; mv -f "$SIGOS_UNIT_FILE.new" "$SIGOS_UNIT_FILE"
systemctl daemon-reload
systemctl enable "$SIGOS_UNIT" >/dev/null 2>&1
systemctl start "$SIGOS_UNIT" || { diagnose; die "$EXIT_START" "systemctl start sigos fallo ('journalctl -u sigos')."; }
ok "sigos.service habilitado ($(systemctl is-enabled "$SIGOS_UNIT")) y activo ($(systemctl is-active "$SIGOS_UNIT"))"

# ---------------------------------------------------------------------------------------------------------
step "8/8 SIGOS Desktop"
if [[ $SKIP_DESKTOP -eq 1 ]]; then
  info "Omitido (--skip-desktop). El servidor queda disponible en $API_URL para clientes de la red."
else
  app_dir="$SIGOS_HOME/desktop"
  tmpd="$(mktemp -d)"
  appimage="$DESKTOP_APPIMAGE"
  if [[ -z "$appimage" ]]; then
    url="$SIGOS_RELEASES_URL/download/desktop-latest/SIGOS-Desktop-x86_64.AppImage"
    info "Descargando $url"
    if curl -fsSL --retry 3 -o "$tmpd/SIGOS.AppImage" "$url"; then appimage="$tmpd/SIGOS.AppImage"
    elif [[ -f "$REPO_ROOT/apps/desktop/package.json" ]]; then
      info "No hay version publicada; se construye SIGOS Desktop desde el codigo con Docker (Node 22, 3-8 minutos)..."
      # Sin montajes (los archivos entran y salen por stdin/stdout): funciona con SELinux en modo enforcing.
      if tar cf - -C "$REPO_ROOT/apps/desktop" --exclude=node_modules --exclude=dist . \
         | docker run --rm -i node:22 bash -c 'mkdir /w && cd /w && tar xf - && npm ci --no-audit --no-fund >&2 \
             && npx electron-builder --linux AppImage --publish never >&2 && cat dist/SIGOS-Desktop-x86_64.AppImage' \
             > "$tmpd/SIGOS.AppImage" && [[ -s "$tmpd/SIGOS.AppImage" ]]; then
        appimage="$tmpd/SIGOS.AppImage"; ok "SIGOS Desktop construido"
      else
        warn "No se pudo construir SIGOS Desktop. Instale despues con: sudo sigos desktop-install RUTA.AppImage"
      fi
    else
      warn "No se pudo descargar SIGOS Desktop. Instale despues con: sudo sigos desktop-install RUTA.AppImage"
    fi
  fi
  if [[ -n "$appimage" ]]; then
    [[ -s "$appimage" ]] || die "$EXIT_PREREQ" "No existe o esta vacio: $appimage"
    [[ "$appimage" == "$tmpd/SIGOS.AppImage" ]] || cp "$appimage" "$tmpd/SIGOS.AppImage"
    chmod 755 "$tmpd/SIGOS.AppImage"
    # Se extrae (no requiere FUSE) y se instala de forma atomica.
    (cd "$tmpd" && ./SIGOS.AppImage --appimage-extract >/dev/null) || die "$EXIT_PREREQ" "No se pudo extraer el AppImage."
    rm -rf "$app_dir.new"; mv "$tmpd/squashfs-root" "$app_dir.new"
    # Legible y ejecutable por todos los usuarios (la extraccion hereda el umask de root), escribible solo por root.
    chown -R root:root "$app_dir.new"; chmod -R u=rwX,go=rX "$app_dir.new"
    # Sandbox de Chromium: chrome-sandbox debe ser root:root 4755 (se mantiene el sandbox activo).
    if [[ -f "$app_dir.new/chrome-sandbox" ]]; then chown root:root "$app_dir.new/chrome-sandbox"; chmod 4755 "$app_dir.new/chrome-sandbox"; fi
    rm -rf "$app_dir.old"; [[ -d "$app_dir" ]] && mv "$app_dir" "$app_dir.old"; mv "$app_dir.new" "$app_dir"; rm -rf "$app_dir.old"
    # Librerias del sistema que necesita Electron (GTK, NSS, audio...). En escritorios completos ya estan;
    # en instalaciones minimas se instalan las que falten.
    missing_libs() { ldd "$app_dir/sigos-desktop" 2>/dev/null | awk '/not found/ {print $1}' | sort -u; }
    libs="$(missing_libs)"
    if [[ -n "$libs" ]]; then
      info "Instalando librerias que faltan para SIGOS Desktop: $(echo "$libs" | tr '\n' ' ')"
      # shellcheck disable=SC2046,SC2086  # separacion intencionada: una capacidad por libreria
      case "$family" in
        suse) zypper --non-interactive install --no-recommends $(printf '%s()(64bit) ' $libs) >/dev/null 2>&1 \
                || for l in $libs; do zypper --non-interactive install --no-recommends "$l()(64bit)" >/dev/null 2>&1 || true; done ;;
        rhel) dnf -y install $(printf '%s()(64bit) ' $libs) >/dev/null 2>&1 || true ;;
        debian)
          DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 || true
          for p in libgtk-3-0 libgtk-3-0t64 libnss3 libgbm1 libxss1 libcups2 libcups2t64 libatspi2.0-0 libatspi2.0-0t64 \
                   libasound2 libasound2t64 libxcomposite1 libxdamage1 libxrandr2 libdrm2 libatk-bridge2.0-0 libatk-bridge2.0-0t64; do
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$p" >/dev/null 2>&1 || true
          done ;;
      esac
      libs="$(missing_libs)"
      if [[ -n "$libs" ]]; then warn "Siguen faltando librerias para SIGOS Desktop: $(echo "$libs" | tr '\n' ' ')"
      else ok "Librerias de SIGOS Desktop instaladas"; fi
    fi
    install -d /usr/share/icons/hicolor/512x512/apps /usr/share/applications
    icon_src=""
    for c in "$app_dir/sigos-desktop.png" "$app_dir/usr/share/icons/hicolor/512x512/apps/sigos-desktop.png" "$SRC_DIR/desktop/sigos-desktop.png"; do
      [[ -f "$c" ]] && { icon_src="$c"; break; }
    done
    [[ -n "$icon_src" ]] && install -m 644 "$icon_src" /usr/share/icons/hicolor/512x512/apps/sigos-desktop.png
    # Se ejecuta el binario: AppRun solo funciona dentro del AppImage montado (necesita APPDIR).
    [[ -x "$app_dir/sigos-desktop" ]] || die "$EXIT_PREREQ" "El AppImage no contiene sigos-desktop: no es un build valido de SIGOS Desktop."
    sed "s#{{EXEC}}#$app_dir/sigos-desktop#" "$SRC_DIR/desktop/sigos-desktop.desktop" > /usr/share/applications/sigos-desktop.desktop
    chmod 644 /usr/share/applications/sigos-desktop.desktop
    # Con SELinux, lo extraido en /tmp conserva etiquetas tmp_t: se restauran las de su ubicacion definitiva.
    if command -v restorecon >/dev/null; then restorecon -R "$app_dir" /usr/share/applications/sigos-desktop.desktop /usr/share/icons/hicolor/512x512/apps >/dev/null 2>&1 || true; fi
    command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
    ok "SIGOS Desktop instalado: menu de aplicaciones > SIGOS"
    if [[ -z "$AUTOSTART" ]]; then
      ask_yes_no "¿Abrir SIGOS automaticamente al iniciar sesion${DESKTOP_USER:+ ($DESKTOP_USER)}?" s && AUTOSTART=1 || AUTOSTART=0
    fi
    if [[ "$AUTOSTART" == "1" ]]; then
      if [[ -n "$DESKTOP_USER" ]] && id "$DESKTOP_USER" >/dev/null 2>&1; then
        if su - "$DESKTOP_USER" -s /bin/sh -c "/usr/local/bin/sigos autostart on" >/dev/null; then ok "Inicio automatico activado para $DESKTOP_USER"
        else warn "No se pudo activar el inicio automatico para $DESKTOP_USER. Hagalo con su usuario: sigos autostart on"; fi
      else
        warn "Sin usuario de escritorio (--desktop-user). Cada usuario puede activarlo con: sigos autostart on"
      fi
    else
      info "Inicio automatico desactivado. Para activarlo (como su usuario, sin sudo): sigos autostart on"
    fi
  fi
  rm -rf "$tmpd"
fi

trap - EXIT
printf '\n%sSIGOS instalado.%s\n' "$C_G" "$C_0"
info "Abrir: menu de aplicaciones > SIGOS   (servidor: $API_URL)"
info "Administrar: sigos status | start | stop | restart | logs | update | backup | restore"
info "Configuracion: $SIGOS_ENV_FILE (0600)   Respaldos: $SIGOS_VAR/backups   Registro: $LOG_FILE"
