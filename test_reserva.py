from services.reserva_service import ReservaService
from models import Reserva, Huesped
from datetime import date, timedelta
import streamlit as st

# Configurar para prueba
st.set_page_config = lambda **kwargs: None

# Crear datos de prueba
huesped = Huesped(
    nombre_completo="Test Usuario",
    tipo_documento="DNI",
    numero_documento="99999999",
    email="test@email.com",
    telefono="555-9999"
)

reserva = Reserva(
    fecha_checkin=date.today() + timedelta(days=5),
    fecha_checkout=date.today() + timedelta(days=8),
    numero_adultos=2,
    numero_ninos=0,
    tipo_habitacion_solicitada_id=1,  # ID de Habitación Estándar
    estado_reserva="confirmada"
)

# Intentar crear reserva
print("Intentando crear reserva de prueba...")
resultado = ReservaService.crear_reserva(reserva, huesped)

if resultado:
    print(f"✅ Reserva creada con ID: {resultado}")
else:
    print("❌ Error al crear reserva")