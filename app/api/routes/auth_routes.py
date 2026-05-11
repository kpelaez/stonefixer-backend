from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from datetime import timedelta

# Importacion de modelos
from app.api.deps import get_current_user
from app.models.user import User, UserRead, UserCreate

# Funciones de Auth Services
from app.services.auth import authenticate_user, create_access_token, create_user, get_user_by_email

# Configuraciones de aplicacion
from app.config import settings
# Conexion con la base de datos
from app.db.database import get_db

from app.core.rate_limiter import limiter


router = APIRouter()

def _set_auth_cookie(response: Response, token: str) -> None:
    """Centraliza la configuración de la cookie de auth."""
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,                          # JS no puede leerla
        secure=settings.is_production(),        # HTTPS only en producción
        samesite="lax",                         # Protección CSRF básica
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


# Endpoint para login
@router.post("/token")
@limiter.limit(settings.LOGIN_RATE_LIMIT) # 5 intentos por minuto
async def login_for_access_token(request: Request, response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Endpoint para iniciar sesión y obtener un token JWT
    
    Rate Limit: 5 intentos por minuto por IP
    """

    # Autenticar al usuario
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Obtener roles del usuario directamente de la base de datos
    user_roles = []
    if user.roles:
        user_roles = [user_role.role for user_role in user.roles]

    access_token = create_access_token(
        data={"sub": user.email},
        user_roles=user_roles,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Setear cookie httpOnly — el token nunca viaja en el body
    _set_auth_cookie(response, access_token)

    # Devolver solo lo que el frontend necesita para UX (roles, user info)
    # NUNCA el token en el body
    return {
        "message": "Login exitoso",
        "roles": user_roles,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(response: Response):
    """Elimina la cookie de auth."""
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=settings.is_production(),
        httponly=True,
        samesite="lax"
    )
    return {"message": "Sesión cerrada exitosamente"}

# Endpoint para registro
@router.post("/register", response_model=UserRead)
@limiter.limit("5/hour") # Solo 5 registros por hora por IP
async def register(request:Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """Endpoint para registrar un nuevo usuario"""

    # Verificar si el usuario ya existe
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    # Crear y devolver el usuario
    return create_user(db, user_data)
