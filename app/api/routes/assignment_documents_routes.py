import logging
from datetime import datetime, timezone
 
from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, or_, update
 
from app.api.deps import require_admin
from app.config import settings
from app.core.dni_security import dni_manager
from app.core.exceptions import (
    BusinessRuleViolationError,
    ExternalServiceError,
    InvalidOperationError,
    ResourceNotFoundError,
)
from app.db.database import get_db
from app.models.asset_assignment import AssetAssignment
from app.models.user import User
from app.services.asset_assignment_service import get_assignment
from app.services.assignment_document_service import AssignmentDocumentGenerator
from app.services.humand_integration_service import humand_service
from app.services.tech_asset_service import get_tech_asset
 
router = APIRouter()
logger = logging.getLogger(__name__)
 
 
# Helpers internos 
 
def _build_employee_data(user: User, assignment: AssetAssignment, dni: str) -> dict:
    return {
        "full_name": user.full_name,
        "dni": dni,
        "email": user.email,
        "department": getattr(user, "department", None) or assignment.location_of_use or "N/A",
    }
 
 
def _build_asset_data(asset) -> dict:
    return {
        "name": asset.name,
        "category": asset.category.value if hasattr(asset.category, "value") else asset.category,
        "brand": asset.brand,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "asset_tag": asset.asset_tag or "N/A",
    }
 
 
def _build_assignment_data(assignment: AssetAssignment) -> dict:
    return {
        "id": assignment.id,
        "assigned_date": assignment.assigned_date,
        "condition_at_assignment": assignment.condition_at_assignment or "Buen estado",
        "accessories": assignment.accessories or "Ninguno",
    }
 
 
def _resolve_user_and_dni(db: Session, assignment: AssetAssignment) -> tuple[User, str]:
    """
    Obtiene el usuario y desencripta su DNI.
    Usa excepciones centralizadas de StoneFixer.
    """
    user = db.get(User, assignment.assigned_to_user_id)
 
    if not user:
        raise ResourceNotFoundError(
            resource_type="Usuario",
            resource_id=assignment.assigned_to_user_id,
        )
 
    if not user.dni_encrypted:
        raise BusinessRuleViolationError(
            rule="DNI requerido para documentos",
            reason=(
                f"El usuario '{user.full_name}' no tiene DNI registrado. "
                "Es necesario para generar el Acta de Entrega."
            ),
        )
 
    try:
        dni = dni_manager.decrypt_dni(user.dni_encrypted)
    except Exception as exc:
        logger.error(
            f"Error desencriptando DNI para usuario {assignment.assigned_to_user_id}: {exc}"
        )
        raise ExternalServiceError(
            service_name="DNI Encryption",
            reason="No se pudo procesar el DNI del usuario. Contactá al administrador.",
        )
 
    return user, dni
 
 
# Tarea de background 
 
async def _send_to_humand_background(
    assignment_id: int,
    employee_dni: str,
    employee_name: str,
    send_notification: bool,
    employee_data: dict,
    asset_data: dict,
    assignment_data: dict,
) -> None:
    """
    Genera el PDF y lo envía a Humand de forma asíncrona.
    Actualiza el estado en la DB según el resultado.
 
    Crea su propia sesión de DB porque corre fuera del request/response cycle.
    """
    from app.db.database import get_background_session
    from fastapi import HTTPException

    with get_background_session() as db:
        try:
            assignment = db.get(AssetAssignment, assignment_id)
            if not assignment:
                logger.error(
                    f"[BG-Humand] Asignación #{assignment_id} no encontrada en background task"
                )
                return
    
            # Registrar timestamp del intento
            assignment.humand_last_attempt_at = datetime.now(timezone.utc)
            db.add(assignment)
            db.commit()
    
            # Generar PDF
            logger.info(f"[BG-Humand] Generando PDF — asignación #{assignment_id}")
            doc_generator = AssignmentDocumentGenerator()
            pdf_buffer = doc_generator.generate_assignment_pdf(
                assignment_data=assignment_data,
                employee_data=employee_data,
                asset_data=asset_data,
            )
    
            # Enviar a Humand
            logger.info(f"[BG-Humand] Enviando a Humand — asignación #{assignment_id}")
            humand_response = await humand_service.upload_assignment_document(
                employee_dni=employee_dni,
                pdf_buffer=pdf_buffer,
                assignment_id=assignment_id,
                send_notification=send_notification,
            )
    
            # Éxito — actualizar estado
            now = datetime.now(timezone.utc)
            assignment.document_sent_to_humand = True
            assignment.humand_send_status = "SENT"
            assignment.document_sent_at = now
            assignment.humand_last_attempt_at = now
            assignment.humand_document_name = humand_response.get(
                "name",
                f"Acta_Entrega_Activo_{assignment_id}.pdf",
            )
            assignment.humand_folder_id = settings.HUMAND_FOLDER_ID
            assignment.humand_error_detail = None
    
            db.add(assignment)
            db.commit()
            logger.info(f"[BG-Humand] ✓ Enviado y registrado — asignación #{assignment_id}")
    
        except HTTPException as exc:
            # Las HTTPException que lanza humand_service (timeout, 404, 401, etc.)
            db.rollback()
            error_detail = exc.detail
            logger.error(
                f"[BG-Humand] Error en envío asignación #{assignment_id}: {error_detail}"
            )
            assignment = db.get(AssetAssignment, assignment_id)
            if assignment:
                assignment.humand_send_status = "FAILED"
                assignment.humand_error_detail = str(error_detail)[:500]
                assignment.humand_last_attempt_at = datetime.now(timezone.utc)
                db.add(assignment)
                db.commit()
    
        except Exception as exc:
            db.rollback()
            logger.exception(
                f"[BG-Humand] Error inesperado asignación #{assignment_id}: {exc}"
            )
            assignment = db.get(AssetAssignment, assignment_id)
            if assignment:
                assignment.humand_send_status = "FAILED"
                assignment.humand_error_detail = f"Error inesperado: {str(exc)[:400]}"
                assignment.humand_last_attempt_at = datetime.now(timezone.utc)
                db.add(assignment)
                db.commit()

 
 
