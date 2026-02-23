from datetime import datetime, date
import locale
import re

# Intentar configurar locale para formato de moneda
try:
    locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Spanish_Spain.1252')
    except:
        pass

def formatear_moneda(valor: float) -> str:
    """
    Formatea un valor numérico como moneda.
    Ejemplo: 1234.56 -> "$1,234.56"
    """
    if valor is None:
        return "$0.00"
    
    try:
        # Formato simple sin locale para evitar problemas
        return f"${valor:,.2f}"
    except:
        return f"${valor:.2f}"

def formatear_fecha(fecha, formato: str = "%d/%m/%Y %H:%M") -> str:
    """
    Formatea una fecha en el formato especificado.
    Si la fecha es None, retorna 'No especificado'.
    """
    if fecha is None:
        return "No especificado"
    
    if isinstance(fecha, str):
        try:
            fecha = datetime.fromisoformat(fecha)
        except:
            return fecha
    
    if isinstance(fecha, (datetime, date)):
        return fecha.strftime(formato)
    
    return str(fecha)

def formatear_fecha_corta(fecha) -> str:
    """Formato corto de fecha (DD/MM/YYYY)."""
    return formatear_fecha(fecha, "%d/%m/%Y")

def calcular_dias_entre(fecha_inicio, fecha_fin) -> int:
    """Calcula el número de días entre dos fechas."""
    if not fecha_inicio or not fecha_fin:
        return 0
    
    if isinstance(fecha_inicio, str):
        fecha_inicio = datetime.fromisoformat(fecha_inicio).date()
    if isinstance(fecha_fin, str):
        fecha_fin = datetime.fromisoformat(fecha_fin).date()
    
    return (fecha_fin - fecha_inicio).days

def validar_fechas(fecha_inicio, fecha_fin) -> tuple[bool, str]:
    """
    Valida que la fecha de inicio sea anterior a la fecha de fin.
    Retorna (es_valido, mensaje_error)
    """
    if not fecha_inicio or not fecha_fin:
        return False, "Ambas fechas son requeridas"
    
    if fecha_inicio >= fecha_fin:
        return False, "La fecha de fin debe ser posterior a la fecha de inicio"
    
    return True, ""

def truncar_texto(texto: str, longitud: int = 50) -> str:
    """Trunca un texto a la longitud especificada."""
    if not texto:
        return ""
    if len(texto) <= longitud:
        return texto
    return texto[:longitud-3] + "..."

def limpiar_telefono(telefono: str) -> str:
    """Limpia un número de teléfono, dejando solo dígitos."""
    if not telefono:
        return ""
    return re.sub(r'\D', '', telefono)

def formatear_telefono(telefono: str) -> str:
    """Formatea un número de teléfono (formato argentino por defecto)."""
    if not telefono:
        return ""
    
    # Limpiar el teléfono
    tel = limpiar_telefono(telefono)
    
    # Formato según longitud
    if len(tel) == 10:  # Formato: (XX) XXXX-XXXX
        return f"({tel[:2]}) {tel[2:6]}-{tel[6:]}"
    elif len(tel) == 8:  # Formato: XXXX-XXXX
        return f"{tel[:4]}-{tel[4:]}"
    else:
        return telefono

def generar_resumen_consumo(consumos: list) -> dict:
    """
    Genera un resumen de consumos.
    Retorna total y cantidad por tipo.
    """
    if not consumos:
        return {'total': 0, 'cantidad': 0, 'items': []}
    
    total = sum(c.get('cantidad', 0) * c.get('precio_unitario', 0) for c in consumos)
    
    return {
        'total': total,
        'cantidad': len(consumos),
        'items': consumos
    }