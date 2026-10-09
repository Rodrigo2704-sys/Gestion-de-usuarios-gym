from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.roles import Rol  # noqa: F401  (re-exportado para los routers)
from app.core.security import decodificar_token
from app.models.usuarios import UsuarioModel


def obtener_usuario_actual(
    claims: dict = Depends(decodificar_token),
    db: Session = Depends(get_db),
) -> UsuarioModel:
    # El 'sub' del token es el ID del usuario, así cambiar el correo no invalida la sesión.
    try:
        usuario_id = int(claims["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buscamos al usuario y, con 'joinedload', traemos su Rol en la misma consulta.
    usuario = (
        db.query(UsuarioModel)
        .options(joinedload(UsuarioModel.rol))
        .filter(UsuarioModel.id == usuario_id)
        .first()
    )

    # Si el usuario no existe o su cuenta fue desactivada (activo=False)
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # NUEVO: revocación de sesiones. Al cambiar o restablecer la contraseña, la
    # token_version del usuario sube y los tokens emitidos antes dejan de servir
    # (si alguien había robado la sesión, queda expulsado de inmediato).
    if claims["tv"] != usuario.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada. Inicia sesión de nuevo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return usuario


# Si el rol_id del usuario no es el de administrador (1), se rechaza con 403.
def solo_administradores(
    usuario_actual: UsuarioModel = Depends(obtener_usuario_actual),
) -> UsuarioModel:
    if usuario_actual.rol_id != Rol.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requieren privilegios de Administrador.",
        )
    return usuario_actual