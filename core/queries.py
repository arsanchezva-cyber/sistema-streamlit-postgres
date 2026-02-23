# Consultas SQL reutilizables

# ==================== CONSULTAS DE HUÉSPEDES ====================

GET_HUESPED_BY_DOCUMENTO = """
SELECT id, nombre_completo, tipo_documento, numero_documento, 
       email, telefono, direccion, fecha_nacimiento, es_frecuente
FROM huespedes
WHERE tipo_documento = %s AND numero_documento = %s
"""

CREATE_HUESPED = """
INSERT INTO huespedes (nombre_completo, tipo_documento, numero_documento, 
                      email, telefono, direccion, fecha_nacimiento)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""

UPDATE_HUESPED = """
UPDATE huespedes
SET nombre_completo = %s, email = %s, telefono = %s, 
    direccion = %s, fecha_nacimiento = %s
WHERE id = %s
"""

# ==================== CONSULTAS DE HABITACIONES ====================

GET_HABITACIONES_DISPONIBLES = """
SELECT h.id, h.numero_habitacion, h.piso, t.nombre as tipo, 
       t.precio_base_por_noche, t.capacidad_maxima
FROM habitaciones h
JOIN tipos_habitacion t ON h.tipo_habitacion_id = t.id
WHERE h.activa = true 
AND h.estado_actual NOT IN ('ocupada', 'mantenimiento')
AND h.id NOT IN (
    SELECT e.habitacion_id
    FROM estancias e
    WHERE e.estado_estancia = 'activa'
    AND e.fecha_checkin_esperada < %s
    AND e.fecha_checkout_esperada > %s
)
AND (%s IS NULL OR h.tipo_habitacion_id = %s)
ORDER BY h.numero_habitacion
"""

GET_HABITACIONES_POR_TIPO = """
SELECT t.nombre as tipo, COUNT(h.id) as total,
       SUM(CASE WHEN h.estado_actual = 'ocupada' THEN 1 ELSE 0 END) as ocupadas
FROM tipos_habitacion t
LEFT JOIN habitaciones h ON t.id = h.tipo_habitacion_id
WHERE t.activo = true
GROUP BY t.id, t.nombre
ORDER BY t.nombre
"""

# ==================== CONSULTAS DE RESERVAS ====================

GET_RESERVAS_ACTIVAS = """
SELECT r.id, r.codigo_reserva, h.nombre_completo, 
       r.fecha_checkin, r.fecha_checkout, r.estado_reserva
FROM reservas r
JOIN huespedes h ON r.huesped_id = h.id
WHERE r.estado_reserva = 'confirmada'
AND r.fecha_checkin <= CURRENT_DATE + INTERVAL '7 days'
ORDER BY r.fecha_checkin
"""

VERIFICAR_DISPONIBILIDAD_RESERVA = """
SELECT COUNT(*) as conflictos
FROM reservas r
WHERE r.estado_reserva = 'confirmada'
AND r.tipo_habitacion_solicitada_id = %s
AND r.fecha_checkin < %s
AND r.fecha_checkout > %s
"""

# ==================== CONSULTAS DE ESTANCIAS ====================

GET_ESTANCIAS_ACTIVAS = """
SELECT e.id, h.nombre_completo, hab.numero_habitacion,
       e.fecha_checkin_real, e.fecha_checkout_esperada,
       t.nombre as tipo_habitacion
FROM estancias e
JOIN huespedes h ON e.huesped_id = h.id
JOIN habitaciones hab ON e.habitacion_id = hab.id
JOIN tipos_habitacion t ON hab.tipo_habitacion_id = t.id
WHERE e.estado_estancia = 'activa'
ORDER BY h.nombre_completo
"""

GET_CONSUMOS_ESTANCIA = """
SELECT id, descripcion, cantidad, precio_unitario, fecha_consumo
FROM consumos
WHERE estancia_id = %s
ORDER BY fecha_consumo DESC
"""

# ==================== CONSULTAS DE FACTURACIÓN ====================

GET_FACTURA_BY_ESTANCIA = """
SELECT f.id, f.numero_factura, f.fecha_emision, f.subtotal, 
       f.impuestos, f.total, f.metodo_pago, f.estado_pago
FROM facturas f
WHERE f.estancia_id = %s
"""

CREATE_FACTURA = """
INSERT INTO facturas (numero_factura, estancia_id, huesped_id, 
                     subtotal, impuestos, total, metodo_pago, estado_pago)
VALUES (%s, %s, %s, %s, %s, %s, %s, 'pagado')
RETURNING id
"""

CREATE_DETALLE_FACTURA = """
INSERT INTO detalles_factura (factura_id, descripcion, cantidad, 
                             precio_unitario, importe_total, tipo_detalle, consumo_id)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

# ==================== CONSULTAS DE ESTADÍSTICAS ====================

GET_OCUPACION_POR_DIA = """
SELECT 
    DATE(e.fecha_checkin_esperada) as fecha,
    COUNT(DISTINCT e.habitacion_id) as ocupadas
FROM estancias e
WHERE e.fecha_checkin_esperada BETWEEN %s AND %s
GROUP BY DATE(e.fecha_checkin_esperada)
ORDER BY fecha
"""

GET_INGRESOS_POR_MES = """
SELECT 
    EXTRACT(YEAR FROM fecha_emision) as año,
    EXTRACT(MONTH FROM fecha_emision) as mes,
    SUM(total) as ingresos
FROM facturas
WHERE fecha_emision BETWEEN %s AND %s
AND estado_pago = 'pagado'
GROUP BY EXTRACT(YEAR FROM fecha_emision), EXTRACT(MONTH FROM fecha_emision)
ORDER BY año, mes
"""