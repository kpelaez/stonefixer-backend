"""
Docstring for app.core.rate_limiter
Sistema de Rate Limiting para StoneFixer
Protege contra ataques de fuerza bruta y abuso de API
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Inicializar limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.API_RATE_LIMIT] if settings.RATE_LIMIT_ENABLED else [],
    enabled=settings.RATE_LIMIT_ENABLED,
    storage_uri="memory://",  # Para producción usar Redis: "redis://localhost:6379"
    strategy="fixed-window"
)

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Handler personalizado para errores de rate limiting
    Devuelve mensaje amigable al usuario
    """
    logger.warning(
        f"Rate limit exceeded from IP: {get_remote_address(request)} "
        f"Path: {request.url.path}"
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Demasiadas solicitudes. Por favor, intenta nuevamente en unos minutos.",
            "details": {
                "retry_after": "60 seconds",
                "limit": str(exc.detail)
            }
        },
        headers={"Retry-After": "60"}
    )