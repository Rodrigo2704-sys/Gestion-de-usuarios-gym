from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import LOGIN_BLOQUEO_MINUTOS, LOGIN_MAX_INTENTOS
from app.core.roles import Rol
from app.core.security import hash_password, verificar_contraseña
from app.models.usuarios import UsuarioModel, ahora_utc
from app.schemas.usuarios import EntradaRegistro


# ==========================================
# ERRORES DE NEGOCIO
# ==========================================
# El CRUD lanza excepciones propias y el ROUTER decide qué status HTTP devolver.
# Así la capa de datos no depende de FastAPI.
class CorreoYaRegistrado(Exception):
    """El correo ya pertenece a otro usuario (regla UNIQUE de MySQL)."""


class RolInvalido(Exception):
    """El rol_id enviado no existe en el enum Rol."""


# Filtro de seguridad: solo permite editar estas columnas.
CAMPOS_EDITABLES = {"nombre", "correo", "activo"}

# Escudo contra ataques de sincronización: si un correo no existe, gastamos tiempo verificando
# este hash falso para que el servidor tarde lo mismo y no se sepa qué correos existen.
_HASH_FALSO = hash_password("hash-falso-para-igualar-tiempos")


# Quita espacios y pasa el correo a minúsculas para evitar errores al loguearse.
def _normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


# MySQL usa el código 1062 para "Duplicate entry"; solo en ese caso es un correo repetido.
def _es_correo_duplicado(error: IntegrityError) -> bool:
    args = getattr(error.orig, "args", ())
    return bool(args) and args[0] == 1062


# ==========================================
# BLOQUEO DE CUENTA (anti fuerza bruta por cuenta, no solo por IP)
# ==========================================
def _esta_bloqueado(usuario: UsuarioModel) -> bool:
    return usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora_utc()


def _registrar_fallo(db: Session, usuario: UsuarioModel) -> None:
    """Suma un intento fallido; al llegar al máximo bloquea la cuenta un rato."""
    try:
        # UPDATE atómico (intentos = intentos + 1): si llegan varias peticiones a la vez
        # no se pierden cuentas.
        db.query(UsuarioModel).filter(UsuarioModel.id == usuario.id).update(
            {UsuarioModel.intentos_fallidos: UsuarioModel.intentos_fallidos + 1},
            synchronize_session=False,
        )
        db.commit()
        db.refresh(usuario)

        if usuario.intentos_fallidos >= LOGIN_MAX_INTENTOS:
            usuario.bloqueado_hasta = ahora_utc() + timedelta(minutes=LOGIN_BLOQUEO_MINUTOS)
            usuario.intentos_fallidos = 0
            db.commit()
    except Exception:
        db.rollback()
        raise


def _limpiar_fallos(db: Session, usuario: UsuarioModel) -> None:
    if usuario.intentos_fallidos or usuario.bloqueado_hasta:
        try:
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = None
            db.commit()
        except Exception:
            db.rollback()
            raise


def confirmar_password(db: Session, usuario: UsuarioModel, password: str) -> bool:
    """Comprueba la contraseña de un usuario YA autenticado (cambiar contraseña,
    cambiar correo). Comparte el contador de intentos del login: quien tenga un token
    robado no puede adivinar la contraseña actual sin límite."""
    if _esta_bloqueado(usuario):
        return False
    if not verificar_contraseña(password, usuario.password):
        _registrar_fallo(db, usuario)
        return False
    return True


def iniciar_sesion(db: Session, email: str, contraseña_ingresada: str):
    usuario = (
        db.query(UsuarioModel)
        .options(joinedload(UsuarioModel.rol))
        .filter(UsuarioModel.correo == _normalizar_correo(email))
        .first()
    )

    # Correo inexistente: se gasta el mismo tiempo que con un usuario real.
    if not usuario:
        verificar_contraseña(contraseña_ingresada, _HASH_FALSO)
        return None

    # NUEVO: cuenta bloqueada por demasiados intentos. Se rechaza incluso con la
    # contraseña correcta (si no, el bloqueo no serviría) y se gasta el mismo tiempo.
    # La respuesta es la misma que una contraseña incorrecta.
    if _esta_bloqueado(usuario):
        verificar_contraseña(contraseña_ingresada, _HASH_FALSO)
        return None

    if not verificar_contraseña(contraseña_ingresada, usuario.password):
        _registrar_fallo(db, usuario)
        return None

    # Borrado lógico: una cuenta desactivada no entra. Se revisa DESPUÉS de verificar la
    # contraseña para no revelar si la cuenta existe/está desactivada.
    if not usuario.activo:
        return None

    _limpiar_fallos(db, usuario)
    return usuario


