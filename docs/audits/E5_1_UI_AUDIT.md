# E5.1 Auditoría de interfaz y preparación del diseño del módulo de evidencias

## 1. Resumen ejecutivo

La interfaz actual de SIGOS 2.0 es una aplicación Electron (`apps/desktop/src/renderer`) sobre una API Flask. No existen templates Flask ni CSS del backend. El módulo de materiales (`apps/desktop/src/renderer/app.js`, `common/materials.js`, `sigos.css`) es la referencia visual y técnica para evidencias. El backend de evidencias ya expone endpoints E1-E4; la UI aún no consume evidencias.

## 2. Estado inicial del repositorio

- Rama: `work/estado-actual`.
- Commit E4 presente: `0da05b6`.
- Cambios sin commit preexistentes preservados: migración `d4e5f6a7b8c9`, `pytest.ini`, `seed_calendar.py`.
- No se modificó código funcional en esta fase.

## 3. Arquitectura actual de la interfaz

- Entrada: `apps/desktop/src/renderer/index.html`.
- Lógica principal: `apps/desktop/src/renderer/app.js`.
- Estilos: `sigos.css`, `app-sigos.css`, `styles.css`.
- Módulo compartido: `apps/desktop/src/renderer/common/materials.js`.
- Navegación por vistas (`state.view`) con renderizado dinámico en `#app`.
- API consumida mediante `api(method, path)`; autenticación Bearer JWT.

## 4. Inventario de archivos del módulo de materiales

| Archivo | Función | Reutilizable |
|---|---|---|
| `apps/desktop/src/renderer/app.js` | Renderizado de inventario, filtros, tabla, paginación, modales | Sí, como patrón de listado |
| `apps/desktop/src/renderer/common/materials.js` | Formato COP, estado de stock, filtros | Parcial |
| `apps/desktop/src/renderer/sigos.css` | Tokens, botones, badges, cards, empty states | Sí |
| `apps/desktop/src/renderer/app-sigos.css` | Ajustes de layout | Sí |

Patrones visuales:
- Paleta: `#163028`, `#2E7A50`, `#F5F2EB`, `#DDD9D3`, estados `#E8A520`, `#D63B3B`, `#4AAF72`.
- Fuentes: Outfit (títulos), DM Sans (cuerpo), JetBrains Mono.
- Componentes: `.sigos-card`, `.sigos-btn-primary`, `.sigos-btn-secondary`, `.sigos-input`, badges `.badge-*`, `.empty-state`.

## 5. Patrones visuales reutilizables

| Patrón | Archivo | Requiere adaptación |
|---|---|---|
| Tarjeta KPI | `sigos.css` + `app.js` | Sí, para conteos por estado |
| Tabla con filtros | `app.js` renderMaterials | Sí, para bandeja/detalle |
| Badges de estado | `sigos.css` | Sí, nuevos estados de evidencia |
| Empty state | `sigos.css` | No |
| Modal de formulario | `app.js` | Sí, para firma/checklist |
| Paginación | `app.js` | No |

## 6. Inventario técnico del módulo de evidencias

Backend:
- Modelos: `services/api/app/evidence/models.py` (`VisitEvidence`, `VisitSignature`, `EvidenceReview`, `EvidenceEvent`, `VisitChecklistItem`).
- Servicios: `services/api/app/evidence/service.py`.
- Rutas: `services/api/app/evidence/routes.py`.
- Storage: `services/api/app/evidence/storage.py`.
- Permisos: `services/api/app/evidence/permissions.py`.

