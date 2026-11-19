# Mapeo de tablas y columnas: proyecto (inglés) -> SIGOS_DEV (español)

Convencion de SIGOS (fuente de verdad):
- Tablas: PascalCase, español, plural o compuesto (Auditoria, Evidencias, HistorialEstadoOrden, Materiales, MovimientosStock, Notificaciones, OperacionesSincronizacion, OrdenesTrabajo, PerfilesTecnico, Roles, Usuarios, UsuariosXRoles).
- Columnas: PascalCase, español: Id<Entidad>, Nombre, Descripcion, CreadoEn, ActualizadoEn, EstaActivo, etc.
- PK: Id<Entidad> (o compuesta IdUsuario, IdRol).
- FK: Id<Entidad> -> tabla referenciada.
- Tablas intermedias: X (UsuariosXRoles).
- Tipos: INTEGER, VARCHAR(n), NVARCHAR, FLOAT, BIT, DATETIMEOFFSET.
- Nullability segun SIGOS.

Leyenda: [EXISTENTE] = tabla ya en SIGOS (se mantiene estructura + columnas nuevas aprobadas). [NUEVA] = tabla nueva a crear.

---

## A. Tablas existentes en SIGOS (12) -> modelos del proyecto se ajustan

### 1. Auditoria (EXISTENTE)  <=>  audit_log (proyecto)  [AMBIGUO: proyecto tambien tiene audit_events]
Columnas SIGOS (se mantienen):
- IdAuditoria (PK, int, NOT NULL)  <->  id
- NombreTabla (varchar(100), NOT NULL)  <->  section? (ambiguo: SIGOS usa NombreTabla, proyecto usa section/field)
- Accion (varchar(20), NOT NULL)  <->  result? action?
- IdRegistro (int, NOT NULL)  <->  (no hay equivalente directo)
- DatosAntiguos (nvarchar, NULL)  <->  old_value
- DatosNuevos (nvarchar, NULL)  <->  new_value
- IdUsuario (int, NULL)  <->  user_id
- CreadoEn (datetimeoffset, NULL)  <->  created_at

Columnas del proyecto NO presentes en SIGOS (propuesta nueva en español):
- section -> Seccion (VARCHAR(40), NOT NULL) [o reusar NombreTabla? AMBIGUO]
- field -> Campo (VARCHAR(80), NULL)
- result -> Resultado (VARCHAR(20), NOT NULL)
- request_id -> IdSolicitud (VARCHAR(40), NULL)
- username -> NombreUsuario (VARCHAR(80), NULL)
- actor_id / target_user_id (de audit_events) -> IdActor, IdUsuarioObjetivo (INTEGER, NULL)

PREGUNTA: SIGOS tiene una sola tabla Auditoria; el proyecto tiene audit_log y audit_events. Se mapean ambas a Auditoria (agregando columnas) o se crea AuditoriaEventos (nueva)? Decidir antes de continuar.

### 2. Evidencias (EXISTENTE)  <=>  visit_evidences (proyecto)
Columnas SIGOS (se mantienen):
- IdEvidencia (PK, int, NOT NULL)  <->  id
- IdOrden (int, NOT NULL)  <->  work_order_id
- IdSubidoPor (int, NOT NULL)  <->  uploaded_by_id
- TipoEvidencia (varchar(20), NOT NULL)  <->  category
- NombreArchivo (varchar(250), NULL)  <->  original_name / file_name
- NombreAlmacenado (varchar(250), NULL)  <->  storage_key / stored_name
- TipoArchivo (varchar(50), NULL)  <->  mime_type / file_type
- TamanoArchivo (int, NULL)  <->  size_bytes / file_size
- Descripcion (nvarchar, NULL)  <->  description
- CreadoEn (datetimeoffset, NULL)  <->  created_at

Columnas del proyecto NO presentes en SIGOS (propuesta nueva en español):
- sha256 -> HashSha256 (VARCHAR(64), NULL)
- declared_capture_at -> FechaCapturaDeclarada (DATETIME, NULL)
- received_at -> FechaRecepcion (DATETIME, NULL)
- status -> Estado (VARCHAR(30), NOT NULL)
- previous_evidence_id -> IdEvidenciaAnterior (INTEGER, NULL, FK->Evidencias)
- version_number -> NumeroVersion (INTEGER, NOT NULL)
- duplicate_of_id -> IdDuplicadoDe (INTEGER, NULL, FK->Evidencias)
- client_operation_id -> IdOperacionCliente (VARCHAR(36), NULL)