def registrar_usuario(db: Session, usuario: EntradaRegistro):
    db_usuario = UsuarioModel(
        nombre=usuario.nombre,
        correo=_normalizar_correo(usuario.correo),
        password=hash_password(usuario.password),
        rol_id=int(Rol.CLIENTE),
    )

    try:
        db.add(db_usuario)
        db.commit()  # Aquí MySQL saltará si el correo ya existe
        db.refresh(db_usuario)

        # Forzamos la carga de la relación 'rol' ANTES del return: si no, el esquema de
        # salida (Pydantic) intentaría leerla perezosamente y podría fallar.
        _ = db_usuario.rol

        return db_usuario

    except IntegrityError as e:
        db.rollback()
        # Solo es "correo duplicado" si es un Duplicate entry (1062). Cualquier otro
        # IntegrityError se relanza tal cual para no mentirle al usuario.
        if _es_correo_duplicado(e):
            raise CorreoYaRegistrado("El correo electrónico ya se encuentra registrado.")
        raise
    except Exception:
        db.rollback()
        raise


def actualizar_rol_usuario_crud(db: Session, usuario_id: int, nuevo_rol_id: int):
    # El rol inválido lanza RolInvalido; None significa únicamente "usuario no encontrado".
    if nuevo_rol_id not in {rol.value for rol in Rol}:
        raise RolInvalido("El rol indicado no es válido.")

    usuario = obtener_usuario_por_id(db, usuario_id)
    if not usuario:
        return None

    try:
        usuario.rol_id = nuevo_rol_id
        db.commit()
        db.refresh(usuario)
        _ = usuario.rol
        return usuario
    except Exception:
        db.rollback()
        raise


def obtener_usuario_por_correo(db: Session, correo: str):
    return (
        db.query(UsuarioModel)
        .options(joinedload(UsuarioModel.rol))
        .filter(UsuarioModel.correo == _normalizar_correo(correo))
        .first()
    )


def obtener_usuario_por_id(db: Session, usuario_id: int):
    return (
        db.query(UsuarioModel)
        .options(joinedload(UsuarioModel.rol))
        .filter(UsuarioModel.id == usuario_id)
        .first()
    )


def obtener_todos_los_usuarios(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(UsuarioModel)
        .options(joinedload(UsuarioModel.rol))  # evita una consulta extra por usuario
        .order_by(UsuarioModel.id)              # sin orden, la paginación es inestable
        .offset(skip)
        .limit(limit)
        .all()
    )


def actualizar_usuario(db: Session, usuario_id: int, datos_actualizacion: dict):
    db_usuario = obtener_usuario_por_id(db, usuario_id)
    if not db_usuario:
        return None

    for campo, valor in datos_actualizacion.items():
        # Lista blanca de campos editables.
        if campo not in CAMPOS_EDITABLES:
            continue

        if campo == "correo":
            valor = _normalizar_correo(valor)
            # Un correo nuevo vuelve a quedar sin verificar.
            if valor != db_usuario.correo:
                db_usuario.correo_verificado = False

        setattr(db_usuario, campo, valor)

    try:
        db.commit()
        db.refresh(db_usuario)
        _ = db_usuario.rol  # fuerza la carga del Rol para que el esquema no falle
        return db_usuario
    except IntegrityError as e:  # correo ya usado por otro usuario (regla UNIQUE)
        db.rollback()
        if _es_correo_duplicado(e):
            raise CorreoYaRegistrado("El correo electrónico ya se encuentra registrado por otro usuario.")
        raise
    except Exception:
        db.rollback()
        raise


def cambiar_password(
    db: Session, usuario: UsuarioModel, password_actual: str, password_nueva: str
) -> bool:
    """Devuelve False si la contraseña actual no coincide (o la cuenta está bloqueada).

    Al cambiarla sube token_version: TODOS los tokens anteriores (otros dispositivos,
    un atacante con sesión robada) dejan de servir. El router entrega un token nuevo
    para que la sesión actual continúe.
    """
    if not confirmar_password(db, usuario, password_actual):
        return False

    try:
        usuario.password = hash_password(password_nueva)
        # Expresión SQL (token_version + 1): atómica, sin carreras.
        usuario.token_version = UsuarioModel.token_version + 1
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        db.commit()
        db.refresh(usuario)  # recarga el token_version real para emitir el token nuevo
        return True
    except Exception:
        db.rollback()
        raise


def eliminar_usuario(db: Session, usuario_id: int):
    """Borrado lógico: desactiva la cuenta y conserva su historial (membresías, ventas).

    Un DELETE real borraría en cascada las membresías del usuario.
    Para reactivarlo, un admin envía {"activo": true} al PATCH.
    """
    db_usuario = obtener_usuario_por_id(db, usuario_id)
    if not db_usuario:
        return None

    try:
        db_usuario.activo = False
        db.commit()
        return db_usuario
    except Exception:
        db.rollback()
        raise