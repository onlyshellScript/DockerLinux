# SIGOS en Linux: instalación y mantenimiento

Instalación de producción de SIGOS en un equipo Linux con un único comando. Docker ejecuta el backend
(SQL Server, API, worker de notificaciones y proxy Caddy) y SIGOS Desktop es la aplicación gráfica.

```
SIGOS Desktop (Electron) ──HTTP──> Caddy :80/:443 ──> API Flask (gunicorn) ──> SQL Server
                                                      worker de notificaciones ─┘
```

Solo Caddy publica puertos. SQL Server, la API y el worker viven en la red interna de Docker.

## Requisitos

| | Mínimo | Recomendado |
|---|---|---|
| Sistema | openSUSE Leap 15.6 / Tumbleweed, SLES 15, Fedora/RHEL 9, Ubuntu 22.04+/Debian 12 | openSUSE |
| Arquitectura | x86_64 (la imagen de SQL Server no existe para ARM) | |
| Memoria | 3 GB | 6 GB |
| Disco | 15 GB libres | 30 GB |
| Otros | systemd, acceso a internet (GHCR y repositorios de la distribución) | |

Docker Engine y Docker Compose v2 se instalan automáticamente si faltan (zypper, dnf o apt).

## Instalar

```bash
git clone https://github.com/onlyshellScript/DockerLinux.git
cd DockerLinux
sudo infra/linux/install.sh
```

Sin git, también sirve el paquete que publica el CI en la release `desktop-latest`:

```bash
curl -fLO https://github.com/onlyshellScript/DockerLinux/releases/download/desktop-latest/sigos-linux-installer.tar.gz
mkdir sigos-installer && tar xzf sigos-linux-installer.tar.gz -C sigos-installer
sudo sigos-installer/infra/linux/install.sh
```

El instalador:

1. Comprueba la distribución, la arquitectura, la memoria y systemd.
2. Instala y habilita Docker y Compose si faltan.
3. Copia el programa a `/opt/sigos` e instala el comando `sigos`.
4. Crea `/etc/sigos/sigos.env` (0600, solo root) con secretos aleatorios: contraseña `sa`, usuarios de base de
   datos y clave JWT.
5. Descarga la imagen de la API desde GHCR, levanta el stack (las migraciones se aplican solas) y espera a que
   todo esté sano.
6. Crea el usuario **`admin`** y muestra su contraseña temporal **una sola vez**. SIGOS obliga a cambiarla en el
   primer inicio de sesión.
7. Instala y habilita `sigos.service`, para que el backend arranque solo al encender el equipo.
8. Instala SIGOS Desktop en el menú de aplicaciones y, si se pide, lo abre al iniciar sesión.

Opciones frecuentes:

| Opción | Uso |
|---|---|
| `--yes` | Sin preguntas: valores por defecto y contraseña de admin generada |
| `--admin-password-stdin` | Lee la contraseña inicial del admin de la entrada estándar (`printf '%s\n' "$P" \| sudo ... --admin-password-stdin`) |
| `--http-port 8080` | Otro puerto HTTP, si el 80 está ocupado |
| `--domain sigos.empresa.com` | HTTPS automático con Let's Encrypt (requiere DNS y los puertos 80/443 abiertos) |
| `--version TAG` | Instala una versión concreta de la imagen (`latest`, `1.0.0-rc.1`, `sha-abc1234`) |
| `--autostart` / `--no-autostart` | Abre o no SIGOS Desktop al iniciar sesión |
| `--desktop-appimage RUTA` | Usa un AppImage local en lugar de descargarlo |
| `--skip-desktop` | Solo el servidor, por ejemplo en un servidor sin escritorio |

**Imagen privada en GHCR.** Si el paquete `sigos-api` no es público, exporta `GHCR_USER` y `GHCR_TOKEN` (un
token con `read:packages`) antes de ejecutar: `sudo -E infra/linux/install.sh`. El token se pasa a
`docker login` por la entrada estándar.

**Repetir la instalación es seguro.** No regenera secretos, no toca la base de datos ni los archivos y no crea un
segundo administrador. Solo añade a `sigos.env` las claves nuevas que falten.

Si no hay terminal, por ejemplo en una instalación automatizada, la contraseña temporal se guarda en
`/etc/sigos/initial-admin.txt` (0600). Bórralo después del primer acceso.

## Usar

Abre **SIGOS** desde el menú de aplicaciones. Si el backend todavía está arrancando, por ejemplo justo después
de encender el equipo, la aplicación muestra "Conectando con el servidor…" y entra sola cuando la API responde.
No hace falta abrir ninguna terminal.

Inicio automático de la ventana, por usuario y sin sudo:

```bash
sigos autostart on      # abrir SIGOS al iniciar sesión
sigos autostart off
```

**Desde otro equipo de la red.** El proxy escucha en todas las interfaces (puerto `HTTP_PORT`, 80 por defecto).
En el otro equipo, instala SIGOS Desktop y crea `~/.config/SIGOS Desktop/sigos-config.json` con
`{"apiBaseUrl": "http://IP-DEL-SERVIDOR"}`, o arráncalo con `SIGOS_API_BASE_URL=http://IP-DEL-SERVIDOR`. Abre
el puerto en el firewall del servidor:

- openSUSE: `sudo firewall-cmd --permanent --add-service=http && sudo firewall-cmd --reload`
- Ubuntu: `sudo ufw allow 80/tcp`

En una red que no sea de confianza, usa `--domain` para tener HTTPS.

