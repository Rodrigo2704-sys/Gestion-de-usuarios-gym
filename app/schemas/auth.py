# app/schemas/auth.py
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.schemas.usuarios import MAX_PASSWORD, _normalizar_correo, _validar_bytes_password

# Código numérico de exactamente 6 dígitos.
Codigo = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


class _ConCorreo(BaseModel):
    correo: EmailStr

    # Rechaza campos inventados (mismo criterio que EntradaRegistro).
    model_config = ConfigDict(extra="forbid")

    @field_validator("correo")
    @classmethod
    def correo_en_minusculas(cls, valor: str) -> str:
        return _normalizar_correo(valor)


# Sirve para "reenviar código de verificación" y para "olvidé mi contraseña".
class SolicitudCorreo(_ConCorreo):
    pass


class VerificarCorreo(_ConCorreo):
    codigo: Codigo


class RestablecerPassword(_ConCorreo):
    codigo: Codigo
    password_nueva: str = Field(..., min_length=8, max_length=MAX_PASSWORD)

    @field_validator("password_nueva")
    @classmethod
    def password_72_bytes(cls, valor: str) -> str:
        return _validar_bytes_password(valor)