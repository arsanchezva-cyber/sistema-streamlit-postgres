-- =====================================================
-- SISTEMA DE GESTIÓN HOTELERA (SGH) - ESQUEMA COMPLETO
-- Para BD existente: ALTER TABLE reservas ALTER COLUMN codigo_reserva TYPE VARCHAR(30);
-- =====================================================

-- Extensión para UUID, mejora la seguridad y escalabilidad
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------
-- Tabla: tipos_habitacion (Catálogo)
-- -----------------------------------------------------
CREATE TABLE tipos_habitacion (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE, -- Ej: 'Habitación Estándar', 'Suite Junior'
    descripcion TEXT,
    capacidad_maxima INT NOT NULL CHECK (capacidad_maxima > 0),
    precio_base_por_noche DECIMAL(10, 2) NOT NULL CHECK (precio_base_por_noche >= 0),
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE tipos_habitacion IS 'Catálogo de tipos de habitación con precio base y capacidad.';
COMMENT ON COLUMN tipos_habitacion.precio_base_por_noche IS 'Puede ser modificado por ofertas/temporadas en la práctica, pero sirve como precio por defecto.';

-- -----------------------------------------------------
-- Tabla: habitaciones (Inventario físico)
-- -----------------------------------------------------
CREATE TABLE habitaciones (
    id SERIAL PRIMARY KEY,
    numero_habitacion VARCHAR(10) NOT NULL UNIQUE,
    piso INT NOT NULL,
    tipo_habitacion_id INT NOT NULL REFERENCES tipos_habitacion(id) ON DELETE RESTRICT,
    estado_actual VARCHAR(20) DEFAULT 'disponible' 
        CHECK (estado_actual IN ('disponible', 'ocupada', 'mantenimiento', 'reservada', 'limpieza')),
    activa BOOLEAN DEFAULT TRUE,
    notas TEXT,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE habitaciones IS 'Inventario físico de cada habitación del hotel.';
CREATE INDEX idx_habitaciones_estado ON habitaciones(estado_actual);
CREATE INDEX idx_habitaciones_tipo ON habitaciones(tipo_habitacion_id);

-- -----------------------------------------------------
-- Tabla: huespedes (Maestro de clientes)
-- -----------------------------------------------------
CREATE TABLE huespedes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre_completo VARCHAR(150) NOT NULL,
    tipo_documento VARCHAR(20) NOT NULL, -- Ej: 'DNI', 'Pasaporte', 'Cédula'
    numero_documento VARCHAR(50) NOT NULL,
    email VARCHAR(150),
    telefono VARCHAR(30),
    direccion TEXT,
    fecha_nacimiento DATE,
    es_frecuente BOOLEAN DEFAULT FALSE,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tipo_documento, numero_documento) -- Evita duplicados por documento
);

COMMENT ON TABLE huespedes IS 'Información maestra de los huéspedes/clientes.';
CREATE INDEX idx_huespedes_documento ON huespedes(tipo_documento, numero_documento);
CREATE INDEX idx_huespedes_email ON huespedes(email);

-- -----------------------------------------------------
-- Tabla: reservas (Reservas anticipadas)
-- -----------------------------------------------------
CREATE TABLE reservas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_reserva VARCHAR(30) UNIQUE NOT NULL, -- Código amigable para el cliente
    huesped_id UUID NOT NULL REFERENCES huespedes(id) ON DELETE RESTRICT,
    tipo_habitacion_solicitada_id INT NOT NULL REFERENCES tipos_habitacion(id) ON DELETE RESTRICT,
    fecha_checkin DATE NOT NULL,
    fecha_checkout DATE NOT NULL CHECK (fecha_checkout > fecha_checkin),
    numero_adultos INT NOT NULL DEFAULT 1 CHECK (numero_adultos >= 0),
    numero_ninos INT NOT NULL DEFAULT 0 CHECK (numero_ninos >= 0),
    estado_reserva VARCHAR(20) DEFAULT 'confirmada'
        CHECK (estado_reserva IN ('confirmada', 'checkeado', 'cancelada', 'no_show')),
    observaciones TEXT,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Asegura que la reserva no sea demasiado larga (opcional)
    CHECK (fecha_checkout - fecha_checkin <= 30) 
);

