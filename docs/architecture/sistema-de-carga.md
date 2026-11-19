# Sistema global de carga (MetaballLoader + SigosLoading)

> 18/11/2026 · Escritorio Electron (`apps/desktop/src/renderer`) · Referencia visual: prototipo `index.html` "Metaball 2D Loader"

## 1. Piezas

| Archivo | Responsabilidad |
|---|---|
| `metaball-loader.js` | **MetaballLoader**: única implementación visual. Tres círculos 2D sólidos (`currentColor`), fusión metaball con un filtro SVG compartido (`#sigos-goo`: desenfoque 6.5 + umbral alfa 24/−11), las 6 fases y el ciclo de 2400 ms del prototipo, con *smoothstep*. Un solo `requestAnimationFrame` para todas las instancias; se detiene cuando no queda ninguna en el DOM y se reactiva al insertar una. `prefers-reduced-motion`: círculo fusionado y quieto, con mensaje. |
| `loading.js` | **SigosLoading**: gestor de estados. Operaciones con id, tres modalidades, retraso de aparición, tiempo mínimo visible, salida con transición, `reset()` por sesión, guarda contra doble envío, mensajes por operación. |
| `loader.css` | Estilos de las tres modalidades. Sombra 2D discreta; sin degradados, reflejos ni volumen. |
| `app.js` | Integración: `api()`, `ipcTracked()`, `loaderBlock()`, `trackView()`, `quietRender()`, login, logout y restauración de sesión. |

## 2. Modalidades

| Modalidad | Cuándo | Comportamiento |
|---|---|---|
| **Global** (`mode: 'global'`) | Iniciar y cerrar sesión, restaurar la sesión, mutaciones sin un botón de origen (p. ej. reprogramar arrastrando en el calendario). | Overlay con mensaje. Con `block: true` (por defecto) la app queda `inert`. Si dura más de 60 s pasa a aviso no bloqueante ("está tardando más de lo habitual"): la app nunca queda congelada. |
| **Local** (`mode: 'local'`) | Carga de cada vista; filtros y paginación con datos en pantalla. | Capa sobre el contenedor; el resto de la app sigue usable. Si la vista ya muestra su placeholder no se duplica. |
| **Placeholder** (`SigosLoading.block()` / `loaderBlock()`) | Contenedor que todavía no tiene contenido (vista, tabla, modal, paso del asistente). | Metaball + mensaje en lugar del contenido. Sustituye a todos los esqueletos y textos "Cargando...". |
| **Botón** (`mode: 'button'`) | Cualquier acción de un botón que llama a la API. | Se deshabilita al instante, conserva su ancho y alto, muestra el metaball compacto (mensaje para lectores de pantalla). Los clics o envíos sobre un botón ocupado se cancelan en fase de captura. |

Tiempos por defecto: global aparece a los 350 ms (mínimo visible 380 ms), local a los 250 ms (mínimo 300 ms), botón a los 120 ms (deshabilitado desde el primer instante). Salida: 180 ms. Las operaciones más rápidas que el retraso nunca muestran indicador.

## 3. Uso en módulos nuevos

```js
// 1) Mutaciones: nada que hacer. api('POST'|'PUT'|'PATCH'|'DELETE', ...) muestra el indicador en el botón que
//    originó la acción (o global si no hay botón), con un mensaje según la ruta (SigosLoading.describe).
await api('POST', `/api/v1/material-requests/${id}/approve`, body);

// 2) Mensaje o modalidad explícitos (7.º argumento de api):
await api('POST', '/api/v1/algo', body, null, null, true, { loading: { mode: 'global', message: 'Procesando lote…' } });
await api('POST', '/api/v1/validar', body, null, null, true, { loading: false }); // consulta en segundo plano

// 3) Vista nueva: placeholder inicial + registrar la vista una vez (al final de app.js).
async function renderAlgo(content) {
  content.innerHTML = loaderBlock('Consultando algo…', 240);
  const res = await api('GET', '/api/v1/algo');
  if (!content.isConnected) return; // el usuario cambió de módulo
  /* pintar */
}
renderAlgo = trackView(renderAlgo, 'Consultando algo…');

// 4) Archivos por IPC (subida, descarga, exportación):
await ipcTracked('uploadFile', payload, { message: 'Procesando evidencia…' });

// 5) Cualquier otra operación asíncrona, siempre cerrada con try/finally:
await SigosLoading.run({ mode: 'local', target: el, message: 'Calculando…' }, () => trabajo());
await SigosLoading.button(btn, () => trabajo(), 'Guardando cambios…');
const id = SigosLoading.start({ message: 'Generando documento PDF…' });
try { /* … */ } finally { SigosLoading.end(id); }
```

