import re
from datetime import date, datetime
from typing import Optional, Tuple

def validar_email(email: str) -> bool:
    """
    Valida que un email tenga formato correcto.
    Retorna True si es válido, False en caso contrario.
    """
    if not email:
        return False
    
    # Patrón básico de email
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(patron, email))

def validar_telefono(telefono: str) -> bool:
    """
    Valida que un teléfono tenga formato válido (solo dígitos y longitud adecuada).
    """
    if not telefono:
        return False
    
    # Eliminar caracteres no dígitos
    solo_digitos = re.sub(r'\D', '', telefono)
    
    # Longitud típica de teléfonos (8-15 dígitos)
    return 8 <= len(solo_digitos) <= 15

def validar_documento(tipo: str, numero: str) -> Tuple[bool, str]:
    """
    Valida un documento según su tipo.
    Retorna (es_valido, mensaje_error)
    """
    if not numero:
        return False, "El número de documento es requerido"
    
    # Limpiar el número
    numero_limpio = re.sub(r'\D', '', numero)
    
    if tipo == "DNI":
        if len(numero_limpio) not in [7, 8]:
            return False, "El DNI debe tener 7 u 8 dígitos"
    elif tipo == "Pasaporte":
        # Los pasaportes pueden tener letras y números
        if len(numero) < 6 or len(numero) > 15:
            return False, "El pasaporte debe tener entre 6 y 15 caracteres"
    elif tipo == "Cédula":
        if len(numero_limpio) not in [8, 9, 10]:
            return False, "La cédula debe tener entre 8 y 10 dígitos"
    
    return True, ""

def validar_fechas_reserva(
    fecha_checkin: date,
    fecha_checkout: date
) -> Tuple[bool, str]:
    """
    Valida las fechas de una reserva.
    Retorna (es_valido, mensaje_error)
    """
    hoy = date.today()
    
    if fecha_checkin < hoy:
        return False, "La fecha de check-in no puede ser anterior a hoy"
    
    if fecha_checkin >= fecha_checkout:
        return False, "La fecha de check-out debe ser posterior al check-in"
    
    # Máximo 30 días de estadía (opcional)
    if (fecha_checkout - fecha_checkin).days > 30:
        return False, "La estadía no puede exceder los 30 días"
    
    return True, ""

def validar_cantidad_personas(
    adultos: int,
    ninos: int,
    capacidad_maxima: int
) -> Tuple[bool, str]:
    """
    Valida que la cantidad de personas no exceda la capacidad.
    """
    total = adultos + ninos
    
    if adultos < 1:
        return False, "Debe haber al menos 1 adulto"
    
    if adultos < 0 or ninos < 0:
        return False, "Las cantidades no pueden ser negativas"
    
    if total > capacidad_maxima:
        return False, f"Capacidad máxima excedida. Máximo {capacidad_maxima} personas"
    
    return True, ""

def validar_entero_positivo(valor, nombre_campo: str) -> Tuple[bool, str]:
    """
    Valida que un valor sea un entero positivo.
    """
    try:
        num = int(valor)
        if num <= 0:
            return False, f"{nombre_campo} debe ser mayor a 0"
        return True, ""
    except (ValueError, TypeError):
        return False, f"{nombre_campo} debe ser un número válido"

def validar_precio(precio: float) -> Tuple[bool, str]:
    """
    Valida que un precio sea válido.
    """
    try:
        precio_float = float(precio)
        if precio_float < 0:
            return False, "El precio no puede ser negativo"
        if precio_float > 999999.99:
            return False, "El precio es demasiado alto"
        return True, ""
    except (ValueError, TypeError):
        return False, "El precio debe ser un número válido"

def sanitizar_input(texto: str) -> str:
    """
    Sanitiza texto de entrada eliminando caracteres peligrosos.
    """
    if not texto:
        return ""
    
    # Eliminar caracteres de control y otros potencialmente peligrosos
    caracteres_prohibidos = r'[<>\"\'%;()&+]'
    texto_limpio = re.sub(caracteres_prohibidos, '', texto)
    
    # Limitar longitud
    if len(texto_limpio) > 500:
        texto_limpio = texto_limpio[:500]
    
    return texto_limpio.strip()