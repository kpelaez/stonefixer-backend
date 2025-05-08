from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select
from app.config import settings
from app.models.user import User, UserCreate
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
    return db_user


# Funciones de manejo de Roles

def get_user_roles(db: Session, user_id: int) -> List[str]:
    """Obtener los roles de un usuario"""
    statement = select(UserRole).where(UserRole.user_id == user_id)
    user_roles = db.exec(statement).all()

    return [ur.role for ur in user_roles]


def has_role(db: Session, user_id: int, role: str) -> List[str]:
    """Verificar si un usuario tiene un rol especifico"""
    statement = select(UserRole).where(
        (UserRole.user_id == user_id) & (UserRole.role == role)
    )
    return db.exec(statement).first() is not None


def add_role_to_user(db: Session, user_id: int, role: str) -> bool:
    """Añadir un rol a un usuario"""
    #Verificar que el rol sea valido
    valid_roles = [r.value for r in Role]
    if role not in valid_roles:
        return False
    
    #Verificar si el usuario ya tiene el rol a añadir
    if has_role(db, user_id, role):
        return True
    
    #Añadir el rol
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


# Funciones de JWT
def create_access_token(data: dict, user_roles: List[str] ,expires_delta: timedelta | None = None):
    """Crea un token JWT de acceso"""
    to_encode = data.copy()
    
    # Establecer el tiempo de expiración
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else: 
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "roles": user_roles
        })

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Verifica un token JWT y devuelve los datos"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None