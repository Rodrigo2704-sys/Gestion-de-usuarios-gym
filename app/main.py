# app/main.py
import logging
 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
 
from app.core.config import CORS_ORIGINS
from app.core.limiter import limiter
from app.routers import planes, usuarios
from app.routers import auth
 
# Sin esto, los logger.exception(...) de los routers salen sin formato ni fecha.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
 
app = FastAPI(
    title="Mi Backend Junior",
    version="1.0.0",
    description="API desarrollada con FastAPI y SQLAlchemy con Arquitectura Limpia",
)
 
# Conectamos el limitador a la aplicación y su manejador de errores
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
 
# CORS: solo los orígenes del .env (variable CORS_ORIGINS). Se usa el token en la
# cabecera Authorization, no cookies, así que allow_credentials queda en False.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
 
app.include_router(usuarios.router)
app.include_router(planes.router)
app.include_router(auth.router)
 
@app.get("/", tags=["Raíz"])
def read_root():
    return {"message": "¡Servidor corriendo al 100% con Rate Limiting modularizado!"}