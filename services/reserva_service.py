import streamlit as st
import uuid
from datetime import date
from typing import Optional, List, Dict
from core.database import execute_transaction, run_query
from models import Reserva, Huesped
from core.queries import *

class ReservaService:
    """Servicio para gestionar reservas."""
    
    @staticmethod
    def generar_codigo_reserva() -> str:
        """
        Genera un código único para la reserva.
        MÁXIMO 20 CARACTERES para cumplir con VARCHAR(20) de la BD.
        Formato: RES-YYMMDD-XXXXXX (ej: RES-230223-A1B2C3) = 17 caracteres
        """
        fecha = date.today().strftime('%y%m%d')
        unique_id = str(uuid.uuid4())[:6].upper()
        return f"RES-{fecha}-{unique_id}"
    
    @staticmethod
    def verificar_disponibilidad(
        fecha_checkin: date,
        fecha_checkout: date,
        tipo_habitacion_id: int,
        num_habitaciones: int = 1
    ) -> bool:
        """Verifica si hay disponibilidad para una reserva."""
        query_reservas = """
        SELECT COUNT(*) as conflictos
        FROM reservas
        WHERE tipo_habitacion_solicitada_id = %s
        AND estado_reserva = 'confirmada'
        AND fecha_checkin < %s
        AND fecha_checkout > %s
        """
        result_reservas = run_query(query_reservas, (tipo_habitacion_id, fecha_checkout, fecha_checkin))
        reservas_conflictos = result_reservas[0]['conflictos'] if result_reservas else 0
        query_estancias = """
        SELECT COUNT(DISTINCT e.habitacion_id) as conflictos
        FROM estancias e
        JOIN habitaciones h ON e.habitacion_id = h.id
        WHERE h.tipo_habitacion_id = %s
        AND e.estado_estancia = 'activa'
        AND e.fecha_checkin_esperada < %s
        AND e.fecha_checkout_esperada > %s
        """
        result_estancias = run_query(query_estancias, (tipo_habitacion_id, fecha_checkout, fecha_checkin))
        estancias_conflictos = result_estancias[0]['conflictos'] if result_estancias else 0
        query_total = """
        SELECT COUNT(*) as total
        FROM habitaciones
        WHERE tipo_habitacion_id = %s AND activa = true
        """
        result_total = run_query(query_total, (tipo_habitacion_id,))
        total_habitaciones = result_total[0]['total'] if result_total else 0
        ocupadas = reservas_conflictos + estancias_conflictos
        disponibles = total_habitaciones - ocupadas
        st.write(f"🔍 Total: {total_habitaciones}, Ocupadas: {ocupadas}, Disponibles: {disponibles}")
        return disponibles >= num_habitaciones
    
    @staticmethod
    def ver_disponibilidad_completa(fecha_checkin: date, fecha_checkout: date):
        """
        Muestra un diagnóstico completo de disponibilidad de habitaciones.
        """
        st.subheader("🔍 DIAGNÓSTICO DE DISPONIBILIDAD")
        st.write(f"**Período consultado:** {fecha_checkin} al {fecha_checkout}")
        
        # 1. Ver todas las habitaciones con su estado actual
        query_todas = """
        SELECT 
            h.id,
            h.numero_habitacion,
            h.piso,
            t.nombre as tipo,
            h.estado_actual,
            CASE 
                WHEN e.id IS NOT NULL THEN 
                    'OCUPADA: ' || to_char(e.fecha_checkin_esperada, 'DD/MM/YYYY') || ' al ' || to_char(e.fecha_checkout_esperada, 'DD/MM/YYYY')
                ELSE 'Disponible'
            END as estado_real,
            e.fecha_checkin_esperada,
            e.fecha_checkout_esperada
        FROM habitaciones h
        JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
        LEFT JOIN estancias e ON h.id = e.habitacion_id AND e.estado_estancia = 'activa'
        WHERE h.activa = true
        ORDER BY h.numero_habitacion
        """
        
        todas = run_query(query_todas)
        
        if todas:
            st.write("### 📋 ESTADO ACTUAL DE TODAS LAS HABITACIONES")
            for hab in todas:
                if hab['estado_actual'] == 'ocupada' or hab['estado_real'] != 'Disponible':
                    st.error(f"🏨 Hab {hab['numero_habitacion']} ({hab['tipo']}): {hab['estado_real']}")
                else:
                    st.success(f"🏨 Hab {hab['numero_habitacion']} ({hab['tipo']}): {hab['estado_real']}")
        
        # 2. Ver SOLO las disponibles para las fechas solicitadas
        query_disponibles = """
        SELECT 
            h.id,
            h.numero_habitacion,
            h.piso,
            t.nombre as tipo,
            t.precio_base_por_noche
        FROM habitaciones h
        JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
        WHERE h.activa = true
        AND h.estado_actual NOT IN ('mantenimiento')
        AND h.id NOT IN (
            SELECT e.habitacion_id
            FROM estancias e
            WHERE e.estado_estancia = 'activa'
            AND e.fecha_checkin_esperada < %s
            AND e.fecha_checkout_esperada > %s
        )
        ORDER BY h.numero_habitacion
        """
        
        disponibles = run_query(query_disponibles, (fecha_checkout, fecha_checkin))
        
        if disponibles:
            st.write("### ✅ HABITACIONES DISPONIBLES PARA TUS FECHAS")
            for hab in disponibles:
                st.success(f"🏨 Hab {hab['numero_habitacion']} - Piso {hab['piso']} - {hab['tipo']} - ${hab['precio_base_por_noche']}/noche")
            st.write(f"**Total disponibles:** {len(disponibles)} habitaciones")
        else:
            st.error("❌ NO HAY HABITACIONES DISPONIBLES para estas fechas")
        
        # 3. Ver conflictos específicos
        query_conflictos = """
        SELECT 
            h.numero_habitacion,
            t.nombre as tipo,
            e.fecha_checkin_esperada,
            e.fecha_checkout_esperada,
            h2.nombre_completo as huesped
        FROM estancias e
        JOIN habitaciones h ON e.habitacion_id = h.id
        JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
        JOIN huespedes h2 ON e.huesped_id = h2.id
        WHERE e.estado_estancia = 'activa'
        AND e.fecha_checkin_esperada < %s
        AND e.fecha_checkout_esperada > %s
        ORDER BY e.fecha_checkin_esperada
        """
        
        conflictos = run_query(query_conflictos, (fecha_checkout, fecha_checkin))
        
        if conflictos:
            st.write("### ⚠️ CONFLICTOS - Habitaciones ocupadas en tu período")
            for conf in conflictos:
                st.warning(f"🏨 Hab {conf['numero_habitacion']} ({conf['tipo']}): Ocupada del {conf['fecha_checkin_esperada']} al {conf['fecha_checkout_esperada']} por {conf['huesped']}")
    
    @staticmethod
    def crear_reserva(reserva: Reserva, huesped: Huesped) -> Optional[str]:
        """
        Crea una nueva reserva en UNA SOLA TRANSACCIÓN.
        Si el huésped ya existe, usa su ID existente.
        Retorna el ID de la reserva o None si hay error.
        """
        
        # 1. Validar datos básicos
        if not huesped.nombre_completo or not huesped.numero_documento:
            st.error("❌ Faltan datos del huésped")
            return None
        
        if not reserva.tipo_habitacion_solicitada_id:
            st.error("❌ Falta tipo de habitación")
            return None
        
        # 2. Verificar disponibilidad
        disponible = ReservaService.verificar_disponibilidad(
            reserva.fecha_checkin,
            reserva.fecha_checkout,
            reserva.tipo_habitacion_solicitada_id
        )
        
        if not disponible:
            st.error("❌ No hay disponibilidad para las fechas seleccionadas")
            ReservaService.ver_disponibilidad_completa(
                reserva.fecha_checkin,
                reserva.fecha_checkout
            )
            return None
        
        # 3. Verificar si el huésped ya existe
        query_huesped_existente = """
        SELECT id FROM huespedes 
        WHERE tipo_documento = %s AND numero_documento = %s
        """
        
        huesped_existente = run_query(
            query_huesped_existente, 
            (huesped.tipo_documento, huesped.numero_documento)
        )
        
        # 4. Generar código de reserva
        codigo = ReservaService.generar_codigo_reserva()
        st.write(f"Código generado: {codigo} (longitud: {len(codigo)})")
        
        # 5. Preparar transacción
        queries = []
        
        if huesped_existente and len(huesped_existente) > 0:
            # El huésped YA EXISTE - usar su ID
            huesped_id = huesped_existente[0]['id']
            st.info(f"✅ Huésped existente encontrado con ID: {huesped_id}")
            
            queries.append((
                """
                INSERT INTO reservas (
                    codigo_reserva,
                    huesped_id,
                    tipo_habitacion_solicitada_id,
                    fecha_checkin,
                    fecha_checkout,
                    numero_adultos,
                    numero_ninos,
                    estado_reserva,
                    observaciones
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    codigo,
                    huesped_id,
                    reserva.tipo_habitacion_solicitada_id,
                    reserva.fecha_checkin,
                    reserva.fecha_checkout,
                    reserva.numero_adultos,
                    reserva.numero_ninos,
                    'confirmada',
                    reserva.observaciones
                )
            ))
        else:
            # El huésped NO existe - insertar huésped y reserva
            st.info("🆕 Nuevo huésped - se insertará en la base de datos")
            
            queries.append((
                """
                INSERT INTO huespedes (
                    nombre_completo, 
                    tipo_documento, 
                    numero_documento, 
                    email, 
                    telefono
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    huesped.nombre_completo,
                    huesped.tipo_documento,
                    huesped.numero_documento,
                    huesped.email,
                    huesped.telefono
                )
            ))
            
            queries.append((
                """
                INSERT INTO reservas (
                    codigo_reserva,
                    huesped_id,
                    tipo_habitacion_solicitada_id,
                    fecha_checkin,
                    fecha_checkout,
                    numero_adultos,
                    numero_ninos,
                    estado_reserva,
                    observaciones
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    codigo,
                    None,
                    reserva.tipo_habitacion_solicitada_id,
                    reserva.fecha_checkin,
                    reserva.fecha_checkout,
                    reserva.numero_adultos,
                    reserva.numero_ninos,
                    'confirmada',
                    reserva.observaciones
                )
            ))
        
        # 6. Ejecutar transacción
        st.info("🔄 Ejecutando transacción...")
        success, results = execute_transaction(queries)
        
        if success:
            st.success("✅ Transacción completada")
            reserva_result = results[-1] if results else None
            if reserva_result and len(reserva_result) > 0:
                reserva_id = reserva_result[0]['id']
                st.success(f"✅ Reserva creada con ID: {reserva_id}")
                return reserva_id
            else:
                st.error("❌ No se pudo obtener el ID de la reserva")
        else:
            st.error("❌ La transacción falló")
        
        return None
    
    @staticmethod
    def buscar_reservas(
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        estado: Optional[str] = None,
        huesped_nombre: Optional[str] = None
    ) -> List[Dict]:
        """Busca reservas según filtros."""
        
        query = """
        SELECT 
            r.id, 
            r.codigo_reserva,
            h.nombre_completo as huesped_nombre,
            h.numero_documento,
            t.nombre as tipo_habitacion,
            r.fecha_checkin,
            r.fecha_checkout,
            r.numero_adultos + r.numero_ninos as personas,
            r.estado_reserva,
            (r.fecha_checkout - r.fecha_checkin) as noches
        FROM reservas r
        JOIN huespedes h ON r.huesped_id = h.id
        JOIN tipos_habitacion t ON r.tipo_habitacion_solicitada_id = t.id
        WHERE 1=1
        """
        
        params = []
        
        if fecha_desde:
            query += " AND r.fecha_checkin >= %s"
            params.append(fecha_desde)
        
        if fecha_hasta:
            query += " AND r.fecha_checkin <= %s"
            params.append(fecha_hasta)
        
        if estado:
            query += " AND r.estado_reserva = %s"
            params.append(estado)
        
        if huesped_nombre:
            query += " AND h.nombre_completo ILIKE %s"
            params.append(f"%{huesped_nombre}%")
        
        query += " ORDER BY r.fecha_checkin DESC"
        
        result = run_query(query, tuple(params) if params else None)
        return result if result else []
    
    @staticmethod
    def cancelar_reserva(reserva_id: str) -> bool:
        """Cancela una reserva."""
        query = """
        UPDATE reservas
        SET estado_reserva = 'cancelada'
        WHERE id = %s AND estado_reserva = 'confirmada'
        RETURNING id
        """
        
        result = run_query(query, (reserva_id,))
        return result and len(result) > 0
    
    @staticmethod
    def obtener_reserva(codigo: str) -> Optional[Dict]:
        """Obtiene una reserva por su código."""
        query = """
        SELECT 
            r.*,
            h.nombre_completo, 
            h.tipo_documento, 
            h.numero_documento,
            h.email, 
            h.telefono,
            t.nombre as tipo_habitacion_nombre,
            t.precio_base_por_noche
        FROM reservas r
        JOIN huespedes h ON r.huesped_id = h.id
        JOIN tipos_habitacion t ON r.tipo_habitacion_solicitada_id = t.id
        WHERE r.codigo_reserva = %s
        """
        
        result = run_query(query, (codigo,))
        return result[0] if result else None