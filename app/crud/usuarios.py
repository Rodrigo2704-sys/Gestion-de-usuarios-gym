from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.roles import Rol
from app.core.security import hash_password, verificar_contraseña
from app.models.usuarios import UsuarioModel
from app.schemas.usuarios import EntradaRegistro

# CORRECCIÓN: todos los imports quedan arriba y juntos. Antes había un
# `from sqlalchemy.exc import IntegrityError` repetido en medio del archivo, con un espacio
# al inicio de la línea (riesgo de IndentationError). Se quitó también SQLAlchemyError (no se usaba).
# CORRECCIÓN: ya NO se importa HTTPException ni status. Antes se usaban sin importarse (NameError)
# y además mezclaban la capa de datos con FastAPI. Ahora se usan excepciones propias (ver abajo).


# ==========================================
# ERRORES DE NEGOCIO
# ==========================================
# CORRECCIÓN: mismo patrón que en planes_crud.py. El CRUD lanza excepciones propias y el
# ROUTER decide qué status HTTP devolver (400/409/404...). Así la capa de datos no depende de FastAPI.
class CorreoYaRegistrado(Exception):
    """El correo ya pertenece a otro usuario (regla UNIQUE de MySQL)."""


class RolInvalido(Exception):
    """El rol_id enviado no existe en el enum Rol."""


# Filtro de seguridad: Solo permite editar estas columnas. Evita que alteren el rol o ID por la fuerza.
CAMPOS_EDITABLES = {"nombre", "correo", "activo"}

# Escudo contra Ataques de Sincronización: Si un correo no existe, gastamos tiempo verificando
# este hash falso para que el servidor tarde lo mismo y el hacker no sepa qué correos existen.
_HASH_FALSO = hash_password("hash-falso-para-igualar-tiempos")


# Limpiador de texto: Quita espacios y pasa el correo a minúsculas para evitar errores al loguearse.
def _normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


# CORRECCIÓN (nueva): antes se asumía que CUALQUIER IntegrityError era un correo duplicado.
# Pero también podría ser una llave foránea inválida (por ejemplo un rol_id que no existe).
# MySQL usa el código 1062 para "Duplicate entry"; solo en ese caso lo tratamos como correo repetido.
def _es_correo_duplicado(error: IntegrityError) -> bool:
    args = getattr(error.orig, "args", ())
    return bool(args) and args[0] == 1062


def iniciar_sesion(db: Session, email: str, contraseña_ingresada: str):
    usuario = (
        # Primero usa _normalizar_correo(email) para transformar el correo ingresado a minúsculas y quitarle espacios.
        # Usa joinedload(UsuarioModel.rol) para traerse de inmediato el Rol del usuario (si es administrador, cliente, etc.)
        # en esa misma consulta rápida.
        # CORRECCIÓN: se limpió el comentario (tenía restos pegados como "[12.1, 12.2]").
        db.query(UsuarioModel)
        .options(joinedload(UsuarioModel.rol))
        .filter(UsuarioModel.correo == _normalizar_correo(email))
        .first()
    )

    # El backend tarda el mismo tiempo que si el usuario existiera, protegiéndote contra los ataques de sincronización. Al final, devuelve None (Acceso denegado).

    if not usuario:
        verificar_contraseña(contraseña_ingresada, _HASH_FALSO)
        return None

    # Si el usuario sí existía en la base de datos, el código se salta el paso anterior y llega aquí.
    # (osea si no se ejecutó el verificar contraseña.)

    if not verificar_contraseña(contraseña_ingresada, usuario.password):
        return None

    # CORRECCIÓN (nueva, importante): eliminar_usuario hace borrado lógico (activo=False), pero antes
    # un usuario "eliminado" podía seguir iniciando sesión. Ahora se le niega el acceso.
    # Se revisa DESPUÉS de verificar la contraseña para no revelar si la cuenta existe/está desactivada.
    if not usuario.activo:
        return None

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
        db.commit()              # Aquí MySQL saltará si el correo ya existe
        db.refresh(db_usuario)

        # TRUCO TÉCNICO: Forzamos a SQLAlchemy a cargar la relación 'rol' en la memoria del servidor.
        # Es obligatorio hacerlo ANTES del 'return' porque la base de datos es "perezosa"
        # Si no tocamos el rol aquí, el esquema de salida de FastAPI (Pydantic) fallará al intentar armar el JSON,
        # ya que los datos del rol vendrán vacíos en la respuesta. Le obligamos que vaya a la tabla de roles ya que
        # los otros ya andan en memoria, por eso le obligamos que traiga todo a la fuerza
        _ = db_usuario.rol

        return db_usuario

    except IntegrityError as e:  # <--- ¡CAPTURAMOS EL CORREO DUPLICADO!
        db.rollback()            # Limpiamos la base de datos de inmediato
        # CORRECCIÓN: solo es "correo duplicado" si el error es realmente un Duplicate entry (1062).
        # Cualquier otro IntegrityError (FK inválida, etc.) se relanza tal cual para no mentirle al usuario.
        if _es_correo_duplicado(e):
            raise CorreoYaRegistrado("El correo electrónico ya se encuentra registrado.")
        raise
    except Exception:
        db.rollback()            # Por si pasa cualquier otro error inesperado
        raise


