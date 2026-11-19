# Plan de recuperación de migraciones (Alembic)

> Fase 0.5 · 18/11/2026 · Diagnóstico de **solo lectura**: no se movió, borró ni editó ninguna migración y no se
> ejecutó `flask db upgrade`/`downgrade`. Las consultas a `SIGOS_DEV` fueron `SELECT`/`inspect`; la prueba de login se
> hizo dentro de una transacción revertida.
>
> **Corrige** lo afirmado el 17/11 en `docs/database/esquema-espanol-y-orm.md` §4 (ver §7).

> **Estado (18/11/2026, Fase 1): EJECUTADO.** Pasos 1–6 de §6 aplicados y validados:
> respaldo `SIGOS_DEV_preR2_20261118_195235.bak` (COPY_ONLY, CHECKSUM, `RESTORE VERIFYONLY` correcto, carpeta de
> respaldos por defecto de la instancia); cadena española versionada (`7670df7`); inglesa movida a
> `migrations/legacy_en/` con `d4e5f6a7b8c9` (`82339c2`); `db heads` = `a7c8e9f0b1d2` (única); instalación nueva en
> `SIGOS_MIGTEST` = 43/43 tablas sin diferencias; `SIGOS_DEV` migrada `615483f3bc21 → a7c8e9f0b1d2`, 43/43 tablas y
> login 200. Drift M5 (`Leida`, `AsignadoPorId`) sin cambios. `SIGOS_MIGTEST` se conserva (base desechable, sin datos).

## 1. Entorno consultado

| Dato | Valor |
|---|---|
| Servidor / base | `localhost` / `SIGOS_DEV` (desarrollo) |
| Motor | SQL Server 17.0.1000.7 (2025) Express, 64-bit |
| Driver | ODBC Driver 18 for SQL Server |
| `alembic_version` | **`615483f3bc21`** |

No se consultó ninguna base productiva (no hay credenciales ni conexión a producción en este equipo).

## 2. Inventario de revisiones

### 2.1 `migrations/versions/` (24 archivos)

| Cadena | Revisiones | En Git |
|---|---|---|
| **Española** (válida) | `ef3ab0606ef4` (raíz, baseline) → `3a374aacae1f` (`AsignadoPorId`) → `615483f3bc21` (`Leida`) → `a7c8e9f0b1d2` (sesiones y firmas, 18/11) | **No** (4 archivos sin rastrear) |
| **Inglesa** (histórica) | `683fd21c4219` (raíz) → … → `c3d4e5f6a7b8` ✕ `e5f6a7b8c9d0` → `e6f7a8b9c0d1` → `f4a5b6c7d8e9` → `b1c2d3e4f5a6` → `c1d2e3f4a5b6` → `e1a2b3c4d5e6` → `e2a3b4c5d6e7` | Sí (20 archivos, modificados sin commit) |

✕ = eslabón roto: `e5f6a7b8c9d0.down_revision = 'd4e5f6a7b8c9'`, y `d4e5f6a7b8c9` **no está** en `versions/`.

### 2.2 `migrations/versions_backup/` (21 `.py` + 21 `.pyc`, sin rastrear)

Las 20 inglesas de `versions/` **más** `d4e5f6a7b8c9` (`down_revision = c3d4e5f6a7b8`). Es la única copia de esa revisión:
**`d4e5f6a7b8c9` nunca estuvo en el historial de Git** (`git log --all` no la registra).

### 2.3 Cambios sin commit en las inglesas

Los 21 archivos modificados de `migrations/` (20 versiones + `env.py`) tienen **solo comentarios** añadidos (0 líneas
de código cambiadas, verificado). `versions_backup/` es una copia del working tree con esos comentarios.

## 3. Diagnóstico

| # | Hallazgo | Consecuencia |
|---|---|---|
| M1 | Dos raíces en `versions/` (`683fd21c4219` y `ef3ab0606ef4`). | `flask db upgrade` no puede resolver una cabeza única. |
| M2 | `d4e5f6a7b8c9` ausente de `versions/` y del historial Git. | `KeyError: 'd4e5f6a7b8c9'`: Alembic no carga el árbol. **Roto en todos los commits**, no solo en el working tree. |
| M3 | La cadena española (incluida la base que usa `SIGOS_DEV`) **no está en Git**. | Un clon limpio no puede crear el esquema que usa el código. |
| M4 | **`SIGOS_DEV` está en `615483f3bc21`: `a7c8e9f0b1d2` no está aplicada.** | Ver §4. |
| M5 | `Notificaciones.Leida` y `OrdenesTrabajo.AsignadoPorId` existen en la BD y no en los modelos. | Sin impacto funcional (nullable/default). Drift documentado. |

