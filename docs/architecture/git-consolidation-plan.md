# Plan de consolidación Git

> Fase 0.5 · 18/11/2026 · **Propuesta**: no se ha creado ningún commit, fusión, stash ni movimiento de archivos.
> Único cambio en el working tree durante esta fase: este documento y `migration-recovery-plan.md`.

## 1. Estado inicial (fuente de verdad: `git status`)

| Dato | Valor |
|---|---|
| Rama actual | `fix/panel-admin` (`6796ec1`, 70 commits sobre `main`) |
| Entradas pendientes | **207**: 141 modificadas, 66 sin rastrear, 0 en staging, 0 eliminadas |
| Stash | vacío |
| **Remoto** | **ninguno configurado** (`git remote -v` vacío): el CI no se ejecuta y no se puede verificar `CI_DB_PASSWORD` desde este clon |
| Worktrees | `SIGOSV-blockA` (`feat/mobile-sync-ui`), `SIGOSV-blockB` (`chore/ci-secrets-docker`), 4 worktrees `agent/*` en `main` sin cambios, 1 temporal de opencode |
| Línea base de pruebas | API: **403 passed, 11 skipped, 0 failed** (SQLite) · Desktop: **49/49** |

### Hallazgo: el historial commiteado no arranca

`HEAD` registra en `app/__init__.py` los blueprints `app.tecnico` y `app.reportes` (que importa `reportes/service.py`),
pero `app/tecnico/` y `app/reportes/service.py` **nunca se commitearon**. Cualquier checkout limpio de `fix/panel-admin`,
`chore/ci-secrets-docker` o `feat/mobile-sync-ui` falla al importar la app. El primer commit de backend debe incluirlos.

## 2. Ramas

| Rama | Relación | Aporta | Conflictos con el working tree | Pruebas para fusionar |
|---|---|---|---|---|
| `fix/cierre-brechas-criticas` | **ya contenida** en `fix/panel-admin` | — | — | — (puede archivarse) |
| `work/estado-actual` | **ya contenida** | — | — | — |
| `agent/backend`, `agent/desktop`, `agent/mobile`, `agent/tests` | = `main` (sin commits propios) | — | — | — (worktrees vacíos) |
| `chore/ci-secrets-docker` | `HEAD` + 1 commit | `ci.yml`: YAML válido, secreto vía `env`, job `build-api-image` con healthcheck | **ninguno** (`ci.yml` sin cambios locales) | validar YAML; el job de build fallará hasta commitear el backend (hallazgo §1) |
| `feat/mobile-sync-ui` | `HEAD` + 1 commit | Cola offline integrada en la UI móvil (8 archivos) | **7 de 8 archivos** tienen cambios locales; 37 líneas funcionales (logout contra la API, borrado de caché local, sesión) además de comentarios | `flutter analyze`, `flutter test`, revisión manual de cada archivo |

## 3. Inventario por área

Fecha según `mtime`: el trabajo del 17/11 (138 entradas) y del 18/11 (51) **comparten archivos** (`app.js`,
`identity/*`, `decorators.py`, `config*.py`, `evidence/*`, `main/index.js`, `index.html`…). No es posible separar por
sesión sin partir archivos; los commits se organizan **por área funcional**.

