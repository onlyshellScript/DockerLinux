# Sesiones aisladas, firma del técnico y consulta de evidencias por orden

> 18/11/2026 · Rama `fix/panel-admin` · API Flask (`services/api`), escritorio Electron (`apps/desktop`), móvil Flutter (`apps/mobile`)

## 1. Problemas y causas encontradas

| # | Problema | Causa real (verificada en el código) |
|---|---|---|
| 1 | Tras cerrar sesión un administrador, el técnico que entraba en el mismo equipo veía la vista y datos de la sesión anterior. | El logout del escritorio (`app.js`) solo hacía `state.session = null` y borraba el archivo de sesión. El objeto `state` conservaba `view` (p. ej. `users`), filtros, cachés de vistas (`profiles`, `_calItems`, `_materialsOpts`…), temporizadores, la ruta en el hash y `localStorage['sigos.calendar']`. Al entrar el técnico, `bindLogin` mantenía `state.view` del admin y la guarda de rol solo se aplicaba al restaurar una ruta pendiente. |
| 2 | Una petición de la sesión administrativa se podía reutilizar después del logout. | No existía `POST /auth/logout`. Los JWT eran puramente sin estado: el access token seguía valiendo hasta 15 min y el refresh token 7 días aunque el usuario hubiera cerrado sesión. |
| 3 | Sin política de caché en la API. | Ninguna respuesta enviaba `Cache-Control`; solo el restablecimiento de contraseña y las exportaciones lo hacían. |
| 4 | Móvil: el logout dejaba en SQLite las órdenes y materiales en caché del usuario anterior. | `SessionStore.clear()` solo borraba `sync_meta`. |
| 5 | Sin firma del técnico en las evidencias. | `FirmasVisita` es la firma **del cliente**; no había firma de perfil del técnico ni vínculo con cada evidencia. |
| 6 | El módulo de evidencias cargaba todas las imágenes al entrar. | `renderEvidence` seleccionaba la primera orden y descargaba en paralelo cada archivo (base64 por IPC); el expediente de la bandeja hacía lo mismo. |
| 7 | Glifos y emojis decorativos. | `⚠` en agenda y calendario, `📅` corrupto (`ðŸ“…`), `✕` como icono de quitar, `✓` en exportaciones, `⚠`/`▼` dentro de etiquetas de stock y `←` como icono de volver. |

## 2. Soluciones implementadas

### 2.1 Aislamiento de sesiones (prioridad 1)

**Servidor**
- Nueva tabla `SesionesUsuario`: una fila por login. Access y refresh token llevan su id en el claim `sid`.
- `require_auth` / `require_role` (unificados en `_authenticate`) validan **en cada petición**: firma, vencimiento, tipo, sesión existente, del mismo usuario, no revocada y vigente, usuario activo, roles leídos de la base.
- `POST /api/v1/auth/logout` revoca la sesión (acepta el access token aunque haya vencido, y/o el refresh token). Idempotente.
- `/auth/refresh` solo renueva sesiones vigentes.
- Se revocan todas las sesiones del usuario al restablecer su contraseña o desactivarlo; al cambiar la propia contraseña se revocan las demás.
- Tokens emitidos antes de este cambio (sin `sid`) se rechazan: **los usuarios deberán iniciar sesión de nuevo una vez** tras el despliegue.
- Todas las respuestas `/api/*` llevan `Cache-Control: no-store, private, max-age=0`, `Pragma: no-cache`, `Expires: 0` y `Vary: Authorization`.

**Escritorio**
- `endSession()` centraliza logout y expiración: revoca en el servidor, borra las claves de `localStorage` con datos del usuario, y el proceso principal (`sigos:session:end`) borra el archivo de sesión, la caché HTTP, sessionStorage/IndexedDB/Cache Storage/service workers/cookies y el historial de navegación, y **recarga el renderer desde cero** sin la ruta anterior. No sobrevive ningún estado en memoria. Las preferencias de interfaz (tema, menú) se conservan a propósito.
- `viewAllowed()` aplica la guarda de rol en cada render y en cada cambio de hash; al iniciar sesión la vista se decide para el usuario nuevo.

**Móvil**
- El logout revoca la sesión en el servidor y borra `sync_meta`, `cached_work_orders` y `cached_materials`.

### 2.2 Firma del técnico

