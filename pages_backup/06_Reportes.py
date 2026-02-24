import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import tempfile
import os
from core.database import run_query
from services.report_service import (
    generar_reporte_ocupacion,
    generar_reporte_ingresos,
    generar_reporte_estadistico
)
from utils.helpers import formatear_moneda


st.title("📄 Generación de Reportes")
st.markdown("---")

# Inicializar estado
if 'reporte_generado' not in st.session_state:
    st.session_state.reporte_generado = None

# Tipos de reporte
tipo_reporte = st.selectbox(
    "Seleccionar tipo de reporte",
    [
        "Reporte de Ocupación",
        "Reporte de Ingresos",
        "Reporte de Estadísticas Generales",
        "Reporte de Consumos",
        "Reporte de Huéspedes Frecuentes"
    ]
)

# Filtros comunes
col1, col2 = st.columns(2)
with col1:
    fecha_inicio = st.date_input(
        "Fecha de inicio",
        value=date.today() - timedelta(days=30),
        key="reporte_fecha_inicio"
    )
with col2:
    fecha_fin = st.date_input(
        "Fecha de fin",
        value=date.today(),
        key="reporte_fecha_fin",
        min_value=fecha_inicio
    )

# Filtros específicos según tipo
if tipo_reporte == "Reporte de Ocupación":
    incluir_detalle = st.checkbox("Incluir detalle por habitación", value=True)
    agrupar_por = st.selectbox(
        "Agrupar por",
        ["Día", "Semana", "Mes"]
    )

elif tipo_reporte == "Reporte de Ingresos":
    incluir_consumos = st.checkbox("Incluir consumos", value=True)
    incluir_impuestos = st.checkbox("Incluir desglose de impuestos", value=True)

elif tipo_reporte == "Reporte de Consumos":
    categorias = st.multiselect(
        "Categorías de consumo",
        ["Minibar", "Restaurante", "Lavandería", "Spa", "Otros"],
        default=["Minibar", "Restaurante"]
    )

elif tipo_reporte == "Reporte de Huéspedes Frecuentes":
    min_estancias = st.number_input("Mínimo de estancias", min_value=1, value=2)
    incluir_contacto = st.checkbox("Incluir datos de contacto", value=True)

# Botón para generar reporte
if st.button("📊 Generar Reporte", type="primary", use_container_width=True):
    with st.spinner("Generando reporte..."):
        
        if tipo_reporte == "Reporte de Ocupación":
            # Consulta de ocupación
            query = """
            SELECT 
                DATE(e.fecha_checkin_esperada) as fecha,
                h.numero_habitacion,
                t.nombre as tipo_habitacion,
                CASE 
                    WHEN e.estado_estancia = 'activa' THEN 'Ocupada'
                    WHEN e.estado_estancia = 'finalizada' THEN 'Finalizada'
                END as estado,
                e.numero_adultos + e.numero_ninos as personas,
                e.fecha_checkout_esperada as fecha_salida,
                CASE 
                    WHEN e.reserva_id IS NOT NULL THEN 'Reserva'
                    ELSE 'Walk-In'
                END as tipo_ingreso
            FROM estancias e
            JOIN habitaciones h ON e.habitacion_id = h.id
            JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
            WHERE e.fecha_checkin_esperada BETWEEN %s AND %s
            ORDER BY e.fecha_checkin_esperada
            """
            
            df = pd.DataFrame(run_query(query, (fecha_inicio, fecha_fin)))
            
            if not df.empty:
                st.session_state.reporte_generado = {
                    'tipo': 'ocupacion',
                    'data': df,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin
                }
            else:
                st.warning("No hay datos para el período seleccionado")
        
        elif tipo_reporte == "Reporte de Ingresos":
            # Consulta de ingresos
            query = """
            SELECT 
                DATE(f.fecha_emision) as fecha,
                f.numero_factura,
                h.nombre_completo as huesped,
                hab.numero_habitacion,
                f.subtotal,
                f.impuestos,
                f.total,
                f.metodo_pago,
                f.estado_pago
            FROM facturas f
            JOIN huespedes h ON f.huesped_id = h.id
            JOIN estancias e ON f.estancia_id = e.id
            JOIN habitaciones hab ON e.habitacion_id = hab.id
            WHERE f.fecha_emision::DATE BETWEEN %s AND %s
            ORDER BY f.fecha_emision
            """
            
            df = pd.DataFrame(run_query(query, (fecha_inicio, fecha_fin)))
            
            if not df.empty:
                st.session_state.reporte_generado = {
                    'tipo': 'ingresos',
                    'data': df,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin
                }
            else:
                st.warning("No hay datos para el período seleccionado")
        
        elif tipo_reporte == "Reporte de Estadísticas Generales":
            # Estadísticas generales
            stats_query = """
            WITH estadisticas AS (
                SELECT 
                    COUNT(DISTINCT e.id) as total_estancias,
                    COUNT(DISTINCT h.id) as huespedes_unicos,
                    SUM(e.fecha_checkout_esperada - e.fecha_checkin_esperada) as noches_totales,
                    AVG(e.fecha_checkout_esperada - e.fecha_checkin_esperada) as promedio_noches,
                    SUM(f.total) as ingresos_totales,
                    AVG(f.total) as ticket_promedio,
                    COUNT(DISTINCT CASE WHEN e.reserva_id IS NOT NULL THEN e.id END) as estancias_con_reserva,
                    COUNT(DISTINCT CASE WHEN e.reserva_id IS NULL THEN e.id END) as walk_ins
                FROM estancias e
                LEFT JOIN facturas f ON e.id = f.estancia_id
                JOIN huespedes h ON e.huesped_id = h.id
                WHERE e.fecha_checkin_esperada BETWEEN %s AND %s
            )
            SELECT * FROM estadisticas
            """
            
            stats = run_query(stats_query, (fecha_inicio, fecha_fin))
            
            # Ocupación por tipo
            tipos_query = """
            SELECT 
                t.nombre as tipo_habitacion,
                COUNT(e.id) as num_estancias,
                SUM(e.fecha_checkout_esperada - e.fecha_checkin_esperada) as noches,
                AVG(e.precio_acordado_por_noche) as precio_promedio
            FROM estancias e
            JOIN habitaciones h ON e.habitacion_id = h.id
            JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
            WHERE e.fecha_checkin_esperada BETWEEN %s AND %s
            GROUP BY t.nombre
            ORDER BY num_estancias DESC
            """
            
            df_tipos = pd.DataFrame(run_query(tipos_query, (fecha_inicio, fecha_fin)))
            
            st.session_state.reporte_generado = {
                'tipo': 'estadisticas',
                'stats': stats[0] if stats else {},
                'tipos': df_tipos,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin
            }

