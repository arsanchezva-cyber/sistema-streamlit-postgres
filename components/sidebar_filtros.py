import streamlit as st
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, Callable

class SidebarFiltros:
    """Componente reutilizable para filtros en sidebar."""
    
    @staticmethod
    def filtros_fecha(
        key_prefix: str = "filtro",
        fecha_inicio_defecto: Optional[date] = None,
        fecha_fin_defecto: Optional[date] = None,
        mostrar_opciones_rapidas: bool = True
    ) -> Tuple[date, date]:
        """
        Crea filtros de fecha en el sidebar.
        Retorna (fecha_inicio, fecha_fin)
        """
        with st.sidebar:
            st.subheader("📅 Filtros de Fecha")
            
            if mostrar_opciones_rapidas:
                opciones_rapidas = st.selectbox(
                    "Período rápido",
                    ["Personalizado", "Hoy", "Esta semana", "Este mes", "Últimos 30 días"],
                    key=f"{key_prefix}_rapido"
                )
                
                hoy = date.today()
                
                if opciones_rapidas == "Hoy":
                    fecha_inicio = hoy
                    fecha_fin = hoy
                elif opciones_rapidas == "Esta semana":
                    fecha_inicio = hoy - timedelta(days=hoy.weekday())
                    fecha_fin = fecha_inicio + timedelta(days=6)
                elif opciones_rapidas == "Este mes":
                    fecha_inicio = date(hoy.year, hoy.month, 1)
                    if hoy.month == 12:
                        fecha_fin = date(hoy.year + 1, 1, 1) - timedelta(days=1)
                    else:
                        fecha_fin = date(hoy.year, hoy.month + 1, 1) - timedelta(days=1)
                elif opciones_rapidas == "Últimos 30 días":
                    fecha_inicio = hoy - timedelta(days=29)
                    fecha_fin = hoy
                else:
                    fecha_inicio = fecha_inicio_defecto or (hoy - timedelta(days=30))
                    fecha_fin = fecha_fin_defecto or hoy
            else:
                fecha_inicio = fecha_inicio_defecto or (date.today() - timedelta(days=30))
                fecha_fin = fecha_fin_defecto or date.today()
            
            if opciones_rapidas == "Personalizado" or not mostrar_opciones_rapidas:
                col1, col2 = st.columns(2)
                with col1:
                    fecha_inicio = st.date_input(
                        "Desde",
                        value=fecha_inicio,
                        key=f"{key_prefix}_inicio"
                    )
                with col2:
                    fecha_fin = st.date_input(
                        "Hasta",
                        value=fecha_fin,
                        min_value=fecha_inicio,
                        key=f"{key_prefix}_fin"
                    )
            
            return fecha_inicio, fecha_fin
    
    @staticmethod
    def filtros_busqueda(
        key_prefix: str = "busqueda",
        incluir_estado: bool = True,
        incluir_tipo: bool = True
    ) -> dict:
        """
        Crea filtros de búsqueda en el sidebar.
        Retorna un diccionario con los filtros aplicados.
        """
        filtros = {}
        
        with st.sidebar:
            st.subheader("🔍 Filtros de Búsqueda")
            
            # Búsqueda por texto
            texto_busqueda = st.text_input(
                "Buscar",
                placeholder="Nombre, documento, habitación...",
                key=f"{key_prefix}_texto"
            )
            if texto_busqueda:
                filtros['texto'] = texto_busqueda
            
            if incluir_estado:
                estados = st.multiselect(
                    "Estado",
                    ["Confirmada", "Pendiente", "Cancelada", "Completada"],
                    key=f"{key_prefix}_estado"
                )
                if estados:
                    filtros['estados'] = estados
            
            if incluir_tipo:
                from core.database import run_query
                tipos_query = "SELECT id, nombre FROM tipos_habitacion WHERE activo = true"
                tipos = run_query(tipos_query)
                
                if tipos:
                    tipos_seleccionados = st.multiselect(
                        "Tipo de habitación",
                        options=[t['id'] for t in tipos],
                        format_func=lambda x: next((t['nombre'] for t in tipos if t['id'] == x), ""),
                        key=f"{key_prefix}_tipo"
                    )
                    if tipos_seleccionados:
                        filtros['tipos'] = tipos_seleccionados
            
            # Ordenamiento
            st.subheader("📊 Ordenar por")
            col1, col2 = st.columns(2)
            with col1:
                orden_campo = st.selectbox(
                    "Campo",
                    ["Fecha", "Nombre", "Estado"],
                    key=f"{key_prefix}_orden_campo"
                )
            with col2:
                orden_direccion = st.selectbox(
                    "Dirección",
                    ["Descendente", "Ascendente"],
                    key=f"{key_prefix}_orden_dir"
                )
            
            filtros['orden'] = {
                'campo': orden_campo,
                'direccion': orden_direccion
            }
        
        return filtros
    
    @staticmethod
    def filtros_estado_habitacion(
        key_prefix: str = "hab",
        on_change: Optional[Callable] = None
    ) -> str:
        """
        Filtro para estado de habitaciones.
        Retorna el estado seleccionado.
        """
        with st.sidebar:
            st.subheader("🏨 Estado Habitación")
            
            estado = st.radio(
                "Mostrar:",
                ["Todas", "Disponibles", "Ocupadas", "Mantenimiento"],
                key=f"{key_prefix}_estado",
                on_change=on_change
            )
            
            return estado

    @staticmethod
    def aplicar_filtros_a_query(filtros: dict, query_base: str) -> tuple[str, list]:
        """
        Aplica los filtros a una consulta SQL.
        Retorna (query_modificada, parametros)
        """
        query = query_base
        params = []
        
        if filtros.get('texto'):
            query += " AND (h.nombre_completo ILIKE %s OR h.numero_documento ILIKE %s OR hab.numero_habitacion ILIKE %s)"
            texto_param = f"%{filtros['texto']}%"
            params.extend([texto_param, texto_param, texto_param])
        
        if filtros.get('estados'):
            placeholders = ', '.join(['%s'] * len(filtros['estados']))
            query += f" AND e.estado_estancia IN ({placeholders})"
            params.extend(filtros['estados'])
        
        if filtros.get('tipos'):
            placeholders = ', '.join(['%s'] * len(filtros['tipos']))
            query += f" AND h.tipo_habitacion_id IN ({placeholders})"
            params.extend(filtros['tipos'])
        
        # Ordenamiento
        if filtros.get('orden'):
            campo = filtros['orden']['campo']
            direccion = "DESC" if filtros['orden']['direccion'] == "Descendente" else "ASC"
            
            if campo == "Fecha":
                query += " ORDER BY e.fecha_checkin_real " + direccion
            elif campo == "Nombre":
                query += " ORDER BY h.nombre_completo " + direccion
            elif campo == "Estado":
                query += " ORDER BY e.estado_estancia " + direccion
        
        return query, params