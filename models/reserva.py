from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from .huesped import Huesped

@dataclass
class Reserva:
    """Modelo de datos para reserva."""
    
    id: Optional[str] = None
    codigo_reserva: str = ""
    huesped_id: Optional[str] = None
    huesped: Optional[Huesped] = None
    tipo_habitacion_solicitada_id: Optional[int] = None
    fecha_checkin: date = None
    fecha_checkout: date = None
    numero_adultos: int = 1
    numero_ninos: int = 0
    estado_reserva: str = "confirmada"
    observaciones: Optional[str] = None
    creado_en: Optional[datetime] = None
    
    ESTADOS_VALIDOS = ['confirmada', 'checkeado', 'cancelada', 'no_show']
    
    @classmethod
    def from_dict(cls, data):
        reserva = cls(
            id=data.get('id'),
            codigo_reserva=data.get('codigo_reserva', ''),
            huesped_id=data.get('huesped_id'),
            tipo_habitacion_solicitada_id=data.get('tipo_habitacion_solicitada_id'),
            fecha_checkin=data.get('fecha_checkin'),
            fecha_checkout=data.get('fecha_checkout'),
            numero_adultos=data.get('numero_adultos', 1),
            numero_ninos=data.get('numero_ninos', 0),
            estado_reserva=data.get('estado_reserva', 'confirmada'),
            observaciones=data.get('observaciones'),
            creado_en=data.get('creado_en')
        )
        
        if 'huesped' in data and data['huesped']:
            reserva.huesped = Huesped.from_dict(data['huesped'])
        
        return reserva
    
    def to_dict(self):
        result = {
            'id': self.id,
            'codigo_reserva': self.codigo_reserva,
            'huesped_id': self.huesped_id,
            'tipo_habitacion_solicitada_id': self.tipo_habitacion_solicitada_id,
            'fecha_checkin': self.fecha_checkin,
            'fecha_checkout': self.fecha_checkout,
            'numero_adultos': self.numero_adultos,
            'numero_ninos': self.numero_ninos,
            'estado_reserva': self.estado_reserva,
            'observaciones': self.observaciones
        }
        
        if self.huesped:
            result['huesped'] = self.huesped.to_dict()
        
        return result
    
    @property
    def total_personas(self):
        """Retorna el total de personas."""
        return self.numero_adultos + self.numero_ninos
    
    @property
    def noches(self):
        """Retorna el número de noches de la reserva."""
        if self.fecha_checkin and self.fecha_checkout:
            return (self.fecha_checkout - self.fecha_checkin).days
        return 0
    
    def validar(self):
        """Valida los datos de la reserva."""
        errores = []
        
        if not self.huesped_id and not self.huesped:
            errores.append("Se requiere un huésped")
        
        if not self.tipo_habitacion_solicitada_id:
            errores.append("Se requiere un tipo de habitación")
        
        if not self.fecha_checkin or not self.fecha_checkout:
            errores.append("Las fechas de check-in y check-out son obligatorias")
        elif self.fecha_checkin >= self.fecha_checkout:
            errores.append("La fecha de check-out debe ser posterior al check-in")
        
        if self.numero_adultos < 1:
            errores.append("Debe haber al menos 1 adulto")
        
        if self.estado_reserva not in self.ESTADOS_VALIDOS:
            errores.append(f"Estado no válido: {self.estado_reserva}")
        
        return errores
    
    def __str__(self):
        return f"Reserva {self.codigo_reserva} - {self.fecha_checkin} a {self.fecha_checkout}"