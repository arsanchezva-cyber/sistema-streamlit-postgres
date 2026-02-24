import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from core.database import run_query, execute_transaction
from utils.helpers import formatear_fecha

st.set_page_config(page_title="Check-In", page_icon="✅", layout="wide")

st.title("✅ Proceso de Check-In")
st.markdown("---")

# Inicializar estado de sesión
if 'checkin_step' not in st.session_state:
    st.session_state.checkin_step = 1
if 'checkin_data' not in st.session_state:
    st.session_state.checkin_data = {}
if 'selected_reserva' not in st.session_state:
    st.session_state.selected_reserva = None
if 'show_walkin_selection' not in st.session_state:
    st.session_state.show_walkin_selection = False
if 'walkin_data' not in st.session_state:
    st.session_state.walkin_data = {}

# Función para buscar reserva
def buscar_reserva(codigo=None, documento=None):
    query = """
    SELECT 
        t.precio_base_por_noche,
        r.id,
        r.codigo_reserva,
        h.id as huesped_id,
        h.nombre_completo,
        h.tipo_documento,
        h.numero_documento,
        h.email,
        h.telefono,
        t.nombre as tipo_habitacion,
        t.id as tipo_habitacion_id,
        t.precio_base_por_noche,
        r.fecha_checkin,
        r.fecha_checkout,
        r.numero_adultos,
        r.numero_ninos,
        r.observaciones
    FROM reservas r
    JOIN huespedes h ON r.huesped_id = h.id
    JOIN tipos_habitacion t ON r.tipo_habitacion_solicitada_id = t.id
    WHERE r.estado_reserva = 'confirmada'
    """
    
    if codigo:
        query += " AND r.codigo_reserva = %s"
        params = [codigo]
    elif documento:
        query += " AND h.numero_documento = %s AND r.fecha_checkin <= CURRENT_DATE"
        params = [documento]
    else:
        return None
    
    result = run_query(query, tuple(params))
    return result[0] if result else None

