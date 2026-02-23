import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from core.database import run_query
from utils.helpers import formatear_moneda

st.set_page_config(page_title="Estadísticas", page_icon="📊", layout="wide")

st.title("📊 Estadísticas y Análisis")
st.markdown("---")

# Filtros globales
with st.sidebar:
    st.header("Filtros de Análisis")
    
    periodo = st.selectbox(
        "Período",
        ["Últimos 7 días", "Últimos 30 días", "Últimos 90 días", "Año actual", "Personalizado"]
    )
    
    if periodo == "Personalizado":
        fecha_inicio = st.date_input("Fecha inicio", date.today() - timedelta(days=30))
        fecha_fin = st.date_input("Fecha fin", date.today())
    else:
        fecha_fin = date.today()
        if periodo == "Últimos 7 días":
            fecha_inicio = date.today() - timedelta(days=7)
        elif periodo == "Últimos 30 días":
            fecha_inicio = date.today() - timedelta(days=30)
        elif periodo == "Últimos 90 días":
            fecha_inicio = date.today() - timedelta(days=90)
        else:  # Año actual
            fecha_inicio = date(date.today().year, 1, 1)
    
    incluir_consumos = st.checkbox("Incluir consumos en ingresos", value=True)

# Obtener datos para estadísticas
def get_estadisticas_generales(fecha_inicio, fecha_fin, incluir_consumos):
    """Obtiene estadísticas generales del período"""
    
    # Ingresos por día
    if incluir_consumos:
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
    else:
        ingresos_query = """
        SELECT 
            DATE(fecha_emision) as fecha,
            SUM(subtotal) as ingresos,
            COUNT(*) as num_facturas
        FROM facturas
        WHERE fecha_emision::DATE BETWEEN %s AND %s
        AND estado_pago = 'pagado'
        GROUP BY DATE(fecha_emision)
        ORDER BY fecha
        """
    
    df_ingresos = pd.DataFrame(run_query(ingresos_query, (fecha_inicio, fecha_fin)))
    
    # Ocupación por día
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
    
    # Tipos de habitación más reservados
    tipos_query = """
    SELECT 
        t.nombre as tipo_habitacion,
        COUNT(DISTINCT e.id) as num_estancias,
        SUM(e.fecha_checkout_esperada - e.fecha_checkin_esperada) as noches_totales,
        ROUND(AVG(e.precio_acordado_por_noche), 2) as precio_promedio,
        SUM((e.fecha_checkout_esperada - e.fecha_checkin_esperada) * e.precio_acordado_por_noche) as ingresos_totales
    FROM estancias e
    JOIN habitaciones h ON e.habitacion_id = h.id
    JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
    WHERE e.fecha_checkin_esperada BETWEEN %s AND %s
    GROUP BY t.id, t.nombre
    ORDER BY num_estancias DESC
    """
    
    df_tipos = pd.DataFrame(run_query(tipos_query, (fecha_inicio, fecha_fin)))
    
    # Procedencia de huéspedes (por tipo de documento como proxy)
    procedencia_query = """
    SELECT 
        h.tipo_documento,
        COUNT(DISTINCT e.id) as num_estancias,
        COUNT(DISTINCT h.id) as num_huespedes,
        AVG(e.fecha_checkout_esperada - e.fecha_checkin_esperada) as estancia_promedio
    FROM estancias e
    JOIN huespedes h ON e.huesped_id = h.id
    WHERE e.fecha_checkin_esperada BETWEEN %s AND %s
    GROUP BY h.tipo_documento
    ORDER BY num_estancias DESC
    """
    
    df_procedencia = pd.DataFrame(run_query(procedencia_query, (fecha_inicio, fecha_fin)))
    
    return df_ingresos, df_ocupacion, df_tipos, df_procedencia

# Cargar datos
with st.spinner("Cargando estadísticas..."):
    df_ingresos, df_ocupacion, df_tipos, df_procedencia = get_estadisticas_generales(
        fecha_inicio, fecha_fin, incluir_consumos
    )

# KPIs generales
st.subheader("📌 Resumen del Período")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if not df_ingresos.empty:
        total_ingresos = df_ingresos['ingresos'].sum()
        st.metric("Ingresos Totales", formatear_moneda(total_ingresos))
    else:
        st.metric("Ingresos Totales", "$0")

with col2:
    if not df_ocupacion.empty:
        ocupacion_promedio = df_ocupacion['porcentaje_ocupacion'].mean()
        st.metric("Ocupación Promedio", f"{ocupacion_promedio:.1f}%")
    else:
        st.metric("Ocupación Promedio", "0%")

with col3:
    if not df_ingresos.empty:
        num_facturas = df_ingresos['num_facturas'].sum()
        st.metric("Total Facturas", int(num_facturas))
    else:
        st.metric("Total Facturas", "0")

with col4:
    if not df_ocupacion.empty:
        total_noches = (fecha_fin - fecha_inicio).days
        st.metric("Días Analizados", total_noches)
    else:
        st.metric("Días Analizados", "0")

st.markdown("---")

