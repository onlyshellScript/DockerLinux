# -*- coding: utf-8 -*-
from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db
from app.common.normalize import normalize_upper

MOVEMENT_IN = "IN"
MOVEMENT_OUT = "OUT"
MOVEMENT_CONSUMPTION = "CONSUMPTION"
MOVEMENT_ADJUSTMENT = "ADJUSTMENT"
MOVEMENT_RETURN = "RETURN"
MOVEMENT_TRANSFER_OUT = "TRANSFER_OUT"

ALL_MOVEMENTS = [MOVEMENT_IN, MOVEMENT_OUT, MOVEMENT_CONSUMPTION, MOVEMENT_ADJUSTMENT, MOVEMENT_RETURN]


# Material: modelo de base de datos que representa la entidad Material.
class Material(db.Model):
    __tablename__ = "Materiales"

    id = db.Column("IdMaterial", db.Integer, primary_key=True)
    name = db.Column("Nombre", db.String(120), nullable=False, index=True)
    code = db.Column("Codigo", db.String(40), unique=True, index=True)
    description = db.Column("Descripcion", db.String(250))
    unit = db.Column("Unidad", db.String(20), nullable=False)
    current_stock = db.Column("StockActual", db.Float, nullable=False, default=0)
    min_stock = db.Column("StockMinimo", db.Float, nullable=False, default=0)
    unit_price = db.Column("PrecioUnitario", db.Numeric(18, 2), nullable=False, default=0)
    is_active = db.Column("EstaActivo", db.Boolean, nullable=False, default=True)
    catalog_item_id = db.Column("IdItemCatalogo", db.Integer, db.ForeignKey("CatalogoMateriales.IdItemCatalogo", ondelete="NO ACTION"), unique=True, index=True)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column("ActualizadoEn", 
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    catalog_item = db.relationship("MaterialCatalog")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "catalog_item_id": self.catalog_item_id,
            "category": (self.catalog_item.category.name if getattr(self, "catalog_item", None) and self.catalog_item.category else ("Sin catalogo" if self.catalog_item_id is None else None)),
            "catalog_name": (self.catalog_item.name if getattr(self, "catalog_item", None) else None),
            "description": self.description,
            "unit": self.unit,
            "current_stock": self.current_stock,
            "min_stock": self.min_stock,
            "unit_price": self.unit_price,
            "is_active": self.is_active,
        }



    # Textos del módulo de materiales siempre en MAYÚSCULAS, sin importar quién escriba (rutas, servicios, semillas).
    @sa.orm.validates('name', 'description', 'unit')
    def _upper_text(self, key, value):
        return normalize_upper(value)

# StockMovement: modelo de base de datos que representa la entidad StockMovement.
class StockMovement(db.Model):
    __tablename__ = "MovimientosStock"

    id = db.Column("IdMovimiento", db.Integer, primary_key=True)
    material_id = db.Column("IdMaterial", db.Integer, db.ForeignKey("Materiales.IdMaterial"), nullable=False, index=True)
    quantity = db.Column("Cantidad", db.Float, nullable=False, default=0)
    quantity_requested = db.Column("CantidadSolicitada", db.Float, nullable=False, default=0)
    quantity_approved = db.Column("CantidadAprobada", db.Float, nullable=False, default=0, server_default=sa.text("0"))
    quantity_delivered = db.Column("CantidadEntregada", db.Float, nullable=False, default=0, server_default=sa.text("0"))
    movement_type = db.Column("TipoMovimiento", db.String(15), nullable=False)
    work_order_id = db.Column("IdOrden", db.Integer, db.ForeignKey("OrdenesTrabajo.IdOrden"))
    user_id = db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), nullable=False)
    notes = db.Column("Notas", db.String(250))
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    material = db.relationship("Material")
    user = db.relationship("User")
    work_order = db.relationship("WorkOrder")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "material": self.material.to_dict() if self.material else None,
            "quantity": self.quantity,
            "movement_type": self.movement_type,
            "work_order_id": self.work_order_id,
            "user": self.user.to_dict() if self.user else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }



    # Textos del módulo de materiales siempre en MAYÚSCULAS, sin importar quién escriba (rutas, servicios, semillas).
    @sa.orm.validates('notes')
    def _upper_text(self, key, value):
        return normalize_upper(value)

