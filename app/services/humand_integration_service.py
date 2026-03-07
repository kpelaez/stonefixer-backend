import httpx
from datetime import datetime
from io import BytesIO
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class HumandIntegrationService:
    """
    Maneja la comunicación con la API de Humand
    """
    
    def __init__(self):
        self.base_url = settings.HUMAND_API_URL
        self.api_key = settings.HUMAND_API_KEY
        self.folder_id = settings.HUMAND_FOLDER_ID
        
        if not self.api_key:
            raise ValueError("HUMAND_API_KEY no configurada")
    
    async def upload_assignment_document(
        self,
        employee_dni: str,
        pdf_buffer: BytesIO,
        assignment_id: int,
        send_notification: bool = False #Cambiar luego en produccion
    ) -> dict:
        """
        Sube documento de asignación a Humand
        
        Args:
            employee_dni: DNI del empleado (employeeInternalId en Humand)
            pdf_buffer: PDF en memoria
            assignment_id: ID de la asignación en StoneFixer
            send_notification: Si enviar notificación al empleado
            
        Returns:
            dict: Respuesta de Humand
            
        Raises:
            httpx.HTTPStatusError: Si falla la petición
        """
        # Nombre único del archivo
        filename = f"Asignacion_Activo_{assignment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Preparar datos multipart/form-data
        files = {
            'file': (filename, pdf_buffer, 'application/pdf')
        }
        
        data = {
            'folderId': str(self.folder_id),
            'name': filename,
            'sendNotification': str(send_notification).lower(),
            'signatureStatus': 'PENDING',  # Requiere firma
            'signatureCoordinates': self._get_signature_coordinates(),
            'allowDisagreement': 'false'
        }
        
        url = f"{self.base_url}/users/{employee_dni}/documents/files"
        
        headers = {
            'Authorization': self.api_key,
            'Accept': 'application/json'
        }
        
        logger.info(f"Enviando documento a Humand para empleado {employee_dni}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers=headers,
                files=files,
                data=data
            )
            response.raise_for_status()
            
        logger.info(f"Documento enviado exitosamente a Humand")
        
        return response.json()
    
    def _get_signature_coordinates(self) -> str:
        """
        Retorna coordenadas de firma (FIJAS para template estándar)

        Estas coordenadas son para la línea de firma en la parte inferior del documento
        """
        coordinates = [{
            "page": 1,  # Segunda página
            "x": 0.10,  # 10% desde la izquierda
            "y": 0.80,  # 80% desde arriba (20% desde abajo)
            "height": 0.08,  # 8% de altura
            "width": 0.40   # 40% de ancho
        }]
        
        import json
        return json.dumps(coordinates)


# Instancia global
humand_service = HumandIntegrationService()