import streamlit as st
from datetime import datetime, date
from typing import Optional, Dict, List
from core.database import run_query, execute_transaction
from models import Reserva, Huesped, Habitacion

class CheckInService:
    """Servicio para gestionar el proceso de check-in."""
    
    @staticmethod
    def buscar_estancias_activas(filtro: str = None, valor: str = None) -> List[Dict]:
        """Busca estancias activas según filtro."""
        
        query = """
        SELECT 
            e.id as estancia_id,
            h.nombre_completo,
            h.tipo_documento,
            h.numero_documento,
            hab.numero_habitacion,
            t.nombre as tipo_habitacion,
            e.fecha_checkin_real,
            e.fecha_checkout_esperada,
            e.numero_adultos,
            e.numero_ninos
        FROM estancias e
        JOIN huespedes h ON e.huesped_id = h.id
        JOIN habitaciones hab ON e.habitacion_id = hab.id
        JOIN tipos_habitacion t ON hab.tipo_habitacion_id = t.id
        WHERE e.estado_estancia = 'activa'
        """
        
        params = []
        
        if filtro and valor:
            if filtro == "Habitación":
                query += " AND hab.numero_habitacion = %s"
                params.append(valor)
            elif filtro == "Documento":
                query += " AND h.numero_documento = %s"
                params.append(valor)
            elif filtro == "Nombre":
                query += " AND h.nombre_completo ILIKE %s"
                params.append(f"%{valor}%")
        
        query += " ORDER BY h.nombre_completo"
        
        result = run_query(query, tuple(params) if params else None)
        return result if result else []
    
    @staticmethod
    def obtener_habitaciones_disponibles(
        tipo_habitacion_id: int,
        fecha_checkin: date,
        fecha_checkout: date
    ) -> List[Dict]:
        """Obtiene habitaciones disponibles para un tipo específico."""
        
        query = """
        SELECT 
            h.id,
            h.numero_habitacion,
            h.piso,
            t.nombre as tipo,
            t.precio_base_por_noche
        FROM habitaciones h
        JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
        WHERE h.tipo_habitacion_id = %s
        AND h.activa = true
        AND h.estado_actual NOT IN ('ocupada', 'mantenimiento')
        AND h.id NOT IN (
            SELECT e.habitacion_id
            FROM estancias e
            WHERE e.estado_estancia = 'activa'
            AND e.fecha_checkin_esperada < %s
            AND e.fecha_checkout_esperada > %s
        )
        ORDER BY h.numero_habitacion
        """
        
        result = run_query(query, (tipo_habitacion_id, fecha_checkout, fecha_checkin))
        return result if result else []
    
    @staticmethod
    def realizar_checkin(
        huesped_id: str,
        habitacion_id: int,
        fecha_checkin: date,
        fecha_checkout: date,
        adultos: int,
        ninos: int,
        precio_noche: float,
        reserva_id: Optional[str] = None,
        observaciones: str = ""
    ) -> Optional[str]:
        """Realiza el check-in de un huésped."""
        
        # Verificar que la habitación sigue disponible
        check_disponibilidad = """
        SELECT COUNT(*) as ocupada
        FROM estancias
        WHERE habitacion_id = %s
        AND estado_estancia = 'activa'
        AND fecha_checkin_esperada < %s
        AND fecha_checkout_esperada > %s
        """
        
        result = run_query(check_disponibilidad, (habitacion_id, fecha_checkout, fecha_checkin))
        
        if result and result[0]['ocupada'] > 0:
            st.error("La habitación ya no está disponible")
            return None
        
        # Crear estancia
        estancia_query = """
        INSERT INTO estancias (
            reserva_id, huesped_id, habitacion_id,
            fecha_checkin_real, fecha_checkin_esperada, fecha_checkout_esperada,
            numero_adultos, numero_ninos, precio_acordado_por_noche,
            estado_estancia, observaciones
        ) VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, 'activa', %s)
        RETURNING id
        """
        
        result = run_query(estancia_query, (
            reserva_id,
            huesped_id,
            habitacion_id,
            fecha_checkin,
            fecha_checkout,
            adultos,
            ninos,
            precio_noche,
            observaciones
        ))
        
        return result[0]['id'] if result else None
    
    @staticmethod
    def realizar_checkin_walkin(data: dict) -> Optional[str]:
        """
        Realiza check-in para walk-in (crea huésped y estancia en UNA SOLA TRANSACCIÓN)
        data debe contener: nombre, tipo_documento, numero_documento, email, telefono,
        fecha_nacimiento, habitacion_id, fecha_checkin, fecha_checkout,
        adultos, ninos, precio_noche, observaciones
        """
        
        queries = []
        
        # 1. Insertar huésped
        queries.append((
            """
            INSERT INTO huespedes (
                nombre_completo, tipo_documento, numero_documento,
                email, telefono, fecha_nacimiento
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                data['nombre'],
                data['tipo_documento'],
                data['numero_documento'],
                data.get('email'),
                data['telefono'],
                data.get('fecha_nacimiento')
            )
        ))
        
        # 2. Crear estancia (usando el ID del huésped de la consulta anterior)
        queries.append((
            """
            INSERT INTO estancias (
                reserva_id, huesped_id, habitacion_id,
                fecha_checkin_real, fecha_checkin_esperada, fecha_checkout_esperada,
                numero_adultos, numero_ninos, precio_acordado_por_noche,
                estado_estancia, observaciones
            ) VALUES (
                %s, %s, %s,
                CURRENT_TIMESTAMP, %s, %s,
                %s, %s, %s,
                'activa', %s
            )
            RETURNING id
            """,
            (
                None,  # reserva_id (NULL para walk-in)
                None,  # Este None será reemplazado por el ID del huésped
                data['habitacion_id'],
                data['fecha_checkin'],
                data['fecha_checkout'],
                data['adultos'],
                data['ninos'],
                data['precio_noche'],
                data.get('observaciones', '')
            )
        ))
        
        # Ejecutar transacción
        success, results = execute_transaction(queries)
        
        if success and len(results) >= 2:
            # results[0] es el resultado del INSERT de huésped
            # results[1] es el resultado del INSERT de estancia
            if results[1] and len(results[1]) > 0:
                estancia_id = results[1][0]['id']
                return estancia_id
        
        return None
    
    @staticmethod
    def obtener_estancia(estancia_id: str) -> Optional[Dict]:
        """Obtiene los detalles de una estancia."""
        
        query = """
        SELECT 
            e.id,
            e.reserva_id,
            e.huesped_id,
            e.habitacion_id,
            e.fecha_checkin_real,
            e.fecha_checkin_esperada,
            e.fecha_checkout_esperada,
            e.numero_adultos,
            e.numero_ninos,
            e.precio_acordado_por_noche,
            e.estado_estancia,
            e.observaciones,
            h.nombre_completo,
            h.tipo_documento,
            h.numero_documento,
            h.email,
            h.telefono,
            hab.numero_habitacion,
            t.nombre as tipo_habitacion
        FROM estancias e
        JOIN huespedes h ON e.huesped_id = h.id
        JOIN habitaciones hab ON e.habitacion_id = hab.id
        JOIN tipos_habitacion t ON hab.tipo_habitacion_id = t.id
        WHERE e.id = %s
        """
        
        result = run_query(query, (estancia_id,))
        return result[0] if result else None