# Gráficos principales
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Evolución de Ingresos")
    if not df_ingresos.empty:
        fig = px.line(
            df_ingresos,
            x='fecha',
            y='ingresos',
            title="Ingresos Diarios",
            labels={'ingresos': 'Ingresos ($)', 'fecha': 'Fecha'}
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de ingresos para el período")

with col2:
    st.subheader("📊 Ocupación Diaria")
    if not df_ocupacion.empty:
        fig = px.area(
            df_ocupacion,
            x='fecha',
            y='porcentaje_ocupacion',
            title="% Ocupación Diaria",
            labels={'porcentaje_ocupacion': '% Ocupación', 'fecha': 'Fecha'}
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de ocupación para el período")

# Distribución por tipo de habitación
st.markdown("---")
st.subheader("🏨 Análisis por Tipo de Habitación")

if not df_tipos.empty:
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(
            df_tipos,
            values='num_estancias',
            names='tipo_habitacion',
            title="Distribución de Estancias por Tipo"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            df_tipos,
            x='tipo_habitacion',
            y='ingresos_totales',
            title="Ingresos por Tipo de Habitación",
            labels={'ingresos_totales': 'Ingresos ($)', 'tipo_habitacion': 'Tipo'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Tabla detallada
    st.subheader("📋 Detalle por Tipo de Habitación")
    df_tipos_display = df_tipos.copy()
    df_tipos_display['ingresos_totales'] = df_tipos_display['ingresos_totales'].apply(formatear_moneda)
    df_tipos_display['precio_promedio'] = df_tipos_display['precio_promedio'].apply(lambda x: f"${x:,.2f}")
    
    st.dataframe(
        df_tipos_display,
        column_config={
            "tipo_habitacion": "Tipo",
            "num_estancias": "N° Estancias",
            "noches_totales": "Noches",
            "precio_promedio": "Precio Prom.",
            "ingresos_totales": "Ingresos"
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.info("No hay datos de tipos de habitación para el período")

# Análisis de tendencias
st.markdown("---")
st.subheader("📈 Análisis de Tendencias")

if not df_ocupacion.empty and not df_ingresos.empty:
    # Calcular métricas de tendencia
    ocupacion_media = df_ocupacion['porcentaje_ocupacion'].mean()
    ingresos_medios = df_ingresos['ingresos'].mean()
    
    # Días de la semana
    df_ocupacion['dia_semana'] = pd.to_datetime(df_ocupacion['fecha']).dt.day_name()
    ocupacion_dia = df_ocupacion.groupby('dia_semana')['porcentaje_ocupacion'].mean().reset_index()
    
    # Ordenar días
    orden_dias = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    ocupacion_dia['dia_semana'] = pd.Categorical(ocupacion_dia['dia_semana'], categories=orden_dias, ordered=True)
    ocupacion_dia = ocupacion_dia.sort_values('dia_semana')
    ocupacion_dia['dia_semana'] = ocupacion_dia['dia_semana'].cat.rename_categories(nombres_dias)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            ocupacion_dia,
            x='dia_semana',
            y='porcentaje_ocupacion',
            title="Ocupación Promedio por Día",
            labels={'porcentaje_ocupacion': '% Ocupación', 'dia_semana': 'Día'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Análisis de estacionalidad
        df_ocupacion['mes'] = pd.to_datetime(df_ocupacion['fecha']).dt.month
        ocupacion_mes = df_ocupacion.groupby('mes')['porcentaje_ocupacion'].mean().reset_index()
        
        nombres_meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        ocupacion_mes['mes_nombre'] = ocupacion_mes['mes'].apply(lambda x: nombres_meses[x-1])
        
        fig = px.line(
            ocupacion_mes,
            x='mes_nombre',
            y='porcentaje_ocupacion',
            title="Ocupación por Mes",
            labels={'porcentaje_ocupacion': '% Ocupación', 'mes_nombre': 'Mes'}
        )
        st.plotly_chart(fig, use_container_width=True)

# Procedencia de huéspedes
if not df_procedencia.empty:
    st.markdown("---")
    st.subheader("🌍 Procedencia de Huéspedes")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(
            df_procedencia,
            values='num_huespedes',
            names='tipo_documento',
            title="Distribución por Tipo de Documento"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            df_procedencia,
            x='tipo_documento',
            y='estancia_promedio',
            title="Duración Promedio de Estancia",
            labels={'estancia_promedio': 'Días', 'tipo_documento': 'Tipo'}
        )
        st.plotly_chart(fig, use_container_width=True)

# Exportar datos
st.markdown("---")
with st.expander("📥 Exportar Datos"):
    st.write("Descargar datos en formato CSV")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not df_ingresos.empty:
            csv_ingresos = df_ingresos.to_csv(index=False)
            st.download_button(
                label="📊 Ingresos",
                data=csv_ingresos,
                file_name=f"ingresos_{fecha_inicio}_{fecha_fin}.csv",
                mime="text/csv"
            )
    
    with col2:
        if not df_ocupacion.empty:
            csv_ocupacion = df_ocupacion.to_csv(index=False)
            st.download_button(
                label="🏨 Ocupación",
                data=csv_ocupacion,
                file_name=f"ocupacion_{fecha_inicio}_{fecha_fin}.csv",
                mime="text/csv"
            )
    
    with col3:
        if not df_tipos.empty:
            csv_tipos = df_tipos.to_csv(index=False)
            st.download_button(
                label="📋 Tipos Habitación",
                data=csv_tipos,
                file_name=f"tipos_habitacion_{fecha_inicio}_{fecha_fin}.csv",
                mime="text/csv"
            )