## Administrar

| Comando | Qué hace |
|---|---|
| `sigos status` | Servicio, salud de la API y, con sudo, el estado de cada contenedor |
| `sudo sigos start` / `stop` / `restart` | Controla el stack a través de systemd (`stop` conserva los datos) |
| `sudo sigos logs [api\|worker\|migrate\|sqlserver\|proxy] [-f]` | Logs de los contenedores |
| `sudo sigos update` | Actualiza a la última imagen (ver abajo) |
| `sudo sigos backup` | Respaldo de la base de datos y de los archivos subidos en `/var/lib/sigos/backups` |
| `sudo sigos restore ARCHIVO.bak [--uploads ARCHIVO.tar.gz]` | Restaura un respaldo |
| `sudo sigos desktop-install RUTA.AppImage` | Instala o actualiza SIGOS Desktop |
| `sudo sigos uninstall [--purge-data]` | Desinstala (ver abajo) |

También se pueden usar directamente `systemctl status sigos` y `journalctl -u sigos`.

### Actualizar

`sudo sigos update` hace, en este orden:

1. Descarga la imagen nueva y la compara con la instalada. Si es la misma, termina.
2. Hace un respaldo de la base de datos y de los archivos.
3. Recrea los servicios. `migrate` aplica las migraciones pendientes, que solo añaden y nunca borran.
4. Comprueba los healthchecks y la API.
5. Si la versión nueva no queda sana, vuelve sola a la imagen anterior y lo informa.

Nunca borra volúmenes ni bases de datos. `--version TAG` instala una versión concreta y `--no-backup` omite el
respaldo.

### Desinstalar

`sudo sigos uninstall` quita el programa, el servicio y SIGOS Desktop, y **conserva** la base de datos, los
archivos subidos (volúmenes Docker), `/etc/sigos` y los respaldos. Reinstalar los reutiliza tal cual.

`--purge-data` además lo borra todo, de forma definitiva, y exige escribir `BORRAR`. Nunca se borran datos sin
pedirlo de forma explícita.

## Dónde está cada cosa

| Ruta | Contenido | Permisos |
|---|---|---|
| `/opt/sigos` | Programa: compose, Caddyfile, scripts y SIGOS Desktop (`desktop/`) | root, 755 |
| `/etc/sigos/sigos.env` | Configuración y secretos | root, **0600** |
| `/etc/sigos/desktop.json` | URL del servidor para SIGOS Desktop (sin secretos) | 0644 |
| `/var/lib/sigos/backups` | Respaldos | root, 0700 |
| `/var/log/sigos` | Registros de instalación y actualización (sin contraseñas) | root, 0750 |
| Volúmenes `sigos_sqlserver-data`, `sigos_api-uploads`, `sigos_caddy-*` | Base de datos, evidencias y certificados | Docker |
| `/etc/systemd/system/sigos.service` | Arranque automático | 0644 |

Logs de contenedores: driver `json-file` con rotación (10 MB × 5 por contenedor).

## Arranque automático: cómo funciona

- **`sigos.service`** (systemd, `Type=oneshot`) espera a Docker y ejecuta `docker compose up -d --wait`. Así se
  respeta el orden: SQL Server sano → migraciones → API → worker y proxy. Si algo falla, reintenta cada 30 s.
- **`restart: unless-stopped`** en cada contenedor recupera un contenedor caído mientras el equipo está encendido.
- No se duplican: `up -d` es idempotente y no recrea lo que ya está en marcha.
- **SIGOS Desktop no arranca ningún backend.** Solo espera al configurado en `/etc/sigos/desktop.json`.

## Seguridad

- No hay credenciales por defecto. Cada instalación genera secretos propios con el generador del kernel
  (`/dev/urandom`) y su propia contraseña de admin, que caduca en el primer acceso.
- Los secretos nunca están en la imagen, en el repositorio ni en los logs. Viajan como variables de entorno,
  nunca como argumentos.
- La API corre como `sigos_app`, con solo lectura y escritura de datos. Las migraciones usan `sigos_migrator`.
  Solo el servicio `migrate` recibe la contraseña `sa`.
- **SELinux no se desactiva.** Los volúmenes nombrados reciben su etiqueta automáticamente y el `Caddyfile` se
  monta con `:z`. Con AppArmor (openSUSE Leap) no hace falta nada más.
- SIGOS Desktop mantiene el sandbox de Chromium: `chrome-sandbox` es root 4755.

## Solución de problemas

| Síntoma | Qué mirar |
|---|---|
| La app se queda en "Conectando…" | `sigos status` y luego `sudo sigos logs api` o `journalctl -u sigos` |
| `pull access denied` al instalar | La imagen es privada: exporta `GHCR_USER` y `GHCR_TOKEN` o hazla pública |
| El puerto 80 está ocupado | `sudo infra/linux/install.sh --http-port 8080` (también actualiza SIGOS Desktop) |
| SQL Server no arranca | Memoria: necesita 2 GB libres (`free -h`) |
| Has olvidado la contraseña del admin | Otro administrador la restablece desde Usuarios. Si no hay ninguno, `seed.py` no la cambia: hay que restablecerla en la base de datos |

## Pruebas

`infra/linux/tests/test-installer.sh` ejecuta el ciclo completo en una máquina Linux real con systemd: lo usa el
job `linux-installer` del CI. Las pruebas del inicializador del admin están en
`services/api/tests/test_seed_admin.py`.
