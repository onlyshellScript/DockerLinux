#!/usr/bin/env bash
# Prueba de integracion REAL del instalador de Linux (requiere root, systemd y una maquina desechable).
# Recorre: instalacion -> admin inicial (login, cambio obligatorio) -> reinstalacion idempotente ->
# reinicio del servicio -> caida de un contenedor -> actualizacion -> reversion -> respaldo/restauracion ->
# desinstalacion conservando datos -> reinstalacion -> purga.
#
#   sudo infra/linux/tests/test-installer.sh --image sigos-api --version ci    (imagen ya cargada localmente)
#   sudo infra/linux/tests/test-installer.sh                                    (descarga de GHCR)
# Codigo de salida: numero de pasos fallidos (0 = todo bien).
set -Euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
IMAGE=""; VERSION=""; EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE="$2"; shift ;;
    --version) VERSION="$2"; shift ;;
    *) EXTRA+=("$1") ;;
  esac; shift
done
INSTALL=(bash "$ROOT/infra/linux/install.sh" --yes --skip-desktop)
[[ -n "$IMAGE" ]] && INSTALL+=(--image "$IMAGE" --no-pull)
[[ -n "$VERSION" ]] && INSTALL+=(--version "$VERSION")
INSTALL+=("${EXTRA[@]}")

