# Esquema original de SIGOS (solo lectura)

Base: SIGOS en <servidor-sql>:1433 (SQL Server). Tabla `sysdiagrams` excluida.
Generado automaticamente. NO modificar SIGOS.

## Tabla: Auditoria

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdAuditoria | INTEGER | False |  |
| NombreTabla | VARCHAR(100) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Accion | VARCHAR(20) COLLATE "Modern_Spanish_CI_AS" | False |  |
| IdRegistro | INTEGER | False |  |
| DatosAntiguos | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | True |  |
| DatosNuevos | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | True |  |
| IdUsuario | INTEGER | True |  |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdAuditoria']
Nombre: PK__Auditori__7FD13FA06F8B0D3E

### Claves foraneas

(ninguna)

### Indices

(ninguno adicional)

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- CreadoEn default (sysdatetimeoffset()) (constraint DF__Auditoria__Cread__2EA5EC27)

---

## Tabla: Evidencias

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdEvidencia | INTEGER | False |  |
| IdOrden | INTEGER | False |  |
| IdSubidoPor | INTEGER | False |  |
| TipoEvidencia | VARCHAR(20) COLLATE "Modern_Spanish_CI_AS" | False |  |
| NombreArchivo | VARCHAR(250) COLLATE "Modern_Spanish_CI_AS" | True |  |
| NombreAlmacenado | VARCHAR(250) COLLATE "Modern_Spanish_CI_AS" | True |  |
| TipoArchivo | VARCHAR(50) COLLATE "Modern_Spanish_CI_AS" | True |  |
| TamañoArchivo | INTEGER | True |  |
| Descripcion | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | True |  |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdEvidencia']
Nombre: PK_Evidencias

### Claves foraneas

- ['IdOrden'] -> OrdenesTrabajo ['IdOrden'] (nombre: FK_Evidencias_OrdenesTrabajo)
- ['IdSubidoPor'] -> Usuarios ['IdUsuario'] (nombre: FK_Evidencias_PerfilesTecnico)

### Indices

