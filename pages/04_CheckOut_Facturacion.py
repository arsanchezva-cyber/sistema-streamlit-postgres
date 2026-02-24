import streamlit as st
import pandas as pd
from datetime import datetime
from core.database import run_query
from services.facturacion_service import FacturacionService
from services.report_service import generar_factura_pdf
from utils.helpers import formatear_moneda
import decimal

st.set_page_config(page_title="Check-Out", page_icon="❌", layout="wide")

st.title("❌ Check-Out y Facturación")
st.markdown("---")

# Inicializar estado
if 'checkout_estancia' not in st.session_state:
    st.session_state.checkout_estancia = None
if 'checkout_step' not in st.session_state:
    st.session_state.checkout_step = 1

# Función para convertir decimal a float
def a_float(valor):
    """Convierte decimal.Decimal a float de forma segura."""
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    return float(valor) if valor else 0.0

# Función para buscar estancias activas
def buscar_estancias_activas(filtro=None, valor=None):
    """Busca estancias activas y reservas pendientes de check-in."""
    
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
        END as codigo_referencia,
        'activa' as estado
    FROM estancias e
    JOIN huespedes h ON e.huesped_id = h.id
    JOIN habitaciones hab ON e.habitacion_id = hab.id
    JOIN tipos_habitacion t ON hab.tipo_habitacion_id = t.id
    LEFT JOIN reservas r ON e.reserva_id = r.id
    WHERE e.estado_estancia = 'activa'
    
    UNION ALL
    
    SELECT 
        NULL as estancia_id,
        h.id as huesped_id,
        h.nombre_completo,
        h.tipo_documento,
        h.numero_documento,
        h.telefono,
        NULL as numero_habitacion,
        t.nombre as tipo_habitacion,
        NULL as fecha_checkin_real,
        r.fecha_checkout as fecha_checkout_esperada,
        r.numero_adultos,
        r.numero_ninos,
        t.precio_base_por_noche as precio_acordado_por_noche,
        r.observaciones,
        r.codigo_reserva as codigo_referencia,
        'reserva_confirmada' as estado
    FROM reservas r
    JOIN huespedes h ON r.huesped_id = h.id
    JOIN tipos_habitacion t ON r.tipo_habitacion_solicitada_id = t.id
    LEFT JOIN estancias e ON r.id = e.reserva_id
    WHERE r.estado_reserva = 'confirmada'
    AND e.id IS NULL
    AND r.fecha_checkin <= CURRENT_DATE
    """
    
    params = []
    
    if filtro and valor:
        if filtro == "Habitación":
            # Para habitación, solo aplica a estancias
            query = query.replace("WHERE e.estado_estancia = 'activa'", 
                                 "WHERE e.estado_estancia = 'activa' AND hab.numero_habitacion = %s")
            params.append(valor)
        elif filtro == "Documento":
            query += " AND h.numero_documento = %s"
            params.append(valor)
        elif filtro == "Nombre":
            query += " AND h.nombre_completo ILIKE %s"
            params.append(f"%{valor}%")
    
    query += " ORDER BY nombre_completo"
    
    result = run_query(query, tuple(params) if params else None)
    return pd.DataFrame(result) if result else pd.DataFrame()

# Función para agregar consumo
def agregar_consumo(estancia_id, descripcion, cantidad, precio_unitario):
    query = """
    INSERT INTO consumos (estancia_id, descripcion, cantidad, precio_unitario)
    VALUES (%s, %s, %s, %s)
    RETURNING id
    """
    # Convertir precio_unitario a Decimal para PostgreSQL
    if isinstance(precio_unitario, float):
        precio_unitario = decimal.Decimal(str(precio_unitario))
    result = run_query(query, (estancia_id, descripcion, cantidad, precio_unitario))
    return result[0]['id'] if result else None

# Función para obtener consumos de una estancia
def get_consumos_estancia(estancia_id):
    """Obtiene los consumos de una estancia."""
    return FacturacionService.get_consumos_estancia(estancia_id)

# Función para generar factura
def generar_factura(data):
    """Genera una factura para una estancia."""
    return FacturacionService.generar_factura(data)

# Función para formatear fecha de forma segura
def formatear_fecha_segura(fecha, formato="%d/%m/%Y %H:%M"):
    """Formatea una fecha de forma segura, manejando valores nulos."""
    if fecha is None or pd.isna(fecha):
        return "Pendiente"
    try:
        return pd.to_datetime(fecha).strftime(formato)
    except:
        return "Fecha inválida"

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
                    # Usar la función segura para formatear fechas
                    checkin = formatear_fecha_segura(row['fecha_checkin_real'], "%d/%m/%Y %H:%M")
                    checkout = formatear_fecha_segura(row['fecha_checkout_esperada'], "%d/%m/%Y")
                    st.write(f"Check-in: {checkin}")
                    st.write(f"Check-out esperado: {checkout}")
                
                with col3:
                    # Calcular noches solo si fecha_checkin_real no es nulo
                    if pd.notna(row['fecha_checkin_real']):
                        noches = (datetime.now().date() - pd.to_datetime(row['fecha_checkin_real']).date()).days
                        noches = max(1, noches)
                    else:
                        noches = 1
                    st.metric("Noches", noches)
                
                with col4:
                    # CORREGIDO: Convertir a float para mostrar
                    if pd.notna(row['precio_acordado_por_noche']):
                        precio = a_float(row['precio_acordado_por_noche'])
                        total_estadia = noches * precio
                    else:
                        total_estadia = 0
                    st.metric("Total Estadia", formatear_moneda(total_estadia))
                
                with col5:
                    # Solo permitir seleccionar si es una estancia activa (no reserva)
                    if row['estado'] == 'activa' and pd.notna(row['estancia_id']):
                        if st.button("Seleccionar", key=f"sel_{row['estancia_id']}"):
                            st.session_state.checkout_estancia = row.to_dict()
                            st.session_state.checkout_step = 2
                            st.rerun()
                    else:
                        st.info("Requiere Check-In")

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
        
        # Obtener consumos (puede ser lista o DataFrame)
        consumos_list = get_consumos_estancia(estancia['estancia_id'])
        
        # Convertir a DataFrame si es lista
        if isinstance(consumos_list, list):
            df_consumos = pd.DataFrame(consumos_list) if consumos_list else pd.DataFrame()
        else:
            df_consumos = consumos_list if consumos_list is not None else pd.DataFrame()
        
        if not df_consumos.empty:
            # CORREGIDO: Convertir columnas decimal a float
            for col in ['precio_unitario', 'cantidad']:
                if col in df_consumos.columns:
                    df_consumos[col] = df_consumos[col].apply(a_float)
            
            # Calcular total
            df_consumos['total'] = df_consumos['cantidad'] * df_consumos['precio_unitario']
            total_consumos = df_consumos['total'].sum()
            
            # Mostrar tabla
            df_display = df_consumos.copy()
            if 'fecha_consumo' in df_display.columns:
                df_display['fecha_consumo'] = pd.to_datetime(df_display['fecha_consumo']).dt.strftime('%d/%m/%Y %H:%M')
            
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
        
        # CORREGIDO: Convertir todos los valores decimal a float
        precio_noche = a_float(estancia['precio_acordado_por_noche'])
        
        # Calcular noches de forma segura
        if pd.notna(estancia['fecha_checkin_real']):
            noches = (datetime.now().date() - pd.to_datetime(estancia['fecha_checkin_real']).date()).days
            noches = max(1, noches)
        else:
            noches = 1
        
        total_alojamiento = noches * precio_noche
        
        # Obtener consumos y convertir a float
        consumos_list = get_consumos_estancia(estancia['estancia_id'])
        
        if isinstance(consumos_list, list):
            df_consumos = pd.DataFrame(consumos_list) if consumos_list else pd.DataFrame()
        else:
            df_consumos = consumos_list if consumos_list is not None else pd.DataFrame()
        
        # Calcular total de consumos de forma segura
        total_consumos = 0
        if not df_consumos.empty:
            # Convertir columnas a float
            for col in ['precio_unitario', 'cantidad']:
                if col in df_consumos.columns:
                    df_consumos[col] = df_consumos[col].apply(a_float)
            total_consumos = (df_consumos['cantidad'] * df_consumos['precio_unitario']).sum()
        
        # CORREGIDO: Convertir subtotal a float antes de multiplicar
        subtotal = float(total_alojamiento + total_consumos)
        impuestos = subtotal * 0.16  # 16% IVA - AHORA FUNCIONA
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
                    # Preparar datos de consumos para la factura
                    consumos_para_factura = []
                    if not df_consumos.empty:
                        # Asegurar que todos los valores sean float
                        df_temp = df_consumos.copy()
                        for col in ['precio_unitario', 'cantidad']:
                            if col in df_temp.columns:
                                df_temp[col] = df_temp[col].apply(a_float)
                        
                        # Convertir a diccionarios sin incluir campos problemáticos
                        for _, row in df_temp.iterrows():
                            consumos_para_factura.append({
                                'descripcion': row['descripcion'],
                                'cantidad': float(row['cantidad']),
                                'precio_unitario': float(row['precio_unitario'])
                                # NO incluir 'id' aquí para evitar errores de FK
                            })
                    
                    # Generar factura - INDENTACIÓN CORREGIDA
                    factura_data = {
                        'estancia_id': estancia['estancia_id'],
                        'huesped_id': estancia.get('huesped_id'),
                        'subtotal': float(subtotal),
                        'impuestos': float(impuestos),
                        'total': float(total),
                        'metodo_pago': metodo_pago if metodo_pago != "Otro" else otro_metodo,
                        'noches': noches,
                        'precio_noche': float(precio_noche),
                        'total_alojamiento': float(total_alojamiento),
                        'consumos': consumos_para_factura
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