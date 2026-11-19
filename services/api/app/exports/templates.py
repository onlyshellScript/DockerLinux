"""Plantillas de exportacion declarativas.

Cada plantilla define identificador, nombre, descripcion, modulo, formatos, columnas (con tipo y orden),
filtros admitidos, ordenamientos, resumen, configuracion visual y version. No contiene logica de datos:
la fuente (`source`) se resuelve en sources.py.
"""
from dataclasses import dataclass, field

# Tipos de columna: text, int, number, money, percent, date, datetime
@dataclass(frozen=True)
class Column:
    key: str
    label: str
    type: str = "text"
    width: float = 1.0          # peso relativo para PDF y ancho base para XLSX
    default: bool = True        # incluida por defecto
    align: str = None           # left|right|center (por defecto segun tipo)


@dataclass(frozen=True)
class Filter:
    key: str
    label: str
    type: str                   # date | select | text | number
    options: tuple = ()         # para select: ((valor, etiqueta), ...)
    source: str = None          # opciones dinamicas: technicians | zones | categories


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    module: str
    source: str
    columns: tuple
    formats: tuple = ("pdf", "xlsx")
    filters: tuple = ()
    sorts: tuple = ()           # ((clave_columna, etiqueta), ...)
    default_sort: str = None
    default_order: str = "asc"
    summary: str = None         # nombre del resumen en sources.SUMMARIES
    group_by: str = None        # agrupacion visual (PDF) y hoja por grupo (no se usa en XLSX)
    orientation: str = "auto"   # auto | portrait | landscape
    fixed_filters: dict = field(default_factory=dict)  # filtros impuestos por la plantilla
    allow_columns: bool = True
    roles: tuple = ("admin", "dispatcher")
    version: str = "1.0"


MODULE_LABELS = {
    "materials": "Materiales", "orders": "Órdenes", "technicians": "Técnicos", "requests": "Solicitudes",
    "evidence": "Evidencias", "reports": "Reportes", "users": "Usuarios",
}

ORDER_STATUS = (("pending", "Pendiente"), ("assigned", "Programada"), ("in_progress", "En proceso"),
                ("completed", "Completada"), ("closed", "Cerrada"), ("cancelled", "Cancelada"))
PRIORITY = (("high", "Alta"), ("medium", "Media"), ("low", "Baja"))
REQUEST_STATUS = (("DRAFT", "Borrador"), ("SUBMITTED", "Enviada"), ("APPROVED", "Aprobada"),
                  ("PARTIALLY_APPROVED", "Aprobada parcialmente"), ("REJECTED", "Rechazada"),
                  ("PARTIALLY_DELIVERED", "Entregada parcialmente"), ("DELIVERED", "Entregada"), ("CANCELLED", "Cancelada"))
STOCK_STATUS = (("ok", "Normal"), ("low", "Bajo"), ("critical", "Crítico"))
EVIDENCE_STATUS = (("DRAFT", "Borrador"), ("SUBMITTED", "Enviado"), ("UNDER_REVIEW", "En revisión"),
                   ("CORRECTION_REQUIRED", "Requiere corrección"), ("RESUBMITTED", "Reenviado"),
                   ("APPROVED", "Aprobado"), ("REJECTED", "Rechazado"))
EVIDENCE_CATEGORY = (("BEFORE", "Antes"), ("DURING", "Durante"), ("AFTER", "Después"), ("ADDITIONAL", "Adicional"))
ROLE = (("admin", "Administrador"), ("dispatcher", "Coordinador"), ("technician", "Técnico"))
ACCOUNT_STATUS = (("active", "Activa"), ("inactive", "Inactiva"))

F_FROM = Filter("date_from", "Desde", "date")
F_TO = Filter("date_to", "Hasta", "date")
F_TECH = Filter("technician_id", "Técnico", "select", source="technicians")
F_ZONE = Filter("zone", "Zona", "text")

# ---------------- Columnas reutilizables ----------------
C_MAT = (
    Column("code", "Código", "text", 0.9), Column("name", "Material", "text", 2.2), Column("category", "Categoría", "text", 1.3),
    Column("unit", "Unidad", "text", 0.7), Column("stock", "Stock", "number", 0.8), Column("min_stock", "Mínimo", "number", 0.8),
    Column("level", "Nivel", "percent", 0.7, default=False), Column("status", "Estado", "text", 0.8),
)
C_ORDER = (
    Column("code", "Orden", "text", 0.8), Column("title", "Título", "text", 2.0), Column("customer", "Cliente", "text", 1.5),
    Column("address", "Dirección", "text", 1.6, default=False), Column("zone", "Zona", "text", 0.9),
    Column("installation_type", "Tipo", "text", 1.0, default=False), Column("technician", "Técnico", "text", 1.1),
    Column("status", "Estado", "text", 0.9), Column("priority", "Prioridad", "text", 0.7),
    Column("created_at", "Creada", "datetime", 1.1), Column("scheduled_at", "Programada", "datetime", 1.1, default=False),
    Column("completed_at", "Completada", "datetime", 1.1, default=False),
)

