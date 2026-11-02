from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db


class Country(db.Model):
    __tablename__ = "countries"

    id = db.Column(db.Integer, primary_key=True)
    iso2 = db.Column(db.String(2), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    def to_dict(self):
        return {"id": self.id, "iso2": self.iso2, "name": self.name, "active": self.active}


class City(db.Model):
    __tablename__ = "cities"

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id", ondelete="RESTRICT"), nullable=False, index=True)
    department_name = db.Column(db.String(120))
    dane_code = db.Column(db.String(5), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    country = db.relationship("Country")

    __table_args__ = (
        db.UniqueConstraint("country_id", "dane_code", name="uq_city_country_dane"),
        db.Index("ix_city_country_name_norm", "country_id", "name_norm"),
    )

    def label(self):
        if self.department_name:
            return f"{self.name} · {self.department_name}"
        return self.name

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


class Zone(db.Model):
    __tablename__ = "zones"

    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    city = db.relationship("City")

    __table_args__ = (
        db.UniqueConstraint("city_id", "name_norm", name="uq_zone_city_name"),
        db.CheckConstraint(
            "kind IN ('localidad','comuna','barrio','vereda','corregimiento','sector')",
            name="ck_zone_kind",
        ),
    )

    def to_dict(self):
        return {"id": self.id, "city_id": self.city_id, "kind": self.kind, "name": self.name, "active": self.active}


class InstallationType(db.Model):
    __tablename__ = "installation_types"

    code = db.Column(db.String(60), primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True, nullable=False)


class Specialty(db.Model):
    __tablename__ = "specialties"

    code = db.Column(db.String(60), primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.CheckConstraint("code <> ''", name="ck_specialty_code_nonempty"),
    )


class Department(db.Model):
    __tablename__ = "departments"

    code = db.Column(db.String(2), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120))


class Municipality(db.Model):
    __tablename__ = "municipalities"

    code = db.Column(db.String(5), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120))
    department_code = db.Column(db.String(2), db.ForeignKey("departments.code", ondelete="RESTRICT"), index=True)


class Sector(db.Model):
    __tablename__ = "sectors"

    id = db.Column(db.Integer, primary_key=True)
    municipality_code = db.Column(db.String(5), db.ForeignKey("municipalities.code", ondelete="RESTRICT"), index=True)
    name = db.Column(db.String(120), nullable=False)
    name_norm = db.Column(db.String(120))
    kind = db.Column(db.String(30), nullable=False, default="sector")
    active = db.Column(db.Boolean, default=True, nullable=False)


class TechnicianZone(db.Model):
    __tablename__ = "technician_zones"

    id = db.Column(db.Integer, primary_key=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician_profiles.id", ondelete="RESTRICT"), index=True, nullable=False)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False, index=True)
    zone_id = db.Column(db.Integer, db.ForeignKey("zones.id", ondelete="RESTRICT"), nullable=True, index=True)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)

    city = db.relationship("City")
    zone = db.relationship("Zone")
    technician = db.relationship("TechnicianProfile", backref="coverages")

    __table_args__ = (
        db.Index("uq_techzone_city_all", "technician_id", "city_id", unique=True,
                 sqlite_where=sa.text("zone_id IS NULL"),
                 postgresql_where=sa.text("zone_id IS NULL")),
        db.Index("uq_techzone_zone", "technician_id", "city_id", "zone_id", unique=True,
                 sqlite_where=sa.text("zone_id IS NOT NULL"),
                 postgresql_where=sa.text("zone_id IS NOT NULL")),
        db.Index("uq_techzone_primary", "technician_id", unique=True,
                 sqlite_where=sa.text("is_primary = 1"),
                 postgresql_where=sa.text("is_primary = TRUE")),
    )
