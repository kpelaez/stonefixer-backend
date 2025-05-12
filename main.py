from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from sqlmodel import Session, select
from datetime import timedelta
from jose import JWTError, jwt

from app.db.database import get_db, create_db_and_tables
from app.models.user import User, UserCreate, UserRead, UserLogin
from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_user_by_email,
    get_user_roles,
    create_user,
    add_role_to_user,
    remove_role_from_user,
)
from app.api.deps import get_current_user,get_token_roles, require_roles
from app.config import settings


# Crear tablas
create_db_and_tables()

app = FastAPI(title=settings.APP_NAME)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # URL de tu frontend (ajustar según sea necesario)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Esquema OAuth2 para extraer el token de la cabecera de autorización
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Endpoint para login
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Endpoint para iniciar sesión y obtener un token JWT"""

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
@app.post("/register", response_model=UserRead)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Endpoint para registrar un nuevo usuario"""

    # Verificar si el usuario ya existe
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    # Crear y devolver el usuario
    return create_user(db, user_data)

# Endpoint protegido de ejemplo
@app.get("/users/me", response_model=UserRead)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Endpoint para obtener información del usuario actual"""
    # Crear y devolver UserRead
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )

# Endpoint para obtener los roles del usuario actual
@app.get("/users/me/roles", response_model=List[str])
async def get_current_user_roles(roles: list = Depends(get_token_roles)):
    """Obtener los roles del usuario actual"""
    return roles

# Endpoint para añadir roles a un usuario (solo admin)
@app.post("/users/{user_id}/roles/{role}")
@require_roles(["admin"])
async def add_role(
    user_id: int,
    role: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Añadir un rol a un usuario (solo admin)"""
    if not add_role_to_user(db, user_id, role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No se pudo añadir el rol '{role}' al usuario con ID {user_id}")
    
    return {"message": f"Rol '{role}' añadido correctamente al usuadio con ID {user_id}"}

# Endpoint para eliminar roles de un usuario (solo admin)
@app.delete("users/{user_id}/roles/{role}")
@require_roles(["admin"])
async def remove_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un rol a un usuario (solo admin)"""
    if not remove_role_from_user(db, user_id, role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo eleminar el role '{role}' del usuario con ID {user_id}"
        )
    return {"message": f"Rol '{role}' eliminado correctamente del usuario con ID {user_id}"}

# Endpoint para listar usuarios con sus roles (solo admin)
@app.get("/users", response_model=List[UserRead])
@require_roles(["admin"])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """"Listar todos los usuarios con sus roles (solo admin)"""
    statement = select(User).offset(skip).limit(limit)
    users = db.exec(statement).all()

    #Para cada usuario, obtener sus roles
    for user in users:
        roles = get_user_roles(db, user.id)
        #Añadir roles como atributo
        setattr(user, "roles", roles)

    return users

# Endpoint de ingreso al servidor ¡¡Borrar Luego!!
@app.get("/")
def read_root():
    return {"message": "Bienvenido al servicio de autenticación"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
