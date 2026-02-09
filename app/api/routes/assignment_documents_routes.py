from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import httpx
from sqlmodel import Session
from typing import Optional

from app.db.database import get_db
from app.config import settings
from app.api.deps import require_admin
from app.models.user import User
from app.models.asset_assignment import AssetAssignment
from app.services.assignment_document_service import AssignmentDocumentGenerator
from app.services.humand_integration_service import humand_service
from app.services.asset_assignment_service import get_assignment
from app.services.tech_asset_service import get_tech_asset
from app.core.dni_security import dni_manager
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{assignment_id}/generate-preview")
async def generate_assignment_document_preview(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Genera preview del PDF de asignación (NO lo envía a Humand)
    
    Flujo:
    1. Obtiene datos de la asignación
    2. Obtiene datos del empleado (con DNI encriptado)
    3. Genera el PDF
    4. Retorna el PDF para preview
    
    Permisos: Solo administradores
    """
    # 1. Obtener asignación
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación no encontrada"
        )
    
    # 2. Obtener usuario asignado
    user = db.get(User, assignment.assigned_to_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario asignado no encontrado"
        )
    
    # Verificar que tenga DNI
    if not user.dni_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no tiene DNI registrado. Es necesario para generar el documento."
        )
    
    # 3. Desencriptar DNI solo para este uso
    try:
        dni = dni_manager.decrypt_dni(user.dni_encrypted)
    except Exception as e:
        logger.error(f"Error desencriptando DNI: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar datos del usuario"
        )
    
    # 4. Obtener datos del activo
    asset = get_tech_asset(db, assignment.tech_asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activo no encontrado"
        )
    
    # 5. Preparar datos para el PDF
    employee_data = {
        "full_name": user.full_name,
        "dni": dni,
        "email": user.email,
        "department": getattr(user, 'department', 'N/A')
    }
    
    asset_data = {
        "name": asset.name,
        "category": asset.category.value if hasattr(asset.category, 'value') else asset.category,
        "brand": asset.brand,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "asset_tag": asset.asset_tag or "N/A"
    }
    
    assignment_data = {
        "id": assignment.id,
        "assigned_date": assignment.assigned_date,
        "condition_at_assignment": assignment.condition_at_assignment or "Buen estado"
    }
    
    # 6. Generar PDF
    doc_generator = AssignmentDocumentGenerator()
    pdf_buffer = doc_generator.generate_assignment_pdf(
        assignment_data=assignment_data,
        employee_data=employee_data,
        asset_data=asset_data
    )
    
    # 7. Retornar PDF para preview
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=Asignacion_{assignment_id}_PREVIEW.pdf"
        }
    )


@router.post("/{assignment_id}/send-to-humand")
async def send_assignment_document_to_humand(
    assignment_id: int,
    send_notification: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Genera el PDF y lo envía a Humand
    
    Flujo:
    1. Genera el PDF (igual que preview)
    2. Envía el PDF a Humand API
    3. Actualiza el estado de la asignación
    
    Permisos: Solo administradores
    """
    # 1-6: Mismo flujo que generate_preview
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación no encontrada"
        )
    
    # Verificar que no se haya enviado antes
    if assignment.document_sent_to_humand:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El documento ya fue enviado a Humand el {assignment.document_sent_at.strftime('%d/%m/%Y %H:%M')}"
        )
    
    user = db.get(User, assignment.assigned_to_user_id)
    if not user or not user.dni_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario sin DNI registrado"
        )
    
    try:
        dni = dni_manager.decrypt_dni(user.dni_encrypted)
    except Exception as e:
        logger.error(f"Error desencriptando DNI: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar datos del usuario"
        )
    
    asset = get_tech_asset(db, assignment.tech_asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activo no encontrado"
        )
    
    # Preparar datos
    employee_data = {
        "full_name": user.full_name,
        "dni": dni,
        "email": user.email,
        "department": getattr(user, 'department', 'N/A')
    }
    
    asset_data = {
        "name": asset.name,
        "category": asset.category.value if hasattr(asset.category, 'value') else asset.category,
        "brand": asset.brand,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "asset_tag": asset.asset_tag or "N/A"
    }
    
    assignment_data = {
        "id": assignment.id,
        "assigned_date": assignment.assigned_date,
        "condition_at_assignment": assignment.condition_at_assignment or "Buen estado"
    }
    
    # Generar PDF
    doc_generator = AssignmentDocumentGenerator()
    pdf_buffer = doc_generator.generate_assignment_pdf(
        assignment_data=assignment_data,
        employee_data=employee_data,
        asset_data=asset_data
    )
    
    # 7. Enviar a Humand
    try:
        humand_response = await humand_service.upload_assignment_document(
            employee_dni=dni,
            pdf_buffer=pdf_buffer,
            assignment_id=assignment_id,
            send_notification=send_notification
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Error enviando a Humand: {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al enviar documento a Humand: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al enviar documento"
        )
    
    # 8. Actualizar asignación
    assignment.document_sent_to_humand = True
    assignment.document_sent_at = datetime.now(timezone.utc)
    assignment.humand_document_name = f"Asignacion_Activo_{assignment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    assignment.humand_folder_id = settings.HUMAND_FOLDER_ID
    
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    return {
        "message": "Documento generado y enviado a Humand exitosamente",
        "assignment_id": assignment_id,
        "employee_name": user.full_name,
        "asset_name": asset.name,
        "sent_at": assignment.document_sent_at.isoformat(),
        "humand_response": humand_response
    }


@router.get("/{assignment_id}/document-status")
async def get_assignment_document_status(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Consulta el estado del documento de asignación
    """
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asignación no encontrada"
        )
    
    return {
        "assignment_id": assignment_id,
        "document_sent": assignment.document_sent_to_humand,
        "sent_at": assignment.document_sent_at.isoformat() if assignment.document_sent_at else None,
        "document_name": assignment.humand_document_name,
        "folder_id": assignment.humand_folder_id
    }