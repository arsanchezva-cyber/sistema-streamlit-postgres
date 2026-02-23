from dataclasses import dataclass
from typing import Optional, List

@dataclass
class TipoHabitacion:
    """Modelo de datos para tipo de habitación."""
    
    id: Optional[int] = None
    nombre: str = ""
    descripcion: Optional[str] = None
    capacidad_maxima: int = 2
    precio_base_por_noche: float = 0.0
    activo: bool = True
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id'),
            nombre=data.get('nombre', ''),
            descripcion=data.get('descripcion'),
            capacidad_maxima=data.get('capacidad_maxima', 2),
            precio_base_por_noche=float(data.get('precio_base_por_noche', 0)),
            activo=data.get('activo', True)
        )
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'capacidad_maxima': self.capacidad_maxima,
            'precio_base_por_noche': self.precio_base_por_noche,
            'activo': self.activo
        }

@dataclass
class Habitacion:
    """Modelo de datos para habitación."""
    
    id: Optional[int] = None
    numero_habitacion: str = ""
    piso: int = 1
    tipo_habitacion_id: Optional[int] = None
    tipo_habitacion: Optional[TipoHabitacion] = None
    estado_actual: str = "disponible"
    activa: bool = True
    notas: Optional[str] = None
    
    ESTADOS_VALIDOS = ['disponible', 'ocupada', 'mantenimiento', 'reservada', 'limpieza']
    
    @classmethod
    def from_dict(cls, data):
        habitacion = cls(
            id=data.get('id'),
            numero_habitacion=data.get('numero_habitacion', ''),
            piso=data.get('piso', 1),
            tipo_habitacion_id=data.get('tipo_habitacion_id'),
            estado_actual=data.get('estado_actual', 'disponible'),
            activa=data.get('activa', True),
            notas=data.get('notas')
        )
        
        if 'tipo_habitacion' in data and data['tipo_habitacion']:
            habitacion.tipo_habitacion = TipoHabitacion.from_dict(data['tipo_habitacion'])
        
        return habitacion
    
    def to_dict(self):
        result = {
            'id': self.id,
            'numero_habitacion': self.numero_habitacion,
            'piso': self.piso,
            'tipo_habitacion_id': self.tipo_habitacion_id,
            'estado_actual': self.estado_actual,
            'activa': self.activa,
            'notas': self.notas
        }
        
        if self.tipo_habitacion:
            result['tipo_habitacion'] = self.tipo_habitacion.to_dict()
        
        return result
    
    def cambiar_estado(self, nuevo_estado):
        """Cambia el estado de la habitación si es válido."""
        if nuevo_estado in self.ESTADOS_VALIDOS:
            self.estado_actual = nuevo_estado
            return True
        return False
    
    def esta_disponible(self):
        """Verifica si la habitación está disponible."""
        return self.activa and self.estado_actual == 'disponible'
    
    def __str__(self):
        return f"Habitación {self.numero_habitacion} ({self.estado_actual})"