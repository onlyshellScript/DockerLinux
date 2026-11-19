# Guía de desarrollo y pruebas

> Actualizado: 17/11/2026

## 1. Arranque local

**API** (`services/api`):

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
flask --app wsgi run --port 5000                     # http://localhost:5000/api/v1/health
```

- `services/api/.env` (no versionado): `DB_URL`, `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, opcionalmente `TECH_INITIAL_PASSWORD`.
- `flask db upgrade` **no funciona** hasta corregir la cadena de migraciones (ver `docs/database/esquema-espanol-y-orm.md` §4).
  Una base ya creada (p. ej. `SIGOS_DEV`) funciona sin migrar.
- Flask sin `--debug` no recarga el código: reiniciar la API después de cambiar Python.

**Desktop** (`apps/desktop`):

```bash
npm install
npm start                                            # Electron; API en SIGOS_API_BASE_URL o http://localhost:5000
```

Preferencias de interfaz: `%APPDATA%\sigos-desktop\sigos-ui-prefs.json`. Sesión cifrada: `sigos-session.bin` en la misma carpeta.

## 2. Estructura del renderer

| Archivo | Contenido |
|---|---|
| `index.html` | CSP (`img-src 'self' data: blob:`), orden de carga de scripts y estilos |
| `sigos.css`, `app-sigos.css` | Estilos base históricos |
| `design-system.css` | Tokens y componentes (fuente de verdad visual) |
| `ui-components.js` | `sigosModal`, `confirmDialog`, `askText` |
| `export-wizard.js` | `openExportWizard` |
| `evidence_admin.js` | Bandeja y expediente de evidencias |
| `app.js` | Shell, navegación y vistas de cada módulo |

Reglas:

- Usar los componentes compartidos; no `window.confirm`, no modales propios.
- Colores con tokens (`var(--c-*)`); color semántico solo para estados que requieren atención.
- Toda vista `async function renderX(content)` debe comprobar `if (!content.isConnected) return;` tras cada `await` de
  nivel superior (el usuario puede haber cambiado de pantalla).
- Todo control de formulario con `<label for>` o `aria-label`.

## 3. Pruebas

| Suite | Comando | Estado 17/11/2026 |
|---|---|---|
| API | `cd services/api && python -m pytest tests -q` | ver resumen en `docs/revision-2026-11-17.md` |
| Desktop (unitarias) | `cd apps/desktop && npm test` | 35/35 |
| Visual existente | `cd apps/desktop && node tests/visual/validate.js` | 5 tamaños sin desbordamientos ni solapamientos |

Suites relevantes de la API:

- `test_exports.py` — 18 plantillas × 2 formatos, tipos XLSX, inyección de fórmulas, vista previa vs. generación,
  vacíos, volumen (1 200 órdenes), permisos, auditoría.
- `test_users_admin.py` — CRUD, duplicados, protecciones de admin, restablecimiento, roles leídos de la base.
- `test_settings_operations.py` — validaciones de Operación, control de versión, simulacro de impacto.
- `test_rnf05_access_rules.py` — matriz de acceso: **toda ruta nueva debe declararse aquí**.

Notas:

- SQLite (tests) guarda fechas sin zona; SQL Server (`DATETIMEOFFSET`) sí. Escribir aserciones válidas para ambos.
- El SQL manual de `_lock_row` solo corre en SQL Server; verificarlo contra una base real al cambiar nombres de tablas.

## 4. Verificación visual (Playwright sobre Electron)

Durante el rediseño se usaron scripts que lanzan la app real con `playwright._electron`:
recorrido de rutas (escritorio/minimizado/móvil), auditoría de accesibilidad (etiquetas, nombres, `alt`, contraste
AA, objetivos táctiles, desbordamiento a 1440/820/390 px), diálogos, teclado, Configuración, Bandeja de evidencias,
asistente de exportación (sustituyendo `dialog.showSaveDialog` en el proceso principal) y navegación rápida.
Se recomienda incorporarlos a `apps/desktop/tests/visual/` (ver pendientes).

Para revisar PDFs generados se renderizaron a PNG con `pypdfium2` instalado en una carpeta temporal (no es dependencia del proyecto).

## 5. Convenciones de API

- Errores de validación: `422 {error, code, field}`; conflictos: `409 {error, code}`.
- Rutas nuevas: decorar con `require_role`/`require_auth`, declarar en la matriz de acceso y cubrir con tests.
- Auditoría: `AuditoriaEventos` para cuentas de usuario; `Auditoria` (`settings.service.audit`) para configuración y exportaciones.
