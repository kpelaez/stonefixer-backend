"""
Servicio de generación de documentos de asignación de activos
Versión: 2.0 - Con estructura formal de política
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
from io import BytesIO
import textwrap

class AssignmentDocumentGenerator:
    """
    Genera PDFs de asignación de activos con política formal
    """
    
    def __init__(self):
        # Colores corporativos (ajustá según tu empresa)
        self.primary_color = HexColor("#2C3E50")
        self.secondary_color = HexColor("#34495E")
        self.text_color = black

    def _translate_condition(self, condition: str) -> str:
        """Traduce códigos de condición a español"""
        translations = {
            "excellent": "Excelente",
            "good": "Bueno",
            "fair": "Regular",
            "poor": "Malo"
        }
        return translations.get(condition, condition)
        
    def generate_assignment_pdf(
        self,
        assignment_data: dict,
        employee_data: dict,
        asset_data: dict
    ) -> BytesIO:
        """
        Genera PDF de asignación con estructura formal
        
        Args:
            assignment_data: {
                "id": int,
                "assigned_date": datetime,
                "condition_at_assignment": str,
                "accessories": str (opcional)
            }
            employee_data: {
                "full_name": str,
                "dni": str,
                "email": str,
                "department": str (opcional)
            }
            asset_data: {
                "name": str,
                "category": str,
                "brand": str,
                "model": str,
                "asset_tag": str,
            }
            
        Returns:
            BytesIO: PDF en memoria
        """
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Márgenes
        left_margin = 2*cm
        right_margin = width - 2*cm

        # DIBUJAR LOGO (antes del título)
        self._draw_logo(c, width, height)
        
        # === TÍTULO PRINCIPAL ===
        y_position = height - 2.5*cm
        y_position = self._draw_main_title(c, y_position, width)
        
        # === SECCIÓN 1: OBJETIVO ===
        y_position -= 1*cm
        y_position = self._draw_section(
            c, y_position, left_margin, right_margin,
            "1. Objetivo",
            "Establecer las condiciones de uso, cuidado y devolución de los activos tecnológicos "
            "entregados por la empresa al colaborador para el desempeño de sus funciones laborales."
        )
        
        # === SECCIÓN 2: ALCANCE ===
        y_position -= 0.8*cm
        y_position = self._draw_section(
            c, y_position, left_margin, right_margin,
            "2. Alcance",
            "Aplica a todos los colaboradores que reciban activos tecnológicos propiedad de la empresa."
        )
        
        # === SECCIÓN 3: ACTIVO ASIGNADO ===
        y_position -= 0.8*cm
        y_position = self._draw_asset_section(
            c, y_position, left_margin, right_margin,
            asset_data, assignment_data
        )
        
        # === SECCIÓN 4: PROPIEDAD DEL ACTIVO ===
        y_position -= 0.8*cm
        y_position = self._draw_section(
            c, y_position, left_margin, right_margin,
            "4. Propiedad del activo",
            "El activo entregado es propiedad exclusiva de la empresa y se asigna únicamente para fines laborales."
        )
        
        # === SECCIÓN 5: CONDICIONES DE USO ===
        y_position -= 0.8*cm
        y_position = self._draw_bullet_section(
            c, y_position, left_margin, right_margin,
            "5. Condiciones de uso",
            "El colaborador se compromete a:",
            [
                "Utilizar el activo únicamente para tareas relacionadas con su trabajo.",
                "No prestar, alquilar, vender ni ceder el equipo a terceros.",
                "No utilizar el activo para actividades comerciales personales o externas."
            ]
        )
        
        # === SECCIÓN 6: RESPONSABILIDAD Y CUIDADO ===
        y_position -= 0.8*cm
        y_position = self._draw_bullet_section(
            c, y_position, left_margin, right_margin,
            "6. Responsabilidad y cuidado",
            "El colaborador es responsable por:",
            [
                "El cuidado físico del equipo.",
                "Los daños ocasionados por mal uso, negligencia o incumplimiento de esta política.",
                "Informar de inmediato cualquier daño, pérdida o robo."
            ],
            footer_text="En caso de robo o extravío, deberá presentar la denuncia correspondiente."
        )
        
        # Verificar si necesitamos nueva página
        if y_position < 10*cm:
            c.showPage()
            y_position = height - 3*cm
        
        # === SECCIÓN 7: SOFTWARE, SEGURIDAD Y CONFIDENCIALIDAD ===
        y_position -= 0.8*cm
        y_position = self._draw_security_section(
            c, y_position, left_margin, right_margin
        )
        
        # === SECCIÓN 8: AUDITORÍA Y MONITOREO ===
        y_position -= 0.8*cm
        y_position = self._draw_audit_section(
            c, y_position, left_margin, right_margin
        )
        
        # === SECCIÓN 9: DEVOLUCIÓN DEL ACTIVO ===
        y_position -= 0.8*cm
        y_position = self._draw_return_section(
            c, y_position, left_margin, right_margin
        )
        
        # === SECCIÓN 10: ACEPTACIÓN Y FIRMA ===
        y_position -= 1*cm
        self._draw_signature_section(
            c, y_position, left_margin, right_margin, width,
            employee_data, assignment_data
        )
        
        # === FOOTER ===
        self._draw_footer(c, width, assignment_data["id"])
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _draw_main_title(self, c, y_position, width) -> float:
        """Dibuja el título principal del documento"""
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 14)
        
        # Título en dos líneas
        c.drawCentredString(width/2, y_position, "POLÍTICA DE USO Y RESPONSABILIDAD")
        y_position -= 0.5*cm
        c.drawCentredString(width/2, y_position, "DE ACTIVOS TECNOLÓGICOS")
        y_position -= 0.4*cm
        
        # Línea divisoria
        left_margin = 2*cm
        right_margin = width - 2*cm
        c.setLineWidth(1.5)
        c.line(left_margin + 1*cm, y_position, right_margin - 1*cm, y_position)
        y_position -= 0.3*cm
        
        return y_position - 0.5*cm
    
    def _draw_logo(self, c, width, height):
        """
        Dibuja el logo de Omnimedica en el encabezado
        
        Args:
            c: Canvas de ReportLab
            width: ancho de la página
            height: alto de la página
        """
        try:
            # Path al logo
            logo_path = "app/static/omnimedica_logo.png"  
            
            # Dimensiones del logo
            logo_width = 5*cm
            logo_height = 2*cm

            logo_bottom = height - 2*cm
            
            # Posición: esquina superior derecha
            x_position = (width - logo_width) /2
            
            c.drawImage(
                logo_path,
                x_position,
                logo_bottom,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask='auto'  # Para transparencia si el PNG la tiene
            )

            return logo_bottom + 0.8*cm
        
        except FileNotFoundError:
            # Si no encuentra el logo, dibuja un placeholder
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(HexColor("#119718"))
            c.drawString(width/2, height - 2*cm, "[Logo Omnimedica]")
            return height - 3*cm
        except Exception as e:
            # Log del error pero no rompe el PDF
            import logging
            logging.warning(f"No se pudo cargar el logo: {e}")
            return height - 3*cm
    
    def _draw_section(self, c, y_position, left_margin, right_margin, title, content) -> float:
        """Dibuja una sección simple con título y contenido"""
        # Título de sección
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_margin, y_position, title)
        y_position -= 0.5*cm
        
        # Contenido
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 9)
        
        # Wrap text
        max_width = 80  # caracteres
        wrapped_lines = textwrap.wrap(content, width=max_width)
        
        for line in wrapped_lines:
            c.drawString(left_margin, y_position, line)
            y_position -= 0.4*cm
        
        return y_position
    
    def _draw_asset_section(self, c, y_position, left_margin, right_margin, asset_data, assignment_data) -> float:
        """Dibuja la sección 3: Activo asignado"""
        # Título
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_margin, y_position, "3. Activo asignado")
        y_position -= 0.5*cm
        
        # Intro
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y_position, "El colaborador declara haber recibido el siguiente activo tecnológico:")
        y_position -= 0.6*cm
        
        # Campos del activo
        c.setFont("Helvetica", 9)
        
        fields = [
            ("Tipo de equipo:", asset_data.get("category", "N/A")),
            ("Descripción:", asset_data.get("name", "N/A")),
            ("Marca y Modelo:", f"{asset_data.get('brand', 'N/A')} {asset_data.get('model', 'N/A')}"),
            ("Nro de Tag:", asset_data.get("asset_tag", "N/A")),
            ("Accesorios:", assignment_data.get("accessories", "N/A")),
            ("Estado al momento de la asignación:", self._translate_condition(assignment_data.get("condition_at_assignment", "good")))
        ]
        
        for label, value in fields:
            # Label en negrita
            c.setFont("Helvetica-Bold", 9)
            c.drawString(left_margin + 0.5*cm, y_position, f"• {label}")
            
            # Valor
            c.setFont("Helvetica", 9)
            # Línea para completar
            label_width = c.stringWidth(f"• {label} ", "Helvetica-Bold", 9)
            c.drawString(left_margin + 0.5*cm + label_width, y_position, value)
            
            y_position -= 0.5*cm
        
        return y_position
    
    def _draw_bullet_section(self, c, y_position, left_margin, right_margin, 
                            title, intro, bullets, footer_text=None) -> float:
        """Dibuja una sección con bullets"""
        # Título
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_margin, y_position, title)
        y_position -= 0.5*cm
        
        # Intro
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y_position, intro)
        y_position -= 0.5*cm
        
        # Bullets
        for bullet in bullets:
            c.drawString(left_margin + 0.5*cm, y_position, f"• {bullet}")
            y_position -= 0.4*cm
        
        # Footer text (opcional)
        if footer_text:
            y_position -= 0.2*cm
            c.setFont("Helvetica-Oblique", 9)
            wrapped_lines = textwrap.wrap(footer_text, width=80)
            for line in wrapped_lines:
                c.drawString(left_margin, y_position, line)
                y_position -= 0.4*cm
        
        return y_position
    
    def _draw_security_section(self, c, y_position, left_margin, right_margin) -> float:
        """Dibuja sección 7: Software, seguridad y confidencialidad"""
        # Título
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_margin, y_position, "7. Software, seguridad y confidencialidad")
        y_position -= 0.5*cm
        
        # "Está prohibido:"
        c.setFillColor(self.text_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left_margin, y_position, "Está prohibido:")
        y_position -= 0.5*cm
        
        prohibitions = [
            "Instalar software sin autorización de la empresa.",
            "Modificar configuraciones de seguridad.",
            "Desactivar antivirus u otros sistemas de protección."
        ]
        
        c.setFont("Helvetica", 9)
        for item in prohibitions:
            c.drawString(left_margin + 0.5*cm, y_position, f"• {item}")
            y_position -= 0.4*cm
        
        # Compromiso
        y_position -= 0.2*cm
        c.setFont("Helvetica", 9)
        commitment = (
            "El colaborador se compromete a proteger contraseñas y accesos, así como toda información "
            "sensible, comercial y técnica a la que acceda mediante el uso del activo, incluyendo datos "
            "de clientes, información de proveedores y cualquier información vinculada a la actividad de la empresa."
        )
        
        wrapped_lines = textwrap.wrap(commitment, width=80)
        for line in wrapped_lines:
            c.drawString(left_margin, y_position, line)
            y_position -= 0.4*cm
        
        return y_position
    
    def _draw_audit_section(self, c, y_position, left_margin, right_margin) -> float:
        """Dibuja sección 8: Auditoría y monitoreo"""
        # Título
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_margin, y_position, "8. Auditoría y monitoreo")
        y_position -= 0.5*cm
        
        # "La empresa se reserva el derecho de:"
        c.setFillColor(self.text_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left_margin, y_position, "La empresa se reserva el derecho de:")
        y_position -= 0.5*cm
        
        rights = [
            "Revisar el equipo cuando lo considere necesario.",
            "Implementar sistemas de monitoreo, seguridad y gestión remota."
        ]
        
        c.setFont("Helvetica", 9)
        for item in rights:
            c.drawString(left_margin + 0.5*cm, y_position, f"• {item}")
            y_position -= 0.4*cm
        
        # Nota final
        y_position -= 0.2*cm
        c.setFont("Helvetica", 9)
        c.drawString(
            left_margin, y_position,
            "El colaborador acepta que no existe expectativa de privacidad absoluta sobre el equipo."
        )
        y_position -= 0.4*cm
        
        return y_position
    
    def _draw_return_section(self, c, y_position, left_margin, right_margin) -> float:
        """Dibuja sección 9: Devolución del activo"""
        # Título
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_margin, y_position, "9. Devolución del activo")
        y_position -= 0.5*cm
        
        # "El activo deberá ser devuelto:"
        c.setFillColor(self.text_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left_margin, y_position, "El activo deberá ser devuelto:")
        y_position -= 0.5*cm
        
        conditions = [
            "Al finalizar la relación laboral.",
            "Cuando la empresa lo solicite."
        ]
        
        c.setFont("Helvetica", 9)
        for item in conditions:
            c.drawString(left_margin + 0.5*cm, y_position, f"• {item}")
            y_position -= 0.4*cm
        
        # Condiciones de devolución
        y_position -= 0.2*cm
        c.drawString(
            left_margin, y_position,
            "La devolución deberá realizarse en buen estado y con todos sus accesorios."
        )
        y_position -= 0.5*cm
        
        c.setFont("Helvetica-Oblique", 9)
        warning = (
            "En caso de no devolución o deterioro injustificado, la empresa podrá reclamar el valor correspondiente."
        )
        c.drawString(left_margin, y_position, warning)
        y_position -= 0.4*cm
        
        return y_position
    
    def _draw_signature_section(self, c, y_position, left_margin, right_margin, width,
                                employee_data, assignment_data):
        """Dibuja sección 10: Aceptación y firma"""
        # Título
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_margin, y_position, "10. Aceptación")
        y_position -= 0.5*cm
        
        # Declaración
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 9)
        declaration = "El colaborador declara haber leído, comprendido y aceptado la presente política."
        c.drawString(left_margin, y_position, declaration)
        y_position -= 1.2*cm
        
        # === FIRMA ===
        # Línea de firma (AQUÍ VAN LAS COORDENADAS PARA HUMAND)
        c.setLineWidth(1)
        c.line(left_margin, y_position, left_margin + 8*cm, y_position)
        y_position -= 0.5*cm
        
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y_position, "Firma del colaborador")
        
        # === NOMBRE (PRE-LLENADO) ===
        y_position -= 1*cm
        c.setLineWidth(1)
        c.line(left_margin, y_position, left_margin + 8*cm, y_position)
        y_position -= 0.5*cm
        
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y_position, "Nombre o Aclaración:")
        
        # Escribir el nombre del colaborador
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left_margin + 4.5*cm, y_position, employee_data["full_name"])
        
        # === DNI (PRE-LLENADO) ===
        y_position -= 0.3*cm
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y_position, f"DNI: {employee_data['dni']}")
        
        # === FECHA DE ASIGNACIÓN (PRE-LLENADA) ===
        y_position -= 0.3*cm
        c.drawString(
            left_margin, 
            y_position, 
            f"Fecha de asignación: {assignment_data['assigned_date'].strftime('%d/%m/%Y')}"
        )
    
    def _draw_footer(self, c, width, assignment_id):
        """Dibuja footer con info del documento"""
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#7F8C8D"))
        
        footer_text = (
            f"Documento generado automáticamente por StoneFixer | "
            f"ID Asignación: #{assignment_id} | "
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        
        c.drawCentredString(width/2, 1*cm, footer_text)