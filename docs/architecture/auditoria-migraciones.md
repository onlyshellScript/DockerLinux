# Auditoría de migraciones — SIGOSV (services/api)

Fecha de auditoría: 2026-11-14. Alcance: solo lectura. No se modificaron migraciones ni código.

## 1. Cadena activa (`services/api/migrations/versions`)

| Revisión | `down_revision` | Descripción |
|---|---|---|
| `ef3ab0606ef4` | `None` | Baseline monolítico "esquema_espanol_inicial": crea ~40 tablas con nombres en español (PascalCase) + índices/FK/constraints. |
| `3a374aacae1f` | `ef3ab0606ef4` | Añade `AsignadoPorId` (+ índice + FK a `Usuarios`) en `OrdenesTrabajo`. |
| `615483f3bc21` | `3a374aacae1f` | Añade `Leida` (Boolean, default 0) en `Notificaciones`. |

- **Linealidad:** SÍ. Cadena única `ef3ab0606ef4 → 3a374aacae1f → 615483f3bc21`, sin ramas ni revisiones huérfanas. `head` = `615483f3bc21`.
- El baseline `ef3ab0606ef4` es una revisión "root" nueva (`down_revision=None`), por lo que **no está conectada** con el linaje histórico de `versions_backup`.

## 2. Tablas/columnas/índices en modelos pero no en migraciones activas

Comparación de los 8 `services/api/app/*/models.py` contra las 3 migraciones activas.

- **Tablas:** todas las tablas declaradas en los modelos (`Usuarios`, `Roles`, `UsuariosXRoles`, `Paises`, `Ciudades`, `Zonas`, `Departamentos`, `Municipios`, `Sectores`, `Especialidades`, `TiposInstalacion`, `ZonasTecnico`, `PerfilesTecnico`, `CategoriasMaterial`, `UnidadesMaterial`, `CatalogoMateriales`, `Materiales`, `StockTecnico`, `MovimientosStock`, `SolicitudesMaterial`, `ItemsSolicitudMaterial`, `EntregasSolicitudMaterial`, `ItemsEntregaSolicitud`, `EventosSolicitudMaterial`, `OperacionesSolicitudMaterial`, `OrdenesTrabajo`, `HistorialEstadoOrden`, `Evidencias`, `FirmasVisita`, `RevisionesEvidencia`, `EventosEvidencia`, `ListaVerificacionVisita`, `Notificaciones`, `OperacionesSincronizacion`, `ConfiguracionOrganizacion`, `ConfiguracionOperativa`, `ConfiguracionSeguridad`, `ConfiguracionNotificaciones`, `PreferenciasNotificacionUsuario`, `Auditoria`, `AuditoriaEventos`) están creadas por el baseline.
- **Columnas:** no se detectaron columnas de modelo ausentes en la cadena activa. Las dos adiciones posteriores al baseline (`AsignadoPorId`, `Leida`) están reflejadas tanto en los modelos (`WorkOrder.assigned_by_id`, `Notification.is_read`) como en sus migraciones.
- **Índices/constraints:** los índices declarados en modelos (`unique`/`index`/`__table_args__`, incluidos los índices parciales de `ZonasTecnico` y `ix_city_country_name_norm`) están presentes en la cadena activa.
- **Nota:** los `default=` definidos en Python (no `server_default`) no aparecen como `server_default` en migraciones; es comportamiento esperado de Alembic y no constituye drift de esquema.

**Conclusión:** no se detectan gaps de esquema entre modelos y la cadena activa.

## 3. Cadena histórica (`services/api/migrations/versions_backup`, 21 archivos)

Se verificó `revision`/`down_revision` de los 21 archivos:

```
683fd21c4219 (root, down=None)
 → 611048dcb74d → f33df10403e7 → 36078d0f4f6b → 1c010507bb75
 → 98b6f7e46958 → 012be9890960 → a081cd8fc651 → ed89eaa391be
 → 719f12d0f9c8 → a1b2c3d4e5f6 → b2c3d4e5f6a7 → c3d4e5f6a7b8
 → d4e5f6a7b8c9 → e5f6a7b8c9d0 → e6f7a8b9c0d1 → f4a5b6c7d8e9
 → b1c2d3e4f5a6 → c1d2e3f4a5b6 → e1a2b3c4d5e6 → e2a3b4c5d6e7 (head)
```

- **Encadenamiento:** SÍ es lineal y completo; cada `down_revision` apunta a una revisión existente; no hay huérfanos ni ramas.
- **Pero es un linaje paralelo e incompatible:** tablas/columnas en inglés (`users`, `work_orders`, `material_requests`, `scheduled_at`, etc.) frente al esquema actual en español (`Usuarios`, `OrdenesTrabajo`, `SolicitudesMaterial`, `ProgramadoDesde`). Reutilizarla implicaría renombrar tablas/columnas y migrar datos.
- **Portabilidad:** varias revisiones históricas usan SQL específico de MSSQL (`SET IDENTITY_INSERT`, `GETUTCDATE()`, `sys.default_constraints`, `sys.foreign_keys`), lo que dificulta el replay en SQLite/PostgreSQL.

## 4. Estrategia recomendada

**Recomendación principal: mantener la cadena activa como única fuente de verdad (baseline + 2 deltas) y tratar `versions_backup` como archivo histórico, no ejecutable.**

- No restaurar la cadena antigua: el costo de migración de datos/renombrado supera el beneficio y rompe compatibilidad con los modelos actuales.
- No hacer `alembic stamp` sobre BD legacy sin verificación: el esquema antiguo (inglés) no coincide con el nuevo (español), por lo que un stamp ocultaría drift y rompería la app.
- Para entornos con BD creada con la cadena antigua: planificar una migración de datos one-shot (o recrear BD desde el baseline) antes de apuntar la app al esquema español; validar con `alembic check` y comparación de metadata.
- Para entornos nuevos/vacíos: aplicar la cadena activa completa (`upgrade head`).
- Mantener `versions_backup` fuera de `versions/` (ya está) para que Alembic no lo cargue; opcionalmente archivarlo en un repositorio de migraciones legacy.
- Mitigar drift futuro: ejecutar `alembic revision --autogenerate` + `alembic check` en CI antes de merge; cualquier cambio de modelo debe generar migración en la cadena activa.

**Riesgos:**
- Alta: pérdida de datos si se aplica el baseline sobre una BD legacy sin migración previa.
- Alta: downtime durante migración de esquema inglés→español.
- Media: incompatibilidad de dialectos (MSSQL) al intentar replay de la cadena antigua.
- Baja: drift silencioso si se usan stamps sin verificación.

---

Solo lectura: no se modificaron migraciones, modelos ni otros archivos.
