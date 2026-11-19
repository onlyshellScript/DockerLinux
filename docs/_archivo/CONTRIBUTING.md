# Contribuir — SIGOS 2.0

## Entorno de desarrollo

1. Instalar requisitos (ver `README.md`).
2. Backend: crear venv e instalar dependencias:
   ```powershell
   cd services/api
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
3. Crear BD `sigos` y `sigos_test` (ver `docs/04-calidad-y-despliegue.md`).
4. Ejecutar migraciones y seed.

## Ejecutar pruebas

```powershell
cd services/api
.venv\Scripts\python -m pytest tests/ -v

cd ..\..\apps\desktop
npm test

cd ..\mobile
flutter test
```

Linters: [PENDIENTE: no se detectó configuración de linter en el repo].

## Convención de ramas y commits

[PENDIENTE: inferir del historial; los commits usan prefijos `feat`, `fix`, `docs`, `test`, `chore`, `refactor`].

## Pull requests

- Describir cambios y pruebas ejecutadas.
- Asegurar que CI pasa.
- Actualizar documentación afectada (ver `docs/08-validacion-feedback.md` § Proceso de mantenimiento).
