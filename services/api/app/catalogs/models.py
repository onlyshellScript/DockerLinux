from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db


# Country: modelo de base de datos que representa la entidad Country.
class Country(db.Model):
    __tablename__ = "Paises"

    id = db.Column("IdPais", db.Integer, primary_key=True)
    iso2 = db.Column("CodigoIso2", db.String(2), nullable=False, unique=True)
    name = db.Column("Nombre", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120), nullable=False, unique=True)
    active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False)

# to_dict: serializa el pais a diccionario con id, iso2, nombre y activo; sin parametros; sin efectos secundarios.
    def to_dict(self):
        return {"id": self.id, "iso2": self.iso2, "name": self.name, "active": self.active}


# City: modelo de base de datos que representa la entidad City.
class City(db.Model):
    __tablename__ = "Ciudades"

    id = db.Column("IdCiudad", db.Integer, primary_key=True)
    country_id = db.Column("IdPais", db.Integer, db.ForeignKey("Paises.IdPais", ondelete="NO ACTION"), nullable=False, index=True)
    department_name = db.Column("NombreDepartamento", db.String(120))
    dane_code = db.Column("CodigoDane", db.String(5), nullable=False)
    name = db.Column("Nombre", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120), nullable=False)
    active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False)

    country = db.relationship("Country")

    __table_args__ = (
        db.UniqueConstraint("IdPais", "CodigoDane", name="uq_city_country_dane"),
        db.Index("ix_city_country_name_norm", "IdPais", "NombreNormalizado"),
    )

# label: construye la etiqueta legible de la ciudad combinando nombre y departamento; sin parametros; sin efectos secundarios.
    def label(self):
        if self.department_name:
            return f"{self.name} · {self.department_name}"
        return self.name

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "country_id": self.country_id,
            "country_iso2": self.country.iso2 if self.country else None,
            "department_name": self.department_name,
            "dane_code": self.dane_code,
            "name": self.name,
            "label": self.label(),
            "active": self.active,
        }


# Zone: modelo de base de datos que representa la entidad Zone.
class Zone(db.Model):
    __tablename__ = "Zonas"

    id = db.Column("IdZona", db.Integer, primary_key=True)
    city_id = db.Column("IdCiudad", db.Integer, db.ForeignKey("Ciudades.IdCiudad", ondelete="NO ACTION"), nullable=False, index=True)
    kind = db.Column("Tipo", db.String(30), nullable=False)
    name = db.Column("Nombre", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120), nullable=False)
    active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False)

    city = db.relationship("City")

    __table_args__ = (
        db.UniqueConstraint("IdCiudad", "NombreNormalizado", name="uq_zone_city_name"),
        db.CheckConstraint(
            "Tipo IN ('localidad','comuna','barrio','vereda','corregimiento','sector')",
            name="ck_zone_kind",
        ),
    )

# to_dict: serializa la zona a diccionario con id, ciudad, tipo, nombre y activo; sin parametros; sin efectos secundarios.
    def to_dict(self):
        return {"id": self.id, "city_id": self.city_id, "kind": self.kind, "name": self.name, "active": self.active}


# InstallationType: modelo de base de datos que representa la entidad InstallationType.
class InstallationType(db.Model):
    __tablename__ = "TiposInstalacion"

    code = db.Column("Codigo", db.String(60), primary_key=True)
    label = db.Column("Etiqueta", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120), nullable=False, unique=True)
    active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False)


# Specialty: modelo de base de datos que representa la entidad Specialty.
class Specialty(db.Model):
    __tablename__ = "Especialidades"

    code = db.Column("Codigo", db.String(60), primary_key=True)
    label = db.Column("Etiqueta", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120), nullable=False, unique=True)
    active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.CheckConstraint("Codigo <> ''", name="ck_specialty_code_nonempty"),
    )


# Department: modelo de base de datos que representa la entidad Department.
class Department(db.Model):
    __tablename__ = "Departamentos"

    code = db.Column("Codigo", db.String(2), primary_key=True)
    name = db.Column("Nombre", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120))


# Municipality: modelo de base de datos que representa la entidad Municipality.
class Municipality(db.Model):
    __tablename__ = "Municipios"

    code = db.Column("Codigo", db.String(5), primary_key=True)
    name = db.Column("Nombre", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120))
    department_code = db.Column("CodigoDepartamento", db.String(2), db.ForeignKey("Departamentos.Codigo", ondelete="NO ACTION"), index=True)


# Sector: modelo de base de datos que representa la entidad Sector.
class Sector(db.Model):
    __tablename__ = "Sectores"

    id = db.Column("IdSector", db.Integer, primary_key=True)
    municipality_code = db.Column("CodigoMunicipio", db.String(5), db.ForeignKey("Municipios.Codigo", ondelete="NO ACTION"), index=True)
    name = db.Column("Nombre", db.String(120), nullable=False)
    name_norm = db.Column("NombreNormalizado", db.String(120))
    kind = db.Column("Tipo", db.String(30), nullable=False, default="sector")
    active = db.Column("EstaActivo", db.Boolean, default=True, nullable=False)


# TechnicianZone: modelo de base de datos que representa la entidad TechnicianZone.
class TechnicianZone(db.Model):
    __tablename__ = "ZonasTecnico"

    id = db.Column("IdZonaTecnico", db.Integer, primary_key=True)
    technician_id = db.Column("IdTecnico", db.Integer, db.ForeignKey("PerfilesTecnico.IdPerfil", ondelete="NO ACTION"), index=True, nullable=False)
    city_id = db.Column("IdCiudad", db.Integer, db.ForeignKey("Ciudades.IdCiudad", ondelete="NO ACTION"), nullable=False, index=True)
    zone_id = db.Column("IdZona", db.Integer, db.ForeignKey("Zonas.IdZona", ondelete="NO ACTION"), nullable=True, index=True)
    is_primary = db.Column("EsPrincipal", db.Boolean, default=False, nullable=False)

    city = db.relationship("City")
    zone = db.relationship("Zone")
    technician = db.relationship("TechnicianProfile", backref="coverages")

    __table_args__ = (
        db.Index("uq_techzone_city_all", "IdTecnico", "IdCiudad", unique=True,
                 sqlite_where=sa.text("IdZona IS NULL"),
                 postgresql_where=sa.text("IdZona IS NULL")),
        db.Index("uq_techzone_zone", "IdTecnico", "IdCiudad", "IdZona", unique=True,
                 sqlite_where=sa.text("IdZona IS NOT NULL"),
                 postgresql_where=sa.text("IdZona IS NOT NULL")),
        db.Index("uq_techzone_primary", "IdTecnico", unique=True,
                 sqlite_where=sa.text("EsPrincipal = 1"),
                 postgresql_where=sa.text("EsPrincipal = TRUE")),
    )
