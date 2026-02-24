import streamlit as st
from fpdf import FPDF
from datetime import datetime
import pandas as pd
import io
from typing import Dict, List, Optional
from core.database import run_query
from utils.helpers import formatear_moneda, formatear_fecha

class PDFReport(FPDF):
    """Clase base para reportes PDF."""
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Sistema de Gestión Hotelera', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 6, title, 0, 1, 'L', 1)
        self.ln(4)
    
    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 5, body)
        self.ln()
    
    def add_table(self, headers, data, widths=None):
        """Agrega una tabla al PDF."""
        if not widths:
            # Calcular anchos proporcionales
            page_width = self.w - 2 * self.l_margin
            widths = [page_width / len(headers)] * len(headers)
        
        # Cabeceras
        self.set_font('Arial', 'B', 10)
        self.set_fill_color(200, 220, 255)
        for i, header in enumerate(headers):
            self.cell(widths[i], 7, header, 1, 0, 'C', 1)
        self.ln()
        
        # Datos
        self.set_font('Arial', '', 9)
        for row in data:
            for i, cell in enumerate(row):
                self.cell(widths[i], 6, str(cell), 1, 0, 'L')
            self.ln()

class ReportService:
    """Servicio para generar reportes en PDF."""
    
    @staticmethod
    def generar_factura_pdf(estancia_id: str) -> Optional[bytes]:
        """Genera un PDF con la factura detallada de una estancia."""
        
        # Obtener datos de la factura
        query_factura = """
        SELECT 
            f.numero_factura,
            f.fecha_emision,
            f.subtotal,
            f.impuestos,
            f.total,
            f.metodo_pago,
            h.nombre_completo,
            h.tipo_documento,
            h.numero_documento,
            h.email,
            hab.numero_habitacion,
            t.nombre as tipo_habitacion,
            e.fecha_checkin_real,
            e.fecha_checkout_real,
            e.fecha_checkin_esperada,
            e.fecha_checkout_esperada
        FROM facturas f
        JOIN estancias e ON f.estancia_id = e.id
        JOIN huespedes h ON f.huesped_id = h.id
        JOIN habitaciones hab ON e.habitacion_id = hab.id
        JOIN tipos_habitacion t ON hab.tipo_habitacion_id = t.id
        WHERE f.estancia_id = %s
        """
        
        query_detalles = """
        SELECT 
            descripcion,
            cantidad,
            precio_unitario,
            importe_total,
            tipo_detalle
        FROM detalles_factura
        WHERE factura_id = (SELECT id FROM facturas WHERE estancia_id = %s)
        ORDER BY 
            CASE tipo_detalle 
                WHEN 'alojamiento' THEN 1 
                WHEN 'consumo' THEN 2 
            END
        """
        
        factura_data = run_query(query_factura, (estancia_id,))
        detalles_data = run_query(query_detalles, (estancia_id,))
        
        if not factura_data:
            return None
        
        f = factura_data[0]
        
        # Crear PDF
        pdf = PDFReport()
        pdf.add_page()
        
        # Título
        pdf.set_font('Arial', 'B', 20)
        pdf.cell(0, 10, 'FACTURA', 0, 1, 'C')
        pdf.ln(10)
        
        # Información de la factura
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 6, f"Factura N°: {f['numero_factura']}", 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, f"Fecha de Emisión: {formatear_fecha(f['fecha_emision'])}", 0, 1)
        pdf.ln(5)
        
        # Información del huésped
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 6, 'Datos del Huésped:', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, f"Nombre: {f['nombre_completo']}", 0, 1)
        pdf.cell(0, 5, f"Documento: {f['tipo_documento']} {f['numero_documento']}", 0, 1)
        pdf.cell(0, 5, f"Email: {f['email'] or 'No especificado'}", 0, 1)
        pdf.ln(5)
        
        # Información de la estancia
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 6, 'Detalles de la Estancia:', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, f"Habitación: {f['numero_habitacion']} - {f['tipo_habitacion']}", 0, 1)
        pdf.cell(0, 5, f"Check-in: {formatear_fecha(f['fecha_checkin_real'])}", 0, 1)
        pdf.cell(0, 5, f"Check-out: {formatear_fecha(f['fecha_checkout_real'] or f['fecha_checkout_esperada'])}", 0, 1)
        pdf.ln(10)
        
        # Tabla de detalles
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(80, 7, 'Descripción', 1, 0, 'C', 1)
        pdf.cell(20, 7, 'Cant.', 1, 0, 'C', 1)
        pdf.cell(40, 7, 'P. Unitario', 1, 0, 'C', 1)
        pdf.cell(40, 7, 'Importe', 1, 1, 'C', 1)
        
        pdf.set_font('Arial', '', 9)
        for detalle in detalles_data:
            # Truncar descripción si es muy larga
            desc = detalle['descripcion'][:40] + '...' if len(detalle['descripcion']) > 40 else detalle['descripcion']
            
            pdf.cell(80, 6, desc, 1)
            pdf.cell(20, 6, str(detalle['cantidad']), 1, 0, 'C')
            pdf.cell(40, 6, formatear_moneda(detalle['precio_unitario']), 1, 0, 'R')
            pdf.cell(40, 6, formatear_moneda(detalle['importe_total']), 1, 1, 'R')
        
        # Totales
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(140, 7, 'Subtotal:', 0, 0, 'R')
        pdf.cell(40, 7, formatear_moneda(f['subtotal']), 0, 1, 'R')
        pdf.cell(140, 7, 'Impuestos (16%):', 0, 0, 'R')
        pdf.cell(40, 7, formatear_moneda(f['impuestos']), 0, 1, 'R')
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(140, 8, 'TOTAL:', 0, 0, 'R')
        pdf.cell(40, 8, formatear_moneda(f['total']), 0, 1, 'R')
        pdf.ln(10)
        
        # Método de pago
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"Método de Pago: {f['metodo_pago'] or 'No especificado'}", 0, 1)
        
        # Usar BytesIO en lugar de archivo temporal
        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        return pdf_bytes.getvalue()
    
    @staticmethod
    def generar_reporte_ocupacion(
        fecha_inicio,
        fecha_fin,
        datos: List[Dict],
        incluir_detalle: bool = True
    ) -> Optional[bytes]:
        """Genera un reporte de ocupación en PDF."""
        
        pdf = PDFReport()
        pdf.add_page()
        
        # Título
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Reporte de Ocupación', 0, 1, 'C')
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, f"Período: {formatear_fecha(fecha_inicio)} - {formatear_fecha(fecha_fin)}", 0, 1, 'C')
        pdf.ln(10)
        
        if not datos:
            pdf.cell(0, 10, 'No hay datos para el período seleccionado', 0, 1, 'C')
        else:
            # Resumen
            df = pd.DataFrame(datos)
            total_registros = len(df)
            ocupadas_actual = len(df[df['estado'] == 'Ocupada']) if 'estado' in df.columns else 0
            
            pdf.chapter_title('Resumen')
            pdf.cell(0, 6, f"Total registros: {total_registros}", 0, 1)
            pdf.cell(0, 6, f"Estancias activas: {ocupadas_actual}", 0, 1)
            if 'personas' in df.columns:
                total_personas = df['personas'].sum()
                pdf.cell(0, 6, f"Total huéspedes: {total_personas}", 0, 1)
            pdf.ln(5)
            
            if incluir_detalle:
                pdf.chapter_title('Detalle por Día')
                
                # Preparar datos para tabla
                headers = ['Fecha', 'Habitación', 'Tipo', 'Estado', 'Personas']
                table_data = []
                
                for row in datos[:50]:
                    table_data.append([
                        formatear_fecha(row.get('fecha', '')),
                        row.get('numero_habitacion', ''),
                        row.get('tipo_habitacion', ''),
                        row.get('estado', ''),
                        row.get('personas', '')
                    ])
                
                pdf.add_table(headers, table_data)
                
                if len(datos) > 50:
                    pdf.cell(0, 6, f"... y {len(datos) - 50} registros más", 0, 1)
        
        # Usar BytesIO
        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        return pdf_bytes.getvalue()
    
    @staticmethod
    def generar_reporte_ingresos(
        fecha_inicio,
        fecha_fin,
        datos: List[Dict],
        incluir_detalle: bool = True
    ) -> Optional[bytes]:
        """Genera un reporte de ingresos en PDF."""
        
        pdf = PDFReport()
        pdf.add_page()
        
        # Título
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Reporte de Ingresos', 0, 1, 'C')
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, f"Período: {formatear_fecha(fecha_inicio)} - {formatear_fecha(fecha_fin)}", 0, 1, 'C')
        pdf.ln(10)
        
        if not datos:
            pdf.cell(0, 10, 'No hay datos para el período seleccionado', 0, 1, 'C')
        else:
            # Calcular totales
            df = pd.DataFrame(datos)
            total_ingresos = df['total'].sum() if 'total' in df.columns else 0
            total_facturas = len(df)
            ticket_promedio = total_ingresos / total_facturas if total_facturas > 0 else 0
            
            pdf.chapter_title('Resumen')
            pdf.cell(0, 6, f"Total facturas: {total_facturas}", 0, 1)
            pdf.cell(0, 6, f"Ingresos totales: {formatear_moneda(total_ingresos)}", 0, 1)
            pdf.cell(0, 6, f"Ticket promedio: {formatear_moneda(ticket_promedio)}", 0, 1)
            pdf.ln(5)
            
            if incluir_detalle:
                pdf.chapter_title('Detalle de Facturas')
                
                headers = ['Fecha', 'Factura N°', 'Huésped', 'Habitación', 'Total']
                table_data = []
                
                for row in datos[:50]:
                    table_data.append([
                        formatear_fecha(row.get('fecha', '')),
                        row.get('numero_factura', ''),
                        row.get('huesped', '')[:20] + '...' if len(row.get('huesped', '')) > 20 else row.get('huesped', ''),
                        row.get('numero_habitacion', ''),
                        formatear_moneda(row.get('total', 0))
                    ])
                
                pdf.add_table(headers, table_data, widths=[30, 40, 50, 30, 30])
        
        # Usar BytesIO
        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        return pdf_bytes.getvalue()
    
    @staticmethod
    def generar_reporte_estadistico(
        stats: Dict,
        tipos_df: pd.DataFrame,
        fecha_inicio,
        fecha_fin
    ) -> Optional[bytes]:
        """Genera un reporte estadístico en PDF."""
        
        pdf = PDFReport()
        pdf.add_page()
        
        # Título
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Reporte Estadístico General', 0, 1, 'C')
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, f"Período: {formatear_fecha(fecha_inicio)} - {formatear_fecha(fecha_fin)}", 0, 1, 'C')
        pdf.ln(10)
        
        # Métricas principales
        pdf.chapter_title('Métricas Generales')
        
        metrics = [
            ('Total Estancias', stats.get('total_estancias', 0)),
            ('Huéspedes Únicos', stats.get('huespedes_unicos', 0)),
            ('Noches Totales', stats.get('noches_totales', 0)),
            ('Promedio Noches', f"{stats.get('promedio_noches', 0):.1f}"),
            ('Ingresos Totales', formatear_moneda(stats.get('ingresos_totales', 0))),
            ('Ticket Promedio', formatear_moneda(stats.get('ticket_promedio', 0))),
            ('Con Reserva', stats.get('estancias_con_reserva', 0)),
            ('Walk-Ins', stats.get('walk_ins', 0))
        ]
        
        for i, (label, value) in enumerate(metrics):
            if i % 2 == 0:
                pdf.cell(95, 8, f"{label}: {value}", 0, 0)
            else:
                pdf.cell(95, 8, f"{label}: {value}", 0, 1)
        pdf.ln(5)
        
        # Distribución por tipo de habitación
        if not tipos_df.empty:
            pdf.chapter_title('Distribución por Tipo de Habitación')
            
            headers = ['Tipo', 'N° Estancias', 'Noches', 'Precio Prom.']
            table_data = []
            
            for _, row in tipos_df.iterrows():
                table_data.append([
                    row.get('tipo_habitacion', ''),
                    row.get('num_estancias', 0),
                    row.get('noches', 0),
                    formatear_moneda(row.get('precio_promedio', 0))
                ])
            
            pdf.add_table(headers, table_data, widths=[50, 40, 40, 50])
        
        # Usar BytesIO
        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        return pdf_bytes.getvalue()


