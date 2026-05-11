from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlmodel import Session, select
from app.config import settings
from app.models.user import User, UserCreate, UserRead
from app.models.role import UserRole, Role
from typing import List

# Configuración para el hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Funciones de gestión de contraseñas
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)


# Funciones de autenticación
def authenticate_user(db: Session, email: str, password: str):
    """Autentica un usuario verificando email y contraseña"""
    statement = select(User).where(User.email == email)
    user = db.exec(statement).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# Funciones de gestión de usuarios
def get_user_by_email(db: Session, email: str):
    statement = select(User).where(User.email == email)
    return db.exec(statement).first()


def create_user(db: Session, user_create: UserCreate):
    """Crea un nuevo usuario con roles"""
    hashed_password = get_password_hash(user_create.password)

    # Validar roles
    valid_roles = [role.value for role in Role]
    roles_to_add = []

    for role in user_create.roles:
        if role in valid_roles:
            roles_to_add.append(role)
    
    # Si no se especifican roles, asignar rol USER por defecto
    if not roles_to_add:
        roles_to_add = [Role.USER.value]


    db_user = User(
        email = user_create.email,
        full_name=user_create.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)


    # Asignar roles al usuario
    for role in roles_to_add:
        user_role = UserRole(user_id=db_user.id, role=role)
        db.add(user_role)
    
    db.commit()
    db.refresh(db_user)
    return UserRead(
        id=db_user.id,
        email=db_user.email,
        full_name=db_user.full_name,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        roles=[ur.role for ur in db_user.roles]  # Extraer solo el string del rol
    )


# Funciones de manejo de Roles

def get_user_roles(db: Session, user_id: int) -> List[str]:
    """Obtener los roles de un usuario"""
    statement = select(UserRole).where(UserRole.user_id == user_id)
    user_roles = db.exec(statement).all()

    return [ur.role for ur in user_roles]


def has_role(user: User, role: str) -> bool:
    """Verificar si un usuario tiene un rol específico"""
    # Si tenemos los roles en _roles (de get_current_user)
    if hasattr(user, "_roles"):
        return role in user._roles
    
    # Si no, obtener de la base de datos (relación User.roles)
    if user.roles:
        return any(user_role.role == role for user_role in user.roles)
    
    return False

def has_any_role(user: User, roles: List[str]) -> bool:
    """Verificar si un usuario tiene alguno de los roles especificados"""
    return any(has_role(user, role) for role in roles)



def add_role_to_user(db: Session, user_id: int, role: str) -> bool:
    """Añadir un rol a un usuario"""
    #Verificar que el rol sea valido
    valid_roles = [r.value for r in Role]
    if role not in valid_roles:
        return False
    
    # Verificar si el usuario ya tiene el rol consultando directo a la DB
    existing = db.exec(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role == role,
        )
    ).first()

    if existing:
        return True  # Idempotente: ya lo tiene, no es un error

    user_role = UserRole(user_id=user_id, role=role)
    db.add(user_role)
    db.commit()
    return True

def remove_role_from_user(db: Session, user_id: int, role: str) -> bool:
    """Eliminar un rol de un usuario"""
    statement = select(UserRole).where(
        (UserRole.user_id == user_id) & (UserRole.role == role)
    )

    user_role = db.exec(statement).first()

    if not user_role:
        return False
    
    db.delete(user_role)
    db.commit()
    return True


# Función auxiliar para convertir User a UserRead
def user_to_user_read(user: User) -> UserRead:
    """Convierte un objeto User a UserRead, manejando la conversión de roles"""
    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        roles=[ur.role for ur in user.roles] if user.roles else []
    )


# Funciones de JWT
def create_access_token(data: dict, user_roles: List[str] ,expires_delta: timedelta | None = None):
    """Crea un token JWT de acceso"""
    to_encode = data.copy()
    
    # Establecer el tiempo de expiración
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else: 
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({ "exp": expire })

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Verifica un token JWT y devuelve los datos"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except InvalidTokenError:
        return None