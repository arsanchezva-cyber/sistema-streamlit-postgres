import streamlit as st
from typing import Optional, Dict, Callable

class TarjetaHabitacion:
    """Componente para mostrar información de habitación en formato tarjeta."""
    
    @staticmethod
    def render(
        numero: str,
        tipo: str,
        estado: str,
        piso: int = 1,
        precio: Optional[float] = None,
        capacidad: Optional[int] = None,
        on_click: Optional[Callable] = None,
        button_text: str = "Seleccionar",
        key: Optional[str] = None
    ):
        """
        Renderiza una tarjeta de habitación.
        """
        # Definir colores según estado
        colores_estado = {
            'disponible': '#28a745',  # Verde
            'ocupada': '#dc3545',      # Rojo
            'mantenimiento': '#ffc107', # Amarillo
            'reservada': '#17a2b8',     # Azul
            'limpieza': '#6c757d'       # Gris
        }
        
        color = colores_estado.get(estado.lower(), '#6c757d')
        
        # Crear contenedor con borde
        with st.container():
            st.markdown(f"""
            <div style="
                border: 2px solid {color};
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0;
                background-color: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <h3 style="margin: 0; color: {color};">Habitación {numero}</h3>
                <p style="margin: 5px 0; font-size: 14px;">
                    <strong>Tipo:</strong> {tipo}<br>
                    <strong>Piso:</strong> {piso}<br>
                    <strong>Estado:</strong> <span style="color: {color}; font-weight: bold;">{estado.upper()}</span>
            """, unsafe_allow_html=True)
            
            if precio:
                st.markdown(f"""
                    <strong>Precio:</strong> ${precio:,.2f}/noche<br>
                """, unsafe_allow_html=True)
            
            if capacidad:
                st.markdown(f"""
                    <strong>Capacidad:</strong> {capacidad} personas
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Botón de acción
            if on_click and estado.lower() in ['disponible', 'reservada']:
                if st.button(button_text, key=key, use_container_width=True):
                    on_click()
    
    @staticmethod
    def render_minimal(
        numero: str,
        estado: str,
        tipo: str = "",
        on_click: Optional[Callable] = None,
        key: Optional[str] = None
    ):
        """
        Versión minimalista de la tarjeta (para listas grandes).
        """
        # Definir emojis según estado
        emojis_estado = {
            'disponible': '✅',
            'ocupada': '👤',
            'mantenimiento': '🔧',
            'reservada': '📅',
            'limpieza': '🧹'
        }
        
        colores_estado = {
            'disponible': '#28a745',
            'ocupada': '#dc3545',
            'mantenimiento': '#ffc107',
            'reservada': '#17a2b8',
            'limpieza': '#6c757d'
        }
        
        emoji = emojis_estado.get(estado.lower(), '❓')
        color = colores_estado.get(estado.lower(), '#6c757d')
        
        # Tarjeta horizontal
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            st.markdown(f"<h2 style='color: {color};'>{emoji}</h2>", unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                **Hab. {numero}** - {tipo}<br>
                <span style="color: {color};">{estado}</span>
            """, unsafe_allow_html=True)
        
        with col3:
            if on_click and estado.lower() in ['disponible', 'reservada']:
                if st.button("📌", key=key):
                    on_click()
    
    @staticmethod
    def render_selector(
        habitaciones: list,
        titulo: str = "Seleccionar Habitación",
        columnas: int = 3
    ):
        """
        Renderiza un grid de habitaciones seleccionables.
        """
        st.subheader(titulo)
        
        if not habitaciones:
            st.info("No hay habitaciones disponibles")
            return None
        
        habitacion_seleccionada = None
        
        # Crear grid
        for i in range(0, len(habitaciones), columnas):
            cols = st.columns(columnas)
            for j in range(columnas):
                idx = i + j
                if idx < len(habitaciones):
                    hab = habitaciones[idx]
                    
                    with cols[j]:
                        # Determinar si está disponible
                        disponible = hab.get('estado_actual', '').lower() in ['disponible', 'reservada']
                        
                        # Botón de selección
                        button_type = "primary" if disponible else "secondary"
                        
                        st.markdown(f"""
                        <div style="
                            border: 1px solid #ddd;
                            border-radius: 5px;
                            padding: 10px;
                            margin: 5px;
                            text-align: center;
                        ">
                            <h4>Habitación {hab['numero_habitacion']}</h4>
                            <p>{hab.get('tipo', '')}</p>
                            <p>Piso: {hab.get('piso', 1)}</p>
                        """, unsafe_allow_html=True)
                        
                        if disponible:
                            if st.button(f"Seleccionar Hab. {hab['numero_habitacion']}", 
                                       key=f"sel_hab_{hab['id']}",
                                       use_container_width=True):
                                habitacion_seleccionada = hab
                        
                        st.markdown("</div>", unsafe_allow_html=True)
        
        return habitacion_seleccionada
    
    @staticmethod
    def render_estado_habitacion(habitacion: Dict):
        """
        Renderiza el estado detallado de una habitación.
        """
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Indicador visual de estado
            estados_info = {
                'disponible': {'color': '#28a745', 'icono': '✅', 'texto': 'Disponible'},
                'ocupada': {'color': '#dc3545', 'icono': '👤', 'texto': 'Ocupada'},
                'mantenimiento': {'color': '#ffc107', 'icono': '🔧', 'texto': 'Mantenimiento'},
                'reservada': {'color': '#17a2b8', 'icono': '📅', 'texto': 'Reservada'},
                'limpieza': {'color': '#6c757d', 'icono': '🧹', 'texto': 'Limpieza'}
            }
            
            estado = habitacion.get('estado_actual', 'disponible').lower()
            info = estados_info.get(estado, estados_info['disponible'])
            
            st.markdown(f"""
            <div style="
                background-color: {info['color']}20;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
            ">
                <h1 style="font-size: 48px; margin: 0;">{info['icono']}</h1>
                <h3 style="color: {info['color']}; margin: 0;">{info['texto']}</h3>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            ### Habitación {habitacion.get('numero_habitacion', 'N/A')}
            
            **Tipo:** {habitacion.get('tipo', 'No especificado')}  
            **Piso:** {habitacion.get('piso', 1)}  
            **Capacidad:** {habitacion.get('capacidad', 2)} personas  
            **Precio:** ${habitacion.get('precio', 0):,.2f}/noche  
            """)
            
            if habitacion.get('notas'):
                st.info(f"📝 Notas: {habitacion['notas']}")
    
    @staticmethod
    def render_lista_compacta(habitaciones: list, max_items: int = 10):
        """
        Renderiza una lista compacta de habitaciones.
        """
        if not habitaciones:
            st.caption("No hay habitaciones para mostrar")
            return
        
        for hab in habitaciones[:max_items]:
            estado = hab.get('estado_actual', 'desconocido')
            color = {
                'disponible': 'green',
                'ocupada': 'red',
                'mantenimiento': 'orange',
                'reservada': 'blue',
                'limpieza': 'gray'
            }.get(estado, 'gray')
            
            st.markdown(f"""
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 5px;
                border-bottom: 1px solid #eee;
            ">
                <span><b>Hab. {hab.get('numero_habitacion', 'N/A')}</b> - {hab.get('tipo', '')}</span>
                <span style="color: {color}; font-weight: bold;">{estado.upper()}</span>
            </div>
            """, unsafe_allow_html=True)
        
        if len(habitaciones) > max_items:
            st.caption(f"... y {len(habitaciones) - max_items} más")