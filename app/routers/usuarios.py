import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fastapi import BackgroundTasks
from app.crud.verificacion import PROPOSITO_VERIFICAR
from app.routers.auth import emitir_codigo

from app.core.database import get_db
from app.core.deps import Rol, obtener_usuario_actual, solo_administradores
from app.core.limiter import limiter
from app.core.security import crear_token_acceso
from app.crud.usuarios import (
    # CORRECCIÓN: se importan las excepciones de negocio nuevas del CRUD.
    CorreoYaRegistrado,
    RolInvalido,
    actualizar_rol_usuario_crud,
    actualizar_usuario,
    cambiar_password,
    eliminar_usuario,
    iniciar_sesion,
    obtener_todos_los_usuarios,
    obtener_usuario_por_correo,
    obtener_usuario_por_id,
    registrar_usuario,
)
from app.schemas.usuarios import (
    ActualizarUsuario,
    CambiarPassword,
    EntradaRegistro,
    SalidaUsuario,
)

# CORRECCIÓN: se quitó el import de IntegrityError y la función _es_duplicado().
# Esa lógica ahora vive en el CRUD (_es_correo_duplicado) y el router solo recibe
# CorreoYaRegistrado, así no se repite en dos capas.

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

# Campos que nadie puede cambiar por el PATCH general (el rol tiene su endpoint).
CAMPOS_PROHIBIDOS = {"id", "rol_id"}
# Campos que solo un administrador puede cambiar.
CAMPOS_SOLO_ADMIN = {"activo"}


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------
@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = iniciar_sesion(
        db, email=form_data.username, contraseña_ingresada=form_data.password
    )

    # 1. EMBA'APO RAẼ KÓVA: Ehecha usuario oĩpa (noĩri ramõ, None hína)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico térã contraseña oĩ vai.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. AG̃A SÍ: Reikuaáma usuario OĨMA de verdad, upémarõ remaña ikatu rehecha correo_verificado
    if not usuario.correo_verificado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu correo electrónico antes de iniciar sesión.",
        )

    nombre_rol = usuario.rol.nombre

    access_token = crear_token_acceso(
        datos={"sub": str(usuario.id), "rol": nombre_rol}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "nombre": usuario.nombre,
        "rol": nombre_rol,
    }

# ---------------------------------------------------------------------------
# REGISTRO (pública)
# ---------------------------------------------------------------------------
@router.post(
    "/registrar",
    response_model=SalidaUsuario,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")
def crear_nuevo_usuario(
    request: Request,
    datos: EntradaRegistro,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Revisión rápida previa. Ojo: NO es suficiente por sí sola (dos peticiones simultáneas
    # pueden pasarla), por eso abajo también se captura CorreoYaRegistrado del CRUD.
    # CORRECCIÓN: 400 -> 409 (Conflict), que es el código correcto para un recurso duplicado.
    if obtener_usuario_por_correo(db, correo=datos.correo):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo ya se encuentra registrado",
        )

    try:
        nuevo_usuario = registrar_usuario(db, usuario=datos)
    # CORRECCIÓN: este except va PRIMERO y es el que reemplaza a _es_duplicado().
    except CorreoYaRegistrado as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
    except SQLAlchemyError:
        db.rollback()  # (el CRUD ya hizo rollback; es redundante pero inofensivo)
        logger.exception("Error de BD al registrar usuario")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error inesperado en la base de datos al registrar el usuario",
        )

  # 1. Si no se pudo crear el usuario, lanzamos el error 500
    if not nuevo_usuario:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el usuario",
        )

    # 2. Si el usuario SÍ se creó, continuamos fuera del "if":
    # Generamos y enviamos el código de verificación por correo
    emitir_codigo(db, nuevo_usuario, PROPOSITO_VERIFICAR, tareas)

    # 3. Refrescamos la instancia para asegurarnos de tener todos los campos creados por la BD (como ID, fechas)
    db.refresh(nuevo_usuario)

    # 4. Forzamos la carga de la relación del rol para que Pydantic pueda serializarlo
    _ = nuevo_usuario.rol

    # 5. Retornamos la respuesta con el usuario registrado
    return nuevo_usuario

# ---------------------------------------------------------------------------
# CAMBIAR ROL (solo admin)
# ---------------------------------------------------------------------------
@router.patch("/{usuario_id}/cambiar-rol", response_model=SalidaUsuario)
def cambiar_rol_endpoint(
    usuario_id: int,
    nuevo_rol_id: int,
    db: Session = Depends(get_db),
    admin_actual=Depends(solo_administradores),
):
    if admin_actual.id == usuario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operación no permitida. No puedes cambiar tu propio rol de administrador.",
        )

    if nuevo_rol_id not in {Rol.ADMIN, Rol.CLIENTE}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol inválido. Solo se permite 1 (Admin) o 2 (Cliente).",
        )

    try:
        usuario_actualizado = actualizar_rol_usuario_crud(db, usuario_id, nuevo_rol_id)
    # CORRECCIÓN: el CRUD ahora lanza RolInvalido en vez de devolver None. Así el 400 (rol malo)
    # y el 404 (usuario inexistente) ya no se confunden.
    except RolInvalido as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de BD al cambiar rol del usuario %s", usuario_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al cambiar el rol.",
        )

    # Ahora None significa ÚNICAMENTE "usuario no encontrado".
    if not usuario_actualizado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    return usuario_actualizado


