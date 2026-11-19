# -*- coding: utf-8 -*-
# Firma de perfil del tecnico y firma historica de las evidencias.
#
# - Firma de perfil: FirmasTecnico. Cada registro es una version inmutable (archivo + sha256). Registrar una firma
#   nueva crea otra version y desactiva la anterior; nunca se sobrescribe ni se borra una version.
# - Firma historica: al registrar una evidencia se copia en ella la referencia a la version vigente, su sha256,
#   el firmante y la fecha. El firmante es SIEMPRE el usuario autenticado: el cliente no elige ni envia la firma.
import hashlib
import io
from datetime import datetime, timezone

from flask import current_app
from PIL import Image

from app.extensions import db
from app.evidence.models import TechnicianSignature
from app.evidence.storage import get_storage

SIGNATURE_MIME = "image/png"
SIGNATURE_MAX_BYTES = 512 * 1024
SIGNATURE_MIN_SIZE = (120, 40)
SIGNATURE_MAX_SIZE = (2400, 1200)


# SignatureError: error de validacion de la firma; code es estable para la API.
class SignatureError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


# get_active_signature: version vigente de la firma de perfil del usuario, o None.
def get_active_signature(user_id):
    return (
        TechnicianSignature.query
        .filter(TechnicianSignature.user_id == user_id, TechnicianSignature.is_active == True)
        .order_by(TechnicianSignature.version.desc(), TechnicianSignature.id.desc())
        .first()
    )


# _has_strokes: la imagen tiene trazos; rechaza un lienzo vacio (todo transparente o de un solo color).
def _has_strokes(img):
    rgba = img.convert("RGBA")
    a_lo, a_hi = rgba.getchannel("A").getextrema()
    if a_hi == 0:
        return False
    g_lo, g_hi = rgba.convert("L").getextrema()
    return a_lo != a_hi or g_lo != g_hi


# _validate_signature_png: valida que los bytes sean un PNG real, de tamano razonable y con trazos.
def _validate_signature_png(data):
    if not data:
        raise SignatureError("signature_empty", "La firma esta vacia")
    if len(data) > SIGNATURE_MAX_BYTES:
        raise SignatureError("signature_too_large", "La imagen de la firma supera el tamano permitido")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SignatureError("signature_invalid_format", "La firma debe capturarse en el recuadro de dibujo (PNG)")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise SignatureError("signature_invalid_image", "La imagen de la firma no es valida")
    w, h = img.size
    if w < SIGNATURE_MIN_SIZE[0] or h < SIGNATURE_MIN_SIZE[1] or w > SIGNATURE_MAX_SIZE[0] or h > SIGNATURE_MAX_SIZE[1]:
        raise SignatureError("signature_invalid_size", "Las dimensiones de la firma no son validas")
    if not _has_strokes(img):
        raise SignatureError("signature_blank", "Dibuje su firma antes de guardarla")


# register_profile_signature: registra una nueva version de la firma de perfil del usuario autenticado.
# La version anterior queda inactiva pero intacta (las evidencias que la usan la siguen mostrando).
def register_profile_signature(user_id, data):
    _validate_signature_png(data)
    storage = get_storage()
    key, meta, error = storage.save(data, "firma.png", SIGNATURE_MIME)
    if error:
        raise SignatureError("signature_invalid_image", "La imagen de la firma no es valida")
    now = datetime.now(timezone.utc)
    try:
        previous = TechnicianSignature.query.filter(
            TechnicianSignature.user_id == user_id, TechnicianSignature.is_active == True
        ).all()
        last_version = db.session.query(db.func.max(TechnicianSignature.version)).filter(
            TechnicianSignature.user_id == user_id
        ).scalar() or 0
        for p in previous:
            p.is_active = False
            p.replaced_at = now
        sig = TechnicianSignature(
            user_id=user_id, storage_key=key, mime_type=meta["mime_type"], size_bytes=meta["size_bytes"],
            sha256=meta["sha256"], version=last_version + 1, is_active=True, created_at=now,
        )
        db.session.add(sig)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # El registro no se guardo: el archivo nuevo no esta referenciado por nadie y puede retirarse.
        storage.delete(key)
        raise
    return sig


# load_signature_bytes: lee el archivo de una version de firma y verifica que coincida con la huella esperada
# (la de la version, o la copiada en la evidencia). Devuelve (bytes, None) o (None, codigo_de_error).
def load_signature_bytes(signature, expected_sha256=None):
    if signature is None:
        return None, "signature_not_found"
    path = get_storage().load(signature.storage_key)
    if not path:
        return None, "signature_file_missing"
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != signature.sha256 or (expected_sha256 and digest != expected_sha256):
        current_app.logger.error("firma %s: el archivo no coincide con su huella registrada", signature.id)
        return None, "signature_integrity_error"
    return data, None


# signature_required_for: la configuracion exige firma de perfil a los tecnicos al registrar evidencias.
def signature_required_for(roles):
    if not current_app.config.get("EVIDENCE_REQUIRE_TECH_SIGNATURE", True):
        return False
    return "technician" in set(roles or [])