### 3. HistorialEstadoOrden (EXISTENTE)  <=>  work_order_status_history (proyecto)
Columnas SIGOS (se mantienen):
- IdHistorial (PK, int, NOT NULL)  <->  id
- IdOrden (int, NOT NULL)  <->  work_order_id
- EstadoAnterior (varchar(20), NOT NULL)  <->  from_status
- EstadoNuevo (varchar(20), NOT NULL)  <->  to_status
- IdCambiadoPor (int, NOT NULL)  <->  changed_by_id
- Notas (nvarchar, NULL)  <->  notes
- CreadoEn (datetimeoffset, NULL)  <->  created_at
Columnas del proyecto no presentes: (ninguna adicional)

### 4. Materiales (EXISTENTE)  <=>  materials (proyecto)
Columnas SIGOS (se mantienen):
- IdMaterial (PK, int, NOT NULL)  <->  id
- Nombre (varchar(120), NOT NULL)  <->  name
- Descripcion (varchar(250), NULL)  <->  description
- Unidad (varchar(20), NOT NULL)  <->  unit
- StockActual (float, NOT NULL)  <->  current_stock
- StockMinimo (float, NOT NULL)  <->  min_stock
- PrecioUnitario (float, NOT NULL)  <->  unit_price (NOTA: SIGOS usa FLOAT, proyecto usa NUMERIC(18,2); mantener FLOAT segun SIGOS? o cambiar a NUMERIC? AMBIGUO)
- EstaActivo (bit, NOT NULL)  <->  is_active
- CreadoEn (datetimeoffset, NULL)  <->  created_at
- ActualizadoEn (datetimeoffset, NULL)  <->  updated_at

Columnas del proyecto NO presentes en SIGOS (propuesta nueva en español):
- code -> Codigo (VARCHAR(40), NULL)
- catalog_item_id -> IdItemCatalogo (INTEGER, NULL, FK->CatalogoMateriales)

PREGUNTA: PrecioUnitario en SIGOS es FLOAT, en el proyecto NUMERIC(18,2). Cual mantener? (recomiendo NUMERIC para dinero, pero SIGOS es fuente de verdad -> FLOAT). Decidir.

### 5. MovimientosStock (EXISTENTE)  <=>  stock_movements (proyecto)
Columnas SIGOS (se mantienen):
- IdMovimiento (PK, int, NOT NULL)  <->  id
- IdMaterial (int, NOT NULL)  <->  material_id
- Cantidad (float, NOT NULL)  <->  quantity (y quantity_requested/approved/delivered? AMBIGUO)
- TipoMovimiento (varchar(15), NOT NULL)  <->  movement_type
- IdOrden (int, NULL)  <->  work_order_id
- IdUsuario (int, NOT NULL)  <->  user_id
- Notas (varchar(250), NULL)  <->  notes
- CreadoEn (datetimeoffset, NULL)  <->  created_at

Columnas del proyecto NO presentes en SIGOS (propuesta nueva en español):
- quantity_requested -> CantidadSolicitada (FLOAT, NOT NULL)
- quantity_approved -> CantidadAprobada (FLOAT, NOT NULL)
- quantity_delivered -> CantidadEntregada (FLOAT, NOT NULL)

PREGUNTA: SIGOS tiene una sola Cantidad; el proyecto tiene 4 cantidades. Mantener Cantidad + agregar las 3 nuevas? o reinterpretar? Decidir.

### 6. Notificaciones (EXISTENTE)  <=>  notifications (proyecto)
Columnas SIGOS (se mantienen):
- IdNotificacion (PK, int, NOT NULL)  <->  id
- IdUsuario (int, NOT NULL)  <->  user_id
- Canal (varchar(15), NOT NULL)  <->  channel
- Destinatario (varchar(250), NOT NULL)  <->  recipient
- Asunto (varchar(200), NULL)  <->  subject
- Mensaje (nvarchar, NOT NULL)  <->  message
- Estado (varchar(15), NOT NULL)  <->  status
- Intentos (int, NOT NULL)  <->  retry_count
- MensajeError (varchar(500), NULL)  <->  error_message
- CreadoEn (datetimeoffset, NULL)  <->  created_at
- EnviadoEn (datetimeoffset, NULL)  <->  sent_at
Columnas del proyecto no presentes: (ninguna adicional)

