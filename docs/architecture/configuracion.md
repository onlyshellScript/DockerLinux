# Configuración de la API (Fase 2 · O5)

> Actualizado: 18/11/2026 · Código: `services/api/app/config.py`

## Jerarquía

| Clase | `SIGOS_ENV` | Uso |
|---|---|---|
| `BaseConfig` | — | Lectura única de variables de entorno |
| `DevelopmentConfig` (alias `Config`) | `development` (predeterminado) | `wsgi.py`, desarrollo local |
| `ProductionConfig` (alias `app.config_prod.ProductionConfig`) | `production` | `wsgi_prod.py`, Waitress/Gunicorn |
| `TestingConfig` (alias `TestConfig`) | `testing` | pytest |

- `create_app()` sin argumento elige la clase con `SIGOS_ENV` (`dev`/`prod`/`test` también valen; un valor desconocido falla al arrancar).
- `create_app(Clase)` instancia la clase: **las variables se leen al construir la app, no al importar el módulo**. Una subclase puede fijar un valor con un atributo de clase normal (así lo hace `SqlServerTestConfig` en `tests/conftest.py`).
- Fuera de `TESTING`, faltar `DB_URL` o `JWT_SECRET_KEY` detiene el arranque con `RuntimeError` (antes, `config_prod` lanzaba `KeyError` al importarse).
- `TestingConfig` **no hereda** `DB_URL`, `JWT_SECRET_KEY`, SMTP ni WhatsApp del entorno: SQLite en memoria, secreto fijo y canales sin configurar (ninguna prueba puede enviar notificaciones reales).

## Variables centralizadas

| Grupo | Variables | Predeterminado |
|---|---|---|
| BD / JWT | `DB_URL`, `JWT_SECRET_KEY` | obligatorias fuera de testing |
| Login | `LOGIN_RATE_LIMIT_MAX`, `LOGIN_RATE_LIMIT_WINDOW` | 5, 300 s (se consumirán en O4) |
| Evidencias | `UPLOAD_DIR`, `EVIDENCE_UPLOAD_DIR`, `EVIDENCE_MAX_FILE_SIZE`, `EVIDENCE_ALLOWED_MIME_TYPES`, `EVIDENCE_REQUIRE_TECH_SIGNATURE` | `uploads`, 10 MiB, lista interna, `true` |
| SMTP | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | sin host = canal desactivado; puerto 587; `SMTP_FROM` = `SMTP_USER` |
| WhatsApp | `WHATSAPP_API_URL`, `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | sin URL = canal desactivado |
| Logging | `LOG_LEVEL`, `LOG_FORMAT` | `INFO`; `text` (dev/testing), `json` (production) |

Un entero mal escrito (p. ej. `SMTP_PORT=abc`) produce un `RuntimeError` que nombra la variable.

## Almacenamiento

`UPLOAD_DIR` es siempre absoluto. Prioridad: `EVIDENCE_UPLOAD_DIR` > `UPLOAD_DIR` > `uploads`. Las rutas relativas se resuelven contra `services/api/` (antes, contra el directorio de trabajo del proceso).

- Arranque habitual desde `services/api` y Docker (`WORKDIR /app`, `UPLOAD_DIR=/app/uploads`): **misma ubicación que antes**.
- Producción ya no usa por defecto la ruta fija `/app/uploads`; usa `<raíz API>/uploads`, que en la imagen Docker es la misma carpeta. Así no hay rutas de Ubuntu en el núcleo.
- Si alguien arrancaba la API desde otra carpeta con `UPLOAD_DIR` relativo, los archivos ahora van a `services/api/<ruta>`. Fijar `UPLOAD_DIR` absoluto en ese caso.

## Logging

`create_app` llama a `setup_logging` en todos los entornos (antes solo `wsgi_prod.py`). En testing solo se ajusta el nivel, para no romper la captura de pytest.

## Remitentes de notificaciones

`app/notifications/senders.py` lee SMTP/WhatsApp de `app.config` cuando hay contexto de aplicación y, sin él, de las variables de entorno (comportamiento anterior; el hilo del worker actual no tiene contexto — se corrige en O2).
