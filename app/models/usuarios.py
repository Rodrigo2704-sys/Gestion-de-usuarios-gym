from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import relationship

from app.core.database import Base


def ahora_utc() -> datetime:
    """Hora UTC sin zona horaria (naive), lista para columnas DateTime de MySQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RolModel(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), unique=True, nullable=False)

    # Relación uno-a-muchos con usuarios
    usuarios = relationship("UsuarioModel", back_populates="rol")


class UsuarioModel(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(150), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    rol_id = Column(Integer, ForeignKey("roles.id"), default=2, nullable=False)

    # Borrado lógico: False = cuenta desactivada (no puede iniciar sesión).
    activo = Column(Boolean, nullable=False, default=True, server_default=text("1"))

    # NUEVO: False hasta que el usuario confirme el código enviado a su correo.
    # Requiere migración (ver migraciones.sql).
    correo_verificado = Column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )

    # Trae el objeto Rol (y su nombre: "Administrador", "Cliente", etc.)
    rol = relationship("RolModel", back_populates="usuarios")


class CodigoVerificacionModel(Base):
    """Códigos de un solo uso: verificar correo o recuperar contraseña.

    Nunca se guarda el código en claro, solo su HMAC (ver crud/verificacion.py).
    """

    __tablename__ = "codigos_verificacion"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proposito = Column(String(30), nullable=False)  # "verificar_correo" | "recuperar_password"
    codigo_hash = Column(String(64), nullable=False)
    expira_en = Column(DateTime, nullable=False)
    intentos = Column(Integer, nullable=False, default=0, server_default=text("0"))
    usado = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    creado_en = Column(DateTime, nullable=False, default=ahora_utc)