# Tutoriales — SIGOS 2.0

**Proyecto:** SIGOS 2.0
**Versión del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## Tutorial 1: Verificar que la API está viva

**Objetivo:** Confirmar instalación correcta.
**Prerrequisitos:** Backend ejecutándose en `localhost:5000`.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod http://localhost:5000/api/v1/health
   ```
**Resultado esperado:** `{"checks":{"application":"UP","database":"UP"},"status":"UP"}`.
**Errores frecuentes:** Puerto ocupado; `DB_URL` incorrecto.

## Tutorial 2: Autenticarse y obtener token

**Objetivo:** Obtener JWT de acceso.
**Prerrequisitos:** Usuario admin existente (seed).
**Pasos:**
1. Ejecutar:
   ```powershell
   $resp = Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/v1/auth/login -ContentType "application/json" -Body '{"username":"admin","password":"Admin123!"}'
   $token = $resp.access_token
   ```
**Resultado esperado:** Objeto con `access_token`, `refresh_token`, `user`.
**Errores frecuentes:** 401 `invalid credentials`.

## Tutorial 3: Crear una orden de trabajo

**Objetivo:** Crear una orden pendiente.
**Prerrequisitos:** Token de admin.
**Pasos:**
1. Ejecutar:
   ```powershell
   $h = @{ Authorization = "Bearer $token" }
   Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/v1/work-orders -Headers $h -ContentType "application/json" -Body '{"title":"Orden de prueba","description":"Prueba doc","priority":"high"}'
   ```
**Resultado esperado:** Orden con `status: "pending"` e `id` asignado.
**Errores frecuentes:** 422 si falta `title`.

## Tutorial 4: Listar órdenes con filtros

**Objetivo:** Consultar órdenes.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:5000/api/v1/work-orders?status=pending&page=1&page_size=10" -Headers $h
   ```
**Resultado esperado:** Objeto con `items`, `total`, `page`.

## Tutorial 5: Consultar catálogo de materiales

**Objetivo:** Listar materiales.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5000/api/v1/materials -Headers $h
   ```
**Resultado esperado:** Lista de materiales con `stock_actual`.

## Tutorial 6: Sincronización offline (pull)

**Objetivo:** Obtener cambios desde servidor.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:5000/api/v1/sync/pull?since=2026-01-01T00:00:00Z" -Headers $h
   ```
**Resultado esperado:** Objeto con datos y `server_time`.
**Errores frecuentes:** 401 si token expirado.
