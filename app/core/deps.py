from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
 
from app.core.database import get_db
from app.core.roles import Rol  # noqa: F401  (re-exportado para los routers)
from app.core.security import verificar_token
from app.models.usuarios import UsuarioModel
 
 
def obtener_usuario_actual(
    sub: str = Depends(verificar_token),
    db: Session = Depends(get_db),
) -> UsuarioModel:#esperamos que nos triaga como respuesta los datos de la columna

    # El 'sub' del token es el ID del usuario, así cambiar el correo no
    # invalida la sesión.
    try:
        usuario_id = int(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
 
    # Buscamos al usuario en la DB y con 'joinedload' nos traemos su Rol en una sola consulta rápida.
    usuario = db.query(UsuarioModel).options(joinedload(UsuarioModel.rol)).filter(UsuarioModel.id == usuario_id).first()
 
    # Si el usuario no existe en la base de datos o su cuenta fue desactivada (activo=False)
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
            # Le avisa a Swagger que debe revocar los permisos del candado de inmediato.
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return usuario

 #Que pasa si no es adminsitrador? pues si el actual rol_id que puede ser 2, entonces si es diferente al 1 (que es el del admin) pues rechazara y saldra un eror de acceso denegado., sino pues obtenemos el usuario actual
def solo_administradores(
    usuario_actual: UsuarioModel = Depends(obtener_usuario_actual),
) -> UsuarioModel:
    if usuario_actual.rol_id != Rol.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requieren privilegios de Administrador.",
        )
    return usuario_actual