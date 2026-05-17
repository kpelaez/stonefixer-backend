from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select
from typing import Any, Dict, List
from datetime import datetime, timezone

from app.core.dni_security import dni_manager


from app.api.deps import get_current_user, get_user_permissions, require_admin
from app.db.database import get_db
from app.models.user import User
from app.services.auth import add_role_to_user, get_user_roles, remove_role_from_user

from app.core.rate_limiter import limiter
from app.config import settings
import logging
logger = logging.getLogger(__name__)


router = APIRouter()

# Endpoint para obtener informacion del usuario
@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener información del usuario actual"""
    try:
        # Obtener roles del usuario desde la base de datos
        user_roles = get_user_roles(db, current_user.id)
        
        # Obtener permisos
        permissions_info = get_user_permissions(current_user, db)
        
        return {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "department": getattr(current_user, 'department', None),
            "role": user_roles[0] if user_roles else "user",  # Rol principal
            "roles": user_roles,
            "permissions": permissions_info["permissions"],
            "is_admin": permissions_info["is_admin"],
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None
        }
        
    except Exception as e:
        logger.error(f" Error en get_current_user_info: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al obtener información del usuario"
        )


# Endpoint para obtener los roles del usuario actual
@router.get("/me/roles", response_model=List[str])
async def get_current_user_roles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener los roles del usuario actual.
    
    Requiere: Autenticación básica
    """
    try:
        user_roles = get_user_roles(db, current_user.id)
        return user_roles
        
    except Exception as e:
        logger.error(f" Error obteniendo roles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener los roles del usuario"
        )
    
@router.get("/me/permissions", response_model=Dict[str, Any])
async def get_current_user_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener los permisos del usuario actual.
    
    Retorna información detallada sobre qué puede hacer el usuario.
    
    Requiere: Autenticación básica
    """
    try:
        permissions_info = get_user_permissions(current_user, db)
        return permissions_info
        
    except Exception as e:
        logger.error(f" Error obteniendo permisos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener los permisos del usuario"
        )

# Endpoint para añadir roles a un usuario (solo admin)
@router.get("/", response_model=List[Dict[str, Any]])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Listar todos los usuarios activos del sistema.
    
    Retorna información completa de cada usuario incluyendo roles.
    
    Requiere: Rol de administrador
    """
    try:
        # Obtener usuarios activos con paginación
        statement = select(User).where(User.is_active == True).offset(skip).limit(limit)
        users = db.exec(statement).all()
        
        users_response = []
        
        for user in users:
            # Obtener roles del usuario
            user_roles = get_user_roles(db, user.id)
            
            user_data = {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "department": getattr(user, 'department', None),
                "role": user_roles[0] if user_roles else "user",  # Rol principal
                "roles": user_roles,
                "is_active": user.is_active,
                "has_dni": user.dni_encrypted is not None,
                "personal_data_consent": user.personal_data_consent,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            }
            users_response.append(user_data)
        
        logger.info(f" Admin {current_user.email} listó {len(users_response)} usuarios")
        return users_response
    
    except Exception as e:
        logger.error(f" Error en list_users: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al obtener usuarios"
        )
    
@router.get("/{user_id}", response_model=Dict[str, Any])
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Obtener información de un usuario específico.
    
    Requiere: Rol de administrador
    """
    try:
        user = db.get(User, user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado"
            )
        
        # Obtener roles del usuario
        user_roles = get_user_roles(db, user.id)
        
        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "department": getattr(user, 'department', None),
            "role": user_roles[0] if user_roles else "user",
            "roles": user_roles,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error obteniendo usuario {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener información del usuario"
        )

@router.post("/{user_id}/roles/{role}", response_model=Dict[str, str])
async def add_role(
    user_id: int,
    role: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Añadir un rol a un usuario.
    
    Permite a los administradores asignar roles adicionales a los usuarios.
    
    Requiere: Rol de administrador
    
    Args:
        user_id: ID del usuario
        role: Nombre del rol a añadir (admin, manager, inventory_manager, user)
    """
    try:
        # Verificar que el usuario existe
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado"
            )
        
        # Añadir el rol
        success = add_role_to_user(db, user_id, role)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se pudo añadir el rol '{role}'. Verifica que sea un rol válido."
            )
        
        logger.info(f" Admin {current_user.email} añadió rol '{role}' al usuario {user_id}")
        
        return {
            "message": f"Rol '{role}' añadido correctamente al usuario con ID {user_id}",
            "user_id": str(user_id),
            "role_added": role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error añadiendo rol: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al añadir el rol"
        )