COMMENT ON TABLE reservas IS 'Registro de reservas confirmadas.';
COMMENT ON COLUMN reservas.estado_reserva IS 'checkeado: cuando el huésped ya hizo check-in.';
CREATE INDEX idx_reservas_fechas ON reservas(fecha_checkin, fecha_checkout);
CREATE INDEX idx_reservas_huesped ON reservas(huesped_id);
CREATE INDEX idx_reservas_estado ON reservas(estado_reserva);

-- -----------------------------------------------------
-- Tabla: estancias (Corazón operativo: Check-in / Check-out)
-- -----------------------------------------------------
CREATE TABLE estancias (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reserva_id UUID UNIQUE REFERENCES reservas(id) ON DELETE SET NULL, -- Una estancia puede venir de una reserva o ser walk-in
    huesped_id UUID NOT NULL REFERENCES huespedes(id) ON DELETE RESTRICT,
    habitacion_id INT NOT NULL REFERENCES habitaciones(id) ON DELETE RESTRICT,
    fecha_checkin_real TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_checkout_real TIMESTAMP, -- Se llena al hacer checkout
    fecha_checkin_esperada DATE NOT NULL, -- Copia de la reserva o fecha de walk-in
    fecha_checkout_esperada DATE NOT NULL, -- Copia de la reserva o fecha de walk-in
    numero_adultos INT NOT NULL,
    numero_ninos INT NOT NULL,
    precio_acordado_por_noche DECIMAL(10, 2) NOT NULL, -- Precio al momento del check-in (puede diferir del base)
    estado_estancia VARCHAR(20) DEFAULT 'activa'
        CHECK (estado_estancia IN ('activa', 'finalizada', 'cancelada')),
    observaciones TEXT,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Restricción para asegurar que checkout_real sea posterior a checkin_real
    CHECK (fecha_checkout_real IS NULL OR fecha_checkout_real > fecha_checkin_real)
);

COMMENT ON TABLE estancias IS 'Registro central de la ocupación física. Se crea en el Check-in.';
CREATE INDEX idx_estancias_activas ON estancias(estado_estancia) WHERE estado_estancia = 'activa';
CREATE INDEX idx_estancias_habitacion_activa ON estancias(habitacion_id) WHERE estado_estancia = 'activa';
CREATE INDEX idx_estancias_huesped ON estancias(huesped_id);
CREATE INDEX idx_estancias_fechas_esperadas ON estancias(fecha_checkin_esperada, fecha_checkout_esperada);

