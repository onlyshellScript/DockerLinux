# Introducción — SIGOS 2.0

**Proyecto:** SIGOS 2.0
**Versión del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## 1. Descripción

SIGOS 2.0 es un monorepositorio para la gestión de órdenes de servicio técnico con backend Flask, cliente de escritorio Electron y cliente móvil Flutter, sobre SQL Server.

## 2. Audiencia

Desarrolladores que instalan, ejecutan y extienden el sistema; operadores que despliegan.

## 3. Glosario mínimo

| Término | Definición (fuente) |
|---|---|
| Orden de trabajo | Entidad `WorkOrder` en `services/api/app/workorders/models.py:33` |
| Técnico | Usuario con rol `technician` (`services/api/seed.py`) |
| Evidencia | Archivo/foto/documento/observación asociado a una orden (`services/api/app/evidence/models.py:46`) |

## 4. Navegación de la documentación

Ver `README.md` § Documentación.

## 5. Requisitos previos

Ver `README.md` § Requisitos previos. Comandos verificados localmente contra SQL Server 2022 (localhost:1433).
