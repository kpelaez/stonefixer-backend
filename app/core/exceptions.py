# app/core/exceptions.py
"""
Sistema Centralizado de Manejo de Errores para StoneFixer
Versión: 1.0.0

Este módulo proporciona:
- Excepciones personalizadas
- Handlers de errores globales
- Formatos de respuesta estandarizados
- Logging automático de errores
"""

from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, NoResultFound
import logging
import traceback
from datetime import datetime

# Configurar logger
logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================

class StoneFixerException(Exception):
    """Excepción base para todas las excepciones personalizadas de StoneFixer"""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFoundError(StoneFixerException):
    """Recurso no encontrado"""
    
    def __init__(self, resource_type: str, resource_id: Union[int, str], **kwargs):
        message = f"{resource_type} con ID '{resource_id}' no encontrado"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": str(resource_id)}
        )


class DuplicateResourceError(StoneFixerException):
    """Recurso duplicado"""
    
    def __init__(self, resource_type: str, field: str, value: str, **kwargs):
        message = f"{resource_type} con {field}='{value}' ya existe"
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="DUPLICATE_RESOURCE",
            details={"resource_type": resource_type, "field": field, "value": value}
        )


class InvalidOperationError(StoneFixerException):
    """Operación inválida o no permitida"""
    
    def __init__(self, operation: str, reason: str, **kwargs):
        message = f"Operación '{operation}' no permitida: {reason}"
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_OPERATION",
            details={"operation": operation, "reason": reason}
        )


class PermissionDeniedError(StoneFixerException):
    """Permisos insuficientes"""
    
    def __init__(self, required_permission: str, **kwargs):
        message = f"Permiso requerido: {required_permission}"
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="PERMISSION_DENIED",
            details={"required_permission": required_permission}
        )


class BusinessRuleViolationError(StoneFixerException):
    """Violación de regla de negocio"""
    
    def __init__(self, rule: str, reason: str, **kwargs):
        message = f"Regla de negocio violada - {rule}: {reason}"
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="BUSINESS_RULE_VIOLATION",
            details={"rule": rule, "reason": reason}
        )


class DatabaseError(StoneFixerException):
    """Error de base de datos"""
    
    def __init__(self, operation: str, original_error: Optional[Exception] = None, **kwargs):
        message = f"Error de base de datos durante '{operation}'"
        details = {"operation": operation}
        
        if original_error:
            details["original_error"] = str(original_error)
        
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            details=details
        )


class ExternalServiceError(StoneFixerException):
    """Error de servicio externo"""
    
    def __init__(self, service_name: str, reason: str, **kwargs):
        message = f"Error en servicio externo '{service_name}': {reason}"
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service_name": service_name, "reason": reason}
        )


# ============================================================================
# FORMATOS DE RESPUESTA ESTANDARIZADOS
# ============================================================================

def create_error_response(
    message: str,
    status_code: int,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crear respuesta de error estandarizada.
    
    Args:
        message: Mensaje de error legible para el usuario
        status_code: Código de estado HTTP
        error_code: Código de error interno
        details: Detalles adicionales del error
        request_id: ID de la request para tracking
        
    Returns:
        Diccionario con formato estandarizado de error
    """
    error_response = {
        "success": False,
        "error": {
            "message": message,
            "code": error_code or "INTERNAL_ERROR",
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    if details:
        error_response["error"]["details"] = details
    
    if request_id:
        error_response["error"]["request_id"] = request_id
    
    return error_response


def create_success_response(
    data: Any,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Crear respuesta exitosa estandarizada.
    
    Args:
        data: Datos de la respuesta
        message: Mensaje opcional de éxito
        metadata: Metadatos adicionales
        
    Returns:
        Diccionario con formato estandarizado de éxito
    """
    response = {
        "success": True,
        "data": data
    }
    
    if message:
        response["message"] = message
    
    if metadata:
        response["metadata"] = metadata
    
    return response


# ============================================================================
# EXCEPTION HANDLERS GLOBALES
# ============================================================================

async def stonefixer_exception_handler(
    request: Request,
    exc: StoneFixerException
) -> JSONResponse:
    """Handler para excepciones personalizadas de StoneFixer"""
    
    # Log del error
    logger.warning(
        f"StoneFixerException: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            message=exc.message,
            status_code=exc.status_code,
            error_code=exc.error_code,
            details=exc.details
        )
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """Handler para HTTPException de FastAPI"""
    
    # Log del error
    logger.warning(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )
    
    # Formatear detalles si es un diccionario
    details = None
    message = str(exc.detail)
    
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", str(exc.detail))
        details = {k: v for k, v in exc.detail.items() if k != "message"}
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            message=message,
            status_code=exc.status_code,
            error_code="HTTP_ERROR",
            details=details if details else None
        )
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """Handler para errores de validación de Pydantic"""
    
    # Formatear errores de validación
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"ValidationError: {len(errors)} validation errors",
        extra={
            "errors": errors,
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            message="Error de validación en los datos enviados",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details={"validation_errors": errors}
        )
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """Handler para errores de SQLAlchemy"""
    
    # Log del error completo
    logger.error(
        f"SQLAlchemyError: {type(exc).__name__}",
        extra={
            "error_type": type(exc).__name__,
            "path": request.url.path
        },
        exc_info=True
    )
    
    # Manejar tipos específicos de errores de SQLAlchemy
    if isinstance(exc, IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=create_error_response(
                message="Violación de restricción de integridad en la base de datos",
                status_code=status.HTTP_409_CONFLICT,
                error_code="INTEGRITY_ERROR",
                details={"hint": "Puede que estés intentando crear un registro duplicado"}
            )
        )
    
    elif isinstance(exc, NoResultFound):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=create_error_response(
                message="Recurso no encontrado en la base de datos",
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="NO_RESULT_FOUND"
            )
        )
    
    # Error genérico de base de datos
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            message="Error interno de base de datos",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            details={"hint": "Por favor contacta al administrador del sistema"}
        )
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handler para excepciones no manejadas"""
    
    # Log del error completo con stack trace
    logger.error(
        f"UnhandledException: {type(exc).__name__} - {str(exc)}",
        extra={
            "error_type": type(exc).__name__,
            "path": request.url.path
        },
        exc_info=True
    )
    
    # En desarrollo, incluir el stack trace
    import os
    details = None
    
    if os.getenv("DEBUG", "False") == "True":
        details = {
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            message="Error interno del servidor",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            details=details
        )
    )


# ============================================================================
# FUNCIÓN DE REGISTRO DE HANDLERS
# ============================================================================

def register_exception_handlers(app):
    """
    Registrar todos los exception handlers en la aplicación FastAPI.
    
    Llamar esta función en main.py después de crear la app.
    
    Args:
        app: Instancia de FastAPI
    """
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError
    from sqlalchemy.exc import SQLAlchemyError
    
    # Registrar handlers personalizados
    app.add_exception_handler(StoneFixerException, stonefixer_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("✅ Exception handlers registrados correctamente")