-- -----------------------------------------------------
-- Tabla: consumos (Cargos extras durante la estancia)
-- -----------------------------------------------------
CREATE TABLE consumos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estancia_id UUID NOT NULL REFERENCES estancias(id) ON DELETE CASCADE,
    descripcion VARCHAR(255) NOT NULL,
    cantidad INT NOT NULL DEFAULT 1 CHECK (cantidad > 0),
    precio_unitario DECIMAL(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    fecha_consumo TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE consumos IS 'Cargos adicionales (minibar, spa, etc.) durante la estancia.';
CREATE INDEX idx_consumos_estancia ON consumos(estancia_id);

-- -----------------------------------------------------
-- Tabla: facturas (Maestro de facturas)
-- -----------------------------------------------------
CREATE TABLE facturas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    numero_factura VARCHAR(50) UNIQUE NOT NULL, -- Número de factura legible para el fisco/cliente
    estancia_id UUID NOT NULL UNIQUE REFERENCES estancias(id) ON DELETE RESTRICT, -- Relación 1 a 1 con estancia
    huesped_id UUID NOT NULL REFERENCES huespedes(id) ON DELETE RESTRICT,
    fecha_emision TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal DECIMAL(10, 2) NOT NULL DEFAULT 0,
    impuestos DECIMAL(10, 2) NOT NULL DEFAULT 0,
    total DECIMAL(10, 2) NOT NULL DEFAULT 0,
    metodo_pago VARCHAR(30), -- Ej: 'Efectivo', 'Tarjeta', 'Transferencia'
    estado_pago VARCHAR(20) DEFAULT 'pendiente' CHECK (estado_pago IN ('pendiente', 'pagado', 'anulado')),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE facturas IS 'Cabecera de la factura generada en el Check-out.';
CREATE INDEX idx_facturas_huesped ON facturas(huesped_id);
CREATE INDEX idx_facturas_fecha ON facturas(fecha_emision);

-- -----------------------------------------------------
-- Tabla: detalles_factura (Líneas de la factura)
-- -----------------------------------------------------
CREATE TABLE detalles_factura (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    factura_id UUID NOT NULL REFERENCES facturas(id) ON DELETE CASCADE,
    descripcion TEXT NOT NULL, -- Ej: "Alojamiento (3 noches)", "Consumo: Minibar"
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    importe_total DECIMAL(10, 2) NOT NULL, -- cantidad * precio_unitario
    tipo_detalle VARCHAR(20) CHECK (tipo_detalle IN ('alojamiento', 'consumo')),
    consumo_id UUID REFERENCES consumos(id) ON DELETE SET NULL, -- Opcional, para trackear el consumo origen
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE detalles_factura IS 'Líneas detalladas que componen el total de la factura.';
CREATE INDEX idx_detalles_factura ON detalles_factura(factura_id);

-- =====================================================
-- FUNCIONES Y TRIGGERS (Ejemplo de automatización)
-- =====================================================

-- Función para actualizar el estado de la habitación a 'ocupada' al hacer check-in
CREATE OR REPLACE FUNCTION fn_actualizar_estado_habitacion_checkin()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE habitaciones SET estado_actual = 'ocupada' WHERE id = NEW.habitacion_id;
    -- Si la estancia viene de una reserva, actualizar estado de la reserva
    IF NEW.reserva_id IS NOT NULL THEN
        UPDATE reservas SET estado_reserva = 'checkeado' WHERE id = NEW.reserva_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_after_insert_estancia
    AFTER INSERT ON estancias
    FOR EACH ROW
    WHEN (NEW.estado_estancia = 'activa')
    EXECUTE FUNCTION fn_actualizar_estado_habitacion_checkin();

-- Función para liberar la habitación y actualizar estado al hacer checkout
CREATE OR REPLACE FUNCTION fn_actualizar_estado_habitacion_checkout()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.estado_estancia = 'finalizada' AND OLD.estado_estancia = 'activa' THEN
        UPDATE habitaciones SET estado_actual = 'limpieza' WHERE id = NEW.habitacion_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_after_update_estancia
    AFTER UPDATE OF estado_estancia ON estancias
    FOR EACH ROW
    WHEN (NEW.estado_estancia = 'finalizada')
    EXECUTE FUNCTION fn_actualizar_estado_habitacion_checkout();

-- =====================================================
-- ÍNDICES ADICIONALES PARA RENDIMIENTO
-- =====================================================

-- Índice compuesto para búsquedas de disponibilidad (muy común)
CREATE INDEX idx_reservas_fechas_tipo ON reservas(fecha_checkin, fecha_checkout, tipo_habitacion_solicitada_id);

-- Índice para búsqueda de estancias activas por habitación
CREATE INDEX idx_estancias_habitacion_fechas ON estancias(habitacion_id, fecha_checkin_esperada, fecha_checkout_esperada) WHERE estado_estancia = 'activa';
