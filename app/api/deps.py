from fastapi import Depends, HTTPException, logger, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session
from typing import List
from functools import wraps

from app.config import settings
from app.db.database import get_db
from app.models.user import User
from app.services.auth import get_user_by_email, get_user_roles

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> User:
    """
    Obtener el usuario actual a partir del token JWT.
    
    Esta es la dependencia base que verifica autenticación.
    Lanza HTTPException si el token es inválido.
    
    Args:
        token: JWT token del header Authorization
        db: Sesión de base de datos
        
    Returns:
        User: Usuario autenticado
        
    Raises:
        HTTPException: Si las credenciales son inválidas
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decodificar token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        
        if email is None:
            raise credentials_exception
        
    except InvalidTokenError:
        logger.warning("Token JWT inválido recibido")
        raise credentials_exception
    
    # Buscar usuario en la base de datos
    user = get_user_by_email(db, email)
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verificar que el usuario actual esté activo.
    
    Args:
        current_user: Usuario del token
        
    Returns:
        User: Usuario activo
        
    Raises:
        HTTPException: Si el usuario está inactivo
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Usuario inactivo"
        )
    return current_user


# SISTEMA DE ROLES Y PERMISOS

class RoleChecker:
    """
    Clase para verificar roles de usuario.
    
    Esta es la forma correcta de implementar verificación de roles en FastAPI.
    Se usa como una dependencia que puede ser reutilizada.
    
    Ejemplo de uso:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(RoleChecker(["admin"]))):
            return {"message": "Hello admin"}
    """
    
    def __init__(self, allowed_roles: List[str]):
        """
        Inicializar el verificador de roles.
        
        Args:
            allowed_roles: Lista de roles permitidos
        """
        self.allowed_roles = allowed_roles
    
    async def __call__(
        self, 
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        """
        Verificar que el usuario tenga al menos uno de los roles permitidos.
        
        Args:
            current_user: Usuario autenticado
            db: Sesión de base de datos
            
        Returns:
            User: Usuario con roles válidos
            
        Raises:
            HTTPException: Si el usuario no tiene los roles necesarios
        """
        # Obtener roles del usuario desde la base de datos
        user_roles = get_user_roles(db, current_user.id)
        
        # Verificar si el usuario tiene al menos uno de los roles permitidos
        has_permission = any(role in user_roles for role in self.allowed_roles)
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "No tienes permisos suficientes para realizar esta acción",
                    "required_roles": self.allowed_roles,
                    "your_roles": user_roles
                }
            )
        
        return current_user


# DEPENDENCIAS DE ROLES ESPECÍFICOS (Para facilitar uso)

async def require_admin(
    current_user: User = Depends(RoleChecker(["admin"]))
) -> User:
    """Requiere que el usuario sea administrador"""
    return current_user


async def require_manager(
    current_user: User = Depends(RoleChecker(["admin", "manager"]))
) -> User:
    """Requiere que el usuario sea admin o manager"""
    return current_user


async def require_inventory_manager(
    current_user: User = Depends(RoleChecker(["admin", "manager", "inventory_manager"]))
) -> User:
    """Requiere permisos de gestión de inventario"""
    return current_user

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_user_permissions(user: User, db: Session) -> dict:
    """
    Obtener todos los permisos del usuario.
    
    Args:
        user: Usuario autenticado
        db: Sesión de base de datos
        
    Returns:
        dict: Diccionario con información de permisos
    """
    user_roles = get_user_roles(db, user.id)
    
    # Definir permisos por rol
    permissions_map = {
        "admin": ["all"],
        "manager": ["view_reports", "manage_team", "view_inventory", "create_inventory"],
        "inventory_manager": ["view_inventory", "create_inventory", "edit_inventory", "assign_assets"],
        "user": ["view_own_data", "view_inventory"]
    }
    
    # Acumular permisos de todos los roles del usuario
    all_permissions = set()
    for role in user_roles:
        if role in permissions_map:
            all_permissions.update(permissions_map[role])
    
    return {
        "user_id": user.id,
        "roles": user_roles,
        "permissions": list(all_permissions),
        "is_admin": "admin" in user_roles
    }

def get_available_roles() -> List[str]:
    """
    Obtener lista de roles disponibles en el sistema.
    
    Returns:
        List[str]: Lista de roles válidos
    """
    from app.models.role import Role
    return [role.value for role in Role]


def validate_role(role: str) -> bool:
    """
    Validar si un rol es válido.
    
    Args:
        role: Nombre del rol a validar
        
    Returns:
        bool: True si es válido, False si no
    """
    return role in get_available_roles()

def check_permission(user: User, db: Session, required_permission: str) -> bool:
    """
    Verificar si un usuario tiene un permiso específico.
    
    Args:
        user: Usuario a verificar
        db: Sesión de base de datos
        required_permission: Permiso requerido
        
    Returns:
        bool: True si tiene el permiso, False si no
    """
    permissions = get_user_permissions(user, db)
    
    # Admin tiene todos los permisos
    if "all" in permissions["permissions"]:
        return True
    
    return required_permission in permissions["permissions"]

# Función para obtener los roles del token actual
# async def get_token_roles(token: str = Depends(oauth2_scheme)) -> list:
#     """Extraer roles del token JWT sin verificar usuario"""
#     try:
#         payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
#         return payload.get("roles", [])
#     except JWTError:
#         return []

# ============================================================================
# DECORADOR LEGACY (Para compatibilidad con código antiguo)
# ============================================================================

def require_roles(allowed_roles: List[str]):
    """
    DEPRECADO: Usar RoleChecker en su lugar.
    
    Este decorador se mantiene solo para compatibilidad con código antiguo.
    
    Ejemplo antiguo (NO USAR):
        @require_roles(["admin"])
        async def my_endpoint(...):
            pass
    
    Ejemplo nuevo (USAR):
        async def my_endpoint(
            current_user: User = Depends(RoleChecker(["admin"]))
        ):
            pass
    """
    print(f"WARNING: @require_roles está deprecado. Usa RoleChecker en su lugar.")
    print(f"Ejemplo: current_user: User = Depends(RoleChecker({allowed_roles}))")
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Este decorador ya no debería usarse
            # Si se llama, simplemente ejecuta la función
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================================
# EJEMPLOS DE USO
# ============================================================================

"""
EJEMPLOS DE CÓMO USAR EL NUEVO SISTEMA:

