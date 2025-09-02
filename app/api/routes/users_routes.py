from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from app.api.deps import get_current_user, get_token_roles, require_roles
from app.db.database import get_db
from app.models.user import User, UserRead
from app.services.auth import add_role_to_user, get_user_roles, remove_role_from_user


router = APIRouter()

# Endpoint para obtener informacion del usuario
@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Obtener información del usuario actual"""
    try:
        # Obtener roles del usuario actual
        user_roles = []
        if hasattr(current_user, 'roles') and current_user.roles:
            for role in current_user.roles:
                if hasattr(role, 'name'):
                    user_roles.append(role.name)
                else:
                    user_roles.append(str(role))
        
        return {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "department": getattr(current_user, 'department', None),
            "role": user_roles[0] if user_roles else "user",
            "roles": user_roles,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None
        }
        
    except Exception as e:
        print(f"Error in get_current_user_info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al obtener información del usuario"
        )


# Endpoint para obtener los roles del usuario actual
@router.get("/me/roles", response_model=List[str])
async def get_current_user_roles(roles: list = Depends(get_token_roles)):
    """Obtener los roles del usuario actual"""
    return roles

# Endpoint para añadir roles a un usuario (solo admin)
@router.post("/{user_id}/roles/{role}")
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
@router.delete("/{user_id}/roles/{role}")
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

@router.get("/", response_model=List[UserRead])
# @require_roles(["admin"])
async def list_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """"Listar todos los usuarios con sus roles (solo admin)"""
    try:
        statement = select(User).where(User.is_active == True)
        users = db.exec(statement).all()

        #Para cada usuario, obtener sus roles
        users_response = []
        for user in users:
            # Obtener roles del usuario de forma segura
            user_roles = []
            if hasattr(user, 'roles') and user.roles:
                for role in user.roles:
                    if hasattr(role, 'name'):
                        user_roles.append(role.name)
                    else:
                        user_roles.append(str(role))
            
            user_data = {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "department": getattr(user, 'department', None),
                "role": user_roles[0] if user_roles else "user",  # Primer rol como rol principal
                "roles": user_roles,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            }
            users_response.append(user_data)
        
        return users_response
    
    except Exception as e:
        print(f"Error in list_users: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al obtener usuarios"
        )


@router.get("/{user_id}", response_model=UserRead)
@require_roles(["admin"])
async def get_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Obtener un usuario especifico (solo admin)"""
    user = db.get(User, user_id)
    if not user: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    
    #Obtener roles del usuario
    roles = get_user_roles(db, user.id)
    setattr(user, "roles", roles)

    return user