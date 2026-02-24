import streamlit as st
from datetime import datetime
from typing import Optional, Dict, List
from core.database import run_query, execute_transaction
from core.queries import *
import uuid

class FacturacionService:
    """Servicio para gestionar facturación y check-out."""
    
    @staticmethod
    def generar_numero_factura() -> str:
        """Genera un número único para la factura."""
        fecha = datetime.now().strftime('%Y%m%d')
        secuencia = str(uuid.uuid4())[:6].upper()
        return f"FAC-{fecha}-{secuencia}"
    
    @staticmethod
    def get_consumos_estancia(estancia_id: str) -> List[Dict]:
        """Obtiene los consumos de una estancia."""
        result = run_query(GET_CONSUMOS_ESTANCIA, (estancia_id,))
        return result if result else []
    
    @staticmethod
    def agregar_consumo(
        estancia_id: str,
        descripcion: str,
        cantidad: int,
        precio_unitario: float
    ) -> Optional[str]:
        """Agrega un consumo a una estancia."""
        
        query = """
        INSERT INTO consumos (estancia_id, descripcion, cantidad, precio_unitario)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """
        
        result = run_query(query, (estancia_id, descripcion, cantidad, precio_unitario))
        return result[0]['id'] if result else None
    
    @staticmethod
    def eliminar_consumo(consumo_id: str) -> bool:
        """Elimina un consumo."""
        query = "DELETE FROM consumos WHERE id = %s"
        result = run_query(query, (consumo_id,))
        return result and result[0].get('rowcount', 0) > 0
    
    @staticmethod
    def calcular_totales_estancia(estancia_id: str) -> Dict:
        """Calcula los totales de una estancia (alojamiento + consumos)."""
        
        # Obtener datos de la estancia
        query_estancia = """
        SELECT 
            e.fecha_checkin_real,
            e.fecha_checkout_esperada,
            e.precio_acordado_por_noche,
            e.huesped_id
        FROM estancias e
        WHERE e.id = %s
        """
        
        estancia = run_query(query_estancia, (estancia_id,))
        
        if not estancia:
            return {
                'noches': 0,
                'total_alojamiento': 0,
                'total_consumos': 0,
                'subtotal': 0,
                'impuestos': 0,
                'total': 0,
                'huesped_id': None
            }
        
        estancia = estancia[0]
        
        # Calcular noches
        checkin = estancia['fecha_checkin_real'].date() if estancia['fecha_checkin_real'] else datetime.now().date()
        checkout = estancia['fecha_checkout_esperada']
        noches = max(1, (checkout - checkin).days)
        
        total_alojamiento = noches * estancia['precio_acordado_por_noche']
        
        # Obtener consumos
        consumos = FacturacionService.get_consumos_estancia(estancia_id)
        total_consumos = sum(c['cantidad'] * c['precio_unitario'] for c in consumos)
        
        subtotal = total_alojamiento + total_consumos
        impuestos = subtotal * 0.16  # 16% IVA
        total = subtotal + impuestos
        
        return {
            'noches': noches,
            'total_alojamiento': total_alojamiento,
            'total_consumos': total_consumos,
            'subtotal': subtotal,
            'impuestos': impuestos,
            'total': total,
            'huesped_id': estancia['huesped_id'],
            'consumos': consumos
        }
    
    @staticmethod
    def generar_factura(data: Dict) -> Optional[str]:
        """
        Genera una factura para una estancia.
        data debe contener: estancia_id, huesped_id, subtotal, impuestos, total, 
        metodo_pago, noches, precio_noche, total_alojamiento, consumos
        """
        
        # Verificar que no exista factura previa
        check_query = "SELECT id FROM facturas WHERE estancia_id = %s"
        existente = run_query(check_query, (data['estancia_id'],))
        
        if existente:
            st.error("Ya existe una factura para esta estancia")
            return None
        
        numero_factura = FacturacionService.generar_numero_factura()
        
        # Preparar transacción
        queries = []
        
        # 1. Insertar factura
        queries.append((
            """
            INSERT INTO facturas (
                numero_factura, estancia_id, huesped_id, 
                subtotal, impuestos, total, metodo_pago, estado_pago
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pagado')
            RETURNING id
            """,
            (
                numero_factura,
                data['estancia_id'],
                data['huesped_id'],
                data['subtotal'],
                data['impuestos'],
                data['total'],
                data['metodo_pago']
            )
        ))
        
        # 2. Insertar detalle de alojamiento (SIN consumo_id)
        queries.append((
            """
            INSERT INTO detalles_factura (
                factura_id, descripcion, cantidad, 
                precio_unitario, importe_total, tipo_detalle
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                None,  # Será reemplazado por el ID de la factura
                f"Alojamiento ({data['noches']} noches)",
                data['noches'],
                data['precio_noche'],
                data['total_alojamiento'],
                'alojamiento'
            )
        ))
        
        # 3. Insertar detalles de consumos (SIN consumo_id)
        for consumo in data.get('consumos', []):
            importe_total = consumo['cantidad'] * consumo['precio_unitario']
            queries.append((
                """
                INSERT INTO detalles_factura (
                    factura_id, descripcion, cantidad, 
                    precio_unitario, importe_total, tipo_detalle
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    None,  # Será reemplazado por el ID de la factura
                    consumo['descripcion'],
                    consumo['cantidad'],
                    consumo['precio_unitario'],
                    importe_total,
                    'consumo'
                )
            ))
        
        # 4. Actualizar estado de la estancia
        queries.append((
            """
            UPDATE estancias 
            SET estado_estancia = 'finalizada', fecha_checkout_real = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (data['estancia_id'],)
        ))
        
        # Ejecutar transacción
        success, results = execute_transaction(queries)
        
        if success and results and len(results) > 0:
            # El resultado de la factura está en results[0]
            if results[0] and len(results[0]) > 0:
                factura_id = results[0][0]['id']
                st.success(f"✅ Factura generada con ID: {factura_id}")
                return factura_id
        
        st.error("Error al generar la factura")
        return None
    
    @staticmethod
    def obtener_factura(estancia_id: str) -> Optional[Dict]:
        """Obtiene la factura de una estancia."""
        result = run_query(GET_FACTURA_BY_ESTANCIA, (estancia_id,))
        return result[0] if result else None
    
    @staticmethod
    def anular_factura(factura_id: str) -> bool:
        """Anula una factura (cambia estado a anulado)."""
        query = """
        UPDATE facturas
        SET estado_pago = 'anulado'
        WHERE id = %s AND estado_pago = 'pagado'
        RETURNING id
        """
        
        result = run_query(query, (factura_id,))
        return result and len(result) > 0


# =============================================
# FUNCIONES WRAPPER PARA COMPATIBILIDAD
# =============================================

def generar_factura(data: Dict) -> Optional[str]:
    """Wrapper para compatibilidad con importaciones antiguas."""
    return FacturacionService.generar_factura(data)

def get_consumos_estancia(estancia_id: str) -> List[Dict]:
    """Wrapper para compatibilidad con importaciones antiguas."""
    return FacturacionService.get_consumos_estancia(estancia_id)

def agregar_consumo(estancia_id: str, descripcion: str, cantidad: int, precio_unitario: float) -> Optional[str]:
    """Wrapper para compatibilidad."""
    return FacturacionService.agregar_consumo(estancia_id, descripcion, cantidad, precio_unitario)

def calcular_totales_estancia(estancia_id: str) -> Dict:
    """Wrapper para compatibilidad."""
    return FacturacionService.calcular_totales_estancia(estancia_id)

def eliminar_consumo(consumo_id: str) -> bool:
    """Wrapper para compatibilidad."""
    return FacturacionService.eliminar_consumo(consumo_id)

def obtener_factura(estancia_id: str) -> Optional[Dict]:
    """Wrapper para compatibilidad."""
    return FacturacionService.obtener_factura(estancia_id)

def anular_factura(factura_id: str) -> bool:
    """Wrapper para compatibilidad."""
    return FacturacionService.anular_factura(factura_id)