# Mostrar reporte generado
if st.session_state.reporte_generado:
    st.markdown("---")
    st.subheader("📋 Reporte Generado")
    
    reporte = st.session_state.reporte_generado
    
    if reporte['tipo'] == 'ocupacion':
        df = reporte['data']
        
        # Resumen
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Registros", len(df))
        with col2:
            ocupadas = len(df[df['estado'] == 'Ocupada'])
            st.metric("Estancias Activas", ocupadas)
        with col3:
            total_personas = df['personas'].sum()
            st.metric("Total Huéspedes", total_personas)
        
        # Mostrar datos
        st.dataframe(
            df,
            column_config={
                "fecha": "Fecha",
                "numero_habitacion": "Habitación",
                "tipo_habitacion": "Tipo",
                "estado": "Estado",
                "personas": "Personas",
                "fecha_salida": "Salida",
                "tipo_ingreso": "Tipo Ingreso"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Botón de descarga
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Reporte CSV",
            data=csv,
            file_name=f"reporte_ocupacion_{reporte['fecha_inicio']}_{reporte['fecha_fin']}.csv",
            mime="text/csv"
        )
    
    elif reporte['tipo'] == 'ingresos':
        df = reporte['data']
        
        # Resumen
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Facturas", len(df))
        with col2:
            total_ingresos = df['total'].sum()
            st.metric("Ingresos Totales", formatear_moneda(total_ingresos))
        with col3:
            ticket_promedio = df['total'].mean()
            st.metric("Ticket Promedio", formatear_moneda(ticket_promedio))
        
        # Mostrar datos
        df_display = df.copy()
        df_display['subtotal'] = df_display['subtotal'].apply(formatear_moneda)
        df_display['impuestos'] = df_display['impuestos'].apply(formatear_moneda)
        df_display['total'] = df_display['total'].apply(formatear_moneda)
        
        st.dataframe(
            df_display,
            column_config={
                "fecha": "Fecha",
                "numero_factura": "Factura N°",
                "huesped": "Huésped",
                "numero_habitacion": "Hab.",
                "subtotal": "Subtotal",
                "impuestos": "Impuestos",
                "total": "Total",
                "metodo_pago": "Método Pago",
                "estado_pago": "Estado"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Botón de descarga
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Reporte CSV",
            data=csv,
            file_name=f"reporte_ingresos_{reporte['fecha_inicio']}_{reporte['fecha_fin']}.csv",
            mime="text/csv"
        )
    
    elif reporte['tipo'] == 'estadisticas':
        stats = reporte['stats']
        df_tipos = reporte['tipos']
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Estancias", stats.get('total_estancias', 0))
        with col2:
            st.metric("Huéspedes Únicos", stats.get('huespedes_unicos', 0))
        with col3:
            st.metric("Noches Totales", stats.get('noches_totales', 0))
        with col4:
            st.metric("Promedio Noches", f"{stats.get('promedio_noches', 0):.1f}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Ingresos Totales", formatear_moneda(stats.get('ingresos_totales', 0)))
        with col2:
            st.metric("Ticket Promedio", formatear_moneda(stats.get('ticket_promedio', 0)))
        with col3:
            st.metric("Con Reserva", stats.get('estancias_con_reserva', 0))
        with col4:
            st.metric("Walk-Ins", stats.get('walk_ins', 0))
        
        # Distribución por tipo
        if not df_tipos.empty:
            st.subheader("Distribución por Tipo de Habitación")
            st.dataframe(
                df_tipos,
                column_config={
                    "tipo_habitacion": "Tipo",
                    "num_estancias": "N° Estancias",
                    "noches": "Noches",
                    "precio_promedio": st.column_config.NumberColumn("Precio Prom.", format="$%.2f")
                },
                hide_index=True,
                use_container_width=True
            )
        
        # Botón de descarga
        if st.button("📥 Exportar Estadísticas"):
            # Crear reporte en PDF
            pdf_bytes = generar_reporte_estadistico(
                stats,
                df_tipos,
                reporte['fecha_inicio'],
                reporte['fecha_fin']
            )
            
            if pdf_bytes:
                st.download_button(
                    label="📥 Descargar Reporte PDF",
                    data=pdf_bytes,
                    file_name=f"estadisticas_{reporte['fecha_inicio']}_{reporte['fecha_fin']}.pdf",
                    mime="application/pdf"
                )
    
    # Botón para nuevo reporte
    if st.button("🆕 Nuevo Reporte"):
        st.session_state.reporte_generado = None
        st.rerun()