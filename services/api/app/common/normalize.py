import re
import unicodedata


def normalize_text(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    # decompose accents
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_email(value):
    if value is None:
        return None
    return normalize_text(value)
