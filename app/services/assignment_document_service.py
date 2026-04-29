"""
Servicio de generación de Acta de Entrega de Activos Tecnológicos
Versión: 3.0 - Acta simple, una página, lista para firma en Humand
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from datetime import datetime
from io import BytesIO

class AssignmentDocumentGenerator:
    """
    Genera Actas de Entrega de activos tecnológicos.
    Diseño limpio, una página, apto para firma digital en Humand.
    """

    def __init__(self):
        self.primary_color = HexColor("#1a3a2a")      # Verde oscuro corporativo
        self.accent_color = HexColor("#2d7a4f")       # Verde medio
        self.light_bg = HexColor("#f0f7f3")           # Fondo muy suave
        self.border_color = HexColor("#b2d8c4")       # Borde suave
        self.text_color = HexColor("#1a1a1a")
        self.muted_color = HexColor("#5a5a5a")

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
        asset_data: dict,
    ) -> BytesIO:
        """
        Genera el Acta de Entrega en formato PDF.

        Args:
            assignment_data: id, assigned_date, condition_at_assignment, accessories
            employee_data:   full_name, dni, email, department
            asset_data:      name, category, brand, model, serial_number, asset_tag
        Returns:
            BytesIO con el PDF listo para enviar a Humand
        """
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        left = 2 * cm
        right = width - 2 * cm
        content_width = right - left

        y = height - 1.5 * cm

        # ── Logo ──────────────────────────────────────────────────────────────
        y = self._draw_logo(c, width, height, y)

        # ── Título ────────────────────────────────────────────────────────────
        y -= 0.4 * cm
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, y, "ACTA DE ENTREGA DE ACTIVO TECNOLÓGICO")
        y -= 0.3 * cm

        # Línea decorativa bajo el título
        c.setStrokeColor(self.accent_color)
        c.setLineWidth(2)
        c.line(left + 2 * cm, y, right - 2 * cm, y)
        y -= 0.6 * cm

        # Número de acta y fecha — alineados
        c.setFont("Helvetica", 8)
        c.setFillColor(self.muted_color)
        c.drawString(left, y, f"N° de Asignación: #{assignment_data['id']}")
        fecha_str = self._format_date(assignment_data["assigned_date"])
        c.drawRightString(right, y, f"Fecha de entrega: {fecha_str}")
        y -= 1.0 * cm

        # ── Sección Empleado ──────────────────────────────────────────────────
        y = self._draw_card(
            c, y, left, right, content_width,
            title="DATOS DEL EMPLEADO",
            rows=[
                ("Apellido y Nombre", employee_data.get("full_name", "—")),
                ("DNI",               employee_data.get("dni", "—")),
                ("Sector / Área",     employee_data.get("department") or "—"),
            ],
            two_col=True,
        )
        y -= 0.5 * cm

        # ── Sección Activo ────────────────────────────────────────────────────
        y = self._draw_card(
            c, y, left, right, content_width,
            title="DATOS DEL ACTIVO",
            rows=[
                ("Tipo",           asset_data.get("category", "—")),
                ("Descripción",    asset_data.get("name", "—")),
                ("Marca",          asset_data.get("brand", "—")),
                ("Modelo",         asset_data.get("model", "—")),
                ("N° de Serie",    asset_data.get("serial_number", "—")),
                ("Asset Tag",      asset_data.get("asset_tag") or "—"),
            ],
            two_col=True,
        )
        y -= 0.5 * cm

        # ── Sección Entrega ───────────────────────────────────────────────────
        condition_label = self._translate_condition(
            assignment_data.get("condition_at_assignment", "good")
        )
        accessories = assignment_data.get("accessories") or "Ninguno"

        y = self._draw_card(
            c, y, left, right, content_width,
            title="CONDICIONES DE ENTREGA",
            rows=[
                ("Estado del equipo", condition_label),
                ("Accesorios incluidos", accessories),
            ],
            two_col=False,
        )
        y -= 0.7 * cm

        # ── Cláusula legal ────────────────────────────────────────────────────
        y = self._draw_clause(c, y, left, right, content_width)
        y -= 1.0 * cm

        # ── Firma ─────────────────────────────────────────────────────────────
        self._draw_signature(c, y, left, right, employee_data, assignment_data)

        # ── Footer ────────────────────────────────────────────────────────────
        self._draw_footer(c, width, assignment_data["id"])

        c.save()
        buffer.seek(0)
        return buffer
        
    def _format_date(self, date_value) -> str:
        if date_value is None:
            return "—"
        if isinstance(date_value, str):
            try:
                date_value = datetime.fromisoformat(date_value)
            except ValueError:
                return date_value
        return date_value.strftime("%d/%m/%Y")
    
    def _draw_logo(self, c, width, height, y) -> float:
        """Dibuja el logo centrado. Devuelve la nueva posición Y."""
        try:
            logo_path = "app/static/omnimedica_logo.png"
            logo_w = 5 * cm
            logo_h = 2 * cm
            x = (width - logo_w) / 2
            logo_y = height - 1.5 * cm - logo_h
            c.drawImage(
                logo_path, x, logo_y,
                width=logo_w, height=logo_h,
                preserveAspectRatio=True, mask="auto",
            )
            return logo_y - 0.3 * cm
        except Exception:
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(HexColor("#119718"))
            c.drawCentredString(width / 2, y - 1 * cm, "Omnimedica")
            return y - 1.5 * cm

    def _draw_card(
        self, c, y, left, right, content_width,
        title: str, rows: list[tuple], two_col: bool = True,
    ) -> float:
        """
        Dibuja un bloque tipo 'card' con título y filas de datos.
        two_col=True: label izquierda, valor derecha en dos columnas.
        two_col=False: label y valor en la misma fila completa.
        """
        padding = 0.3 * cm
        row_h = 0.55 * cm
        header_h = 0.6 * cm

        # Calcular altura total del card
        total_h = header_h + padding + len(rows) * row_h + padding

        card_y_top = y
        card_y_bottom = y - total_h

        # Fondo del card
        c.setFillColor(white)
        c.setStrokeColor(self.border_color)
        c.setLineWidth(0.5)
        c.roundRect(left, card_y_bottom, content_width, total_h, 4, fill=1, stroke=1)

        # Header del card
        c.setFillColor(self.accent_color)
        c.roundRect(left, card_y_top - header_h, content_width, header_h, 4, fill=1, stroke=0)
        # Esquinas inferiores del header cuadradas (truco: rect encima)
        c.rect(left, card_y_top - header_h, content_width, header_h / 2, fill=1, stroke=0)

        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left + padding * 2, card_y_top - header_h + 0.18 * cm, title)

        # Filas de datos
        row_y = card_y_top - header_h - padding - 0.1 * cm
        col_mid = left + content_width * 0.38  # 38% para labels

        for i, (label, value) in enumerate(rows):
            # Fondo alternado suave
            if i % 2 == 0:
                c.setFillColor(self.light_bg)
                c.rect(left + 1, row_y - row_h + 0.05 * cm,
                       content_width - 2, row_h - 0.05 * cm, fill=1, stroke=0)

            c.setFillColor(self.muted_color)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(left + padding * 2, row_y - 0.35 * cm, f"{label}:")

            c.setFillColor(self.text_color)
            c.setFont("Helvetica", 8)
            if two_col:
                c.drawString(col_mid, row_y - 0.35 * cm, str(value))
            else:
                c.drawString(left + padding * 2 + 4.5 * cm, row_y - 0.35 * cm, str(value))

            row_y -= row_h

        return card_y_bottom

    def _draw_clause(self, c, y, left, right, content_width) -> float:
        """Dibuja la cláusula legal en un recuadro destacado."""
        text = (
            "El colaborador declara recibir el activo descripto en conformidad y se compromete "
            "a devolverlo en las mismas condiciones al finalizar la relación laboral o cuando "
            "la empresa así lo requiera."
        )

        # Calcular altura necesaria
        c.setFont("Helvetica-Oblique", 8)
        # ~90 chars por línea a 8pt con este ancho
        import textwrap
        lines = textwrap.wrap(text, width=100)
        box_h = 0.4 * cm + len(lines) * 0.45 * cm + 0.3 * cm

        box_bottom = y - box_h

        c.setFillColor(HexColor("#fff8e1"))     # Fondo amarillo muy suave
        c.setStrokeColor(HexColor("#f0c040"))   # Borde amarillo
        c.setLineWidth(0.8)
        c.roundRect(left, box_bottom, content_width, box_h, 4, fill=1, stroke=1)

        text_y = y - 0.4 * cm
        c.setFillColor(HexColor("#5a4500"))
        c.setFont("Helvetica-Oblique", 8)
        for line in lines:
            c.drawString(left + 0.4 * cm, text_y, line)
            text_y -= 0.45 * cm

        return box_bottom

    def _draw_signature(self, c, y, left, right, employee_data, assignment_data):
        """Dibuja la sección de firma del empleado."""
        # Encabezado
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left, y, "CONFORMIDAD DEL EMPLEADO")
        y -= 0.35 * cm

        c.setFillColor(self.muted_color)
        c.setFont("Helvetica", 8)
        c.drawString(
            left, y,
            "Al firmar este documento, el empleado confirma haber recibido el activo detallado arriba."
        )
        y -= 1.2 * cm

        # Línea de firma — zona que Humand usa para la firma digital
        sig_width = 9 * cm
        c.setStrokeColor(self.primary_color)
        c.setLineWidth(1)
        c.line(left, y, left + sig_width, y)
        y -= 0.4 * cm

        c.setFillColor(self.text_color)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(left, y, "Firma del colaborador")
        y -= 0.5 * cm

        # Datos pre-llenados
        c.setFillColor(self.muted_color)
        c.setFont("Helvetica", 8)
        c.drawString(left + 6 * cm, y, "Fecha de entrega: ")
        c.setFillColor(self.text_color)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(
            left + 9.5 * cm, y,
            self._format_date(assignment_data.get("assigned_date"))
        )

    def _draw_footer(self, c, width, assignment_id):
        """Footer con info del documento."""
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#aaaaaa"))
        footer = (
            f"Documento generado por StoneFixer  ·  "
            f"ID Asignación #{assignment_id}  ·  "
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        c.drawCentredString(width / 2, 0.8 * cm, footer)