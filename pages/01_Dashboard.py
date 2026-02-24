import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from core.database import run_query
from utils.helpers import formatear_moneda, formatear_fecha


# Título
st.title("📊 Panel de Control - Vista General")
st.markdown("---")

# Filtros en sidebar
with st.sidebar:
    st.header("Filtros del Dashboard")
    fecha_inicio = st.date_input("Fecha Inicio", date.today() - timedelta(days=30))
    fecha_fin = st.date_input("Fecha Fin", date.today())
    ver_detalle = st.checkbox("Mostrar detalles", value=True)

# Obtener datos del dashboard
def get_dashboard_data(fecha_inicio, fecha_fin):
    """Obtiene todos los datos necesarios para el dashboard"""
    
    # KPIs principales
    kpis_query = """
    WITH stats AS (
        SELECT 
            (SELECT COUNT(*) FROM habitaciones WHERE activa = true) as total_habitaciones,
            (SELECT COUNT(DISTINCT habitacion_id) FROM estancias 
             WHERE estado_estancia = 'activa') as habitaciones_ocupadas,
            (SELECT COUNT(*) FROM estancias WHERE fecha_checkout_esperada = CURRENT_DATE 
             AND estado_estancia = 'activa') as salidas_hoy,
            (SELECT COUNT(*) FROM reservas WHERE fecha_checkin = CURRENT_DATE 
             AND estado_reserva = 'confirmada') as llegadas_hoy,
            COALESCE((SELECT SUM(total) FROM facturas 
             WHERE fecha_emision::DATE = CURRENT_DATE AND estado_pago = 'pagado'), 0) as ingresos_hoy,
            COALESCE((SELECT SUM(total) FROM facturas 
             WHERE fecha_emision::DATE BETWEEN %s AND %s AND estado_pago = 'pagado'), 0) as ingresos_periodo
    )
    SELECT * FROM stats
    """
    
    kpis = run_query(kpis_query, (fecha_inicio, fecha_fin))
    
    # Ocupación por día (últimos 30 días)
    ocupacion_query = """
    WITH fechas AS (
        SELECT generate_series(%s::DATE, %s::DATE, '1 day'::interval)::DATE AS fecha
    )
    SELECT 
        f.fecha,
        COUNT(DISTINCT e.habitacion_id) as habitaciones_ocupadas,
        (SELECT COUNT(*) FROM habitaciones WHERE activa = true) as total_habitaciones,
        ROUND(COUNT(DISTINCT e.habitacion_id)::NUMERIC / 
              NULLIF((SELECT COUNT(*) FROM habitaciones WHERE activa = true), 0) * 100, 2) as porcentaje_ocupacion
    FROM fechas f
    LEFT JOIN estancias e ON 
        e.fecha_checkin_esperada <= f.fecha 
        AND e.fecha_checkout_esperada > f.fecha
        AND e.estado_estancia IN ('activa', 'finalizada')
    GROUP BY f.fecha
    ORDER BY f.fecha
    """
    
    df_ocupacion = pd.DataFrame(run_query(ocupacion_query, (fecha_inicio, fecha_fin)))
    
    # Ingresos por día
    ingresos_query = """
    SELECT 
        DATE(fecha_emision) as fecha,
        SUM(total) as ingresos,
        COUNT(*) as num_facturas
    FROM facturas
    WHERE fecha_emision::DATE BETWEEN %s AND %s
    AND estado_pago = 'pagado'
    GROUP BY DATE(fecha_emision)
    ORDER BY fecha
    """
    
    df_ingresos = pd.DataFrame(run_query(ingresos_query, (fecha_inicio, fecha_fin)))
    
    # Últimas reservas
    reservas_query = """
    SELECT 
        r.codigo_reserva,
        h.nombre_completo as huesped,
        t.nombre as tipo_habitacion,
        r.fecha_checkin,
        r.fecha_checkout,
        r.estado_reserva,
        r.numero_adultos + r.numero_ninos as personas
    FROM reservas r
    JOIN huespedes h ON r.huesped_id = h.id
    JOIN tipos_habitacion t ON r.tipo_habitacion_solicitada_id = t.id
    WHERE r.fecha_checkin BETWEEN %s AND %s
    ORDER BY r.fecha_checkin DESC
    LIMIT 10
    """
    
    df_reservas = pd.DataFrame(run_query(reservas_query, (fecha_inicio, fecha_fin)))
    
    return kpis[0] if kpis else {}, df_ocupacion, df_ingresos, df_reservas

# Cargar datos
with st.spinner("Cargando datos del dashboard..."):
    kpis, df_ocupacion, df_ingresos, df_reservas = get_dashboard_data(fecha_inicio, fecha_fin)

# KPIs en 4 columnas
col1, col2, col3, col4 = st.columns(4)

with col1:
    ocupacion = kpis.get('habitaciones_ocupadas', 0)
    total_hab = kpis.get('total_habitaciones', 1)
    porcentaje_ocupacion = (ocupacion / total_hab * 100) if total_hab > 0 else 0
    
    st.metric(
        label="🏨 Ocupación Actual",
        value=f"{ocupacion}/{total_hab} hab",
        delta=f"{porcentaje_ocupacion:.1f}%",
        delta_color="off"
    )

with col2:
    st.metric(
        label="📅 Llegadas/ Salidas Hoy",
        value=f"⬇️ {kpis.get('llegadas_hoy', 0)} / ⬆️ {kpis.get('salidas_hoy', 0)}",
        delta=None
    )

