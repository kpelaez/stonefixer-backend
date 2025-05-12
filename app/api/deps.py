from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session
from typing import List, Callable
from functools import wraps
import inspect

from app.config import settings
from app.db.database import get_db
from app.models.user import User
from app.services.auth import get_user_by_email, get_user_roles

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

#Funcion asincrona
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Obtener el usuario actual a partir del token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        
        # Obtener roles del token
        token_roles = payload.get("roles", [])

    except JWTError:
        raise credentials_exception
    
    user = get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    
    # Simplemente devolver el usuario, sin modificarlo
    return user

# Función para obtener los roles del token actual
async def get_token_roles(token: str = Depends(oauth2_scheme)) -> list:
    """Extraer roles del token JWT sin verificar usuario"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("roles", [])
    except JWTError:
        return []

def require_roles(required_roles: List[str]):
    """Decorador para verificar que el usuario tenga al menos uno de los roles requeridos"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
            # Obtener roles del usuario
            user_roles = get_token_roles()
            
            # Verificar roles
            if not any(role in user_roles for role in required_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos suficientes para realizar esta acción",
                )
            
            return await func(*args, current_user=current_user, **kwargs)
        
        # Mantener la firma de la función original para FastAPI
        sig = inspect.signature(func)
        sig_params = list(sig.parameters.values())
        wrapper.__signature__ = sig.replace(parameters=sig_params)
        
        return wrapper
    
    return decorator