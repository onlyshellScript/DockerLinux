import json
import os

from app.extensions import db
from app.catalogs.models import (
    Country, City, Zone, Specialty, InstallationType,
)
from app.common.normalize import normalize_text

SPECIALTIES = [
    ("instalacion_domiciliaria", "Instalación domiciliaria"),
    ("instalacion_comercial", "Instalación comercial"),
    ("instalacion_industrial", "Instalación industrial"),
    ("instalacion_institucional", "Instalación institucional (hospitales, colegios)"),
    ("mantenimiento_revision", "Mantenimiento y revisión periódica"),
    ("medidores", "Instalación y cambio de medidores"),
    ("tuberias_hermeticidad", "Revisión de tuberías y pruebas de hermeticidad"),
    ("quemadores_gasodomesticos", "Reparación de quemadores y gasodomésticos"),
    ("emergencias_fugas", "Atención de fugas y emergencias"),
    ("conversion_equipos", "Conversión de equipos a gas"),
    ("otra", "Otra"),
]

BOGOTA_LOCALITIES = [
    "Usaquén", "Chapinero", "Santa Fe", "San Cristóbal", "Usme", "Tunjuelito", "Bosa",
    "Kennedy", "Fontibón", "Engativá", "Suba", "Barrios Unidos", "Teusaquillo",
    "Los Mártires", "Antonio Nariño", "Puente Aranda", "La Candelaria",
    "Rafael Uribe Uribe", "Ciudad Bolívar", "Sumapaz",
]

INSTALLATION_TYPES = [
    ("residencial", "Residencial"),
    ("comercial", "Comercial"),
    ("industrial", "Industrial"),
    ("institucional", "Institucional"),
]


# Carga los datos indicados; recibe sin parametros; accede al sistema de archivos; devuelve el valor correspondiente.
def _load_cities():
    json_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "seeds", "colombia_divipola.json"))
    if not os.path.exists(json_path):
        json_path = os.path.normpath(os.path.join(os.getcwd(), "services", "api", "seeds", "colombia_divipola.json"))
    if not os.path.exists(json_path):
        return []
    return json.load(open(json_path, encoding="utf-8"))


# Inserta datos iniciales en la base; recibe sin parametros; interactua con la base de datos; escribe en consola; devuelve el valor correspondiente.
def seed():
    if not Country.query.filter_by(iso2="CO").first():
        db.session.add(Country(iso2="CO", name="Colombia", name_norm=normalize_text("Colombia"), active=True))
    db.session.flush()
    country = Country.query.filter_by(iso2="CO").first()

    for item in _load_cities():
        code = item["dane_code"].zfill(5)
        if City.query.filter_by(dane_code=code).first():
            continue
        db.session.add(City(
            country_id=country.id,
            department_name=item["department_name"],
            dane_code=code,
            name=item["name"],
            name_norm=normalize_text(item["name"]),
            active=True,
        ))
    db.session.flush()

    for code, label in SPECIALTIES:
        if not Specialty.query.get(code):
            db.session.add(Specialty(code=code, label=label, name_norm=normalize_text(label), active=True))

    for code, label in INSTALLATION_TYPES:
        if not InstallationType.query.get(code):
            db.session.add(InstallationType(code=code, label=label, name_norm=normalize_text(label), active=True))

    bogota = City.query.filter_by(dane_code="11001").first()
    if bogota:
        for loc in BOGOTA_LOCALITIES:
            nn = normalize_text(loc)
            if not Zone.query.filter_by(city_id=bogota.id, name_norm=nn).first():
                db.session.add(Zone(city_id=bogota.id, kind="localidad", name=loc, name_norm=nn, active=True))

    db.session.commit()
    print("seeded catalogs")