# =============================================
# FUNCIONES WRAPPER PARA COMPATIBILIDAD
# =============================================

def generar_factura_pdf(estancia_id: str) -> Optional[bytes]:
    """Wrapper para compatibilidad."""
    return ReportService.generar_factura_pdf(estancia_id)

def generar_reporte_ocupacion(fecha_inicio, fecha_fin, datos, incluir_detalle=True):
    """Wrapper para compatibilidad con importaciones."""
    return ReportService.generar_reporte_ocupacion(fecha_inicio, fecha_fin, datos, incluir_detalle)

def generar_reporte_ingresos(fecha_inicio, fecha_fin, datos, incluir_detalle=True):
    """Wrapper para compatibilidad con importaciones."""
    return ReportService.generar_reporte_ingresos(fecha_inicio, fecha_fin, datos, incluir_detalle)

def generar_reporte_estadistico(stats, tipos_df, fecha_inicio, fecha_fin):
    """Wrapper para compatibilidad con importaciones."""
    return ReportService.generar_reporte_estadistico(stats, tipos_df, fecha_inicio, fecha_fin)

def get_consumos_estancia(estancia_id: str) -> List[Dict]:
    """Obtiene consumos de una estancia."""
    return run_query(
        "SELECT * FROM consumos WHERE estancia_id = %s ORDER BY fecha_consumo DESC",
        (estancia_id,)
    ) or []