TEMPLATES = [
    # ---------------- MATERIALES ----------------
    Template("materials.inventory", "Inventario general", "Existencias actuales de todos los materiales activos.", "materials", "materials",
             C_MAT, filters=(Filter("status", "Estado de stock", "select", STOCK_STATUS), Filter("category", "Categoría", "select", source="categories"),
                             Filter("q", "Buscar", "text")),
             sorts=(("name", "Material"), ("code", "Código"), ("stock", "Stock"), ("category", "Categoría")), default_sort="name",
             summary="materials"),
    Template("materials.valued", "Inventario valorizado", "Existencias con precio unitario y valor total del inventario.", "materials", "materials",
             C_MAT[:6] + (Column("unit_price", "Precio unitario", "money", 1.0), Column("value", "Valor total", "money", 1.1), C_MAT[7]),
             filters=(Filter("category", "Categoría", "select", source="categories"), Filter("q", "Buscar", "text")),
             sorts=(("value", "Valor total"), ("name", "Material"), ("code", "Código")), default_sort="value", default_order="desc",
             summary="materials_valued", orientation="landscape"),
    Template("materials.critical", "Existencias críticas", "Materiales con stock bajo o crítico frente a su mínimo.", "materials", "materials",
             C_MAT[:6] + (Column("shortage", "Faltante", "number", 0.8), Column("level", "Nivel", "percent", 0.7), C_MAT[7]),
             filters=(Filter("category", "Categoría", "select", source="categories"),),
             sorts=(("level", "Nivel"), ("shortage", "Faltante"), ("name", "Material")), default_sort="level",
             summary="materials", fixed_filters={"status_in": ("low", "critical")}),

    # ---------------- ÓRDENES ----------------
    Template("orders.general", "Órdenes generales", "Listado de órdenes de servicio con su estado y responsable.", "orders", "orders",
             C_ORDER, filters=(Filter("status", "Estado", "select", ORDER_STATUS), F_TECH, F_ZONE, F_FROM, F_TO),
             sorts=(("created_at", "Fecha de creación"), ("code", "Orden"), ("status", "Estado"), ("priority", "Prioridad")),
             default_sort="created_at", default_order="desc", summary="orders", orientation="landscape"),
    Template("orders.by_status", "Órdenes por estado", "Órdenes agrupadas por estado, con totales por grupo.", "orders", "orders",
             C_ORDER, filters=(F_TECH, F_ZONE, F_FROM, F_TO), sorts=(("created_at", "Fecha de creación"), ("priority", "Prioridad")),
             default_sort="created_at", default_order="desc", summary="orders", group_by="status", orientation="landscape"),
    Template("orders.by_period", "Órdenes por período", "Órdenes creadas o programadas en un período, con resumen diario.", "orders", "orders",
             C_ORDER, filters=(F_FROM, F_TO, Filter("date_field", "Fecha de referencia", "select", (("created_at", "Creación"), ("scheduled_at", "Programación"))),
                               Filter("status", "Estado", "select", ORDER_STATUS), F_TECH),
             sorts=(("created_at", "Fecha de creación"), ("scheduled_at", "Fecha programada")), default_sort="created_at",
             summary="orders_period", orientation="landscape"),

    # ---------------- TÉCNICOS ----------------
    Template("technicians.directory", "Directorio de técnicos", "Datos de contacto, especialidad y disponibilidad.", "technicians", "technicians",
             (Column("name", "Nombre", "text", 1.6), Column("username", "Usuario", "text", 1.0), Column("document", "Documento", "text", 1.0),
              Column("phone", "Teléfono", "text", 1.0), Column("email", "Correo", "text", 1.7), Column("specialty", "Especialidad", "text", 1.2),
              Column("zones", "Zonas", "text", 1.5), Column("available", "Disponible", "text", 0.8), Column("active", "Activo", "text", 0.7, default=False)),
             filters=(Filter("availability", "Disponibilidad", "select", (("available", "Disponibles"), ("unavailable", "No disponibles"))),),
             sorts=(("name", "Nombre"), ("specialty", "Especialidad")), default_sort="name", summary="technicians", orientation="landscape"),
    Template("technicians.assignments", "Asignaciones", "Carga de trabajo actual por técnico según sus órdenes.", "technicians", "technician_assignments",
             (Column("name", "Técnico", "text", 1.6), Column("pending", "Pendientes", "int", 0.8), Column("assigned", "Programadas", "int", 0.8),
              Column("in_progress", "En proceso", "int", 0.8), Column("open_total", "Abiertas", "int", 0.8), Column("completed", "Completadas", "int", 0.8),
              Column("available", "Disponible", "text", 0.8)),
             filters=(F_FROM, F_TO), sorts=(("open_total", "Órdenes abiertas"), ("name", "Técnico")), default_sort="open_total", default_order="desc",
             summary="technician_assignments", allow_columns=False),
    Template("technicians.activity", "Actividad de técnicos", "Cambios de estado registrados por cada técnico en el período.", "technicians", "technician_activity",
             (Column("name", "Técnico", "text", 1.6), Column("changes", "Cambios de estado", "int", 0.9), Column("started", "Iniciadas", "int", 0.8),
              Column("completed", "Completadas", "int", 0.8), Column("orders", "Órdenes distintas", "int", 0.9), Column("last_activity", "Última actividad", "datetime", 1.2)),
             filters=(F_FROM, F_TO), sorts=(("changes", "Cambios"), ("completed", "Completadas"), ("name", "Técnico")), default_sort="changes", default_order="desc",
             summary="technician_activity", allow_columns=False),

    # ---------------- SOLICITUDES ----------------
    Template("requests.general", "Solicitudes generales", "Solicitudes de materiales con cantidades solicitadas, aprobadas y entregadas.", "requests", "requests",
             (Column("code", "Solicitud", "text", 0.8), Column("order", "Orden", "text", 0.8), Column("requester", "Solicitante", "text", 1.1),
              Column("technician", "Técnico", "text", 1.1), Column("status", "Estado", "text", 1.2), Column("items", "Ítems", "int", 0.5),
              Column("requested", "Solicitado", "number", 0.8), Column("approved", "Aprobado", "number", 0.8), Column("delivered", "Entregado", "number", 0.8),
              Column("reason", "Motivo", "text", 1.6, default=False), Column("created_at", "Fecha", "datetime", 1.1)),
             filters=(Filter("status", "Estado", "select", REQUEST_STATUS), F_FROM, F_TO),
             sorts=(("created_at", "Fecha"), ("status", "Estado")), default_sort="created_at", default_order="desc",
             summary="requests", orientation="landscape"),
    Template("requests.pending", "Solicitudes pendientes", "Solicitudes que aún no se han atendido por completo.", "requests", "requests",
             (Column("code", "Solicitud", "text", 0.8), Column("order", "Orden", "text", 0.8), Column("technician", "Técnico", "text", 1.2),
              Column("status", "Estado", "text", 1.3), Column("requested", "Solicitado", "number", 0.8), Column("approved", "Aprobado", "number", 0.8),
              Column("pending_qty", "Por entregar", "number", 0.9), Column("created_at", "Fecha", "datetime", 1.1), Column("age_days", "Días abiertos", "int", 0.8)),
             filters=(F_FROM, F_TO), sorts=(("age_days", "Antigüedad"), ("created_at", "Fecha")), default_sort="age_days", default_order="desc",
             summary="requests", fixed_filters={"status_in": ("DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_APPROVED", "PARTIALLY_DELIVERED")}),
    Template("requests.attended", "Solicitudes atendidas", "Solicitudes entregadas, rechazadas o canceladas.", "requests", "requests",
             (Column("code", "Solicitud", "text", 0.8), Column("order", "Orden", "text", 0.8), Column("technician", "Técnico", "text", 1.2),
              Column("status", "Resultado", "text", 1.1), Column("requested", "Solicitado", "number", 0.8), Column("delivered", "Entregado", "number", 0.8),
              Column("fulfillment", "Cumplimiento", "percent", 0.9), Column("approval_reason", "Observación", "text", 1.6, default=False),
              Column("created_at", "Fecha", "datetime", 1.1)),
             filters=(F_FROM, F_TO), sorts=(("created_at", "Fecha"), ("fulfillment", "Cumplimiento")), default_sort="created_at", default_order="desc",
             summary="requests", fixed_filters={"status_in": ("DELIVERED", "REJECTED", "CANCELLED")}),

    # ---------------- EVIDENCIAS ----------------
    Template("evidence.relation", "Relación de evidencias", "Archivos de evidencia recibidos, con su orden y estado.", "evidence", "evidence",
             (Column("order", "Orden", "text", 0.8), Column("customer", "Cliente", "text", 1.3), Column("category", "Momento", "text", 0.8),
              Column("file", "Archivo", "text", 1.8), Column("description", "Descripción", "text", 1.6, default=False), Column("size_kb", "Tamaño (KB)", "number", 0.8),
              Column("status", "Estado", "text", 1.0), Column("uploaded_by", "Subido por", "text", 1.0), Column("received_at", "Recibida", "datetime", 1.1)),
             filters=(Filter("status", "Estado", "select", EVIDENCE_STATUS), Filter("category", "Momento", "select", EVIDENCE_CATEGORY), F_FROM, F_TO),
             sorts=(("received_at", "Fecha de recepción"), ("order", "Orden")), default_sort="received_at", default_order="desc",
             summary="evidence", orientation="landscape"),
    Template("evidence.by_order", "Evidencias por orden", "Expediente consolidado por orden: evidencias, firma y estado.", "evidence", "evidence_by_order",
             (Column("order", "Orden", "text", 0.8), Column("customer", "Cliente", "text", 1.4), Column("technician", "Técnico", "text", 1.1),
              Column("files", "Evidencias", "int", 0.7), Column("before", "Antes", "int", 0.6), Column("during", "Durante", "int", 0.6),
              Column("after", "Después", "int", 0.6), Column("signature", "Firma", "text", 0.9), Column("status", "Expediente", "text", 1.1),
              Column("last_received", "Última recepción", "datetime", 1.1)),
             filters=(Filter("status", "Estado del expediente", "select", EVIDENCE_STATUS), F_FROM, F_TO),
             sorts=(("last_received", "Última recepción"), ("files", "Evidencias")), default_sort="last_received", default_order="desc",
             summary="evidence_by_order", orientation="landscape", allow_columns=False),

    # ---------------- REPORTES ----------------
    Template("reports.kpis", "Resumen de indicadores", "Indicadores principales del período del Dashboard.", "reports", "kpis",
             (Column("indicator", "Indicador", "text", 2.2), Column("value", "Valor", "text", 1.0), Column("delta", "Variación vs. período anterior", "percent", 1.3)),
             filters=(Filter("range", "Período", "select", (("7", "Últimos 7 días"), ("14", "Últimos 14 días"), ("30", "Últimos 30 días"))),),
             summary="kpis", orientation="portrait", allow_columns=False),
    Template("reports.operations", "Estadísticas operativas", "Distribución de órdenes por estado, prioridad, zona y tipo de instalación.", "reports", "operations",
             (Column("dimension", "Dimensión", "text", 1.2), Column("category", "Categoría", "text", 1.8), Column("count", "Órdenes", "int", 0.8),
              Column("share", "Participación", "percent", 0.9)),
             filters=(Filter("range", "Período", "select", (("7", "Últimos 7 días"), ("14", "Últimos 14 días"), ("30", "Últimos 30 días"))),),
             summary="operations", group_by="dimension", orientation="portrait", allow_columns=False),

    # ---------------- USUARIOS ----------------
    Template("users.directory", "Directorio de usuarios", "Cuentas del sistema con rol, estado y último acceso.", "users", "users",
             (Column("username", "Usuario", "text", 1.2), Column("email", "Correo", "text", 1.9), Column("roles", "Rol", "text", 1.1),
              Column("status", "Estado", "text", 0.8), Column("must_change", "Cambio de contraseña pendiente", "text", 1.0, default=False),
              Column("created_at", "Creado", "datetime", 1.1), Column("last_login", "Último acceso", "datetime", 1.1)),
             filters=(Filter("role", "Rol", "select", ROLE), Filter("status", "Estado", "select", ACCOUNT_STATUS)),
             sorts=(("username", "Usuario"), ("last_login", "Último acceso")), default_sort="username",
             summary="users", roles=("admin",)),
    Template("users.roles", "Distribución de roles y estados", "Cantidad de cuentas por rol y estado.", "users", "users_roles",
             (Column("role", "Rol", "text", 1.4), Column("active", "Activas", "int", 0.8), Column("inactive", "Inactivas", "int", 0.8),
              Column("total", "Total", "int", 0.8), Column("share", "Participación", "percent", 0.9)),
             summary="users", roles=("admin",), orientation="portrait", allow_columns=False),
]

BY_ID = {t.id: t for t in TEMPLATES}


def get_template(template_id):
    return BY_ID.get(template_id)


def list_templates(module=None, fmt=None, roles=()):
    out = []
    for t in TEMPLATES:
        if module and t.module != module:
            continue
        if fmt and fmt not in t.formats:
            continue
        if roles is not None and not any(r in t.roles for r in roles):
            continue
        out.append(t)
    return out


def template_to_dict(t):
    return {
        "id": t.id, "name": t.name, "description": t.description, "module": t.module, "module_label": MODULE_LABELS.get(t.module, t.module),
        "formats": list(t.formats), "version": t.version, "allow_columns": t.allow_columns,
        "columns": [{"key": c.key, "label": c.label, "type": c.type, "default": c.default} for c in t.columns],
        "filters": [{"key": f.key, "label": f.label, "type": f.type, "options": [{"value": v, "label": l} for v, l in f.options], "source": f.source} for f in t.filters],
        "sorts": [{"key": k, "label": l} for k, l in t.sorts], "default_sort": t.default_sort, "default_order": t.default_order,
        "grouped": bool(t.group_by),
    }