| # | Área | Modificados | Nuevos | Contenido principal |
|---|---|---|---|---|
| 1 | API / backend | 41 | 7 | Modelos mapeados al esquema español, `_lock_row`, `settings`, calendario, materiales, órdenes, notificaciones; nuevos `tecnico/`, `reportes/service.py`, `evidence/signatures.py`, `maintenance/`, `seed_calendar.py`, `pytest.ini` |
| 2 | Auth / seguridad | 6 | — | Administración de usuarios, roles desde la BD, `PASSWORD_CHANGE_REQUIRED`, sesiones revocables, logout (18/11) |
| 3 | BD / migraciones | 21 (solo comentarios) | 5 | Cadena española (4) sin rastrear; `versions_backup/` |
| 4 | Electron | 16 | 9 | Sistema de diseño, componentes, asistente, rediseño; cargador/tema/transiciones (18/11); IPC `api-binary`, preferencias |
| 5 | Móvil | 18 | — | Comentarios + cambios funcionales de sesión/logout (18/11) |
| 6 | Exportaciones | 2 | 3 | `app/exports/`, delegación de `/reportes/ordenes` |
| 7 | CI / Docker | 0 | 0 | (el cambio vive en `chore/ci-secrets-docker`) |
| 8 | Documentación | 4 | 23 | Guías 17/11 y 18/11, docs del análisis, `DOCUMENTACION.md`, `.docx` |
| 9 | Configuración | 1 | — | `.env.example` (+`EVIDENCE_REQUIRE_TECH_SIGNATURE`, sin secretos) |
| 10 | Experimental / artefactos | 1 | ~8 | `sigos_flask` (solo comentarios), `.agent/`, `.archify/`, capturas, `salida_sqlserver.txt`, `uploads/` |
| — | Tests | API 19 + desktop 10 | API 8 + desktop 3 | acompañan a cada área |

## 4. Archivos con protección especial

| Ruta | Motivo | Acción propuesta |
|---|---|---|
| `services/api/uploads/` (542 archivos, 2,8 MB) | **Evidencias y firmas reales**; no está en `.gitignore` | Añadir a `.gitignore` **antes** de cualquier `git add`. Nunca commitear |
| `services/api/.env` | Credenciales y `ADMIN_PASSWORD` | Ya ignorado; verificar en cada commit |
| `migrations/versions_backup/d4e5f6a7b8c9_*.py` | **Única copia** de esa revisión (nunca en Git) | No borrar; versionar como histórico (ver plan de migraciones) |
| `migrations/versions/*` | Cadena que usa `SIGOS_DEV` sin versionar | No mover sin aprobación |
| `requerimientos/*.pdf` (4,7 MB) | Documento fuente de requisitos | Decidir: commitear, Git LFS o fuera del repo |
| `docs/DOCUMENTACION_COMPLETA.docx` | Binario exportado | Decidir si se versiona |
| `.archify/`, `.agent/` | Salidas de herramientas | Proponer ignorar |
| `apps/desktop/screenshots/`, `tests/visual/screenshots/` | Capturas generadas | Proponer ignorar |
| `services/api/salida_sqlserver.txt` | Log de una ejecución de pruebas | Proponer ignorar |

## 5. Inconsistencias detectadas

- `contracts/openapi.yaml` documenta los endpoints del 18/11 (logout, cancelación, firmas) pero **no** `/exports/*`,
  `/users/*` (administración) ni `/roles`.
- Dos documentos maestros: `DOCUMENTACION.md` (raíz, nuevo) y `docs/DOCUMENTACION_COMPLETA.md`.
- `migrations/env.py` modificado (solo comentarios).
- `SIGOS_DEV` sin la migración del 18/11: el código actual no permite login contra esa base (ver plan de migraciones §4).

## 6. Propuesta de commits (orden)

Cada commit lista sus archivos explícitamente (`git add <rutas>`; **nunca** `git add -A`).
C3–C5 tienen dependencias cruzadas (modelos ↔ autenticación ↔ exportaciones) y se validan **juntos** al final de C5.

