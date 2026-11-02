import re
import secrets
import unicodedata

AMBIGUOUS = set("0O1lI")
SYMBOLS = "!@#$%&*+-=?"
LOWER = "abcdefghijkmnopqrstuvwxyz"
UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
DIGITS = "23456789"


def normalize_username(first_name, last_name):
    base = (first_name[:1] + last_name).lower()
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]", "", base)
    return base or "user"


def generate_username(first_name, last_name, existing):
    base = normalize_username(first_name, last_name)
    if base not in existing:
        return base
    i = 2
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"


def generate_temporary_password(length=12):
    while True:
        chars = [
            secrets.choice(UPPER),
            secrets.choice(LOWER),
            secrets.choice(DIGITS),
            secrets.choice(SYMBOLS),
        ]
        pool = LOWER + UPPER + DIGITS + SYMBOLS
        chars += [secrets.choice(pool) for _ in range(length - 4)]
        secrets.SystemRandom().shuffle(chars)
        pwd = "".join(chars)
        if _valid_password(pwd):
            return pwd


def _valid_password(pwd):
    if len(pwd) < 10:
        return False
    if not any(c.isupper() for c in pwd):
        return False
    if not any(c.islower() for c in pwd):
        return False
    if not any(c.isdigit() for c in pwd):
        return False
    return True


def validate_password_policy(password, username=None, history=None):
    if len(password) < 10:
        return False, "Mínimo 10 caracteres"
    if not any(c.isupper() for c in password):
        return False, "Debe incluir mayúscula"
    if not any(c.islower() for c in password):
        return False, "Debe incluir minúscula"
    if not any(c.isdigit() for c in password):
        return False, "Debe incluir número"
    if username and password.lower() == username.lower():
        return False, "No puede ser igual al usuario"
    if history and password in history:
        return False, "No puede repetir las últimas 3 contraseñas"
    return True, None


def password_strength(password):
    score = 0
    if len(password) >= 10:
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in SYMBOLS for c in password):
        score += 1
    if len(password) >= 14:
        score += 1
    return min(score, 5)