# Endpoints
 
@router.post("/{assignment_id}/generate-preview")
async def generate_assignment_document_preview(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Genera y retorna el PDF de asignación para preview.
    NO envía a Humand ni modifica el estado de la asignación.
    """
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise ResourceNotFoundError(resource_type="Asignación", resource_id=assignment_id)
 
    user, dni = _resolve_user_and_dni(db, assignment)
 
    asset = get_tech_asset(db, assignment.tech_asset_id)
    if not asset:
        raise ResourceNotFoundError(resource_type="Activo tecnológico", resource_id=assignment.tech_asset_id)
 
    doc_generator = AssignmentDocumentGenerator()
    pdf_buffer = doc_generator.generate_assignment_pdf(
        assignment_data=_build_assignment_data(assignment),
        employee_data=_build_employee_data(user, assignment, dni),
        asset_data=_build_asset_data(asset),
    )
 
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=Asignacion_{assignment_id}_PREVIEW.pdf"
        },
    )
 
 
@router.post("/{assignment_id}/send-to-humand", status_code=status.HTTP_202_ACCEPTED)
async def send_assignment_document_to_humand(
    assignment_id: int,
    background_tasks: BackgroundTasks,
    send_notification: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Genera el PDF y lo envía a Humand en background.
 
    Flujo:
    1. Valida asignación, usuario y activo
    2. Marca la asignación como PENDING
    3. Encola el envío en background (evita timeout de Cloudflare)
    4. Responde 202 Accepted inmediatamente
 
    El frontend debe consultar GET /{assignment_id}/document-status
    para conocer el resultado: PENDING → SENT | FAILED
 
    Permisos: Solo administradores
    """
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise ResourceNotFoundError(resource_type="Asignación", resource_id=assignment_id)
 
    # Ya fue enviado anteriormente
    if assignment.document_sent_to_humand:
        sent_at = (
            assignment.document_sent_at.strftime("%d/%m/%Y %H:%M")
            if assignment.document_sent_at
            else "fecha desconocida"
        )
        raise InvalidOperationError(
            operation="Envío a Humand",
            reason=f"El documento ya fue enviado el {sent_at}. Esta acción no se puede repetir.",
        )
 
    # Hay un envío en curso
    if assignment.humand_send_status == "PENDING":
        raise BusinessRuleViolationError(
            rule="Envío único simultáneo",
            reason="Ya hay un envío en curso para esta asignación. Esperá unos segundos y verificá el estado.",
        )
 
    user, dni = _resolve_user_and_dni(db, assignment)
 
    asset = get_tech_asset(db, assignment.tech_asset_id)
    if not asset:
        raise ResourceNotFoundError(
            resource_type="Activo tecnológico",
            resource_id=assignment.tech_asset_id,
        )
 
    # Pre-calcular datos para el background task antes de cerrar la sesión
    employee_data = _build_employee_data(user, assignment, dni)
    asset_data = _build_asset_data(asset)
    assignment_data = _build_assignment_data(assignment)
 
    # Marcar PENDING de forma atómica — evita doble envío por doble clic
    result = db.execute(
        update(AssetAssignment)
        .where(
            AssetAssignment.id == assignment_id,
            AssetAssignment.document_sent_to_humand == False,
            or_(
                AssetAssignment.humand_send_status != "PENDING",
                AssetAssignment.humand_send_status.is_(None),
            ),
        )
        .values(humand_send_status="PENDING", humand_error_detail=None)
    )
    db.commit()

    if result.rowcount == 0:
        raise BusinessRuleViolationError(
            rule="Envío único simultáneo",
            reason="Ya hay un envío en curso o el documento ya fue enviado.",
        )
 
    background_tasks.add_task(
        _send_to_humand_background,
        assignment_id=assignment_id,
        employee_dni=dni,
        employee_name=user.full_name,
        send_notification=send_notification,
        employee_data=employee_data,
        asset_data=asset_data,
        assignment_data=assignment_data,
    )
 
    logger.info(
        f"[Humand] Envío encolado — asignación #{assignment_id} "
        f"| empleado: {user.full_name} | notificación: {send_notification}"
    )
 
    return {
        "message": "El documento está siendo generado y enviado a Humand.",
        "assignment_id": assignment_id,
        "employee_name": user.full_name,
        "asset_name": asset.name,
        "status": "PENDING",
        "detail": "Consultá el estado en unos segundos con GET /document-status",
    }
 
 
@router.get("/{assignment_id}/document-status")
async def get_assignment_document_status(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Retorna el estado actual del envío a Humand.
 
    Valores posibles de send_status:
    - null:     Nunca se intentó enviar
    - PENDING:  Envío en curso
    - SENT:     Confirmado por Humand
    - FAILED:   Falló — ver error_detail para el motivo
    """
    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        raise ResourceNotFoundError(resource_type="Asignación", resource_id=assignment_id)
 
    return {
        "assignment_id": assignment_id,
        "send_status": assignment.humand_send_status,
        "document_sent": assignment.document_sent_to_humand,
        "sent_at": assignment.document_sent_at.isoformat() if assignment.document_sent_at else None,
        "last_attempt_at": (
            assignment.humand_last_attempt_at.isoformat()
            if assignment.humand_last_attempt_at
            else None
        ),
        "document_name": assignment.humand_document_name,
        "folder_id": assignment.humand_folder_id,
        "error_detail": assignment.humand_error_detail,
    }
 