| # | Commit | Contenido | Validación |
|---|---|---|---|
| C1 | `chore(repo): ignorar evidencias locales y artefactos generados` | `.gitignore` (+`services/api/uploads/`, capturas, `.agent/`, `.archify/`, `salida_sqlserver.txt`, `*.pyc`) | `git status` ya no lista `uploads/` |
| C2 | `feat(db): versionar la cadena de migraciones en español` | `ef3ab0606ef4`, `3a374aacae1f`, `615483f3bc21`, `a7c8e9f0b1d2` | — (sin mover las inglesas todavía) |
| C3 | `feat(api): modelos sobre el esquema en español y módulos pendientes` | `services/api/app/**` salvo `identity/`, `exports/`; `tecnico/`, `reportes/service.py`, `signatures.py`, `maintenance/`; `seed_calendar.py`, `pytest.ini`; `.env.example`; tests del área | (junto con C5) |
| C4 | `feat(auth): administración de usuarios, roles desde la BD y sesiones revocables` | `services/api/app/identity/**`; `test_users_admin.py`, `test_sesiones_firmas.py`, `test_auth.py`, `test_rnf04/05` | (junto con C5) |
| C5 | `feat(exports): motor de exportaciones PDF/XLSX con plantillas` | `app/exports/**`, `reportes/routes.py`, `app/__init__.py`, `test_exports.py` | **API completa** debe pasar |
| C6 | `feat(desktop): sistema de diseño, componentes, asistente de exportación y rediseño` | `apps/desktop/src/**`, `apps/desktop/tests/**` (sin capturas) | `npm test` 49/49 + recorrido Electron |
| C7 | `feat(mobile): logout contra la API y limpieza de caché de sesión` | `apps/mobile/**` | `flutter analyze`, `flutter test` |
| C8 | `docs: documentación técnica y de arquitectura` | `docs/**` (sin binarios pendientes de decisión), `README.md`, `contracts/openapi.yaml`, `examples/`, `scripts/*.py`, `DOCUMENTACION.md` | revisión |
| C9 | `chore(sigos_flask): comentarios del prototipo` | `sigos_flask/**` | — |
| — | `migrations/*` (solo comentarios) | 21 archivos | Se incluyen en el commit de reparación (ver abajo) para no tocar dos veces el árbol |

### Fusiones (después de C1–C9)

| # | Operación | Conflictos esperados | Validación |
|---|---|---|---|
| F1 | `git merge --no-ff chore/ci-secrets-docker` | ninguno | YAML válido; con un remoto configurado: secreto `CI_DB_PASSWORD` y primer run |
| F2 | `git merge --no-ff feat/mobile-sync-ui` | 7 archivos móviles (C7 vs. rama): **resolución manual**, conservando el logout/caché de C7 y la cola offline de la rama | `flutter analyze`, `flutter test`, prueba manual de logout + sincronización |

### Reparación de migraciones (aprobación aparte)

| # | Operación | Detalle |
|---|---|---|
| R1 | `refactor(db): retirar la cadena inglesa del árbol activo de Alembic` | `git mv` de las 20 inglesas a `migrations/legacy_en/` + `d4e5f6a7b8c9` desde `versions_backup/`; comentarios incluidos; `versions_backup/` deja de usarse |
| R2 | Aplicar `a7c8e9f0b1d2` en `SIGOS_DEV` | Tras respaldo; `flask db upgrade` (solo esta revisión) |

## 7. Pruebas requeridas

- Antes de C1: línea base API (resultado en el informe de la Fase 0.5) y desktop 49/49.
- Tras C5: suite API completa, sin regresiones respecto de la línea base.
- Tras C6: `npm test` y recorrido Electron (rutas, diálogos, asistente).
- Tras C7/F2: `flutter analyze` y `flutter test`.
- Tras R1: `flask db heads` (1 cabeza) y `db upgrade` en una base vacía desechable.
- Tras R2: login, sesiones, firma del técnico contra `SIGOS_DEV`.

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| Commitear evidencias reales | C1 primero; `git add` con rutas explícitas; revisar `git diff --cached --stat` antes de cada commit |
| Commits intermedios (C3–C4) no ejecutables por dependencias cruzadas | Validar al final de C5; no publicar ramas intermedias |
| Conflictos móviles (F2) que pierdan el trabajo del 18/11 | Resolución manual archivo por archivo, sin `--theirs/--ours` global |
| Login roto en `SIGOS_DEV` al reiniciar la API | R2 (o el script SQL del 18/11) antes de reiniciar la API con el código actual |
| Sin remoto: CI y secretos no verificables | Configurar el remoto (decisión del equipo) antes de F1 |

## 9. Rollback

Todas las operaciones son aditivas: un commit se revierte con `git revert`; una fusión con `git revert -m 1`; `git mv`
se revierte con su propio `revert`. No se propone ningún `reset`, `rebase`, `squash` ni `clean`.
