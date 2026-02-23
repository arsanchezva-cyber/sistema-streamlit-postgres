from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Huesped:
    """Modelo de datos para huésped."""
    
    id: Optional[str] = None
    nombre_completo: str = ""
    tipo_documento: str = ""
    numero_documento: str = ""
    email: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    es_frecuente: bool = False
    creado_en: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data):
        """Crea una instancia desde un diccionario."""
        return cls(
            id=data.get('id'),
            nombre_completo=data.get('nombre_completo', ''),
            tipo_documento=data.get('tipo_documento', ''),
            numero_documento=data.get('numero_documento', ''),
            email=data.get('email'),
            telefono=data.get('telefono'),
            direccion=data.get('direccion'),
            fecha_nacimiento=data.get('fecha_nacimiento'),
            es_frecuente=data.get('es_frecuente', False),
            creado_en=data.get('creado_en')
        )
    
    def to_dict(self):
        """Convierte la instancia a diccionario."""
        return {
            'id': self.id,
            'nombre_completo': self.nombre_completo,
            'tipo_documento': self.tipo_documento,
            'numero_documento': self.numero_documento,
            'email': self.email,
            'telefono': self.telefono,
            'direccion': self.direccion,
            'fecha_nacimiento': self.fecha_nacimiento,
            'es_frecuente': self.es_frecuente
        }
    
    def validar(self):
        """Valida los datos del huésped."""
        errores = []
        
        if not self.nombre_completo:
            errores.append("El nombre es obligatorio")
        
        if not self.tipo_documento:
            errores.append("El tipo de documento es obligatorio")
        
        if not self.numero_documento:
            errores.append("El número de documento es obligatorio")
        
        if self.email and '@' not in self.email:
            errores.append("El email no es válido")
        
        return errores
    
    def __str__(self):
        return f"{self.nombre_completo} ({self.tipo_documento}: {self.numero_documento})"