- `FirmasTecnico`: versiones **inmutables** de la firma de perfil (archivo PNG + sha256 + versión). Registrar una firma nueva crea otra versión y desactiva la anterior; nunca se sobrescribe ni se borra.
- `POST /api/v1/me/signature` (solo técnicos) recibe el PNG del recuadro de dibujo. El propietario es siempre el usuario del token: cualquier `user_id` enviado se ignora. Se valida PNG real, tamaño, dimensiones y que no esté en blanco.
- `GET /api/v1/me/signature` y `/image`: vista previa de la firma vigente.
- Al registrar una evidencia, el servidor copia en la evidencia la versión vigente del usuario autenticado: `IdFirmaTecnico`, `FirmaTecnicoSha256`, `IdTecnicoFirmante`, `FechaFirmaTecnico`. El cliente no puede enviar ni elegir la firma (campos de firma del formulario se ignoran; un archivo extra no se usa).
- Un técnico sin firma registrada recibe `409 technician_signature_required` (configurable con `EVIDENCE_REQUIRE_TECH_SIGNATURE`, por defecto `true`).
- **Inmutabilidad** en tres capas: (1) servicio: `DELETE /evidences/<id>` responde `409 signed_evidence_immutable` si la evidencia está firmada; (2) ORM: eventos `before_update`/`before_delete` impiden modificar los campos de firma de una evidencia y el contenido o el borrado de una versión de firma (`ImmutableRecordError`); (3) integridad: `GET /evidences/<id>/technician-signature` verifica que el archivo coincida con la huella copiada en la evidencia y responde `409 signature_integrity_error` si fue alterado.
- Firma de perfil ≠ firma histórica: cambiar la firma de perfil no afecta a evidencias anteriores (probado en API y E2E).

### 2.3 Consulta de evidencias por orden

- `GET /api/v1/evidences/orders`: órdenes con cantidad de evidencias, fecha del último registro, técnico, estado de la orden y estado de validación, calculados con una consulta agregada (sin archivos). Búsqueda por número (`12`, `OS-0012`) o texto, filtro por técnico, rango de fechas, solo con evidencias, orden por fecha (las órdenes sin evidencias siempre al final), paginación (máx. 100).
- Alcance decidido en el servidor: el técnico solo ve sus órdenes asignadas aunque envíe otro `technician_id`.
- Escritorio: listado → detalle de la orden con tabla de registros (tipo, momento, descripción, fecha, responsable, firma). La imagen y la firma **solo se descargan al abrir un registro** (modal). El expediente de la bandeja de administración usa la misma tabla y deja de descargar todas las imágenes.
- Se conservan las funciones existentes del módulo: carga de evidencias (ahora también PDF y observaciones de texto), firma y negativa del cliente, checklist, envío y reenvío a revisión.

### 2.4 Limpieza visual

- Eliminados los glifos decorativos; los que tenían función se reemplazaron por los iconos SVG de trazo ya existentes en la aplicación (`icon()`), con `aria-label` donde actúan como control.
- Las etiquetas de stock (`Crítico`, `Bajo`) quedan sin glifo: el color del badge ya comunica el estado.
- Las flechas `→` en transiciones de estado se mantienen: son tipografía que expresa "de A a B", no decoración.

## 3. Archivos modificados

**API:** `app/__init__.py`, `app/config.py`, `app/config_prod.py`, `app/identity/{models,tokens,decorators,service,routes}.py`, `app/evidence/{models,service,routes}.py`, `app/evidence/signatures.py` (nuevo), `migrations/versions/a7c8e9f0b1d2_sesiones_y_firmas_tecnico.py` (nuevo), `tests/test_sesiones_firmas.py` (nuevo), `tests/test_evidence.py`, `tests/test_users_admin.py`, `tests/test_rnf05_access_rules.py`, `tests/test_exports.py`.

**Escritorio:** `src/main/index.js`, `src/preload/index.js`, `src/renderer/app.js`, `src/renderer/evidence_admin.js`, `src/renderer/design-system.css`, `src/renderer/export-wizard.js`, `src/renderer/common/materials.js`.

**Móvil:** `lib/core/auth/session_store.dart`, `lib/features/auth/auth_gate.dart`, `lib/features/orders/order_detail_page.dart`.

**Otros:** `.env.example`, `contracts/openapi.yaml`, `docs/database/2026-11-18_sesiones_firmas.sql` (nuevo).

