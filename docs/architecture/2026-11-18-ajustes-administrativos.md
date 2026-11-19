# Ajustes administrativos: evidencias, aprobación, cancelación de órdenes y materiales en MAYÚSCULAS

> 18/11/2026 · API Flask (`services/api`) · Escritorio Electron (`apps/desktop`)

## 1. Problemas y causas raíz

| # | Problema | Causa raíz verificada |
|---|---|---|
| 1 | El administrador veía en Evidencias el flujo del técnico ("Enviar a revisión", carga, firma del cliente, checklist). | La vista por orden no diferenciaba el rol; la bandeja tenía una segunda vista de expediente separada (duplicada). |
| 2 | La bandeja no permitía aprobar. | **Backend.** `approve_expediente` exige que *todas* las evidencias de la orden estén en revisión. (a) En el flujo de corrección, la foto que el técnico agrega queda en borrador porque `resubmit_expediente` solo reenviaba las marcadas para corrección, así que aprobar devolvía siempre `invalid_state`. (b) Una evidencia agregada después del primer envío nunca podía enviarse: `validate_submission` rechazaba el envío si ya había evidencias `SUBMITTED`, y la UI ocultaba el botón. (c) `resubmit_expediente` tenía un error de precedencia (`return out, None if out else (None, "invalid_state")`) que respondía `{"error": [null, "invalid_state"]}`. **Frontend.** Los errores se mostraban como códigos crudos (`invalid_state`) y los botones aparecían en cualquier estado. |
| 3 | El administrador no podía cancelar órdenes. | Bloqueo explícito en la API (`is_admin = False  # admin cannot change status` en `/status` y `/transitions`, y `"admin cannot cancel orders"` en PATCH), recogido como regla en `docs/plan-panel-admin.md`; se cambia por petición expresa. Además el botón "Cancelar orden" del detalle enviaba `notes` sin `reason`, así que fallaba también para el coordinador (422), y el menú del calendario usaba `window.prompt`, que no existe en Electron. |
| 4 | Materiales con escritura inconsistente (Tornillo / TORNILLO / tornillo). | Solo el catálogo, las categorías y las unidades tienen `NombreNormalizado`; el inventario (`Materiales`) y los textos libres se guardaban tal cual. La búsqueda del inventario comparaba `lower(Nombre)` (con acentos) contra el texto sin acentos, así que "tuberia" no encontraba "Tubería". |

## 2. Soluciones

### 2.1 Vista del administrador en Evidencias
- `renderEvidenceOrder` distingue roles. **Técnico**: registra y envía como antes; "Enviar N nuevas a revisión" aparece siempre que haya borradores. **Administrador / coordinador**: solo verificación. Ven registros (técnico, fecha y hora, firma), la fotografía ampliada y la firma histórica en el modal (con «Anterior / Siguiente»), el estado, quién aprobó y cuándo, el historial de revisión y la actividad. No hay acciones de envío ni herramientas de registro.
- Acciones según rol y estado. Administrador: *Aprobar* (solo si el expediente es aprobable), *Solicitar corrección* y *Rechazar*. Coordinador: *Iniciar revisión*. Si no se puede actuar, se explica el motivo (borradores sin enviar, corrección pendiente, evidencias propias).
- La bandeja abre esta misma vista ("Volver" regresa a la Bandeja); se eliminó la vista de expediente duplicada. La bandeja muestra el técnico responsable.