### 7. OperacionesSincronizacion (EXISTENTE)  <=>  sync_operations (proyecto)
Columnas SIGOS (se mantienen):
- IdOperacion (PK, int, NOT NULL)  <->  id
- IdOperacionCliente (varchar(36), NOT NULL)  <->  client_operation_id
- TipoOperacion (varchar(50), NOT NULL)  <->  operation_type
- Carga (nvarchar, NOT NULL)  <->  payload
- IdUsuario (int, NOT NULL)  <->  user_id
- Estado (varchar(15), NOT NULL)  <->  status
- Resultado (nvarchar, NULL)  <->  result
- CreadoEn (datetimeoffset, NULL)  <->  created_at
- SincronizadoEn (datetimeoffset, NULL)  <->  synced_at
Columnas del proyecto no presentes: (ninguna adicional)

### 8. OrdenesTrabajo (EXISTENTE)  <=>  work_orders (proyecto)
Columnas SIGOS (se mantienen):
- IdOrden (PK, int, NOT NULL)  <->  id
- Titulo (varchar(200), NOT NULL)  <->  title
- Descripcion (nvarchar, NULL)  <->  description
- Estado (varchar(20), NOT NULL)  <->  status
- Prioridad (varchar(10), NOT NULL)  <->  priority
- NombreCliente (varchar(120), NULL)  <->  customer_name
- TelefonoCliente (varchar(30), NULL)  <->  customer_phone
- Direccion (varchar(250), NULL)  <->  address
- IdAsignadoA (int, NULL)  <->  assigned_to_id
- IdCreadoPor (int, NOT NULL)  <->  created_by_id
- CreadoEn (datetimeoffset, NULL)  <->  created_at
- ActualizadoEn (datetimeoffset, NULL)  <->  updated_at

Columnas del proyecto NO presentes en SIGOS (propuesta nueva en español):
- zone -> Zona (VARCHAR(60), NULL)
- legacy_zone -> ZonaLegado (VARCHAR(60), NULL)
- city_id -> IdCiudad (INTEGER, NULL, FK->Ciudades)
- zone_id -> IdZona (INTEGER, NULL, FK->Zonas)
- installation_type -> TipoInstalacion (VARCHAR(80), NULL)
- installation_type_code -> CodigoTipoInstalacion (VARCHAR(60), NULL, FK->TiposInstalacion)
- scheduled_at -> FechaProgramada (DATETIME, NULL)
- scheduled_end -> FechaFinProgramada (DATETIME, NULL)
- schedule_notes -> NotasProgramacion (TEXT, NULL)
- version -> Version (INTEGER, NOT NULL, default 1)
- cancel_reason -> MotivoCancelacion (TEXT, NULL)
- completed_at -> FechaCompletado (DATETIME, NULL)

### 9. PerfilesTecnico (EXISTENTE)  <=>  technician_profiles (proyecto)
Columnas SIGOS (se mantienen):
- IdPerfil (PK, int, NOT NULL)  <->  id
- IdUsuario (int, NOT NULL)  <->  user_id
- Telefono (varchar(30), NULL)  <->  phone
- Especialidad (varchar(80), NULL)  <->  specialty
- EstaDisponible (bit, NOT NULL)  <->  is_available
- CreadoEn (datetimeoffset, NULL)  <->  created_at
- ActualizadoEn (datetimeoffset, NULL)  <->  updated_at

Columnas del proyecto NO presentes en SIGOS (propuesta nueva en español):
- first_name -> Nombre (VARCHAR(80), NULL) [o PrimerNombre?]
- last_name -> Apellido (VARCHAR(80), NULL)
- email -> Correo (VARCHAR(120), NULL)
- specialty_code -> CodigoEspecialidad (VARCHAR(60), NULL, FK->Especialidades)
- legacy_zone -> ZonaLegado (VARCHAR(250), NULL)
- document_type -> TipoDocumento (VARCHAR(20), NULL)
- document_number -> NumeroDocumento (VARCHAR(40), NULL)
- document -> Documento (VARCHAR(40), NULL)
- is_active -> EstaActivo (BIT, NOT NULL)
- open_orders -> OrdenesAbiertas (INTEGER, NOT NULL)
- created_by_id -> IdCreadoPor (INTEGER, NULL, FK->Usuarios)

