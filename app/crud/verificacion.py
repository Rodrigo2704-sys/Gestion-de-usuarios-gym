# app/crud/verificacion.py
"""Códigos de un solo uso (verificar correo / recuperar contraseña).

Seguridad:
- El código se genera con `secrets` (criptográficamente seguro), no con `random`.
- En la BD solo se guarda su HMAC-SHA256 (con SECRET_KEY): si alguien filtra la tabla,
  no obtiene los códigos.
- Vence a los CODIGO_EXPIRA_MINUTOS, se puede usar una sola vez y tiene un máximo de
  intentos fallidos; al pasarlo, el código queda inservible y hay que pedir otro.
- Pedir un código nuevo invalida los anteriores y respeta un tiempo de espera.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import (
    CODIGO_EXPIRA_MINUTOS,
    CODIGO_MAX_INTENTOS,
    CODIGO_REENVIO_SEGUNDOS,
    SECRET_KEY,
)
from app.core.security import hash_password
from app.crud.usuarios import obtener_usuario_por_correo
from app.models.usuarios import CodigoVerificacionModel as Codigo
from app.models.usuarios import ahora_utc

PROPOSITO_VERIFICAR = "verificar_correo"
PROPOSITO_RECUPERAR = "recuperar_password"


class CodigoReciente(Exception):
    """Se pidió un código hace muy poco; hay que esperar antes de pedir otro."""


def _generar_codigo() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _hash_codigo(usuario_id: int, proposito: str, codigo: str) -> str:
    mensaje = f"{usuario_id}:{proposito}:{codigo}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def crear_codigo(db: Session, usuario_id: int, proposito: str) -> str:
    """Crea un código nuevo, invalida los anteriores y devuelve el código EN CLARO
    (para enviarlo por correo; nunca se vuelve a poder leer de la BD)."""
    ahora = ahora_utc()
    try:
        ultimo = (
            db.query(Codigo)
            .filter(Codigo.usuario_id == usuario_id, Codigo.proposito == proposito)
            .order_by(Codigo.id.desc())
            .first()
        )
        if ultimo and (ahora - ultimo.creado_en).total_seconds() < CODIGO_REENVIO_SEGUNDOS:
            raise CodigoReciente("Espera un momento antes de pedir otro código.")

        # Los códigos anteriores sin usar dejan de servir.
        (
            db.query(Codigo)
            .filter(
                Codigo.usuario_id == usuario_id,
                Codigo.proposito == proposito,
                Codigo.usado.is_(False),
            )
            .update({"usado": True}, synchronize_session=False)
        )

        # Limpieza: borra códigos viejos (más de 1 día vencidos) para que la tabla no crezca.
        (
            db.query(Codigo)
            .filter(Codigo.expira_en < ahora - timedelta(days=1))
            .delete(synchronize_session=False)
        )

        codigo = _generar_codigo()
        db.add(
            Codigo(
                usuario_id=usuario_id,
                proposito=proposito,
                codigo_hash=_hash_codigo(usuario_id, proposito, codigo),
                expira_en=ahora + timedelta(minutes=CODIGO_EXPIRA_MINUTOS),
                creado_en=ahora,
            )
        )
        db.commit()
        return codigo
    except Exception:
        db.rollback()
        raise


def _validar_codigo(db: Session, usuario_id: int, proposito: str, codigo: str) -> bool:
    """True si el código es correcto. En ese caso lo marca como usado pero NO hace commit:
    quien llama confirma junto con su propio cambio (así todo ocurre en una sola transacción).
    Si es incorrecto, el intento fallido SÍ se guarda de inmediato."""
    registro = (
        db.query(Codigo)
        .filter(
            Codigo.usuario_id == usuario_id,
            Codigo.proposito == proposito,
            Codigo.usado.is_(False),
            Codigo.expira_en > ahora_utc(),
        )
        .order_by(Codigo.id.desc())
        .with_for_update()  # evita que dos peticiones simultáneas se salten el límite de intentos
        .first()
    )
    if not registro or registro.intentos >= CODIGO_MAX_INTENTOS:
        return False

    esperado = _hash_codigo(usuario_id, proposito, codigo)
    if not hmac.compare_digest(registro.codigo_hash, esperado):
        registro.intentos += 1
        db.commit()
        return False

    registro.usado = True
    db.flush()
    return True


def verificar_correo(db: Session, correo: str, codigo: str) -> bool:
    """Marca el correo como verificado si el código es correcto."""
    usuario = obtener_usuario_por_correo(db, correo)
    if not usuario or not usuario.activo or usuario.correo_verificado:
        return False

    try:
        if not _validar_codigo(db, usuario.id, PROPOSITO_VERIFICAR, codigo):
            return False
        usuario.correo_verificado = True
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def restablecer_password(db: Session, correo: str, codigo: str, password_nueva: str) -> bool:
    """Cambia la contraseña si el código es correcto. Como el usuario demostró que controla
    su bandeja de entrada, también deja el correo como verificado."""
    usuario = obtener_usuario_por_correo(db, correo)
    if not usuario or not usuario.activo:
        return False

    try:
        if not _validar_codigo(db, usuario.id, PROPOSITO_RECUPERAR, codigo):
            return False
        usuario.password = hash_password(password_nueva)
        usuario.correo_verificado = True
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise