from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

# Crea una regla estricta para la columna tipo del plan. Obliga a que sea un texto, le borra los espacios fantasmas de los lados (strip_whitespace), y exige que mida entre 2 y 100 caracteres.
# Si el Frontend intenta enviar un texto vacío o de 200 letras, Pydantic lo rebota de inmediato.
Tipo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class EstadoMembresia(str, Enum):
    # IMPORTANTE: deben coincidir con los valores permitidos en tu BD.
    ACTIVA = "activa"
    VENCIDA = "vencida"
    CANCELADA = "cancelada"


# ---------------------------------------------------------------------------
# PLANES (catálogo)
# ---------------------------------------------------------------------------
class DatosPlan(BaseModel):
    tipo: Tipo
    precio: float = Field(..., gt=0, le=99_999_999.99)  # DECIMAL(10,2) #maximo 99 millones
    duracion: int = Field(..., gt=0, le=3650, description="Duración en días")

#Es un candado de seguridad digital. Si un hacker intenta meter un dato malicioso extra en el JSON que no pertenece al plan (ej. {"tipo": "Gold", "hakeo": "true"}), esta regla lo detecta y rechaza la petición por completo
    model_config = ConfigDict(extra="forbid")

#valor
    @field_validator("precio")
    @classmethod
    def precio_con_dos_decimales(cls, v: float) -> float:
        v = round(v, 2)  # la columna guarda solo 2 decimales
        if v <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        return v


# La salida NO hereda de DatosPlan: así no se vuelven a aplicar las reglas de
# entrada a datos que ya están guardados (un plan viejo con precio 0 daría 500).
class SalidaPlan(BaseModel):
    id: int
    tipo: str
    precio: float
    duracion: int
    estado: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# MEMBRESÍAS
# ---------------------------------------------------------------------------
class AsignarMembresia(BaseModel):
    usuario_id: int = Field(..., gt=0)
    plan_id: int = Field(..., gt=0)

    model_config = ConfigDict(extra="forbid")


class SalidaMembresia(BaseModel):
    id: int
    usuario_id: int
    plan_id: int
    fecha_inicio: datetime
    fecha_fin: datetime
    estado: str
    creado_en: datetime

class ActualizarMembresia(BaseModel):
    # Campos opcionales (= None): el Frontend puede enviar solo uno o ambos si desea actualizar.
    plan_id: Optional[int] = Field(None, gt=0) # Si se envía, debe ser mayor a cero.
    estado: Optional[EstadoMembresia] = None

    # Configuración de comportamiento y seguridad del esquema.
    # from_attributes: Traduce objetos de SQLAlchemy a formato JSON de red.
    # extra="forbid": Bloquea y rechaza peticiones que traigan campos inventados o extraños.
    # use_enum_values: Convierte el Enum a texto plano ("activa") para que mysql-connector lo entienda.
    model_config = ConfigDict(from_attributes=True, extra="forbid", use_enum_values=True)

    # Filtro anti-trampas: Valida los datos justo después de armar el modelo de entrada.
    @model_validator(mode="after")
    def sin_nulos_explicitos(self):
        # Recorre únicamente los campos que el usuario escribió en su JSON enviado.
        for campo in self.model_fields_set:
            # Si el usuario escribió un 'null' (None) a propósito, lanza un error de inmediato.
            if getattr(self, campo) is None:
                raise ValueError(f"'{campo}' no puede ser null")
        return self
