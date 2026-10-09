# app/core/security.py
from datetime import datetime, timedelta, timezone

import jwt  # Identifica quién es el usuario en cada petición web.
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

# Bcrypt: estándar para guardar contraseñas. Transforma "123456" en un revoltijo
# que no se puede revertir.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Extrae el token de la cabecera "Authorization: Bearer ..." de la petición.
autenticacion = OAuth2PasswordBearer(tokenUrl="/usuarios/login")

# Bcrypt solo procesa los primeros 72 bytes de la contraseña.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("La contraseña no puede superar los 72 bytes.")
    return pwd_context.hash(password)


def verificar_contraseña(contraseña_ingresada: str, password_hashed: str) -> bool:
    # Contraseñas absurdamente largas: se rechazan en vez de provocar un 500.
    if len(contraseña_ingresada.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return False
    try:
        return pwd_context.verify(contraseña_ingresada, password_hashed)
    except ValueError:  # hash guardado con formato inválido
        return False


def crear_token_acceso(datos: dict, tiempo_expiracion: timedelta | None = None) -> str:
    # Hora universal (UTC) para que no varíe por país. La expiración sale del .env.
    expiracion = datetime.now(timezone.utc) + (
        tiempo_expiracion or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # El payload es la carga del token: id del usuario, rol, versión y vencimiento.
    # "datos" debe incluir "sub" (id) y "tv" (token_version del usuario).
    payload = {**datos, "exp": expiracion}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# Fábrica de errores: crea un 401 con el texto que explica por qué falló el token.
def _error_credenciales(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decodificar_token(token: str = Depends(autenticacion)) -> dict:
    """Valida el token y devuelve {"sub": <id como texto>, "tv": <token_version>}.

    NUEVO: se devuelve también "tv" para que deps.py pueda rechazar tokens emitidos
    antes de un cambio de contraseña. Los tokens viejos sin "tv" cuentan como versión 0.
    """
    try:
        # Exigimos que traiga vencimiento (exp) e id (sub).
        contenido = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise _error_credenciales("Token inválido o expirado")

    sub = contenido.get("sub")
    if not isinstance(sub, str) or not sub:
        raise _error_credenciales("Credenciales inválidas")

    tv = contenido.get("tv", 0)
    # bool es subclase de int en Python: se descarta a propósito.
    if not isinstance(tv, int) or isinstance(tv, bool):
        raise _error_credenciales("Credenciales inválidas")

    return {"sub": sub, "tv": tv}


def verificar_token(token: str = Depends(autenticacion)) -> str:
    """Se conserva por compatibilidad: devuelve solo el 'sub' (ID del usuario)."""
    return decodificar_token(token)["sub"]