Reglas: mensajes que describen la operación real; nunca porcentajes; no crear otro spinner ni copiar la animación.

## 4. Sesiones

- `endSession()` (logout o expiración) llama a `SigosLoading.reset()`: termina todas las operaciones, quita overlays, restaura botones, levanta el bloqueo y avanza `epoch`; luego muestra "Cerrando sesión…" hasta que el renderer se recarga desde cero.
- `api()` y `downloadAuthed()` descartan (`aborted: true`) cualquier respuesta que llegue después de un cambio de sesión: una petición del usuario anterior nunca actualiza la interfaz del siguiente.
- Las peticiones en curso del proceso principal no se pueden abortar (IPC sin `AbortController`); se descartan al llegar y la recarga del renderer elimina su contexto.
- El indicador no sustituye ninguna validación: los permisos se siguen validando en la API en cada petición.

## 5. Inventario de integraciones

| Área | Operación | Modalidad · mensaje |
|---|---|---|
| Autenticación | Iniciar sesión | Global bloqueante · "Iniciando sesión…" |
| | Restaurar sesión al abrir la app | Global · "Recuperando sesión…" |
| | Cerrar sesión / sesión expirada / cambio de usuario | `reset()` + global · "Cerrando sesión…" |
| | Cambiar contraseña | Botón · "Actualizando contraseña…" |
| Dashboard | Carga y actualización (filtros de rango, zona, técnico) | Placeholder + local · "Cargando indicadores del dashboard…" |
| Órdenes | Listado, filtros, pestañas, paginación | Placeholder + local · "Consultando órdenes…" |
| | Detalle, materiales y evidencias de la orden | Placeholders · "Cargando detalle de la orden…", "Consultando materiales/evidencias de la orden…" |
| | Crear, editar, reprogramar, cambiar estado, cancelar, observación, consumo de material, subir archivo | Botón · "Creando orden…", "Actualizando orden…", "Programando visita…", "Cambiando estado de la orden…", "Registrando movimiento de inventario…", "Procesando evidencia…" |
| Calendario | Carga de agenda e historial | Placeholder + local · "Cargando agenda…", "Cargando historial de la visita…" |
| | Reprogramar por arrastre, deshacer | Global no bloqueante tras el retraso · "Programando visita…" |
| | Cancelar visita desde el menú | Botón · "Cambiando estado de la orden…" |
| Solicitudes | Listado y filtros | Placeholder + local · "Consultando solicitudes…" |
| | Enviar, aprobar, rechazar, entregar, cancelar | Botón · mensaje de cada acción |
| Técnicos | Listado | Placeholder + local · "Cargando información de técnicos…" |
| | Crear y editar | Botón · "Guardando técnico…" |
| Materiales | Inventario, búsqueda, filtros | Placeholder + local · "Consultando inventario…" |
| | Alta de catálogo, edición, desactivar, reposición, ajuste | Botón · "Guardando material…", "Actualizando material…", "Registrando movimiento de inventario…" |
| | Vista previa y descarga de exportación | Placeholder · "Preparando vista previa…"; botón · "Generando documento PDF…" / "Preparando archivo XLSX…" / "Exportando información…" |
| Evidencias | Listado por orden y filtros | Placeholder + local · "Consultando evidencias…" |
| | Evidencias de una orden | Placeholder · "Cargando evidencias de la orden…" |
| | Adjuntar archivo u observación | Botón · "Procesando evidencia…" / "Registrando observación…" |
| | Firma del técnico, firma y negativa del cliente, checklist, enviar y reenviar expediente | Botón · "Guardando firma…", "Guardando firma del cliente…", "Guardando actividad…", "Enviando expediente a revisión…", "Reenviando expediente…" |
| | Ver registro (imagen y firma bajo demanda), Mi firma | Placeholders · "Cargando archivo…", "Cargando firma…", "Consultando su firma registrada…" |
| | Bandeja y expediente de revisión; iniciar revisión, corregir, aprobar, rechazar | Placeholder + local · "Cargando bandeja de evidencias…", "Cargando expediente…"; botón · "Actualizando expediente…" |
| Administración | Usuarios: listado, detalle, crear, editar, rol, estado, restablecer contraseña | Placeholders · "Consultando usuarios…", "Cargando información del usuario…"; botón · "Creando usuario…", "Actualizando usuario…", "Restableciendo contraseña…" |
| | Configuración: carga, validación de impacto, guardado | Placeholder · "Cargando configuración…"; botón · "Validando el impacto de los cambios…", "Guardando configuración…" |
| Reportes | Carga y consulta | Placeholder + local · "Preparando reportes…", "Consultando datos del reporte…" |
| Exportaciones (asistente) | Plantillas, opciones, vista previa | Placeholders · "Cargando plantillas de exportación…", "Preparando opciones de exportación…", "Consultando información para la vista previa…" |
| | Generar PDF / XLSX | Placeholder en el asistente · "Generando documento PDF…" / "Preparando archivo XLSX…" |
| Notificaciones | Listado | Placeholder · "Cargando notificaciones…" |

