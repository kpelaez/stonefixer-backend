# app/core/password_policy.py
import re

MIN_LENGTH = 8
MAX_LENGTH = 72  # límite real de bcrypt — bytes, no caracteres, pero para ASCII es equivalente
MIN_UPPERCASE = 1
MIN_DIGITS = 2

# Lista corta de valores obviamente débiles. No pretende ser exhaustiva,
# es una barrera contra los casos más evidentes.
COMMON_WEAK_PASSWORDS = {
    "12345678", "123456789", "password", "contraseña", "qwerty123",
    "admin123", "changeme", "stonefixer", "welcome123",
}


def validate_password_strength(password: str, email: str | None = None) -> str:
    """
    Valida fortaleza de contraseña siguiendo criterios modernos (NIST 800-63B):
    prioriza longitud sobre complejidad forzada, bloquea valores triviales.

    Reglas: mínimo MIN_LENGTH caracteres, al menos MIN_UPPERCASE mayúscula(s)
    y MIN_DIGITS dígito(s).

    Raises:
        ValueError: si la contraseña no cumple la política.
    """
    if len(password) < MIN_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {MIN_LENGTH} caracteres")

    if len(password.encode("utf-8")) > MAX_LENGTH:
        raise ValueError(
            f"La contraseña no puede superar los {MAX_LENGTH} bytes "
            "(límite técnico de bcrypt)"
        )

    uppercase_count = sum(1 for c in password if c.isupper())
    if uppercase_count < MIN_UPPERCASE:
        raise ValueError(f"La contraseña debe tener al menos {MIN_UPPERCASE} letra mayúscula")

    digit_count = sum(1 for c in password if c.isdigit())
    if digit_count < MIN_DIGITS:
        raise ValueError(f"La contraseña debe tener al menos {MIN_DIGITS} números")

    if password.lower() in COMMON_WEAK_PASSWORDS:
        raise ValueError("Esta contraseña es demasiado común o predecible")

    if email:
        local_part = email.split("@")[0].lower()
        if local_part and local_part in password.lower():
            raise ValueError("La contraseña no puede contener tu email o usuario")

    return password