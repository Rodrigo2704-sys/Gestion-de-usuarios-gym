# app/core/config.py
import os
import warnings

from dotenv import load_dotenv

load_dotenv()

# Prohibido arrancar sin llave secreta.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "ERROR CRÍTICO DE SEGURIDAD: La variable de entorno 'SECRET_KEY' "
        "no está definida en el archivo .env"
    )

if len(SECRET_KEY) < 32:
    warnings.warn(
        "SECRET_KEY es corta (menos de 32 caracteres). Genera una segura con: "
        'python -c "import secrets; print(secrets.token_hex(32))"',
        stacklevel=2,
    )

# ALGORITHM: Define la receta matemática para firmar los tokens de seguridad.
# Evita un hackeo histórico ("none attack") donde se alteraba el token para
# saltarse la seguridad. Solo aceptamos algoritmos HMAC ultra seguros.
ALGORITHM = os.getenv("ALGORITHM", "HS256")
if ALGORITHM not in {"HS256", "HS384", "HS512"}:
    raise ValueError(f"ALGORITHM '{ALGORITHM}' no permitido. Usa HS256, HS384 o HS512.")


ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# CORS_ORIGINS: Lista de invitados VIP. Define qué páginas web (Frontend)
# tienen permiso para hacerle peticiones a esta API. Se leen del .env (separados
# por coma); si no existen, se usan los servidores de desarrollo habituales.
_ORIGENES_DEV = (
    "http://127.0.0.1:5500,http://localhost:5500,"
    "http://127.0.0.1:8080,http://localhost:8080"
)
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _ORIGENES_DEV).split(",") if o.strip()
]


# ---------------------------------------------------------------------------
# NUEVO: CORREO (SMTP) Y CÓDIGOS DE VERIFICACIÓN
# ---------------------------------------------------------------------------
def _bool_env(nombre: str, defecto: bool = False) -> bool:
    return os.getenv(nombre, str(defecto)).strip().lower() in {"1", "true", "si", "sí", "yes"}


SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER
# False -> STARTTLS (puerto 587). True -> SSL directo (puerto 465).
SMTP_SSL = _bool_env("SMTP_SSL", False)

# SOLO DESARROLLO: en vez de enviar el correo, imprime el código en la consola.
# En producción debe quedar en false.
EMAIL_EN_CONSOLA = _bool_env("EMAIL_EN_CONSOLA", False)

NOMBRE_APP = os.getenv("NOMBRE_APP", "Mi aplicación")

CODIGO_EXPIRA_MINUTOS = int(os.getenv("CODIGO_EXPIRA_MINUTOS", 15))
CODIGO_MAX_INTENTOS = int(os.getenv("CODIGO_MAX_INTENTOS", 5))
CODIGO_REENVIO_SEGUNDOS = int(os.getenv("CODIGO_REENVIO_SEGUNDOS", 60))