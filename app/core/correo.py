# app/core/correo.py
"""Envío de correos por SMTP. Pensado para usarse con BackgroundTasks de FastAPI:
las funciones enviar_* nunca lanzan excepciones (solo las registran), así un
fallo del servidor de correo no rompe la respuesta HTTP ni deja tracebacks sueltos.
"""
import html
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core import config as cfg

logger = logging.getLogger(__name__)


class ErrorEnvioCorreo(Exception):
    pass


def _enviar(destino: str, asunto: str, texto: str, cuerpo_html: str) -> None:
    if cfg.EMAIL_EN_CONSOLA:
        # SOLO DESARROLLO. Nunca activar en producción: el código quedaría en los logs.
        logger.warning("[EMAIL EN CONSOLA] Para: %s | %s\n%s", destino, asunto, texto)
        return

    if not (cfg.SMTP_HOST and cfg.SMTP_USER and cfg.SMTP_PASSWORD):
        raise ErrorEnvioCorreo("SMTP no configurado (revisa SMTP_HOST, SMTP_USER y SMTP_PASSWORD).")

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = cfg.SMTP_FROM
    mensaje["To"] = destino
    mensaje.set_content(texto)
    mensaje.add_alternative(cuerpo_html, subtype="html")

    contexto = ssl.create_default_context()
    try:
        if cfg.SMTP_SSL:
            with smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT, context=contexto, timeout=15) as smtp:
                smtp.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
                smtp.send_message(mensaje)
        else:
            with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=15) as smtp:
                smtp.starttls(context=contexto)
                smtp.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
                smtp.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as error:
        raise ErrorEnvioCorreo(str(error)) from error


def _html(nombre: str, intro: str, codigo: str, pie: str) -> str:
    return f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;">
  <h2 style="margin:0 0 16px;">{html.escape(cfg.NOMBRE_APP)}</h2>
  <p>Hola {html.escape(nombre)},</p>
  <p>{html.escape(intro)}</p>
  <p style="font-size:32px;letter-spacing:8px;font-weight:bold;text-align:center;
            background:#f3f4f6;padding:16px;border-radius:8px;">{codigo}</p>
  <p>El código vence en {cfg.CODIGO_EXPIRA_MINUTOS} minutos y solo se puede usar una vez.</p>
  <p style="color:#6b7280;font-size:13px;">{html.escape(pie)}</p>
</div>"""


def enviar_codigo_verificacion(destino: str, nombre: str, codigo: str) -> None:
    intro = "Usa este código para confirmar tu correo y activar tu cuenta:"
    pie = "Si no creaste esta cuenta, ignora este mensaje."
    texto = (
        f"Hola {nombre},\n\n{intro}\n\n{codigo}\n\n"
        f"Vence en {cfg.CODIGO_EXPIRA_MINUTOS} minutos.\n{pie}\n"
    )
    try:
        _enviar(destino, f"{cfg.NOMBRE_APP}: código de verificación", texto, _html(nombre, intro, codigo, pie))
    except ErrorEnvioCorreo:
        logger.exception("No se pudo enviar el correo de verificación")


def enviar_codigo_recuperacion(destino: str, nombre: str, codigo: str) -> None:
    intro = "Recibimos una solicitud para restablecer tu contraseña. Tu código es:"
    pie = "Si no fuiste tú, ignora este mensaje: tu contraseña no cambiará."
    texto = (
        f"Hola {nombre},\n\n{intro}\n\n{codigo}\n\n"
        f"Vence en {cfg.CODIGO_EXPIRA_MINUTOS} minutos.\n{pie}\n"
    )
    try:
        _enviar(destino, f"{cfg.NOMBRE_APP}: recuperar contraseña", texto, _html(nombre, intro, codigo, pie))
    except ErrorEnvioCorreo:
        logger.exception("No se pudo enviar el correo de recuperación")


# NUEVO: aviso de seguridad cuando la contraseña cambia (por "cambiar contraseña" o
# por "olvidé mi contraseña"). Si no fue el usuario, se entera al instante.
def enviar_aviso_cambio_password(destino: str, nombre: str) -> None:
    asunto = f"{cfg.NOMBRE_APP}: tu contraseña fue cambiada"
    intro = "La contraseña de tu cuenta acaba de cambiar y se cerraron tus otras sesiones."
    pie = (
        "Si no fuiste tú, restablece tu contraseña de inmediato con la opción "
        "'Olvidé mi contraseña' y contacta al soporte."
    )
    texto = f"Hola {nombre},\n\n{intro}\n\n{pie}\n"
    cuerpo_html = f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;">
  <h2 style="margin:0 0 16px;">{html.escape(cfg.NOMBRE_APP)}</h2>
  <p>Hola {html.escape(nombre)},</p>
  <p>{html.escape(intro)}</p>
  <p style="color:#b91c1c;font-size:14px;"><strong>{html.escape(pie)}</strong></p>
</div>"""
    try:
        _enviar(destino, asunto, texto, cuerpo_html)
    except ErrorEnvioCorreo:
        logger.exception("No se pudo enviar el aviso de cambio de contraseña")