## 4. Impacto inmediato de M4 (bloqueante)

Comparación `SIGOS_DEV` ↔ modelos actuales:

- Tablas en modelos y **no** en BD: `SesionesUsuario`, `FirmasTecnico`.
- Columnas en modelos y **no** en BD: `Evidencias.IdFirmaTecnico`, `FirmaTecnicoSha256`, `IdTecnicoFirmante`, `FechaFirmaTecnico`.

Prueba con el código actual contra `SIGOS_DEV` (transacción revertida): `POST /auth/login` → **500**
`Invalid object name 'SesionesUsuario'`. **Al reiniciar la API con el código del working tree, nadie podrá iniciar
sesión** hasta aplicar `a7c8e9f0b1d2` (o su equivalente `docs/database/2026-11-18_sesiones_firmas.sql`).

`a7c8e9f0b1d2` es **aditiva** (crea 2 tablas, 2 índices y 4 columnas nullable con su índice/FK); el script SQL no tiene
`DROP`, `DELETE` ni `TRUNCATE`. Cumple el patrón *expand*. Su `downgrade` sí elimina tablas (solo para rollback).

## 5. ¿Siguen siendo necesarias las migraciones inglesas?

- `SIGOS_DEV` y cualquier base creada con el baseline `ef3ab0606ef4` **no** las necesitan: el baseline crea el esquema
  completo en español.
- Una base creada con la cadena inglesa tendría tablas **en inglés** (`users`, `work_orders`…), incompatibles con los
  modelos actuales: el código ya no puede funcionar sobre ella. No hay evidencia en el repositorio de una base así en uso;
  **debe confirmarse** con los responsables de otros entornos antes de retirarlas.
- Conclusión: son historia, no camino de actualización. Deben conservarse **fuera** de `versions/`.

## 6. Propuesta de recuperación (requiere aprobación)

Orden pensado para que una instalación **nueva** y una **existente** lleguen al mismo esquema:

1. **Respaldo** de `SIGOS_DEV` (`scripts/backup-db.ps1` o `BACKUP DATABASE`) y de `migrations/` (copia de la carpeta).
2. **Versionar la cadena española**: commitear `ef3ab0606ef4`, `3a374aacae1f`, `615483f3bc21`, `a7c8e9f0b1d2`.
3. **Retirar del árbol activo la cadena inglesa** con `git mv` (conserva historia) a `migrations/legacy_en/`
   (no la escanea Alembic), **incluyendo** `d4e5f6a7b8c9` desde `versions_backup/`, que así queda en Git por primera vez.
   `versions_backup/` deja de ser necesario; sus `.pyc` no se commitean.
4. **Verificar el árbol** sin tocar ninguna base: `flask --app wsgi db heads` → una sola cabeza `a7c8e9f0b1d2`;
   `flask --app wsgi db history` → cadena lineal de 4.
5. **Instalación nueva**: `flask db upgrade` sobre una base **vacía y desechable** (p. ej. `SIGOS_MIGTEST` en el SQL Server
   local); comparar su esquema con los modelos con el mismo script de §4 (0 diferencias esperadas, salvo M5).
6. **Instalación existente**: tras el respaldo, `flask db upgrade` en `SIGOS_DEV` (aplica solo `a7c8e9f0b1d2`);
   repetir la comparación y el login.
7. **Producción** (cuando exista): mismo procedimiento con ventana y respaldo; nunca desde el arranque de los workers
   (se ejecuta una vez, desde un paso controlado del despliegue).

Rollback: restaurar el respaldo de la base; revertir el commit de `git mv`. `alembic downgrade 615483f3bc21` solo si no se
han escrito datos en las tablas nuevas.

## 7. Correcciones al diagnóstico del 17/11

| Se afirmó | Realidad verificada |
|---|---|
| 21 migraciones inglesas en `versions/` | **20**; la 21.ª (`d4e5f6a7b8c9`) solo está en `versions_backup/` |
| Las de `versions/` están duplicadas en `versions_backup/` | No son idénticas: difieren en comentarios; y el backup **no** está en Git |
| Basta con sacar las inglesas de `versions/` | Además hay que **versionar** la cadena española y **aplicar `a7c8e9f0b1d2`** en `SIGOS_DEV` |

## 8. Validación posterior

- `db heads` único y `db history` lineal.
- Comparación esquema↔modelos sin diferencias (salvo M5) en la base nueva y en `SIGOS_DEV`.
- Login, sesiones revocables y firma del técnico contra SQL Server real.
- Suite completa con `TEST_DB_URL` apuntando a una base de pruebas de SQL Server (hoy omitida).
