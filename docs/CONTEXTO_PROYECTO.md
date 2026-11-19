# Contexto del proyecto SIGOS

> Actualizado: 18/11/2026 · Rama: `fix/panel-admin`

## Fase 2 — Estabilización del núcleo

Orden: O5 → O6 → O1 → O2 → O3 → O4. Línea base de partida (Fase 1, commit `c721aa2`): API 403 aprobadas / 11 omitidas; Desktop 49/49; Flutter análisis limpio, 6/6.

| Objetivo | Estado | Commit | Pruebas API |
|---|---|---|---|
| O5 Configuración unificada | Cerrado | `refactor(config): unify application configuration` | 423 aprobadas / 11 omitidas / 0 fallidas (+20 nuevas en `tests/test_fase2_o5_config.py`) |
| O6 Versión y health | Pendiente | — | — |
| O1 Pool SQLAlchemy | Pendiente | — | — |
| O2 Worker de notificaciones | Pendiente | — | — |
| O3 Concurrencia del Calendario | Pendiente | — | — |
| O4 Límite de login | Pendiente | — | — |

### O5 — resultado
- `BaseConfig` → `DevelopmentConfig` / `ProductionConfig` / `TestingConfig`, seleccionadas con `SIGOS_ENV`. Detalle: [architecture/configuracion.md](architecture/configuracion.md).
- Compatibilidad: `Config`, `TestConfig` y `app.config_prod.ProductionConfig` siguen importables.
- Producción sin `DB_URL` o `JWT_SECRET_KEY` no arranca (`RuntimeError`).
- Testing no hereda BD, JWT, SMTP ni WhatsApp del entorno: no hay envíos reales en pruebas.
- `UPLOAD_DIR` es absoluto (relativas contra `services/api/`).
- `create_app` configura logs; SMTP y WhatsApp se leen de `app.config`.
- No se probaron Desktop ni Flutter: O5 no los toca.
- Pendiente conocido: el hilo del worker no tiene contexto de aplicación y lee SMTP/WhatsApp del entorno. Se corrige en O2.

### Bloqueos que requieren autorización
- Crear `SIGOS_TEST` (pruebas SQL Server y multiproceso).
- Aplicar la migración `IntentosLogin` (O4) sobre `SIGOS_DEV`.