# ---------------------------------------------------------------------------
# LISTAR Y BUSCAR (solo admin)
# ---------------------------------------------------------------------------
@router.get("/buscar/correo", response_model=SalidaUsuario)
def obtener_usuario_por_correo_endpoint(
    email: str,
    db: Session = Depends(get_db),
    admin_actual=Depends(solo_administradores),
):
    usuario = obtener_usuario_por_correo(db, correo=email)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró ningún usuario con ese correo electrónico",
        )
    return usuario


@router.get("/", response_model=List[SalidaUsuario])
def listar_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_actual=Depends(solo_administradores),
):
    return obtener_todos_los_usuarios(db, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# OBTENER POR ID (dueño o admin)
# ---------------------------------------------------------------------------
@router.get("/{usuario_id}", response_model=SalidaUsuario)
def obtener_usuario_por_id_endpoint(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_actual=Depends(obtener_usuario_actual),
):
    # CORRECCIÓN (la más grave): en tu archivo, el cuerpo de este endpoint tenía pegado un
    # pedazo del PATCH (usaba `es_admin` y `datos_dict`, que aquí no existen -> NameError
    # en cada petición) y nunca buscaba al usuario. Lo reescribí con la lógica correcta:
    # solo el dueño o un admin pueden ver el perfil.
    es_admin = usuario_actual.rol_id == Rol.ADMIN

    if not es_admin and usuario_actual.id != usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver los datos de otro usuario.",
        )

    usuario = obtener_usuario_por_id(db, usuario_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )
    return usuario


# ---------------------------------------------------------------------------
# MODIFICAR (dueño o admin)
# ---------------------------------------------------------------------------
@router.patch("/{usuario_id}", response_model=SalidaUsuario)
def modificar_usuario(
    usuario_id: int,
    datos: ActualizarUsuario,
    db: Session = Depends(get_db),
    usuario_actual=Depends(obtener_usuario_actual),
):
    es_admin = usuario_actual.rol_id == Rol.ADMIN

    if not es_admin and usuario_actual.id != usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para modificar los datos de otro usuario.",
        )

    # Solo los campos que el cliente envió realmente.
    if hasattr(datos, "model_dump"):  # Pydantic v2
        datos_dict = datos.model_dump(exclude_unset=True)
    else:  # Pydantic v1
        datos_dict = datos.dict(exclude_unset=True)

    if not datos_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron datos para actualizar.",
        )

    # Anti escalada de privilegios.
    prohibidos = CAMPOS_PROHIBIDOS if es_admin else CAMPOS_PROHIBIDOS | CAMPOS_SOLO_ADMIN
    if prohibidos & datos_dict.keys():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar uno o más de los campos enviados.",
        )

    # Un admin no puede dejarse a sí mismo fuera del sistema.
    if datos_dict.get("activo") is False and usuario_actual.id == usuario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta.",
        )

    try:
        usuario_actualizado = actualizar_usuario(
            db=db, usuario_id=usuario_id, datos_actualizacion=datos_dict
        )
    # CORRECCIÓN: antes se detectaba el duplicado con _es_duplicado(); ahora el CRUD lanza
    # CorreoYaRegistrado y el router solo lo traduce a 409.
    except CorreoYaRegistrado as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de BD al actualizar usuario %s", usuario_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al actualizar el usuario.",
        )

    if not usuario_actualizado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    return usuario_actualizado


# ---------------------------------------------------------------------------
# ELIMINAR (solo admin)
# ---------------------------------------------------------------------------
@router.delete("/{usuario_id}")
def borrar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin_actual=Depends(solo_administradores),
):
    if admin_actual.id == usuario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operación no permitida. No puedes eliminar tu propia cuenta.",
        )

    try:
        usuario_eliminado = eliminar_usuario(db, usuario_id=usuario_id)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de BD al eliminar usuario %s", usuario_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al intentar desactivar el usuario.",
        )

    if not usuario_eliminado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    return {"Exito": True, "Mensaje": "Usuario desactivado correctamente"}


# ---------------------------------------------------------------------------
# CAMBIAR MI CONTRASEÑA (usuario autenticado, pide la actual)
# ---------------------------------------------------------------------------
@router.post("/cambiar-password")
@limiter.limit("5/minute")
def cambiar_password_endpoint(
    request: Request,  # obligatorio para que slowapi funcione
    datos: CambiarPassword,
    db: Session = Depends(get_db),
    usuario_actual=Depends(obtener_usuario_actual),
):
    try:
        cambiada = cambiar_password(
            db, usuario_actual, datos.password_actual, datos.password_nueva
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de BD al cambiar contraseña del usuario %s", usuario_actual.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la base de datos al cambiar la contraseña.",
        )

    if not cambiada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta.",
        )

    return {"Exito": True, "Mensaje": "Contraseña actualizada correctamente"}