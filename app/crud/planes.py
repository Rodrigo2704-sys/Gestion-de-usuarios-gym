from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.planes import membresiasModel, planesModel
from app.models.usuarios import UsuarioModel
from app.schemas.planes import ActualizarMembresia, AsignarMembresia, DatosPlan

# CORRECCIÓN: se eliminaron los imports duplicados (datetime/timedelta estaban dos veces)
# y los que no se usaban (IntegrityError y SQLAlchemyError). Todos los imports
# quedan juntos arriba, que es donde deben estar.

# Valores de estado tal como están en la BD (planes usa "activo", membresías "activa").
PLAN_ACTIVO = "activo"
MEMBRESIA_ACTIVA = "activa"


# Errores de negocio: el router los traduce a 404 / 409 con mensajes distintos.
class UsuarioNoEncontrado(Exception):
    pass


class PlanNoDisponible(Exception):
    """El plan no existe o está inactivo."""


class MembresiaActivaExistente(Exception):
    pass


# ==========================================
# PLANES
# ==========================================
def crear_plan(db: Session, plan: DatosPlan):
    db_plan = planesModel(
        tipo=plan.tipo,
        precio=plan.precio,
        duracion=plan.duracion,
    )
    try:
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)
        return db_plan
    except Exception:
        db.rollback()  # Escudo: Limpia si falla la base de datos al crear un plan
        # CORRECCIÓN: `raise` a secas en vez de `raise e`, así se conserva el traceback original.
        raise


def consultar_planes(db: Session):
    return (
        db.query(planesModel)
        # CORRECCIÓN: PLAN_ACTIVE no existía (NameError). La constante se llama PLAN_ACTIVO.
        .filter(planesModel.estado == PLAN_ACTIVO)
        .order_by(planesModel.id)
        .all()
    )


def _obtener_plan_activo(db: Session, plan_id: int):
    return (
        db.query(planesModel)
        # CORRECCIÓN: mismo error de nombre (PLAN_ACTIVE -> PLAN_ACTIVO).
        .filter(planesModel.id == plan_id, planesModel.estado == PLAN_ACTIVO)
        .first()
    )


# ==========================================
# MEMBRESÍAS
# ==========================================
def asignar_membresia(db: Session, datos: AsignarMembresia):
    plan = _obtener_plan_activo(db, datos.plan_id)
    if not plan:
        # ¡MEJORA! Le metemos el texto personalizado adentro al letrero
        raise PlanNoDisponible("El plan seleccionado no existe o se encuentra inactivo.")

    try:
        # with_for_update bloquea la fila del usuario hasta el commit: si dos
        # administradores asignan a la vez, el segundo espera y ve la membresía
        # que creó el primero (evita duplicados por condición de carrera).
        usuario = (
            db.query(UsuarioModel)
            .filter(UsuarioModel.id == datos.usuario_id)
            .with_for_update()
            .first()
        )
        if not usuario:
            raise UsuarioNoEncontrado("El ID del usuario no existe en la base de datos.")

        # CORRECCIÓN (nueva): eliminar_usuario hace borrado lógico (activo=False), así que la fila
        # sigue existiendo. Sin esta validación, un admin podía asignarle un plan a una cuenta
        # "eliminada". Se reutiliza UsuarioNoEncontrado para que el router lo devuelva como 404.
        if not usuario.activo:
            raise UsuarioNoEncontrado("El usuario está desactivado.")

        # NOTA: datetime.now() es "naive" (sin zona horaria). Se deja así a propósito
        # para que sea consistente con lo que guarda tu BD. Si algún día migras a UTC,
        # cámbialo aquí Y en la columna, no solo en un lado.
        ahora = datetime.now()

        vigente = (
            db.query(membresiasModel)
            .filter(
                membresiasModel.usuario_id == datos.usuario_id,
                membresiasModel.estado == MEMBRESIA_ACTIVA,
                membresiasModel.fecha_fin > ahora,
            )
            .first()
        )
        if vigente:
            raise MembresiaActivaExistente("El usuario ya cuenta con una membresía activa en este momento.")

        asignacion = membresiasModel(
            usuario_id=datos.usuario_id,
            plan_id=datos.plan_id,
            fecha_inicio=ahora,
            fecha_fin=ahora + timedelta(days=plan.duracion),
            # 'estado' lo asigna la BD ('activa' por defecto)
        )

        db.add(asignacion)
        db.commit()
        db.refresh(asignacion)
        return asignacion

    # CORRECCIÓN: antes había dos `except` que hacían exactamente lo mismo (rollback + raise).
    # Se unificaron en uno. Es importante que el rollback siga aquí incluso para los errores
    # de negocio: libera el bloqueo de with_for_update para que otro admin no quede esperando.
    except Exception:
        db.rollback()  # Limpia la sesión ante errores de negocio O fallas técnicas de MySQL
        raise          # Relanza el error tal cual para que el router decida el HTTP Status


def actualizar_membresia(db: Session, usuario_id: int, datos: ActualizarMembresia):
    # Un usuario puede tener varias membresías (historial): se actualiza la más reciente.
    membresia = (
        db.query(membresiasModel)
        .filter(membresiasModel.usuario_id == usuario_id)
        .order_by(membresiasModel.id.desc())
        .first()
    )
    if not membresia:
        return None

    if datos.plan_id is not None:
        if not _obtener_plan_activo(db, datos.plan_id):
            raise PlanNoDisponible("El nuevo plan seleccionado no está disponible o no existe.")
        # OJO: cambiar el plan NO recalcula fecha_fin. Si tu regla de negocio
        # es que el nuevo plan empiece de nuevo, hay que hacerlo aquí.
        membresia.plan_id = datos.plan_id

    if datos.estado is not None:
        membresia.estado = getattr(datos.estado, "value", datos.estado)

    # CORRECCIÓN: se quitó `except PlanNoDisponible`. Esa excepción se lanza ANTES del try,
    # así que ese bloque nunca se ejecutaba (código muerto). Además, si el plan es inválido
    # no se ha modificado nada todavía, por lo que no hay nada que revertir.
    try:
        db.commit()
        db.refresh(membresia)
        return membresia
    except Exception:
        db.rollback()
        raise


def membresia_usuario_por_id(db: Session, usuario_id: int):
    """Todas las membresías del usuario, de la más reciente a la más antigua."""
    return (
        db.query(membresiasModel)
        .filter(membresiasModel.usuario_id == usuario_id)
        .order_by(membresiasModel.id.desc())
        .all()
    )