from datetime import datetime

from sqlalchemy import DECIMAL, Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class planesModel(Base):
    __tablename__ = "planes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tipo = Column(String(100), nullable=False)
    precio = Column(DECIMAL(10, 2), nullable=False)   # máximo 99,999,999.99
    duracion = Column(Integer, nullable=False)        # en días
    estado = Column(String(20), nullable=False, default="activo")


class membresiasModel(Base):
    __tablename__ = "membresias_usuario"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(Integer, ForeignKey("planes.id", ondelete="RESTRICT"), nullable=False)
    fecha_inicio = Column(DateTime, nullable=False)
    fecha_fin = Column(DateTime, nullable=False)
    estado = Column(String(50), nullable=False, default="activa")
    creado_en = Column(DateTime, default=datetime.now)