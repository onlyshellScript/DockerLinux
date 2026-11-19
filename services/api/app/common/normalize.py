import re
import unicodedata


# Normaliza un texto: recorta, pasa a minúsculas, elimina acentos y colapsa espacios. Devuelve el texto normalizado o None si la entrada es None.
def normalize_text(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Normaliza un correo electrónico reutilizando normalize_text; devuelve el correo normalizado o None si la entrada es None.
def normalize_email(value):
    if value is None:
        return None
    return normalize_text(value)


# normalize_upper(value): texto en MAYÚSCULAS para el módulo de materiales. Recorta, colapsa espacios internos y
# convierte con str.upper(), que respeta el español (ñ -> Ñ, á -> Á, ü -> Ü). Conserva acentos: solo cambia la escritura.
# None se mantiene None; los valores que no son texto se devuelven sin cambios.
def normalize_upper(value):
    if value is None or not isinstance(value, str):
        return value
    return re.sub(r"\s+", " ", value).strip().upper()