## 6. Operaciones sin indicador, a propósito

| Operación | Motivo |
|---|---|
| `POST /calendar/validate` (formulario de programación y arrastre) | Validación en vivo mientras se escribe o arrastra; un indicador interrumpiría el gesto. Su resultado ya se muestra en línea. |
| `POST /exports/preview` | El paso del asistente ya muestra su placeholder; evitar duplicado. |
| `POST /auth/refresh` | Renovación transparente del token dentro de otra operación que ya tiene indicador. |
| Refresco automático de la agenda (cada 45 s) y fin del resaltado de un evento | `quietRender()`: refrescos no solicitados por el usuario. |
| Generación de PDF/XLSX: tiempo con el diálogo nativo de guardado abierto | El asistente cierra el indicador antes de abrir el diálogo. En la descarga de inventario (`exportDownload`) la petición y el diálogo ocurren en el mismo IPC del proceso principal, así que el botón sigue ocupado mientras el diálogo está abierto. |
| App móvil (Flutter) | Otra tecnología: integrar el metaball exigiría una segunda implementación (CustomPainter). Fuera del alcance de esta entrega. |
| `sigos_flask/` | Prototipo independiente que no forma parte de la aplicación desplegada. |

## 7. Pruebas

- `apps/desktop/tests/loading.test.js` (14 casos, jsdom): fases del metaball (inicio y fin fusionados, separación, cruce), un solo filtro compartido, ciclo que se detiene sin instancias y con movimiento reducido, operaciones simultáneas, anti-parpadeo, bloqueo y paso a no bloqueante, mínimo visible y salida, cierre en error (`run`), botón (deshabilitado al instante, tamaño, doble envío, restauración), contenedor local sin duplicados ni huérfanos, `reset()` de sesión, mensajes.
- E2E en Electron real contra la API (35 comprobaciones), con latencias y errores simulados: login lento (overlay bloqueante), vista lenta, cambio de módulo durante carga, exportación PDF y XLSX (archivo escrito), logout durante una carga lenta, cambio de usuario y login rápido sin parpadeo, firma con doble clic (una sola petición), adjuntar evidencia (el botón no cambia de tamaño), filtro con capa local, error del servidor, operaciones simultáneas, error de conexión, sin errores JS, ciclo de animación detenido al final. Tras cada escenario se comprueba que no quedan operaciones activas, overlays, capas, botones ocupados ni bloqueo.
