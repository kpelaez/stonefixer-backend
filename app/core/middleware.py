import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from app.config import settings

logger = logging.getLogger(__name__)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PATHS = {"/api/v1/auth/token"}


async def log_requests(request: Request, call_next: RequestResponseEndpoint):
    """Registra duración y status de cada request. Advierte sobre lentos o errores."""
    start_time = time.time()
    logger.info(f"→ {request.method} {request.url.path}")

    response = await call_next(request)
    process_time = time.time() - start_time

    if process_time > 1.0 or response.status_code >= 400:
        logger.warning(
            f"{request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.3f}s"
        )
    else:
        logger.info(
            f"← {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s"
        )

    response.headers["X-Process-Time"] = str(process_time)
    return response


async def security_headers_middleware(request: Request, call_next: RequestResponseEndpoint):
    """Inyecta security headers en todas las respuestas."""
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if settings.is_production():
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if "server" in response.headers:
        del response.headers["server"]

    return response


async def csrf_protection_middleware(request: Request, call_next: RequestResponseEndpoint):
    """
    Bloquea CSRF clásico exigiendo un header custom que solo JS del origen
    autorizado por CORS puede setear en requests cross-origin.
    """
    uses_cookie_auth = (
        "access_token" in request.cookies
        and "authorization" not in request.headers
    )

    if (
        request.method in UNSAFE_METHODS
        and request.url.path not in CSRF_EXEMPT_PATHS
        and uses_cookie_auth
    ):
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Falta header requerido de seguridad (CSRF)"},
            )

    return await call_next(request)


def register_cors(app: FastAPI) -> None:
    """CORS debe quedar como el middleware más 'externo' de todos —
    así intercepta y resuelve el preflight OPTIONS antes de que llegue
    a los middlewares custom (CSRF, security headers, logging), que no
    tienen por qué lidiar con requests de preflight."""
    allowed_origins = settings.get_allowed_origins()
    logger.info(f"CORS permitido para: {allowed_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=["X-Process-Time", "Content-Disposition"],
    )


def register_middlewares(app: FastAPI) -> None:
    """
    Orden real de ejecución para la request ENTRANTE (Starlette: el
    último middleware agregado queda más 'afuera' → se ejecuta primero):

      1. csrf_protection_middleware   (se agrega último → corre primero, corta temprano y barato)
      2. security_headers_middleware
      3. log_requests                  (se agrega primero → corre último, mide el tiempo total real de la request)

    CORS se agrega aparte, después de esta función, para quedar como
    la capa más externa de todas — ver register_cors().
    """
    app.middleware("http")(log_requests)
    app.middleware("http")(security_headers_middleware)
    app.middleware("http")(csrf_protection_middleware)