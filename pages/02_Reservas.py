import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import plotly.express as px
from core.database import run_query
from utils.helpers import formatear_moneda, validar_fechas
from utils.validators import validar_email, validar_telefono
import uuid


st.title("📅 Gestión de Reservas")
st.markdown("---")

# Inicializar estado de sesión para la reserva actual
if 'reserva_step' not in st.session_state:
    st.session_state.reserva_step = 1
if 'reserva_data' not in st.session_state:
    st.session_state.reserva_data = {}
if 'editing_reserva' not in st.session_state:
    st.session_state.editing_reserva = False

# Función para obtener tipos de habitación disponibles
def get_tipos_habitacion():
    from core.database import run_query
    query = """
    SELECT id, nombre, descripcion, capacidad_maxima, precio_base_por_noche
    FROM tipos_habitacion
    WHERE activo = true
    ORDER BY precio_base_por_noche
    """
    result = run_query(query)
    return pd.DataFrame(result) if result else pd.DataFrame()

# Función para verificar disponibilidad
# Función para verificar disponibilidad (VERSIÓN CORREGIDA)
def verificar_disponibilidad(fecha_checkin, fecha_checkout, tipo_habitacion_id, num_habitaciones=1):
    """
    Verifica cuántas habitaciones de un tipo están disponibles para un período.
    Retorna True si hay al menos num_habitaciones disponibles.
    """
    
    # Consulta para obtener:
    # - Total de habitaciones de este tipo
    # - Habitaciones ocupadas por estancias activas
    # - Reservas confirmadas (que ocupan una habitación virtual)
    query = """
    WITH 
    -- Total de habitaciones de este tipo
    total_habitaciones AS (
        SELECT COUNT(*) as total
        FROM habitaciones
        WHERE tipo_habitacion_id = %s AND activa = true
    ),
    -- Habitaciones ocupadas por estancias activas en el período
    estancias_ocupadas AS (
        SELECT COUNT(DISTINCT e.habitacion_id) as ocupadas
        FROM estancias e
        JOIN habitaciones h ON e.habitacion_id = h.id
        WHERE h.tipo_habitacion_id = %s
        AND e.estado_estancia = 'activa'
        AND e.fecha_checkin_esperada < %s  -- Check-in antes de la salida
        AND e.fecha_checkout_esperada > %s -- Check-out después de la entrada
    ),
    -- Reservas confirmadas que ocupan este tipo de habitación en el período
    reservas_ocupadas AS (
        SELECT COUNT(*) as reservadas
        FROM reservas
        WHERE tipo_habitacion_solicitada_id = %s
        AND estado_reserva = 'confirmada'
        AND fecha_checkin < %s
        AND fecha_checkout > %s
    )
    SELECT 
        (SELECT total FROM total_habitaciones) as total,
        (SELECT ocupadas FROM estancias_ocupadas) as ocupadas,
        (SELECT reservadas FROM reservas_ocupadas) as reservadas,
        (SELECT total FROM total_habitaciones) 
        - (SELECT ocupadas FROM estancias_ocupadas) 
        - (SELECT reservadas FROM reservas_ocupadas) as disponibles
    """
    
    result = run_query(query, (
        tipo_habitacion_id,  # para total
        tipo_habitacion_id, fecha_checkout, fecha_checkin,  # para estancias
        tipo_habitacion_id, fecha_checkout, fecha_checkin   # para reservas
    ))
    
    if result and len(result) > 0:
        disponibles = result[0]['disponibles']
        st.write(f"🔍 Debug: Total={result[0]['total']}, Ocupadas={result[0]['ocupadas']}, Reservadas={result[0]['reservadas']}, Disponibles={disponibles}")
        return disponibles >= num_habitaciones
    
    return False

# Función para crear una nueva reserva
def crear_reserva(data):
    codigo = f"RES-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    
    huesped_existente = run_query(
        "SELECT id FROM huespedes WHERE tipo_documento = %s AND numero_documento = %s",
        (data['tipo_documento'], data['numero_documento'])
    )
    if huesped_existente:
        huesped_id = huesped_existente[0]['id']
        run_query(
            "UPDATE huespedes SET nombre_completo = %s, email = %s, telefono = %s WHERE id = %s",
            (data['nombre'], data.get('email') or '', data.get('telefono') or '', huesped_id)
        )
    else:
        huesped_result = run_query(
            """INSERT INTO huespedes (nombre_completo, tipo_documento, numero_documento, email, telefono)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (data['nombre'], data['tipo_documento'], data['numero_documento'],
             data.get('email') or '', data.get('telefono') or '')
        )
        if not huesped_result:
            return None
        huesped_id = huesped_result[0]['id']
    
    
    reserva_result = run_query(
        """INSERT INTO reservas (codigo_reserva, huesped_id, tipo_habitacion_solicitada_id,
           fecha_checkin, fecha_checkout, numero_adultos, numero_ninos, estado_reserva, observaciones)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (codigo, huesped_id, data['tipo_habitacion_id'], data['fecha_checkin'], data['fecha_checkout'],
         data['adultos'], data['ninos'], 'confirmada', data.get('observaciones', ''))
    )
    return reserva_result[0]['id'] if reserva_result else None

