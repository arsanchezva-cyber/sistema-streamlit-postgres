import streamlit as st
from datetime import datetime
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Gestión Hotelera",
    page_icon="🏨",
    layout="wide",
)

# Inicializar estado de sesión
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Dashboard"

# Función de login simple (en producción usar autenticación real)
def login():
    st.sidebar.title("🔐 Acceso al Sistema")
    username = st.sidebar.text_input("Usuario")
    password = st.sidebar.text_input("Contraseña", type="password")
    
    if st.sidebar.button("Ingresar"):
        # Autenticación básica (mejorar en producción)
        if username == "admin" and password == "admin123":
            st.session_state.authenticated = True
            st.session_state.username = username
            st.sidebar.success("¡Login exitoso!")
            st.rerun()
        else:
            st.sidebar.error("Credenciales incorrectas")

# Verificar autenticación
if not st.session_state.authenticated:
    st.title("🏨 Sistema de Gestión Hotelera")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        
        st.markdown("""
        ### Bienvenido al Sistema de Gestión Hotelera
        
        Por favor, inicie sesión para continuar.
        
        **Credenciales de prueba:**
        - Usuario: admin
        - Contraseña: admin123
        """)
    login()
else:
    # Barra lateral con menú de navegación
    st.sidebar.title(f"👤 Bienvenido, {st.session_state.username}")
    st.sidebar.markdown("---")
    
    
    
    
    st.sidebar.markdown("---")
    
    # Información del sistema
    st.sidebar.info(
        f"**Hotel Gestión v1.0**\n\n"
        f"Fecha: {datetime.now().strftime('%d/%m/%Y')}\n"
        f"Hora: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    # Botón de logout
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
    
    # Página principal
    st.title(f"🏨 {st.session_state.current_page}")
    st.markdown("---")
    
  