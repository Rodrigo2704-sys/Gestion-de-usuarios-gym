from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

# Ajusta max_length al tamaño real de la columna en tu tabla.
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]

# bcrypt ignora (o rechaza, según la librería) lo que pase de 72 bytes.
# Si usas argon2 puedes subir este límite.
MAX_PASSWORD = 72


def _validar_bytes_password(valor: str) -> str:
    # Los caracteres con tilde, ñ o emojis ocupan más de 1 byte.
    if len(valor.encode("utf-8")) > MAX_PASSWORD:
        raise ValueError(f"La contraseña no puede superar {MAX_PASSWORD} bytes")
    return valor


MAX_CORREO = 150  # largo de la columna usuarios.correo


def _normalizar_correo(valor: Optional[str]) -> Optional[str]:
    """Evita duplicados tipo 'Ana@x.com' vs 'ana@x.com' y correos más largos que la columna."""
    if valor and len(valor) > MAX_CORREO:
        raise ValueError(f"El correo no puede superar {MAX_CORREO} caracteres")
    return valor.lower() if valor else valor


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
class RolSalida(BaseModel):
    # Si ya tienes RolSalida definido en otro lado, borra esta clase e impórtala.
    id: int
    nombre: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Base: datos comunes del usuario (la contraseña NO va aquí, así no se hereda
# a los esquemas de salida).
# ---------------------------------------------------------------------------
class DatosUsuario(BaseModel):
    nombre: str
    correo: EmailStr


# Sin uso en el router actual (el login usa OAuth2PasswordRequestForm).
# Se conserva por si otro módulo la importa.
class EntradaLogin(BaseModel):
    correo: EmailStr
    password: str


# ---------------------------------------------------------------------------
# Registro: rechaza campos extra, así un "rol_id" enviado por el cliente
# devuelve 422 en lugar de ignorarse en silencio.
# ---------------------------------------------------------------------------
class EntradaRegistro(DatosUsuario):
    # Reglas estrictas solo al ENTRAR datos. La salida hereda DatosUsuario sin
    # ellas, para no dar 500 con usuarios antiguos (p. ej. un nombre de 1 letra).
    nombre: Nombre

    @field_validator("correo")
    @classmethod
    def correo_en_minusculas(clase, valor: str) -> str:
        return _normalizar_correo(valor)

    password: str = Field( ...,min_length=8
    ,max_length=MAX_PASSWORD
    ,description="Entre 8 y 72 caracteres",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("password")
    @classmethod
    def password_72_bytes(clase, valor: str) -> str:
        return _validar_bytes_password(valor)


# ---------------------------------------------------------------------------
# Salida: id, nombre, correo (heredados) + rol. Nunca incluye contraseña.
# ---------------------------------------------------------------------------
class SalidaUsuario(DatosUsuario):
    id: int
    rol_id: int
    activo: bool = True
    rol: Optional[RolSalida] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Actualización parcial. nombre y correo: el propio usuario; activo: solo un admin.
# La contraseña se cambia con CambiarPassword, no por aquí.
# ---------------------------------------------------------------------------
class ActualizarUsuario(BaseModel):
    nombre: Optional[Nombre] = None
    correo: Optional[EmailStr] = None
    activo: Optional[bool] = None  # solo admin (lo controla el router)

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("correo")
    @classmethod
    def correo_en_minusculas(clase, valor: Optional[str]) -> Optional[str]:
        return _normalizar_correo(valor)

    @model_validator(mode="after")
    def sin_nulos_explicitos(self):
        # Con exclude_unset, un {"nombre": null} llegaría a la BD como NULL
        # y reventaría con un 500 si la columna es NOT NULL.
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"'{campo}' no puede ser null")
        return self


# ---------------------------------------------------------------------------
# Cambio de contraseña (requiere la actual). Falta el endpoint; se arma
# al revisar crud/usuarios.py y core/security.py.
# ---------------------------------------------------------------------------
class CambiarPassword(BaseModel):
    password_actual: str
    password_nueva: str = Field(..., min_length=8, max_length=MAX_PASSWORD)

    model_config = ConfigDict(extra="forbid")

    @field_validator("password_nueva")
    @classmethod
    def password_72_bytes(clase, valor: str) -> str:
        return _validar_bytes_password(valor)

    @model_validator(mode="after")
    def distinta_de_la_actual(self):
        if self.password_actual == self.password_nueva:
            raise ValueError("La contraseña nueva debe ser distinta de la actual")
        return self