# Pestañas para diferentes vistas
tab1, tab2, tab3 = st.tabs(["📝 Nueva Reserva", "📋 Ver Reservas", "🔍 Buscar Disponibilidad"])

with tab1:
    st.subheader("Nueva Reserva")
    
    # Paso 1: Información básica
    with st.form("form_reserva_basico"):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_checkin = st.date_input(
                "Fecha de Check-in",
                min_value=date.today(),
                value=date.today() + timedelta(days=1)
            )
            adultos = st.number_input("Número de Adultos", min_value=1, max_value=10, value=2)
            tipo_documento = st.selectbox(
                "Tipo de Documento",
                ["DNI", "Pasaporte", "Cédula", "Otro"]
            )
        
        with col2:
            fecha_checkout = st.date_input(
                "Fecha de Check-out",
                min_value=fecha_checkin + timedelta(days=1),
                value=fecha_checkin + timedelta(days=3)
            )
            ninos = st.number_input("Número de Niños", min_value=0, max_value=10, value=0)
            numero_documento = st.text_input("Número de Documento")
        
        # Validar fechas
        if fecha_checkin >= fecha_checkout:
            st.error("La fecha de check-out debe ser posterior al check-in")
        
        nombre_completo = st.text_input("Nombre Completo del Huésped")
        
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Email")
        with col2:
            telefono = st.text_input("Teléfono")
        
        # Selección de tipo de habitación
        df_tipos = get_tipos_habitacion()
        if not df_tipos.empty:
            tipo_habitacion = st.selectbox(
                "Tipo de Habitación",
                options=df_tipos['id'].tolist(),
                format_func=lambda x: f"{df_tipos[df_tipos['id']==x]['nombre'].values[0]} - ${df_tipos[df_tipos['id']==x]['precio_base_por_noche'].values[0]:.2f}/noche"
            )
            
            # Mostrar capacidad máxima
            capacidad_max = df_tipos[df_tipos['id']==tipo_habitacion]['capacidad_maxima'].values[0]
            if adultos + ninos > capacidad_max:
                st.warning(f"⚠️ La capacidad máxima de esta habitación es {capacidad_max} personas")
        else:
            st.error("No hay tipos de habitación disponibles")
            tipo_habitacion = None
        
        observaciones = st.text_area("Observaciones")
        
        submitted = st.form_submit_button("Verificar Disponibilidad y Continuar")
        
        if submitted:
            if not nombre_completo or not numero_documento:
                st.error("Por favor complete los campos obligatorios")
            elif not validar_email(email) and email:
                st.error("Email no válido")
            elif tipo_habitacion:
                # Verificar disponibilidad
                disponible = verificar_disponibilidad(
                    fecha_checkin, fecha_checkout, tipo_habitacion
                )
                
                if disponible:
                    st.session_state.reserva_data = {
                        'fecha_checkin': fecha_checkin,
                        'fecha_checkout': fecha_checkout,
                        'adultos': adultos,
                        'ninos': ninos,
                        'tipo_documento': tipo_documento,
                        'numero_documento': numero_documento,
                        'nombre': nombre_completo,
                        'email': email,
                        'telefono': telefono,
                        'tipo_habitacion_id': tipo_habitacion,
                        'observaciones': observaciones
                    }
                    st.session_state.reserva_step = 2
                    st.success("✅ Habitación disponible. Complete la confirmación.")
                    st.rerun()
                else:
                    st.error("No hay disponibilidad para las fechas seleccionadas")
    
    # Paso 2: Confirmación
    if st.session_state.reserva_step == 2 and st.session_state.reserva_data:
        st.subheader("Paso 2: Confirmar Reserva")
        
        data = st.session_state.reserva_data
        df_tipos = get_tipos_habitacion()
        tipo_info = df_tipos[df_tipos['id'] == data['tipo_habitacion_id']].iloc[0]
        
        # Resumen de la reserva
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Información del Huésped:**")
            st.write(f"**Nombre:** {data['nombre']}")
            st.write(f"**Documento:** {data['tipo_documento']} - {data['numero_documento']}")
            st.write(f"**Email:** {data['email']}")
            st.write(f"**Teléfono:** {data['telefono']}")
        
        with col2:
            st.markdown("**Detalles de la Reserva:**")
            st.write(f"**Check-in:** {data['fecha_checkin'].strftime('%d/%m/%Y')}")
            st.write(f"**Check-out:** {data['fecha_checkout'].strftime('%d/%m/%Y')}")
            st.write(f"**Personas:** {data['adultos']} adultos, {data['ninos']} niños")
            st.write(f"**Habitación:** {tipo_info['nombre']}")
            
            noches = (data['fecha_checkout'] - data['fecha_checkin']).days
            total = noches * tipo_info['precio_base_por_noche']
            st.write(f"**Total estimado:** {formatear_moneda(total)} ({noches} noches)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("⬅️ Modificar"):
                st.session_state.reserva_step = 1
                st.rerun()
        
        with col2:
            if st.button("✅ Confirmar Reserva"):
                with st.spinner("Creando reserva..."):
                    # IMPORTANTE: Usar el servicio en lugar de la función local
                    from services.reserva_service import ReservaService
                    from models import Reserva, Huesped
                    
                    # Crear objetos con los datos del formulario
                    nuevo_huesped = Huesped(
                        nombre_completo=data['nombre'],
                        tipo_documento=data['tipo_documento'],
                        numero_documento=data['numero_documento'],
                        email=data.get('email'),
                        telefono=data.get('telefono')
                    )
                    
                    nueva_reserva = Reserva(
                        fecha_checkin=data['fecha_checkin'],
                        fecha_checkout=data['fecha_checkout'],
                        numero_adultos=data['adultos'],
                        numero_ninos=data['ninos'],
                        tipo_habitacion_solicitada_id=data['tipo_habitacion_id'],
                        observaciones=data.get('observaciones', '')
                    )
                    
                    # Llamar al servicio
                    reserva_id = ReservaService.crear_reserva(nueva_reserva, nuevo_huesped)
                    
                    if reserva_id:
                        st.success("🎉 ¡Reserva creada exitosamente!")
                        st.balloons()
                        st.session_state.reserva_step = 1
                        st.session_state.reserva_data = {}
                        st.rerun()
                    else:
                        st.error("Error al crear la reserva")

with tab2:
    st.subheader("Listado de Reservas")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_estado = st.selectbox(
            "Estado",
            ["Todas", "confirmada", "checkeado", "cancelada", "no_show"]
        )
    with col2:
        fecha_desde = st.date_input("Desde", date.today() - timedelta(days=30))
    with col3:
        fecha_hasta = st.date_input("Hasta", date.today() + timedelta(days=30))
    
    # Consulta de reservas
    query = """
    SELECT 
        r.codigo_reserva,
        h.nombre_completo as huesped,
        h.numero_documento as documento,
        t.nombre as tipo_habitacion,
        r.fecha_checkin,
        r.fecha_checkout,
        r.numero_adultos + r.numero_ninos as personas,
        r.estado_reserva,
        r.observaciones,
        (r.fecha_checkout - r.fecha_checkin) as noches,
        t.precio_base_por_noche * (r.fecha_checkout - r.fecha_checkin) as total_estimado
    FROM reservas r
    JOIN huespedes h ON r.huesped_id = h.id
    JOIN tipos_habitacion t ON r.tipo_habitacion_solicitada_id = t.id
    WHERE r.fecha_checkin BETWEEN %s AND %s
    """
    
    params = [fecha_desde, fecha_hasta]
    
    if filtro_estado != "Todas":
        query += " AND r.estado_reserva = %s"
        params.append(filtro_estado)
    
    query += " ORDER BY r.fecha_checkin DESC"
    
    df_reservas = pd.DataFrame(run_query(query, tuple(params)))
    
    if not df_reservas.empty:
        # Formatear fechas
        df_reservas['fecha_checkin'] = pd.to_datetime(df_reservas['fecha_checkin']).dt.strftime('%d/%m/%Y')
        df_reservas['fecha_checkout'] = pd.to_datetime(df_reservas['fecha_checkout']).dt.strftime('%d/%m/%Y')
        
        # Mostrar DataFrame interactivo
        st.dataframe(
            df_reservas,
            column_config={
                "codigo_reserva": "Código",
                "huesped": "Huésped",
                "documento": "Documento",
                "tipo_habitacion": "Tipo Hab.",
                "fecha_checkin": "Check-in",
                "fecha_checkout": "Check-out",
                "personas": "Personas",
                "estado_reserva": "Estado",
                "noches": "Noches",
                "total_estimado": st.column_config.NumberColumn("Total Est.", format="$%.2f")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Estadísticas rápidas
        st.markdown("---")
        st.subheader("📊 Resumen de Reservas")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Reservas", len(df_reservas))
        with col2:
            confirmadas = len(df_reservas[df_reservas['estado_reserva'] == 'confirmada'])
            st.metric("Confirmadas", confirmadas)
        with col3:
            total_ingresos = df_reservas['total_estimado'].sum()
            st.metric("Ingresos Estimados", formatear_moneda(total_ingresos))
        with col4:
            noches_totales = df_reservas['noches'].sum()
            st.metric("Noches Reservadas", noches_totales)
    else:
        st.info("No se encontraron reservas para los filtros seleccionados")

with tab3:
    st.subheader("Buscar Disponibilidad")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input(
            "Fecha de Inicio",
            min_value=date.today(),
            value=date.today(),
            key="disp_inicio"
        )
    with col2:
        fecha_fin = st.date_input(
            "Fecha de Fin",
            min_value=fecha_inicio + timedelta(days=1),
            value=fecha_inicio + timedelta(days=1),
            key="disp_fin"
        )
    
    if st.button("🔍 Buscar Disponibilidad"):
        # Consulta corregida para mostrar disponibilidad real
        query = """
        WITH 
        -- Totales por tipo
        total_por_tipo AS (
            SELECT 
                t.id,
                t.nombre,
                t.capacidad_maxima,
                t.precio_base_por_noche,
                COUNT(h.id) as total_habitaciones
            FROM tipos_habitacion t
            LEFT JOIN habitaciones h ON t.id = h.tipo_habitacion_id AND h.activa = true
            WHERE t.activo = true
            GROUP BY t.id, t.nombre, t.capacidad_maxima, t.precio_base_por_noche
        ),
        -- Estancias activas en el período
        estancias_en_periodo AS (
            SELECT 
                h.tipo_habitacion_id,
                COUNT(DISTINCT e.habitacion_id) as ocupadas
            FROM estancias e
            JOIN habitaciones h ON e.habitacion_id = h.id
            WHERE e.estado_estancia = 'activa'
            AND e.fecha_checkin_esperada < %s
            AND e.fecha_checkout_esperada > %s
            GROUP BY h.tipo_habitacion_id
        ),
        -- Reservas confirmadas en el período
        reservas_en_periodo AS (
            SELECT 
                tipo_habitacion_solicitada_id,
                COUNT(*) as reservadas
            FROM reservas
            WHERE estado_reserva = 'confirmada'
            AND fecha_checkin < %s
            AND fecha_checkout > %s
            GROUP BY tipo_habitacion_solicitada_id
        )
        SELECT 
            t.id as tipo_habitacion_id,
            t.nombre as tipo_habitacion,
            t.capacidad_maxima,
            t.precio_base_por_noche,
            t.total_habitaciones,
            COALESCE(e.ocupadas, 0) as ocupadas,
            COALESCE(r.reservadas, 0) as reservadas,
            (t.total_habitaciones - COALESCE(e.ocupadas, 0) - COALESCE(r.reservadas, 0)) as disponibles
        FROM total_por_tipo t
        LEFT JOIN estancias_en_periodo e ON t.id = e.tipo_habitacion_id
        LEFT JOIN reservas_en_periodo r ON t.id = r.tipo_habitacion_solicitada_id
        ORDER BY t.precio_base_por_noche
        """
        
        df_disponibilidad = pd.DataFrame(run_query(query, (fecha_fin, fecha_inicio, fecha_fin, fecha_inicio)))
        
        if not df_disponibilidad.empty:
            st.subheader("Resultados de Disponibilidad")
            
            for _, row in df_disponibilidad.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 1, 1])
                    with col1:
                        st.write(f"**{row['tipo_habitacion']}**")
                    with col2:
                        st.write(f"Capacidad: {row['capacidad_maxima']} pers")
                    with col3:
                        st.write(f"Precio: {formatear_moneda(row['precio_base_por_noche'])}/noche")
                    with col4:
                        st.write(f"Total: {row['total_habitaciones']}")
                    with col5:
                        disponibles = row['disponibles']
                        color = "green" if disponibles > 0 else "red"
                        st.markdown(f"<span style='color:{color}; font-weight:bold'>**{disponibles} disp**</span>", unsafe_allow_html=True)
                    with col6:
                        if disponibles > 0:
                            if st.button("Seleccionar", key=f"sel_{row['tipo_habitacion_id']}"):
                                st.session_state.reserva_data['tipo_habitacion_id'] = row['tipo_habitacion_id']
                                st.session_state.reserva_step = 1
                                st.rerun()
                    st.markdown("---")
                    
                    # Mostrar detalles si hay ocupadas o reservadas
                    if row['ocupadas'] > 0 or row['reservadas'] > 0:
                        with st.expander(f"Ver detalles de ocupación para {row['tipo_habitacion']}"):
                            if row['ocupadas'] > 0:
                                st.info(f"🏨 {row['ocupadas']} habitaciones ocupadas por estancias activas")
                            if row['reservadas'] > 0:
                                st.warning(f"📅 {row['reservadas']} habitaciones reservadas")
        else:
            st.info("No hay habitaciones disponibles para las fechas seleccionadas")