## 4. Base de datos

Solo se agregan tablas y columnas `NULL`; ningún dato existente se modifica ni se borra. Las evidencias anteriores quedan sin firma del técnico (se muestran como "Sin firma").

| Objeto | Cambio |
|---|---|
| `SesionesUsuario` | Nueva: `IdSesion` (PK, uuid), `IdUsuario` (FK Usuarios), `CreadaEn`, `ExpiraEn`, `RevocadaEn`, `MotivoRevocacion`, `IpOrigen`. |
| `FirmasTecnico` | Nueva: `IdFirmaTecnico` (PK), `IdUsuario` (FK Usuarios), `ClaveAlmacenamiento` (único), `TipoArchivo`, `TamanoArchivo`, `Sha256`, `Version`, `EsActiva`, `CreadaEn`, `ReemplazadaEn`. |
| `Evidencias` | Nuevas columnas nullable: `IdFirmaTecnico` (FK FirmasTecnico), `FirmaTecnicoSha256`, `IdTecnicoFirmante` (FK Usuarios), `FechaFirmaTecnico`. |

Aplicación:
- Alembic: `a7c8e9f0b1d2`, encadenada a la cabeza válida `615483f3bc21`; idempotente; su `downgrade` se niega a ejecutarse si ya hay evidencias firmadas.
- Mientras `flask db upgrade` siga fallando por la cadena duplicada (ver `docs/database/esquema-espanol-y-orm.md` §4): `docs/database/2026-11-18_sesiones_firmas.sql` con `sqlcmd`/SSMS y luego actualizar `alembic_version`.

## 5. Pruebas ejecutadas

| Suite | Resultado |
|---|---|
| API `pytest` completa | ver §5.1 |
| API `tests/test_sesiones_firmas.py` (nueva, 20 casos) | 20/20 |
| Escritorio `npm test` | 35/35 |
| Móvil `flutter test` / `flutter analyze` | 4/4 · sin errores nuevos |
| E2E Electron real + API (SQLite temporal) | 19/19 |

El E2E recorre: admin consulta Usuarios → logout → sin ruta, estado, archivo de sesión ni datos del admin en pantalla → Atrás no vuelve a la sesión → token y refresh del admin rechazados (401) → técnico entra al Dashboard, sin módulos administrativos; URL `#/usuarios` redirige; API responde 403 → listado de evidencias con solo sus 2 órdenes y sin imágenes → sin firma no puede adjuntar → dibuja y guarda su firma → adjunta una imagen → el registro muestra su firma → el modal carga imagen y firma bajo demanda → cambia su firma de perfil y la evidencia conserva la original byte a byte.

### 5.1 Cambios de expectativas en pruebas existentes

- `test_users_admin`: tras restablecer la contraseña, la sesión abierta ahora recibe **401** (revocada) en lugar de 403, y `Cache-Control` contiene `no-store` (la política global es más estricta).
- `test_exports`: misma razón para `Cache-Control`.
- `test_evidence`: el técnico registra su firma antes de adjuntar; se añadió la comprobación del 409 sin firma.

## 6. Pendientes reales

1. **Aplicar el esquema en SQL Server.** No se ejecutó contra `SIGOS_DEV` (las pruebas usan SQLite). Ejecutar el script SQL o la migración y repetir la verificación con `TEST_DB_URL`.
2. **Re-login tras el despliegue**: los tokens sin `sid` dejan de valer.
3. **Firma en la app móvil**: no tiene recuadro para registrar la firma. Un técnico sin firma registrada en el escritorio no podrá agregar observaciones desde el móvil (recibe un mensaje claro). Alternativa temporal: `EVIDENCE_REQUIRE_TECH_SIGNATURE=false`.
4. **Operaciones offline pendientes del móvil** (`pending_operations`) no registran a qué usuario pertenecen; si otra cuenta inicia sesión en el mismo teléfono antes de sincronizar, se enviarían con su token. No se borraron para no perder trabajo; requiere añadir el usuario propietario a la tabla (migración de la base local).
5. **Limitación conocida**: el servidor no puede distinguir un PNG dibujado en el recuadro de uno generado fuera de la app; la interfaz solo ofrece el recuadro (sin selector de archivo). La garantía fuerte es la identidad: la firma siempre queda ligada al usuario autenticado.
