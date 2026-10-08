# app/core/security.py
from datetime import datetime, timedelta, timezone

import jwt #Identifica quién es el usuario en cada petición web.
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

# Configura Bcrypt, que es el estándar de la industria para encriptar contraseñas. Transforma contraseñas fáciles como 123456 en un revoltijo indescifrable

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Busca un candado en la parte superior derecha de la pantalla y, cuando el usuario ponga su token ahí, extrae el código de la cabecera oculta de la petición web
autenticacion = OAuth2PasswordBearer(tokenUrl="/usuarios/login")

#El algoritmo matemático Bcrypt tiene una limitación técnica: solo procesa los primeros 72 caracteres/bytes de una contraseña. Si alguien pone una contraseña de 100 letras, Bcrypt ignorará las últimas 28. 
MAX_PASSWORD_BYTES = 72

#Le prometemos que al final va devolver una respuesta de tipo str
def hash_password(password: str) -> str:
    #Es el "diccionario de traducción" universal más famoso del mundo. Le dice a la computadora exactamente qué número le corresponde a cada letra, emoticón o símbolo de cualquier idioma del planeta
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        #Si la contrasñea tiene mas de 72 bytes lanzara un error, sino devuelve la contraseña encriptada para enviarla a la base de datos.
        raise ValueError("La contraseña no puede superar los 72 bytes.")
    return pwd_context.hash(password)

#Le decimos al visualcode que al fianl la respuesta sera de tipo booleano
def verificar_contraseña(contraseña_ingresada: str, password_hashed: str) -> bool:
    # Contraseñas absurdamente largas: se rechazan en vez de provocar un 500.
    if len(contraseña_ingresada.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return False
    try:
        #Si la contraseña que ingreso el usuario(se convierte en hasheada, entonces verifica si la contraseña ingresada y contraseñ hasheada de la bd coincide, pues ingresa de forma exitosa.)
        return pwd_context.verify(contraseña_ingresada, password_hashed)
    except ValueError:  # hash guardado con formato inválido
        return False

#Aquí recibes un diccionario con la información del usuario, ict significa Diccionario en Python. Es una estructura de datos que sirve para guardar información organizada en parejas de Clave y Valo

#timedelta que sirve para representar duraciones de tiempo No es una hora fija (como las 3:00 PM), sino una cantidad de tiempo. o puede venir vacia con el none

def crear_token_acceso(datos: dict, tiempo_expiracion: timedelta | None = None) -> str:
    # Agarramos el tiempo de ahora en la hora universal (UTC) para que no varie por el país.
    # Si iniciamos sesión a las 3:30, como en el .env definimos que vence en media hora (30 min), 
    # se le suma ese tiempo y queda configurado que a las 4:00 va a vencer
    expiracion = datetime.now(timezone.utc) + (
        tiempo_expiracion or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    #pero el payload es la mercancía valiosa que lleva dentro, el ID de tu usuario y la fecha en la que vence su pase VIP)
    # El payload es la carga útil donde metemos los datos valiosos.
    # Desempaquetamos (destapamos con el **) los datos y le añadimos el tiempo que vence.
    payload = {**datos, "exp": expiracion}

    # El jwt.encode codifica la mercancía (datos valiosos), la secret key y el algoritmo.
    # De esta fusión matemática es de donde sale el token final.
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# Fábrica de errores: Crea un aviso oficial de que el Token fallo.
def _error_credenciales(detalle: str) -> HTTPException:
    return HTTPException(
        # Devuelve un estado 401 (No Autorizado) al Frontend
        status_code=status.HTTP_401_UNAUTHORIZED,
        # Aquí mete el texto personalizado que explica por qué falló el token
        detail=detalle,
        # Envía una cabecera en la respuesta avisando que se exiga sea el portador del token
        headers={"WWW-Authenticate": "Bearer"},
    )

# El portero: Extrae el token de la cabecera Bearer gracias a Depends(autenticacion)
def verificar_token(token: str = Depends(autenticacion)) -> str:
    """Devuelve el 'sub' del token, que es el ID del usuario (como texto)."""
    try:
        # Decodificamos (abrimos) el token con la llave secreta y el algoritmo.
        # Con 'options' exigimos estrictamente que traiga el tiempo (exp) y el ID (sub).
        contenido = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        # Usamos try/except para capturar errores del token y evitar que el backend se congele.
        raise _error_credenciales("Token inválido o expirado")

    # Obtenemos el ID del usuario (sub). Usamos ID porque nunca cambia, a diferencia del correo.
    sub = contenido.get("sub")
    
    # Si el ID no existe o no es un texto válido, lanzamos credenciales inválidas.
    if not isinstance(sub, str) or not sub:
        raise _error_credenciales("Credenciales inválidas")

    return sub

#jwt.encode es cuando el inicio de sesion es extoso, le crea el token
#jwt.decode, es para decodificar para validar que si esten estos datos ahi