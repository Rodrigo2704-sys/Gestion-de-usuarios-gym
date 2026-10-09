# app/routers/auth.py
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.correo import (
    enviar_aviso_cambio_password,
    enviar_codigo_recuperacion,
    enviar_codigo_verificacion,
)
from app.core.database import get_db
from app.core.limiter import limiter
from app.crud.usuarios import obtener_usuario_por_correo
from app.crud.verificacion import (
    PROPOSITO_RECUPERAR,
    PROPOSITO_VERIFICAR,
    CodigoReciente,
    crear_codigo,
    restablecer_password,
    verificar_correo,
)
from app.schemas.auth import RestablecerPassword, SolicitudCorreo, VerificarCorreo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usuarios", tags=["Verificación y recuperación"])

_ENVIADORES = {
    PROPOSITO_VERIFICAR: enviar_codigo_verificacion,
    PROPOSITO_RECUPERAR: enviar_codigo_recuperacion,
}

# Respuesta idéntica exista o no el correo: así nadie puede descubrir qué correos
# están registrados usando estos endpoints.
MSG_SOLICITUD = "Si el correo está registrado, recibirás un código en unos minutos."
MSG_CODIGO_INVALIDO = "Código inválido o expirado."


def emitir_codigo(db: Session, usuario, proposito: str, tareas: BackgroundTasks) -> None:
    """Crea el código y programa el envío del correo DESPUÉS de responder al cliente
    (el SMTP es lento y, además, así la respuesta tarda igual exista o no el usuario).
    Nunca lanza errores: si algo falla se registra y el usuario puede pedir otro código."""
    correo, nombre = usuario.correo, usuario.nombre
    try:
        codigo = crear_codigo(db, usuario.id, proposito)
    except CodigoReciente:
        return  # pidió otro código hace muy poco; se ignora en silencio
    except SQLAlchemyError:
        logger.exception("Error de BD al crear código (%s) para el usuario %s", proposito, usuario.id)
        return
    tareas.add_task(_ENVIADORES[proposito], correo, nombre, codigo)


# ---------------------------------------------------------------------------
# VERIFICAR CORREO (después del registro)
# ---------------------------------------------------------------------------
@router.post("/verificar-correo")
@limiter.limit("5/minute")
def verificar_correo_endpoint(
    request: Request,  # obligatorio para que slowapi funcione
    datos: VerificarCorreo,
    db: Session = Depends(get_db),
):
    try:
        verificado = verificar_correo(db, datos.correo, datos.codigo)
    except SQLAlchemyError:
        logger.exception("Error de BD al verificar correo")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al verificar el correo.",
        )

    if not verificado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MSG_CODIGO_INVALIDO)

    return {"Exito": True, "Mensaje": "Correo verificado correctamente. Ya puedes iniciar sesión."}


# ---------------------------------------------------------------------------
# REENVIAR CÓDIGO DE VERIFICACIÓN
# ---------------------------------------------------------------------------
@router.post("/reenviar-codigo")
@limiter.limit("3/minute")
def reenviar_codigo(
    request: Request,
    datos: SolicitudCorreo,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
):
    usuario = obtener_usuario_por_correo(db, datos.correo)
    if usuario and usuario.activo and not usuario.correo_verificado:
        emitir_codigo(db, usuario, PROPOSITO_VERIFICAR, tareas)
    return {"Exito": True, "Mensaje": MSG_SOLICITUD}


# ---------------------------------------------------------------------------
# OLVIDÉ MI CONTRASEÑA: paso 1 (pedir código)
# ---------------------------------------------------------------------------
@router.post("/olvide-password")
@limiter.limit("3/minute")
def olvide_password(
    request: Request,
    datos: SolicitudCorreo,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
):
    usuario = obtener_usuario_por_correo(db, datos.correo)
    if usuario and usuario.activo:
        emitir_codigo(db, usuario, PROPOSITO_RECUPERAR, tareas)
    return {"Exito": True, "Mensaje": MSG_SOLICITUD}


# ---------------------------------------------------------------------------
# OLVIDÉ MI CONTRASEÑA: paso 2 (código + contraseña nueva)
# ---------------------------------------------------------------------------
@router.post("/restablecer-password")
@limiter.limit("5/minute")
def restablecer_password_endpoint(
    request: Request,
    datos: RestablecerPassword,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        cambiada = restablecer_password(db, datos.correo, datos.codigo, datos.password_nueva)
        usuario = obtener_usuario_por_correo(db, datos.correo) if cambiada else None
        destino = (usuario.correo, usuario.nombre) if usuario else None
    except SQLAlchemyError:
        logger.exception("Error de BD al restablecer contraseña")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al restablecer la contraseña.",
        )

    if not cambiada:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MSG_CODIGO_INVALIDO)

    # NUEVO: aviso de seguridad por correo (se envía después de responder).
    if destino:
        tareas.add_task(enviar_aviso_cambio_password, *destino)

    return {"Exito": True, "Mensaje": "Contraseña actualizada. Ya puedes iniciar sesión."}