# Función para obtener habitaciones disponibles por tipo
def get_habitaciones_disponibles(tipo_habitacion_id, fecha_checkin, fecha_checkout):
    query = """
    SELECT 
        h.id,
        h.numero_habitacion,
        h.piso
    FROM habitaciones h
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
    return pd.DataFrame(run_query(query, (tipo_habitacion_id, fecha_checkout, fecha_checkin)))

# Función para realizar check-in (CORREGIDA - USA TRANSACCIÓN)
def realizar_checkin(data):
    # Verificar que la habitación sigue disponible
    check_disponibilidad = """
    SELECT COUNT(*) as ocupada
    FROM estancias
    WHERE habitacion_id = %s
    AND estado_estancia = 'activa'
    AND fecha_checkin_esperada < %s
    AND fecha_checkout_esperada > %s
    """
    
    result = run_query(check_disponibilidad, (data['habitacion_id'], data['fecha_checkout'], data['fecha_checkin']))
    
    if result and result[0]['ocupada'] > 0:
        st.error("La habitación ya no está disponible")
        return None
    
    # Preparar transacción
    queries = []
    
    # Insertar estancia
    queries.append((
        """
        INSERT INTO estancias (
            reserva_id, huesped_id, habitacion_id,
            fecha_checkin_real, fecha_checkin_esperada, fecha_checkout_esperada,
            numero_adultos, numero_ninos, precio_acordado_por_noche,
            estado_estancia, observaciones
        ) VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, 'activa', %s)
        RETURNING id
        """,
        (
            data.get('reserva_id'),
            data['huesped_id'],
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
    
    if success and results and len(results) > 0 and results[0] and len(results[0]) > 0:
        estancia_id = results[0][0]['id']
        return estancia_id
    
    return None

# Pestañas para diferentes tipos de check-in
tab1, tab2 = st.tabs(["📋 Desde Reserva", "🚶 Walk-In (Sin Reserva)"])

with tab1:
    st.subheader("Check-In desde Reserva")
    
    # Paso 1: Buscar reserva
    if st.session_state.checkin_step == 1:
        with st.form("buscar_reserva_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                codigo_reserva = st.text_input("Código de Reserva")
            with col2:
                st.write("O")
                documento = st.text_input("Número de Documento")
            
            buscar = st.form_submit_button("🔍 Buscar Reserva")
            
            if buscar:
                reserva = None
                if codigo_reserva:
                    reserva = buscar_reserva(codigo=codigo_reserva)
                elif documento:
                    reserva = buscar_reserva(documento=documento)
                
                if reserva:
                    st.session_state.selected_reserva = reserva
                    st.session_state.checkin_step = 2
                    st.rerun()
                else:
                    st.error("No se encontró una reserva confirmada para hoy")
    
    # Paso 2: Confirmar datos y seleccionar habitación
    elif st.session_state.checkin_step == 2 and st.session_state.selected_reserva:
        reserva = st.session_state.selected_reserva
        
        st.success(f"✅ Reserva encontrada: {reserva['codigo_reserva']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Datos del Huésped:**")
            st.write(f"**Nombre:** {reserva['nombre_completo']}")
            st.write(f"**Documento:** {reserva['tipo_documento']} - {reserva['numero_documento']}")
            st.write(f"**Email:** {reserva['email']}")
            st.write(f"**Teléfono:** {reserva['telefono']}")
        
        with col2:
            st.markdown("**Detalles de la Reserva:**")
            st.write(f"**Check-in:** {formatear_fecha(reserva['fecha_checkin'])}")
            st.write(f"**Check-out:** {formatear_fecha(reserva['fecha_checkout'])}")
            st.write(f"**Adultos:** {reserva['numero_adultos']}")
            st.write(f"**Niños:** {reserva['numero_ninos']}")
            st.write(f"**Tipo Habitación:** {reserva['tipo_habitacion']}")
        
        # Buscar habitaciones disponibles
        habitaciones_disp = get_habitaciones_disponibles(
            reserva['tipo_habitacion_id'],
            reserva['fecha_checkin'],
            reserva['fecha_checkout']
        )
        
        if not habitaciones_disp.empty:
            st.subheader("Seleccionar Habitación")
            
            # Mostrar habitaciones disponibles en grid
            cols = st.columns(3)
            for idx, (_, hab) in enumerate(habitaciones_disp.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"### Habitación {hab['numero_habitacion']}")
                        st.write(f"Piso: {hab['piso']}")
                        
                        if st.button(
                            "Seleccionar",
                            key=f"sel_hab_{hab['id']}",
                            use_container_width=True
                        ):
                            st.session_state.checkin_data = {
                                'reserva_id': reserva['id'],
                                'huesped_id': reserva['huesped_id'],
                                'habitacion_id': hab['id'],
                                'fecha_checkin': reserva['fecha_checkin'],
                                'fecha_checkout': reserva['fecha_checkout'],
                                'adultos': reserva['numero_adultos'],
                                'ninos': reserva['numero_ninos'],
                                'precio_noche': reserva.get('precio_base_por_noche', 100.00),
                                'observaciones': reserva.get('observaciones', '')
                            }
                            st.session_state.checkin_step = 3
                            st.rerun()
        else:
            st.error("No hay habitaciones disponibles de este tipo")
        
        if st.button("⬅️ Volver"):
            st.session_state.checkin_step = 1
            st.session_state.selected_reserva = None
            st.rerun()
    
    # Paso 3: Confirmar check-in
    elif st.session_state.checkin_step == 3 and st.session_state.checkin_data:
        st.subheader("Confirmar Check-In")
        
        data = st.session_state.checkin_data
        
        st.info("Por favor revise los datos antes de confirmar el check-in")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Resumen:**")
            st.write(f"**Reserva:** {st.session_state.selected_reserva['codigo_reserva']}")
            st.write(f"**Huésped:** {st.session_state.selected_reserva['nombre_completo']}")
            st.write(f"**Habitación:** {data['habitacion_id']}")
        
        with col2:
            st.markdown("**Acción:**")
            if st.button("✅ Confirmar Check-In", type="primary"):
                with st.spinner("Procesando check-in..."):
                    estancia_id = realizar_checkin(data)
                    if estancia_id:
                        st.success("🎉 ¡Check-in realizado exitosamente!")
                        st.balloons()
                        
                        # Limpiar estado
                        st.session_state.checkin_step = 1
                        st.session_state.checkin_data = {}
                        st.session_state.selected_reserva = None
                    else:
                        st.error("Error al realizar el check-in")

with tab2:
    st.subheader("Walk-In (Sin Reserva)")
    
    with st.form("walkin_form"):
        st.markdown("### Datos del Huésped")
        
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre Completo *")
            tipo_documento = st.selectbox(
                "Tipo de Documento *",
                ["DNI", "Pasaporte", "Cédula"]
            )
            email = st.text_input("Email")
        
        with col2:
            telefono = st.text_input("Teléfono *")
            numero_documento = st.text_input("Número de Documento *")
            fecha_nacimiento = st.date_input("Fecha de Nacimiento", value=None)
        
        st.markdown("### Detalles de la Estancia")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_checkin = date.today()
            st.write(f"**Check-in:** {formatear_fecha(fecha_checkin)}")
            adultos = st.number_input("Adultos *", min_value=1, value=2)
        
        with col2:
            fecha_checkout = st.date_input(
                "Check-out *",
                min_value=date.today() + timedelta(days=1),
                value=date.today() + timedelta(days=2)
            )
            ninos = st.number_input("Niños", min_value=0, value=0)
        
        # Selección de tipo de habitación
        tipos_query = """
        SELECT id, nombre, precio_base_por_noche, capacidad_maxima
        FROM tipos_habitacion
        WHERE activo = true
        ORDER BY precio_base_por_noche
        """
        df_tipos = pd.DataFrame(run_query(tipos_query))
        
        if not df_tipos.empty:
            tipo_habitacion = st.selectbox(
                "Tipo de Habitación *",
                options=df_tipos['id'].tolist(),
                format_func=lambda x: f"{df_tipos[df_tipos['id']==x]['nombre'].values[0]} - ${df_tipos[df_tipos['id']==x]['precio_base_por_noche'].values[0]:.2f}/noche"
            )
            
            # Verificar capacidad
            capacidad = df_tipos[df_tipos['id']==tipo_habitacion]['capacidad_maxima'].values[0]
            if adultos + ninos > capacidad:
                st.warning(f"⚠️ Capacidad máxima: {capacidad} personas")
        
        observaciones = st.text_area("Observaciones")
        
        submitted = st.form_submit_button("Buscar Disponibilidad")
        
        if submitted:
            if not all([nombre, telefono, numero_documento]):
                st.error("Complete los campos obligatorios (*)")
            else:
                # Buscar habitaciones disponibles
                from services.check_in_service import CheckInService
                habitaciones_disp = CheckInService.obtener_habitaciones_disponibles(
                    tipo_habitacion,
                    fecha_checkin,
                    fecha_checkout
                )
                
                if habitaciones_disp and len(habitaciones_disp) > 0:
                    st.session_state.walkin_data = {
                        'nombre': nombre,
                        'tipo_documento': tipo_documento,
                        'numero_documento': numero_documento,
                        'email': email,
                        'telefono': telefono,
                        'fecha_nacimiento': fecha_nacimiento,
                        'fecha_checkin': fecha_checkin,
                        'fecha_checkout': fecha_checkout,
                        'adultos': adultos,
                        'ninos': ninos,
                        'tipo_habitacion_id': tipo_habitacion,
                        'observaciones': observaciones,
                        'precio_noche': df_tipos[df_tipos['id']==tipo_habitacion]['precio_base_por_noche'].values[0],
                        'habitaciones_disponibles': habitaciones_disp
                    }
                    st.session_state.show_walkin_selection = True
                    st.rerun()
                else:
                    st.error("No hay habitaciones disponibles para las fechas seleccionadas")
    
    # Mostrar selección de habitación para walk-in
    if 'show_walkin_selection' in st.session_state and st.session_state.show_walkin_selection:
        st.markdown("---")
        st.subheader("Seleccionar Habitación")
        
        data = st.session_state.walkin_data
        
        # Mostrar habitaciones disponibles
        cols = st.columns(3)
        for idx, hab in enumerate(data['habitaciones_disponibles']):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"### Habitación {hab['numero_habitacion']}")
                    st.write(f"Piso: {hab['piso']}")
                    st.write(f"Precio: ${data['precio_noche']:.2f}/noche")
                    
                    if st.button(
                        "Seleccionar y Confirmar Check-In",
                        key=f"walkin_hab_{hab['id']}",
                        use_container_width=True
                    ):
                        with st.spinner("Procesando check-in..."):
                            # Preparar datos para la transacción
                            walkin_data = {
                                'nombre': data['nombre'],
                                'tipo_documento': data['tipo_documento'],
                                'numero_documento': data['numero_documento'],
                                'email': data.get('email'),
                                'telefono': data['telefono'],
                                'fecha_nacimiento': data.get('fecha_nacimiento'),
                                'habitacion_id': hab['id'],
                                'fecha_checkin': data['fecha_checkin'],
                                'fecha_checkout': data['fecha_checkout'],
                                'adultos': data['adultos'],
                                'ninos': data['ninos'],
                                'precio_noche': data['precio_noche'],
                                'observaciones': data.get('observaciones', '')
                            }
                            
                            # Usar la función específica para walk-in
                            from services.check_in_service import CheckInService
                            estancia_id = CheckInService.realizar_checkin_walkin(walkin_data)
                            
                            if estancia_id:
                                st.success("✅ ¡Check-In realizado exitosamente!")
                                st.balloons()
                                st.session_state.show_walkin_selection = False
                                del st.session_state.walkin_data
                                st.rerun()
                            else:
                                st.error("Error al realizar el check-in")