1. Endpoint que requiere autenticación básica:
   
   @router.get("/protected")
   async def protected_endpoint(
       current_user: User = Depends(get_current_user)
   ):
       return {"user": current_user.email}

2. Endpoint que requiere roles específicos:
   
   @router.post("/admin-action")
   async def admin_action(
       current_user: User = Depends(RoleChecker(["admin"])),
       db: Session = Depends(get_db)
   ):
       return {"message": "Admin action performed"}

3. Endpoint con múltiples roles permitidos:
   
   @router.get("/inventory")
   async def view_inventory(
       current_user: User = Depends(RoleChecker(["admin", "manager", "inventory_manager"])),
       db: Session = Depends(get_db)
   ):
       return {"inventory": [...]}

4. Usar dependencias predefinidas:
   
   @router.delete("/users/{user_id}")
   async def delete_user(
       user_id: int,
       current_user: User = Depends(require_admin),
       db: Session = Depends(get_db)
   ):
       # Solo admins pueden eliminar usuarios
       return {"deleted": user_id}

5. Verificar permisos manualmente:
   
   @router.post("/custom-action")
   async def custom_action(
       current_user: User = Depends(get_current_user),
       db: Session = Depends(get_db)
   ):
       if not check_permission(current_user, db, "manage_team"):
           raise HTTPException(status_code=403, detail="No permission")
       
       return {"message": "Action performed"}
"""