# TechnicianStock: modelo de base de datos que representa la entidad TechnicianStock.
class TechnicianStock(db.Model):
    __tablename__ = "StockTecnico"

    id = db.Column("IdStockTecnico", db.Integer, primary_key=True)
    technician_id = db.Column("IdTecnico", db.Integer, db.ForeignKey("PerfilesTecnico.IdPerfil", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column("IdMaterial", db.Integer, db.ForeignKey("Materiales.IdMaterial", ondelete="CASCADE"), nullable=False, index=True)
    quantity = db.Column("Cantidad", db.Float, nullable=False, default=0)
    updated_at = db.Column("ActualizadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    technician = db.relationship("TechnicianProfile")
    material = db.relationship("Material")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "technician_id": self.technician_id,
            "material_id": self.material_id,
            "material": self.material.to_dict() if self.material else None,
            "quantity": self.quantity,
        }


# MaterialRequest: modelo de base de datos que representa la entidad MaterialRequest.
class MaterialRequest(db.Model):
    __tablename__ = "SolicitudesMaterial"

    id = db.Column("IdSolicitud", db.Integer, primary_key=True)
    requester_id = db.Column("IdSolicitante", db.Integer, db.ForeignKey("Usuarios.IdUsuario", ondelete="NO ACTION"), nullable=False, index=True)
    technician_id = db.Column("IdTecnico", db.Integer, db.ForeignKey("PerfilesTecnico.IdPerfil", ondelete="NO ACTION"), nullable=True, index=True)
    work_order_id = db.Column("IdOrden", db.Integer, db.ForeignKey("OrdenesTrabajo.IdOrden", ondelete="NO ACTION"), nullable=True, index=True)
    status = db.Column("Estado", db.String(30), nullable=False, default="SUBMITTED")
    client_operation_id = db.Column("IdOperacionCliente", db.String(36), unique=True, index=True)
    delivered_by_id = db.Column("IdEntregadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario", ondelete="NO ACTION"))
    reason = db.Column("Motivo", db.Text)
    approved_by_id = db.Column("IdAprobadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario", ondelete="NO ACTION"), nullable=True)
    approval_reason = db.Column("MotivoAprobacion", db.Text)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column("ActualizadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    requester = db.relationship("User", foreign_keys=[requester_id])
    approver = db.relationship("User", foreign_keys=[approved_by_id])
    items = db.relationship("MaterialRequestItem", backref="request", cascade="all, delete-orphan")
    events = db.relationship("MaterialRequestEvent", backref="request", cascade="all, delete-orphan", order_by="MaterialRequestEvent.created_at")
    deliveries = db.relationship("MaterialRequestDelivery", backref="request", cascade="all, delete-orphan", order_by="MaterialRequestDelivery.created_at")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "requester_id": self.requester_id,
            "technician_id": self.technician_id,
            "work_order_id": self.work_order_id,
            "status": self.status,
            "reason": self.reason,
            "approved_by_id": self.approved_by_id,
            "approval_reason": self.approval_reason,
            "items": [i.to_dict() for i in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# MaterialRequestItem: modelo de base de datos que representa la entidad MaterialRequestItem.
class MaterialRequestItem(db.Model):
    __tablename__ = "ItemsSolicitudMaterial"

    id = db.Column("IdItem", db.Integer, primary_key=True)
    request_id = db.Column("IdSolicitud", db.Integer, db.ForeignKey("SolicitudesMaterial.IdSolicitud", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column("IdMaterial", db.Integer, db.ForeignKey("Materiales.IdMaterial", ondelete="NO ACTION"), nullable=False, index=True)
    quantity = db.Column("Cantidad", db.Float, nullable=False, default=0)
    quantity_requested = db.Column("CantidadSolicitada", db.Float, nullable=False, default=0)
    quantity_approved = db.Column("CantidadAprobada", db.Float, nullable=False, default=0, server_default=sa.text("0"))
    quantity_delivered = db.Column("CantidadEntregada", db.Float, nullable=False, default=0, server_default=sa.text("0"))

    material = db.relationship("Material")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "material_id": self.material_id,
            "material": self.material.to_dict() if self.material else None,
            "quantity": self.quantity,
            "quantity_requested": self.quantity_requested,
            "quantity_approved": self.quantity_approved,
            "quantity_delivered": self.quantity_delivered,
        }


# TechnicianProfile: modelo de base de datos que representa la entidad TechnicianProfile.
class TechnicianProfile(db.Model):
    __tablename__ = "PerfilesTecnico"

    id = db.Column("IdPerfil", db.Integer, primary_key=True)
    user_id = db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), nullable=False, unique=True)
    first_name = db.Column("Nombre", db.String(80))
    last_name = db.Column("Apellido", db.String(80))
    phone = db.Column("Telefono", db.String(30))
    email = db.Column("Correo", db.String(120))
    specialty = db.Column("Especialidad", db.String(80))
    specialty_code = db.Column("CodigoEspecialidad", db.String(60), db.ForeignKey("Especialidades.Codigo", ondelete="NO ACTION"))
    legacy_zone = db.Column("ZonaLegado", db.String(250))
    document_type = db.Column("TipoDocumento", db.String(20))
    document_number = db.Column("NumeroDocumento", db.String(40))
    document = db.Column("Documento", db.String(40))
    is_available = db.Column("EstaDisponible", db.Boolean, nullable=False, default=True)
    is_active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False, server_default=sa.text("1"))
    open_orders = db.Column("OrdenesAbiertas", db.Integer, default=0, nullable=False, server_default=sa.text("0"))
    created_by_id = db.Column("IdCreadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column("ActualizadoEn", 
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", foreign_keys=[user_id])

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "user": self.user.to_dict() if self.user else None,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "name": f"{self.first_name or ''} {self.last_name or ''}".strip() or (self.user.username if self.user else ''),
            "phone": self.phone,
            "email": self.email,
            "specialty": self.specialty,
            "zones": self.legacy_zone,
            "legacy_zone": self.legacy_zone,
            "document": self.document,
            "is_available": self.is_available,
            "is_active": self.is_active,
            "open_orders": self.open_orders,
            "coverage": [
                {
                    "id": c.id,
                    "city_id": c.city_id,
                    "city_label": (c.city.label() if c.city else None),
                    "zone_id": c.zone_id,
                    "zone_name": (c.zone.name if c.zone else None),
                    "is_primary": c.is_primary,
                }
                for c in (getattr(self, "coverages", None) or [])
            ],
        }