with col3:
    st.metric(
        label="💰 Ingresos Hoy",
        value=formatear_moneda(kpis.get('ingresos_hoy', 0)),
        delta=formatear_moneda(kpis.get('ingresos_periodo', 0)) if kpis.get('ingresos_periodo') else None,
        delta_color="normal"
    )

with col4:
    # Calcular ingresos promedio diario
    if not df_ingresos.empty:
        avg_ingresos = df_ingresos['ingresos'].mean()
        st.metric(
            label="📊 Promedio Diario",
            value=formatear_moneda(avg_ingresos),
            delta=None
        )
    else:
        st.metric(label="📊 Promedio Diario", value="$0")

st.markdown("---")

# Gráficos en 2 columnas
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Tendencia de Ocupación")
    if not df_ocupacion.empty:
        fig = px.line(
            df_ocupacion, 
            x='fecha', 
            y='porcentaje_ocupacion',
            title="% Ocupación por Día",
            labels={'porcentaje_ocupacion': '% Ocupación', 'fecha': 'Fecha'}
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de ocupación para mostrar")

with col2:
    st.subheader("💰 Ingresos Diarios")
    if not df_ingresos.empty:
        fig = px.bar(
            df_ingresos,
            x='fecha',
            y='ingresos',
            title="Ingresos por Día",
            labels={'ingresos': 'Ingresos ($)', 'fecha': 'Fecha'}
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de ingresos para mostrar")

# Distribución de habitaciones
st.subheader("🏢 Distribución de Habitaciones por Tipo")

distribucion_query = """
SELECT 
    t.nombre as tipo_habitacion,
    COUNT(h.id) as total_habitaciones,
    SUM(CASE WHEN h.estado_actual = 'ocupada' THEN 1 ELSE 0 END) as ocupadas,
    ROUND(AVG(t.precio_base_por_noche), 2) as precio_promedio
FROM tipos_habitacion t
LEFT JOIN habitaciones h ON t.id = h.tipo_habitacion_id AND h.activa = true
GROUP BY t.id, t.nombre
ORDER BY t.nombre
"""

df_distribucion = pd.DataFrame(run_query(distribucion_query))

if not df_distribucion.empty:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Gráfico de barras apiladas
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Ocupadas',
            x=df_distribucion['tipo_habitacion'],
            y=df_distribucion['ocupadas'],
            marker_color='#FF6B6B'
        ))
        fig.add_trace(go.Bar(
            name='Disponibles',
            x=df_distribucion['tipo_habitacion'],
            y=df_distribucion['total_habitaciones'] - df_distribucion['ocupadas'],
            marker_color='#4ECDC4'
        ))
        fig.update_layout(
            barmode='stack',
            title="Ocupación por Tipo de Habitación",
            xaxis_title="Tipo de Habitación",
            yaxis_title="Número de Habitaciones"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.dataframe(
            df_distribucion,
            column_config={
                "tipo_habitacion": "Tipo",
                "total_habitaciones": "Total",
                "ocupadas": "Ocupadas",
                "precio_promedio": st.column_config.NumberColumn("Precio Prom.", format="$%.2f")
            },
            hide_index=True,
            use_container_width=True
        )

# Últimas reservas
if ver_detalle:
    st.markdown("---")
    st.subheader("📋 Últimas Reservas")
    
    if not df_reservas.empty:
        df_reservas['fecha_checkin'] = pd.to_datetime(df_reservas['fecha_checkin']).dt.strftime('%d/%m/%Y')
        df_reservas['fecha_checkout'] = pd.to_datetime(df_reservas['fecha_checkout']).dt.strftime('%d/%m/%Y')
        
        # Colorear según estado
        def color_estado(val):
            colors = {
                'confirmada': 'background-color: #90EE90',
                'checkeado': 'background-color: #87CEEB',
                'cancelada': 'background-color: #FFB6C1',
                'no_show': 'background-color: #D3D3D3'
            }
            return colors.get(val, '')
        
        styled_df = df_reservas.style.map(color_estado, subset=['estado_reserva'])
        st.dataframe(
            styled_df,
            column_config={
                "codigo_reserva": "Código",
                "huesped": "Huésped",
                "tipo_habitacion": "Tipo Hab.",
                "fecha_checkin": "Check-in",
                "fecha_checkout": "Check-out",
                "estado_reserva": "Estado",
                "personas": "Personas"
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No hay reservas en el período seleccionado")

# Alertas y notificaciones
st.markdown("---")
with st.expander("🔔 Alertas y Notificaciones"):
    col1, col2 = st.columns(2)
    
    with col1:
        # Habitaciones en mantenimiento
        mantenimiento_query = """
        SELECT COUNT(*) as en_mantenimiento
        FROM habitaciones
        WHERE estado_actual = 'mantenimiento' AND activa = true
        """
        mantenimiento = run_query(mantenimiento_query)
        if mantenimiento and mantenimiento[0]['en_mantenimiento'] > 0:
            st.warning(f"🔧 {mantenimiento[0]['en_mantenimiento']} habitaciones en mantenimiento")
    
    with col2:
        # Reservas sin confirmar
        pendientes_query = """
        SELECT COUNT(*) as pendientes
        FROM reservas
        WHERE estado_reserva = 'confirmada' AND fecha_checkin < CURRENT_DATE + INTERVAL '2 days'
        """
        pendientes = run_query(pendientes_query)
        if pendientes and pendientes[0]['pendientes'] > 0:
            st.info(f"📅 {pendientes[0]['pendientes']} reservas próximas")