### 10. Roles (EXISTENTE)  <=>  roles (proyecto)
Columnas SIGOS (se mantienen):
- IdRol (PK, int, NOT NULL)  <->  id
- Nombre (varchar(50), NOT NULL)  <->  name
- Descripcion (varchar(200), NULL)  <->  description
Columnas del proyecto no presentes: (ninguna)

### 11. Usuarios (EXISTENTE)  <=>  users (proyecto)
Columnas SIGOS (se mantienen):
- IdUsuario (PK, int, NOT NULL)  <->  id
- Nombre_usuario (varchar(80), NOT NULL)  <->  username
- Correo (varchar(120), NOT NULL)  <->  email
- HashContrasena (varchar(256), NOT NULL)  <->  password_hash
- EstaActivo (bit, NOT NULL)  <->  is_active
- CreadoEn (datetimeoffset, NULL)  <->  created_at
- ActualizadoEn (datetimeoffset, NULL)  <->  updated_at

Columnas del proyecto NO presentes en SIGOS (propuesta nueva en español):
- must_change_password -> DebeCambiarContrasena (BIT, NOT NULL)
- password_changed_at -> FechaCambioContrasena (DATETIME, NULL)
- failed_attempts -> IntentosFallidos (INTEGER, NOT NULL)
- locked_until -> BloqueadoHasta (DATETIME, NULL)
- last_login -> UltimoAcceso (DATETIME, NULL)

### 12. UsuariosXRoles (EXISTENTE)  <=>  user_roles (proyecto)
Columnas SIGOS (se mantienen):
- IdUsuario (int, NOT NULL)  <->  user_id
- IdRol (int, NOT NULL)  <->  role_id
PK compuesta (IdUsuario, IdRol). FKs a Usuarios y Roles.
Columnas del proyecto no presentes: (ninguna)

---

## B. Tablas nuevas (~29) — propuesta de nombre y columnas en español

Convencion: PascalCase, español, PK Id<Entidad>, FK Id<Entidad>, CreadoEn/ActualizadoEn (DATETIMEOFFSET segun SIGOS).

### 13. AuditoriaEventos (nueva) [si se decide separar de Auditoria]
Origen proyecto: audit_events
Columnas:
- IdAuditoriaEvento (PK, int, NOT NULL)
- IdActor (int, NULL, FK->Usuarios)
- IdUsuarioObjetivo (int, NULL, FK->Usuarios)
- Accion (varchar(40), NOT NULL)
- Cambios (nvarchar, NULL)
- CreadoEn (datetimeoffset, NULL)

### 14. Ciudades (nueva)
Origen: cities
- IdCiudad (PK, int, NOT NULL)
- IdPais (int, NOT NULL, FK->Paises)
- NombreDepartamento (varchar(120), NULL)
- CodigoDane (varchar(5), NOT NULL)
- Nombre (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NOT NULL)
- EstaActivo (bit, NOT NULL)

### 15. Paises (nueva)
Origen: countries
- IdPais (PK, int, NOT NULL)
- CodigoIso2 (varchar(2), NOT NULL)
- Nombre (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NOT NULL)
- EstaActivo (bit, NOT NULL)

### 16. Departamentos (nueva)
Origen: departments
- Codigo (varchar(2), PK, NOT NULL)
- Nombre (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NULL)

### 17. EventosEvidencia (nueva)
Origen: evidence_events
- IdEventoEvidencia (PK, int, NOT NULL)
- IdOrden (int, NULL, FK->OrdenesTrabajo)
- IdEvidencia (int, NULL, FK->Evidencias)
- IdActor (int, NULL, FK->Usuarios)
- Accion (varchar(40), NOT NULL)
- EstadoAnterior (varchar(30), NULL)
- EstadoNuevo (varchar(30), NULL)
- Detalles (nvarchar, NULL)
- CreadoEn (datetimeoffset, NULL)

### 18. RevisionesEvidencia (nueva)
Origen: evidence_reviews
- IdRevisionEvidencia (PK, int, NOT NULL)
- IdEvidencia (int, NOT NULL, FK->Evidencias)
- IdRevisor (int, NOT NULL, FK->Usuarios)
- Decision (varchar(30), NOT NULL)
- Notas (nvarchar, NULL)
- CreadoEn (datetimeoffset, NULL)

### 19. TiposInstalacion (nueva)
Origen: installation_types
- Codigo (varchar(60), PK, NOT NULL)
- Etiqueta (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NOT NULL)
- EstaActivo (bit, NOT NULL)