### 2.2 Aprobación
- `resubmit_expediente` también envía los borradores agregados durante la corrección, y se corrigió el error de precedencia.
- `validate_submission` permite enviar borradores nuevos a un expediente en revisión o aprobado (vuelve a revisión); un expediente rechazado queda cerrado.
- `approve_expediente` es idempotente: si ya está aprobado no crea más registros. Si hay motivos que lo impiden, devuelve un código estable: `pending_drafts`, `correction_pending`, `already_rejected`, `own_evidence` (nadie aprueba, rechaza ni pide corrección sobre evidencias registradas por sí mismo, aunque tenga varios roles), con mensaje en español y HTTP 403/404/409.
- Trazabilidad: `RevisionesEvidencia` (revisor, decisión, fecha y hora por evidencia) y `EventosEvidencia` (acción, actor, estado anterior y nuevo). `EvidenceReview.to_dict` incluye `reviewer_username`.
- Estados: se mantienen los existentes (`DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `CORRECTION_REQUIRED`, `RESUBMITTED`, `APPROVED`, `REJECTED`); no se crearon nuevos.

### 2.3 Cancelación lógica de órdenes
- `GET /work-orders/<id>/cancellation` (admin, coordinador): indica si se puede cancelar y qué se conserva (evidencias, aprobadas, consumos de material, solicitudes abiertas).
- `POST /work-orders/<id>/cancel` (admin, coordinador): motivo opcional. Bloquea la fila en SQL Server (`UPDLOCK`) y reutiliza `change_status`, así que queda en `HistorialEstadoOrden` (usuario, fecha y hora, estado anterior, nuevo, motivo), en la auditoría (`Auditoria`) y en `MotivoCancelacion`. No borra nada.
- Reglas (de `TRANSITIONS`, sin restricciones nuevas):
  - `pending`, `assigned` e `in_progress` → se pueden cancelar.
  - `completed` y `closed` → no; `cancelled` → "ya está cancelada", con explicación.
  - Evidencias aprobadas → no bloquean; se conservan.
  - Consumos de material → se conservan; el stock no se revierte, porque el material ya se usó físicamente.
  - Solicitudes de material abiertas → no se cancelan solas, porque tienen su propio flujo, permisos y stock; la confirmación lo advierte.
- El administrador ahora también puede cancelar por `/status` y `/transitions` (con el motivo obligatorio de esas rutas, sin cambios); el resto de transiciones siguen siendo del coordinador o del técnico asignado. El técnico no puede cancelar por ninguna ruta.
- UI: icono discreto en la columna de acciones de la tabla (solo en órdenes cancelables y para admin/coordinador), botón del detalle y menú del calendario. Los tres usan la misma confirmación: «¿Deseas cancelar la orden OS-0003?», con motivo opcional, Volver y Confirmar cancelación.

### 2.4 Materiales en MAYÚSCULAS
- **Backend, centralizado:** `normalize_upper()` en `app/common/normalize.py` (recorta, colapsa espacios y aplica `str.upper()`, que respeta Ñ y las vocales acentuadas). Se aplica con `@validates` en los modelos, así que cubre cualquier vía de escritura (rutas, servicios, semillas, sincronización):
  - `Material`: nombre, descripción, unidad.
  - `MaterialCatalog`: nombre, medida, etapa, aplica a.
  - `MaterialCategory` y `MaterialUnit`: nombre.
  - `StockMovement`: notas.
- **No se convierten** los códigos (`Codigo` de materiales, catálogo, categorías y unidades), que son identificadores técnicos.
- Duplicados: el catálogo ya los impedía con `NombreNormalizado` (sin mayúsculas ni acentos). Ahora también se rechaza (409 `DUPLICATE_NAME`) renombrar un material del inventario a un nombre que solo difiere en la escritura.
- Búsqueda: el inventario compara sin mayúsculas ni acentos en la aplicación ("tuberia" encuentra "TUBERÍA", igual en SQL Server y SQLite); el catálogo usa `NombreNormalizado`; los filtros de etapa y aplica a se normalizan.
- **Frontend:** los campos de texto del módulo (`data-upper`: nombre, medida, etapa, aplica a, búsqueda, notas de reposición y ajuste) convierten el valor real a mayúsculas al escribir y al pegar, conservando el cursor. No es `text-transform`.
- **Collation:** `SIGOS_DEV` usa `Modern_Spanish_CI_AS` (sin distinguir mayúsculas, sí acentos). No se modificó: la comparación sin acentos se hace en la aplicación.

#### Datos existentes y consolidación de duplicados
`python -m maintenance.normalizar_materiales` informa de los textos por normalizar y de los grupos duplicados por escritura, con sus referencias (movimientos, ítems de solicitud, stock de técnicos, ítem de catálogo). Con `--apply` normaliza los textos en una transacción; es idempotente y **no fusiona ni elimina** nada. En `SIGOS_DEV` las tablas de materiales están vacías: 0 cambios, 0 duplicados.

Si en producción aparecen duplicados, consolidar uno por uno:
1. Elegir el material superviviente (el vinculado al catálogo o el que tenga más movimientos).
2. En una transacción, reasignar `IdMaterial` en `MovimientosStock`, `ItemsSolicitudMaterial` y `StockTecnico` (sumando cantidades si el técnico tiene ambos), y sumar `StockActual`.
3. Desactivar (`EstaActivo = 0`) el duplicado; no borrarlo.
4. Registrar la consolidación en la auditoría.

Este paso no está automatizado porque requiere decidir qué registro sobrevive.

## 3. Archivos modificados
- **API:** `app/evidence/{service,routes,models}.py`, `app/workorders/{service,routes}.py`, `app/materials/{models,service,routes}.py`, `app/common/normalize.py`, `maintenance/normalizar_materiales.py` (nuevo).
- **Pruebas:** `tests/test_ajustes_administrativos.py` (nuevo, 15 casos), `tests/test_rnf05_access_rules.py` (rutas nuevas declaradas).
- **Escritorio:** `src/renderer/app.js`, `src/renderer/evidence_admin.js`, `src/renderer/design-system.css`.

## 4. Base de datos
Sin cambios de esquema ni migraciones: se usan las tablas y columnas existentes (`RevisionesEvidencia`, `EventosEvidencia`, `HistorialEstadoOrden`, `Auditoria`, `MotivoCancelacion`). La normalización de datos existentes la hace el script, con informe previo.

## 5. Pruebas
| Prueba | Resultado |
|---|---|
| `pytest` completo (API) | ver informe final |
| `tests/test_ajustes_administrativos.py` | 15/15: aprobación con revisor y fecha, idempotencia y persistencia; aprobación tras corrección con evidencia nueva; borradores sin enviar; permisos (técnico y coordinador no aprueban); nadie revisa lo propio; inexistentes y estados inválidos; cancelación lógica (orden, técnico, evidencias e historial intactos); motivo e impactos; reglas de estados; técnico sin cancelación por ninguna ruta; admin por transición; MAYÚSCULAS en alta, edición y notas; duplicados por escritura; búsqueda sin acentos; script de normalización (informe, aplicación, idempotencia, sin pérdida de relaciones). |
| Escritorio `npm test` | 49/49 |
| E2E Electron, ajustes administrativos | 28/28: el técnico registra, firma y envía; no puede aprobar ni cancelar (UI y petición directa). El admin entra desde la Bandeja, no ve acciones de envío, ve responsable, fecha, firma y fotografía ampliada, navega entre registros, aprueba (estado y "Aprobado por" inmediatos; persiste). Cancela desde la tabla con motivo (orden, técnico, motivo e historial conservados). Materiales en mayúsculas al escribir y pegar, código intacto, guardado normalizado, duplicado rechazado, búsqueda sin acentos. |
| E2E de regresión (sesiones, sistema de carga) | 19/19 y 35/35 |

## 6. Pendientes y limitaciones
1. Aplicar en producción: no hay cambios de esquema; ejecutar `python -m maintenance.normalizar_materiales` (informe) y, tras revisarlo, `--apply`.
2. La consolidación de duplicados del inventario, si aparecen, es manual (ver §2.4).
3. Las solicitudes de material (módulo Solicitudes) no se normalizan a mayúsculas: el alcance pedido es el módulo de materiales.
4. La app móvil no tiene acciones de revisión ni de cancelación (no las tenía); el backend aplica las mismas reglas a cualquier cliente.