# Endpoint para eliminar roles de un usuario (solo admin)
@router.delete("/{user_id}/roles/{role}", response_model=Dict[str, str])
async def remove_role(
    user_id: int,
    role: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Eliminar un rol de un usuario.
    
    Permite a los administradores remover roles de los usuarios.
    
    Requiere: Rol de administrador
    
    Args:
        user_id: ID del usuario
        role: Nombre del rol a eliminar
    """
    try:
        # Verificar que el usuario existe
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado"
            )
        
        # Verificar que el usuario tiene el rol
        user_roles = get_user_roles(db, user_id)
        if role not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El usuario no tiene el rol '{role}'"
            )
        
        # No permitir eliminar el último rol
        if len(user_roles) == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar el último rol del usuario"
            )
        
        # Eliminar el rol
        success = remove_role_from_user(db, user_id, role)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se pudo eliminar el rol '{role}' del usuario con ID {user_id}"
            )
        
        logger.info(f" Admin {current_user.email} eliminó rol '{role}' del usuario {user_id}")
        
        return {
            "message": f"Rol '{role}' eliminado correctamente del usuario con ID {user_id}",
            "user_id": str(user_id),
            "role_removed": role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error eliminando rol: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al eliminar el rol"
        )


@router.get("/{user_id}/roles", response_model=List[str])
async def get_user_roles_endpoint(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Obtener los roles de un usuario específico.
    
    Requiere: Rol de administrador
    """
    try:
        # Verificar que el usuario existe
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {user_id} no encontrado"
            )
        
        user_roles = get_user_roles(db, user_id)
        return user_roles
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f" Error obteniendo roles del usuario {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener los roles del usuario"
        )


# ENDPOINTS DE ESTADÍSTICAS (Solo Admin)

@router.get("/stats/roles", response_model=Dict[str, Any])
async def get_roles_statistics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Obtener estadísticas sobre la distribución de roles.
    
    Retorna información sobre cuántos usuarios tienen cada rol.
    
    Requiere: Rol de administrador
    """
    try:
        from app.models.role import UserRole
        from sqlalchemy import func
        
        # Contar usuarios por rol
        statement = select(
            UserRole.role,
            func.count(UserRole.user_id).label('count')
        ).group_by(UserRole.role)
        
        results = db.exec(statement).all()
        
        role_stats = {
            role: count for role, count in results
        }
        
        # Total de usuarios activos
        total_users = db.exec(
            select(func.count(User.id)).where(User.is_active == True)
        ).one()
        
        return {
            "total_users": total_users,
            "roles_distribution": role_stats,
            "available_roles": ["admin", "manager", "inventory_manager", "user"]
        }
        
    except Exception as e:
        logger.error(f" Error obteniendo estadísticas de roles: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estadísticas de roles"
        )


class UserDNIUpdate(BaseModel):
    dni: str
    consent: bool = True  # Consentimiento explícito

@router.patch("/{user_id}/dni")
async def update_user_dni(
    user_id: int,
    dni_data: UserDNIUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Actualiza el DNI encriptado de un usuario
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if not dni_data.consent:
        raise HTTPException(
            status_code=400,
            detail="Se requiere consentimiento explícito para almacenar el DNI"
        )
    
    # Encriptar DNI
    user.dni_encrypted = dni_manager.encrypt_dni(dni_data.dni)
    user.dni_hash = dni_manager.hash_dni(dni_data.dni)
    user.personal_data_consent = True
    user.personal_data_consent_date = datetime.now(timezone.utc)
    
    db.add(user)
    db.commit()
    
    return {"message": "DNI actualizado exitosamente (encriptado)"}



