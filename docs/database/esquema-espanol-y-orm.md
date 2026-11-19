# Esquema en español, mapeo ORM y estado de migraciones

> Actualizado: 17/11/2026 · Modelos: `services/api/app/*/models.py`

## 1. Contexto

La base `SIGOS_DEV` (SQL Server) usa el esquema en español creado por la migración `ef3ab0606ef4`
(`Usuarios`, `Roles`, `UsuariosXRoles`, `OrdenesTrabajo`, `Materiales`, `Evidencias`, …; 41 tablas).
Los modelos SQLAlchemy conservan **atributos en inglés** (`user.id`, `user.username`, `wo.status`) y declaran el
**nombre físico** en español:

```python
class User(db.Model):
    __tablename__ = "Usuarios"
    id = db.Column("IdUsuario", db.Integer, primary_key=True)
    username = db.Column("Nombre_usuario", db.String(80), unique=True, nullable=False, index=True)
```

Así el resto del backend (servicios, rutas, serialización) no cambia. Las claves foráneas, `UniqueConstraint`,
`Index` y `CheckConstraint` usan los nombres físicos en español.

> `docs/DOCUMENTACION_COMPLETA.md` §3.1 lista las tablas con sus nombres antiguos en inglés; la equivalencia es
> `users → Usuarios`, `work_orders → OrdenesTrabajo`, etc. (ver `docs/mapeo_tablas.md`).

## 2. Particularidades

| Tabla | Nota |
|---|---|
| `Evidencias` | No tiene columnas propias para `file_name`, `stored_name`, `file_type`, `file_size`: en el modelo son **sinónimos** de `original_name`, `storage_key`, `mime_type`, `size_bytes`. |
| `Notificaciones` | Columna `Leida` (bit, con default) sin uso en el ORM. |
| `OrdenesTrabajo` | Columna `AsignadoPorId` (nullable) sin uso en el ORM. |
| Fechas | Columnas `DATETIMEOFFSET` (con zona). En SQLite (tests) se guardan sin zona; el código que compara fechas normaliza a UTC. |

## 3. SQL escrito a mano

`materials/service.py::_lock_row` (bloqueos `UPDLOCK, HOLDLOCK`, solo SQL Server) usa nombres físicos:
`Materiales.IdMaterial`, `StockTecnico (IdTecnico, IdMaterial)`, `SolicitudesMaterial.IdSolicitud`, `Evidencias.IdOrden`.
Los tests con SQLite **no** ejecutan este SQL; se verificó contra SQL Server.

## 4. Estado de las migraciones (Alembic)

- **Cadena válida (español):** `ef3ab0606ef4` (baseline) → `3a374aacae1f` (`AsignadoPorId`) → `615483f3bc21` (`Leida`).
- **`SIGOS_DEV`** está en `615483f3bc21` (cabeza de la cadena válida).
- **18/11/2026:** nueva migración `a7c8e9f0b1d2` (sesiones revocables `SesionesUsuario`, firma del técnico `FirmasTecnico`,
  columnas nullable de firma histórica en `Evidencias`), encadenada a `615483f3bc21`. Equivalente SQL Server manual:
  `docs/database/2026-11-18_sesiones_firmas.sql`. Detalle: `docs/architecture/2026-11-18-sesiones-firmas-evidencias.md`.
- **Problema:** en `migrations/versions/` conviven además las 21 migraciones antiguas en inglés (`683fd21c4219` …
  `f4a5b6c7d8e9`), duplicadas de `versions_backup/`. Crean una **segunda raíz** y `e5f6a7b8c9d0` apunta a
  `d4e5f6a7b8c9`, que solo existe en `versions_backup/`. Resultado: `flask db upgrade` falla con `KeyError: 'd4e5f6a7b8c9'`.
- **Corrección propuesta (no aplicada):** dejar en `versions/` solo las 3 migraciones de la cadena española
  (las 21 en inglés ya están en `versions_backup/`) y verificar con `flask --app wsgi db heads` (una sola cabeza) y
  `flask --app wsgi db upgrade` sobre una base vacía.

## 5. Datos de desarrollo

- Usuario `admin`: contraseña en `services/api/.env` (`ADMIN_PASSWORD`, archivo ignorado por git).
- `seed.py` crea roles y el admin solo si no hay usuarios.