- NonClusteredIndex_NombreAlmacendo : ['NombreAlmacenado'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- CreadoEn default (sysdatetimeoffset()) (constraint DF_Evidencias_CreadoEn)

---

## Tabla: HistorialEstadoOrden

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdHistorial | INTEGER | False |  |
| IdOrden | INTEGER | False |  |
| EstadoAnterior | VARCHAR(20) COLLATE "Modern_Spanish_CI_AS" | False |  |
| EstadoNuevo | VARCHAR(20) COLLATE "Modern_Spanish_CI_AS" | False |  |
| IdCambiadoPor | INTEGER | False |  |
| Notas | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | True |  |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdHistorial']
Nombre: PK_HistorialEstadoOrden

### Claves foraneas

- ['IdOrden'] -> OrdenesTrabajo ['IdOrden'] (nombre: FK_HistorialEstadoOrden_OrdenesTrabajo)
- ['IdCambiadoPor'] -> Usuarios ['IdUsuario'] (nombre: FK_HistorialEstadoOrden_Usuarios)

### Indices

- NonClusteredIndex_IdCambiadoPor : ['IdCambiadoPor'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- CreadoEn default (sysdatetimeoffset()) (constraint DF_HistorialEstadoOrden_CreadoEn)

---

## Tabla: Materiales

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdMaterial | INTEGER | False |  |
| Nombre | VARCHAR(120) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Descripcion | VARCHAR(250) COLLATE "Modern_Spanish_CI_AS" | True |  |
| Unidad | VARCHAR(20) COLLATE "Modern_Spanish_CI_AS" | False |  |
| StockActual | FLOAT | False | ((0)) |
| StockMinimo | FLOAT | False | ((0)) |
| PrecioUnitario | FLOAT | False | ((0)) |
| EstaActivo | BIT | False | ((1)) |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |
| ActualizadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdMaterial']
Nombre: PK_Materiales

### Claves foraneas

(ninguna)

### Indices

- NonClusteredIndex-NombreMaterial : ['Nombre'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- StockActual default ((0)) (constraint DF_Materiales_StockActual)
- StockMinimo default ((0)) (constraint DF_Materiales_StockMinimo)
- PrecioUnitario default ((0)) (constraint DF_Materiales_PrecioUnitario)
- EstaActivo default ((1)) (constraint DF_Materiales_EstaActivo)
- CreadoEn default (sysdatetimeoffset()) (constraint DF_Materiales_CreadoEn)
- ActualizadoEn default (sysdatetimeoffset()) (constraint DF_Materiales_ActualizadoEn)

---

## Tabla: MovimientosStock

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdMovimiento | INTEGER | False |  |
| IdMaterial | INTEGER | False |  |
| Cantidad | FLOAT | False |  |
| TipoMovimiento | VARCHAR(15) COLLATE "Modern_Spanish_CI_AS" | False |  |
| IdOrden | INTEGER | True |  |
| IdUsuario | INTEGER | False |  |
| Notas | VARCHAR(250) COLLATE "Modern_Spanish_CI_AS" | True |  |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdMovimiento']
Nombre: PK_MovimientosStock

### Claves foraneas

- ['IdMaterial'] -> Materiales ['IdMaterial'] (nombre: FK_MovimientosStock_Materiales)
- ['IdOrden'] -> OrdenesTrabajo ['IdOrden'] (nombre: FK_MovimientosStock_OrdenesTrabajo)
- ['IdUsuario'] -> Usuarios ['IdUsuario'] (nombre: FK_MovimientosStock_Usuarios)

### Indices

- NonClusteredIndex-IdOrden : ['IdOrden'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- CreadoEn default (sysdatetimeoffset()) (constraint DF_MovimientosStock_CreadoEn)

---

## Tabla: Notificaciones

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdNotificacion | INTEGER | False |  |
| IdUsuario | INTEGER | False |  |
| Canal | VARCHAR(15) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Destinatario | VARCHAR(250) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Asunto | VARCHAR(200) COLLATE "Modern_Spanish_CI_AS" | True |  |
| Mensaje | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | False |  |
| Estado | VARCHAR(15) COLLATE "Modern_Spanish_CI_AS" | False | ('Pendiente') |
| Intentos | INTEGER | False | ((0)) |
| MensajeError | VARCHAR(500) COLLATE "Modern_Spanish_CI_AS" | True |  |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |
| EnviadoEn | DATETIMEOFFSET | True |  |

### Clave primaria

Columnas: ['IdNotificacion']
Nombre: PK_Notificaciones

### Claves foraneas

- ['IdUsuario'] -> Usuarios ['IdUsuario'] (nombre: FK_Notificaciones_Usuarios)

### Indices

- NonClusteredIndex-Destinatario : ['Destinatario'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- Intentos default ((0)) (constraint DF_Notificaciones_Intentos)
- Estado default ('Pendiente') (constraint DF_Notificaciones_Estado)
- CreadoEn default (sysdatetimeoffset()) (constraint DF_Notificaciones_CreadoEn)

---

## Tabla: OperacionesSincronizacion

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdOperacion | INTEGER | False |  |
| IdOperacionCliente | VARCHAR(36) COLLATE "Modern_Spanish_CI_AS" | False |  |
| TipoOperacion | VARCHAR(50) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Carga | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | False |  |
| IdUsuario | INTEGER | False |  |
| Estado | VARCHAR(15) COLLATE "Modern_Spanish_CI_AS" | False | ('Estado') |
| Resultado | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | True |  |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |
| SincronizadoEn | DATETIMEOFFSET | True |  |

### Clave primaria

Columnas: ['IdOperacion']
Nombre: PK_OperacionesSincronizacion

### Claves foraneas

- ['IdUsuario'] -> Usuarios ['IdUsuario'] (nombre: FK_OperacionesSincronizacion_Usuarios)

### Indices

- NonClusteredIndex-TipoOperacion : ['TipoOperacion'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- Estado default ('Estado') (constraint DF_OperacionesSincronizacion_Estado)
- CreadoEn default (sysdatetimeoffset()) (constraint DF_OperacionesSincronizacion_CreadoEn)

---

## Tabla: OrdenesTrabajo

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdOrden | INTEGER | False |  |
| Titulo | VARCHAR(200) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Descripcion | NVARCHAR COLLATE "Modern_Spanish_CI_AS" | True |  |
| Estado | VARCHAR(20) COLLATE "Modern_Spanish_CI_AS" | False | ('Pendiente') |
| Prioridad | VARCHAR(10) COLLATE "Modern_Spanish_CI_AS" | False | ('Media') |
| NombreCliente | VARCHAR(120) COLLATE "Modern_Spanish_CI_AS" | True |  |
| TelefonoCliente | VARCHAR(30) COLLATE "Modern_Spanish_CI_AS" | True |  |
| Direccion | VARCHAR(250) COLLATE "Modern_Spanish_CI_AS" | True |  |
| IdAsignadoA | INTEGER | True |  |
| IdCreadoPor | INTEGER | False |  |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |
| ActualizadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdOrden']
Nombre: PK_OrdenesTrabajo

### Claves foraneas

- ['IdCreadoPor'] -> Usuarios ['IdUsuario'] (nombre: FK_OrdenesTrabajo_Usuarios)
- ['IdAsignadoA'] -> Usuarios ['IdUsuario'] (nombre: FK_OrdenesTrabajo_Usuarios1)

### Indices

- NonClusteredIndex-NombreCliente : ['NombreCliente'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- Estado default ('Pendiente') (constraint DF_OrdenesTrabajo_Estado)
- Prioridad default ('Media') (constraint DF_OrdenesTrabajo_Prioridad)
- CreadoEn default (sysdatetimeoffset()) (constraint DF_OrdenesTrabajo_CreadoEn)
- ActualizadoEn default (sysdatetimeoffset()) (constraint DF_OrdenesTrabajo_ActualizadoEn)

---

## Tabla: PerfilesTecnico

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdPerfil | INTEGER | False |  |
| IdUsuario | INTEGER | False |  |
| Telefono | VARCHAR(30) COLLATE "Modern_Spanish_CI_AS" | True |  |
| Especialidad | VARCHAR(80) COLLATE "Modern_Spanish_CI_AS" | True |  |
| EstaDisponible | BIT | False | ((1)) |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |
| ActualizadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdPerfil']
Nombre: PK_PerfilesTecnico

### Claves foraneas

- ['IdUsuario'] -> Usuarios ['IdUsuario'] (nombre: FK_PerfilesTecnico_Usuarios)

### Indices

- NonClusteredIndex-IdUsuario : ['IdUsuario'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- EstaDisponible default ((1)) (constraint DF_PerfilesTecnico_EstaDisponible)
- CreadoEn default (sysdatetimeoffset()) (constraint DF_PerfilesTecnico_CreadoEn)
- ActualizadoEn default (sysdatetimeoffset()) (constraint DF_PerfilesTecnico_ActualizadoEn)

---

## Tabla: Roles

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdRol | INTEGER | False |  |
| Nombre | VARCHAR(50) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Descripcion | VARCHAR(200) COLLATE "Modern_Spanish_CI_AS" | True |  |

### Clave primaria

Columnas: ['IdRol']
Nombre: PK_Roles

### Claves foraneas

(ninguna)

### Indices

- NonClusteredIndex-NombreRol : ['Nombre'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

(ninguno)

---

## Tabla: Usuarios

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdUsuario | INTEGER | False |  |
| Nombre_usuario | VARCHAR(80) COLLATE "Modern_Spanish_CI_AS" | False |  |
| Correo | VARCHAR(120) COLLATE "Modern_Spanish_CI_AS" | False |  |
| HashContraseña | VARCHAR(256) COLLATE "Modern_Spanish_CI_AS" | False |  |
| EstaActivo | BIT | False | ((1)) |
| CreadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |
| ActualizadoEn | DATETIMEOFFSET | True | (sysdatetimeoffset()) |

### Clave primaria

Columnas: ['IdUsuario']
Nombre: PK_Usuarios

### Claves foraneas

(ninguna)

### Indices

- NonClusteredIndex-NombreUsuario : ['Nombre_usuario'] unique=False

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

- EstaActivo default ((1)) (constraint DF_Usuarios_EstaActivo)
- CreadoEn default (sysdatetimeoffset()) (constraint DF_Usuarios_CreadoEn)
- ActualizadoEn default (sysdatetimeoffset()) (constraint DF_Usuarios_ActualizadoEn)

---

## Tabla: UsuariosXRoles

### Columnas

| Columna | Tipo | Nullable | Default |
|---|---|---|---|
| IdUsuario | INTEGER | False |  |
| IdRol | INTEGER | False |  |

### Clave primaria

Columnas: ['IdUsuario', 'IdRol']
Nombre: PK_UsuariosXRoles

### Claves foraneas

- ['IdRol'] -> Roles ['IdRol'] (nombre: FK_UsuariosXRoles_Roles)
- ['IdUsuario'] -> Usuarios ['IdUsuario'] (nombre: FK_UsuariosXRoles_Usuarios2)

### Indices

(ninguno adicional)

### Restricciones UNIQUE

(ninguna o no disponible via inspector)

### Restricciones CHECK (sys.check_constraints)

(ninguna)

### Defaults (sys.default_constraints)

(ninguno)

---