### 20. CatalogoMateriales (nueva)
Origen: material_catalog
- IdItemCatalogo (PK, int, NOT NULL)
- IdCategoria (int, NOT NULL, FK->CategoriasMaterial)
- Codigo (varchar(40), NOT NULL)
- Nombre (varchar(200), NOT NULL)
- NombreNormalizado (varchar(200), NOT NULL)
- IdUnidad (int, NOT NULL, FK->UnidadesMaterial)
- Medida (varchar(60), NULL)
- Etapa (varchar(60), NULL)
- AplicaA (varchar(40), NULL)
- EstaActivo (bit, NOT NULL)

### 21. CategoriasMaterial (nueva)
Origen: material_categories
- IdCategoria (PK, int, NOT NULL)
- Codigo (varchar(40), NOT NULL)
- Nombre (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NOT NULL)
- EstaActivo (bit, NOT NULL)

### 22. EntregasSolicitudMaterial (nueva)
Origen: material_request_deliveries
- IdEntrega (PK, int, NOT NULL)
- IdSolicitud (int, NOT NULL, FK->SolicitudesMaterial)
- IdActor (int, NOT NULL, FK->Usuarios)
- IdOperacion (varchar(36), NULL)
- CreadoEn (datetimeoffset, NULL)

### 23. ItemsEntregaSolicitud (nueva)
Origen: material_request_delivery_items
- IdItemEntrega (PK, int, NOT NULL)
- IdEntrega (int, NOT NULL, FK->EntregasSolicitudMaterial)
- IdItemSolicitud (int, NOT NULL, FK->ItemsSolicitudMaterial)
- CantidadEntregada (float, NOT NULL)
- IdMovimiento (int, NULL, FK->MovimientosStock)

### 24. EventosSolicitudMaterial (nueva)
Origen: material_request_events
- IdEvento (PK, int, NOT NULL)
- IdSolicitud (int, NOT NULL, FK->SolicitudesMaterial)
- IdActor (int, NULL, FK->Usuarios)
- Accion (varchar(40), NOT NULL)
- EstadoAnterior (varchar(30), NULL)
- EstadoNuevo (varchar(30), NULL)
- Carga (nvarchar, NULL)
- CreadoEn (datetimeoffset, NULL)

### 25. ItemsSolicitudMaterial (nueva)
Origen: material_request_items
- IdItem (PK, int, NOT NULL)
- IdSolicitud (int, NOT NULL, FK->SolicitudesMaterial)
- IdMaterial (int, NOT NULL, FK->Materiales)
- Cantidad (float, NOT NULL)
- CantidadSolicitada (float, NOT NULL)
- CantidadAprobada (float, NOT NULL)
- CantidadEntregada (float, NOT NULL)

### 26. OperacionesSolicitudMaterial (nueva)
Origen: material_request_operations
- IdOperacion (PK, int, NOT NULL)
- IdOperacionCliente (varchar(36), NOT NULL)
- TipoOperacion (varchar(40), NOT NULL)
- IdActor (int, NULL, FK->Usuarios)
- IdSolicitud (int, NULL, FK->SolicitudesMaterial)
- Resultado (nvarchar, NULL)
- CreadoEn (datetimeoffset, NULL)

### 27. SolicitudesMaterial (nueva)
Origen: material_requests
- IdSolicitud (PK, int, NOT NULL)
- IdSolicitante (int, NOT NULL, FK->Usuarios)
- IdTecnico (int, NULL, FK->PerfilesTecnico)
- IdOrden (int, NULL, FK->OrdenesTrabajo)
- Estado (varchar(30), NOT NULL)
- IdOperacionCliente (varchar(36), NULL)
- IdEntregadoPor (int, NULL, FK->Usuarios)
- Motivo (nvarchar, NULL)
- IdAprobadoPor (int, NULL, FK->Usuarios)
- MotivoAprobacion (nvarchar, NULL)
- CreadoEn (datetimeoffset, NULL)
- ActualizadoEn (datetimeoffset, NULL)

### 28. UnidadesMaterial (nueva)
Origen: material_units
- IdUnidad (PK, int, NOT NULL)
- Codigo (varchar(20), NOT NULL)
- Nombre (varchar(60), NOT NULL)
- NombreNormalizado (varchar(60), NOT NULL)
- PermiteDecimal (bit, NOT NULL)
- EstaActivo (bit, NOT NULL)