pass=0; fail=0
check() { local name="$1"; shift; if "$@"; then echo "PASS  $name"; pass=$((pass+1)); else echo "FAIL  $name"; fail=$((fail+1)); fi; }
url=http://127.0.0.1
login() { curl -s -X POST "$url/api/v1/auth/login" -H 'Content-Type: application/json' -d "{\"username\":\"$1\",\"password\":\"$2\"}"; }
token() { login "$1" "$2" | sed -n 's/.*"access_token": *"\([^"]*\)".*/\1/p'; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
users() { curl -s "$url/api/v1/users" -H "Authorization: Bearer $1"; }
count_user() { users "$1" | grep -o "\"username\": *\"$2\"" | wc -l; }
NEWPWD='Definitiva-2026-Qa'

[[ ! -e /opt/sigos ]] || { echo "Ya hay una instalacion en /opt/sigos: use una maquina desechable."; exit 99; }

"${INSTALL[@]}" > /tmp/sigos-install-1.log 2>&1; rc=$?
check "1. instalacion limpia (codigo $rc)" test "$rc" -eq 0
[[ $rc -eq 0 ]] || { tail -60 /tmp/sigos-install-1.log; exit 1; }
check "2. sigos.env 0600 root" test "$(stat -c '%a %U' /etc/sigos/sigos.env)" = "600 root"
check "3. servicio habilitado y activo" bash -c '[[ $(systemctl is-enabled sigos) == enabled && $(systemctl is-active sigos) == active ]]'
check "4. API UP via Caddy" bash -c "curl -fsS $url/api/v1/health | grep -q '\"status\":\"UP\"'"
for s in api worker proxy sqlserver; do
  check "5. $s healthy" bash -c "docker compose -p sigos --env-file /etc/sigos/sigos.env -f /opt/sigos/compose/docker-compose.prod.yaml ps --format '{{.Service}} {{.Health}}' | grep -qx '$s healthy'"
done
P="$(sed -n 's/^contrasena_temporal=//p' /etc/sigos/initial-admin.txt 2>/dev/null)"
check "6. contrasena temporal entregada (sin terminal: archivo 0600)" test -n "$P"
check "7. contrasena ausente de registros" bash -c "! grep -rqF -- '$P' /var/log/sigos /opt/sigos && ! docker ps -aq | xargs -r docker logs 2>&1 | grep -qF -- '$P'"
must_change() { login admin "$P" | grep -qE '"must_change_password": *true'; }
check "8. login admin exige cambio" must_change
T="$(token admin "$P")"
check "9. bloqueado antes de cambiar" test "$(code "$url/api/v1/users" -H "Authorization: Bearer $T")" = 403
check "10. cambio de contrasena" test "$(code -X POST "$url/api/v1/auth/change-password" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d "{\"current_password\":\"$P\",\"new_password\":\"$NEWPWD\"}")" = 200
T="$(token admin "$NEWPWD")"
check "11. dato marcador creado" test "$(code -X POST "$url/api/v1/users" -H "Authorization: Bearer $T" -H 'Content-Type: application/json' -d '{"username":"marcador","email":"m@sigos.local","role_names":["dispatcher"]}')" = 201
sum="$(sha256sum /etc/sigos/sigos.env)"
"${INSTALL[@]}" > /tmp/sigos-install-2.log 2>&1
check "12. reinstalacion idempotente: secretos intactos" bash -c "echo '$sum' | sha256sum -c --quiet"
T="$(token admin "$NEWPWD")"
check "13. reinstalacion: un solo admin, contrasena conservada" bash -c "[[ -n '$T' && \$(curl -s $url/api/v1/users -H 'Authorization: Bearer $T' | grep -o '\"username\": *\"admin\"' | wc -l) -eq 1 ]]"
systemctl restart sigos
check "14. systemctl restart sigos y API UP" bash -c "for i in \$(seq 1 40); do curl -fsS $url/api/v1/health 2>/dev/null | grep -q UP && exit 0; sleep 5; done; exit 1"
T="$(token admin "$NEWPWD")"
check "15. datos persisten tras reinicio" test "$(count_user "$T" marcador)" -eq 1
cid="$(docker ps -q --filter label=com.docker.compose.service=api)"; kill -9 "$(docker inspect -f '{{.State.Pid}}' "$cid")"
check "16. recuperacion ante caida del contenedor api" bash -c "for i in \$(seq 1 40); do [[ \$(docker inspect -f '{{.State.Health.Status}}' $cid) == healthy ]] && curl -fsS $url/api/v1/health | grep -q UP && exit 0; sleep 5; done; exit 1"
cur="$(sed -n 's/^SIGOS_IMAGE=//p' /etc/sigos/sigos.env):$(sed -n 's/^SIGOS_VERSION=//p' /etc/sigos/sigos.env)"
repo="${cur%:*}"
printf 'FROM %s\nLABEL sigos.test=next\n' "$cur" | docker build -q -t "$repo:test-next" - >/dev/null
sigos update --version test-next --no-pull --yes > /tmp/sigos-update.log 2>&1
check "17. actualizacion a imagen nueva (con respaldo)" bash -c "grep -q 'SIGOS actualizado' /tmp/sigos-update.log && ls /var/lib/sigos/backups/*.bak >/dev/null"
T="$(token admin "$NEWPWD")"
check "18. datos conservados tras actualizar" test "$(count_user "$T" marcador)" -eq 1
printf 'FROM %s\nENTRYPOINT ["/bin/false"]\n' "$cur" | docker build -q -t "$repo:test-broken" - >/dev/null
SIGOS_WAIT_TIMEOUT=120 sigos update --version test-broken --no-pull --no-backup --yes > /tmp/sigos-rollback.log 2>&1; rc=$?
check "19. actualizacion fallida se revierte (codigo 9) y la API sigue UP" bash -c "[[ $rc -eq 9 ]] && curl -fsS $url/api/v1/health | grep -q UP"
bak="$(ls /var/lib/sigos/backups/*.bak | tail -1)"
sigos restore "$bak" --yes > /tmp/sigos-restore.log 2>&1
check "20. restauracion de respaldo" bash -c "for i in \$(seq 1 30); do curl -fsS $url/api/v1/health 2>/dev/null | grep -q UP && exit 0; sleep 5; done; exit 1"
sigos uninstall > /tmp/sigos-uninstall.log 2>&1
check "21. desinstalacion conserva datos" bash -c "[[ ! -e /opt/sigos && -f /etc/sigos/sigos.env ]] && docker volume inspect sigos_sqlserver-data >/dev/null"
"${INSTALL[@]}" > /tmp/sigos-install-3.log 2>&1
T="$(token admin "$NEWPWD")"
check "22. reinstalacion recupera los datos" test "$(count_user "$T" marcador)" -eq 1
sigos uninstall --purge-data </dev/null > /tmp/sigos-purge-1.log 2>&1
vol_exists() { docker volume inspect sigos_sqlserver-data >/dev/null 2>&1; }
check "23. purga sin confirmar no borra nada" vol_exists
sigos uninstall --purge-data --yes-delete-data > /tmp/sigos-purge-2.log 2>&1
check "24. purga confirmada borra datos" bash -c "! docker volume inspect sigos_sqlserver-data >/dev/null 2>&1 && [[ ! -e /etc/sigos ]]"

echo "Resultado: $pass PASS, $fail FAIL"
exit "$fail"