Estados: `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `CORRECTION_REQUIRED`, `RESUBMITTED`, `APPROVED`, `REJECTED`.

Endpoints reutilizables:
- `POST/GET /api/v1/work-orders/{wo_id}/evidences`
- `GET /api/v1/evidences/{id}`, `GET /api/v1/evidences`
- `GET /api/v1/evidences/{id}/download`
- `POST /api/v1/work-orders/{wo_id}/signatures`
- `GET /api/v1/work-orders/{wo_id}/signatures`
- `POST/GET /api/v1/work-orders/{wo_id}/checklist`
- `PATCH /api/v1/checklist/{id}`
- `POST /api/v1/work-orders/{wo_id}/evidences/submit`
- `POST /api/v1/work-orders/{wo_id}/evidences/resubmit`
- `GET /api/v1/work-orders/{wo_id}/evidence-status`
- `GET /api/v1/evidences/inbox`
- `GET /api/v1/work-orders/{wo_id}/evidence-detail`
- `POST .../start-review`, `request-correction`, `approve`, `reject`

## 7. Matriz de pantallas propuestas

Técnico:
1. Órdenes asignadas con acceso a expediente.
2. Detalle de expediente.
3. Carga de fotografías por categoría.
4. Firma o negativa justificada.
5. Checklist.
6. Observaciones.
7. Guardado/envío/reenvío.
8. Estado y correcciones.

Administrador:
1. Bandeja de expedientes.
2. Filtros/búsqueda/paginación.
3. Detalle completo.
4. Galería de fotos.
5. Firma/negativa.
6. Checklist/observaciones.
7. Historial.
8. Acciones de revisión/aprobación/rechazo.

## 8. Matriz pantalla → endpoint → permiso

| Pantalla | Endpoint | Permiso |
|---|---|---|
| Lista órdenes | `/api/v1/work-orders` | técnico/admin/dispatcher |
| Expediente técnico | `/api/v1/work-orders/{id}/evidence-status` | asignado/admin/dispatcher |
| Carga foto | `POST /evidences` | asignado/admin/dispatcher |
| Firma | `POST /signatures` | asignado/admin/dispatcher |
| Checklist | `POST/GET /checklist` | asignado/admin/dispatcher |
| Envío | `POST .../submit` | asignado/admin/dispatcher |
| Bandeja admin | `GET /evidences/inbox` | admin/dispatcher |
| Detalle admin | `GET .../evidence-detail` | admin/dispatcher/técnico autorizado |
| Descarga | `GET /evidences/{id}/download` | autorizado |
| Revisión | `POST .../start-review` | admin/dispatcher |
| Corrección | `POST .../request-correction` | admin |
| Aprobación | `POST .../approve` | admin |
| Rechazo | `POST .../reject` | admin |

## 9. Brechas entre frontend y backend

- No existe consumo de evidencias en `apps/desktop`.
- No hay componentes `EvidenceThumbnail`, `EvidenceUpload`, `EvidenceViewer` implementados.
- No hay navegación/menú para evidencias.
- Dispatcher no puede aprobar (RBAC real: solo admin).
- Reglas de obligatoriedad por tipo de servicio no están expuestas como configuración.

## 10. Riesgos técnicos

- Descargas privadas requieren manejo de blobs en Electron.
- Estados y permisos deben reflejarse en UI sin confiar en frontend.
- Concurrencia requiere manejo de 409.
- Almacenamiento local privado depende de `UPLOAD_DIR`.

## 11. Recomendación de implementación por fases

- E5.2: interfaz del técnico (lista, detalle, carga, firma, checklist, envío).
- E5.3: interfaz administrativa (bandeja, detalle, revisión, aprobación/rechazo).
- E5.4: pulido visual, accesibilidad, responsive y pruebas de interfaz.

## 12. Criterios de aceptación

- E5.2: técnico completa y envía expediente desde UI.
- E5.3: admin revisa, corrige, aprueba/rechaza.
- E5.4: consistencia visual y accesibilidad verificadas.

## Referencias

- `apps/desktop/src/renderer/app.js`
- `apps/desktop/src/renderer/common/materials.js`
- `apps/desktop/src/renderer/sigos.css`
- `services/api/app/evidence/routes.py`
- `services/api/app/evidence/service.py`
- `services/api/app/evidence/models.py`
- `docs/design/component-catalog.md`