### 29. Municipios (nueva)
Origen: municipalities
- Codigo (varchar(5), PK, NOT NULL)
- Nombre (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NULL)
- CodigoDepartamento (varchar(2), NULL, FK->Departamentos)

### 30. ConfiguracionNotificaciones (nueva)
Origen: notification_settings
- IdConfiguracion (PK, int, NOT NULL)
- Preferencias (nvarchar, NOT NULL)
- Version (int, NOT NULL)
- IdActualizadoPor (int, NULL, FK->Usuarios)
- ActualizadoEn (datetimeoffset, NULL)

### 31. ConfiguracionOperativa (nueva)
Origen: operational_settings
- IdConfiguracion (PK, int, NOT NULL)
- DiasLaborales (varchar(20), NOT NULL)
- HoraInicio (varchar(5), NOT NULL)
- HoraFin (varchar(5), NOT NULL)
- DuracionVisitaDefault (int, NOT NULL)
- DuracionVisitaMax (int, NOT NULL)
- HorasAntelacionMin (int, NOT NULL)
- MargenTrasladoMin (int, NOT NULL)
- IntervaloCalendario (int, NOT NULL)
- UmbralStockCritico (float, NOT NULL)
- Version (int, NOT NULL)
- IdActualizadoPor (int, NULL, FK->Usuarios)
- ActualizadoEn (datetimeoffset, NULL)

### 32. ConfiguracionOrganizacion (nueva)
Origen: organization_settings
- IdConfiguracion (PK, int, NOT NULL)
- NombreEmpresa (varchar(150), NOT NULL)
- Nit (varchar(40), NULL)
- CorreoAdmin (varchar(120), NOT NULL)
- TelefonoContacto (varchar(30), NULL)
- Direccion (varchar(250), NULL)
- IdCiudad (int, NULL, FK->Ciudades)
- ZonaHoraria (varchar(60), NOT NULL)
- Version (int, NOT NULL)
- IdActualizadoPor (int, NULL, FK->Usuarios)
- ActualizadoEn (datetimeoffset, NULL)

### 33. Sectores (nueva)
Origen: sectors
- IdSector (PK, int, NOT NULL)
- CodigoMunicipio (varchar(5), NULL, FK->Municipios)
- Nombre (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NULL)
- Tipo (varchar(30), NOT NULL)
- EstaActivo (bit, NOT NULL)

### 34. ConfiguracionSeguridad (nueva)
Origen: security_settings
- IdConfiguracion (PK, int, NOT NULL)
- MinutosInactividadSesion (int, NOT NULL)
- HorasMaxSesion (int, NOT NULL)
- LongitudMinContrasena (int, NOT NULL)
- HistorialContrasenas (int, NOT NULL)
- IntentosBloqueo (int, NOT NULL)
- MinutosBloqueo (int, NOT NULL)
- DiasVigenciaContrasenaTemporal (int, NOT NULL)
- Version (int, NOT NULL)
- IdActualizadoPor (int, NULL, FK->Usuarios)
- ActualizadoEn (datetimeoffset, NULL)

### 35. Especialidades (nueva)
Origen: specialties
- Codigo (varchar(60), PK, NOT NULL)
- Etiqueta (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NOT NULL)
- EstaActivo (bit, NOT NULL)

### 36. StockTecnico (nueva)
Origen: technician_stock
- IdStockTecnico (PK, int, NOT NULL)
- IdTecnico (int, NOT NULL, FK->PerfilesTecnico)
- IdMaterial (int, NOT NULL, FK->Materiales)
- Cantidad (float, NOT NULL)
- ActualizadoEn (datetimeoffset, NULL)

### 37. ZonasTecnico (nueva)
Origen: technician_zones
- IdZonaTecnico (PK, int, NOT NULL)
- IdTecnico (int, NOT NULL, FK->PerfilesTecnico)
- IdCiudad (int, NOT NULL, FK->Ciudades)
- IdZona (int, NULL, FK->Zonas)
- EsPrincipal (bit, NOT NULL)

### 38. PreferenciasNotificacionUsuario (nueva)
Origen: user_notification_preferences
- IdPreferencia (PK, int, NOT NULL)
- IdUsuario (int, NOT NULL, FK->Usuarios)
- Preferencias (nvarchar, NOT NULL)
- Version (int, NOT NULL)
- ActualizadoEn (datetimeoffset, NULL)

