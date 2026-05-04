from fastapi import APIRouter, Depends, HTTPException, status, Request
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

# Endpoint para login
@router.post("/token")
@limiter.limit(settings.LOGIN_RATE_LIMIT) # 5 intentos por minuto
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # Crear y devolver el token
    access_token = create_access_token(
        data={"sub": user.email},
        user_roles= user_roles,
        expires_delta=access_token_expires
        )
    
    return {"access_token": access_token, "token_type": "bearer", "roles": user_roles}

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
