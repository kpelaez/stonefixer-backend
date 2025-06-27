from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from app.api.deps import get_current_user, get_token_roles, require_roles
from app.db.database import get_db
from app.models.user import User, UserRead
from app.services.auth import add_role_to_user, get_user_roles, remove_role_from_user


router = APIRouter()

##EN MAIN ANTEPONER EN ENDPOINT "/users/..."

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