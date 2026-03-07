# app/core/dni_security.py
"""
Sistema de encriptación segura de DNIs
Cumple con Ley 25.326 de Protección de Datos Personales (Argentina)
"""

from cryptography.fernet import Fernet
import hashlib
from app.config import settings

class DNISecurityManager:
    """
    Maneja encriptación/desencriptación de DNIs de forma segura
    """
    
    def __init__(self):
        if not settings.DNI_ENCRYPTION_KEY:
            raise ValueError(
                "DNI_ENCRYPTION_KEY no configurada. "
                "Esto es obligatorio para el cumplimiento legal."
            )
        self.cipher = Fernet(settings.DNI_ENCRYPTION_KEY.encode())
    
    def encrypt_dni(self, dni: str) -> str:
        """
        Encripta un DNI
        
        Args:
            dni: DNI en texto plano (ej: "12345678")
            
        Returns:
            str: DNI encriptado
        """
        # Normalizar DNI (remover espacios, puntos)
        clean_dni = dni.strip().replace(".", "").replace("-", "")
        return self.cipher.encrypt(clean_dni.encode()).decode()
    
    def decrypt_dni(self, encrypted_dni: str) -> str:
        """
        Desencripta un DNI
        
        ⚠️ IMPORTANTE: Solo usar cuando sea absolutamente necesario
        (ej: envío a Humand, generación de documentos)
        
        Args:
            encrypted_dni: DNI encriptado
            
        Returns:
            str: DNI en texto plano
        """
        return self.cipher.decrypt(encrypted_dni.encode()).decode()
    
    def hash_dni(self, dni: str) -> str:
        """
        Genera hash SHA256 del DNI para búsquedas
        
        Args:
            dni: DNI en texto plano
            
        Returns:
            str: Hash SHA256
        """
        clean_dni = dni.strip().replace(".", "").replace("-", "")
        return hashlib.sha256(clean_dni.encode()).hexdigest()
    
    def verify_dni(self, dni: str, dni_hash: str) -> bool:
        """
        Verifica si un DNI coincide con su hash
        
        Args:
            dni: DNI en texto plano
            dni_hash: Hash almacenado
            
        Returns:
            bool: True si coinciden
        """
        return self.hash_dni(dni) == dni_hash


# Instancia global
dni_manager = DNISecurityManager()