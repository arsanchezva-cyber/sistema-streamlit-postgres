import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import run_query
from services.facturacion_service import generar_factura, get_consumos_estancia
from services.report_service import generar_factura_pdf
from utils.helpers import formatear_moneda

st.set_page_config(page_title="Check-Out", page_icon="❌", layout="wide")

st.title("❌ Check-Out y Facturación")
st.markdown("---")

# Inicializar estado
if 'checkout_estancia' not in st.session_state:
    st.session_state.checkout_estancia = None
if 'checkout_step' not in st.session_state:
    st.session_state.checkout_step = 1

# Función para buscar estancias activas
def buscar_estancias_activas(filtro=None, valor=None):
    query = """
    SELECT 
        e.id as estancia_id,
        e.huesped_id,
        h.nombre_completo,
        h.tipo_documento,
        h.numero_documento,
        h.telefono,
        hab.numero_habitacion,
        t.nombre as tipo_habitacion,
        e.fecha_checkin_real,
        e.fecha_checkout_esperada,
        e.numero_adultos,
        e.numero_ninos,
        e.precio_acordado_por_noche,
        e.observaciones,
        CASE 
            WHEN e.reserva_id IS NOT NULL THEN r.codigo_reserva 
            ELSE 'WALK-IN' 
        END as codigo_referencia
    FROM estancias e
    JOIN huespedes h ON e.huesped_id = h.id
    JOIN habitaciones hab ON e.habitacion_id = hab.id
    JOIN tipos_habitacion t ON hab.tipo_habitacion_id = t.id
    LEFT JOIN reservas r ON e.reserva_id = r.id
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
    
    return pd.DataFrame(run_query(query, tuple(params) if params else None))

# Función para agregar consumo
def agregar_consumo(estancia_id, descripcion, cantidad, precio_unitario):
    query = """
    INSERT INTO consumos (estancia_id, descripcion, cantidad, precio_unitario)
    VALUES (%s, %s, %s, %s)
    RETURNING id
    """
    result = run_query(query, (estancia_id, descripcion, cantidad, precio_unitario))
    return result[0]['id'] if result else None

# Paso 1: Buscar estancia para checkout
if st.session_state.checkout_step == 1:
    st.subheader("Buscar Huésped para Check-Out")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        filtro = st.radio(
            "Buscar por:",
            ["Habitación", "Documento", "Nombre"]
        )
    
    with col2:
        if filtro == "Habitación":
            valor = st.text_input("Número de Habitación")
        elif filtro == "Documento":
            valor = st.text_input("Número de Documento")
        else:
            valor = st.text_input("Nombre del Huésped")
        
        if st.button("🔍 Buscar", type="primary") and valor:
            df_estancias = buscar_estancias_activas(filtro, valor)
            
            if not df_estancias.empty:
                st.session_state.search_results = df_estancias
            else:
                st.warning("No se encontraron estancias activas")
                st.session_state.search_results = pd.DataFrame()
    
    # Mostrar resultados de búsqueda
    if 'search_results' in st.session_state and not st.session_state.search_results.empty:
        st.markdown("---")
        st.subheader("Estancias Activas Encontradas")
        
        df = st.session_state.search_results
        for idx, row in df.iterrows():
            with st.container(border=True):
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
                
                with col1:
                    st.write(f"**{row['nombre_completo']}**")
                    st.write(f"Hab: {row['numero_habitacion']} - {row['tipo_habitacion']}")
                
                with col2:
                    checkin = pd.to_datetime(row['fecha_checkin_real']).strftime('%d/%m/%Y %H:%M')
                    st.write(f"Check-in: {checkin}")
                    st.write(f"Check-out esperado: {pd.to_datetime(row['fecha_checkout_esperada']).strftime('%d/%m/%Y')}")
                
                with col3:
                    noches = (datetime.now().date() - pd.to_datetime(row['fecha_checkin_real']).date()).days
                    st.metric("Noches", max(1, noches))
                
                with col4:
                    total_estadia = max(1, noches) * row['precio_acordado_por_noche']
                    st.metric("Total Estadia", formatear_moneda(total_estadia))
                
                with col5:
                    if st.button("Seleccionar", key=f"sel_{row['estancia_id']}"):
                        st.session_state.checkout_estancia = row.to_dict()
                        st.session_state.checkout_step = 2
                        st.rerun()

# Paso 2: Procesar checkout y consumos
elif st.session_state.checkout_step == 2 and st.session_state.checkout_estancia:
    estancia = st.session_state.checkout_estancia
    
    st.success(f"Procesando Check-Out para: **{estancia['nombre_completo']}** - Habitación {estancia['numero_habitacion']}")
    
    # Pestañas para consumos y facturación
    tab1, tab2, tab3 = st.tabs(["➕ Agregar Consumos", "📋 Resumen de Consumos", "💰 Facturación"])
    
    with tab1:
        st.subheader("Agregar Consumo")
        
        with st.form("form_consumo"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                descripcion = st.text_input("Descripción del consumo *")
            with col2:
                cantidad = st.number_input("Cantidad", min_value=1, value=1)
            with col3:
                precio_unitario = st.number_input(
                    "Precio Unitario *",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    format="%.2f"
                )
            
            submitted = st.form_submit_button("➕ Agregar Consumo")
            
            if submitted and descripcion and precio_unitario > 0:
                consumo_id = agregar_consumo(
                    estancia['estancia_id'],
                    descripcion,
                    cantidad,
                    precio_unitario
                )
                if consumo_id:
                    st.success("✅ Consumo agregado correctamente")
                    st.rerun()
                else:
                    st.error("Error al agregar el consumo")
    
    with tab2:
        st.subheader("Consumos Registrados")
        
        # Obtener consumos
        consumos_list = get_consumos_estancia(estancia['estancia_id'])
        df_consumos = pd.DataFrame(consumos_list) if consumos_list else pd.DataFrame()
        
        if not df_consumos.empty:
            # Calcular total
            total_consumos = (df_consumos['cantidad'] * df_consumos['precio_unitario']).sum()
            
            # Mostrar tabla
            df_display = df_consumos.copy()
            df_display['fecha_consumo'] = pd.to_datetime(df_display['fecha_consumo']).dt.strftime('%d/%m/%Y %H:%M')
            df_display['total'] = df_display['cantidad'] * df_display['precio_unitario']
            
            st.dataframe(
                df_display[['descripcion', 'cantidad', 'precio_unitario', 'total', 'fecha_consumo']],
                column_config={
                    "descripcion": "Descripción",
                    "cantidad": "Cant.",
                    "precio_unitario": st.column_config.NumberColumn("P. Unitario", format="$%.2f"),
                    "total": st.column_config.NumberColumn("Total", format="$%.2f"),
                    "fecha_consumo": "Fecha"
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.metric("Total Consumos", formatear_moneda(total_consumos))
        else:
            st.info("No hay consumos registrados para esta estancia")
    
    with tab3:
        st.subheader("Facturación")
        
        # Calcular totales
        noches = (datetime.now().date() - pd.to_datetime(estancia['fecha_checkin_real']).date()).days
        noches = max(1, noches)  # Mínimo 1 noche
        
        total_alojamiento = noches * estancia['precio_acordado_por_noche']
        
        df_consumos = get_consumos_estancia(estancia['estancia_id'])
        total_consumos = (df_consumos['cantidad'] * df_consumos['precio_unitario']).sum() if not df_consumos.empty else 0
        
        subtotal = total_alojamiento + total_consumos
        impuestos = subtotal * 0.16  # 16% IVA
        total = subtotal + impuestos
        
        # Resumen de cargos
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Detalle de Cargos:**")
            st.write(f"Alojamiento ({noches} noches): {formatear_moneda(total_alojamiento)}")
            st.write(f"Consumos: {formatear_moneda(total_consumos)}")
            st.write(f"Subtotal: {formatear_moneda(subtotal)}")
            st.write(f"Impuestos (16%): {formatear_moneda(impuestos)}")
            st.markdown("---")
            st.markdown(f"### TOTAL: {formatear_moneda(total)}")
        
        with col2:
            st.markdown("**Método de Pago:**")
            metodo_pago = st.selectbox(
                "Seleccionar método de pago",
                ["Efectivo", "Tarjeta de Crédito", "Tarjeta de Débito", "Transferencia", "Otro"]
            )
            otro_metodo = metodo_pago
            if metodo_pago == "Otro":
                otro_metodo = st.text_input("Especificar método de pago", value="Otro")
        
        # Botones de acción
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("⬅️ Volver", use_container_width=True):
                st.session_state.checkout_step = 1
                st.session_state.checkout_estancia = None
                st.rerun()
        
        with col2:
            if st.button("💰 Procesar Pago y Check-Out", type="primary", use_container_width=True):
                with st.spinner("Procesando facturación..."):
                    # Generar factura
                    factura_data = {
                        'estancia_id': estancia['estancia_id'],
                        'huesped_id': estancia.get('huesped_id'),
                        'subtotal': subtotal,
                        'impuestos': impuestos,
                        'total': total,
                        'metodo_pago': metodo_pago if metodo_pago != "Otro" else otro_metodo,
                        'noches': noches,
                        'precio_noche': estancia['precio_acordado_por_noche'],
                        'consumos': df_consumos.to_dict('records') if not df_consumos.empty else []
                    }
                    
                    factura_id = generar_factura(factura_data)
                    
                    if factura_id:
                        st.session_state.factura_generada = {
                            'factura_id': factura_id,
                            'estancia': estancia,
                            'total': total,
                            'metodo_pago': metodo_pago
                        }
                        st.session_state.checkout_step = 3
                        st.rerun()
                    else:
                        st.error("Error al generar la factura")
        
        with col3:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.checkout_step = 1
                st.session_state.checkout_estancia = None
                st.rerun()

# Paso 3: Confirmación y descarga de factura
elif st.session_state.checkout_step == 3 and 'factura_generada' in st.session_state:
    factura = st.session_state.factura_generada
    
    st.success("✅ ¡Check-Out completado exitosamente!")
    st.balloons()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Resumen de la Factura")
        st.write(f"**Huésped:** {factura['estancia']['nombre_completo']}")
        st.write(f"**Habitación:** {factura['estancia']['numero_habitacion']}")
        st.write(f"**Total Pagado:** {formatear_moneda(factura['total'])}")
        st.write(f"**Método de Pago:** {factura['metodo_pago']}")
    
    with col2:
        st.markdown("### Acciones")
        
        # Generar PDF
        pdf_bytes = generar_factura_pdf(factura['estancia']['estancia_id'])
        
        if pdf_bytes:
            st.download_button(
                label="📥 Descargar Factura PDF",
                data=pdf_bytes,
                file_name=f"factura_{factura['estancia']['estancia_id']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        if st.button("🆕 Nuevo Check-Out", use_container_width=True):
            st.session_state.checkout_step = 1
            st.session_state.checkout_estancia = None
            del st.session_state.factura_generada
            st.rerun()