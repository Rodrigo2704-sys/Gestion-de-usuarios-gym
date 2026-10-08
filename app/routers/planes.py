import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import obtener_usuario_actual, solo_administradores
from app.crud.planes import (
    MembresiaActivaExistente,
    PlanNoDisponible,
    UsuarioNoEncontrado,
    actualizar_membresia,
    asignar_membresia,
    consultar_planes,
    crear_plan,
    membresia_usuario_por_id,
)
from app.schemas.planes import (
    ActualizarMembresia,
    AsignarMembresia,
    DatosPlan,
    SalidaMembresia,
    SalidaPlan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planes", tags=["Planes"])

# CORRECCIÓN (general): se quitaron los `db.rollback()` de los except SQLAlchemyError de
# este archivo. El CRUD ya hace rollback antes de relanzar el error, así que aquí eran
# redundantes. El except se mantiene porque sigue siendo el que devuelve el 500 al cliente.


# 1. CREAR PLAN (solo admin)
@router.post("/crear", response_model=SalidaPlan, status_code=status.HTTP_201_CREATED)
def creacion_plan(
    datos: DatosPlan,
    db: Session = Depends(get_db),
    admin=Depends(solo_administradores),
):
    try:
        return crear_plan(db, datos)
    except SQLAlchemyError:
        logger.exception("Error de BD al crear plan")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error en la base de datos al intentar crear el plan.",
        )


# 2. LISTAR PLANES ACTIVOS (cualquier usuario autenticado)
@router.get("/obtener", response_model=List[SalidaPlan])
def listar_planes_activos(
    db: Session = Depends(get_db),
    usuario_actual=Depends(obtener_usuario_actual),
):
    return consultar_planes(db)


# 3. ASIGNAR MEMBRESÍA (solo admin)
@router.post("/asignar", response_model=SalidaMembresia, status_code=status.HTTP_201_CREATED)
def endpoint_asignar_membresia(
    datos: AsignarMembresia,
    db: Session = Depends(get_db),
    admin=Depends(solo_administradores),
):
    try:
        return asignar_membresia(db, datos)
    except UsuarioNoEncontrado:
        # Cubre tanto "no existe" como "está desactivado" (el CRUD lanza esta excepción en ambos casos).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario indicado no existe o está desactivado.",
        )
    except PlanNoDisponible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El plan indicado no existe o está inactivo.",
        )
    except MembresiaActivaExistente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya tiene una membresía activa vigente.",
        )
    except SQLAlchemyError:
        logger.exception("Error de BD al asignar membresía")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al intentar asignar la membresía.",
        )


# 4. ACTUALIZAR MEMBRESÍA (solo admin)
@router.put("/actualizar-plan/{usuario_id}", response_model=SalidaMembresia)
def endpoint_actualizar_membresia(
    usuario_id: int,
    datos: ActualizarMembresia,
    db: Session = Depends(get_db),
    admin=Depends(solo_administradores),
):
    # CORRECCIÓN: model_dump() solo existe en Pydantic v2. Se usa el mismo patrón que en el
    # router de usuarios para que funcione tanto en v2 (model_dump) como en v1 (dict).
    if hasattr(datos, "model_dump"):  # Pydantic v2
        campos_enviados = datos.model_dump(exclude_unset=True)
    else:  # Pydantic v1
        campos_enviados = datos.dict(exclude_unset=True)

    if not campos_enviados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe enviar al menos un campo para actualizar (plan_id o estado).",
        )

    try:
        membresia = actualizar_membresia(db, usuario_id=usuario_id, datos=datos)
    except PlanNoDisponible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El plan indicado no existe o está inactivo.",
        )
    except SQLAlchemyError:
        logger.exception("Error de BD al actualizar membresía del usuario %s", usuario_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al intentar actualizar la membresía.",
        )

    if not membresia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró una membresía registrada para este usuario.",
        )

    return membresia


# 5. VER MIS MEMBRESÍAS (cualquier usuario autenticado)
@router.get("/mi-membresia", response_model=List[SalidaMembresia])
def ver_mi_membresia(
    db: Session = Depends(get_db),
    usuario_actual=Depends(obtener_usuario_actual),
):
    # Siempre se filtra por el id del token, nunca por un id enviado por el cliente.
    return membresia_usuario_por_id(db, usuario_id=usuario_actual.id)