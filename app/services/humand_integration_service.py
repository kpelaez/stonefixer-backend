"""
Servicio de integración con Humand API
Versión: 2.0 — Timeout por fases, manejo de errores robusto
"""

import json
import logging
from datetime import datetime
from io import BytesIO

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


# Timeouts diferenciados según la fase de la operación
_HUMAND_TIMEOUT = httpx.Timeout(
    connect=10.0,   # Establecer conexión TCP con Humand
    write=45.0,     # Subir el PDF (multipart/form-data puede ser lento)
    read=60.0,      # Esperar respuesta de Humand tras procesar el documento
    pool=5.0,       # Adquirir conexión del pool
)


class HumandIntegrationService:
    """
    Maneja la comunicación con la API de Humand.

    Responsabilidades:
    - Subir documentos PDF al legajo del empleado
    - Configurar firma digital con coordenadas correctas
    - Manejar errores de red, autenticación y timeout de forma explícita
    """

    def __init__(self) -> None:
        self.base_url = settings.HUMAND_API_URL
        self.api_key = settings.HUMAND_API_KEY
        self.folder_id = settings.HUMAND_FOLDER_ID

        if not self.api_key:
            raise ValueError(
                "HUMAND_API_KEY no configurada. "
                "Verificar variable de entorno HUMAND_API_KEY."
            )

    async def upload_assignment_document(
        self,
        employee_dni: str,
        pdf_buffer: BytesIO,
        assignment_id: int,
        send_notification: bool,       # Sin default: el caller decide siempre
    ) -> dict:
        """
        Sube el Acta de Entrega al legajo del empleado en Humand.

        Args:
            employee_dni:      DNI del empleado (employeeInternalId en Humand)
            pdf_buffer:        PDF en memoria generado por AssignmentDocumentGenerator
            assignment_id:     ID de la asignación en StoneFixer (para trazabilidad)
            send_notification: Si Humand debe notificar al empleado por email/push

        Returns:
            dict: Respuesta JSON de Humand (incluye el ID del documento creado)

        Raises:
            HTTPException 401: API key inválida o expirada
            HTTPException 404: Empleado no encontrado en Humand (DNI incorrecto)
            HTTPException 422: Datos inválidos rechazados por Humand
            HTTPException 502: Error inesperado del lado de Humand
            HTTPException 504: Timeout de red al comunicarse con Humand
        """
        filename = self._build_filename(assignment_id)
        url = f"{self.base_url}/users/{employee_dni}/documents/files"

        # Asegurar que el buffer esté al inicio antes de leerlo
        pdf_buffer.seek(0)

        files = {
            "file": (filename, pdf_buffer, "application/pdf"),
        }

        data = {
            "folderId": str(self.folder_id),
            "name": filename,
            "sendNotification": str(send_notification).lower(),
            "signatureStatus": "PENDING",
            "signatureCoordinates": self._get_signature_coordinates(),
            "allowDisagreement": "false",
        }

        headers = {
            "Authorization": self.api_key,
            "Accept": "application/json",
        }

        logger.info(
            f"[Humand] Iniciando envío — asignación #{assignment_id} "
            f"| empleado DNI: {employee_dni[:4]}*** "
            f"| notificación: {send_notification}"
        )

        try:
            async with httpx.AsyncClient(timeout=_HUMAND_TIMEOUT) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                )

            # Manejo explícito por código de estado de Humand

            if response.status_code == 400:
                logger.error(f"[Humand] Bad Request (400): {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Datos rechazados por Humand: {response.text}",
                )


            if response.status_code == 401:
                logger.error("[Humand] API key inválida o expirada (401)")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Error de autenticación con Humand. Verificar HUMAND_API_KEY.",
                )

            if response.status_code == 404:
                logger.warning(
                    f"[Humand] Empleado DNI {employee_dni[:4]}*** no encontrado (404)"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "El empleado no fue encontrado en Humand. "
                        "Verificar que el DNI esté registrado en el sistema."
                    ),
                )

            if response.status_code == 422:
                logger.error(f"[Humand] Datos inválidos (422): {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Datos rechazados por Humand: {response.text}",
                )

            # Cualquier otro 4xx/5xx
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"[Humand] Documento subido exitosamente — asignación #{assignment_id}"
            )
            return result

        except httpx.TimeoutException as exc:
            # Cloudflare corta la conexión antes de que Humand responda
            logger.error(
                f"[Humand] Timeout al enviar asignación #{assignment_id}: {exc}"
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=(
                    "Timeout al comunicarse con Humand. "
                    "El servidor de Humand tardó demasiado en responder. "
                    "Intentá nuevamente en unos minutos."
                ),
            )

        except httpx.ConnectError as exc:
            logger.error(f"[Humand] Error de conexión: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo establecer conexión con Humand. Verificar conectividad.",
            )

        except HTTPException:
            # Re-raise las HTTPException que lanzamos arriba (no envolver)
            raise

        except Exception as exc:
            logger.exception(
                f"[Humand] Error inesperado al enviar asignación #{assignment_id}: {exc}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error inesperado al comunicarse con Humand: {str(exc)}",
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers privados
    # ──────────────────────────────────────────────────────────────────────────

    def _build_filename(self, assignment_id: int) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"Acta_Entrega_Activo_{assignment_id}_{timestamp}.pdf"

    def _get_signature_coordinates(self) -> str:
        """
        Coordenadas de la zona de firma en el PDF.

        Sistema de coordenadas de Humand (página base-1):
        - page:   número de página (0 = primera)
        - x:      posición horizontal desde el borde izquierdo (0.0 a 1.0)
        - y:      posición vertical desde el borde SUPERIOR (0.0 a 1.0)
        - width:  ancho de la zona de firma como fracción del ancho de página
        - height: alto de la zona de firma como fracción del alto de página

        El PDF de StoneFixer tiene la sección de firma aproximadamente al 75–78%
        del alto de la página, alineada a la izquierda (margen 2cm ≈ 10% del ancho A4).
        """
        coordinates = [
            {
                "page": 0,
                "x": 0.10,
                "y": 0.75,
                "width": 0.42,
                "height": 0.08,
            }
        ]
        return json.dumps(coordinates)


# Instancia global — importar esto desde las rutas
humand_service = HumandIntegrationService()