def actualizar_rol_usuario_crud(db: Session, usuario_id: int, nuevo_rol_id: int):
    # Genera el grupo de números válidos (ej. {1, 2}).
    # CORRECCIÓN: antes devolvía None tanto si el rol era inválido como si el usuario no existía,
    # y el router no podía dar mensajes distintos. Ahora el rol inválido lanza RolInvalido
    # y None significa únicamente "usuario no encontrado".
    if nuevo_rol_id not in {rol.value for rol in Rol}:
        raise RolInvalido("El rol indicado no es válido.")

    # Busca al usuario por su ID antes de intentar editarlo
    usuario = obtener_usuario_por_id(db, usuario_id)
    if not usuario:
        return None

    try:
        usuario.rol_id = nuevo_rol_id  # Aplica el nuevo número de rol
        db.commit()                     # Guarda en MySQL
        db.refresh(usuario)            # Sincroniza los datos
        _ = usuario.rol                # Carga el nuevo rol en memoria
        return usuario
    except Exception:
        db.rollback()                  # Si MySQL falla, limpia la sesión
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
    # Buscamos al usuario por su ID
    db_usuario = obtener_usuario_por_id(db, usuario_id)
    if not db_usuario:
        return None

    # Ciclo que revisa cada dato enviado
    for campo, valor in datos_actualizacion.items():
        # Lista blanca de campos editables (asegúrate de incluir "rol_id" aquí)
        if campo not in CAMPOS_EDITABLES:
            continue
            
        # Normalizamos el correo
        if campo == "correo":
            valor = _normalizar_correo(valor)
            if valor != db_usuario.correo:
                db_usuario.correo_verificado = False

        # Asignación dinámica
        setattr(db_usuario, campo, valor)

    try:
        db.commit()              # Intentamos guardar los cambios en MySQL
        db.refresh(db_usuario)   # Refrescamos los datos para tenerlos sincronizados
        _ = db_usuario.rol       # Fuerza la carga del objeto Rol para que el esquema no falle, nos trae es el nombre del rol que tiene el usuario
        return db_usuario
    except IntegrityError as e:  # Atrapamos el error si el correo ya existe en otro usuario (regla UNIQUE)
        db.rollback()            # Limpiamos la sesión de inmediato
        # CORRECCIÓN: mismo cambio que en registrar_usuario: excepción propia en vez de HTTPException,
        # y solo si de verdad es un duplicado.
        if _es_correo_duplicado(e):
            raise CorreoYaRegistrado("El correo electrónico ya se encuentra registrado por otro usuario.")
        raise
    except Exception:
        db.rollback()            # Si pasa cualquier otro error inesperado, limpia la base de datos
        raise


def cambiar_password(
    db: Session, usuario: UsuarioModel, password_actual: str, password_nueva: str
) -> bool:
    """Devuelve False si la contraseña actual no coincide."""
    if not verificar_contraseña(password_actual, usuario.password):
        return False

    try:
        usuario.password = hash_password(password_nueva)
        db.commit()
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