### 39. ListaVerificacionVisita (nueva)
Origen: visit_checklist_items
- IdItem (PK, int, NOT NULL)
- IdOrden (int, NOT NULL, FK->OrdenesTrabajo)
- Etiqueta (varchar(250), NOT NULL)
- Resultado (varchar(30), NULL)
- Notas (nvarchar, NULL)
- IdVerificadoPor (int, NULL, FK->Usuarios)
- CreadoEn (datetimeoffset, NULL)

### 40. FirmasVisita (nueva)
Origen: visit_signatures
- IdFirma (PK, int, NOT NULL)
- IdOrden (int, NOT NULL, FK->OrdenesTrabajo)
- ClaveAlmacenamiento (varchar(120), NULL)
- NombreFirmante (varchar(120), NULL)
- RolFirmante (varchar(120), NULL)
- FechaRecepcion (datetimeoffset, NULL)
- TextoAceptacion (nvarchar, NULL)
- VersionConsentimiento (varchar(40), NULL)
- IdTecnico (int, NULL, FK->Usuarios)
- Rechazado (bit, NOT NULL)
- MotivoRechazo (nvarchar, NULL)
- IdOperacionCliente (varchar(36), NULL)
- CreadoEn (datetimeoffset, NULL)

### 41. Zonas (nueva)
Origen: zones
- IdZona (PK, int, NOT NULL)
- IdCiudad (int, NOT NULL, FK->Ciudades)
- Tipo (varchar(30), NOT NULL)
- Nombre (varchar(120), NOT NULL)
- NombreNormalizado (varchar(120), NOT NULL)
- EstaActivo (bit, NOT NULL)

---

## Propuesta de columnas nuevas (pendiente de aprobación)

### OrdenesTrabajo (existente) — nueva columna
- AsignadoPorId (INTEGER, NULL, FK->Usuarios) — usuario (coordinador) que asignó/reasignó el técnico. Se llena en cada asignación. Si es nulo (órdenes antiguas), notificar solo a administradores.

### Notificaciones (existente) — columna nueva para lectura
- Leida (BIT, NOT NULL, default 0) — marca de leída para la campana. Alternativa: LeidaEn (DATETIMEOFFSET, NULL).

### Materiales (existente) — stock mínimo
- Ya existe StockMinimo (FLOAT, NOT NULL) en SIGOS. Se usa como punto de reorden para reportes de inventario.

---
## Excepciones a la regla "todo en español"
- Palabras reservadas del framework: id (PK se traduce a Id<Entidad>, pero en codigo Python las variables pueden usar id; se justifica por convencion SQLAlchemy).
- Nombres tecnicos no traducibles: sha256, mime_type (se traduce a TipoArchivo), UUID, JSON, HTTP, JWT, SMTP, etc.
- Tipos de datos SQL: VARCHAR, NVARCHAR, DATETIME, BIT, FLOAT, INTEGER (no se traducen).
- Nombres de migraciones Alembic (revision ids).
- Nombres de archivos/carpetas del framework (app, migrations, tests).

---

## PREGUNTAS / AMBIGUEDADES (detener y preguntar)
1. Auditoria: el proyecto tiene audit_log y audit_events; SIGOS tiene una sola Auditoria. Se mapean ambas a Auditoria (agregando columnas) o se crea AuditoriaEventos (nueva)?
2. Materiales: PrecioUnitario en SIGOS es FLOAT, en el proyecto NUMERIC(18,2). Mantener FLOAT (fuente SIGOS) o cambiar a NUMERIC?
3. MovimientosStock: SIGOS tiene una sola Cantidad; el proyecto tiene 4 (quantity, requested, approved, delivered). Mantener Cantidad + agregar las 3 nuevas?
4. PerfilesTecnico: first_name/last_name en SIGOS no existen; propongo Nombre/Apellido. OK?
5. OrdenesTrabajo: se agregan ~12 columnas nuevas (zone, city_id, zone_id, installation_type, scheduled_*, version, cancel_reason, completed_at). OK?
6. Evidencias: se agregan ~8 columnas nuevas (sha256, declared_capture_at, received_at, status, previous_evidence_id, version_number, duplicate_of_id, client_operation_id). OK?

Espero aprobacion del mapeo (y respuestas a las preguntas) antes de continuar con crear SIGOS_DEV y refactor.
"