# MaterialCategory: modelo de base de datos que representa la entidad MaterialCategory.
class MaterialCategory(db.Model):
    __tablename__ = "CategoriasMaterial"

    id = db.Column("IdCategoria", db.Integer, primary_key=True)
    code = db.Column("Codigo", db.String(40), nullable=False, unique=True, index=True)
    name = db.Column("Nombre", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120), nullable=False, unique=True, index=True)
    is_active = db.Column("EstaActivo", db.Boolean, nullable=False, default=True, server_default=sa.text("1"))

# to_dict: serializa la categoria de material a diccionario con id, codigo, nombre, nombre normalizado y activo; sin parametros; sin efectos secundarios.
    def to_dict(self):
        return {"id": self.id, "code": self.code, "name": self.name, "name_norm": self.name_norm, "is_active": self.is_active}



    # Textos del módulo de materiales siempre en MAYÚSCULAS, sin importar quién escriba (rutas, servicios, semillas).
    @sa.orm.validates('name')
    def _upper_text(self, key, value):
        return normalize_upper(value)

# MaterialUnit: modelo de base de datos que representa la entidad MaterialUnit.
class MaterialUnit(db.Model):
    __tablename__ = "UnidadesMaterial"

    id = db.Column("IdUnidad", db.Integer, primary_key=True)
    code = db.Column("Codigo", db.String(20), nullable=False, unique=True, index=True)
    name = db.Column("Nombre", db.String(60), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(60), nullable=False, unique=True, index=True)
    allows_decimal = db.Column("PermiteDecimal", db.Boolean, nullable=False, default=False, server_default=sa.text("0"))
    is_active = db.Column("EstaActivo", db.Boolean, nullable=False, default=True, server_default=sa.text("1"))

# to_dict: serializa la unidad de material a diccionario con id, codigo, nombre, nombre normalizado, permite decimales y activo; sin parametros; sin efectos secundarios.
    def to_dict(self):
        return {"id": self.id, "code": self.code, "name": self.name, "name_norm": self.name_norm,
                "allows_decimal": self.allows_decimal, "is_active": self.is_active}



    # Textos del módulo de materiales siempre en MAYÚSCULAS, sin importar quién escriba (rutas, servicios, semillas).
    @sa.orm.validates('name')
    def _upper_text(self, key, value):
        return normalize_upper(value)

# MaterialCatalog: modelo de base de datos que representa la entidad MaterialCatalog.
class MaterialCatalog(db.Model):
    __tablename__ = "CatalogoMateriales"

    id = db.Column("IdItemCatalogo", db.Integer, primary_key=True)
    category_id = db.Column("IdCategoria", db.Integer, db.ForeignKey("CategoriasMaterial.IdCategoria", ondelete="NO ACTION"), nullable=False, index=True)
    code = db.Column("Codigo", db.String(40), nullable=False, unique=True, index=True)
    name = db.Column("Nombre", db.String(200), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(200), nullable=False, unique=True, index=True)
    unit_id = db.Column("IdUnidad", db.Integer, db.ForeignKey("UnidadesMaterial.IdUnidad", ondelete="NO ACTION"), nullable=False, index=True)
    measure = db.Column("Medida", db.String(60))
    stage = db.Column("Etapa", db.String(60))
    applies_to = db.Column("AplicaA", db.String(40))
    is_active = db.Column("EstaActivo", db.Boolean, nullable=False, default=True, server_default=sa.text("1"))

    category = db.relationship("MaterialCategory")
    unit = db.relationship("MaterialUnit")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "category_id": self.category_id,
            "category": self.category.name if self.category else None,
            "code": self.code,
            "name": self.name,
            "name_norm": self.name_norm,
            "unit_id": self.unit_id,
            "unit": self.unit.code if self.unit else None,
            "unit_name": self.unit.name if self.unit else None,
            "allows_decimal": self.unit.allows_decimal if self.unit else False,
            "measure": self.measure,
            "stage": self.stage,
            "applies_to": self.applies_to,
            "is_active": self.is_active,
        }



    # Textos del módulo de materiales siempre en MAYÚSCULAS, sin importar quién escriba (rutas, servicios, semillas).
    @sa.orm.validates('name', 'measure', 'stage', 'applies_to')
    def _upper_text(self, key, value):
        return normalize_upper(value)

# MaterialRequestEvent: modelo de base de datos que representa la entidad MaterialRequestEvent.
class MaterialRequestEvent(db.Model):
    __tablename__ = "EventosSolicitudMaterial"

    id = db.Column("IdEvento", db.Integer, primary_key=True)
    request_id = db.Column("IdSolicitud", db.Integer, db.ForeignKey("SolicitudesMaterial.IdSolicitud", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = db.Column("IdActor", db.Integer, db.ForeignKey("Usuarios.IdUsuario", ondelete="NO ACTION"))
    action = db.Column("Accion", db.String(40), nullable=False)
    from_status = db.Column("EstadoAnterior", db.String(30))
    to_status = db.Column("EstadoNuevo", db.String(30))
    payload = db.Column("Carga", db.Text)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    actor = db.relationship("User")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# MaterialRequestDelivery: modelo de base de datos que representa la entidad MaterialRequestDelivery.
class MaterialRequestDelivery(db.Model):
    __tablename__ = "EntregasSolicitudMaterial"

    id = db.Column("IdEntrega", db.Integer, primary_key=True)
    request_id = db.Column("IdSolicitud", db.Integer, db.ForeignKey("SolicitudesMaterial.IdSolicitud", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = db.Column("IdActor", db.Integer, db.ForeignKey("Usuarios.IdUsuario", ondelete="NO ACTION"), nullable=False)
    operation_id = db.Column("IdOperacion", db.String(36), index=True)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    items = db.relationship("MaterialRequestDeliveryItem", backref="delivery", cascade="all, delete-orphan")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "actor_id": self.actor_id,
            "operation_id": self.operation_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


# MaterialRequestDeliveryItem: modelo de base de datos que representa la entidad MaterialRequestDeliveryItem.
class MaterialRequestDeliveryItem(db.Model):
    __tablename__ = "ItemsEntregaSolicitud"

    id = db.Column("IdItemEntrega", db.Integer, primary_key=True)
    delivery_id = db.Column("IdEntrega", db.Integer, db.ForeignKey("EntregasSolicitudMaterial.IdEntrega", ondelete="CASCADE"), nullable=False, index=True)
    request_item_id = db.Column("IdItemSolicitud", db.Integer, db.ForeignKey("ItemsSolicitudMaterial.IdItem", ondelete="NO ACTION"), nullable=False, index=True)
    quantity_delivered = db.Column("CantidadEntregada", db.Float, nullable=False)
    movement_id = db.Column("IdMovimiento", db.Integer, db.ForeignKey("MovimientosStock.IdMovimiento", ondelete="NO ACTION"))

    request_item = db.relationship("MaterialRequestItem")
    movement = db.relationship("StockMovement")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "delivery_id": self.delivery_id,
            "request_item_id": self.request_item_id,
            "quantity_delivered": self.quantity_delivered,
            "movement_id": self.movement_id,
        }


# MaterialRequestOperation: modelo de base de datos que representa la entidad MaterialRequestOperation.
class MaterialRequestOperation(db.Model):
    __tablename__ = "OperacionesSolicitudMaterial"

    id = db.Column("IdOperacion", db.Integer, primary_key=True)
    operation_id = db.Column("IdOperacionCliente", db.String(36), nullable=False, unique=True, index=True)
    operation_type = db.Column("TipoOperacion", db.String(40), nullable=False, index=True)
    actor_id = db.Column("IdActor", db.Integer, db.ForeignKey("Usuarios.IdUsuario", ondelete="NO ACTION"))
    request_id = db.Column("IdSolicitud", db.Integer, db.ForeignKey("SolicitudesMaterial.IdSolicitud", ondelete="NO ACTION"), index=True)
    result = db.Column("Resultado", db.Text)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "actor_id": self.actor_id,
            "request_id": self.request_id,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
